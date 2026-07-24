"""QAV v4 (leg B3) contrast-pair additions — the vacancy cohort + the DC-05 boundary (axis D).

Hermetic, pure (``dict -> (mutated_bundle, locus) | None``): a tiny vacancy-cohort-style CONTROL
fixture (wiring + stub_scan POPULATED, plan_audit NULL, independent_tests present) exercises the new
recipes. Verifies: the vacancy cohort scope, the axis-D + vacancy CTRL scope extensions, the split-
side assignment (DB-005/DB-006 hash eval; the other five train), label-honesty (a blank recipe LOUD-
skips an already-null section), the DC-05 tamper signatures vs the honest-skip / clean CTRL mates,
determinism (x2), cue-cleanliness, and the raised contrast_pair_budget.
"""

from __future__ import annotations

import copy
import json
import re
from pathlib import Path

import pytest
import yaml

from qav.bundle_pairs import (
    AB_COHORT_TASKS,
    AB_PLUS_VACANCY_TASKS,
    VACANCY_COHORT_TASKS,
    PAIR_RECIPES,
    _claimed_passing,
    apply_pair_recipe,
    applicable_pair_recipes,
    task_pair_plan,
)
from qav.contracts import PHASE1_DC_CLASSES, validate_bundle, validate_label
from qav.generate import assign_split, bundle_content_hash, cue_audit, evidence_empty_reason


# --------------------------------------------------------------------------------------
# The PRIMARY vacancy-cohort CONTROL mirrors the REAL guardkit gather shape (verified on disk at
# record-store/api_test/TASK-UPT-001): quality_gates carries a BOOL ``tests_passed`` flag with NO
# ``tests_passing`` key; ``tests.tests_run`` is null; the independent junit carries no int passing
# count (only a bool ``tests_passed`` + a 0 ``tests_skipped``). wiring + stub_scan are POPULATED and
# plan_audit is NULL (the B2-proven pure-shape enabler). Because NO genuine int passing count exists
# anywhere, ``_claimed_passing`` falls to its per-spine VARIED default — the exact axis-D path the v3
# int-shape fixture masked (the bool leaked in as ``True`` == 1 and collapsed every count). The
# int-shape second case lives in ``_vac_control_intshape``.
# --------------------------------------------------------------------------------------
def _vac_control(**over):
    b = {
        "honesty": {"verified": True, "discrepancies": []},
        "gathering_status": "complete",
        "gathering_error": None,
        "quality_gates": {"tests_passed": True, "tests_failed": 0, "all_gates_passed": True},
        "plan_audit": None,  # the pure-shape enabler: no plan-audit block
        "tests": {"tests_passed": True, "tests_run": None, "tests_failed": 0, "all_passed": True},
        "wiring": {"analyzed": True, "call_sites": 5, "unwired": 0, "producer_bound": True},
        "stub_scan": {"analyzed": True, "stubs_found": 0, "scanned_modules": 5},
        "runtime_parity": {"checked": True, "mismatches": 0},
        "independent_tests": {"tests_passed": True, "signal_absent": False, "tests_skipped": 0},
        "profile_name": "vac-fixture-def456",
    }
    b.update(over)
    return b


def _vac_control_intshape(**over):
    """The int-shape SECOND case: quality_gates / tests / independent_tests carry GENUINE int counts
    (some real spines do record ``tests_run``). ``_claimed_passing`` reads the int directly (== 21)."""
    b = _vac_control()
    b["quality_gates"] = {"all_passed": True, "tests_passed": 21, "tests_passing": 21, "tests_failed": 0}
    b["tests"] = {"tests_run": 21, "passed": True, "all_passed": True, "collected": 21}
    b["independent_tests"] = {"signal_absent": False, "passed": True, "collected": 21}
    b.update(over)
    return b


_CUE_TOKENS = ("__seeded__", "seeded_defect", "__injected__", "injected_by_recipe", "sentinel", "xxxcue")

