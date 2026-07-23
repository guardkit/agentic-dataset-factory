"""Hermetic unit tests for the contrast-pair mutation family (``qav.bundle_pairs``).

Pure — every recipe is a ``dict -> (mutated_bundle, locus) | None`` transform over a tiny local
CONTROL-bundle fixture. No worktree, no regenerator, no model. Verifies: registry namespace + class
discipline, verdict-carrying labels fixed by construction, per-recipe fidelity (the mutation lands on
the intended bundle-visible surface), the anti-shortcut approve controls, anchor-absent loudness
(None, never a silent no-op), determinism (×2), cue-cleanliness, schema validity, the
three-distinct-hashes law per atomic pair, and the task-scope ownership cut.
"""

from __future__ import annotations

import copy
import json

import pytest

from qav.bundle_pairs import (
    AB_COHORT_TASKS,
    BDD_OWNING_TASKS,
    EVAL_COHORT_TASKS,
    PAIR_GROUPS,
    PAIR_RECIPES,
    WIRING_OWNING_TASKS,
    PairRecipeError,
    _derive_paths,
    _stable_count,
    apply_pair_recipe,
    applicable_pair_recipes,
    task_pair_plan,
)
from qav.contracts import PHASE1_DC_CLASSES, validate_bundle, validate_label
from qav.generate import bundle_content_hash, cue_audit, evidence_empty_reason


# --------------------------------------------------------------------------------------
# A faithful tiny CONTROL bundle (a healthy green regenerated control — 25-field schema).
# --------------------------------------------------------------------------------------
def _control(**over):
    b = {
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
        "profile_name": "pair-fixture-abc123",
    }
    b.update(over)
    return b


REJECT_IDS = [rid for rid, r in PAIR_RECIPES.items() if r.verdict == "reject"]
APPROVE_IDS = [rid for rid, r in PAIR_RECIPES.items() if r.verdict == "approve"]
_CUE_TOKENS = ("__seeded__", "seeded_defect", "__injected__", "injected_by_recipe", "sentinel", "xxxcue")


# --------------------------------------------------------------------------------------
# Registry integrity.
# --------------------------------------------------------------------------------------
def test_registry_namespace_and_class_discipline():
    assert REJECT_IDS and APPROVE_IDS
    for rid, r in PAIR_RECIPES.items():
        assert rid.startswith("R-BUNDLE-PAIR-"), rid
        assert r.verdict in ("reject", "approve")
        assert callable(r.task_scope)
        if r.verdict == "reject":
            assert r.dc_class in PHASE1_DC_CLASSES
        else:
            assert r.dc_class is None


def test_pair_namespace_disjoint_from_code_record_and_legacy_bundle_recipes():
    from qav.record_recipes import RECORD_RECIPES
    from qav.recipes import RECIPES

    assert set(PAIR_RECIPES).isdisjoint(set(RECIPES))
    assert set(PAIR_RECIPES).isdisjoint(set(RECORD_RECIPES))
    # disjoint from the legacy direct-bundle recipes (R-BUNDLE-DC*) — no id equals a legacy one
    assert not (set(PAIR_RECIPES) & {"R-BUNDLE-DC03-oracle", "R-BUNDLE-DC08-bdd", "R-BUNDLE-DC14-honesty"})


def test_pair_groups_have_exactly_two_reject_sides():
    assert set(PAIR_GROUPS) == {"A", "B"}
    for group, members in PAIR_GROUPS.items():
        assert len(members) == 2
        for m in members:
            assert PAIR_RECIPES[m].verdict == "reject"
            assert PAIR_RECIPES[m].pair_group == group


def test_unknown_recipe_raises_loud():
    with pytest.raises(KeyError):
        apply_pair_recipe(_control(), "R-BUNDLE-PAIR-does-not-exist")


# --------------------------------------------------------------------------------------
# Every recipe fires on the clean control, fixes a valid label, keeps the schema, no in-place mut.
# --------------------------------------------------------------------------------------
@pytest.mark.parametrize("rid", sorted(PAIR_RECIPES))
def test_recipe_fires_and_fixes_a_valid_label(rid):
    original = _control()
    frozen = copy.deepcopy(original)
    res = apply_pair_recipe(original, rid)
    assert res is not None, f"{rid} did not fire on the clean control"
    assert original == frozen, f"{rid} mutated its input bundle in place"
    validate_bundle(res.mutated_bundle)      # the frozen 25-field schema holds (null, never add)
    validate_label(res.label)                # the contracts.py label contract holds by construction
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


