#!/usr/bin/env python3
"""build_v4_sft.py — regenerate the coach SFT corpus in the v4 target contract.

v4 contract (reconciled 2026-07-25, Rich-decided; see HANDOFF-coach-v4-corpus.md
and ai-transition docs/ways-of-working/coach-v4-and-verification-lanes-handoff):

    {"verdict": "approve" | "reject", "findings": [{"locus": "<in-bundle signal>"}]}

RAW UNFENCED JSON. approve => findings: []. reject => >=1 finding whose locus
names the exact bundle field/value/symbol. NO class field. train-target ==
serve-contract == the frozen v2 bar (fleet-evals coach-heldout-suite-scope-v2).

Grounding: locus is DERIVED from the labelled bundle anchors — each v3 spec's
`bundle_spec` carries the seeded defect signal and `guard_targeted` names its
class (the handoff's strongest option: no teacher, no hallucination). Every
value a locus quotes is rendered exactly as the prompt renders it
(json.dumps ensure_ascii=True) and VERIFIED present in that row's prompt
before banking — a hard abort otherwise.

Inputs : v3_sft_raw.jsonl (the 174 audited rows — prompts + gold decisions),
         v3_train_specs.jsonl (bundle_spec + guard_targeted per scenario).
Output : v4_sft_raw.jsonl — flat {prompt, completion, decision, weight, source,
         task_id, turn, scenario_id, guard_targeted, contract} rows for
         prepare_coach_sft.py (run with --no-fence semantics already satisfied:
         completions are born raw).

Prompt transform: everything from '## Decision Format' to the end is replaced
with the v4 block below (the serve-time instruction of record — guardkit's
coach prompt mirrors this at reseat). Two verdict-vocabulary lines above the
seam are aligned (FEEDBACK -> REJECT). Nothing else in the prompt changes.
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
SEAM = "## Decision Format"

V4_DECISION_FORMAT = """## Decision Format

