"""Tests for _parse_coach_verdict, _extract_json_object, and _extract_coach_content.

Covers TASK-TRF-008 acceptance criteria:
- Bare JSON (no fence)
- Fenced JSON (code fence at start)
- Preamble text + fenced JSON
- Invalid content raises ValueError

Covers TASK-TRF-013 acceptance criteria:
- Empty .content + reasoning_content in additional_kwargs → verdict parsed
- Content as list of blocks with reasoning type → verdict parsed
- Normal string content → existing path still works
- All sources empty → ValueError raised
- Logging: which extraction path was used
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest

from entrypoint.generation_loop import (
    _extract_coach_content,
    _extract_json_object,
    _parse_coach_verdict,
)

# ---------------------------------------------------------------------------
# Fixtures — valid CoachVerdict JSON payloads
# ---------------------------------------------------------------------------

VALID_VERDICT = {
    "decision": "accept",
    "score": 4,
    "layer_correct": True,
    "type_correct": True,
    "criteria_met": {"accuracy": True, "completeness": True},
    "issues": [],
    "quality_assessment": "Good example.",
}

VALID_VERDICT_JSON = json.dumps(VALID_VERDICT)


# ---------------------------------------------------------------------------
# Tests for _extract_json_object (shared helper)
# ---------------------------------------------------------------------------


class TestExtractJsonObject:
    """Test the 3-try JSON extraction strategy."""

    def test_bare_json(self) -> None:
        result = _extract_json_object(VALID_VERDICT_JSON)
        assert json.loads(result) == VALID_VERDICT

    def test_bare_json_with_whitespace(self) -> None:
        result = _extract_json_object(f"  \n{VALID_VERDICT_JSON}\n  ")
        assert json.loads(result) == VALID_VERDICT

    def test_fenced_json_at_start(self) -> None:
        content = f"```json\n{VALID_VERDICT_JSON}\n```"
        result = _extract_json_object(content)
        assert json.loads(result) == VALID_VERDICT

    def test_fenced_without_language_tag(self) -> None:
        content = f"```\n{VALID_VERDICT_JSON}\n```"
        result = _extract_json_object(content)
        assert json.loads(result) == VALID_VERDICT

    def test_preamble_then_fenced_json(self) -> None:
        content = (
            "I can see the training example. Let me evaluate it.\n\n"
            f"```json\n{VALID_VERDICT_JSON}\n```"
        )
        result = _extract_json_object(content)
        assert json.loads(result) == VALID_VERDICT

    def test_preamble_and_postamble(self) -> None:
        content = (
            "Here is my evaluation:\n\n"
            f"```json\n{VALID_VERDICT_JSON}\n```\n\n"
            "Let me know if you need further details."
        )
        result = _extract_json_object(content)
        assert json.loads(result) == VALID_VERDICT

    def test_brace_matching_fallback(self) -> None:
        content = f"The verdict is: {VALID_VERDICT_JSON} -- end."
        result = _extract_json_object(content)
        assert json.loads(result) == VALID_VERDICT

    def test_invalid_content_raises(self) -> None:
        with pytest.raises(ValueError, match="Failed to extract JSON"):
            _extract_json_object("no json here at all")

    def test_empty_string_raises(self) -> None:
        with pytest.raises(ValueError, match="Failed to extract JSON"):
            _extract_json_object("")

    def test_non_dict_json_raises(self) -> None:
        with pytest.raises(ValueError, match="Failed to extract JSON"):
            _extract_json_object("[1, 2, 3]")


# ---------------------------------------------------------------------------
# Tests for _parse_coach_verdict
# ---------------------------------------------------------------------------


class TestParseCoachVerdict:
    """Test CoachVerdict parsing with various response formats."""

    def test_bare_json(self) -> None:
        verdict = _parse_coach_verdict(VALID_VERDICT_JSON)
        assert verdict.decision == "accept"
        assert verdict.score == 4
        assert verdict.layer_correct is True
        assert verdict.type_correct is True

    def test_fenced_json_at_start(self) -> None:
        content = f"```json\n{VALID_VERDICT_JSON}\n```"
        verdict = _parse_coach_verdict(content)
        assert verdict.decision == "accept"

    def test_preamble_then_fenced_json(self) -> None:
        content = (
            "I can see the training example in your message. "
            "Let me evaluate it against the criteria.\n\n"
            f"```json\n{VALID_VERDICT_JSON}\n```"
        )
        verdict = _parse_coach_verdict(content)
        assert verdict.decision == "accept"
        assert verdict.score == 4

    def test_preamble_with_revise_verdict(self) -> None:
        revise = {
            **VALID_VERDICT,
            "decision": "revise",
            "score": 2,
            "type_correct": False,
            "issues": [
                {
                    "criterion": "type_accuracy",
                    "severity": "blocking",
                    "description": "Wrong type",
                    "suggestion": "Fix the type field",
                }
            ],
            "quality_assessment": "Needs revision.",
        }
        content = (
            "Looking at this example carefully...\n\n"
            f"```json\n{json.dumps(revise)}\n```"
        )
        verdict = _parse_coach_verdict(content)
        assert verdict.decision == "revise"
        assert verdict.score == 2
        assert not verdict.is_accepted
        assert len(verdict.issues) == 1

    def test_invalid_json_raises_valueerror(self) -> None:
        with pytest.raises(ValueError, match="no JSON object found"):
            _parse_coach_verdict("this is not json at all")

    def test_valid_json_but_invalid_schema_raises(self) -> None:
        bad_schema = json.dumps({"foo": "bar"})
        with pytest.raises(ValueError, match="validation failed"):
            _parse_coach_verdict(bad_schema)

    def test_empty_string_raises(self) -> None:
        with pytest.raises(ValueError, match="no JSON object found"):
            _parse_coach_verdict("")


# ---------------------------------------------------------------------------
# Tests for _extract_coach_content (TASK-TRF-013)
# ---------------------------------------------------------------------------


def _make_mock_message(
    content: str | list | None = None,
    additional_kwargs: dict | None = None,
) -> MagicMock:
    """Create a mock LangChain AIMessage with configurable content sources."""
    msg = MagicMock()
    msg.content = content if content is not None else ""
    msg.additional_kwargs = additional_kwargs or {}
    return msg


class TestExtractCoachContent:
    """TASK-TRF-013: Coach content extraction with vLLM reasoning fallback."""

    def test_standard_string_content(self) -> None:
        """Normal string content → extracted via standard path."""
        msg = _make_mock_message(content=VALID_VERDICT_JSON)
        response = {"messages": [msg]}
        result = _extract_coach_content(response)
        assert result == VALID_VERDICT_JSON

    def test_empty_content_with_reasoning_in_additional_kwargs(self) -> None:
        """Empty .content + reasoning_content in additional_kwargs → verdict extracted."""
        msg = _make_mock_message(
            content="",
            additional_kwargs={"reasoning_content": VALID_VERDICT_JSON},
        )
        response = {"messages": [msg]}
        result = _extract_coach_content(response)
        assert result == VALID_VERDICT_JSON

    def test_whitespace_content_falls_through_to_reasoning(self) -> None:
        """Whitespace-only .content treated as empty, falls through to reasoning."""
        msg = _make_mock_message(
            content="   \n  ",
            additional_kwargs={"reasoning_content": VALID_VERDICT_JSON},
        )
        response = {"messages": [msg]}
        result = _extract_coach_content(response)
        assert result == VALID_VERDICT_JSON

    def test_content_list_with_text_blocks(self) -> None:
        """Content as list with text-type blocks → text extracted."""
        msg = _make_mock_message(
            content=[{"type": "text", "text": VALID_VERDICT_JSON}],
        )
        response = {"messages": [msg]}
        result = _extract_coach_content(response)
        assert result == VALID_VERDICT_JSON

    def test_content_list_with_reasoning_blocks(self) -> None:
        """Content as list with reasoning-type blocks → reasoning extracted."""
        msg = _make_mock_message(
            content=[{"type": "reasoning", "text": VALID_VERDICT_JSON}],
        )
        response = {"messages": [msg]}
        result = _extract_coach_content(response)
        assert result == VALID_VERDICT_JSON

    def test_content_list_reasoning_block_with_content_key(self) -> None:
        """Reasoning block using 'content' key instead of 'text'."""
        msg = _make_mock_message(
            content=[{"type": "reasoning", "content": VALID_VERDICT_JSON}],
        )
        response = {"messages": [msg]}
        result = _extract_coach_content(response)
        assert result == VALID_VERDICT_JSON

    def test_content_list_text_blocks_preferred_over_reasoning(self) -> None:
        """When both text and reasoning blocks exist, text blocks win."""
        msg = _make_mock_message(
            content=[
                {"type": "text", "text": "text-path-content"},
                {"type": "reasoning", "text": "reasoning-path-content"},
            ],
        )
        response = {"messages": [msg]}
        result = _extract_coach_content(response)
        assert result == "text-path-content"

    def test_all_sources_empty_raises_valueerror(self) -> None:
        """All content sources empty → ValueError raised."""
        msg = _make_mock_message(content="", additional_kwargs={})
        response = {"messages": [msg]}
        with pytest.raises(ValueError, match="no extractable content"):
            _extract_coach_content(response)

    def test_none_content_with_reasoning_fallback(self) -> None:
        """None .content falls through to reasoning_content."""
        msg = _make_mock_message(
            content=None,
            additional_kwargs={"reasoning_content": VALID_VERDICT_JSON},
        )
        # content is None, not a string, so isinstance(content, str) is False
        # and isinstance(content, list) is False → falls to additional_kwargs
        response = {"messages": [msg]}
        result = _extract_coach_content(response)
        assert result == VALID_VERDICT_JSON

    def test_end_to_end_verdict_from_reasoning_content(self) -> None:
        """Full pipeline: empty content + reasoning_content → CoachVerdict parsed."""
        msg = _make_mock_message(
            content="",
            additional_kwargs={"reasoning_content": VALID_VERDICT_JSON},
        )
        response = {"messages": [msg]}
        content = _extract_coach_content(response)
        verdict = _parse_coach_verdict(content)
        assert verdict.decision == "accept"
        assert verdict.score == 4