@pytest.mark.parametrize("rid", sorted(PAIR_RECIPES))
def test_recipe_is_deterministic(rid):
    a = apply_pair_recipe(_control(), rid)
    b = apply_pair_recipe(_control(), rid)
    assert a is not None and b is not None
    assert a.mutated_bundle == b.mutated_bundle
    assert a.finding == b.finding


@pytest.mark.parametrize("rid", sorted(PAIR_RECIPES))
def test_mutation_is_distinct_from_control_and_evidence_bearing(rid):
    res = apply_pair_recipe(_control(), rid)
    assert bundle_content_hash(res.mutated_bundle) != bundle_content_hash(_control())
    # every minted side must survive the evidence-empty pre-gate (complete / partial_gate_abort)
    assert evidence_empty_reason(res.mutated_bundle) is None, f"{rid} looks evidence-empty"


@pytest.mark.parametrize("rid", sorted(PAIR_RECIPES))
def test_mutated_bundle_is_cue_clean(rid):
    res = apply_pair_recipe(_control(), rid)
    blob = json.dumps(res.mutated_bundle).lower()
    for tok in _CUE_TOKENS:
        assert tok not in blob, f"{rid} leaked cue token {tok!r}"
    assert '"..."' not in json.dumps(res.mutated_bundle)
    assert "…" not in json.dumps(res.mutated_bundle)  # the ellipsis char
    assert rid.lower() not in blob, f"{rid} leaked its own recipe id into the bundle"
    assert not cue_audit(res.mutated_bundle), f"{rid} tripped the widened cue-audit"


# --------------------------------------------------------------------------------------
# Axis A — the DC-12 ↔ DC-03 attractor cut.
# --------------------------------------------------------------------------------------
def test_a_dc12_lands_a_plan_audit_violation_and_aborts():
    res = apply_pair_recipe(_control(), "R-BUNDLE-PAIR-A-dc12")
    pa = res.mutated_bundle["plan_audit"]
    assert pa["status"] == "violation" and pa["severity"] == "high"
    assert 1 <= pa["violations"] <= 4
    assert len(pa["missing_files"]) == pa["violations"]
    assert res.mutated_bundle["gathering_status"] == "partial_gate_abort"
    assert res.dc_class == "DC-12"
    assert "plan_audit_passed=False" in res.finding["locus"]
    assert "missing_files" in res.finding["locus"]


def test_a_dc03_populates_defect_wiring_on_a_plan_clean_green_spine():
    # v1.2 populate-with-defect doctrine: DC-03 ADDS defect-bearing call-site evidence to wiring
    # (the reject side never NULLS a field), plan_audit stays untouched-clean, suites stay green.
    res = apply_pair_recipe(_control(), "R-BUNDLE-PAIR-A-dc03")
    b = res.mutated_bundle
    w = b["wiring"]
    assert isinstance(w, dict) and w["producer_bound"] is False
    assert w["unexercised_call_sites"] >= 1 and w["missing_kwargs"]
    assert w["unexercised_call_sites"] <= w["call_sites"]
    assert b["plan_audit"] == _control()["plan_audit"]  # untouched (clean, not a violation)
    assert b["gathering_status"] == "complete"
    assert res.dc_class == "DC-03"
    locus = res.finding["locus"]
    assert "call site" in locus and "kwargs" in locus and "production construction" in locus


@pytest.mark.parametrize("wiring", [None, {"analyzed": True, "call_sites": 4, "unwired": 0}])
def test_a_dc03_fires_and_diverges_on_both_null_and_populated_control_wiring(wiring):
    # The v1.2 guard: A-dc03 fires whether the control wiring is None (populate) or a dict
    # (overwrite-with-defect) — and MUST hash-diverge from the control either way.
    ctrl = _control(wiring=wiring)
    res = apply_pair_recipe(ctrl, "R-BUNDLE-PAIR-A-dc03")
    assert res is not None
    assert isinstance(res.mutated_bundle["wiring"], dict)
    assert res.mutated_bundle["wiring"]["producer_bound"] is False
    assert bundle_content_hash(res.mutated_bundle) != bundle_content_hash(ctrl)
    assert res.dc_class == "DC-03"


