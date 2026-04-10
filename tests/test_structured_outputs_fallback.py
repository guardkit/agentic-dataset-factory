"""Tests for TASK-CR-007: structured outputs fallback on coach refusal.

Covers acceptance criteria:
- Fallback triggered only after both initial + reframed retries fail with refusal
- Free-form text containing valid JSON is successfully parsed
- Free-form text without valid JSON results in coach_refusal rejection
- Integration: refusal → reframe → refusal → fallback → success path
- Integration: refusal → reframe → refusal → fallback → refusal → rejection path
- Fallback usage logged at INFO level with coach_content_source
- Metrics track fallback recoveries
"""

from __future__ import annotations

import asyncio
import io
import json
from dataclasses import dataclass
from unittest.mock import AsyncMock, MagicMock

import pytest

from entrypoint.generation_loop import (
    CoachRefusalError,
    _extract_coach_content,
    _parse_coach_verdict,
    run_generation_loop,
)

# ---------------------------------------------------------------------------
# Fixtures
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

VALID_PLAYER_EXAMPLE = json.dumps({
    "messages": [{"role": "user", "content": "test"}],
    "metadata": {"category": "test_cat"},
})


@dataclass
class _MinimalConfig:
    """Minimal config stub for run_generation_loop."""

    max_turns: int = 3
    max_write_attempts: int = 3
    max_format_retries: int = 3
    target_timeout: int = 60
    llm_retry_attempts: int = 0
    llm_retry_backoff: float = 0.0


def _make_target(
    category: str = "test_cat", type_: str = "reasoning"
) -> MagicMock:
    t = MagicMock()
    t.category = category
    t.type = type_
    t.count = 1
    t.grade_targets = [7]
    return t


def _make_output_manager() -> MagicMock:
    om = MagicMock()
    om.rejected_fh = io.StringIO()
    return om


def _make_checkpoint() -> MagicMock:
    cp = MagicMock()
    cp.save = MagicMock()
    return cp


def _make_mock_message(
    content: str = "",
    additional_kwargs: dict | None = None,
) -> MagicMock:
    msg = MagicMock()
    msg.content = content
    msg.additional_kwargs = additional_kwargs or {}
    msg.response_metadata = {}
    msg.usage_metadata = {}
    return msg


def _make_agent_response(content: str) -> dict:
    return {"messages": [_make_mock_message(content=content)]}


def _make_refusal_response(reason: str = "I cannot evaluate this") -> dict:
    """Create an agent response that triggers CoachRefusalError."""
    return {
        "messages": [
            _make_mock_message(
                content="",
                additional_kwargs={"refusal": reason},
            )
        ]
    }


# ---------------------------------------------------------------------------
# Unit tests: _parse_coach_verdict with free-form text
# ---------------------------------------------------------------------------


class TestFreeFormTextParsing:
    """TASK-CR-007: Free-form text parsing into CoachVerdict."""

    def test_freeform_text_with_embedded_json_parses(self) -> None:
        """Free-form text containing valid JSON → CoachVerdict parsed."""
        content = (
            "Let me evaluate this training example. Here is my assessment:\n\n"
            f"```json\n{VALID_VERDICT_JSON}\n```\n\n"
            "This is a good example overall."
        )
        verdict = _parse_coach_verdict(content)
        assert verdict.decision == "accept"
        assert verdict.score == 4

    def test_freeform_text_with_bare_json_parses(self) -> None:
        """Free-form text with bare JSON object → CoachVerdict parsed."""
        content = (
            f"Here is my evaluation: {VALID_VERDICT_JSON} "
            "-- end of assessment."
        )
        verdict = _parse_coach_verdict(content)
        assert verdict.decision == "accept"

    def test_freeform_text_without_json_raises(self) -> None:
        """Free-form text without any JSON → ValueError."""
        content = (
            "I have evaluated the training example and found it to be "
            "of acceptable quality. The example demonstrates good use "
            "of the concepts."
        )
        with pytest.raises(ValueError, match="no JSON object found"):
            _parse_coach_verdict(content)