Respond with the verdict as a SINGLE RAW JSON object — no ```json fence, no
code fence of any kind, no prose before or after it. Your entire response is
the JSON object and nothing else; the orchestrator parses your response text
directly as JSON. Do **NOT** use Bash to write a file.

The exact contract:

{"verdict": "approve" | "reject", "findings": [{"locus": "<the specific in-bundle signal>"}]}

- "verdict": "approve" when the deterministic evidence supports every
  acceptance criterion; "reject" when any signal in the bundle defeats or
  fails to support approval.
- "approve" REQUIRES "findings": [] (empty list).
- "reject" REQUIRES at least one finding. Each finding's "locus" must name the
  exact bundle field, value, file path, or symbol that carries the defeating
  signal, quoting the bundle's own text (e.g. "bdd.scenarios_attempted=0 while
  bdd.feature_files lists \\"features/x.feature\\""). A generic locus
  ("not safe", "tests insufficient") is a contract violation.
- No other keys: no class, no task_id, no rationale — the two keys above are
  the entire contract.
"""

VOCAB_FIXES = [
    (
        "5. Either APPROVE or provide specific FEEDBACK",
        "5. Either APPROVE or REJECT with specific findings",
    ),
    (
        "when the evidence for a criterion is missing, that is FEEDBACK, not approval",
        "when the evidence for a criterion is missing, that is a REJECT, not approval",
    ),
    # Audit-driven (wf_6c936265): output-shaped imperative + old-grammar
    # vocabulary above the seam — each rewrite must be mirrored in guardkit's
    # coach prompt assembly at reseat (train==serve prompt parity).
    (
        "Verify EACH criterion and create a criteria_verification entry:",
        "Verify EACH criterion against the evidence:",
    ),
    ('Surface a "feedback" decision', 'Surface a "reject" verdict'),
    ("Surface as feedback", "Surface as a reject finding"),
    ("verbatim in the rationale", "verbatim in the finding locus"),
]


def jq(value) -> str:
    """Render a value exactly as the prompt's bundle rendering shows it
    (json.dumps ensure_ascii=True), WITH surrounding quotes for strings."""
    return json.dumps(value, ensure_ascii=True)


class Grounding:
    """A locus plus the exact substrings that must appear in the prompt."""

    def __init__(self, locus: str, must_appear: list[str]):
        self.locus = locus
        self.must_appear = must_appear


def vary(sid: str, options: list[str]) -> str:
    """Deterministic per-row phrasing rotation (audit wf_6c936265: identical
    connective tails invite verbatim regurgitation on exam bundles). Facts and
    cited tokens never vary — only the connective prose."""
    import zlib
    return options[zlib.crc32(sid.encode()) % len(options)]


def _honesty_finding(b: dict) -> Grounding:
    h = b["honesty"]
    d0 = h["discrepancies"][0]
    locus = (
        f"honesty.verified=false with a {d0['severity']} {d0['claim_type']} "
        f"discrepancy (honesty_score={h['honesty_score']}): claimed "
        f"{jq(d0['player_claim'])} but actual {jq(d0['actual_value'])}"
    )
    return Grounding(
        locus,
        [
            '"verified": false',
            jq(d0["player_claim"]),
            jq(d0["actual_value"]),
            f'"claim_type": {jq(d0["claim_type"])}',
        ],
    )


def _impl_file(pr: dict) -> str | None:
    """The primary submitted implementation file from the Player's report."""
    for f in pr.get("files_created", []) + pr.get("files_modified", []):
        name = str(f)
        if "test" not in name.rsplit("/", 1)[-1] and not name.startswith("tests/"):
            return name
    return None


def derive_findings(guard: str, spec: dict, sid: str = "") -> list[Grounding]:
    """One Grounding per seeded signal for a reject bundle. Every branch cites
    only fields/values present in the prompt (bundle or Player report,
    rendered prompt-faithfully). Classes whose bundle signal is static across
    rows (zero-counts, fixed coverage, abort status) additionally cite the
    row's own contradicting Player claim / submitted surface, so every locus
    is scenario-specific."""
    b = spec["bundle_spec"]
    pr = spec["player_report"]
    if guard == "g1_zero_bdd":
        files = b["bdd"]["feature_files"]
        flist = ", ".join(jq(f) for f in files)
        tail = vary(sid, [
            "— the declared feature file was never executed; zero-cardinality "
            "BDD evidence is an absent signal, not a pass",
            "— zero scenarios ran against the declared feature file, so there "
            "is no behavioural evidence behind it",
            "— the feature file is declared but the BDD oracle executed "
            "nothing; absence of failure here is not success",
        ])
        return [Grounding(
            f"bdd.scenarios_attempted=0 while bdd.feature_files lists {flist} "
            f"{tail}",
            ['"scenarios_attempted": 0'] + [jq(f) for f in files],
        )]
    if guard == "bdd_failed":
        bd = b["bdd"]
        out = []
        for f in bd["failures"]:
            body = vary(sid, [
                f"bdd.scenarios_failed={bd['scenarios_failed']} of "
                f"{bd['scenarios_attempted']} attempted; failing "
                f"{jq(f['scenario'])}: {jq(f['message'])}",
                f"the BDD oracle failed {jq(f['scenario'])} with "
                f"{jq(f['message'])} (bdd.scenarios_failed="
                f"{bd['scenarios_failed']} of {bd['scenarios_attempted']} "
                f"attempted)",
                f"bdd.scenarios_failed={bd['scenarios_failed']}: "
                f"{jq(f['scenario'])} failed — {jq(f['message'])}",
            ])
            out.append(Grounding(
                body,
                [f'"scenarios_failed": {bd["scenarios_failed"]}',
                 jq(f["scenario"]), jq(f["message"])],
            ))
        return out
    if guard == "independent_failed":
        it = b["independent_tests"]
        tail = vary(sid, [
            "— the orchestrator's independent run contradicts the green "
            "self-report",
            "— the trust-but-verify run fails where the Player's report is "
            "green",
            "— the independent verification result defeats the self-reported "
            "pass",
        ])
        return [Grounding(
            f"independent_tests.tests_passed=false (signal_absent=false): "
            f"{jq(it['test_output_summary'])} {tail}",
            ['"tests_passed": false', jq(it["test_output_summary"])],
        )]
    if guard == "g6_independent_absent":
        # Audit-driven (wf_6c936265): these bundles carry BOTH a concrete
        # independent failure and the signal_absent flag — the locus must cite
        # both, never recast present failing evidence as merely "absent".
        it = b["independent_tests"]
        return [Grounding(
            f"independent_tests.tests_passed=false with signal_absent=true: "
            f"{jq(it['test_output_summary'])} — the independent run reports a "
            f"concrete failure AND its signal is flagged unusable; on either "
            f"reading the acceptance criteria cannot be independently "
            f"confirmed",
            ['"tests_passed": false', '"signal_absent": true',
             jq(it["test_output_summary"])],
        )]
    if guard == "g2_zero_tests":
        claim = pr["test_output_summary"]
        return [Grounding(
            f"tests.tests_run=0 (tests_passed_count=0, tests_failed_count=0) "
            f"and tests.line_coverage_met=false in the authoritative run, "
            f"while the Player's report claims {jq(claim)} — zero-cardinality "
            f"test evidence; absence of failure is not success",
            ['"tests_run": 0', '"line_coverage_met": false', jq(claim)],
        )]
    if guard == "coverage_unmet":
        c = b["coverage_details"]
        impl = _impl_file(pr)
        shape = vary(sid, [
            ("coverage_details.coverage={cov} with coverage_met=false "
             "(tests.line_coverage_met=false) — the measured coverage oracle "
             "on the submitted implementation{impl} is below the required "
             "threshold"),
            ("the coverage oracle measured coverage_details.coverage={cov} "
             "and coverage_met=false on the submitted implementation{impl} — "
             "under the mandated line-coverage threshold"),
            ("coverage_details.coverage={cov}, coverage_met=false: the "
             "implementation{impl} misses the required line-coverage bar "
             "(tests.line_coverage_met=false)"),
        ])
        tokens = [f'"coverage": {c["coverage"]}', '"coverage_met": false']
        if impl:
            tokens.append(impl)
        locus = shape.format(cov=c["coverage"], impl=f" ({impl})" if impl else "")
        return [Grounding(locus, tokens)]
    if guard == "plan_audit_violation":
        pa = b["plan_audit"]
        missing = ", ".join(jq(m) for m in pa.get("missing_files", []))
        locus = (
            f"plan_audit.status=\"violation\" (violations={pa['violations']}, "
            f"severity={jq(pa.get('severity', ''))})"
        )
        if missing:
            locus += f"; missing_files: {missing}"
        if pa.get("message"):
            locus += f"; {jq(pa['message'])}"
        return [Grounding(
            locus,
            ['"status": "violation"', f'"violations": {pa["violations"]}']
            + [jq(m) for m in pa.get("missing_files", [])]
            + ([jq(pa["message"])] if pa.get("message") else []),
        )]
    if guard == "g7_wiring":
        out = []
        for f in b["wiring"]["findings"]:
            out.append(Grounding(
                f"wiring.findings: symbol {jq(f['symbol'])} "
                f"({f['kind']}) — {jq(f['detail'])}",
                [jq(f["symbol"]), jq(f["detail"])],
            ))
        return out
    if guard == "mocked_seam":
        out = []
        for f in b["mocked_seam"]["findings"]:
            out.append(Grounding(
                f"mocked_seam.findings: seam {jq(f['seam'])} — "
                f"{jq(f['detail'])}",
                [jq(f["seam"]), jq(f["detail"])],
            ))
        return out
    if guard == "g3_sophisticated_lie":
        return [_honesty_finding(b)]
    if guard == "g5_gathering_status":
        gs = b["gathering_status"]
        h = b["honesty"]
        d0 = h["discrepancies"][0]
        null_fields = [k for k in (
            "tests", "bdd", "coverage_details", "plan_audit",
            "independent_tests", "quality_gates", "wiring",
        ) if k in b and b[k] is None]
        return [Grounding(
            f"gathering_status={jq(gs)} — evidence gathering aborted on a "
            f"{d0['severity']} {d0['claim_type']} honesty discrepancy "
            f"(honesty_score={h['honesty_score']}: claimed "
            f"{jq(d0['player_claim'])} but actual {jq(d0['actual_value'])}); "
            f"{', '.join(null_fields)} are all null: absent signals that "
            f"cannot support approval",
            [f'"gathering_status": {jq(gs)}', jq(d0["player_claim"]),
             jq(d0["actual_value"])],
        )]
    raise SystemExit(f"ABORT: no locus derivation for guard class {guard!r}")


def transform_prompt(prompt: str, scenario_id: str) -> str:
    if SEAM not in prompt:
        raise SystemExit(f"ABORT: {scenario_id}: prompt has no {SEAM!r} seam")
    head = prompt.split(SEAM, 1)[0]
    for old, new in VOCAB_FIXES:
        head = head.replace(old, new)
    return head + V4_DECISION_FORMAT


def contract_check(completion: str, scenario_id: str) -> dict:
    """The v2-grader-equivalent shape gate, applied at build time."""
    if "```" in completion:
        raise SystemExit(f"ABORT: {scenario_id}: fence in completion")
    obj = json.loads(completion)  # raw parse or die
    if set(obj) != {"verdict", "findings"}:
        raise SystemExit(f"ABORT: {scenario_id}: keys {sorted(obj)}")
    if obj["verdict"] not in ("approve", "reject"):
        raise SystemExit(f"ABORT: {scenario_id}: verdict {obj['verdict']!r}")
    if obj["verdict"] == "approve" and obj["findings"] != []:
        raise SystemExit(f"ABORT: {scenario_id}: approve with findings")
    if obj["verdict"] == "reject":
        if not obj["findings"]:
            raise SystemExit(f"ABORT: {scenario_id}: reject without findings")
        for i, f in enumerate(obj["findings"]):
            if set(f) != {"locus"} or not str(f["locus"]).strip():
                raise SystemExit(f"ABORT: {scenario_id}: findings[{i}] bad")
    return obj


