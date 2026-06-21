#!/usr/bin/env python3
"""build_step0_eval.py — Coach v3 Step 0: render the balanced-real holdout in the
PRODUCTION Coach prompt format (player_report + reconstructed <evidence_bundle> +
7 absence-of-failure guards + toolless-synthesis framing).

Why (HANDOFF-coach-v3 Step 0): every prior Coach eval — including the base's "94%
false-approval" — ran on the HARVEST prompt (`player_report` only), which is NOT
the production Coach's input. Production serves the Coach a `CoachEvidenceBundle`
in toolless-synthesis mode. This script rebuilds the SAME 32 real holdout cases in
the production format so we can re-measure the base WITH the bundle. If base+bundle
+guards lands false-approval AND false-feedback both < ~20%, the rubber-stamp was a
harvest artifact and the fine-tune may be unnecessary.

FIDELITY LEVER (the single most important choice, HANDOFF Step 3): we call the REAL
production builder `AgentInvoker._build_coach_prompt(synthesis=True)` plus its
`_render_evidence_bundle_section` / `_render_absence_of_failure_guards` /
`_render_bundle_honesty_section` — train==serve byte-for-byte, zero drift. Those
methods are pure string formatting (no __init__ state), so we call them on a bare
`AgentInvoker.__new__` instance.

LEAKAGE DISCIPLINE (evidence-in, judgment-out): the bundle is reconstructed ONLY
from input-side artifacts — `task_work_results.json` (Player-produced gate output)
and the task definition. We NEVER read `coach_turn_N.json` (the verdict/label) into
the bundle. The gold label comes from the holdout's `decision` field.

HONEST FIDELITY GAP (documented, by design): the Coach's OWN independent signals —
`independent_tests` (its trust-but-verify pytest run) and `honesty` (CoachVerifier
cross-check) — are never persisted per turn (coach_turn_N.json is output-only). We
therefore leave `independent_tests=None` and `honesty=neutral` (no fabricated
discrepancies — that would both leak and bias toward feedback). The reconstructed
bundle thus carries only the Player-reported deterministic gates (tests / bdd /
coverage / plan_audit). This UNDER-informs the Coach relative to production, making
Step 0 a CONSERVATIVE LOWER BOUND: if the base improves materially on just these
gates, the real production gain is at least that large.

Also: these are Claude-era turns whose `task_work_results` predates the current
bundle schema (uses `quality_gates` rather than `test_results`); the mapping below
is a faithful best-effort onto the live `CoachEvidenceBundle` fields.

Output: `step0_eval.jsonl` — one row per case with the production-format `prompt`,
the gold `decision`, a `bundle_signal` diagnostic, and token length. Plus a printed
report (token distribution, leakage audit, bundle-vs-gold separability) and two
dumped sample prompts.

Run:  python3 build_step0_eval.py
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# --- make the production guardkit package importable (package dir is guardkit/guardkit) ---
GUARDKIT_ROOT = Path("/home/richardwoollcott/Projects/appmilla_github/guardkit")
if str(GUARDKIT_ROOT) not in sys.path:
    sys.path.insert(0, str(GUARDKIT_ROOT))

from guardkit.orchestrator.agent_invoker import AgentInvoker  # noqa: E402
from guardkit.orchestrator.coach_verification import HonestyVerification  # noqa: E402
from guardkit.orchestrator.quality_gates.coach_evidence import (  # noqa: E402
    CoachEvidenceBundle,
)

REPOS_ROOT = Path("/home/richardwoollcott/Projects/appmilla_github")
CURATED = Path("/home/richardwoollcott/coach-dataset")
HOLDOUT = CURATED / "curated" / "holdout_balanced_real.jsonl"
PAIRS = CURATED / "coach_verdict_pairs.jsonl"
HERE = Path(__file__).resolve().parent
OUT = HERE / "step0_eval.jsonl"
SAMPLE_DIR = HERE / "step0_samples"

# A bare invoker instance — the prompt-builder methods touch no __init__ state.
_INV = AgentInvoker.__new__(AgentInvoker)


# --------------------------------------------------------------------------- #
# Bundle reconstruction — INPUT-SIDE ONLY (task_work_results.json)
# --------------------------------------------------------------------------- #
def _num(v: Any, default: int = 0) -> int:
    return v if isinstance(v, int) else default


def reconstruct_bundle(
    twr: Optional[Dict[str, Any]],
) -> Tuple[CoachEvidenceBundle, Dict[str, Any]]:
    """Rebuild a partial CoachEvidenceBundle from the Player-produced
    task_work_results.json. Returns (bundle, signal) where `signal` is a
    label-free diagnostic of what the deterministic gates report.

    Coach-only fields (independent_tests, honesty, wiring/mocked_seam/spec_gap)
    are left absent — they are never persisted (see module docstring).
    """
    twr = twr or {}
    qg = twr.get("quality_gates") or {}
    bdd_raw = twr.get("bdd_results")
    plan_audit = twr.get("plan_audit")
    task_type = twr.get("task_type")

    # --- tests aggregate (mapped from the Claude-era quality_gates layout) ---
    tests: Optional[Dict[str, Any]] = None
    if qg:
        passed_ct = _num(qg.get("tests_passed"))
        failed_ct = _num(qg.get("tests_failed"))
        tests = {
            # bundle.tests.tests_passed is the BOOL the Coach reads; the raw
            # counts are surfaced under *_count so no signal is hidden.
            "tests_passed": bool(qg.get("tests_passing")),
            "tests_run": passed_ct + failed_ct,
            "tests_passed_count": passed_ct,
            "tests_failed_count": failed_ct,
            "line_coverage_met": qg.get("coverage_met"),
            "coverage": qg.get("coverage"),
        }

    # --- bdd: pass through, add scenarios_attempted (guard #1 reads it) ---
    bdd: Optional[Dict[str, Any]] = None
    if isinstance(bdd_raw, dict):
        bdd = dict(bdd_raw)
        if "scenarios_attempted" not in bdd:
            bdd["scenarios_attempted"] = (
                _num(bdd.get("scenarios_passed"))
                + _num(bdd.get("scenarios_failed"))
                + _num(bdd.get("scenarios_pending"))
            )

    coverage_details: Optional[Dict[str, Any]] = None
    if qg.get("coverage") is not None or qg.get("coverage_met") is not None:
        coverage_details = {
            "coverage": qg.get("coverage"),
            "coverage_met": qg.get("coverage_met"),
        }

    bundle = CoachEvidenceBundle(
        # neutral honesty — real result not persisted; no fabricated discrepancies
        honesty=HonestyVerification(
            verified=True, discrepancies=[], honesty_score=1.0
        ),
        gathering_status="complete",
        quality_gates=None,  # aggregate not reconstructable without arch_review; rely on per-gate fields
        coverage_details=coverage_details,
        plan_audit=plan_audit if isinstance(plan_audit, dict) else None,
        bdd=bdd,
        tests=tests,
        independent_tests=None,  # Coach's own pytest run — never persisted
        task_type=task_type,
    )

    # --- label-free diagnostic of what the deterministic gates "say" ---
    signal = {
        "tests_run": (tests or {}).get("tests_run"),
        "tests_passed_bool": (tests or {}).get("tests_passed"),
        "tests_failed_count": (tests or {}).get("tests_failed_count"),
        "bdd_attempted": (bdd or {}).get("scenarios_attempted"),
        "bdd_failed": (bdd or {}).get("scenarios_failed"),
        "plan_audit_status": (plan_audit or {}).get("status")
        if isinstance(plan_audit, dict)
        else None,
        "plan_audit_violations": (plan_audit or {}).get("violations")
        if isinstance(plan_audit, dict)
        else None,
        "task_type": task_type,
    }
    # A coarse deterministic "would a strict gate-reader reject?" flag.
    failing = (
        bool(signal["bdd_failed"]) and signal["bdd_failed"] not in (0, None)
    ) or (
        signal["tests_passed_bool"] is False
    ) or (
        isinstance(signal["plan_audit_violations"], int)
        and signal["plan_audit_violations"] > 0
    )
    # zero-cardinality (absent) test/bdd oracle — guards say this is NOT a pass
    absent_oracle = (signal["tests_run"] in (0, None)) and (
        signal["bdd_attempted"] in (0, None)
    )
    signal["gate_failing"] = failing
    signal["gate_absent_oracle"] = absent_oracle
    return bundle, signal


# --------------------------------------------------------------------------- #
# Per-case prompt assembly using the REAL production builder
# --------------------------------------------------------------------------- #
def acceptance_criteria_from(player_report: Dict[str, Any]) -> List[Dict[str, str]]:
    acs: List[Dict[str, str]] = []
    for cp in player_report.get("completion_promises") or []:
        if not isinstance(cp, dict):
            continue
        cid = cp.get("criterion_id") or cp.get("id")
        ctext = cp.get("criterion_text") or cp.get("text") or ""
        if cid:
            acs.append({"id": str(cid), "text": str(ctext)})
    return acs


def turn_dir_for(pair: Dict[str, Any]) -> Optional[Path]:
    """Resolve the autobuild turn dir for a pair.

    Prefer the recorded source_path; fall back to repo/.guardkit/autobuild/task_id.
    """
    sp = pair.get("source_path")
    if sp:
        p = Path(sp)
        # source_path may point at a coach_turn_N.json or the turn dir itself
        cand = p if p.is_dir() else p.parent
        if (cand / "task_work_results.json").exists():
            return cand
    repo = pair.get("repo")
    task_id = pair.get("task_id")
    if repo and task_id:
        cand = REPOS_ROOT / repo / ".guardkit" / "autobuild" / task_id
        if cand.exists():
            return cand
    return None


def build() -> None:
    holdout = [json.loads(l) for l in HOLDOUT.open()]
    pairs = [json.loads(l) for l in PAIRS.open()]
    pair_idx = {(p.get("repo"), p.get("task_id"), p.get("turn")): p for p in pairs}

    rows: List[Dict[str, Any]] = []
    missing_twr: List[str] = []
    leak_violations: List[str] = []

    for h in holdout:
        key = (h["repo"], h["task_id"], h["turn"])
        pair = pair_idx.get(key)
        if pair is None:
            missing_twr.append(f"{key} (no pair)")
            continue
        player_report = pair.get("player_report") or {}
        task_text = pair.get("task") or ""
        gold = h["decision"]

        tdir = turn_dir_for(pair)
        twr = None
        if tdir is not None:
            twr_path = tdir / "task_work_results.json"
            if twr_path.exists():
                try:
                    twr = json.loads(twr_path.read_text())
                except Exception:
                    twr = None
        if twr is None:
            missing_twr.append(str(key))

        bundle, signal = reconstruct_bundle(twr)
        acs = acceptance_criteria_from(player_report)

        prompt = _INV._build_coach_prompt(
            task_id=h["task_id"],
            turn=h["turn"],
            requirements=task_text,
            player_report=player_report,
            acceptance_criteria=acs,
            evidence_bundle=bundle,
            synthesis=True,
        )

        # --- leakage audit: the gold decision string must NOT appear inside the
        # rendered <evidence_bundle> (it would mean a verdict field leaked in).
        bundle_json = _INV._render_evidence_bundle_section(bundle)
        for token in ('"decision"', "criteria_verification", '"rationale"', '"issues"'):
            if token in bundle_json:
                leak_violations.append(f"{key}: bundle contains {token}")

        rows.append(
            {
                "repo": h["repo"],
                "task_id": h["task_id"],
                "turn": h["turn"],
                "decision": gold,  # GOLD label (from coach output, kept OUT of prompt)
                "prompt": prompt,
                "n_acs": len(acs),
                "has_twr": twr is not None,
                "bundle_signal": signal,
                "prompt_chars": len(prompt),
            }
        )

    with OUT.open("w") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")

    _report(rows, missing_twr, leak_violations)
    _dump_samples(rows)
    _token_lengths(rows)


def _report(rows, missing_twr, leak_violations) -> None:
    print(f"\n=== Step 0 eval corpus: {len(rows)} cases -> {OUT} ===")
    dec = Counter(r["decision"] for r in rows)
    print(f"balance: {dict(dec)}")
    print(f"cases without task_work_results (bundle = empty/absent gates): "
          f"{sum(1 for r in rows if not r['has_twr'])}")
    if missing_twr:
        print("  missing twr:", missing_twr)

    print("\n--- LEAKAGE AUDIT (evidence-in, judgment-out) ---")
    if leak_violations:
        print("  !! VIOLATIONS:", leak_violations)
    else:
        print("  OK: no verdict/criteria/rationale fields present in any <evidence_bundle>.")

    # separability diagnostic: does the deterministic gate flag predict the gold label?
    print("\n--- BUNDLE-vs-GOLD SEPARABILITY (how 'inferable' the verdict now is) ---")
    print("  (gate_failing OR gate_absent_oracle) => a strict gate-reader would push feedback")
    tab = Counter()
    for r in rows:
        s = r["bundle_signal"]
        gate_says_feedback = bool(s.get("gate_failing") or s.get("gate_absent_oracle"))
        tab[(r["decision"], gate_says_feedback)] += 1
    print(f"  gold=feedback & gate->feedback : {tab[('feedback', True)]:2d}  (recoverable feedback)")
    print(f"  gold=feedback & gate->approve  : {tab[('feedback', False)]:2d}  (still uninferable - needs Coach's own signal)")
    print(f"  gold=approve   & gate->approve : {tab[('approve', False)]:2d}  (clean approves)")
    print(f"  gold=approve   & gate->feedback: {tab[('approve', True)]:2d}  (gate over-rejects - approve-trap risk)")
    fb_recoverable = tab[('feedback', True)]
    fb_total = tab[('feedback', True)] + tab[('feedback', False)]
    if fb_total:
        print(f"  => deterministic gates alone recover {fb_recoverable}/{fb_total} feedback cases "
              f"({100*fb_recoverable/fb_total:.0f}%); the rest hinge on the Coach's own (absent) signal.")


def _dump_samples(rows) -> None:
    SAMPLE_DIR.mkdir(exist_ok=True)
    fb = next((r for r in rows if r["decision"] == "feedback" and r["has_twr"]), None)
    ap = next((r for r in rows if r["decision"] == "approve" and r["has_twr"]), None)
    for tag, r in (("feedback", fb), ("approve", ap)):
        if r is None:
            continue
        path = SAMPLE_DIR / f"sample_{tag}_{r['repo']}_{r['task_id']}_t{r['turn']}.txt"
        path.write_text(r["prompt"])
        print(f"\n--- sample {tag} prompt -> {path} ({r['prompt_chars']} chars) ---")


def _token_lengths(rows) -> None:
    print("\n--- TOKEN LENGTHS (Step 4 / GB10 seq feasibility) ---")
    try:
        from transformers import AutoTokenizer

        tok = AutoTokenizer.from_pretrained(
            "unsloth/gemma-4-26b-a4b-it", trust_remote_code=True
        )
        lens = sorted(len(tok(r["prompt"], add_special_tokens=False)["input_ids"]) for r in rows)
        import statistics

        n = len(lens)
        p = lambda q: lens[min(n - 1, int(q * n))]
        print(f"  n={n}  min={lens[0]}  p50={statistics.median(lens):.0f}  "
              f"p90={p(0.90)}  p99={p(0.99)}  max={lens[-1]}")
        print(f"  > 4096 tokens: {sum(1 for x in lens if x > 4096)}/{n}  "
              f"(prompt-only; INFERENCE not training, base ctx=65536 so fine to run)")
    except Exception as e:
        chars = sorted(r["prompt_chars"] for r in rows)
        print(f"  (tokenizer unavailable: {type(e).__name__}: {str(e)[:80]})")
        print(f"  char proxy: p50~{chars[len(chars)//2]}  max~{chars[-1]}  (~chars/4 = rough tokens)")


if __name__ == "__main__":
    build()
