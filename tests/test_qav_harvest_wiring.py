"""QAV harvest-mode wiring tests (S2b) — ratified-outcomes ingestion, census-safe bundle
location (skip-filter), label-fixed teacher <think>, the evidence-empty pre-gate on the harvest
path, and the honest manifest/balance verdict at the real expected N.

Drives ``qav.generate.run_generation`` in ``mode='harvest'`` against STUB teacher/coach — zero
real model calls, zero network. The harvest bundles are REAL committed shapes materialised into a
tmp corpus root (never the live corpus). Mirrors the seeded-path test conventions.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from qav.contracts import extract_label, validate_row
from qav.generate import (
    CoachVerdict,
    GenerateConfig,
    LoadedOutcomes,
    OutcomesSchemaError,
    discover_final_turn_bundles,
    load_harvest_outcomes,
    run_generation,
)

# A real-shaped healthy green bundle (ugly-green via advisory_issues so any approve subset clears
# the ugly-green floor, matching the census's 76/82 finals).
_GREEN = {
    "honesty": {"discrepancies": [], "should_fix_count": 0},
    "gathering_status": "complete",
    "tests": {"passed": True},
    "advisory_issues": [{"msg": "cosmetic"}],
}
# The round-3 evidence-empty poison (partial_exception + missing_results) — poison in any mode.
_POISON = {
    "honesty": {"verified": True, "discrepancies": []},
    "gathering_status": "partial_exception",
    "gathering_error": "missing_results: task_work_results.json absent",
    "tests": None,
}


# --------------------------------------------------------------------------------------
# Stubs.
# --------------------------------------------------------------------------------------
class StubTeacher:
    def __init__(self, output: str | None = None):
        self._output = output
        self.calls = 0
        self.last_user = ""

    def complete(self, system: str, user: str) -> str:
        self.calls += 1
        self.last_user = user
        if self._output is not None:
            return self._output
        return (
            "<think>\nReading gathering_status='complete' with advisory_issues present: an honest "
            "green carrying a cosmetic blemish. Per-task green is not feature green.\n</think>"
        )


class StubCoach:
    def __init__(self, decision: str = "accept"):
        self.decision = decision
        self.calls = 0
        self.last_label = None

    def assess(self, bundle, think, label) -> CoachVerdict:
        self.calls += 1
        self.last_label = label
        return CoachVerdict(decision=self.decision, reasons=["stub"])


def _write_bundle(root: Path, task: str, bundle: dict, *, turn: int = 2,
                  sub: str = ".guardkit/autobuild") -> Path:
    d = root / sub / task
    d.mkdir(parents=True, exist_ok=True)
    p = d / f"coach_evidence_turn_{turn}.json"
    p.write_text(json.dumps(bundle), encoding="utf-8")
    return p


def _outcomes_yaml(tmp_path: Path, entries: list[dict], *, version=1) -> Path:
    import yaml
    p = tmp_path / "outcomes.yaml"
    p.write_text(yaml.safe_dump({"version": version, "outcomes": entries}), encoding="utf-8")
    return p


def _consumable(repo="guardkit", task="TASK-BDDW-001", feature="FEAT-E2CB",
                sha="917bcef7", source="coach_correct", **over) -> dict:
    d = {"repo": repo, "feature": feature, "task": task, "run": "archive/FEAT-E2CB",
         "sha": sha, "ground_truth_source": source, "disposition": "consumable"}
    d.update(over)
    return d


def _cfg(tmp_path, corpus_roots, **over):
    base = dict(
        mode="harvest",
        holdout_fraction=0.0,
        output_dir=str(tmp_path / "out"),
        manifest_path=str(tmp_path / "manifests" / "train.manifest.json"),
        scratch_dir=str(tmp_path / "scratch"),
        seed="qav-test",
        corpus_roots={k: str(v) for k, v in corpus_roots.items()},
    )
    base.update(over)
    return GenerateConfig(**base)


def _run(cfg, *, teacher=None, coach=None, outcomes=None, **kw):
    return run_generation(
        cfg,
        teacher=teacher or StubTeacher(),
        coach=coach or StubCoach(),
        regenerator=None,  # harvest never regenerates — real bundles are read from disk
        source_tasks=[],
        outcomes=outcomes,
        emit_gold_negatives=False,
        created="2026-07-21", factory_sha="test",
        **kw,
    )


# --------------------------------------------------------------------------------------
# 1. Census-safe discovery — the skip-filter (the jarvis .claude/worktrees footgun).
# --------------------------------------------------------------------------------------
def test_discovery_skips_claude_worktrees_decoy(tmp_path):
    repo = tmp_path / "repo"
    # the authentic final-turn record (turn 2)
    _write_bundle(repo, "TASK-A", _GREEN, turn=2)
    # a jarvis worktree DECOY with a HIGHER turn — must NOT win despite the rglob tie-break
    _write_bundle(repo, "TASK-A", {"honesty": {}, "gathering_status": "complete", "profile_name": "DECOY"},
                  turn=9, sub=".claude/worktrees/FEAT-X/.guardkit/autobuild")

    index = discover_final_turn_bundles({"repo": repo})
    assert set(index) == {("repo", "TASK-A")}
    art = index[("repo", "TASK-A")]
    assert art.turn == 2  # the real record, not the turn-9 decoy
    assert art.bundle.get("profile_name") != "DECOY"
    assert ".claude/worktrees" not in art.path.as_posix()


def test_discovery_keeps_guardkit_worktrees(tmp_path):
    # .guardkit/worktrees is a LEGITIMATE record location (only .claude/worktrees is skipped).
    repo = tmp_path / "repo"
    _write_bundle(repo, "TASK-B", _GREEN, turn=2,
                  sub=".guardkit/worktrees/FEAT-E2CB/.guardkit/autobuild")
    index = discover_final_turn_bundles({"repo": repo})
    assert ("repo", "TASK-B") in index


def test_discovery_final_turn_deterministic(tmp_path):
    repo = tmp_path / "repo"
    _write_bundle(repo, "TASK-C", {"honesty": {}, "gathering_status": "partial_exception"}, turn=1)
    _write_bundle(repo, "TASK-C", _GREEN, turn=3)
    index = discover_final_turn_bundles({"repo": repo})
    assert index[("repo", "TASK-C")].turn == 3


# --------------------------------------------------------------------------------------
# 2. Outcomes-yaml ingestion — valid / malformed / queued-skipped.
# --------------------------------------------------------------------------------------
def test_load_outcomes_none_is_inert():
    loaded = load_harvest_outcomes(None)
    assert loaded == LoadedOutcomes({}, 0)


def test_load_outcomes_valid_and_queued_skipped(tmp_path):
    p = _outcomes_yaml(tmp_path, [
        _consumable(task="TASK-BDDW-001"),
        _consumable(task="TASK-BDDW-002"),
        _consumable(task="PO02-001", repo="study-tutor", feature="FEAT-PO-002",
                    sha="unresolved", disposition="queued", note="A3"),
        _consumable(task="DD4F-x", disposition="flagged", note="U2 task-id blank"),
    ])
    loaded = load_harvest_outcomes(p)
    assert set(loaded.outcomes) == {("guardkit", "TASK-BDDW-001"), ("guardkit", "TASK-BDDW-002")}
    assert loaded.skipped == 2  # the queued + the flagged
    assert loaded.outcomes[("guardkit", "TASK-BDDW-001")].ground_truth_source == "coach_correct"


def test_load_outcomes_reject_source_requires_finding(tmp_path):
    p = _outcomes_yaml(tmp_path, [
        _consumable(source="operator_caught"),  # reject source, no finding
    ])
    with pytest.raises(OutcomesSchemaError, match="no finding"):
        load_harvest_outcomes(p)


def test_load_outcomes_reject_source_with_finding_ok(tmp_path):
    p = _outcomes_yaml(tmp_path, [
        _consumable(source="operator_caught",
                    finding={"class": "DC-08", "locus": "cli/main.py"}),
    ])
    loaded = load_harvest_outcomes(p)
    oc = loaded.outcomes[("guardkit", "TASK-BDDW-001")]
    assert oc.finding == {"class": "DC-08", "locus": "cli/main.py"}


@pytest.mark.parametrize("mutate,match", [
    (lambda d: d.__setitem__("version", 2), "version"),
    (lambda d: d.__setitem__("outcomes", {"not": "a list"}), "must be a list"),
    (lambda d: d["outcomes"][0].pop("sha"), "missing keys"),
    (lambda d: d["outcomes"][0].__setitem__("disposition", "maybe"), "disposition"),
    (lambda d: (d["outcomes"][0].update(
        {"ground_truth_source": "seeded", "finding": {"class": "DC-03", "locus": "x"}})), "seeded"),
    (lambda d: d["outcomes"].__setitem__(0, "notadict"), "must be a mapping"),
])
def test_load_outcomes_malformed_is_loud(tmp_path, mutate, match):
    import yaml
    data = {"version": 1, "outcomes": [_consumable()]}
    mutate(data)
    p = tmp_path / "bad.yaml"
    p.write_text(yaml.safe_dump(data), encoding="utf-8")
    with pytest.raises(OutcomesSchemaError, match=match):
        load_harvest_outcomes(p)


def test_load_outcomes_missing_file_is_loud(tmp_path):
    with pytest.raises(OutcomesSchemaError, match="does not exist"):
        load_harvest_outcomes(tmp_path / "nope.yaml")


# --------------------------------------------------------------------------------------
# 3. End-to-end harvest via the config-load path (outcomes=None -> yaml).
# --------------------------------------------------------------------------------------
def test_harvest_run_from_config_yaml_banks_rows(tmp_path):
    repo = tmp_path / "guardkit"
    _write_bundle(repo, "TASK-BDDW-001", _GREEN, turn=1)
    _write_bundle(repo, "TASK-BDDW-002", {**_GREEN, "profile_name": "b2"}, turn=2)
    outcomes = _outcomes_yaml(tmp_path, [
        _consumable(task="TASK-BDDW-001"),
        _consumable(task="TASK-BDDW-002"),
    ])
    cfg = _cfg(tmp_path, {"guardkit": repo}, harvest_outcomes_path=str(outcomes))
    teacher, coach = StubTeacher(), StubCoach()
    summary = _run(cfg, teacher=teacher, coach=coach)  # outcomes=None -> loads yaml

    assert summary.harvest_written == 2
    assert teacher.calls == 2 and coach.calls == 2
    rows = [json.loads(x) for x in (tmp_path / "out" / "train.jsonl").read_text().splitlines()]
    assert len(rows) == 2
    for r in rows:
        validate_row(r)
        assert r["metadata"]["generation_mode"] == "harvest"
        assert r["metadata"]["provenance"]["sha"] == "917bcef7"
        assert extract_label(r)["ground_truth_source"] == "coach_correct"


def test_harvest_skips_queued_and_counts_them(tmp_path):
    repo = tmp_path / "guardkit"
    _write_bundle(repo, "TASK-BDDW-001", _GREEN)
    outcomes = _outcomes_yaml(tmp_path, [
        _consumable(task="TASK-BDDW-001"),
        _consumable(task="PO02-001", disposition="queued"),
    ])
    cfg = _cfg(tmp_path, {"guardkit": repo}, harvest_outcomes_path=str(outcomes))
    summary = _run(cfg)
    assert summary.harvest_written == 1
    assert summary.harvest_outcomes_skipped == 1


# --------------------------------------------------------------------------------------
# 4. Label-fixed teacher — the <think> is authored AGAINST the ratified label, never derived.
# --------------------------------------------------------------------------------------
def test_teacher_think_is_authored_against_the_fixed_label(tmp_path):
    from qav.harvest import Outcome
    repo = tmp_path / "guardkit"
    _write_bundle(repo, "TASK-BDDW-001", _GREEN)
    # a teacher whose output CONTRADICTS the verdict must not change the row label.
    teacher = StubTeacher(output="<think>this looks like a reject to me</think>")
    coach = StubCoach()
    summary = _run(
        _cfg(tmp_path, {"guardkit": repo}), teacher=teacher, coach=coach,
        outcomes={("guardkit", "TASK-BDDW-001"): Outcome(
            ground_truth_source="coach_correct", feature="FEAT-E2CB", run="r", sha="917bcef7")},
    )
    assert summary.harvest_written == 1
    # the fixed verdict is threaded into the teacher prompt AND is what the coach judges against.
    assert "approve" in teacher.last_user
    assert coach.last_label["verdict"] == "approve"
    row = json.loads((tmp_path / "out" / "train.jsonl").read_text().splitlines()[0])
    assert extract_label(row)["verdict"] == "approve"  # NOT the teacher's "reject"


def test_teacher_refusal_is_a_loud_reject(tmp_path):
    from qav.harvest import Outcome
    repo = tmp_path / "guardkit"
    _write_bundle(repo, "TASK-BDDW-001", _GREEN)
    summary = _run(
        _cfg(tmp_path, {"guardkit": repo}), teacher=StubTeacher(output="   "),
        outcomes={("guardkit", "TASK-BDDW-001"): Outcome(
            ground_truth_source="coach_correct", feature="F", run="r", sha="s")},
    )
    assert summary.teacher_refused == 1 and summary.harvest_written == 0
    rej = [json.loads(x) for x in (tmp_path / "out" / "rejected.jsonl").read_text().splitlines()]
    assert rej and rej[0]["reason"] == "teacher_refusal"


def test_coach_revise_routes_to_rejected(tmp_path):
    from qav.harvest import Outcome
    repo = tmp_path / "guardkit"
    _write_bundle(repo, "TASK-BDDW-001", _GREEN)
    summary = _run(
        _cfg(tmp_path, {"guardkit": repo}), coach=StubCoach(decision="revise"),
        outcomes={("guardkit", "TASK-BDDW-001"): Outcome(
            ground_truth_source="coach_correct", feature="F", run="r", sha="s")},
    )
    assert summary.coach_rejected == 1 and summary.harvest_written == 0
    rej = [json.loads(x) for x in (tmp_path / "out" / "rejected.jsonl").read_text().splitlines()]
    assert rej[0]["reason"] == "coach_rejected"


def test_consumable_with_no_bundle_on_disk_is_loud(tmp_path):
    from qav.harvest import Outcome
    repo = tmp_path / "guardkit"  # empty — no bundles
    repo.mkdir()
    summary = _run(
        _cfg(tmp_path, {"guardkit": repo}),
        outcomes={("guardkit", "TASK-GONE"): Outcome(
            ground_truth_source="coach_correct", feature="F", run="r", sha="s")},
    )
    assert summary.harvest_bundle_not_found == 1 and summary.harvest_written == 0
    rej = [json.loads(x) for x in (tmp_path / "out" / "rejected.jsonl").read_text().splitlines()]
    assert rej[0]["reason"] == "bundle_not_found"


# --------------------------------------------------------------------------------------
# 5. The evidence-empty pre-gate applies on the harvest path — BEFORE the teacher call.
# --------------------------------------------------------------------------------------
def test_evidence_empty_bundle_rejected_before_teacher(tmp_path):
    from qav.harvest import Outcome
    repo = tmp_path / "guardkit"
    _write_bundle(repo, "TASK-POISON", _POISON)
    teacher, coach = StubTeacher(), StubCoach()
    summary = _run(
        _cfg(tmp_path, {"guardkit": repo}), teacher=teacher, coach=coach,
        outcomes={("guardkit", "TASK-POISON"): Outcome(
            ground_truth_source="coach_correct", feature="F", run="r", sha="s")},
    )
    assert summary.evidence_empty_rejected == 1 and summary.harvest_written == 0
    assert teacher.calls == 0 and coach.calls == 0  # pre-gate runs first — no wasted GPU
    rej = [json.loads(x) for x in (tmp_path / "out" / "rejected.jsonl").read_text().splitlines()]
    assert rej[0]["reason"] == "evidence_empty_bundle"
    assert rej[0]["gathering_status"] == "partial_exception"


def test_gold_source_task_excluded_from_harvest(tmp_path):
    from qav.harvest import Outcome
    # study-tutor / TASK-SMP3-06 is a gold-negative source (GN-2) — never a harvest row.
    repo = tmp_path / "study-tutor"
    _write_bundle(repo, "TASK-SMP3-06", _GREEN)
    summary = _run(
        _cfg(tmp_path, {"study-tutor": repo}),
        outcomes={("study-tutor", "TASK-SMP3-06"): Outcome(
            ground_truth_source="coach_correct", feature="FEAT-SMP-003", run="r", sha="s")},
    )
    assert summary.harvest_written == 0
    assert summary.gold_source_skipped == 1


# --------------------------------------------------------------------------------------
# 6. Honest manifest/balance verdict at the real expected N (approve-only -> advisory fail).
# --------------------------------------------------------------------------------------
def test_manifest_finalizes_but_records_balance_refusal_on_approve_only(tmp_path):
    # The census reality: today's consumable labels are approve-only (rejects are eval-holdout
    # golds). validate_manifest gates ONLY contamination, so the run FINALIZES; balance is the
    # advisory verdict — recorded loudly, rows still banked, manifest still written.
    repo = tmp_path / "guardkit"
    _write_bundle(repo, "TASK-BDDW-001", _GREEN, turn=1)
    _write_bundle(repo, "TASK-BDDW-002", {**_GREEN, "profile_name": "b2"}, turn=2)
    outcomes = _outcomes_yaml(tmp_path, [
        _consumable(task="TASK-BDDW-001"),
        _consumable(task="TASK-BDDW-002"),
    ])
    cfg = _cfg(tmp_path, {"guardkit": repo}, harvest_outcomes_path=str(outcomes))
    summary = _run(cfg, write_manifest=True)

    assert summary.harvest_written == 2
    assert summary.manifest_finalized is True          # NOT crashed
    assert summary.manifest_approve_share == 1.0        # approve-only
    assert summary.manifest_balance_ok is False         # advisory refusal recorded
    assert any("approve_share" in v for v in summary.manifest_balance_violations)
    # rows banked + manifest written honestly (contamination passes -> valid manifest).
    assert len((tmp_path / "out" / "train.jsonl").read_text().splitlines()) == 2
    manifest = json.loads((tmp_path / "out" / "manifest.json").read_text())
    assert manifest["contamination_check"]["status"] == "pass"
    assert manifest["counts"]["by_verdict"] == {"approve": 2, "reject": 0}
    assert manifest["counts"]["by_generation_mode"]["harvest"] == 2