V4_VACANCY_REJECTS = (
    "R-BUNDLE-PAIR-Cvac-wiring", "R-BUNDLE-PAIR-Cvac-stub",
    "R-BUNDLE-PAIR-Cvac-both", "R-BUNDLE-PAIR-Cvac-clean",
)
V4_AXIS_D_REJECTS = ("R-BUNDLE-PAIR-D-dc05", "R-BUNDLE-PAIR-D-dc05stub")
V4_NEW_APPROVES = ("R-BUNDLE-PAIR-CTRL-stub", "R-BUNDLE-PAIR-CTRL-vac", "R-BUNDLE-PAIR-CTRL-skips")
V4_ALL_NEW = V4_VACANCY_REJECTS + V4_AXIS_D_REJECTS + V4_NEW_APPROVES


# --------------------------------------------------------------------------------------
# Cohorts + scopes.
# --------------------------------------------------------------------------------------
def test_vacancy_cohort_is_the_seven_api_test_go_spines():
    assert VACANCY_COHORT_TASKS == frozenset({
        ("api_test", "TASK-UPT-001"),
        ("api_test", "TASK-DB-005"),
        ("api_test", "TASK-DB-006"),
        ("api_test", "TASK-DB-007"),
        ("api_test", "TASK-DB-008"),
        ("api_test", "TASK-ADOC-002"),
        ("api_test", "TASK-ED5F"),
    })
    # a second repo (api_test) — breaks the single-repo monoculture the v3 exam failed on.
    assert {repo for repo, _ in VACANCY_COHORT_TASKS} == {"api_test"}


def test_ab_plus_vacancy_is_the_disjoint_union():
    assert AB_PLUS_VACANCY_TASKS == AB_COHORT_TASKS | VACANCY_COHORT_TASKS
    assert AB_COHORT_TASKS.isdisjoint(VACANCY_COHORT_TASKS)  # api_test never overlaps the AB cohort


def test_v4_registry_additions_are_present_and_class_correct():
    for rid in V4_ALL_NEW:
        assert rid in PAIR_RECIPES, rid
    for rid in V4_VACANCY_REJECTS:
        assert PAIR_RECIPES[rid].verdict == "reject" and PAIR_RECIPES[rid].dc_class == "DC-03"
    for rid in V4_AXIS_D_REJECTS:
        assert PAIR_RECIPES[rid].verdict == "reject" and PAIR_RECIPES[rid].dc_class == "DC-05"
        assert PAIR_RECIPES[rid].axis == "D"
    for rid in V4_NEW_APPROVES:
        assert PAIR_RECIPES[rid].verdict == "approve" and PAIR_RECIPES[rid].dc_class is None
    # DC-05 is now a represented reject class (the v4 boundary axis).
    assert "DC-05" in {PAIR_RECIPES[r].dc_class for r in PAIR_RECIPES if PAIR_RECIPES[r].verdict == "reject"}


def test_vacancy_blanks_ride_only_the_vacancy_cohort():
    for rid in V4_VACANCY_REJECTS:
        scope = PAIR_RECIPES[rid].task_scope
        for repo, task in VACANCY_COHORT_TASKS:
            assert scope(repo, task), f"{rid} should ride {repo}/{task}"
        # never an AB-cohort task, never a stranger
        assert not scope("guardkit", "TASK-QAWE-004")
        assert not scope("nobody", "TASK-NONE")


def test_axis_d_and_new_controls_ride_ab_and_vacancy():
    for rid in V4_AXIS_D_REJECTS + ("R-BUNDLE-PAIR-CTRL-stub", "R-BUNDLE-PAIR-CTRL-vac",
                                     "R-BUNDLE-PAIR-CTRL-skips"):
        scope = PAIR_RECIPES[rid].task_scope
        assert scope("guardkit", "TASK-QAWE-004")        # an AB (eval) cohort task
        assert scope("api_test", "TASK-DB-005")          # a vacancy cohort task
        assert not scope("guardkit", "TASK-BDDW-001")    # BDD-owning only — never


def test_ctrl_comp_scope_extended_to_the_vacancy_cohort():
    scope = PAIR_RECIPES["R-BUNDLE-PAIR-CTRL-comp"].task_scope
    for repo, task in VACANCY_COHORT_TASKS:
        assert scope(repo, task)
    assert scope("guardkit", "TASK-QAWE-004")  # still rides the AB cohort


