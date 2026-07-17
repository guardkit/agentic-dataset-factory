"""Offline generation driver for the dcl-capability-language domain.

Runnable WITHOUT the live Player-Coach loop (the QAV README-code-half pattern): the
mechanism is here; a real run wires an OpenAI-compatible endpoint from
``agent-config.draft.yaml``, while tests drive it against local stub clients. **Zero real
model calls happen in this module by construction** — the model client is injected.

Two modes:

- ``dcl_author``: for each brief → Player authors a capability → **COMPILE GATE** (the
  deterministic truth source; up to ``max_format_retries`` repair-style retries with the
  real diagnostics fed back) → **LLM Coach** brief-fidelity check → accepted rows written.
- ``dcl_repair``: for each source capability (rendered from a brief, and/or an accepted
  author capability) × recipe → break it → REAL diagnostics → the teacher authors only the
  ``<think>`` rationale (the corrected text is the pre-injection original by construction) →
  rows written.

Every label is compiler-verified. The hold-out denylist refuses on hit at every entry
point. Output: ``output/dcl-capability-language/{train,eval_dcl,rejected}.jsonl`` +
``manifest.json``, with a house backup of any prior files.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

import yaml

from dcl import checker, contamination
from dcl.briefs import Brief, load_briefs, render_reference_capability
from dcl.contracts import (
    SYSTEM_PROMPT,
    build_author_row,
    build_author_user_message,
    build_repair_row,
    build_repair_user_message,
    load_vocab_reference,
    validate_row,
)
from dcl.manifest import build_manifest, validate_manifest
from dcl.recipes import RECIPES, AnchorNotFound, apply_recipe, verify_breaks

logger = logging.getLogger(__name__)

_DCL_FENCE_RE = re.compile(r"```dcl\s*\n(.*?)\n```", re.S)


# --------------------------------------------------------------------------------------
# Pluggable model clients — injected. The real client hits an OpenAI-compatible endpoint;
# tests inject stubs. Nothing in this module constructs the real client automatically.
# --------------------------------------------------------------------------------------
class ModelClient(Protocol):
    def complete(self, system: str, user: str) -> str:  # pragma: no cover - protocol
        ...


@dataclass
class CoachVerdict:
    """Structured brief-fidelity verdict (the row-quality gate)."""

    decision: str  # "accept" | "revise"
    score: int
    reasons: list[str] = field(default_factory=list)

    @property
    def accepted(self) -> bool:
        return self.decision == "accept"


class CoachClient(Protocol):
    def assess(self, brief: Brief, capability_text: str) -> CoachVerdict:  # pragma: no cover
        ...


@dataclass
class OpenAICompatibleClient:
    """Real Player/teacher client against an OpenAI-compatible ``/chat/completions`` endpoint.

    NEVER instantiated or called by tests (the ZERO-real-model-calls law). Kept minimal and
    dependency-light (stdlib ``urllib``) so a generation run can wire it without new deps.
    """

    endpoint: str
    model: str
    temperature: float = 0.4
    max_tokens: int = 4096

    def complete(self, system: str, user: str) -> str:  # pragma: no cover - real network
        import urllib.request

        payload = json.dumps({
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
        }).encode()
        req = urllib.request.Request(
            self.endpoint.rstrip("/") + "/chat/completions",
            data=payload,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req) as resp:
            body = json.loads(resp.read())
        return body["choices"][0]["message"]["content"]


# --------------------------------------------------------------------------------------
# Config — loaded from agent-config.draft.yaml (or constructed directly).
# --------------------------------------------------------------------------------------
@dataclass
class GenerateConfig:
    mode: str = "both"  # dcl_author | dcl_repair | both
    limit: int | None = None
    holdout_fraction: float = 0.1
    max_format_retries: int = 3
    coach_max_turns: int = 2
    recipes: dict[str, float] = field(default_factory=lambda: {r: 1.0 for r in RECIPES})
    output_dir: str = "output/dcl-capability-language"
    seed: str = "dcl-phase1"

    @classmethod
    def from_yaml(cls, path: str | Path) -> "GenerateConfig":
        data = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
        gen = data.get("generation", {})
        out = data.get("output", {})
        return cls(
            mode=gen.get("mode", "both"),
            limit=gen.get("limit"),
            holdout_fraction=gen.get("holdout_fraction", 0.1),
            max_format_retries=gen.get("max_format_retries", 3),
            coach_max_turns=gen.get("coach_max_turns", 2),
            recipes=gen.get("recipes") or {r: 1.0 for r in RECIPES},
            output_dir=out.get("dir", "output/dcl-capability-language"),
            seed=gen.get("seed", "dcl-phase1"),
        )


def extract_dcl(text: str) -> str | None:
    """Pull the first ```dcl fenced block out of model output (None if absent)."""
    m = _DCL_FENCE_RE.search(text)
    return m.group(1).strip() if m else None


# --------------------------------------------------------------------------------------
# House output writer — routes by split, mirrors the write_output validator conventions
# (message-key discipline + type/think consistency are enforced by contracts.validate_row).
# --------------------------------------------------------------------------------------
class OutputWriter:
    """Fresh-start writer with the house backup convention (prior files -> ``*.bak``)."""

    def __init__(self, output_dir: str | Path) -> None:
        self.dir = Path(output_dir)
        self.counts = {"train": 0, "eval_dcl": 0, "rejected": 0}
        self._fh: dict[str, Any] = {}

    @staticmethod
    def _backup(path: Path) -> None:
        if path.exists():
            path.replace(path.with_suffix(path.suffix + ".bak"))

    def __enter__(self) -> "OutputWriter":
        self.dir.mkdir(parents=True, exist_ok=True)
        for name in ("train.jsonl", "eval_dcl.jsonl", "rejected.jsonl", "manifest.json"):
            self._backup(self.dir / name)
        self._fh["train"] = open(self.dir / "train.jsonl", "w", encoding="utf-8")
        self._fh["eval_dcl"] = open(self.dir / "eval_dcl.jsonl", "w", encoding="utf-8")
        self._fh["rejected"] = open(self.dir / "rejected.jsonl", "w", encoding="utf-8")
        self.train_rows: list[dict[str, Any]] = []
        self.eval_rows: list[dict[str, Any]] = []
        return self

    def write_row(self, row: dict[str, Any]) -> None:
        validate_row(row)  # mirrors write_output's schema/think/type gate
        split = row["metadata"]["split"]
        self._fh[split].write(json.dumps(row, ensure_ascii=False) + "\n")
        self._fh[split].flush()
        self.counts[split] += 1
        (self.train_rows if split == "train" else self.eval_rows).append(row)

    def write_rejected(self, record: dict[str, Any]) -> None:
        self._fh["rejected"].write(json.dumps(record, ensure_ascii=False) + "\n")
        self._fh["rejected"].flush()
        self.counts["rejected"] += 1

    def __exit__(self, *exc: Any) -> None:
        for fh in self._fh.values():
            fh.close()


# --------------------------------------------------------------------------------------
# AUTHOR mode.
# --------------------------------------------------------------------------------------
def _author_one(
    brief: Brief,
    player: ModelClient,
    coach: CoachClient,
    vocab: str,
    config: GenerateConfig,
) -> tuple[str, dict[str, Any]]:
    """Return ``("accepted", dcl_text)`` or ``("rejected", {reason,...})`` for one brief."""
    contamination.assert_clean(brief.brief_text, what=f"brief {brief.id}")
    user = build_author_user_message(brief.brief_text, vocab)
    feedback = ""
    last_diag = ""
    for attempt in range(config.max_format_retries + 1):
        prompt = user if not feedback else f"{user}\n\n## Compiler feedback (repair)\n{feedback}"
        raw = player.complete(SYSTEM_PROMPT, prompt)
        dcl_text = extract_dcl(raw)
        if dcl_text is None:
            feedback = "Your response contained no ```dcl fenced block. Emit exactly one."
            continue
        compiled = checker.compile(dcl_text)
        if not compiled.ok:
            last_diag = compiled.diagnostics_json()
            feedback = (
                "The capability failed to compile. Fix ONLY what these diagnostics require:\n"
                f"{last_diag}"
            )
            continue
        # Compiles clean — refuse if it drifted toward a hold-out, then Coach-gate.
        contamination.assert_clean(dcl_text, what=f"authored capability for {brief.id}")
        for _ in range(config.coach_max_turns):
            verdict = coach.assess(brief, dcl_text)
            if verdict.accepted:
                return "accepted", {"dcl": dcl_text}
            # revise on coach feedback
            raw = player.complete(
                SYSTEM_PROMPT,
                f"{user}\n\n## Coach feedback (revise)\n" + "; ".join(verdict.reasons),
            )
            revised = extract_dcl(raw)
            if revised and checker.compile(revised).ok:
                contamination.assert_clean(revised, what=f"revised capability for {brief.id}")
                dcl_text = revised
        return "rejected", {"reason": "coach_rejected", "brief": brief.id}
    return "rejected", {"reason": "compile_gate_exhausted", "brief": brief.id, "diagnostics": last_diag}


