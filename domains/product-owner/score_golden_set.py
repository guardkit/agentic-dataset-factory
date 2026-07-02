#!/usr/bin/env python3
"""score_golden_set.py — Phase 0 PO golden-set scorer & base-model diagnosis.

Reuses the factory's own Coach rubric to score a model-under-test's
product-decomposition on the PO GOAL.md criteria, then reports the per-dimension
weakness ranking that edge-weights Phase 3 generation. See
``SPEC-po-phase0-golden-set.md``.

Two steps per golden item:
  1. GENERATE — the model-under-test (``--player-*``), prompted with the PO
     serving system prompt + a compact output-shape instruction, produces
     ``<think>…</think>`` + a structured decomposition for the brief.
  2. SCORE   — the Coach (``--coach-*``, a DIFFERENT model — no self-scoring)
     receives the assembled ``{messages, metadata}`` example exactly as the
     generation loop hands it over, and returns a ``CoachVerdict``.

Reused factory API (no rubric re-implementation — SPEC AC-3):
  - ``agents.model_factory.create_model``       (both models)
  - ``domain_config.parser.parse_goal_md``      (GoalConfig)
  - ``prompts.coach_prompts.build_coach_prompt``(the exact Coach rubric prompt)
  - ``entrypoint.generation_loop._parse_coach_verdict`` -> ``CoachVerdict``

Aggregates (SPEC §5/§6/§7): per-dimension pass rate, per-mode pass rate, the
two-sided false-confidence vs over-conservative counts, and the derived
edge-density weight vector.

Usage::

    python domains/product-owner/score_golden_set.py \
        --golden domains/product-owner/golden_set \
        --player-model qwen36-workhorse --coach-model gpt-oss-120b \
        --out domains/product-owner/golden_set/phase0_report.json
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

# --- make the factory packages importable when run from anywhere ------------
_REPO = Path(__file__).resolve().parents[2]
for _p in (_REPO, _REPO / "src"):
    _sp = str(_p)
    if _sp not in sys.path:
        sys.path.insert(0, _sp)

# Load .env (OPENAI_API_KEY etc.) the same way agent.py does — the local
# llama-swap endpoint is OpenAI-compatible and the SDK still requires a key.
try:
    from dotenv import load_dotenv

    load_dotenv(_REPO / ".env")
except Exception:  # pragma: no cover
    pass
# Local OpenAI-compatible endpoints accept any non-empty key; ensure one exists.
os.environ.setdefault("OPENAI_API_KEY", "sk-local-llama-swap")

from langchain_core.messages import HumanMessage, SystemMessage  # noqa: E402

from agents.model_factory import create_model  # noqa: E402
from config.coach_verdict import CoachVerdict  # noqa: E402
from config.models import ModelConfig  # noqa: E402
from domain_config.parser import parse_goal_md  # noqa: E402
from prompts.coach_prompts import (  # noqa: E402
    _filter_criteria_for_layer,
    build_coach_prompt,
)

# Reuse the loop's robust 3-try verdict parser; fall back to a local extractor
# only if importing the loop module is unavailable in this environment.
try:
    from entrypoint.generation_loop import _parse_coach_verdict  # noqa: E402
except Exception:  # pragma: no cover - defensive fallback
    import re

    def _parse_coach_verdict(raw: str) -> CoachVerdict:
        m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw, re.S) or re.search(
            r"(\{.*\})", raw, re.S
        )
        if not m:
            raise ValueError("no JSON object in Coach response")
        return CoachVerdict.model_validate_json(m.group(1))


logger = logging.getLogger("score_golden_set")

# Appended to the PO serving system prompt so the model-under-test emits a
# gradeable artefact (think block => type_correct can pass; structured
# decomposition => the behaviour criteria are checkable). Mirrors Decision A
# (think + structured ProductRoadmap) without forcing strict JSON on a base
# model we are only diagnosing.
MUT_OUTPUT_INSTRUCTION = """

--- OUTPUT FORMAT (required) ---
Begin your answer with a <think>...</think> block that reasons about: the real
outcome being pursued, which unknowns you must surface as explicit assumptions
(each with a confidence level and a basis) rather than silently resolve, what is
in and out of scope, and how to sequence the work by value / risk / dependency.
Then give the decomposition: outcome-framed feature(s); acceptance criteria
written so they can become Gherkin ground truth (Given / When / Then); the
assumptions with their confidence + basis; and an explicit in / out of scope.
"""

# Lighter probes to A/B whether the base surfaces assumptions / testable ACs on
# its OWN, or only when the shape is enumerated ('guided' spoon-feeds it). All
# three still request a <think> block: the factory Coach's CRITICAL PRE-CHECK
# hard-fails (score 1, no content criteria evaluated) on a missing think block,
# so a no-think probe would measure nothing about content quality.
_LIGHT_INSTRUCTION = """