# --------------------------------------------------------------------------------------
# Split-side assignment — the eval-side coverage the vacancy cohort finally lands (seeded_bundle).
# --------------------------------------------------------------------------------------
def test_vacancy_cohort_split_sides_two_eval_five_train():
    def split(task):
        return assign_split("api_test", task, "seeded_bundle", holdout_fraction=0.15, seed="qav-phase1")

    assert split("TASK-DB-005") == "eval_qav"
    assert split("TASK-DB-006") == "eval_qav"
    for task in ("TASK-UPT-001", "TASK-DB-007", "TASK-DB-008", "TASK-ADOC-002", "TASK-ED5F"):
        assert split(task) == "train", task


# --------------------------------------------------------------------------------------
# Label-honesty — a blank recipe LOUD-skips (None) an already-null section (never a silent no-op).
# --------------------------------------------------------------------------------------
def test_vacancy_blanks_skip_loudly_when_the_target_section_is_already_null():
    assert apply_pair_recipe(_vac_control(wiring=None), "R-BUNDLE-PAIR-Cvac-wiring") is None
    assert apply_pair_recipe(_vac_control(stub_scan=None), "R-BUNDLE-PAIR-Cvac-stub") is None
    assert apply_pair_recipe(_vac_control(wiring=None), "R-BUNDLE-PAIR-Cvac-both") is None
    assert apply_pair_recipe(_vac_control(stub_scan=None), "R-BUNDLE-PAIR-Cvac-both") is None
    assert apply_pair_recipe(_vac_control(wiring=None), "R-BUNDLE-PAIR-Cvac-clean") is None


@pytest.mark.parametrize("rid", V4_ALL_NEW)
def test_v4_recipe_skips_on_a_non_green_spine(rid):
    assert apply_pair_recipe(_vac_control(gathering_status="partial_gate_abort"), rid) is None


# --------------------------------------------------------------------------------------
# Per-recipe fidelity, determinism, schema/label validity, cue-cleanliness.
# --------------------------------------------------------------------------------------
@pytest.mark.parametrize("rid", V4_ALL_NEW)
def test_v4_recipe_fires_deterministic_valid_and_cue_clean(rid):
    original = _vac_control()
    frozen = copy.deepcopy(original)
    a = apply_pair_recipe(original, rid)
    b = apply_pair_recipe(_vac_control(), rid)
    assert a is not None, f"{rid} did not fire on the vacancy control"
    assert original == frozen, f"{rid} mutated its input in place"
    # determinism x2
    assert a.mutated_bundle == b.mutated_bundle and a.finding == b.finding
    validate_bundle(a.mutated_bundle)
    validate_label(a.label)
    # diverges from the control + survives the evidence-empty pre-gate
    assert bundle_content_hash(a.mutated_bundle) != bundle_content_hash(_vac_control())
    assert evidence_empty_reason(a.mutated_bundle) is None
    # cue-clean
    blob = json.dumps(a.mutated_bundle).lower()
    for tok in _CUE_TOKENS:
        assert tok not in blob, f"{rid} leaked cue {tok!r}"
    assert '"..."' not in json.dumps(a.mutated_bundle) and "…" not in json.dumps(a.mutated_bundle)
    assert rid.lower() not in blob
    assert not cue_audit(a.mutated_bundle), f"{rid} tripped cue_audit"
    # label discipline by construction
    if a.verdict == "reject":
        assert a.dc_class in PHASE1_DC_CLASSES and a.finding["class"] == a.dc_class
        assert a.finding["locus"].strip()
    else:
        assert a.finding is None and a.label["findings"] == []
    assert a.label["ground_truth_source"] == "seeded"


# --------------------------------------------------------------------------------------
# The pure-shape vacancy blanks — the exam shape (blank section AND no plan-audit block).
# --------------------------------------------------------------------------------------
def test_cvac_wiring_blanks_wiring_only_keeping_plan_null():
    b = apply_pair_recipe(_vac_control(), "R-BUNDLE-PAIR-Cvac-wiring").mutated_bundle
    assert b["wiring"] is None
    assert b["stub_scan"] is not None          # only wiring blanked
    assert b["plan_audit"] is None             # pure shape: no plan-audit block
    assert b["gathering_status"] == "complete"


def test_cvac_stub_blanks_stub_scan_only():
    b = apply_pair_recipe(_vac_control(), "R-BUNDLE-PAIR-Cvac-stub").mutated_bundle
    assert b["stub_scan"] is None
    assert b["wiring"] is not None
    assert b["plan_audit"] is None


