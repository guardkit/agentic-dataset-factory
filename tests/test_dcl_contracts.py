"""DCL row contracts — round-trip, row_id stability, author/repair mode discipline.

Pure (no compiler call): validate_row checks structure/fence/think, not compilation.
"""

from __future__ import annotations

import copy

import pytest

from dcl import contracts
from dcl.contracts import (
    RowValidationError,
    build_author_row,
    build_repair_row,
    extract_capability,
    row_id,
    validate_row,
)

CAP = "language dcl 1.0\n\nactor Customer is human\n\ncapability PlaceOrder {\n  intent X from Customer\n  outcome Accepted\n  when {\n    always Accepted\n  }\n}"
BROKEN = CAP.replace("is human", "is machine")
DIAG = '[{"severity": "error", "code": "DCL_SEM_ACTOR_KIND_UNKNOWN", "message": "unknown kind"}]'
VOCAB = "# DCL vocab\nactor kinds: human, system, agent, scheduled_process\n"


def test_author_row_round_trips():
    row = build_author_row(brief="Place an order.", dcl_text=CAP, vocab_reference=VOCAB, split="train")
    validate_row(row)
    assert row["metadata"]["mode"] == "dcl_author"
    assert row["metadata"]["type"] == "direct"
    assert row["metadata"]["recipe_id"] is None
    assert row["metadata"]["compile_verified"] is True
    assert row["metadata"]["provenance"] == {
        "source": "synthetic-brief", "vocab_pin": "4f9fbe56", "compiler_pin": "4f9fbe56",
    }
    assert "<think>" not in row["messages"][2]["content"]
    assert extract_capability(row).strip() == CAP.strip()


def test_repair_row_round_trips():
    row = build_repair_row(
        broken_dcl=BROKEN, diagnostics_json=DIAG, think="The actor kind `machine` is not in the "
        "closed set; restore `human`.", corrected_dcl=CAP, recipe_id="R-actor-kind", split="eval_dcl",
    )
    validate_row(row)
    assert row["metadata"]["mode"] == "dcl_repair"
    assert row["metadata"]["type"] == "reasoning"
    assert row["metadata"]["recipe_id"] == "R-actor-kind"
    assert row["metadata"]["provenance"]["source"] == "derived"
    assert "<think>" in row["messages"][2]["content"]
    # user message carries the broken dcl + the verbatim diagnostics
    user = row["messages"][1]["content"]
    assert "is machine" in user
    assert "DCL_SEM_ACTOR_KIND_UNKNOWN" in user
    # the corrected capability is the pre-injection original
    assert extract_capability(row).strip() == CAP.strip()


def test_row_id_is_content_addressed_and_stable():
    row1 = build_author_row(brief="Place an order.", dcl_text=CAP, vocab_reference=VOCAB, split="train")
    row2 = build_author_row(brief="Place an order.", dcl_text=CAP, vocab_reference=VOCAB, split="eval_dcl")
    # identical user message -> identical row_id, regardless of split/label
    assert row1["metadata"]["row_id"] == row2["metadata"]["row_id"]
    assert row1["metadata"]["row_id"].startswith("dcl-")
    assert len(row1["metadata"]["row_id"]) == len("dcl-") + 16
    # a different brief -> a different row_id
    row3 = build_author_row(brief="Cancel an order.", dcl_text=CAP, vocab_reference=VOCAB, split="train")
    assert row3["metadata"]["row_id"] != row1["metadata"]["row_id"]


def test_system_prompt_matches_goal_md():
    from pathlib import Path
    from domain_config.parser import parse_goal_md

    cfg = parse_goal_md(Path(__file__).resolve().parent.parent / "domains" / "dcl-capability-language" / "GOAL.md")
    norm = lambda s: " ".join(s.split())
    assert norm(cfg.system_prompt) == norm(contracts.SYSTEM_PROMPT)


def test_validate_rejects_author_with_think():
    row = build_author_row(brief="Place an order.", dcl_text=CAP, vocab_reference=VOCAB, split="train")
    row["messages"][2]["content"] = "<think>sneaky</think>\n\n" + row["messages"][2]["content"]
    with pytest.raises(RowValidationError):
        validate_row(row)


def test_validate_rejects_repair_without_think():
    row = build_repair_row(broken_dcl=BROKEN, diagnostics_json=DIAG, think="x", corrected_dcl=CAP,
                           recipe_id="R-actor-kind", split="train")
    row["messages"][2]["content"] = contracts.author_assistant_content(CAP)  # strip think
    with pytest.raises(RowValidationError):
        validate_row(row)


def test_validate_rejects_tampered_row_id():
    row = build_author_row(brief="Place an order.", dcl_text=CAP, vocab_reference=VOCAB, split="train")
    row["metadata"]["row_id"] = "dcl-0000000000000000"
    with pytest.raises(RowValidationError):
        validate_row(row)


def test_validate_rejects_bad_mode():
    row = build_author_row(brief="Place an order.", dcl_text=CAP, vocab_reference=VOCAB, split="train")
    bad = copy.deepcopy(row)
    bad["metadata"]["mode"] = "dcl_freestyle"
    with pytest.raises(RowValidationError):
        validate_row(bad)


def test_compile_verified_must_be_true():
    row = build_author_row(brief="Place an order.", dcl_text=CAP, vocab_reference=VOCAB, split="train")
    row["metadata"]["compile_verified"] = False
    with pytest.raises(RowValidationError):
        validate_row(row)