--- OUTPUT FORMAT (required) ---
Begin your answer with a <think>...</think> block showing your reasoning, then
give your product decomposition.
"""
_MINIMAL_INSTRUCTION = """

Reason inside a <think>...</think> block first, then give your answer.
"""
INSTRUCTIONS = {
    "guided": MUT_OUTPUT_INSTRUCTION,
    "light": _LIGHT_INSTRUCTION,
    "minimal": _MINIMAL_INSTRUCTION,
}

# Fallback behaviour-criteria keys. The RUNTIME list is derived dynamically from
# the GOAL (see _behaviour_criteria) so the report tracks whatever the rubric
# defines — e.g. the 2026-07-01 `grounding_fidelity` addition, the exact axis the
# extract items test. This constant is only a last-resort default.
BEHAVIOUR_CRITERIA = [
    "outcome_over_output",
    "decomposition_coherence",
    "acceptance_criteria_testability",
    "assumption_explicitness",
    "scope_discipline",
    "prioritisation_rationale",
    "grounding_fidelity",
    "terminology_correct",
    "no_verbatim_reproduction",
]


def _behaviour_criteria(goal: Any) -> list[str]:
    """The behaviour-layer criterion keys the Coach will report, from the GOAL.

    Derived from ``goal.evaluation_criteria`` (layer behaviour or all) so the
    harness never lags the rubric — the exact bug that would have let the extract
    items run against a grounding-blind report.
    """
    try:
        crits = [c.name for c in _filter_criteria_for_layer(
            goal.evaluation_criteria, "behaviour")]
        return crits or list(BEHAVIOUR_CRITERIA)
    except Exception:  # pragma: no cover - defensive
        return list(BEHAVIOUR_CRITERIA)

# Default source_books per mode when a golden item does not pin them (metadata
# is secondary to the content criteria the Coach actually scores).
_DEFAULT_BOOKS = ["adzic_sbe", "adzic_impact_mapping"]


async def _ainvoke_retry(
    model: Any, messages: list[Any], *, retries: int = 4, backoff: float = 2.0
) -> Any:
    """Invoke a chat model with backoff on transient errors.

    llama-swap returns HTTP 429 "Too many requests" when concurrent requests
    exceed a model's concurrencyLimit / -np; those are transient and worth
    retrying (mirrors the generation loop's llm_retry discipline).
    """
    last: Exception | None = None
    for attempt in range(retries):
        try:
            return await model.ainvoke(messages)
        except Exception as exc:  # noqa: BLE001 - classify by message
            last = exc
            msg = str(exc).lower()
            transient = any(
                t in msg
                for t in (
                    "too many requests", "429", "rate limit", "timeout",
                    "connection", "overloaded", "502", "503",
                )
            )
            if attempt == retries - 1 or not transient:
                raise
            await asyncio.sleep(backoff * (2 ** attempt))
    raise last  # pragma: no cover - loop always returns or raises


def _content_to_text(content: Any) -> str:
    """Coerce a chat-model response content into a plain string."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):  # some providers return content parts
        parts = []
        for p in content:
            if isinstance(p, dict):
                parts.append(str(p.get("text", "")))
            else:
                parts.append(str(p))
        return "".join(parts)
    return str(content)


def _example_envelope(system_prompt: str, item: dict[str, Any], assistant: str) -> str:
    """Assemble the {messages, metadata} training-example JSON the Coach grades.

    Matches the ShareGPT envelope the generation loop hands the Coach; metadata
    is filled from the golden item + sensible defaults so layer_correct /
    type_correct evaluate sensibly and the Coach focuses on content criteria.
    """
    example = {
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": item["user"]},
            {"role": "assistant", "content": assistant},
        ],
        "metadata": {
            "layer": "behaviour",
            "type": "reasoning",
            "dimension": item.get("primary_dimension", "feature_decomposition"),
            "mode": item.get("mode", "greenfield"),
            "source_books": item.get("source_books") or _DEFAULT_BOOKS,
            "topic": item.get("topic", "mvp_scoping"),
            "source": "synthetic",
            "turns": item.get("turns", 1),
        },
    }
    return json.dumps(example, ensure_ascii=False)


