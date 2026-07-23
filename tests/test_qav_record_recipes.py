"""Hermetic unit tests for the ``seeded_record`` mutation family (``qav.record_recipes``).

Pure — every recipe is a ``dict -> (mutated_record, locus) | None`` transform over a tiny local
``task_work_results`` fixture. No worktree, no regenerator, no model. Verifies: per-recipe fidelity
(the mutation lands on the intended bundle-visible surface + fixes the label by construction),
control no-ops bank as APPROVE on the same surface (the anti-shortcut law), anchor-absent loudness
(None, never a silent no-op), determinism/reproducibility, cue-cleanliness, and the shortcut-defeat
proportion (every reject class is matched by an approve control on the same surface).
"""

from __future__ import annotations

import copy
import json

import pytest

from qav.contracts import PHASE1_DC_CLASSES, validate_label
from qav.record_recipes import (
    RECORD_RECIPES,
    RecordRecipeError,
    _all_record_paths,
    _derive_nonexistent_paths,
    apply_record_recipe,
)


# --------------------------------------------------------------------------------------
# A faithful tiny record fixture (the real task_work_results shape — verified against
# record-store/study_tutor/TASK-PRV-003 + guardkit/TASK-QAWE-003).
# --------------------------------------------------------------------------------------
def _record(**over):
    rec = {
        "task_id": "TASK-REC-001",
        "task_type": "feature",
        "plan_audit": {
            "status": "skipped", "severity": None, "violations": 0,
            "extra_files": [], "missing_files": [], "extra_modifications": [],
            "missing_modifications": [], "extra_dependencies": [], "missing_dependencies": [],
            "loc_variance_pct": None, "discrepancies_count": 0,
            "message": "no implementation plan on disk",
        },
        "quality_gates": {
            "all_passed": True, "coverage": 87.0, "coverage_met": True,
            "tests_failed": 0, "tests_passed": 14, "tests_passing": 14,
        },
        "completion_promises": [
            {
                "criterion_id": "AC-001", "criterion_text": "does the thing",
                "status": "complete", "evidence": "unit + integration",
                "implementation_files": ["src/svc/retrieval.py"],
                "test_file": "tests/test_retrieval.py",
            },
            {
                "criterion_id": "AC-002", "criterion_text": "does another thing",
                "status": "complete", "evidence": "unit",
                "implementation_files": ["src/svc/models.py"],
                "test_file": "tests/test_models.py",
            },
        ],
        "files_created": ["src/svc/retrieval.py", "src/svc/models.py"],
        "files_modified": ["src/svc/app.py"],
        "tests_written": ["tests/test_retrieval.py"],
        "summary": "implemented retrieval",
    }
    rec.update(over)
    return rec


REJECT_IDS = [rid for rid, r in RECORD_RECIPES.items() if r.verdict == "reject"]
APPROVE_IDS = [rid for rid, r in RECORD_RECIPES.items() if r.verdict == "approve"]
_CUE_TOKENS = ("__seeded__", "seeded_defect", "__injected__", "injected_by_recipe", "sentinel", "xxxcue")


# --------------------------------------------------------------------------------------
# Registry integrity.
# --------------------------------------------------------------------------------------
def test_registry_namespace_and_class_discipline():
    assert REJECT_IDS and APPROVE_IDS
    for rid, r in RECORD_RECIPES.items():
        assert rid.startswith("R-RECORD-"), rid
        assert r.verdict in ("reject", "approve")
        if r.verdict == "reject":
            assert r.dc_class in PHASE1_DC_CLASSES
        else:
            assert r.dc_class is None


def test_record_namespace_disjoint_from_code_and_bundle_recipes():
    from qav.recipes import RECIPES  # the frozen code recipes

    assert set(RECORD_RECIPES).isdisjoint(set(RECIPES))
    assert all(not rid.startswith("R-BUNDLE-") for rid in RECORD_RECIPES)


def test_unknown_recipe_raises_loud():
    with pytest.raises(KeyError):
        apply_record_recipe(_record(), "R-RECORD-does-not-exist")


# --------------------------------------------------------------------------------------
# Every recipe fires on the clean fixture, fixes a valid label, and does not mutate the input.
# --------------------------------------------------------------------------------------
@pytest.mark.parametrize("rid", sorted(RECORD_RECIPES))
def test_recipe_fires_and_fixes_a_valid_label(rid):
    # DC-05 is registered but its plan fires on the fixture's green quality_gates.
    original = _record()
    frozen = copy.deepcopy(original)
    res = apply_record_recipe(original, rid)
    assert res is not None, f"{rid} did not fire on the clean fixture"
    assert original == frozen, f"{rid} mutated its input record in place"
    validate_label(res.label)  # the contracts.py label contract holds by construction
    if res.verdict == "reject":
        assert res.label["verdict"] == "reject"
        assert res.finding and res.finding["class"] == res.dc_class
        assert res.finding["locus"].strip()
        assert len(res.label["findings"]) == 1
    else:
        assert res.label["verdict"] == "approve"
        assert res.label["findings"] == []
        assert res.finding is None
    assert res.label["ground_truth_source"] == "seeded"


