"""Contamination + hold-out discipline — the gate must REFUSE a poisoned corpus.

Content-sha AND identity denylist (stats/version/uptime/GetStats), refuse-on-hit at
brief/source/row level, deterministic split assignment, and train/eval disjointness.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from dcl import contamination
from dcl.contamination import (
    ContaminationError,
    assert_clean,
    assign_split,
    check_contamination,
    content_sha,
    scan,
)
from dcl.contracts import build_author_row

CAP = "language dcl 1.0\n\nactor Customer is human\n\ncapability PlaceOrder {\n  intent X from Customer\n  outcome Accepted\n  when {\n    always Accepted\n  }\n}"
VOCAB = "# vocab (contains the word version in DCL_VERSION_DECL_MISSING — must NOT trip the scan)\n"

FLEET = Path("/home/richardwoollcott/Projects/appmilla_github/fleet-evals")
HELD001 = FLEET / "tasks" / "dcl-held-001-author-stats" / "solution" / "response.dcl"


def _row(brief, cap=CAP, split="train"):
    return build_author_row(brief=brief, dcl_text=cap, vocab_reference=VOCAB, split=split)


# --- identity denylist -----------------------------------------------------------------
@pytest.mark.parametrize("bad", [
    "Add a GET /stats endpoint returning counters.",
    "Author a capability GetStats for the service.",
    "Expose the /version build identity endpoint.",
    "Report service uptime since process start.",
    "Return runtime statistics for the app.",
])
def test_identity_poison_refused_loudly(bad):
    with pytest.raises(ContaminationError):
        assert_clean(bad, what="brief")


def test_clean_brief_passes():
    assert scan("Place a customer order with idempotent persistence.") == []
    assert_clean("Reserve a booking slot for a guest.", what="brief")  # no raise


def test_vocab_boilerplate_word_version_is_not_scanned_at_row_level():
    # The vocab reference legitimately contains "version"; the row-level scan is scoped to
    # the capability text, so a benign author row does not trip the denylist.
    row = _row("Place an order.")
    result = check_contamination([row], [])
    assert result.passed


# --- content-sha denylist --------------------------------------------------------------
@pytest.mark.skipif(not HELD001.is_file(), reason="fleet-evals hold-out not present")
def test_content_sha_poison_refused():
    text = HELD001.read_text(encoding="utf-8")
    assert content_sha(text) in contamination.DENYLIST_CONTENT_SHAS
    with pytest.raises(ContaminationError):
        assert_clean(text, what="source capability")


# --- check_contamination over rows -----------------------------------------------------
def test_clean_split_passes():
    train = [_row("Place an order."), _row("Cancel an order.")]
    eval_rows = [_row("Refund an order.", split="eval_dcl")]
    result = check_contamination(train, eval_rows)
    assert result.passed
    assert result.to_dict()["status"] == "pass"
    assert result.to_dict()["denylist_violations"] == []


def test_row_id_intersection_fails():
    shared = _row("Place an order.")
    result = check_contamination([shared], [shared])
    assert not result.passed
    assert len(result.intersection) == 1


def test_denylisted_capability_in_a_row_fails():
    poisoned_cap = CAP.replace("PlaceOrder", "GetStats")
    row = _row("A benign brief.", cap=poisoned_cap)
    result = check_contamination([row], [])
    assert not result.passed
    assert result.denylist_violations
    # "GetStats" camelCase-splits to {get, stats}; the `stats` hold-out identity is caught.
    assert any("stats" in v["hit"] for v in result.denylist_violations)


# --- split assignment ------------------------------------------------------------------
def test_assign_split_is_deterministic_and_fractional():
    ids = [f"dcl-{i:016x}" for i in range(2000)]
    assert all(assign_split(i, holdout_fraction=0.0) == "train" for i in ids)
    assert all(assign_split(i, holdout_fraction=1.0) == "eval_dcl" for i in ids)
    # stable across calls
    assert assign_split(ids[0], holdout_fraction=0.1) == assign_split(ids[0], holdout_fraction=0.1)
    evals = sum(1 for i in ids if assign_split(i, holdout_fraction=0.1) == "eval_dcl")
    assert 0.05 < evals / len(ids) < 0.15  # ~10% within a loose band