async def _score_item(
    item: dict[str, Any],
    *,
    mut_model: Any,
    coach_model: Any,
    mut_system: str,
    po_system_prompt: str,
    coach_prompt: str,
    sem: asyncio.Semaphore,
) -> dict[str, Any]:
    """Generate the model-under-test output for one brief and Coach-score it.

    ``mut_system`` = the PO system prompt + the selected output instruction (the
    model-under-test sees this). ``po_system_prompt`` = the clean PO persona that
    goes into the example envelope the Coach grades (train==serve — the appended
    output instruction is harness scaffolding, not part of the example).
    """
    async with sem:
        try:
            gen = await _ainvoke_retry(
                mut_model,
                [
                    SystemMessage(content=mut_system),
                    HumanMessage(content=item["user"]),
                ],
            )
            assistant = _content_to_text(gen.content).strip()
        except Exception as exc:  # generation failure — record, keep going
            logger.warning("GEN FAILED %s: %s", item["id"], exc)
            return {"id": item["id"], "error": f"generate: {exc}"}

        has_think = "<think>" in assistant and "</think>" in assistant
        example_json = _example_envelope(po_system_prompt, item, assistant)

        try:
            verdict_raw = await _ainvoke_retry(
                coach_model,
                [SystemMessage(content=coach_prompt), HumanMessage(content=example_json)],
            )
            verdict: CoachVerdict = _parse_coach_verdict(
                _content_to_text(verdict_raw.content)
            )
        except Exception as exc:  # score failure — record, keep going
            logger.warning("SCORE FAILED %s: %s", item["id"], exc)
            return {
                "id": item["id"],
                "error": f"score: {exc}",
                "assistant_len": len(assistant),
                "has_think": has_think,
            }

    logger.info(
        "%s  decision=%s score=%d accepted=%s",
        item["id"],
        verdict.decision,
        verdict.score,
        verdict.is_accepted,
    )
    return {
        "id": item["id"],
        "mode": item.get("mode"),
        "primary_dimension": item.get("primary_dimension"),
        "is_assumption_trap": bool(item.get("is_assumption_trap")),
        "has_think": has_think,
        "assistant_len": len(assistant),
        "decision": verdict.decision,
        "score": verdict.score,
        "is_accepted": verdict.is_accepted,
        "layer_correct": verdict.layer_correct,
        "type_correct": verdict.type_correct,
        "criteria_met": dict(verdict.criteria_met),
        "issues": [i.model_dump() for i in verdict.issues],
        "quality_assessment": verdict.quality_assessment,
        # persist the model-under-test output so traps are auditable and the
        # decompositions can be curated later (not just the verdict metadata).
        "assistant": assistant,
    }


def _load_golden(path: Path) -> list[dict[str, Any]]:
    """Load golden items from a .jsonl file or a directory of .jsonl files."""
    files = sorted(path.glob("*.jsonl")) if path.is_dir() else [path]
    items: list[dict[str, Any]] = []
    for f in files:
        for line in f.read_text().splitlines():
            line = line.strip()
            if line:
                items.append(json.loads(line))
    return items