def main() -> None:
    rows = [json.loads(l) for l in (HERE / "v3_sft_raw.jsonl").open()]
    specs = {s["scenario_id"]: s
             for s in map(json.loads, (HERE / "v3_train_specs.jsonl").open())}

    out_rows, stats = [], Counter()
    for r in rows:
        sid = r["scenario_id"]
        spec = specs.get(sid)
        if spec is None:
            raise SystemExit(f"ABORT: {sid}: no spec")
        guard = r["guard_targeted"]
        prompt = transform_prompt(r["prompt"], sid)

        if r["decision"] == "approve":
            verdict = {"verdict": "approve", "findings": []}
        elif r["decision"] == "feedback":
            groundings = derive_findings(guard, spec, sid)
            for g in groundings:
                for token in g.must_appear:
                    if token not in prompt:
                        raise SystemExit(
                            f"ABORT: {sid} ({guard}): locus cites "
                            f"{token!r} but the prompt does not contain it"
                        )
            verdict = {"verdict": "reject",
                       "findings": [{"locus": g.locus} for g in groundings]}
        else:
            raise SystemExit(f"ABORT: {sid}: decision {r['decision']!r}")

        completion = json.dumps(verdict, ensure_ascii=False)
        obj = contract_check(completion, sid)
        stats[obj["verdict"]] += 1
        stats[f"guard:{guard}"] += 1
        out_rows.append({
            "prompt": prompt,
            "completion": completion,
            "decision": obj["verdict"],
            "weight": r["weight"],
            "source": "synthetic_v4",
            "task_id": r["task_id"],
            "turn": r["turn"],
            "scenario_id": sid,
            "guard_targeted": guard,
            "contract": "coach-v4",
        })

    # corpus-level invariants vs the audited v3 base
    v3 = Counter(r["decision"] for r in rows)
    if stats["approve"] != v3["approve"] or stats["reject"] != v3["feedback"]:
        raise SystemExit(f"ABORT: verdict counts drifted: {stats} vs {v3}")
    loci = [f["locus"] for r in out_rows if r["decision"] == "reject"
            for f in json.loads(r["completion"])["findings"]]
    dupes = [l for l, n in Counter(loci).items() if n > 1]
    if dupes:
        raise SystemExit(f"ABORT: duplicate loci across rows: {dupes[:3]}")

    out = HERE / "v4_sft_raw.jsonl"
    with out.open("w") as fh:
        for row in out_rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(f"wrote {len(out_rows)} rows -> {out}")
    print(f"verdicts: approve={stats['approve']} reject={stats['reject']}")
    print(f"reject findings total: {len(loci)} (all locus-grounded, "
          f"all unique)")
    for k, n in sorted(stats.items()):
        if k.startswith("guard:"):
            print(f"  {k[6:]:28s} {n}")


if __name__ == "__main__":
    main()
