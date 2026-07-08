"""Manifest tests — validates against OUTPUT-CONTRACT §5; invalid without a passing check."""

from __future__ import annotations

import pytest

from qav.contracts import RowValidationError, build_row
from qav.manifest import (
    build_manifest,
    check_balance,
    balance_report,
    validate_manifest,
)

GREEN = {"honesty": {"discrepancies": [], "should_fix_count": 0}, "gathering_status": "complete",
         "tests": {"passed": True}}
UGLY = {"honesty": {"discrepancies": []}, "gathering_status": "complete",
        "tests": {"passed": True}, "advisory_issues": [{"msg": "flaky import"}]}


def _b(bundle, uniq):
    b = dict(bundle)
    b["profile_name"] = uniq
    return b


def _reject(task, recipe="R-DC03-callsite"):
    return build_row(
        bundle=_b(GREEN, f"{task}-{recipe}"),
        think="Production construction unwitnessed; per-task green is not feature green. Reject.",
        label={"verdict": "reject", "findings": [{"class": "DC-03", "locus": "cli/main.py"}],
               "ground_truth_source": "seeded"},
        provenance={"repo": "guardkit", "feature": "F", "task": task, "run": "r", "sha": "s"},
        split="train", generation_mode="seeded_code", dc_class="DC-03", injection_recipe=recipe,
    )


def _approve(task, bundle=GREEN):
    return build_row(
        bundle=_b(bundle, f"{task}-approve"),
        think="All green, honesty clean. Approve.",
        label={"verdict": "approve", "findings": [], "ground_truth_source": "coach_correct"},
        provenance={"repo": "guardkit", "feature": "F", "task": task, "run": "r", "sha": "s"},
        split="train", generation_mode="harvest", dc_class=None,
    )


def _eval_reject(task):
    r = _reject(task, recipe="R-DC05-sysmod")
    r = build_row(
        bundle=dict(GREEN),
        think="Env tamper suspected. Reject.",
        label={"verdict": "reject", "findings": [{"class": "DC-05", "locus": "pkg/__init__.py"}],
               "ground_truth_source": "seeded"},
        provenance={"repo": "guardkit", "feature": "F", "task": task, "run": "r", "sha": "s"},
        split="eval_qav", generation_mode="seeded_code", dc_class="DC-05", injection_recipe="R-DC05-sysmod",
    )
    return r


def test_manifest_validates_with_passing_check():
    train = [_reject("TASK-A"), _approve("TASK-B")]
    eval_rows = [_eval_reject("TASK-Z")]
    m = build_manifest(train, eval_rows, dataset_id="qav-phase1-train-v1",
                       created="2026-07-08", factory_sha="deadbeef")
    validate_manifest(m)
    assert m["contamination_check"]["status"] == "pass"
    assert m["counts"]["by_verdict"] == {"approve": 1, "reject": 1}
    assert m["counts"]["by_dc_class"]["DC-03"] == 1
    assert m["files"][0]["rows"] == 2
    assert m["visibility"] == "private (DF-008)"
    assert m["format"]["chat_template"] == "gemma-4"


def test_manifest_invalid_when_contamination_fails():
    shared = _reject("TASK-A")
    m = build_manifest([shared], [shared], dataset_id="d", created="2026-07-08", factory_sha="x")
    assert m["contamination_check"]["status"] == "fail"
    with pytest.raises(RowValidationError):
        validate_manifest(m)


def test_manifest_rejects_absent_check_block():
    train = [_approve("TASK-B")]
    m = build_manifest(train, [], dataset_id="d", created="2026-07-08", factory_sha="x")
    m["contamination_check"] = {"status": "unknown"}
    with pytest.raises(RowValidationError):
        validate_manifest(m)


def test_balance_report_and_gate():
    train = [_reject("TASK-A"), _reject("TASK-B"), _approve("TASK-C", UGLY), _approve("TASK-D", UGLY)]
    rep = balance_report(train)
    assert rep["approve_share"] == 0.5
    assert rep["ugly_green_share_of_approves"] == 1.0
    assert check_balance(rep) == []

    skewed = balance_report([_reject("TASK-A"), _reject("TASK-B"), _reject("TASK-E")])
    assert check_balance(skewed)  # approve_share 0.0 -> violation


def test_counts_sum_to_file_rows():
    train = [_reject("TASK-A"), _approve("TASK-B"), _approve("TASK-C")]
    m = build_manifest(train, [], dataset_id="d", created="2026-07-08", factory_sha="x")
    validate_manifest(m)
    assert sum(m["counts"]["by_verdict"].values()) == m["files"][0]["rows"] == 3