def test_a_dc12_count_varies_across_tasks():
    counts = {
        apply_pair_recipe(_control(profile_name=f"t-{i}"), "R-BUNDLE-PAIR-A-dc12")
        .mutated_bundle["plan_audit"]["violations"]
        for i in range(40)
    }
    assert len(counts) > 1  # not a constant-count cue


@pytest.mark.parametrize("rid", ["R-BUNDLE-PAIR-A-dc12", "R-BUNDLE-PAIR-B-dc12",
                                 "R-BUNDLE-PAIR-CTRL-audit"])
def test_plan_audit_recipes_skip_when_already_violation(rid):
    ctrl = _control(plan_audit={"status": "violation", "severity": "high", "violations": 2})
    assert apply_pair_recipe(ctrl, rid) is None  # loud None, never a silent no-op


@pytest.mark.parametrize("rid", sorted(PAIR_RECIPES))
def test_every_recipe_skips_on_a_non_green_spine(rid):
    # A partial_gate_abort spine is not the clean green baseline the minimal pairs need.
    ctrl = _control(gathering_status="partial_gate_abort")
    assert apply_pair_recipe(ctrl, rid) is None


# --------------------------------------------------------------------------------------
# Axis B — the DC-14 ↔ DC-12 RC-01 cut.
# --------------------------------------------------------------------------------------
def test_b_dc14_zeroes_tests_under_a_confident_narrative():
    res = apply_pair_recipe(_control(), "R-BUNDLE-PAIR-B-dc14")
    b = res.mutated_bundle
    assert b["tests"]["tests_run"] == 0 and b["tests"]["collected"] == 0
    assert b["independent_tests"]["signal_absent"] is True
    assert b["plan_audit"] is None
    assert b["gathering_status"] == "complete"
    assert res.dc_class == "DC-14"
    assert "tests_run=0" in res.finding["locus"] and "signal_absent" in res.finding["locus"]


def test_b_dc12_keeps_tests_green_but_plants_a_plan_violation():
    res = apply_pair_recipe(_control(), "R-BUNDLE-PAIR-B-dc12")
    b = res.mutated_bundle
    assert b["tests"]["tests_run"] > 0
    assert b["plan_audit"]["status"] == "violation"
    assert b["gathering_status"] == "partial_gate_abort"
    assert res.dc_class == "DC-12"


@pytest.mark.parametrize("rid", ["R-BUNDLE-PAIR-B-dc14", "R-BUNDLE-PAIR-B-dc12",
                                 "R-BUNDLE-PAIR-CTRL-tests"])
def test_axis_b_recipes_skip_without_executed_tests(rid):
    ctrl = _control(tests={"tests_run": 0, "collected": 0}, quality_gates={"all_passed": True})
    assert apply_pair_recipe(ctrl, rid) is None


# --------------------------------------------------------------------------------------
# Axis C — the ownership cut, and the matched approve controls.
# --------------------------------------------------------------------------------------
def test_c_dc08_populates_a_defect_authoring_sweep_with_wiring_healthy():
    # v1.2 populate-with-defect doctrine: DC-08 POPULATES bdd_authoring_sweep with undefined step
    # definitions on scenarios the authoring task owed (never nulls a field); wiring stays healthy.
    res = apply_pair_recipe(_control(), "R-BUNDLE-PAIR-C-dc08")
    b = res.mutated_bundle
    sweep = b["bdd_authoring_sweep"]
    assert isinstance(sweep, dict) and sweep["authored"] is False
    assert sweep["undefined_steps"] >= 1 and sweep["undefined_steps"] <= sweep["scenarios_total"]
    assert isinstance(b["wiring"], dict) and b["wiring"]["unwired"] == 0
    assert res.dc_class == "DC-08"
    locus = res.finding["locus"]
    assert "undefined step definitions" in locus and "authoring task" in locus