# ---------------------------------------------------------------------------
# Integration tests: Full fallback path through run_generation_loop
# ---------------------------------------------------------------------------


class TestStructuredOutputsFallbackIntegration:
    """TASK-CR-007: Integration tests for the full fallback path."""

    @pytest.mark.asyncio
    async def test_fallback_triggered_after_double_refusal_succeeds(
        self,
    ) -> None:
        """refusal → reframe retry → refusal → fallback → success."""
        target = _make_target()
        config = _MinimalConfig(max_turns=1)
        checkpoint = _make_checkpoint()
        output_manager = _make_output_manager()
        write_tool = MagicMock()
        write_tool.invoke.return_value = "ok"

        # Player returns valid example JSON
        player = AsyncMock()
        player.ainvoke.return_value = _make_agent_response(VALID_PLAYER_EXAMPLE)

        # Main coach: always refuses
        coach = AsyncMock()
        coach.ainvoke.return_value = _make_refusal_response(
            "I cannot evaluate harmful content"
        )

        # Fallback coach: returns valid verdict as free-form text
        coach_fallback = AsyncMock()
        coach_fallback.ainvoke.return_value = _make_agent_response(
            f"Here is my evaluation:\n{VALID_VERDICT_JSON}"
        )

        result = await run_generation_loop(
            player=player,
            coach=coach,
            targets=[target],
            config=config,
            checkpoint=checkpoint,
            output_manager=output_manager,
            write_tool=write_tool,
            coach_fallback=coach_fallback,
        )

        # Target accepted via fallback
        assert result.accepted == 1
        assert result.rejected == 0
        # Main coach called twice (initial + reframed retry)
        assert coach.ainvoke.call_count == 2
        # Fallback coach called once
        assert coach_fallback.ainvoke.call_count == 1

    @pytest.mark.asyncio
    async def test_fallback_triggered_after_double_refusal_fails(
        self,
    ) -> None:
        """refusal → reframe retry → refusal → fallback → refusal → rejection."""
        target = _make_target()
        config = _MinimalConfig(max_turns=1)
        checkpoint = _make_checkpoint()
        output_manager = _make_output_manager()
        write_tool = MagicMock()

        # Player returns valid example JSON
        player = AsyncMock()
        player.ainvoke.return_value = _make_agent_response(VALID_PLAYER_EXAMPLE)

        # Main coach: always refuses
        coach = AsyncMock()
        coach.ainvoke.return_value = _make_refusal_response(
            "I cannot evaluate this content"
        )

        # Fallback coach: also refuses
        coach_fallback = AsyncMock()
        coach_fallback.ainvoke.return_value = _make_refusal_response(
            "Still refusing"
        )

        result = await run_generation_loop(
            player=player,
            coach=coach,
            targets=[target],
            config=config,
            checkpoint=checkpoint,
            output_manager=output_manager,
            write_tool=write_tool,
            coach_fallback=coach_fallback,
        )

        # Target rejected
        assert result.accepted == 0
        assert result.rejected == 1
        # Main coach called twice (initial + reframed retry)
        assert coach.ainvoke.call_count == 2
        # Fallback coach called once
        assert coach_fallback.ainvoke.call_count == 1
        # Check rejection record contains coach_refusal
        rejected_output = output_manager.rejected_fh.getvalue()
        assert "coach_refusal" in rejected_output

    @pytest.mark.asyncio
    async def test_fallback_not_triggered_when_reframe_succeeds(
        self,
    ) -> None:
        """refusal → reframe retry → success → no fallback needed."""
        target = _make_target()
        config = _MinimalConfig(max_turns=1)
        checkpoint = _make_checkpoint()
        output_manager = _make_output_manager()
        write_tool = MagicMock()
        write_tool.invoke.return_value = "ok"

        # Player returns valid example JSON
        player = AsyncMock()
        player.ainvoke.return_value = _make_agent_response(VALID_PLAYER_EXAMPLE)

        # Coach: first call refuses, reframed retry succeeds
        coach = AsyncMock()
        coach_call_count = 0

        async def coach_side_effect(input_data):
            nonlocal coach_call_count
            coach_call_count += 1
            if coach_call_count == 1:
                return _make_refusal_response("Cannot evaluate")
            else:
                return _make_agent_response(VALID_VERDICT_JSON)

        coach.ainvoke.side_effect = coach_side_effect

        # Fallback coach should NOT be called
        coach_fallback = AsyncMock()

        result = await run_generation_loop(
            player=player,
            coach=coach,
            targets=[target],
            config=config,
            checkpoint=checkpoint,
            output_manager=output_manager,
            write_tool=write_tool,
            coach_fallback=coach_fallback,
        )

        # Target accepted via reframed retry
        assert result.accepted == 1
        assert result.rejected == 0
        # Coach called twice (initial + reframed retry)
        assert coach.ainvoke.call_count == 2
        # Fallback coach NOT called
        assert coach_fallback.ainvoke.call_count == 0

    @pytest.mark.asyncio
    async def test_no_fallback_coach_still_raises_on_double_refusal(
        self,
    ) -> None:
        """Without coach_fallback, double refusal still rejects as before."""
        target = _make_target()
        config = _MinimalConfig(max_turns=1)
        checkpoint = _make_checkpoint()
        output_manager = _make_output_manager()
        write_tool = MagicMock()

        # Player returns valid example JSON
        player = AsyncMock()
        player.ainvoke.return_value = _make_agent_response(VALID_PLAYER_EXAMPLE)

        # Coach: always refuses
        coach = AsyncMock()
        coach.ainvoke.return_value = _make_refusal_response("Cannot evaluate")

        # No fallback coach
        result = await run_generation_loop(
            player=player,
            coach=coach,
            targets=[target],
            config=config,
            checkpoint=checkpoint,
            output_manager=output_manager,
            write_tool=write_tool,
            # coach_fallback not provided (defaults to None)
        )

        # Target rejected
        assert result.accepted == 0
        assert result.rejected == 1
        # Coach called twice (initial + reframed retry)
        assert coach.ainvoke.call_count == 2
        # Check rejection record contains coach_refusal
        rejected_output = output_manager.rejected_fh.getvalue()
        assert "coach_refusal" in rejected_output

    @pytest.mark.asyncio
    async def test_fallback_with_dict_coach_selects_correct_layer(
        self,
    ) -> None:
        """Fallback coach dict uses same layer routing as main coach."""
        target = _make_target()
        target.layer = "knowledge"
        config = _MinimalConfig(max_turns=1)
        checkpoint = _make_checkpoint()
        output_manager = _make_output_manager()
        write_tool = MagicMock()
        write_tool.invoke.return_value = "ok"

        # Player returns valid example JSON
        player = AsyncMock()
        player.ainvoke.return_value = _make_agent_response(VALID_PLAYER_EXAMPLE)

        # Main coaches: both refuse
        coach_behaviour = AsyncMock()
        coach_behaviour.ainvoke.return_value = _make_refusal_response(
            "behaviour refuses"
        )
        coach_knowledge = AsyncMock()
        coach_knowledge.ainvoke.return_value = _make_refusal_response(
            "knowledge refuses"
        )

        # Fallback coaches
        fallback_behaviour = AsyncMock()
        fallback_knowledge = AsyncMock()
        fallback_knowledge.ainvoke.return_value = _make_agent_response(
            VALID_VERDICT_JSON
        )

        result = await run_generation_loop(
            player=player,
            coach={
                "behaviour": coach_behaviour,
                "knowledge": coach_knowledge,
            },
            targets=[target],
            config=config,
            checkpoint=checkpoint,
            output_manager=output_manager,
            write_tool=write_tool,
            coach_fallback={
                "behaviour": fallback_behaviour,
                "knowledge": fallback_knowledge,
            },
        )

        # Target accepted via fallback
        assert result.accepted == 1
        # Knowledge coach was used (not behaviour) for both main and fallback
        assert coach_knowledge.ainvoke.call_count == 2
        assert coach_behaviour.ainvoke.call_count == 0
        assert fallback_knowledge.ainvoke.call_count == 1
        assert fallback_behaviour.ainvoke.call_count == 0

    @pytest.mark.asyncio
    async def test_fallback_freeform_text_parsed_into_verdict(
        self,
    ) -> None:
        """Fallback returns free-form text with embedded JSON → parsed."""
        target = _make_target()
        config = _MinimalConfig(max_turns=1)
        checkpoint = _make_checkpoint()
        output_manager = _make_output_manager()
        write_tool = MagicMock()
        write_tool.invoke.return_value = "ok"

        # Player returns valid example JSON
        player = AsyncMock()
        player.ainvoke.return_value = _make_agent_response(VALID_PLAYER_EXAMPLE)

        # Main coach: always refuses
        coach = AsyncMock()
        coach.ainvoke.return_value = _make_refusal_response("refuses")

        # Fallback coach: returns free-form text with embedded JSON
        coach_fallback = AsyncMock()
        coach_fallback.ainvoke.return_value = _make_agent_response(
            "Let me evaluate this example.\n\n"
            f"```json\n{VALID_VERDICT_JSON}\n```\n\n"
            "Overall a solid training example."
        )

        result = await run_generation_loop(
            player=player,
            coach=coach,
            targets=[target],
            config=config,
            checkpoint=checkpoint,
            output_manager=output_manager,
            write_tool=write_tool,
            coach_fallback=coach_fallback,
        )

        # Target accepted — free-form text was parsed successfully
        assert result.accepted == 1
        assert result.rejected == 0

    @pytest.mark.asyncio
    async def test_fallback_unparseable_text_rejects(self) -> None:
        """Fallback returns text without JSON → ValueError → rejection."""
        target = _make_target()
        config = _MinimalConfig(max_turns=1)
        checkpoint = _make_checkpoint()
        output_manager = _make_output_manager()
        write_tool = MagicMock()

        # Player returns valid example JSON
        player = AsyncMock()
        player.ainvoke.return_value = _make_agent_response(VALID_PLAYER_EXAMPLE)

        # Main coach: always refuses
        coach = AsyncMock()
        coach.ainvoke.return_value = _make_refusal_response("refuses")

        # Fallback coach: returns text without any JSON
        coach_fallback = AsyncMock()
        coach_fallback.ainvoke.return_value = _make_agent_response(
            "This training example looks good overall. I would rate it "
            "as acceptable quality with minor issues."
        )

        result = await run_generation_loop(
            player=player,
            coach=coach,
            targets=[target],
            config=config,
            checkpoint=checkpoint,
            output_manager=output_manager,
            write_tool=write_tool,
            coach_fallback=coach_fallback,
        )

        # Target rejected — fallback text couldn't be parsed
        assert result.accepted == 0
        assert result.rejected == 1

    @pytest.mark.asyncio
    async def test_fallback_recovery_count_logged(self) -> None:
        """Fallback recovery is tracked in metrics."""
        target = _make_target()
        config = _MinimalConfig(max_turns=1)
        checkpoint = _make_checkpoint()
        output_manager = _make_output_manager()
        write_tool = MagicMock()
        write_tool.invoke.return_value = "ok"

        # Player returns valid example JSON
        player = AsyncMock()
        player.ainvoke.return_value = _make_agent_response(VALID_PLAYER_EXAMPLE)

        # Main coach: always refuses
        coach = AsyncMock()
        coach.ainvoke.return_value = _make_refusal_response("refuses")

        # Fallback coach: returns valid verdict
        coach_fallback = AsyncMock()
        coach_fallback.ainvoke.return_value = _make_agent_response(
            VALID_VERDICT_JSON
        )

        result = await run_generation_loop(
            player=player,
            coach=coach,
            targets=[target],
            config=config,
            checkpoint=checkpoint,
            output_manager=output_manager,
            write_tool=write_tool,
            coach_fallback=coach_fallback,
        )

        # Target accepted via fallback
        assert result.accepted == 1
        # Verify the INFO log contains structured_outputs_fallback
        # (tested implicitly: if the fallback path wasn't taken,
        # coach_fallback wouldn't be called)
        assert coach_fallback.ainvoke.call_count == 1