def _aggregate(
    results: list[dict[str, Any]], criteria: list[str]
) -> dict[str, Any]:
    """Per-dimension / per-mode pass rates, two-sided counts, edge weights.

    ``criteria`` is the behaviour-criterion set derived from the GOAL, so a
    rubric change (e.g. added ``grounding_fidelity``) flows through automatically.
    """
    scored = [r for r in results if "criteria_met" in r]
    errored = [r for r in results if "error" in r]

    # per-criterion pass rate (the weakness ranking / edge-density signal)
    passed: dict[str, int] = defaultdict(int)
    total: dict[str, int] = defaultdict(int)
    for r in scored:
        cm = r["criteria_met"]
        for crit in criteria:
            if crit in cm:
                total[crit] += 1
                passed[crit] += 1 if cm[crit] else 0
    dim_pass = {
        crit: (passed[crit] / total[crit]) if total[crit] else None
        for crit in criteria
    }

    # per-mode acceptance + mean score
    by_mode: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in scored:
        by_mode[r.get("mode") or "unknown"].append(r)
    mode_stats = {
        m: {
            "n": len(rs),
            "accept_rate": sum(1 for r in rs if r["is_accepted"]) / len(rs),
            "mean_score": round(sum(r["score"] for r in rs) / len(rs), 2),
        }
        for m, rs in by_mode.items()
    }

    # two-sided (SPEC §6)
    traps = [r for r in scored if r["is_assumption_trap"]]
    false_confidence = [
        r for r in traps if r["criteria_met"].get("assumption_explicitness") is False
    ]
    # over-conservative proxy: surfaced assumptions but failed to commit to a
    # coherent, scoped decomposition.
    over_conservative = [
        r
        for r in scored
        if r["criteria_met"].get("assumption_explicitness") is True
        and (
            r["criteria_met"].get("scope_discipline") is False
            or r["criteria_met"].get("decomposition_coherence") is False
        )
    ]

    # grounding — the axis the extract items exist to test (ungrounded = invented
    # capabilities / fabricated citations). Only meaningful once the GOAL rubric
    # carries grounding_fidelity (added 2026-07-01).
    grounding: dict[str, Any] | None = None
    if "grounding_fidelity" in criteria:
        gf = [r for r in scored if "grounding_fidelity" in r["criteria_met"]]
        fails = [r for r in gf if r["criteria_met"]["grounding_fidelity"] is False]
        by_mode_fail: dict[str, int] = defaultdict(int)
        for r in fails:
            by_mode_fail[r.get("mode") or "unknown"] += 1
        grounding = {
            "n_evaluated": len(gf),
            "n_ungrounded": len(fails),
            "ungrounded_ids": [r["id"] for r in fails],
            "ungrounded_by_mode": dict(by_mode_fail),
        }

    # edge-density weight vector: oversample proportional to miss rate.
    miss = {
        crit: (1.0 - dim_pass[crit]) for crit in criteria if dim_pass[crit] is not None
    }
    denom = sum(miss.values()) or 1.0
    edge_weights = {crit: round(m / denom, 3) for crit, m in sorted(
        miss.items(), key=lambda kv: kv[1], reverse=True
    )}

    return {
        "n_items": len(results),
        "n_scored": len(scored),
        "n_errored": len(errored),
        "errored_ids": [r["id"] for r in errored],
        "per_dimension_pass_rate": {
            k: (round(v, 3) if v is not None else None) for k, v in dim_pass.items()
        },
        "per_mode": mode_stats,
        "two_sided": {
            "n_traps": len(traps),
            "false_confidence": {
                "n": len(false_confidence),
                "rate": round(len(false_confidence) / len(traps), 3) if traps else None,
                "ids": [r["id"] for r in false_confidence],
            },
            "over_conservative_proxy": {
                "n": len(over_conservative),
                "ids": [r["id"] for r in over_conservative],
            },
        },
        "grounding": grounding,
        "edge_density_weights": edge_weights,
    }


def _print_summary(agg: dict[str, Any], meta: dict[str, Any]) -> None:
    print("\n" + "=" * 70)
    print("PHASE 0 — PO GOLDEN-SET DIAGNOSIS")
    print("=" * 70)
    print(f"model-under-test : {meta['player']}  (instruction: {meta.get('instruction', 'guided')})")
    print(f"coach (gate)     : {meta['coach']}")
    print(f"items            : {agg['n_scored']} scored / {agg['n_errored']} errored")
    if agg["n_errored"]:
        print(f"  errored ids    : {', '.join(agg['errored_ids'])}")
    print("\nper-mode (accept rate | mean score):")
    for m, s in sorted(agg["per_mode"].items()):
        print(f"  {m:<11} n={s['n']:<2} accept={s['accept_rate']:.0%}  score={s['mean_score']}")
    print("\nper-dimension pass rate (lowest = weakest = oversample target):")
    for crit, rate in sorted(
        agg["per_dimension_pass_rate"].items(),
        key=lambda kv: (kv[1] is None, kv[1]),
    ):
        bar = "n/a" if rate is None else f"{rate:.0%}"
        print(f"  {crit:<34} {bar}")
    ts = agg["two_sided"]
    print(
        f"\ntwo-sided:  false-confidence {ts['false_confidence']['n']}/{ts['n_traps']} traps"
        f"  |  over-conservative(proxy) {ts['over_conservative_proxy']['n']}"
    )
    g = agg.get("grounding")
    if g is not None:
        print(
            f"grounding:  {g['n_ungrounded']}/{g['n_evaluated']} ungrounded"
            f"  |  by mode {g['ungrounded_by_mode'] or '{}'}"
        )
    else:
        print("grounding:  n/a (grounding_fidelity not in the GOAL rubric)")
    print("\nedge-density weights (Phase-3 oversample distribution):")
    for crit, w in agg["edge_density_weights"].items():
        print(f"  {crit:<34} {w}")
    print("=" * 70 + "\n")


