"""DCL manifest — counts by mode/recipe/split, embedded contamination check, invalid
without a passing check, private (DF-008)."""

from __future__ import annotations

import pytest

from dcl.contracts import RowValidationError, build_author_row, build_repair_row
from dcl.manifest import build_manifest, validate_manifest

CAP = "language dcl 1.0\n\nactor Customer is human\n\ncapability PlaceOrder {\n  intent X from Customer\n  outcome Accepted\n  when {\n    always Accepted\n  }\n}"
BROKEN = CAP.replace("is human", "is machine")
DIAG = '[{"severity": "error", "code": "DCL_SEM_ACTOR_KIND_UNKNOWN"}]'
VOCAB = "# vocab\n"


def _author(brief, split="train"):
    return build_author_row(brief=brief, dcl_text=CAP, vocab_reference=VOCAB, split=split)


def _repair(brief_broken, split="train"):
    return build_repair_row(
        broken_dcl=brief_broken, diagnostics_json=DIAG, think="fix the actor kind",
        corrected_dcl=CAP, recipe_id="R-actor-kind", split=split,
    )


def _manifest(train, eval_rows):
    return build_manifest(train, eval_rows, dataset_id="dcl-phase1-train-v1",
                          created="2026-07-17", factory_sha="abc123")


def test_manifest_validates_with_passing_check():
    train = [_author("Place an order."), _repair(BROKEN)]
    eval_rows = [_author("Refund an order.", split="eval_dcl")]
    m = _manifest(train, eval_rows)
    validate_manifest(m)  # no raise
    assert m["contamination_check"]["status"] == "pass"
    assert m["visibility"] == "private (DF-008)"
    assert m["format"]["chat_template"] == "gemma-4"


def test_counts_by_mode_recipe_split():
    train = [_author("Place an order."), _author("Cancel an order."), _repair(BROKEN)]
    m = _manifest(train, [])
    c = m["counts"]["train"]
    assert c["by_mode"] == {"dcl_author": 2, "dcl_repair": 1}
    assert c["by_type"] == {"direct": 2, "reasoning": 1}
    assert c["by_recipe"]["R-actor-kind"] == 1
    assert c["compile_verified"] == 3
    assert c["total"] == 3


def test_manifest_invalid_without_passing_check():
    shared = _author("Place an order.")
    m = _manifest([shared], [shared])  # row_id intersection -> fail
    assert m["contamination_check"]["status"] == "fail"
    with pytest.raises(RowValidationError):
        validate_manifest(m)


def test_manifest_invalid_with_denylisted_row():
    poisoned = build_author_row(
        brief="benign", dcl_text=CAP.replace("PlaceOrder", "GetStats"),
        vocab_reference=VOCAB, split="train",
    )
    m = _manifest([poisoned], [])
    assert m["contamination_check"]["status"] == "fail"
    with pytest.raises(RowValidationError):
        validate_manifest(m)


def test_manifest_rejects_non_private_visibility():
    m = _manifest([_author("Place an order.")], [])
    m["visibility"] = "public"
    with pytest.raises(RowValidationError):
        validate_manifest(m)
