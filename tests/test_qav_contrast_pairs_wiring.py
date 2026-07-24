"""Hermetic wiring tests for the contrast-pair family through ``qav.generate`` end-to-end.

Drives ``run_generation`` against STUB teacher/coach + a control-bundle regenerator (no guardkit,
no network, no GPU). Proves: pair rows bank as ``generation_mode="seeded_bundle"`` with an
``R-BUNDLE-PAIR-*`` ``injection_recipe`` + the fixed label; PAIR-ATOMIC banking (a teacher/coach
dropping one side banks NO lone sibling); the in-engine three-distinct-hashes refusal; the OWN
``contrast_pair_budget`` with eval-cohort-first ordering; approve-control labels; the eval-side
coverage seam (the four eval-hash tasks' pairs land in eval_qav); split no-straddle; and the
cue-audit widening to the ``R-RECORD-*`` / ``R-BUNDLE-PAIR-*`` namespaces.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from qav.bundle_pairs import PAIR_RECIPES
from qav.contracts import extract_label, validate_row
from qav.generate import (
    CoachVerdict,
    GenerateConfig,
    SourceTask,
    cue_audit,
    run_generation,
)


# --------------------------------------------------------------------------------------
# Stubs.
# --------------------------------------------------------------------------------------
class StubTeacher:
    def complete(self, system: str, user: str) -> str:
        return (
            "<think>\nReading gathering_status and the plan_audit / wiring / tests fields named in "
            "the bundle: the evidence does not support the claim. Per-task green is not feature "
            "green.\n</think>"
        )


class StubCoach:
    def __init__(self, decision: str = "accept"):
        self.decision = decision

    def assess(self, bundle, think, label) -> CoachVerdict:
        return CoachVerdict(decision=self.decision, reasons=["stub"])


class SelectiveCoach:
    """Revises ONLY when a finding carries the target class (to drop exactly one pair side)."""

    def __init__(self, revise_class: str):
        self.revise_class = revise_class

    def assess(self, bundle, think, label) -> CoachVerdict:
        for f in label.get("findings", []):
            if isinstance(f, dict) and f.get("class") == self.revise_class:
                return CoachVerdict(decision="revise", reasons=["selective stub"])
        return CoachVerdict(decision="accept", reasons=["stub"])


def _rich_control(tag: str) -> dict:
    """A healthy green regenerated control bundle (25-field schema), unique per task via ``tag``."""
    return {
        "honesty": {"verified": True, "discrepancies": []},
        "gathering_status": "complete",
        "gathering_error": None,
        "quality_gates": {"all_passed": True, "tests_passed": 18, "tests_passing": 18, "tests_failed": 0},
        "plan_audit": {
            "status": "skipped", "severity": None, "violations": 0,
            "missing_files": [], "extra_modifications": [], "loc_variance_pct": None,
            "discrepancies_count": 0, "message": "no implementation plan on disk",
        },
        "bdd": {"scenarios_passed": 5, "scenarios_failed": 0},
        "bdd_authoring_sweep": {"authored": True, "step_definitions": 11},
        "tests": {"tests_run": 18, "passed": True, "all_passed": True, "collected": 18},
        "wiring": {"analyzed": True, "call_sites": 4, "unwired": 0},
        "runtime_parity": {"checked": True, "mismatches": 0},
        "behavioural_oracle": {"present": True},
        "independent_tests": {"signal_absent": False, "passed": True},
        "profile_name": "pair-" + tag,
    }


class PairControlRegenerator:
    """Returns a rich green CONTROL bundle, made UNIQUE per worktree (so each task's minted pairs
    hash distinctly and never collide across tasks)."""

    def regenerate(self, worktree: Path) -> dict:
        return _rich_control(hashlib.sha1(str(worktree).encode()).hexdigest()[:10])


class MinimalGreenRegenerator:
    """A green control carrying NONE of the pair anchors (no plan_audit/tests/wiring/bdd) — every
    pair recipe anchor-skips, so the engine drops each pair/single loudly."""

    def regenerate(self, worktree: Path) -> dict:
        return {
            "honesty": {"verified": True, "discrepancies": []},
            "gathering_status": "complete",
            "profile_name": "min-" + hashlib.sha1(str(worktree).encode()).hexdigest()[:8],
        }


def _src(repo: str, task: str) -> SourceTask:
    return SourceTask(
        repo=repo, feature="FEAT-PAIR", task=task, sha="deadbeef",
        files={"src/svc/app.py": "def app():\n    return 1\n"},  # record_dir=None (canned regen)
    )


def _cfg(tmp_path, **over) -> GenerateConfig:
    base = dict(
        mode="seeded_defect", holdout_fraction=0.15, recipes={},  # no code recipes -> isolate pairs
        output_dir=str(tmp_path / "out"),
        manifest_path=str(tmp_path / "manifests" / "train.manifest.json"),
        scratch_dir=str(tmp_path / "scratch"), seed="qav-phase1",  # the DESIGN split seed
    )
    base.update(over)
    return GenerateConfig(**base)


def _run(cfg, sources, *, teacher=None, coach=None, regen=None, **kw):
    return run_generation(
        cfg, teacher=teacher or StubTeacher(), coach=coach or StubCoach(),
        regenerator=regen or PairControlRegenerator(),
        source_tasks=sources, created="2026-07-23", factory_sha="test",
        emit_gold_negatives=False, **kw,
    )


def _rows(tmp_path, split="train") -> list[dict]:
    p = tmp_path / "out" / f"{split}.jsonl"
    return [json.loads(x) for x in p.read_text().splitlines()] if p.exists() else []


def _all_rows(tmp_path) -> list[dict]:
    return _rows(tmp_path, "train") + _rows(tmp_path, "eval_qav")


def _pair_rows(rows) -> list[dict]:
    return [r for r in rows if str(r["metadata"].get("injection_recipe", "")).startswith("R-BUNDLE-PAIR-")]


def _rejected(tmp_path) -> list[dict]:
    p = tmp_path / "out" / "rejected.jsonl"
    return [json.loads(x) for x in p.read_text().splitlines()] if p.exists() else []


# --------------------------------------------------------------------------------------
# The seam: pair rows bank as seeded_bundle with the pair recipe id + fixed labels.
# --------------------------------------------------------------------------------------
def test_pair_rows_bank_as_seeded_bundle_with_pair_recipe(tmp_path):
    summary = _run(_cfg(tmp_path), [_src("study_tutor", "TASK-PRV-006")])  # AB cohort, train
    pair = _pair_rows(_all_rows(tmp_path))
    assert pair, "no contrast-pair rows banked"
    for r in pair:
        validate_row(r)
        assert r["metadata"]["generation_mode"] == "seeded_bundle"     # frozen-allowlisted mode
        assert r["metadata"]["injection_recipe"] in PAIR_RECIPES
        label = extract_label(r)
        if label["verdict"] == "reject":
            assert label["findings"][0]["class"] == r["metadata"]["dc_class"]
            assert label["ground_truth_source"] == "seeded"
        else:
            assert r["metadata"]["dc_class"] is None
    # v4 (leg B3): a non-owning AB task mints A pair + B pair (4 reject sides) + 8 singles — the 3
    # DC-12/DC-14 controls, the new CTRL-stub, the two axis-D DC-05 rejects (D-dc05 / D-dc05stub),
    # and the two axis-D approve mates (CTRL-vac / CTRL-skips) = 12 pair rows.
    assert len(pair) == 12
    assert summary.pairs_banked == 2  # axis A + axis B
    assert summary.contrast_pair_reject_written == 6  # 4 A/B sides + D-dc05 + D-dc05stub
    assert summary.contrast_pair_control_written == 6  # CTRL-audit/comp/tests/stub/vac/skips
    # the post-run sibling-parity census (DESIGN §3 law 6): 4 A/B sides banked, zero orphans.
    assert summary.pair_census_sides_banked == 4
    assert summary.pair_census_orphans == 0


def test_approve_controls_bank_with_approve_labels(tmp_path):
    _run(_cfg(tmp_path), [_src("study_tutor", "TASK-PRV-006")])
    ctrls = [r for r in _all_rows(tmp_path)
             if str(r["metadata"]["injection_recipe"]).startswith("R-BUNDLE-PAIR-CTRL-")]
    # v4: CTRL-audit/comp/tests (v3) + CTRL-stub/vac/skips (v4) = 6 approve controls on an AB task.
    assert len(ctrls) == 6
    for r in ctrls:
        assert extract_label(r)["verdict"] == "approve"
        assert r["metadata"]["dc_class"] is None
        assert extract_label(r)["findings"] == []


def test_bdd_owning_task_also_gets_the_axis_c_dc08_side(tmp_path):
    _run(_cfg(tmp_path, holdout_fraction=0.5), [_src("guardkit", "TASK-BDDW-002")])
    pair = _pair_rows(_all_rows(tmp_path))
    ids = {r["metadata"]["injection_recipe"] for r in pair}
    assert "R-BUNDLE-PAIR-C-dc08" in ids  # BDD-owning ⇒ the axis-C DC-08 side rides it
    dc08 = next(r for r in pair if r["metadata"]["injection_recipe"] == "R-BUNDLE-PAIR-C-dc08")
    assert extract_label(dc08)["findings"][0]["class"] == "DC-08"
    # v1.2: the DC-08 defect sweep rides with its healthy-sweep CTRL-bdd approve mate.
    assert "R-BUNDLE-PAIR-CTRL-bdd" in ids
    ctrl_bdd = next(r for r in pair if r["metadata"]["injection_recipe"] == "R-BUNDLE-PAIR-CTRL-bdd")
    assert extract_label(ctrl_bdd)["verdict"] == "approve"


def test_pair_census_detects_an_orphaned_ab_side(tmp_path, monkeypatch):
    # The census is belt-and-braces: if a lone A/B side ever reached a banked file (pair-atomic
    # banking should make this impossible), the post-run census RECORDS it as an orphan, loudly,
    # without crashing the run. Force it by making the DC-03 side a no-op deduped write so only its
    # DC-12 sibling lands — the census must count exactly one orphan.
    import qav.generate as gen

    real_write_row = gen.OutputWriter.write_row

    def dropping_write_row(self, row):
        if row["metadata"].get("injection_recipe") == "R-BUNDLE-PAIR-A-dc03":
            return False  # simulate a dedup/no-write for one axis-A side only
        return real_write_row(self, row)

    monkeypatch.setattr(gen.OutputWriter, "write_row", dropping_write_row)
    summary = _run(_cfg(tmp_path), [_src("study_tutor", "TASK-PRV-006")])
    banked = {r["metadata"]["injection_recipe"] for r in _pair_rows(_all_rows(tmp_path))}
    # the DC-12 side of axis A banked but its DC-03 sibling did not -> a lone orphan.
    assert "R-BUNDLE-PAIR-A-dc12" in banked and "R-BUNDLE-PAIR-A-dc03" not in banked
    assert summary.pair_census_orphans == 1  # the loud receipt fired, no crash


# --------------------------------------------------------------------------------------
# Pair-atomicity: one side failing the gate drops BOTH sides — no lone sibling banks.
# --------------------------------------------------------------------------------------
def test_pair_atomicity_drops_both_sides_when_one_fails(tmp_path):
    summary = _run(
        _cfg(tmp_path), [_src("study_tutor", "TASK-PRV-006")],
        coach=SelectiveCoach("DC-14"),  # revises only the axis-B DC-14 side
    )
    banked = {r["metadata"]["injection_recipe"] for r in _pair_rows(_all_rows(tmp_path))}
    # axis B: the DC-14 side is revised AND its clean-gating DC-12 sibling is dropped with it.
    assert "R-BUNDLE-PAIR-B-dc14" not in banked
    assert "R-BUNDLE-PAIR-B-dc12" not in banked
    # axis A is unaffected — both sides bank.
    assert "R-BUNDLE-PAIR-A-dc12" in banked and "R-BUNDLE-PAIR-A-dc03" in banked
    assert summary.pairs_banked == 1               # only axis A
    assert summary.pair_sibling_dropped >= 2        # both axis-B sides dropped
    assert any(x.get("reason") == "pair_sibling_dropped" for x in _rejected(tmp_path))
    # the census confirms sibling-parity: axis A banked BOTH sides, axis B banked NEITHER — no orphan.
    assert summary.pair_census_sides_banked == 2   # only axis A's two sides
    assert summary.pair_census_orphans == 0


def test_anchor_absent_drops_pairs_and_singles_loudly(tmp_path):
    summary = _run(
        _cfg(tmp_path), [_src("study_tutor", "TASK-PRV-006")],
        regen=MinimalGreenRegenerator(),  # carries none of the plan_audit / tests anchors
    )
    banked = {r["metadata"]["injection_recipe"] for r in _pair_rows(_all_rows(tmp_path))}
    # the anchor-dependent recipes drop loudly: axis A (A-dc12 needs plan_audit), axis B (needs
    # executed tests), CTRL-audit (plan_audit), CTRL-tests (tests) — none bank.
    assert "R-BUNDLE-PAIR-A-dc12" not in banked and "R-BUNDLE-PAIR-A-dc03" not in banked
    assert "R-BUNDLE-PAIR-B-dc14" not in banked and "R-BUNDLE-PAIR-B-dc12" not in banked
    assert "R-BUNDLE-PAIR-CTRL-audit" not in banked and "R-BUNDLE-PAIR-CTRL-tests" not in banked
    assert summary.pairs_banked == 0
    assert summary.pair_sibling_dropped >= 4  # A pair (2) + B pair (2) at least
    assert any(x.get("reason") == "pair_anchor_absent" for x in _rejected(tmp_path))
    # populate-with-defect / populate-healthy recipes FIRE EVERYWHERE even on a minimal control:
    # CTRL-comp (wiring healthy) + CTRL-stub (clean stub_scan) approve, and D-dc05stub (planted
    # sys.modules stub) rejects — the only three that survive an anchor-bare control. The skip-
    # divergence recipes (D-dc05 / CTRL-vac / CTRL-skips) correctly anchor-skip: no independent
    # surface to perturb.
    assert banked == {"R-BUNDLE-PAIR-CTRL-comp", "R-BUNDLE-PAIR-CTRL-stub", "R-BUNDLE-PAIR-D-dc05stub"}
    assert summary.contrast_pair_control_written == 2   # CTRL-comp + CTRL-stub
    assert summary.contrast_pair_reject_written == 1    # D-dc05stub
    assert summary.pair_census_orphans == 0  # no A/B side banked ⇒ no orphan


# --------------------------------------------------------------------------------------
# The in-engine three-distinct-hashes law — a colliding pair is refused, banking nothing.
# --------------------------------------------------------------------------------------
def test_pair_hash_collision_refuses_the_pair(tmp_path, monkeypatch):
    import qav.generate as gen
    from qav.bundle_pairs import PairInjectionResult
    from qav.bundle_pairs import apply_pair_recipe as real_apply

    collide = {"honesty": {"verified": True, "discrepancies": []},
               "gathering_status": "complete", "profile_name": "collide"}

    def fake_apply(bundle, rid):
        res = real_apply(bundle, rid)
        if res is not None and rid in ("R-BUNDLE-PAIR-A-dc12", "R-BUNDLE-PAIR-A-dc03"):
            # force BOTH axis-A sides to the identical bundle -> a hash collision.
            return PairInjectionResult(
                recipe_id=rid, dc_class=res.dc_class, verdict=res.verdict,
                pair_group=res.pair_group, mutated_bundle=dict(collide), finding=res.finding,
            )
        return res

    monkeypatch.setattr(gen, "apply_pair_recipe", fake_apply)
    summary = _run(_cfg(tmp_path), [_src("study_tutor", "TASK-PRV-006")])
    assert summary.pair_hash_collisions >= 1
    banked = {r["metadata"]["injection_recipe"] for r in _pair_rows(_all_rows(tmp_path))}
    assert "R-BUNDLE-PAIR-A-dc12" not in banked and "R-BUNDLE-PAIR-A-dc03" not in banked
    rej = _rejected(tmp_path)
    coll = [x for x in rej if x.get("reason") == "pair_hash_collision"]
    assert coll and all(x["bundle_content_sha256"] for x in coll)


# --------------------------------------------------------------------------------------
# Budget + eval-first ordering — a tight budget banks eval's rows, caps the train task.
# --------------------------------------------------------------------------------------
def test_budget_caps_train_after_eval_is_processed_first(tmp_path):
    # v4: a non-owning AB task now mints 12 pair rows (A2 + B2 + 8 singles). budget = 12 fits exactly
    # ONE such task. The eval-cohort task is listed SECOND but processed FIRST, so it banks all 12 and
    # the train task is fully capped — proving budget truncation lands on train, never on eval.
    cfg = _cfg(tmp_path, contrast_pair_budget=12)
    train = _src("study_tutor", "TASK-PRV-006")   # hashes train
    ev = _src("study_tutor", "TASK-PRV-004")       # eval-cohort (hashes eval)
    summary = _run(cfg, [train, ev])  # train listed first
    eval_pair = _pair_rows(_rows(tmp_path, "eval_qav"))
    train_pair = _pair_rows(_rows(tmp_path, "train"))
    assert len(eval_pair) == 12          # the eval task fully banked its pair rows
    assert train_pair == []              # budget exhausted -> the train task's rows all capped
    assert summary.contrast_pair_capped == 12
    assert summary.pairs_banked == 2     # eval axis A + axis B
    # every banked eval pair row is genuinely on the eval split
    assert all(r["metadata"]["split"] == "eval_qav" for r in eval_pair)


# --------------------------------------------------------------------------------------
# Eval-side coverage (DESIGN §4) — the free seam: eval gains DC-12/DC-14/DC-03 + approves.
# --------------------------------------------------------------------------------------
def test_eval_cohort_task_lands_pair_rows_in_eval(tmp_path):
    summary = _run(_cfg(tmp_path), [_src("jarvis", "TASK-JNB-001")])  # an eval-hash cohort task
    eval_pair = _pair_rows(_rows(tmp_path, "eval_qav"))
    assert eval_pair, "no pair rows in eval for an eval-cohort task"
    for r in eval_pair:
        validate_row(r)
        assert r["metadata"]["split"] == "eval_qav"
        assert r["metadata"]["generation_mode"] == "seeded_bundle"
    classes = {r["metadata"]["dc_class"] for r in eval_pair}
    assert {"DC-12", "DC-14", "DC-03"} <= classes          # eval gains all three reject classes
    assert any(extract_label(r)["verdict"] == "approve" for r in eval_pair)  # + matched approves
    # NO pair row for this eval task straddles onto the train split.
    assert not _pair_rows(_rows(tmp_path, "train"))
    assert summary.pairs_banked >= 2


# --------------------------------------------------------------------------------------
# Split no-straddle — one task's pair rows all share the task's seeded_bundle split.
# --------------------------------------------------------------------------------------
def test_pair_rows_of_one_task_share_the_split(tmp_path):
    _run(_cfg(tmp_path, holdout_fraction=0.5), [_src("guardkit", "TASK-QAWE-003")])
    pair = _pair_rows(_all_rows(tmp_path))
    assert pair
    assert len({r["metadata"]["split"] for r in pair}) == 1  # never straddles


# --------------------------------------------------------------------------------------
# Cue-audit widening — R-RECORD-* / R-BUNDLE-PAIR-* ids leaking into bundle prose are caught.
# --------------------------------------------------------------------------------------
def test_cue_audit_flags_record_and_pair_recipe_ids():
    assert cue_audit({"honesty": {}, "profile_name": "R-RECORD-DC12-missingfiles"})
    assert cue_audit({"honesty": {}, "task_type": "R-BUNDLE-PAIR-A-dc12"})
    assert cue_audit({"honesty": {}, "gathering_status": "complete"}) == []