@pytest.mark.parametrize("rid", sorted(RECORD_RECIPES))
def test_recipe_is_deterministic(rid):
    a = apply_record_recipe(_record(), rid)
    b = apply_record_recipe(_record(), rid)
    assert a is not None and b is not None
    assert a.mutated_record == b.mutated_record
    assert a.finding == b.finding


@pytest.mark.parametrize("rid", sorted(RECORD_RECIPES))
def test_mutated_record_is_cue_clean(rid):
    res = apply_record_recipe(_record(), rid)
    blob = json.dumps(res.mutated_record).lower()
    for tok in _CUE_TOKENS:
        assert tok not in blob, f"{rid} leaked cue token {tok!r}"
    assert '"..."' not in json.dumps(res.mutated_record)
    assert "…" not in json.dumps(res.mutated_record)
    assert rid.lower() not in blob, f"{rid} leaked its own recipe id into the record"


# --------------------------------------------------------------------------------------
# DC-12 plan_audit fidelity.
# --------------------------------------------------------------------------------------
def test_dc12_missingfiles_lands_on_plan_audit():
    res = apply_record_recipe(_record(), "R-RECORD-DC12-missingfiles")
    pa = res.mutated_record["plan_audit"]
    assert pa["status"] == "violation" and pa["severity"] == "high"
    assert 1 <= pa["violations"] <= 4
    assert len(pa["missing_files"]) == pa["violations"]
    assert res.dc_class == "DC-12"
    assert "missing_files" in res.finding["locus"]


def test_dc12_extramod_drives_violations_without_severity():
    res = apply_record_recipe(_record(), "R-RECORD-DC12-extramod")
    pa = res.mutated_record["plan_audit"]
    assert pa["status"] == "violation"
    assert pa["severity"] is None  # deliberately no severity key -> model never learns severity==reject
    assert pa["violations"] > 0
    assert pa["extra_modifications"]
    assert pa["loc_variance_pct"] >= 35.0


def test_dc12_gateorder_names_the_ordering_finding():
    res = apply_record_recipe(_record(), "R-RECORD-DC12-gateorder")
    pa = res.mutated_record["plan_audit"]
    assert pa["status"] == "violation" and pa["severity"] == "high"
    assert "gate" in pa["message"].lower()


def test_dc12_missingfiles_count_varies_across_tasks():
    counts = {
        apply_record_recipe(_record(task_id=f"TASK-{i:03d}"), "R-RECORD-DC12-missingfiles")
        .mutated_record["plan_audit"]["violations"]
        for i in range(40)
    }
    assert len(counts) > 1  # not a constant-count cue


@pytest.mark.parametrize("rid", [
    "R-RECORD-DC12-missingfiles", "R-RECORD-DC12-extramod", "R-RECORD-DC12-gateorder",
    "R-RECORD-DC12-control-clean", "R-RECORD-DC12-control-lowvar",
])
def test_dc12_recipes_skip_when_plan_audit_already_violation(rid):
    rec = _record(plan_audit={"status": "violation", "severity": "high", "violations": 2})
    assert apply_record_recipe(rec, rid) is None  # loud None, never a silent no-op


@pytest.mark.parametrize("rid", [
    "R-RECORD-DC12-missingfiles", "R-RECORD-DC12-extramod", "R-RECORD-DC12-gateorder",
    "R-RECORD-DC12-control-clean", "R-RECORD-DC12-control-lowvar",
])
def test_dc12_recipes_skip_when_plan_audit_absent(rid):
    rec = _record()
    del rec["plan_audit"]
    assert apply_record_recipe(rec, rid) is None


def test_dc12_controls_populate_the_same_surface_but_pass():
    for rid in ("R-RECORD-DC12-control-clean", "R-RECORD-DC12-control-lowvar"):
        res = apply_record_recipe(_record(), rid)
        pa = res.mutated_record["plan_audit"]
        assert pa["status"] == "passed" and pa["violations"] == 0
        assert res.verdict == "approve"


# --------------------------------------------------------------------------------------
# DC-14 honesty fidelity.
# --------------------------------------------------------------------------------------
def test_dc14_promisefile_appends_one_nonexistent_impl_file():
    rec = _record()
    before = _all_record_paths(rec)
    res = apply_record_recipe(rec, "R-RECORD-DC14-promisefile")
    promises = res.mutated_record["completion_promises"]
    appended = [p for pr in promises for p in pr["implementation_files"] if p not in before]
    assert len(appended) == 1
    assert appended[0].endswith(".py") and appended[0] not in before
    assert res.dc_class == "DC-14"
    assert "promise_file_existence" in res.finding["locus"]