def test_ctrl_bdd_populates_a_healthy_authoring_sweep():
    # C-dc08's anti-shortcut mate: an elaborated bdd_authoring_sweep with zero undefined steps -> an
    # approve (differs from the defect sweep ONLY in whether steps are undefined).
    res = apply_pair_recipe(_control(), "R-BUNDLE-PAIR-CTRL-bdd")
    assert res.verdict == "approve" and res.finding is None
    sweep = res.mutated_bundle["bdd_authoring_sweep"]
    assert sweep["authored"] is True and sweep["undefined_steps"] == 0


def test_c_dc03_nulls_the_owned_wiring_with_bdd_as_distractor():
    res = apply_pair_recipe(_control(), "R-BUNDLE-PAIR-C-dc03")
    b = res.mutated_bundle
    assert b["wiring"] is None and b["runtime_parity"] is None
    assert b["bdd"] is None  # present only as the distractor
    assert res.dc_class == "DC-03"
    assert "distractor" in res.finding["locus"]


def test_ctrl_audit_populates_a_passing_plan_audit():
    res = apply_pair_recipe(_control(), "R-BUNDLE-PAIR-CTRL-audit")
    assert res.verdict == "approve" and res.finding is None
    pa = res.mutated_bundle["plan_audit"]
    assert pa["status"] == "passed" and pa["violations"] == 0


def test_ctrl_comp_teaches_ownership_from_the_approve_side():
    # wiring populated-HEALTHY + bdd null NOT owned -> an approve (the A-dc03 anti-shortcut mate).
    res = apply_pair_recipe(_control(), "R-BUNDLE-PAIR-CTRL-comp")
    assert res.verdict == "approve"
    w = res.mutated_bundle["wiring"]
    assert isinstance(w, dict) and w["producer_bound"] is True and w["unexercised_call_sites"] == 0
    assert res.mutated_bundle["bdd"] is None


@pytest.mark.parametrize("wiring", [None, {"analyzed": True, "call_sites": 4, "unwired": 0}])
def test_ctrl_comp_fires_everywhere_and_diverges(wiring):
    # v1.2: CTRL-comp fires on ANY green spine (populates wiring healthy whether wiring was null or
    # a dict), and hash-diverges from the control — the fires-everywhere anti-shortcut approve.
    ctrl = _control(wiring=wiring, bdd=None)  # even without bdd present, it still fires
    res = apply_pair_recipe(ctrl, "R-BUNDLE-PAIR-CTRL-comp")
    assert res is not None and res.verdict == "approve"
    assert isinstance(res.mutated_bundle["wiring"], dict)
    assert bundle_content_hash(res.mutated_bundle) != bundle_content_hash(ctrl)


def test_ctrl_tests_is_green_with_an_honest_matching_claim():
    res = apply_pair_recipe(_control(), "R-BUNDLE-PAIR-CTRL-tests")
    assert res.verdict == "approve"
    assert res.mutated_bundle["tests"]["tests_run"] > 0
    assert res.mutated_bundle["independent_tests"]["signal_absent"] is False


def test_every_reject_class_has_a_matched_approve_control_surface():
    reject_classes = {PAIR_RECIPES[r].dc_class for r in REJECT_IDS}
    assert {"DC-12", "DC-14", "DC-03", "DC-08"} <= reject_classes
    # the registry is 4 approve / 6 reject after the v1.2 rebuild (CTRL-bdd = C-dc08's mate).
    assert len(APPROVE_IDS) == 4 and len(REJECT_IDS) == 6
    # the plan_audit surface (DC-12) is matched by CTRL-audit; the tests surface (DC-14) by
    # CTRL-tests; the wiring surface (DC-03) by CTRL-comp; the authoring-sweep surface (DC-08) by
    # CTRL-bdd — every surface both ways.
    for cid in ("CTRL-audit", "CTRL-tests", "CTRL-comp", "CTRL-bdd"):
        assert apply_pair_recipe(_control(), f"R-BUNDLE-PAIR-{cid}").verdict == "approve"
    approve_share = len(APPROVE_IDS) / (len(REJECT_IDS) + len(APPROVE_IDS))
    assert approve_share >= 0.30  # controls in proportion (anti-shortcut law): 4/10 == 0.40