def test_cvac_both_blanks_both_sections():
    b = apply_pair_recipe(_vac_control(), "R-BUNDLE-PAIR-Cvac-both").mutated_bundle
    assert b["wiring"] is None and b["stub_scan"] is None
    assert b["plan_audit"] is None


def test_cvac_wiring_locus_speaks_the_dc03_anchor_vocabulary():
    locus = apply_pair_recipe(_vac_control(), "R-BUNDLE-PAIR-Cvac-wiring").finding["locus"]
    assert "call site" in locus and "producer" in locus and "production construction" in locus


# --------------------------------------------------------------------------------------
# Axis D — the DC-05 tamper signatures and the honest / clean CTRL mates.
# --------------------------------------------------------------------------------------
def test_d_dc05_is_a_skip_vs_claim_divergence():
    # REAL gather shape: claimed comes from the per-spine varied default, so the claim counts the
    # SAME collected suite passing (a plain int, never the bool that used to leak in), while the
    # junit reports skips the claim does not own — the divergence.
    b = apply_pair_recipe(_vac_control(), "R-BUNDLE-PAIR-D-dc05").mutated_bundle
    ind, qg = b["independent_tests"], b["quality_gates"]
    assert ind["skipped"] >= 2                              # the junit reports skips
    assert isinstance(qg["tests_passing"], int) and not isinstance(qg["tests_passing"], bool)
    assert qg["tests_passing"] == ind["collected"]         # the claim counts the collected suite passing
    assert ind["skipped"] != qg.get("tests_skipped", 0)    # DIVERGENCE (claim doesn't own the skips)
    locus = apply_pair_recipe(_vac_control(), "R-BUNDLE-PAIR-D-dc05").finding["locus"]
    assert "skip-guard" in locus and ("diverge" in locus or "divergence" in locus)
    # int-shape variant: the claim reads the genuine int count directly.
    bi = apply_pair_recipe(_vac_control_intshape(), "R-BUNDLE-PAIR-D-dc05").mutated_bundle
    assert bi["quality_gates"]["tests_passing"] == 21 and bi["independent_tests"]["collected"] == 21


def test_d_dc05stub_populates_a_sys_modules_stub_hit():
    b = apply_pair_recipe(_vac_control(), "R-BUNDLE-PAIR-D-dc05stub").mutated_bundle
    ss = b["stub_scan"]
    assert ss["stubs_found"] >= 1 and ss["sys_modules_stubs"]
    assert len(ss["sys_modules_stubs"]) == ss["stubs_found"]
    locus = apply_pair_recipe(_vac_control(), "R-BUNDLE-PAIR-D-dc05stub").finding["locus"]
    assert "sys.modules" in locus and "skip-guard" in locus


def test_ctrl_skips_acknowledges_the_same_skips_no_divergence():
    b = apply_pair_recipe(_vac_control(), "R-BUNDLE-PAIR-CTRL-skips").mutated_bundle
    ind, qg = b["independent_tests"], b["quality_gates"]
    assert ind["skipped"] >= 1
    assert qg["tests_skipped"] == ind["skipped"]   # the claim OWNS the skips — approve, no divergence


def test_ctrl_vac_is_skip_free_and_matches_the_claimed_counts():
    b = apply_pair_recipe(_vac_control(), "R-BUNDLE-PAIR-CTRL-vac").mutated_bundle
    ind = b["independent_tests"]
    assert ind["skipped"] == 0 and ind["collected"] == ind["passed"]
    assert isinstance(ind["collected"], int) and not isinstance(ind["collected"], bool)
    # int-shape variant: the counts are exactly the claimed 21.
    bi = apply_pair_recipe(_vac_control_intshape(), "R-BUNDLE-PAIR-CTRL-vac").mutated_bundle
    assert bi["independent_tests"]["collected"] == bi["independent_tests"]["passed"] == 21


def test_ctrl_stub_populates_a_clean_zero_hit_scan():
    b = apply_pair_recipe(_vac_control(), "R-BUNDLE-PAIR-CTRL-stub").mutated_bundle
    ss = b["stub_scan"]
    assert ss["stubs_found"] == 0 and ss["sys_modules_stubs"] == []


