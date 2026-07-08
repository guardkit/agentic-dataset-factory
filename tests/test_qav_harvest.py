"""Harvest transform tests — real bundles + post-hoc labels, ugly-green detection (PLAN §2)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from qav.contracts import RowValidationError, extract_label, validate_row
from qav.harvest import (
    BundleArtifact,
    Outcome,
    build_harvest_row,
    discover_bundles,
    harvest,
    is_ugly_green,
)

GREEN = {"honesty": {"discrepancies": [], "should_fix_count": 0}, "gathering_status": "complete",
         "tests": {"passed": True}}


def _artifact(bundle, repo="guardkit", task="TASK-X", turn=2):
    return BundleArtifact(repo=repo, task=task, turn=turn, path=Path("x"), bundle=bundle)


def test_coach_correct_becomes_approve():
    row = build_harvest_row(
        _artifact(GREEN),
        Outcome(ground_truth_source="coach_correct", feature="FEAT-X", run="r1", sha="abc"),
    )
    validate_row(row)
    assert extract_label(row) == {"verdict": "approve", "findings": [], "ground_truth_source": "coach_correct"}
    assert row["metadata"]["generation_mode"] == "harvest"


def test_operator_caught_becomes_reject_with_finding():
    row = build_harvest_row(
        _artifact(GREEN),
        Outcome(
            ground_truth_source="operator_caught",
            feature="FEAT-X",
            run="r1",
            sha="abc",
            finding={"class": "DC-03", "locus": "cli/main.py call site"},
        ),
    )
    label = extract_label(row)
    assert label["verdict"] == "reject"
    assert label["findings"][0]["class"] == "DC-03"
    assert row["metadata"]["dc_class"] == "DC-03"


def test_caught_outcome_without_finding_raises():
    with pytest.raises(RowValidationError):
        build_harvest_row(
            _artifact(GREEN),
            Outcome(ground_truth_source="merge_review_caught", feature="F", run="r", sha="s"),
        )


def test_seeded_source_is_rejected_for_harvest():
    with pytest.raises(RowValidationError):
        Outcome(ground_truth_source="seeded", feature="F", run="r", sha="s")


def test_ugly_green_detection():
    assert is_ugly_green({"advisory_issues": [{"msg": "x"}]})
    assert is_ugly_green({"honesty": {"should_fix_count": 2}})
    assert is_ugly_green({"independent_test_classification": {"failure_class": "infrastructure"}})
    assert not is_ugly_green(GREEN)


def test_discover_bundles_picks_final_turn(tmp_path):
    d = tmp_path / "repo" / ".guardkit" / "autobuild" / "TASK-A"
    d.mkdir(parents=True)
    (d / "coach_evidence_turn_1.json").write_text(json.dumps({"gathering_status": "partial_exception"}))
    (d / "coach_evidence_turn_2.json").write_text(json.dumps(GREEN))
    (d / "coach_turn_2.json").write_text(json.dumps({"decision": "approve"}))  # decision record, ignored

    found = discover_bundles({"repo": tmp_path / "repo"})
    assert len(found) == 1
    assert found[0].turn == 2
    assert found[0].task == "TASK-A"
    assert found[0].bundle == GREEN


def test_harvest_skips_tasks_without_an_outcome(tmp_path):
    d = tmp_path / "repo" / ".guardkit" / "autobuild" / "TASK-A"
    d.mkdir(parents=True)
    (d / "coach_evidence_turn_1.json").write_text(json.dumps(GREEN))
    rows = harvest({"repo": tmp_path / "repo"}, outcomes={})  # no outcome supplied
    assert rows == []
