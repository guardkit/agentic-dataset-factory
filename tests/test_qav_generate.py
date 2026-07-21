"""QAV generation-engine tests (PLAN §2 pipeline).

Drives ``qav.generate.run_generation`` end-to-end against STUB teacher / coach / regenerator —
**zero real model calls, zero live-seat/GPU work, zero network** (a test asserts the last by
poisoning ``socket.socket``). Covers: the seeded_code loop + seeded-control greens, the
seeded_bundle cap, split determinism + same-split-for-siblings, the Coach/teacher/cue reject
paths → rejected.jsonl (loud, never a crash), the manifest-must-pass guard, and the writer
``*.bak`` fresh-start behaviour.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from qav.contracts import RowValidationError, extract_label, validate_row
from qav.generate import (
    BundleMutation,
    CoachVerdict,
    GenerateConfig,
    OutputWriter,
    SourceTask,
    assign_split,
    build_bundle_mutations,
    cue_audit,
    evidence_empty_reason,
    run_generation,
)

# --------------------------------------------------------------------------------------
# Stubs — the injected Protocol clients. Nothing here touches a network or a real seat.
# --------------------------------------------------------------------------------------
_GREEN = {"honesty": {"discrepancies": []}, "gathering_status": "complete", "tests": {"passed": True}}


class StubTeacher:
    """Returns a canned <think> that names bundle fields (or a scripted refusal/garbage)."""

    def __init__(self, output: str | None = None):
        self._output = output
        self.calls = 0

    def complete(self, system: str, user: str) -> str:
        self.calls += 1
        if self._output is not None:
            return self._output
        return (
            "<think>\nReading gathering_status='complete' and the tests/honesty fields: "
            "production construction is unwitnessed here. Per-task green is not feature green.\n</think>"
        )


class StubCoach:
    """Consistency gate stub: accepts by default, or always revises."""

    def __init__(self, decision: str = "accept"):
        self.decision = decision
        self.calls = 0

    def assess(self, bundle, think, label) -> CoachVerdict:
        self.calls += 1
        return CoachVerdict(decision=self.decision, reasons=["stub"])


class StubRegenerator:
    """Returns a green-looking bundle, made UNIQUE per worktree (distinct code -> distinct
    evidence -> distinct row_id). The unique tag is a neutral hash — NEVER a recipe id or a
    sentinel (that would trip the cue-audit, exactly as the real gate intends)."""

    def __init__(self, base: dict | None = None):
        self.base = dict(base or _GREEN)
        self.calls = 0

    def regenerate(self, worktree: Path) -> dict:
        self.calls += 1
        b = dict(self.base)
        b["profile_name"] = "wt-" + hashlib.sha1(str(worktree).encode()).hexdigest()[:10]
        return b


def _cfg(tmp_path, **over):
    base = dict(
        mode="seeded_defect",
        holdout_fraction=0.0,
        output_dir=str(tmp_path / "out"),
        manifest_path=str(tmp_path / "manifests" / "train.manifest.json"),
        scratch_dir=str(tmp_path / "scratch"),
        seed="qav-test",
    )
    base.update(over)
    return GenerateConfig(**base)


# The real coach_validator wiring producer (analyze_wiring) — the only recipe this single-file
# map anchors is R-DC03-producer (see tests/test_qav_injector.py for the verbatim corpus source).
_PRODUCER_SRC = (
    "    try:\n"
    "        result = analyze_wiring(\n"
    "            authored_files=authored_files,\n"
    "            worktree_path=worktree_path,\n"
    "            task_type=task_type,\n"
    "            stack=stack_obj,\n"
    "        )\n"
    "        if result is None:\n"
    "            return None\n"
)


def _producer_task(task="TASK-P", repo="guardkit"):
    return SourceTask(
        repo=repo, feature="FEAT-X", task=task, sha="abc",
        files={"guardkit/orchestrator/quality_gates/coach_validator.py": _PRODUCER_SRC},
    )


def _run(cfg, source_tasks=None, teacher=None, coach=None, regen=None, **kw):
    return run_generation(
        cfg,
        teacher=teacher or StubTeacher(),
        coach=coach or StubCoach(),
        regenerator=regen or StubRegenerator(),
        source_tasks=source_tasks if source_tasks is not None else [],
        created="2026-07-20", factory_sha="test",
        **kw,
    )


# --------------------------------------------------------------------------------------
# End-to-end seeded_code + control.
# --------------------------------------------------------------------------------------
def test_seeded_code_and_control_emit_valid_rows(tmp_path):
    cfg = _cfg(tmp_path)
    summary = _run(cfg, [_producer_task()], emit_gold_negatives=False)

    assert summary.seeded_code_written == 1  # only R-DC03-producer anchors this fixture
    assert summary.seeded_control_written == 1
    assert summary.anchor_skipped >= 1  # the other recipes found no anchor (loud skip)

    rows = [json.loads(line) for line in (tmp_path / "out" / "train.jsonl").read_text().splitlines()]
    assert len(rows) == 2
    verdicts = sorted(extract_label(r)["verdict"] for r in rows)
    assert verdicts == ["approve", "reject"]
    for r in rows:
        validate_row(r)
        assert r["metadata"]["generation_mode"] == "seeded_code"
    reject = next(r for r in rows if extract_label(r)["verdict"] == "reject")
    assert reject["metadata"]["dc_class"] == "DC-03"
    assert reject["metadata"]["injection_recipe"] == "R-DC03-producer"
    assert extract_label(reject)["ground_truth_source"] == "seeded"


def test_manifest_written_and_valid(tmp_path):
    cfg = _cfg(tmp_path)
    _run(cfg, [_producer_task()], emit_gold_negatives=False)
    manifest = json.loads((tmp_path / "out" / "manifest.json").read_text())
    assert manifest["contamination_check"]["status"] == "pass"
    assert manifest["visibility"] == "private (DF-008)"
    # written to BOTH the output dir and the configured handover path
    assert (tmp_path / "manifests" / "train.manifest.json").exists()


def test_gold_negatives_always_land_in_eval(tmp_path):
    cfg = _cfg(tmp_path)
    summary = _run(cfg, [_producer_task()], emit_gold_negatives=True)
    assert summary.gold_negatives_written == 4
    eval_rows = [json.loads(line) for line in (tmp_path / "out" / "eval_qav.jsonl").read_text().splitlines()]
    assert all(r["metadata"]["split"] == "eval_qav" for r in eval_rows)
    assert sum(1 for r in eval_rows if r["metadata"]["generation_mode"] == "gold_negative") == 4


def test_gold_negative_source_task_is_skipped(tmp_path):
    cfg = _cfg(tmp_path)
    # study-tutor / TASK-SMP3-06 is a gold-negative source task (GN-2) — must never seed a row.
    gold_src = SourceTask(
        repo="study-tutor", feature="FEAT-SMP-003", task="TASK-SMP3-06", sha="x",
        files={"src/evidence.py": "def gather():\n    behavioural_oracle = compute_oracle(t)\n    return behavioural_oracle\n"},
    )
    summary = _run(cfg, [gold_src], emit_gold_negatives=True)
    assert summary.seeded_code_written == 0
    assert summary.gold_source_skipped == 1


# --------------------------------------------------------------------------------------
# Split determinism + same-split-for-siblings.
# --------------------------------------------------------------------------------------
def test_assign_split_is_deterministic_and_sibling_stable():
    a = assign_split("guardkit", "T", "R-DC03", holdout_fraction=0.5, seed="s")
    b = assign_split("guardkit", "T", "R-DC03", holdout_fraction=0.5, seed="s")
    assert a == b  # deterministic; sibling variants share the (repo, task, family) key
    # a sweep lands roughly holdout_fraction in eval and never straddles a group
    tasks = [f"T{i}" for i in range(400)]
    ev = sum(1 for t in tasks if assign_split("r", t, "R-DC03", holdout_fraction=0.25, seed="s") == "eval_qav")
    assert 60 <= ev <= 140  # ~25% of 400


def test_sibling_variants_of_one_task_share_a_split(tmp_path):
    cfg = _cfg(tmp_path, holdout_fraction=0.5)
    # one source task anchoring TWO R-DC03 recipes (same family) -> two sibling seeded rows.
    src = SourceTask(
        repo="guardkit", feature="F", task="TASK-SIB", sha="s",
        files={
            "guardkit/orchestrator/quality_gates/coach_validator.py": _PRODUCER_SRC,
            "guardkit/orchestrator/bdd_oracle.py": (
                "def invoke(task_id, worktree_path):\n"
                "    run_bdd_for_task(task_id, worktree_path, python_executable=None)\n"
            ),
        },
    )
    summary = _run(cfg, [src], emit_gold_negatives=False)
    assert summary.seeded_code_written == 2  # producer + kwargs, both DC-03
    all_rows = []
    for name in ("train.jsonl", "eval_qav.jsonl"):
        p = tmp_path / "out" / name
        if p.exists():
            all_rows += [json.loads(line) for line in p.read_text().splitlines()]
    dc03 = [r for r in all_rows if r["metadata"].get("injection_recipe", "").startswith("R-DC03-")
            and r["metadata"]["injection_recipe"] != "R-CONTROL-noop"]
    assert len(dc03) == 2
    assert len({r["metadata"]["split"] for r in dc03}) == 1  # never straddles the split


# --------------------------------------------------------------------------------------
# seeded_bundle cap.
# --------------------------------------------------------------------------------------
def test_seeded_bundle_cap_enforced(tmp_path):
    cfg = _cfg(tmp_path, seeded_bundle_cap=0.25)
    tasks = [_producer_task(task=f"TASK-{i}") for i in range(3)]  # 3 reject + 3 control = 6 primary
    muts = [
        BundleMutation(
            repo="guardkit", feature="F", task=f"BUN-{i}", sha="s", run="r",
            bundle={**_GREEN, "behavioural_oracle": None, "profile_name": f"bun-{i}"},
            finding={"class": "DC-03", "locus": "producer severed"},
            recipe_id="R-DC03-producer",
        )
        for i in range(5)
    ]
    summary = _run(cfg, tasks, bundle_mutations=muts, emit_gold_negatives=False)
    primary = summary.seeded_code_written + summary.seeded_control_written
    assert primary == 6
    # floor(0.25 * 6 / 0.75) = 2 admitted; the remaining 3 capped.
    assert summary.seeded_bundle_written == 2
    assert summary.seeded_bundle_capped == 3


# --------------------------------------------------------------------------------------
# Reject paths — loud RESULTS, never a crash, never a silent degrade.
# --------------------------------------------------------------------------------------
def test_coach_reject_goes_to_rejected_jsonl(tmp_path):
    cfg = _cfg(tmp_path)
    summary = _run(cfg, [_producer_task()], coach=StubCoach(decision="revise"), emit_gold_negatives=False)
    assert summary.coach_rejected == 2  # the reject + the control both turned away
    assert summary.seeded_code_written == 0
    rej = [json.loads(line) for line in (tmp_path / "out" / "rejected.jsonl").read_text().splitlines()]
    assert rej and all(r["reason"] == "coach_rejected" for r in rej)


def test_teacher_refusal_is_a_loud_reject_not_a_crash(tmp_path):
    cfg = _cfg(tmp_path)
    summary = _run(cfg, [_producer_task()], teacher=StubTeacher(output="   "), emit_gold_negatives=False)
    assert summary.teacher_refused == 2
    assert summary.seeded_code_written == 0
    rej = [json.loads(line) for line in (tmp_path / "out" / "rejected.jsonl").read_text().splitlines()]
    assert all(r["reason"] == "teacher_refusal" for r in rej)


def test_teacher_garbage_prose_still_produces_a_valid_row(tmp_path):
    # non-empty prose without <think> tags is a rationale, not a refusal -> row is built + gated.
    cfg = _cfg(tmp_path)
    summary = _run(cfg, [_producer_task()],
                   teacher=StubTeacher(output="the evidence shows gathering_status complete"),
                   emit_gold_negatives=False)
    assert summary.seeded_code_written == 1 and summary.seeded_control_written == 1


def test_cue_leakage_row_is_rejected(tmp_path):
    cfg = _cfg(tmp_path)
    # a regenerator that leaks a sentinel into the bundle must be caught by the cue-audit.
    class LeakyRegen(StubRegenerator):
        def regenerate(self, worktree):
            b = super().regenerate(worktree)
            b["task_type"] = "SEEDED_DEFECT sentinel"
            return b
    summary = _run(cfg, [_producer_task()], regen=LeakyRegen(), emit_gold_negatives=False)
    assert summary.cue_rejected == 2
    assert summary.seeded_code_written == 0


def test_cue_audit_flags_recipe_id_and_sentinels():
    assert cue_audit({"honesty": {}, "profile_name": "R-DC03-producer"})  # recipe id leak
    assert cue_audit({"honesty": {}, "task_type": "__seeded__"})
    assert cue_audit({"honesty": {}, "gathering_error": "..."})  # truncated-shape sentinel
    assert cue_audit(_GREEN) == []


# --------------------------------------------------------------------------------------
# THE LOUDNESS LAW — the round-3 poison path (evidence-empty bundle) is closed.
#
# Round-3 (receipts/spike-one-row-2026-07-20.md §R3.3) proved an evidence-empty regeneration —
# gathering_status="partial_exception", gathering_error="missing_results: …", every
# tests/coverage/gates field null — sails through teacher + coach INTO train.jsonl as an approve
# row. That is the false-green class QAV exists to catch. The deterministic pre-gate must reject it
# BEFORE any teacher call (no wasted GPU) and it must never train.
# --------------------------------------------------------------------------------------
# The round-3 shape, replayed byte-for-byte from the receipt (only pinned bundle fields).
_ROUND3_POISON = {
    "gathering_status": "partial_exception",
    "gathering_error": (
        "missing_results: Task-work results not found at "
        "output/qa-verifier/_scratch/guardkit/TASK-QAWE-001/R-CONTROL-noop/"
        ".guardkit/autobuild/TASK-QAWE-001/task_work_results.json"
    ),
    "honesty": {"verified": True, "discrepancies": [], "score": 1.0},
    "profile_name": "python_backend",
    "task_type": "code",
    "quality_gates": None,
    "coverage_details": None,
    "tests": None,
    "wiring": None,
    "stub_scan": None,
}


class PoisonRegenerator:
    """Returns the round-3 evidence-empty ``partial_exception`` bundle for every worktree."""

    def __init__(self):
        self.calls = 0

    def regenerate(self, worktree: Path) -> dict:
        self.calls += 1
        return dict(_ROUND3_POISON)


def test_round3_evidence_empty_bundle_is_rejected_before_teacher(tmp_path):
    cfg = _cfg(tmp_path)
    teacher = StubTeacher()
    coach = StubCoach()
    summary = _run(
        cfg, [_producer_task()], teacher=teacher, coach=coach,
        regen=PoisonRegenerator(), emit_gold_negatives=False,
    )
    # every candidate row (the anchoring reject recipe + the control) is turned away as evidence-empty
    assert summary.evidence_empty_rejected >= 1
    assert summary.seeded_code_written == 0 and summary.seeded_control_written == 0
    # ZERO teacher calls (no wasted GPU) and ZERO coach calls — the pre-gate runs first.
    assert teacher.calls == 0
    assert coach.calls == 0
    # never train: train.jsonl absent/empty.
    train = tmp_path / "out" / "train.jsonl"
    assert not train.exists() or train.read_text().strip() == ""
    # routed to rejected.jsonl with the exact reason + the diagnostic status.
    rej = [json.loads(line) for line in (tmp_path / "out" / "rejected.jsonl").read_text().splitlines()]
    assert rej and all(r["reason"] == "evidence_empty_bundle" for r in rej)
    assert all(r["gathering_status"] == "partial_exception" for r in rej)
    assert any("missing_results" in r["detail"] for r in rej)


def test_evidence_empty_reason_taxonomy():
    # partial_exception + missing_results -> rejected (the round-3 poison).
    assert evidence_empty_reason(_ROUND3_POISON) is not None
    # any partial_exception (even without missing_results) -> rejected (evidence-empty crash class).
    assert evidence_empty_reason({"honesty": {}, "gathering_status": "partial_exception",
                                  "gathering_error": "honesty_exception: boom"}) is not None
    # healthy 'complete' -> allowed.
    assert evidence_empty_reason(_GREEN) is None
    # the evidence-BEARING early stops are NOT evidence-empty: they carry real reject-side signal.
    assert evidence_empty_reason({"honesty": {}, "gathering_status": "partial_gate_abort"}) is None
    assert evidence_empty_reason({"honesty": {}, "gathering_status": "partial_honesty_abort"}) is None
    # a bundle with a missing_results error but a tampered 'complete' status is STILL rejected.
    assert evidence_empty_reason(
        {"honesty": {}, "gathering_status": "complete",
         "gathering_error": "missing_results: gone"}
    ) is not None


# --------------------------------------------------------------------------------------
# Manifest-fail loud.
# --------------------------------------------------------------------------------------
def test_manifest_failure_fails_the_run_loud(tmp_path, monkeypatch):
    import qav.generate as gen
    from qav.manifest import build_manifest as real_build_manifest

    def _poison(*a, **k):
        m = real_build_manifest(*a, **k)
        m["contamination_check"] = {**m["contamination_check"], "status": "fail"}
        return m

    monkeypatch.setattr(gen, "build_manifest", _poison)
    with pytest.raises(RowValidationError):
        _run(_cfg(tmp_path), [_producer_task()], emit_gold_negatives=False)


# --------------------------------------------------------------------------------------
# Hermetic — zero network.
# --------------------------------------------------------------------------------------
def test_generation_makes_no_network_calls(tmp_path, monkeypatch):
    import socket

    def _boom(*a, **k):  # any socket construction is a test failure
        raise AssertionError("network access attempted during generation")

    monkeypatch.setattr(socket, "socket", _boom)
    summary = _run(_cfg(tmp_path), [_producer_task()], emit_gold_negatives=True)
    assert summary.seeded_code_written == 1


# --------------------------------------------------------------------------------------
# OutputWriter .bak fresh-start.
# --------------------------------------------------------------------------------------
def test_writer_backs_up_prior_files(tmp_path):
    d = tmp_path / "out"
    with OutputWriter(d) as w:
        w._fh["train"].write('{"first": 1}\n')
    # second open backs up the first train.jsonl to .bak and starts fresh
    with OutputWriter(d) as w:
        pass
    assert (d / "train.jsonl.bak").exists()
    assert '{"first": 1}' in (d / "train.jsonl.bak").read_text()
    assert (d / "train.jsonl").read_text() == ""


def test_harvest_inert_when_no_outcomes(tmp_path):
    cfg = _cfg(tmp_path, mode="harvest")
    summary = _run(cfg, source_tasks=[], emit_gold_negatives=False)
    assert summary.harvest_written == 0
    assert summary.train == 0 and summary.eval_qav == 0


def test_config_yaml_loads_record_store_roots(tmp_path):
    # The additive search-root config key: corpus.record_store_roots threads into the config so the
    # generation-run discovery can find recovered HEAD-missing records (S-B, 2026-07-21).
    yaml_path = tmp_path / "agent-config.yaml"
    yaml_path.write_text(
        "domain: qa-verifier\n"
        "corpus:\n"
        "  guardkit: /some/guardkit\n"
        "  record_store_roots:\n"
        "    - domains/qa-verifier/record-store\n",
        encoding="utf-8",
    )
    cfg = GenerateConfig.from_yaml(yaml_path)
    assert cfg.record_store_roots == ["domains/qa-verifier/record-store"]
    # ...and record_store_roots is NOT itself parsed as a (bogus) corpus root — only the real
    # repo->path entry survives (G1 filter fix; the feature-tracker walk reads each root's .guardkit,
    # so a stringified list leaking in as a root would be a real filesystem misread).
    assert set(cfg.corpus_roots) == {"guardkit"}


def test_config_yaml_record_store_roots_default_empty(tmp_path):
    # Absent key => pre-recovery behaviour (corpus globs only); never crashes.
    yaml_path = tmp_path / "agent-config.yaml"
    yaml_path.write_text(
        "domain: qa-verifier\ncorpus:\n  guardkit: /some/guardkit\n", encoding="utf-8"
    )
    assert GenerateConfig.from_yaml(yaml_path).record_store_roots == []


# --------------------------------------------------------------------------------------
# seeded_bundle ACTIVATION — the input wiring from REAL final-turn bundles (PLAN §2).
#
# The mode was built (cap enforced above) but produced ZERO rows because its input
# (bundle_mutations) was never discovered — it defaulted to []. build_bundle_mutations wires
# it: real serialized bundles mutated to a documented defect signature, label fixed by the
# mutation (never model-derived), each perturbing a BUNDLE-VISIBLE field so the row_id changes
# and the DC-03/DC-05 render-collapse (seeded-sweep §4 bottleneck #2) is escaped.
# --------------------------------------------------------------------------------------
_SIGNAL_BUNDLE = {
    "honesty": {"verified": True, "discrepancies": []},
    "gathering_status": "complete",
    "behavioural_oracle": {"passed": True, "assertions": 5},
    "bdd": {"scenarios": 3, "passed": 3},
    "profile_name": "guardkit-default",
}


def test_build_bundle_mutations_encodes_dc_classes_and_fixes_labels():
    base = dict(_SIGNAL_BUNDLE)
    muts = build_bundle_mutations(
        {("guardkit", "TASK-A"): base},
        {("guardkit", "TASK-A"): {"feature": "FEAT-A", "sha": "deadbeef", "run": "seeded_bundle"}},
    )
    # one candidate per catalog recipe whose field carries a real signal
    assert sorted(m.finding["class"] for m in muts) == ["DC-03", "DC-08", "DC-14"]
    for m in muts:
        assert (m.repo, m.task, m.feature, m.sha) == ("guardkit", "TASK-A", "FEAT-A", "deadbeef")
        assert m.recipe_id.startswith("R-BUNDLE-")
        # label fixed BY CONSTRUCTION — reject + the encoded finding, seeded source (never a model)
        assert m.label["verdict"] == "reject"
        assert m.label["ground_truth_source"] == "seeded"
        assert m.label["findings"] == [m.finding]
    # each mutation perturbs a distinct bundle-visible field -> distinct serialized bundles,
    # each differing from the base (the render-collapse the seeded_code path suffers is escaped)
    serialized = {json.dumps(m.bundle, sort_keys=True) for m in muts}
    assert len(serialized) == 3
    base_json = json.dumps(base, sort_keys=True)
    assert all(json.dumps(m.bundle, sort_keys=True) != base_json for m in muts)
    by_class = {m.finding["class"]: m for m in muts}
    assert by_class["DC-03"].bundle["behavioural_oracle"] is None
    assert by_class["DC-08"].bundle["bdd"] is None
    assert by_class["DC-14"].bundle["honesty"]["discrepancies"]
    assert by_class["DC-14"].bundle["honesty"]["verified"] is False
    # the source bundle is never mutated in place (deepcopy)
    assert base["behavioural_oracle"] == {"passed": True, "assertions": 5}


def test_build_bundle_mutations_skips_already_vacuous_fields():
    # all three target fields already absent/dirty -> no signal to sever, no candidate
    base = {
        "honesty": {"discrepancies": [{"claim_type": "x", "player_claim": "y", "actual_value": "z"}]},
        "gathering_status": "complete",
        "behavioural_oracle": None,
        "bdd": None,
        "profile_name": "p",
    }
    muts = build_bundle_mutations(
        {("guardkit", "T"): base},
        {("guardkit", "T"): {"feature": "F", "sha": "s", "run": "r"}},
    )
    assert muts == []


def test_build_bundle_mutations_excludes_unresolvable_provenance():
    # a bundle whose (repo, task) has no record-resolved provenance is EXCLUDED — never a guessed sha
    base = dict(_SIGNAL_BUNDLE)
    assert build_bundle_mutations({("guardkit", "T"): base}, {}) == []


def test_build_bundle_mutations_skips_evidence_empty_base():
    # a poison (evidence-empty) base is not a documented signature; the pre-gate would reject it anyway
    base = {
        "honesty": {"discrepancies": []},
        "gathering_status": "partial_exception",
        "gathering_error": "missing_results: task-work record not materialized",
        "behavioural_oracle": {"passed": True},
    }
    muts = build_bundle_mutations(
        {("guardkit", "T"): base},
        {("guardkit", "T"): {"feature": "F", "sha": "s", "run": "r"}},
    )
    assert muts == []


def test_seeded_bundle_rows_are_label_fixed_distinct_and_valid(tmp_path):
    cfg = _cfg(tmp_path, seeded_bundle_cap=0.9)  # generous cap so all three admit
    tasks = [_producer_task(task=f"TASK-{i}") for i in range(3)]  # 6 primary seeded rows
    muts = build_bundle_mutations(
        {("guardkit", "TASK-B"): dict(_SIGNAL_BUNDLE)},
        {("guardkit", "TASK-B"): {"feature": "FEAT-B", "sha": "sha1", "run": "seeded_bundle"}},
    )
    assert len(muts) == 3
    summary = _run(cfg, tasks, bundle_mutations=muts, emit_gold_negatives=False)
    assert summary.seeded_bundle_written == 3  # none render-collapse (distinct bundle-visible fields)

    all_rows = []
    for name in ("train.jsonl", "eval_qav.jsonl"):
        p = tmp_path / "out" / name
        if p.exists():
            all_rows += [json.loads(line) for line in p.read_text().splitlines()]
    sb = [r for r in all_rows if r["metadata"]["generation_mode"] == "seeded_bundle"]
    assert len(sb) == 3
    assert len({r["metadata"]["row_id"] for r in sb}) == 3  # distinct row_ids
    for r in sb:
        lbl = extract_label(r)
        assert lbl["verdict"] == "reject"
        assert lbl["ground_truth_source"] == "seeded"
        assert lbl["findings"][0]["class"] == r["metadata"]["dc_class"]
        validate_row(r)
    assert sorted(r["metadata"]["dc_class"] for r in sb) == ["DC-03", "DC-08", "DC-14"]


def test_seeded_bundle_leaky_mutation_is_cue_rejected(tmp_path):
    cfg = _cfg(tmp_path, seeded_bundle_cap=0.9)
    tasks = [_producer_task(task=f"TASK-{i}") for i in range(2)]  # 4 primary
    leaky = BundleMutation(
        repo="guardkit", feature="F", task="BUN-LEAK", sha="s", run="r",
        bundle={**_GREEN, "task_type": "__seeded__ sentinel", "profile_name": "bun-leak"},
        finding={"class": "DC-03", "locus": "x"}, recipe_id="R-BUNDLE-DC03-oracle",
    )
    summary = _run(cfg, tasks, bundle_mutations=[leaky], emit_gold_negatives=False)
    assert summary.cue_rejected == 1
    assert summary.seeded_bundle_written == 0
    rej = [json.loads(line) for line in (tmp_path / "out" / "rejected.jsonl").read_text().splitlines()]
    assert any(r["reason"] == "cue_leakage" for r in rej)


def test_seeded_bundle_byte_identical_mutations_dedup(tmp_path):
    cfg = _cfg(tmp_path, seeded_bundle_cap=0.9)
    tasks = [_producer_task(task=f"TASK-{i}") for i in range(3)]  # 6 primary
    dc03 = next(
        m for m in build_bundle_mutations(
            {("guardkit", "TASK-C"): dict(_SIGNAL_BUNDLE)},
            {("guardkit", "TASK-C"): {"feature": "F", "sha": "s", "run": "r"}},
        ) if m.finding["class"] == "DC-03"
    )
    dup = BundleMutation(
        repo=dc03.repo, feature=dc03.feature, task=dc03.task, sha=dc03.sha, run=dc03.run,
        bundle=dict(dc03.bundle), finding=dict(dc03.finding), recipe_id=dc03.recipe_id,
    )
    summary = _run(cfg, tasks, bundle_mutations=[dc03, dup], emit_gold_negatives=False)
    # identical serialized bundle -> identical content-addressed row_id -> the 2nd is deduped
    assert summary.seeded_bundle_written == 1
    assert summary.deduped >= 1


# --------------------------------------------------------------------------------------
# THE EVIDENCE-DIVERGENCE GUARD — the render-collapse poison path is structurally closed.
#
# Proven (receipts/render-collapse-rootcause-2026-07-21.md): the current regeneration replay
# is SOURCE-BLIND — a mutated worktree's bundle renders byte-identical to its task's no-op
# control bundle (gather_evidence partial_gate_abort replays the static record). Write-order
# then let a reject recipe claim the shared row_id first and bank a GREEN bundle wearing a
# reject label. The guard regenerates the CONTROL first per task, content-hashes it, and
# REFUSES any reject candidate whose regenerated bundle hashes equal to that baseline
# (reason "evidence_invariant_injection") — before any teacher call. Controls are unaffected.
# --------------------------------------------------------------------------------------
_STATIC_REPLAY = {
    "honesty": {"discrepancies": []},
    "gathering_status": "partial_gate_abort",  # the proven collapse shape — evidence-BEARING
    "tests": {"passed": True},
    "profile_name": "static-replay",
}


class SourceBlindRegenerator:
    """Replays ONE static bundle for every worktree — the render-collapse regeneration shape
    (mutated and control worktrees render byte-identical; worktree contents irrelevant)."""

    def __init__(self, base: dict | None = None):
        self.base = dict(base or _STATIC_REPLAY)
        self.calls = 0

    def regenerate(self, worktree: Path) -> dict:
        self.calls += 1
        return dict(self.base)


class DivergentRegenerator:
    """Control worktree -> green bundle; mutated worktree -> a genuinely DIFFERENT bundle
    (the planted defect surfaced in the evidence) — the healthy-regeneration shape."""

    def __init__(self):
        self.calls = 0

    def regenerate(self, worktree: Path) -> dict:
        self.calls += 1
        if "R-CONTROL-noop" in str(worktree):
            return {**_GREEN, "profile_name": "control-green"}
        return {
            **_GREEN,
            "gathering_status": "partial_gate_abort",
            "tests": {"passed": False},
            "profile_name": "mutated-red",
        }


def test_source_blind_reject_refused_control_still_banks(tmp_path):
    cfg = _cfg(tmp_path)
    teacher = StubTeacher()
    summary = _run(
        cfg, [_producer_task()], teacher=teacher,
        regen=SourceBlindRegenerator(), emit_gold_negatives=False,
    )
    # the reject candidate (R-DC03-producer anchors this fixture) is REFUSED: its bundle is
    # byte-identical to the task's no-op control bundle — the defect never surfaced.
    assert summary.evidence_invariant_rejected == 1
    assert summary.seeded_code_written == 0
    # the CONTROL still banks — its approve label describes the real record.
    assert summary.seeded_control_written == 1
    rows = [json.loads(l) for l in (tmp_path / "out" / "train.jsonl").read_text().splitlines()]
    assert len(rows) == 1
    assert extract_label(rows[0])["verdict"] == "approve"
    assert rows[0]["metadata"]["injection_recipe"] == "R-CONTROL-noop"
    validate_row(rows[0])
    # NO green bundle wearing a reject label anywhere — the poison class is impossible.
    # The refusal is loud in rejected.jsonl with the exact reason + the shared content hash.
    rej = [json.loads(l) for l in (tmp_path / "out" / "rejected.jsonl").read_text().splitlines()]
    assert len(rej) == 1
    assert rej[0]["reason"] == "evidence_invariant_injection"
    assert rej[0]["injection_recipe"] == "R-DC03-producer"
    assert rej[0]["bundle_content_sha256"]
    # refused BEFORE the teacher: the only teacher call is the control's own rationale.
    assert teacher.calls == 1
    # the refusal is NOT a dedup event — it never reached the writer.
    assert summary.deduped == 0


def test_divergent_reject_banks_normally(tmp_path):
    cfg = _cfg(tmp_path)
    summary = _run(
        cfg, [_producer_task()], regen=DivergentRegenerator(), emit_gold_negatives=False,
    )
    # genuinely different evidence -> the guard stays silent and the reject banks.
    assert summary.evidence_invariant_rejected == 0
    assert summary.seeded_code_written == 1
    assert summary.seeded_control_written == 1
    rows = [json.loads(l) for l in (tmp_path / "out" / "train.jsonl").read_text().splitlines()]
    verdicts = sorted(extract_label(r)["verdict"] for r in rows)
    assert verdicts == ["approve", "reject"]
    reject = next(r for r in rows if extract_label(r)["verdict"] == "reject")
    # the banked reject carries its OWN divergent evidence, not the control's.
    assert "mutated-red" in json.dumps(reject)
    for r in rows:
        validate_row(r)
    assert (tmp_path / "out" / "rejected.jsonl").read_text().strip() == ""


def test_source_blind_refusal_covers_every_reject_leg_of_a_task(tmp_path):
    # two anchoring reject recipes on one task (the sibling fixture) — BOTH refused, one control.
    cfg = _cfg(tmp_path)
    src = SourceTask(
        repo="guardkit", feature="F", task="TASK-SIB", sha="s",
        files={
            "guardkit/orchestrator/quality_gates/coach_validator.py": _PRODUCER_SRC,
            "guardkit/orchestrator/bdd_oracle.py": (
                "def invoke(task_id, worktree_path):\n"
                "    run_bdd_for_task(task_id, worktree_path, python_executable=None)\n"
            ),
        },
    )
    summary = _run(cfg, [src], regen=SourceBlindRegenerator(), emit_gold_negatives=False)
    assert summary.evidence_invariant_rejected == 2
    assert summary.seeded_code_written == 0
    assert summary.seeded_control_written == 1


def test_evidence_empty_still_wins_over_divergence_guard(tmp_path):
    # a source-blind POISON regenerator (identical AND evidence-empty bundles): the evidence-empty
    # pre-gate fires first — the more fundamental refusal — and the guard counter stays zero.
    cfg = _cfg(tmp_path)
    summary = _run(
        cfg, [_producer_task()], regen=PoisonRegenerator(), emit_gold_negatives=False,
    )
    assert summary.evidence_invariant_rejected == 0
    assert summary.evidence_empty_rejected == 2  # the reject leg AND the control leg
    rej = [json.loads(l) for l in (tmp_path / "out" / "rejected.jsonl").read_text().splitlines()]
    assert all(r["reason"] == "evidence_empty_bundle" for r in rej)