def test_dc05_reject_and_honest_skip_control_are_distinct_bundles():
    # the flagship contrast: same junit-skip surface, opposite verdict — the tamper reject and its
    # honest-skip approve mate must be different bundles (the two-sided anti-shortcut teaching pair).
    rej = apply_pair_recipe(_vac_control(), "R-BUNDLE-PAIR-D-dc05").mutated_bundle
    app = apply_pair_recipe(_vac_control(), "R-BUNDLE-PAIR-CTRL-skips").mutated_bundle
    assert bundle_content_hash(rej) != bundle_content_hash(app)


def test_cvac_clean_nulls_wiring_with_the_tamper_surfaces_clean():
    # the C-dc03 vacancy shape, clean-tamper-surface variant: blank wiring (DC-03) BUT stub_scan
    # zero-hit + junit skip-free — the DC-05 surfaces are demonstrably clean (teaches not-tamper).
    b = apply_pair_recipe(_vac_control(), "R-BUNDLE-PAIR-Cvac-clean").mutated_bundle
    assert b["wiring"] is None
    assert b["stub_scan"]["stubs_found"] == 0 and b["stub_scan"]["sys_modules_stubs"] == []
    assert b["independent_tests"]["skipped"] == 0
    assert b["plan_audit"] is None
    r = apply_pair_recipe(_vac_control(), "R-BUNDLE-PAIR-Cvac-clean")
    assert r.dc_class == "DC-03"


# --------------------------------------------------------------------------------------
# Axis-D bool-leak regression (the QAV v4 B3 defect that this fix closes). The pre-fix
# _claimed_passing read the bool quality_gates.tests_passed as a count (True == 1), leaking the bool
# into every minted count field, rendering "the same True tests passing" loci, collapsing the skip
# ranges (D-dc05 always skipped==2, CTRL-skips always skipped==1), and minting internally-
# inconsistent rows (skipped=2 of collected=1). These regressions pin the shape→count cure.
# --------------------------------------------------------------------------------------
# The count fields each axis-D / count-minting recipe MINTS (must be plain ints on either shape).
_AXIS_D_MINTED_COUNTS = {
    "R-BUNDLE-PAIR-D-dc05": [
        ("independent_tests", "skipped"), ("independent_tests", "passed"),
        ("independent_tests", "failed"), ("independent_tests", "collected"),
        ("quality_gates", "tests_passing"), ("quality_gates", "tests_passed"),
        ("quality_gates", "tests_failed"),
    ],
    "R-BUNDLE-PAIR-CTRL-vac": [
        ("independent_tests", "skipped"), ("independent_tests", "passed"),
        ("independent_tests", "failed"), ("independent_tests", "collected"),
    ],
    "R-BUNDLE-PAIR-CTRL-skips": [
        ("independent_tests", "skipped"), ("independent_tests", "passed"),
        ("independent_tests", "failed"), ("independent_tests", "collected"),
        ("quality_gates", "tests_skipped"), ("quality_gates", "tests_passing"),
        ("quality_gates", "tests_passed"),
    ],
    "R-BUNDLE-PAIR-Cvac-clean": [
        ("independent_tests", "skipped"), ("independent_tests", "passed"),
        ("independent_tests", "failed"), ("independent_tests", "collected"),
    ],
}


def test_claimed_passing_is_a_plain_int_on_both_shapes():
    # real gather shape (bool gate flag, null counts) -> the per-spine varied default; int shape ->
    # the genuine int passing count read directly. NEVER a bool (True == 1 was the leak).
    c_real = _claimed_passing(_vac_control())
    c_int = _claimed_passing(_vac_control_intshape())
    assert isinstance(c_real, int) and not isinstance(c_real, bool)
    assert 4 <= c_real <= 12                       # the per-spine varied default range
    assert c_int == 21                             # the genuine int passing count read directly


@pytest.mark.parametrize("shape", ["real", "int"])
@pytest.mark.parametrize("rid", sorted(_AXIS_D_MINTED_COUNTS))
def test_no_bool_in_minted_count_fields_or_locus_on_either_shape(rid, shape):
    ctrl = _vac_control() if shape == "real" else _vac_control_intshape()
    res = apply_pair_recipe(ctrl, rid)
    assert res is not None
    b = res.mutated_bundle
    for section, key in _AXIS_D_MINTED_COUNTS[rid]:
        v = b[section][key]
        assert isinstance(v, int) and not isinstance(v, bool), (rid, shape, section, key, repr(v))
    # no standalone bool literal masquerading in the locus text (the "same True tests passing" bug)
    if res.finding:
        assert not re.search(r"\bTrue\b|\bFalse\b", res.finding["locus"]), res.finding["locus"]