# --------------------------------------------------------------------------------------
# REPAIR mode.
# --------------------------------------------------------------------------------------
def _repair_rationale(teacher: ModelClient, broken: str, diagnostics_json: str) -> str:
    """Teacher authors ONLY the <think> rationale (corrected text is fixed by construction)."""
    user = build_repair_user_message(broken, diagnostics_json)
    raw = teacher.complete(SYSTEM_PROMPT, user)
    # Accept a <think> block if given, else use the raw prose as the rationale.
    m = re.search(r"<think>(.*?)</think>", raw, re.S)
    rationale = (m.group(1) if m else raw).strip()
    return rationale or "Diagnose the named DCL error and restore the compiler-clean original."


def _weighted_recipe_ids(config: GenerateConfig) -> list[str]:
    active = {rid: w for rid, w in config.recipes.items() if rid in RECIPES and w > 0}
    return sorted(active, key=lambda r: (-active[r], r))


# --------------------------------------------------------------------------------------
# Driver.
# --------------------------------------------------------------------------------------
@dataclass
class GenerationSummary:
    author_accepted: int = 0
    author_rejected: int = 0
    repair_written: int = 0
    repair_skipped_anchor: int = 0
    train: int = 0
    eval_dcl: int = 0


def run_generation(
    config: GenerateConfig,
    *,
    player: ModelClient,
    coach: CoachClient,
    teacher: ModelClient | None = None,
    briefs: list[Brief] | None = None,
    write_manifest: bool = True,
    created: str = "unset",
    factory_sha: str = "unset",
) -> GenerationSummary:
    """Run the offline generation. ``player``/``coach``/``teacher`` are injected (stubs in
    tests). ``teacher`` defaults to ``player`` (the reused rationale seat)."""
    teacher = teacher or player
    briefs = briefs if briefs is not None else load_briefs()
    vocab = load_vocab_reference()
    summary = GenerationSummary()
    limit = config.limit

    with OutputWriter(config.output_dir) as writer:
        if config.mode in ("dcl_author", "both"):
            for brief in briefs:
                if limit is not None and writer.counts["train"] + writer.counts["eval_dcl"] >= limit:
                    break
                status, payload = _author_one(brief, player, coach, vocab, config)
                if status == "accepted":
                    split = contamination.assign_split(
                        _author_row_id(brief.brief_text, vocab),
                        holdout_fraction=config.holdout_fraction,
                        seed=config.seed,
                    )
                    row = build_author_row(
                        brief=brief.brief_text, dcl_text=payload["dcl"],
                        vocab_reference=vocab, split=split,
                    )
                    writer.write_row(row)
                    summary.author_accepted += 1
                else:
                    writer.write_rejected({"mode": "dcl_author", **payload})
                    summary.author_rejected += 1

        if config.mode in ("dcl_repair", "both"):
            recipe_ids = _weighted_recipe_ids(config)
            # Sources: the compiling brief renders (offline, no model) + any accepted author rows.
            sources = [
                (b.id, render_reference_capability(b))
                for b in briefs
            ]
            for src_id, source in sources:
                contamination.assert_clean(source, what=f"repair source {src_id}")
                for recipe_id in recipe_ids:
                    if limit is not None and summary.repair_written >= (limit or 0) and config.mode == "dcl_repair":
                        break
                    try:
                        broken = apply_recipe(source, recipe_id)
                    except AnchorNotFound:
                        summary.repair_skipped_anchor += 1
                        continue
                    compiled = verify_breaks(broken)
                    diagnostics_json = compiled.diagnostics_json()
                    contamination.assert_clean(broken.broken_text, what=f"broken {src_id}/{recipe_id}")
                    think = _repair_rationale(teacher, broken.broken_text, diagnostics_json)
                    row_id_seed = build_repair_user_message(broken.broken_text, diagnostics_json)
                    split = contamination.assign_split(
                        _repair_row_id(row_id_seed),
                        holdout_fraction=config.holdout_fraction,
                        seed=config.seed,
                    )
                    row = build_repair_row(
                        broken_dcl=broken.broken_text,
                        diagnostics_json=diagnostics_json,
                        think=think,
                        corrected_dcl=source,
                        recipe_id=recipe_id,
                        split=split,
                    )
                    writer.write_row(row)
                    summary.repair_written += 1

        summary.train = writer.counts["train"]
        summary.eval_dcl = writer.counts["eval_dcl"]

        if write_manifest:
            manifest = build_manifest(
                writer.train_rows, writer.eval_rows,
                dataset_id="dcl-phase1-train-v1",
                created=created, factory_sha=factory_sha,
            )
            validate_manifest(manifest)
            (Path(config.output_dir) / "manifest.json").write_text(
                json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8"
            )

    return summary


def _author_row_id(brief_text: str, vocab: str) -> str:
    from dcl.contracts import row_id
    return row_id(build_author_user_message(brief_text, vocab))


def _repair_row_id(user_msg: str) -> str:
    from dcl.contracts import row_id
    return row_id(user_msg)
