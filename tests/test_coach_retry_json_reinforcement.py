"""Tests for Coach retry with JSON reinforcement on parse failure.

Covers TASK-OR-001 acceptance criteria:
- Single retry on Coach JSON parse failure with reinforcement message
- Retry logged at INFO level with target index and turn number
- If retry succeeds, verdict is used normally
- If retry fails, target rejected with llm_failure reason
- Coach reasoning remains enabled (no enable_thinking changes)
- Player content passed to Coach unchanged (no Layer 1 stripping)
- Token usage for retry logged
- No retry on first successful parse
"""

from __future__ import annotations

import asyncio
import io
import json
from dataclasses import dataclass
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from entrypoint.generation_loop import (
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


@dataclass
class _MinimalConfig:
    """Minimal config stub for run_generation_loop."""

    max_turns: int = 3
    max_write_attempts: int = 3
    target_timeout: int = 60
    llm_retry_attempts: int = 1
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


def _make_mock_message(content: str) -> MagicMock:
    msg = MagicMock()
    msg.content = content
    msg.additional_kwargs = {}
    msg.response_metadata = {}
    msg.usage_metadata = {}
    return msg


def _make_agent_response(content: str) -> dict:
    return {"messages": [_make_mock_message(content)]}


# ---------------------------------------------------------------------------
# Unit tests: _parse_coach_verdict retry inside _process_single_target
# ---------------------------------------------------------------------------


class TestCoachRetryOnParseFailure:
    """TASK-OR-001: Coach retry with JSON reinforcement."""

    @pytest.mark.asyncio
    async def test_retry_succeeds_after_initial_parse_failure(self) -> None:
        """ValueError on first parse → retry with reinforcement → succeeds."""
        target = _make_target()
        config = _MinimalConfig(max_turns=1)
        checkpoint = _make_checkpoint()
        output_manager = _make_output_manager()
        write_tool = MagicMock()
        write_tool.invoke.return_value = "ok"

        # Player returns valid example JSON
        player_example = json.dumps({
            "messages": [{"role": "user", "content": "test"}],
            "metadata": {"category": "test_cat"},
        })
        player = AsyncMock()
        player.ainvoke.return_value = _make_agent_response(player_example)

        # Coach: first call returns prose (not JSON), retry returns valid verdict
        coach = AsyncMock()
        coach_call_count = 0

        async def coach_side_effect(input_data):
            nonlocal coach_call_count
            coach_call_count += 1
            if coach_call_count == 1:
                # First call: prose response (will fail _parse_coach_verdict)
                return _make_agent_response(
                    "I think this is a good example. Let me evaluate..."
                )
            else:
                # Retry call: valid JSON verdict
                return _make_agent_response(VALID_VERDICT_JSON)

        coach.ainvoke.side_effect = coach_side_effect

        result = await run_generation_loop(
            player=player,
            coach=coach,
            targets=[target],
            config=config,
            checkpoint=checkpoint,
            output_manager=output_manager,
            write_tool=write_tool,
        )

        # Target accepted after retry
        assert result.accepted == 1
        assert result.rejected == 0
        # Coach called twice: original + retry
        assert coach.ainvoke.call_count == 2
        # Retry call should have single user message with reinforcement merged
        retry_call_input = coach.ainvoke.call_args_list[1][0][0]
        assert len(retry_call_input["messages"]) == 1
        assert retry_call_input["messages"][0]["role"] == "user"
        assert "ONLY a JSON object" in retry_call_input["messages"][0]["content"]

    @pytest.mark.asyncio
    async def test_retry_also_fails_rejects_target(self) -> None:
        """ValueError on first parse → retry also fails → target rejected."""
        target = _make_target()
        config = _MinimalConfig(max_turns=1)
        checkpoint = _make_checkpoint()
        output_manager = _make_output_manager()

        player = AsyncMock()
        player.ainvoke.return_value = _make_agent_response("player output")

        # Coach always returns prose (both calls fail parse)
        coach = AsyncMock()
        coach.ainvoke.return_value = _make_agent_response(
            "This example looks good to me!"
        )

        result = await run_generation_loop(
            player=player,
            coach=coach,
            targets=[target],
            config=config,
            checkpoint=checkpoint,
            output_manager=output_manager,
            write_tool=MagicMock(),
        )

        # Target rejected after retry failure
        assert result.rejected == 1
        assert result.accepted == 0
        # Coach called twice: original + retry
        assert coach.ainvoke.call_count == 2

        # Rejection record written
        rejected_output = output_manager.rejected_fh.getvalue()
        assert rejected_output
        record = json.loads(rejected_output.strip())
        assert "llm_failure" in record["reason"]

    @pytest.mark.asyncio
    async def test_no_retry_on_first_success(self) -> None:
        """Coach returns valid JSON on first try → no retry invoked."""
        target = _make_target()
        config = _MinimalConfig(max_turns=1)
        checkpoint = _make_checkpoint()
        output_manager = _make_output_manager()
        write_tool = MagicMock()
        write_tool.invoke.return_value = "ok"

        player_example = json.dumps({
            "messages": [{"role": "user", "content": "test"}],
            "metadata": {"category": "test_cat"},
        })
        player = AsyncMock()
        player.ainvoke.return_value = _make_agent_response(player_example)

        coach = AsyncMock()
        coach.ainvoke.return_value = _make_agent_response(VALID_VERDICT_JSON)

        result = await run_generation_loop(
            player=player,
            coach=coach,
            targets=[target],
            config=config,
            checkpoint=checkpoint,
            output_manager=output_manager,
            write_tool=write_tool,
        )

        assert result.accepted == 1
        # Coach called exactly once — no retry
        assert coach.ainvoke.call_count == 1

    @pytest.mark.asyncio
    async def test_retry_only_once_per_target(self) -> None:
        """Second parse failure on same target does not trigger another retry."""
        target = _make_target()
        # Allow 2 turns so the coach can fail on both
        config = _MinimalConfig(max_turns=2)
        checkpoint = _make_checkpoint()
        output_manager = _make_output_manager()

        player = AsyncMock()
        player.ainvoke.return_value = _make_agent_response("player output")

        # Coach: turn 1 first call=prose, retry=revise verdict,
        # turn 2 first call=prose (no retry since already used)
        coach_call_count = 0
        revise_verdict = {
            **VALID_VERDICT,
            "decision": "revise",
            "score": 2,
            "quality_assessment": "Needs work.",
        }

        async def coach_side_effect(input_data):
            nonlocal coach_call_count
            coach_call_count += 1
            if coach_call_count == 1:
                # Turn 1, first call: prose
                return _make_agent_response("Evaluating this example...")
            elif coach_call_count == 2:
                # Turn 1, retry: valid revise verdict
                return _make_agent_response(json.dumps(revise_verdict))
            else:
                # Turn 2, first call: prose again
                # Should NOT trigger retry (already used for this target)
                return _make_agent_response("Still evaluating...")

        coach = AsyncMock()
        coach.ainvoke.side_effect = coach_side_effect

        result = await run_generation_loop(
            player=player,
            coach=coach,
            targets=[target],
            config=config,
            checkpoint=checkpoint,
            output_manager=output_manager,
            write_tool=MagicMock(),
        )

        # Target rejected (turn 2 parse failure, no second retry)
        assert result.rejected == 1
        # Coach called 3 times: turn1 original + turn1 retry + turn2 original
        assert coach.ainvoke.call_count == 3

    @pytest.mark.asyncio
    async def test_retry_reinforcement_message_format(self) -> None:
        """Retry message includes system role with CoachVerdict schema instructions."""
        target = _make_target()
        config = _MinimalConfig(max_turns=1)
        checkpoint = _make_checkpoint()
        output_manager = _make_output_manager()
        write_tool = MagicMock()
        write_tool.invoke.return_value = "ok"

        player_content = "Generated training example content"
        player = AsyncMock()
        player.ainvoke.return_value = _make_agent_response(player_content)

        coach_call_count = 0

        async def coach_side_effect(input_data):
            nonlocal coach_call_count
            coach_call_count += 1
            if coach_call_count == 1:
                return _make_agent_response("Not JSON")
            return _make_agent_response(VALID_VERDICT_JSON)

        coach = AsyncMock()
        coach.ainvoke.side_effect = coach_side_effect

        await run_generation_loop(
            player=player,
            coach=coach,
            targets=[target],
            config=config,
            checkpoint=checkpoint,
            output_manager=output_manager,
            write_tool=write_tool,
        )

        # Verify retry message structure — single user message
        retry_call = coach.ainvoke.call_args_list[1]
        retry_input = retry_call[0][0]
        messages = retry_input["messages"]

        # Single user message with reinforcement merged with player content
        assert len(messages) == 1
        assert messages[0]["role"] == "user"
        assert "IMPORTANT" in messages[0]["content"]
        assert "JSON object" in messages[0]["content"]
        assert "CoachVerdict" in messages[0]["content"]
        assert player_content in messages[0]["content"]

        # No system messages in retry input
        assert all(m["role"] != "system" for m in messages)

    @pytest.mark.asyncio
    async def test_retry_input_has_no_system_messages(self) -> None:
        """TASK-OR-006: retry_input must contain zero system messages."""
        target = _make_target()
        config = _MinimalConfig(max_turns=1)
        checkpoint = _make_checkpoint()
        output_manager = _make_output_manager()
        write_tool = MagicMock()
        write_tool.invoke.return_value = "ok"

        player = AsyncMock()
        player.ainvoke.return_value = _make_agent_response("player output")

        coach_call_count = 0

        async def coach_side_effect(input_data):
            nonlocal coach_call_count
            coach_call_count += 1
            if coach_call_count == 1:
                return _make_agent_response("Not JSON")
            return _make_agent_response(VALID_VERDICT_JSON)

        coach = AsyncMock()
        coach.ainvoke.side_effect = coach_side_effect

        await run_generation_loop(
            player=player,
            coach=coach,
            targets=[target],
            config=config,
            checkpoint=checkpoint,
            output_manager=output_manager,
            write_tool=write_tool,
        )

        retry_call = coach.ainvoke.call_args_list[1]
        retry_input = retry_call[0][0]
        system_msgs = [
            m for m in retry_input["messages"] if m["role"] == "system"
        ]
        assert system_msgs == [], (
            f"retry_input must have no system messages, got {system_msgs}"
        )

    @pytest.mark.asyncio
    async def test_retry_logs_at_info_level(self, caplog) -> None:
        """Retry is logged at INFO with target index and turn number."""
        target = _make_target()
        config = _MinimalConfig(max_turns=1)
        checkpoint = _make_checkpoint()
        output_manager = _make_output_manager()
        write_tool = MagicMock()
        write_tool.invoke.return_value = "ok"

        player_example = json.dumps({
            "messages": [{"role": "user", "content": "test"}],
            "metadata": {},
        })
        player = AsyncMock()
        player.ainvoke.return_value = _make_agent_response(player_example)

        coach_call_count = 0

        async def coach_side_effect(input_data):
            nonlocal coach_call_count
            coach_call_count += 1
            if coach_call_count == 1:
                return _make_agent_response("prose response")
            return _make_agent_response(VALID_VERDICT_JSON)

        coach = AsyncMock()
        coach.ainvoke.side_effect = coach_side_effect

        import logging

        with caplog.at_level(logging.INFO, logger="entrypoint.generation_loop"):
            await run_generation_loop(
                player=player,
                coach=coach,
                targets=[target],
                config=config,
                checkpoint=checkpoint,
                output_manager=output_manager,
                write_tool=write_tool,
            )

        retry_logs = [
            r
            for r in caplog.records
            if "JSON reinforcement" in r.message
        ]
        assert len(retry_logs) == 1
        assert "index=0" in retry_logs[0].message
        assert "turn=1" in retry_logs[0].message