def test_skip_counts_vary_across_differing_spines_no_constant_cue():
    # the pre-fix bug collapsed D-dc05 skipped to a constant 2 and CTRL-skips to a constant 1 (the
    # bool forced claimed == 1). On the real shape claimed is the per-spine varied default, so the
    # skip counts AND the collected counts must vary across differing spines.
    d_skips, d_cols, ctrl_skips = set(), set(), set()
    for i in range(16):
        spine = _vac_control(profile_name=f"vary-spine-{i}")
        d_ind = apply_pair_recipe(spine, "R-BUNDLE-PAIR-D-dc05").mutated_bundle["independent_tests"]
        d_skips.add(d_ind["skipped"]); d_cols.add(d_ind["collected"])
        s_ind = apply_pair_recipe(spine, "R-BUNDLE-PAIR-CTRL-skips").mutated_bundle["independent_tests"]
        ctrl_skips.add(s_ind["skipped"])
    assert len(d_skips) > 1, sorted(d_skips)       # NOT a constant skip cue
    assert len(d_cols) > 1, sorted(d_cols)         # NOT a constant collected cue
    assert len(ctrl_skips) > 1, sorted(ctrl_skips)


def test_d_dc05_counts_are_internally_consistent_on_the_real_shape():
    for i in range(16):
        ind = apply_pair_recipe(
            _vac_control(profile_name=f"cons-spine-{i}"), "R-BUNDLE-PAIR-D-dc05"
        ).mutated_bundle["independent_tests"]
        assert ind["skipped"] >= 0 and ind["passed"] >= 0 and ind["failed"] >= 0
        assert ind["skipped"] <= ind["collected"]                              # skipped <= collected
        assert ind["passed"] + ind["skipped"] + ind["failed"] <= ind["collected"]  # sum <= collected


# --------------------------------------------------------------------------------------
# task_pair_plan over the two cohort shapes.
# --------------------------------------------------------------------------------------
def test_vacancy_task_gets_only_pure_shape_singles_no_pairs():
    for _repo, task in sorted(VACANCY_COHORT_TASKS):
        groups, singles = task_pair_plan("api_test", task)
        assert groups == [], task  # no A/B atomic pair on a vacancy spine
        for rid in V4_VACANCY_REJECTS + V4_AXIS_D_REJECTS + (
            "R-BUNDLE-PAIR-CTRL-comp", *V4_NEW_APPROVES
        ):
            assert rid in singles, (task, rid)
        # the AB-only recipes never ride a vacancy spine
        for rid in ("R-BUNDLE-PAIR-A-dc12", "R-BUNDLE-PAIR-B-dc14", "R-BUNDLE-PAIR-CTRL-audit",
                    "R-BUNDLE-PAIR-CTRL-tests", "R-BUNDLE-PAIR-C-dc08"):
            assert rid not in singles


def test_ab_task_gains_the_axis_d_sides_but_keeps_its_pairs():
    groups, singles = task_pair_plan("guardkit", "TASK-QAWE-004")
    assert [g for g, _ in groups] == ["A", "B"]
    assert "R-BUNDLE-PAIR-D-dc05" in singles and "R-BUNDLE-PAIR-D-dc05stub" in singles
    # the vacancy-only blanks never ride an AB spine
    for rid in V4_VACANCY_REJECTS:
        assert rid not in applicable_pair_recipes("guardkit", "TASK-QAWE-004")


# --------------------------------------------------------------------------------------
# The raised contrast_pair_budget — receipted in the shipped yaml (the coach's ~222 candidate
# ceiling, 224 sits just above it).
# --------------------------------------------------------------------------------------
def test_contrast_pair_budget_raised_to_224_in_the_shipped_config():
    cfg_path = Path(__file__).resolve().parents[1] / "domains" / "qa-verifier" / "agent-config.yaml"
    cfg = yaml.safe_load(cfg_path.read_text(encoding="utf-8"))
    assert cfg["generation"]["contrast_pair_budget"] == 224
