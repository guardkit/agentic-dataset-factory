"""Contract/schema tests — OUTPUT-CONTRACT §1–§4, GOAL.md system prompt fidelity."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from qav.contracts import (
    BUNDLE_FIELDS,
    PHASE1_DC_CLASSES,
    SYSTEM_PROMPT,
    RowValidationError,
    build_row,
    extract_bundle,
    extract_label,
    row_id,
    validate_bundle,
    validate_label,
    validate_row,
)

DOMAIN = Path(__file__).resolve().parent.parent / "domains" / "qa-verifier"

GREEN_BUNDLE = {
    "honesty": {"discrepancies": [], "should_fix_count": 0},
    "gathering_status": "complete",
    "tests": {"passed": True},
}


def _base_row(**over):
    kw = dict(
        bundle=GREEN_BUNDLE,
        think="Reading gathering_status=complete; tests green; honesty clean. Approve.",
        label={"verdict": "approve", "findings": [], "ground_truth_source": "coach_correct"},
        provenance={"repo": "guardkit", "feature": "FEAT-X", "task": "TASK-X", "run": "r1", "sha": "abc"},
        split="train",
        generation_mode="harvest",
        dc_class=None,
    )
    kw.update(over)
    return build_row(**kw)


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def test_system_prompt_matches_goal_md():
    goal = (DOMAIN / "GOAL.md").read_text()
    assert _norm(SYSTEM_PROMPT) in _norm(goal), "SYSTEM_PROMPT drifted from GOAL.md"


def test_bundle_field_set_is_25_pinned_fields():
    assert len(BUNDLE_FIELDS) == 25
    assert BUNDLE_FIELDS[0] == "honesty"


def test_row_id_is_content_addressed_and_stable():
    rid = row_id("hello")
    assert rid.startswith("qav-") and len(rid) == 4 + 16
    assert row_id("hello") == rid
    assert row_id("world") != rid


def test_valid_row_round_trips():
    row = _base_row()
    validate_row(row)
    assert extract_bundle(row) == GREEN_BUNDLE
    assert extract_label(row)["verdict"] == "approve"
    assert row["metadata"]["row_id"] == row_id(row["messages"][1]["content"])


def test_validate_bundle_rejects_unknown_field():
    with pytest.raises(RowValidationError):
        validate_bundle({"honesty": {}, "not_a_field": 1})


def test_validate_bundle_requires_honesty():
    with pytest.raises(RowValidationError):
        validate_bundle({"gathering_status": "complete"})


def test_validate_bundle_accepts_older_schema_subset():
    # GN-3-style verbatim bundle: a subset of the pinned fields (additive rule).
    validate_bundle({"honesty": {}, "gathering_status": "complete", "behavioural_oracle": None})


def test_approve_must_have_empty_findings():
    with pytest.raises(RowValidationError):
        validate_label({"verdict": "approve", "findings": [{"class": "DC-03", "locus": "x"}],
                        "ground_truth_source": "coach_correct"})


def test_reject_requires_finding_with_admissible_class():
    with pytest.raises(RowValidationError):
        validate_label({"verdict": "reject", "findings": [], "ground_truth_source": "seeded"})
    with pytest.raises(RowValidationError):
        validate_label({"verdict": "reject",
                        "findings": [{"class": "DC-99", "locus": "x"}],
                        "ground_truth_source": "seeded"})
    # a documented class passes
    validate_label({"verdict": "reject", "findings": [{"class": "DC-03", "locus": "cli/main.py"}],
                    "ground_truth_source": "seeded"})


def test_phase1_admissible_classes_are_named_only():
    assert PHASE1_DC_CLASSES == {"DC-03", "DC-05", "DC-08", "DC-12", "DC-14"}


def test_gold_negative_mode_must_be_reject_evalqav():
    with pytest.raises(RowValidationError):
        _base_row(
            generation_mode="gold_negative",
            split="train",  # illegal for gold_negative
            label={"verdict": "reject", "findings": [{"class": "DC-03", "locus": "x"}],
                   "ground_truth_source": "merge_review_caught"},
            dc_class="DC-03",
        )


def test_seeded_code_reject_requires_injection_recipe():
    with pytest.raises(RowValidationError):
        _base_row(
            generation_mode="seeded_code",
            label={"verdict": "reject", "findings": [{"class": "DC-03", "locus": "x"}],
                   "ground_truth_source": "seeded"},
            dc_class="DC-03",
            injection_recipe=None,
        )


def test_provenance_must_be_the_pinned_quintet():
    with pytest.raises(RowValidationError):
        _base_row(provenance={"repo": "g", "feature": "f", "task": "t", "run": "r"})  # missing sha