async def _run(args: argparse.Namespace) -> dict[str, Any]:
    goal = parse_goal_md(Path(args.goal))
    coach_prompt = build_coach_prompt(goal, target_layer="behaviour")
    po_system_prompt = goal.system_prompt
    mut_system = po_system_prompt + INSTRUCTIONS[args.instruction]
    criteria = _behaviour_criteria(goal)
    logger.info("behaviour criteria from GOAL (%d): %s", len(criteria), criteria)
    if "grounding_fidelity" not in criteria:
        logger.warning(
            "grounding_fidelity NOT in the GOAL rubric — the extract items will "
            "not measure grounding. Is domains/product-owner/GOAL.md up to date?"
        )

    player_cfg = ModelConfig(
        provider="local",
        model=args.player_model,
        endpoint=args.player_endpoint,
        temperature=args.player_temp,
        max_tokens=args.max_tokens,
    )
    coach_cfg = ModelConfig(
        provider="local",
        model=args.coach_model,
        endpoint=args.coach_endpoint,
        temperature=args.coach_temp,
        max_tokens=args.coach_max_tokens,
    )
    if (player_cfg.model, player_cfg.endpoint) == (coach_cfg.model, coach_cfg.endpoint):
        logger.warning(
            "SPEC AC-5 VIOLATION: player and coach are the same model/endpoint "
            "(%s) — this is self-scoring. Use a different --coach-model.",
            coach_cfg.model,
        )

    mut_model = create_model(player_cfg, timeout=args.timeout)
    coach_model = create_model(coach_cfg, timeout=args.timeout)

    items = _load_golden(Path(args.golden))
    logger.info("loaded %d golden items", len(items))
    sem = asyncio.Semaphore(args.concurrency)
    results = await asyncio.gather(
        *(
            _score_item(
                it,
                mut_model=mut_model,
                coach_model=coach_model,
                mut_system=mut_system,
                po_system_prompt=po_system_prompt,
                coach_prompt=coach_prompt,
                sem=sem,
            )
            for it in items
        )
    )
    agg = _aggregate(results, criteria)
    meta = {
        "player": args.player_model,
        "coach": args.coach_model,
        "instruction": args.instruction,
        "behaviour_criteria": criteria,
    }
    return {"meta": meta, "aggregate": agg, "results": results}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    _here = Path(__file__).resolve().parent
    ap.add_argument("--goal", default=str(_here / "GOAL.md"))
    ap.add_argument("--golden", default=str(_here / "golden_set"))
    ap.add_argument("--player-model", default="gemma4-26b",
                    help="the model-under-test being diagnosed (default: the "
                         "Gemma-4-26B-A4B MoE base the PO fine-tune trains from)")
    ap.add_argument("--player-endpoint", default="http://localhost:9000/v1")
    ap.add_argument("--coach-model", default="gpt-oss-120b",
                    help="the gate model — MUST differ from --player-model")
    ap.add_argument("--coach-endpoint", default="http://localhost:9000/v1")
    ap.add_argument("--player-temp", type=float, default=0.3)
    ap.add_argument("--coach-temp", type=float, default=0.2)
    ap.add_argument("--max-tokens", type=int, default=6000,
                    help="model-under-test completion budget (roomy for a roadmap)")
    ap.add_argument("--coach-max-tokens", type=int, default=2048)
    ap.add_argument("--instruction", choices=["guided", "light", "minimal"],
                    default="guided",
                    help="output-shape spoon-feed for the model-under-test; A/B "
                         "'guided' vs 'light' to expose native PO tendency vs "
                         "instruction-following")
    ap.add_argument("--timeout", type=int, default=300)
    ap.add_argument("--concurrency", type=int, default=2,
                    help="keep <= the model's llama-swap concurrencyLimit (2) to "
                         "avoid HTTP 429; transient 429s are retried regardless")
    ap.add_argument("--out", default=str(_here / "golden_set" / "phase0_report.json"))
    ap.add_argument("--log-level", default="INFO")
    args = ap.parse_args()

    logging.basicConfig(
        level=args.log_level, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )

    report = asyncio.run(_run(args))
    Path(args.out).write_text(json.dumps(report, indent=2, ensure_ascii=False))
    _print_summary(report["aggregate"], report["meta"])
    print(f"full report -> {args.out}")


if __name__ == "__main__":
    main()
