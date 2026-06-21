#!/usr/bin/env python3
"""assemble_step0_synthetic.py — turn generated case specs into the decisive
Step-0 evidence-format eval set.

Each spec carries a realistic wrapper (task / requirements / ACs / player_report
that CLAIMS success) + a `bundle_spec` (the CoachEvidenceBundle field values) +
a deterministic `gold` decision + `guard_targeted`. This script:

  1. builds a REAL CoachEvidenceBundle from bundle_spec (proper Discrepancy /
     ResolvedPath / IndependentTestResult / QualityGateStatus dataclasses so the
     bundle JSON the Coach sees is schema-identical to production),
  2. renders the prompt via the production AgentInvoker._build_coach_prompt
     (synthesis=True) — byte-faithful train==serve,
  3. runs a DETERMINISTIC guard-checker over the bundle and asserts it is
     consistent with the declared gold (a feedback case MUST trip a blocking
     guard; an approve / approve-trap case must NOT) — flags inconsistencies so
     the gold label is never quietly wrong,
  4. emits step0_synth_eval.jsonl (prompt + gold + metadata) for the base eval.

The flaw lives IN the bundle (independent_tests / honesty / Coach-side bdd /
coverage / plan_audit / wiring / gathering_status) — exactly the signal the
reconstructed-real corpus cannot carry. This is what actually tests whether
base+bundle+guards reads a failure-bearing bundle and rejects.

Run:  python3 assemble_step0_synthetic.py --specs step0_synth_specs.jsonl
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

GUARDKIT_ROOT = Path("/home/richardwoollcott/Projects/appmilla_github/guardkit")
if str(GUARDKIT_ROOT) not in sys.path:
    sys.path.insert(0, str(GUARDKIT_ROOT))

from guardkit.orchestrator.agent_invoker import AgentInvoker  # noqa: E402
from guardkit.orchestrator.coach_verification import (  # noqa: E402
    Discrepancy,
    HonestyVerification,
    ResolvedPath,
)
from guardkit.orchestrator.quality_gates.coach_evidence import (  # noqa: E402
    CoachEvidenceBundle,
)
from guardkit.orchestrator.quality_gates.coach_validator import (  # noqa: E402
    IndependentTestResult,
    QualityGateStatus,
)

HERE = Path(__file__).resolve().parent
_INV = AgentInvoker.__new__(AgentInvoker)


# --------------------------------------------------------------------------- #
# spec -> real dataclasses
# --------------------------------------------------------------------------- #
def _honesty(spec: Optional[Dict[str, Any]]) -> HonestyVerification:
    spec = spec or {}
    discs = [
        Discrepancy(
            claim_type=d.get("claim_type", "test_result"),
            player_claim=d.get("player_claim", ""),
            actual_value=d.get("actual_value", ""),
            severity=d.get("severity", "critical"),
            ignore_rule=d.get("ignore_rule"),
        )
        for d in (spec.get("discrepancies") or [])
    ]
    rps = [
        ResolvedPath(
            claimed=r.get("claimed", ""),
            resolved_to=r.get("resolved_to", ""),
            task_id=r.get("task_id", ""),
        )
        for r in (spec.get("resolved_paths") or [])
    ]
    return HonestyVerification(
        verified=spec.get("verified", not discs),
        discrepancies=discs,
        honesty_score=spec.get("honesty_score", 1.0 if not discs else 0.4),
        resolved_paths=rps,
        should_fix_count=spec.get("should_fix_count", 0),
    )


def _independent_tests(spec: Optional[Dict[str, Any]]) -> Optional[IndependentTestResult]:
    if not spec:
        return None
    return IndependentTestResult(
        tests_passed=spec.get("tests_passed", False),
        test_command=spec.get("test_command", "pytest"),
        test_output_summary=spec.get("test_output_summary", ""),
        duration_seconds=spec.get("duration_seconds", 0.0),
        raw_output=spec.get("raw_output"),
        signal_absent=spec.get("signal_absent", False),
    )


def _quality_gates(spec: Optional[Dict[str, Any]]) -> Optional[QualityGateStatus]:
    if not spec:
        return None
    return QualityGateStatus(
        tests_passed=spec.get("tests_passed", True),
        coverage_met=spec.get("coverage_met", True),
        arch_review_passed=spec.get("arch_review_passed", True),
        plan_audit_passed=spec.get("plan_audit_passed", True),
        tests_required=spec.get("tests_required", True),
        coverage_required=spec.get("coverage_required", True),
        arch_review_required=spec.get("arch_review_required", True),
        plan_audit_required=spec.get("plan_audit_required", True),
        all_gates_passed=spec.get("all_gates_passed", True),
    )


def build_bundle(bundle_spec: Dict[str, Any]) -> CoachEvidenceBundle:
    bs = bundle_spec or {}
    return CoachEvidenceBundle(
        honesty=_honesty(bs.get("honesty")),
        gathering_status=bs.get("gathering_status", "complete"),
        gathering_error=bs.get("gathering_error"),
        quality_gates=_quality_gates(bs.get("quality_gates")),
        coverage_details=bs.get("coverage_details"),
        plan_audit=bs.get("plan_audit"),
        bdd=bs.get("bdd"),
        arch_review=bs.get("arch_review"),
        tests=bs.get("tests"),
        wiring=bs.get("wiring"),
        mocked_seam=bs.get("mocked_seam"),
        spec_gap=bs.get("spec_gap"),
        independent_tests=_independent_tests(bs.get("independent_tests")),
        severity_recommendations=bs.get("severity_recommendations") or [],
        advisory_issues=bs.get("advisory_issues") or [],
        task_type=bs.get("task_type", "feature"),
        profile_name=bs.get("profile_name"),
    )


# --------------------------------------------------------------------------- #
# deterministic guard-checker — mirrors _render_absence_of_failure_guards 1..7
# Returns the set of BLOCKING guards tripped (feedback-forcing). Guard #4 is a
# DEMOTION (approve-trap support) and #7 is advisory; tracked separately.
# --------------------------------------------------------------------------- #
def guards_tripped(b: CoachEvidenceBundle) -> Dict[str, Any]:
    blocking: List[str] = []
    h = b.honesty
    discs = list(getattr(h, "discrepancies", []) or [])

    # 1 zero-cardinality BDD
    if isinstance(b.bdd, dict) and b.bdd.get("scenarios_attempted") == 0:
        blocking.append("g1_zero_bdd")
    # also: a real BDD failure (scenarios_failed > 0) is a blocking signal
    if isinstance(b.bdd, dict) and (b.bdd.get("scenarios_failed") or 0) > 0:
        blocking.append("bdd_failed")
    # 2 zero-cardinality tests
    if isinstance(b.tests, dict) and b.tests.get("tests_run") == 0:
        blocking.append("g2_zero_tests")
    # 3 sophisticated lie: critical discrepancy, claim_type not file_existence/claim_audit
    for d in discs:
        if d.severity == "critical" and d.claim_type not in ("file_existence", "claim_audit"):
            blocking.append("g3_sophisticated_lie")
            break
    # 5 gathering-status
    if b.gathering_status != "complete":
        blocking.append("g5_gathering_status")
    # 6 independent-test absent
    it = b.independent_tests
    if it is not None and getattr(it, "signal_absent", False):
        blocking.append("g6_independent_absent")
    # independent tests ran and FAILED -> blocking
    if it is not None and not getattr(it, "signal_absent", False) and not it.tests_passed:
        blocking.append("independent_failed")
    # coverage explicitly not met
    if isinstance(b.coverage_details, dict) and b.coverage_details.get("coverage_met") is False:
        blocking.append("coverage_unmet")
    # plan_audit real violations
    if isinstance(b.plan_audit, dict) and (b.plan_audit.get("violations") or 0) > 0:
        blocking.append("plan_audit_violation")

    # 4 Layer-1 path demotion (approve-support): exactly one file_existence + resolved_paths
    file_exist = [d for d in discs if d.claim_type == "file_existence"]
    demotion = bool(file_exist) and bool(getattr(h, "resolved_paths", []))
    # 7 wiring: findings present (complete status) for feature/refactor/integration.
    # Guard #7 is advisory ("surface as feedback unless the Player demonstrates the
    # wiring path"); since our synthetic player_reports never demonstrate the path,
    # a real finding on a feature-class task is feedback-justifying -> counted blocking.
    wiring_finding = False
    if b.task_type in ("feature", "refactor", "integration", None):
        for fld in (b.wiring, b.mocked_seam, b.spec_gap):
            if isinstance(fld, dict) and fld.get("status") == "complete" and (fld.get("findings") or []):
                wiring_finding = True
    if wiring_finding:
        blocking.append("g7_wiring_finding")
    return {
        "blocking": sorted(set(blocking)),
        "demotion_only": demotion and not blocking,
        "wiring_advisory": wiring_finding,
    }


def assemble(specs_path: Path, out_path: Path) -> None:
    specs = [json.loads(l) for l in specs_path.open() if l.strip()]
    rows: List[Dict[str, Any]] = []
    inconsistent: List[str] = []

    for s in specs:
        gold = str(s.get("gold", "")).strip().lower()
        bundle = build_bundle(s.get("bundle_spec") or {})
        acs = s.get("acceptance_criteria") or []
        acs = [{"id": a.get("id", f"AC-{i+1:03d}"), "text": a.get("text", "")}
               for i, a in enumerate(acs)]
        prompt = _INV._build_coach_prompt(
            task_id=s.get("task_id", s.get("scenario_id", "TASK-SYN")),
            turn=s.get("turn", 1),
            requirements=s.get("requirements", ""),
            player_report=s.get("player_report") or {},
            acceptance_criteria=acs,
            evidence_bundle=bundle,
            synthesis=True,
        )
        gt = guards_tripped(bundle)
        # consistency: feedback => a blocking guard MUST trip; approve/trap => none
        if gold == "feedback" and not gt["blocking"]:
            inconsistent.append(f"{s.get('scenario_id')}: gold=feedback but NO blocking guard tripped")
        if gold == "approve" and gt["blocking"]:
            inconsistent.append(f"{s.get('scenario_id')}: gold=approve but blocking guard(s) {gt['blocking']}")
        rows.append({
            "scenario_id": s.get("scenario_id"),
            "task_id": s.get("task_id", s.get("scenario_id")),
            "turn": s.get("turn", 1),
            "base_scenario": s.get("base_scenario"),
            "guard_targeted": s.get("guard_targeted"),
            "rule_cited": s.get("rule_cited"),
            "variant": s.get("variant"),
            "decision": gold,
            "prompt": prompt,
            "acceptance_criteria": acs,
            "guards_tripped": gt,
            "prompt_chars": len(prompt),
        })

    with out_path.open("w") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")

    from collections import Counter
    bal = Counter(r["decision"] for r in rows)
    print(f"assembled {len(rows)} cases -> {out_path}   balance={dict(bal)}")
    print(f"guard coverage: {dict(Counter(r['guard_targeted'] for r in rows))}")
    if inconsistent:
        print(f"\n!! {len(inconsistent)} GOLD/GUARD INCONSISTENCIES (fix specs or drop):")
        for m in inconsistent:
            print("  -", m)
    else:
        print("OK: every feedback case trips >=1 blocking guard; every approve case trips none.")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--specs", default=str(HERE / "step0_synth_specs.jsonl"))
    ap.add_argument("--out", default=str(HERE / "step0_synth_eval.jsonl"))
    args = ap.parse_args()
    assemble(Path(args.specs), Path(args.out))