# --------------------------------------------------------------------------------------
# The three-distinct-hashes law (per atomic pair) — the in-engine collision guard's premise.
# --------------------------------------------------------------------------------------
@pytest.mark.parametrize("group", sorted(PAIR_GROUPS))
def test_pair_sides_are_three_distinct_hashes(group):
    ctrl = _control()
    id_a, id_b = PAIR_GROUPS[group]
    ra = apply_pair_recipe(ctrl, id_a)
    rb = apply_pair_recipe(ctrl, id_b)
    hashes = {bundle_content_hash(ctrl), bundle_content_hash(ra.mutated_bundle),
              bundle_content_hash(rb.mutated_bundle)}
    assert len(hashes) == 3, f"pair {group} does not satisfy three-distinct-hashes"


# --------------------------------------------------------------------------------------
# Task-scope — the ownership cut + the eval-cohort-first cohort.
# --------------------------------------------------------------------------------------
def test_eval_cohort_tasks_get_the_full_ab_plus_controls_set():
    for repo, task in EVAL_COHORT_TASKS:
        app = applicable_pair_recipes(repo, task)
        assert "R-BUNDLE-PAIR-A-dc12" in app and "R-BUNDLE-PAIR-A-dc03" in app
        assert "R-BUNDLE-PAIR-B-dc14" in app and "R-BUNDLE-PAIR-B-dc12" in app
        assert any(rid.startswith("R-BUNDLE-PAIR-CTRL-") for rid in app)


def test_axis_c_ownership_cut_is_task_scoped():
    # DC-08 rides BDD-owning tasks only; DC-03-C rides wiring-owning tasks only.
    for repo, task in BDD_OWNING_TASKS:
        assert "R-BUNDLE-PAIR-C-dc08" in applicable_pair_recipes(repo, task)
    for repo, task in WIRING_OWNING_TASKS:
        assert "R-BUNDLE-PAIR-C-dc03" in applicable_pair_recipes(repo, task)
    # a task in neither ownership cohort nor the AB cohort gets nothing.
    assert applicable_pair_recipes("nobody", "TASK-NONE") == []


def test_no_bdd_owning_task_hashes_eval_the_ss4_honest_cap():
    # DESIGN §4: axis-C DC-08 eval rows are not available this cycle (no BDD-owning task hashes eval).
    from qav.generate import assign_split

    for repo, task in BDD_OWNING_TASKS:
        split = assign_split(repo, task, "seeded_bundle", holdout_fraction=0.15, seed="qav-phase1")
        assert split == "train", f"{repo}/{task} unexpectedly hashes eval"


def test_task_pair_plan_splits_groups_and_singles():
    groups, singles = task_pair_plan("guardkit", "TASK-QAWE-004")  # an eval cohort task
    assert [g for g, _ in groups] == ["A", "B"]
    assert all(rid.startswith("R-BUNDLE-PAIR-CTRL-") for rid in singles)
    # a pure BDD-owning task (not in AB cohort) yields no pairs; the axis-C DC-08 side + its
    # healthy-sweep CTRL-bdd mate (registry order: the reject then its approve mate).
    groups2, singles2 = task_pair_plan("guardkit", "TASK-BDDW-001")
    assert groups2 == []
    assert singles2 == ["R-BUNDLE-PAIR-C-dc08", "R-BUNDLE-PAIR-CTRL-bdd"]


# --------------------------------------------------------------------------------------
# Determinism helpers.
# --------------------------------------------------------------------------------------
def test_derive_paths_are_novel_plausible_and_cue_clean():
    for k in (1, 2, 3, 4):
        paths = _derive_paths(_control(), k, salt="t")
        assert len(paths) == k == len(set(paths))
        for p in paths:
            assert p.endswith(".py")
            assert not any(tok in p.lower() for tok in _CUE_TOKENS)


def test_stable_count_bad_range_is_loud():
    with pytest.raises(PairRecipeError):
        _stable_count(_control(), 4, 1, salt="x")


def test_eval_cohort_is_subset_of_ab_cohort():
    assert EVAL_COHORT_TASKS <= AB_COHORT_TASKS