def test_dc14_multifile_appends_two_or_more_nonexistent_created():
    rec = _record()
    before = set(rec["files_created"])
    res = apply_record_recipe(rec, "R-RECORD-DC14-multifile")
    appended = [p for p in res.mutated_record["files_created"] if p not in before]
    assert len(appended) >= 2
    assert all(p.endswith(".py") for p in appended)
    assert "file_existence" in res.finding["locus"]


def test_dc14_control_demoted_appends_exactly_one():
    rec = _record()
    before = set(rec["files_created"])
    res = apply_record_recipe(rec, "R-RECORD-DC14-control-demoted")
    appended = [p for p in res.mutated_record["files_created"] if p not in before]
    assert len(appended) == 1  # a lone file_existence -> Layer-2 demoted should_fix -> approve
    assert res.verdict == "approve"
    assert res.finding is None


def test_dc14_promisefile_skips_without_a_complete_promise():
    rec = _record(completion_promises=[
        {"criterion_id": "AC-9", "status": "incomplete", "implementation_files": ["src/x.py"]}
    ])
    assert apply_record_recipe(rec, "R-RECORD-DC14-promisefile") is None
    rec2 = _record()
    del rec2["completion_promises"]
    assert apply_record_recipe(rec2, "R-RECORD-DC14-promisefile") is None


@pytest.mark.parametrize("rid", ["R-RECORD-DC14-multifile", "R-RECORD-DC14-control-demoted"])
def test_dc14_created_recipes_skip_without_files_created(rid):
    rec = _record(files_created=[])
    assert apply_record_recipe(rec, rid) is None
    rec2 = _record()
    del rec2["files_created"]
    assert apply_record_recipe(rec2, rid) is None


# --------------------------------------------------------------------------------------
# DC-05 claim-vs-skip (provisional).
# --------------------------------------------------------------------------------------
def test_dc05_skipmask_masks_a_green_resting_on_executed_tests():
    res = apply_record_recipe(_record(), "R-RECORD-DC05-skipmask")
    qg = res.mutated_record["quality_gates"]
    assert qg["all_passed"] is True
    assert qg["tests_passed"] == 0 and qg["tests_passing"] == 0 and qg["tests_failed"] == 0
    assert res.dc_class == "DC-05"


def test_dc05_skipmask_skips_when_no_executed_tests_or_not_green():
    assert apply_record_recipe(
        _record(quality_gates={"all_passed": False, "tests_passing": 3}), "R-RECORD-DC05-skipmask"
    ) is None
    assert apply_record_recipe(
        _record(quality_gates={"all_passed": True, "tests_passing": 0, "tests_passed": 0}),
        "R-RECORD-DC05-skipmask",
    ) is None
    rec = _record()
    del rec["quality_gates"]
    assert apply_record_recipe(rec, "R-RECORD-DC05-skipmask") is None


# --------------------------------------------------------------------------------------
# THE ANTI-SHORTCUT LAW — every reject class is matched by an approve control on the same surface.
# --------------------------------------------------------------------------------------
def test_every_reject_class_has_a_matched_approve_control():
    reject_classes = {RECORD_RECIPES[r].dc_class for r in REJECT_IDS}
    # DC-12 (plan_audit surface) and DC-14 (honesty surface) each carry an approve control that
    # populates the identical bundle-visible surface (the two-sided calibration lever). DC-05 is the
    # provisional claim-vs-skip slice (its two-sided partner is the honest-green harvest/control set).
    assert "DC-12" in reject_classes and "DC-14" in reject_classes
    # DC-12 controls touch plan_audit; DC-14 control touches files_created — the same surfaces.
    dc12_ctrl = apply_record_recipe(_record(), "R-RECORD-DC12-control-clean")
    assert "plan_audit" in dc12_ctrl.mutated_record and dc12_ctrl.verdict == "approve"
    dc14_ctrl = apply_record_recipe(_record(), "R-RECORD-DC14-control-demoted")
    assert dc14_ctrl.verdict == "approve"


def test_derive_nonexistent_paths_are_novel_and_plausible():
    rec = _record()
    existing = _all_record_paths(rec)
    for k in (1, 2, 3, 4):
        paths = _derive_nonexistent_paths(rec, k, salt="t")
        assert len(paths) == k == len(set(paths))
        for p in paths:
            assert p.endswith(".py")
            assert p not in existing
            assert not any(tok in p.lower() for tok in _CUE_TOKENS)


def test_stable_count_bad_range_is_loud():
    from qav.record_recipes import _stable_count

    with pytest.raises(RecordRecipeError):
        _stable_count(_record(), 4, 1, salt="x")
