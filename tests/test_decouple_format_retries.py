"""Tests for decoupled format correction retries (TASK-FPF1-003).

Verifies that format gate failures do not consume the Coach turn budget.

Acceptance criteria:
- Target with format failures followed by Coach acceptance = accepted (not rejected)
- Format retries do NOT increment coach_turn counter
- Format retries bounded by configurable max_format_retries
- Exceeding max_format_retries causes target rejection
- Coach turns remain bounded by config.max_turns
- Write validation failures still count against the coach turn budget
- Post-gen validation failures still count against the coach turn budget
- turn reporting correct for mixed format/coach scenarios
"""

from __future__ import annotations

import asyncio
import io
import json
import logging
from dataclasses import dataclass
from unittest.mock import AsyncMock, MagicMock

import pytest

from entrypoint.generation_loop import run_generation_loop


# ---------------------------------------------------------------------------
# Shared fixtures
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

REVISE_VERDICT = {
    "decision": "revise",
    "score": 2,
    "layer_correct": True,
    "type_correct": True,
    "criteria_met": {"accuracy": False, "completeness": False},
    "issues": [],
    "quality_assessment": "Needs work.",
}

REVISE_VERDICT_JSON = json.dumps(REVISE_VERDICT)


@dataclass
class _MinimalConfig:
    """Minimal config stub for run_generation_loop (TASK-FPF1-003)."""

    max_turns: int = 3
    max_write_attempts: int = 3
    max_format_retries: int = 3
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


def _valid_example_json() -> str:
    return json.dumps({
        "messages": [{"role": "user", "content": "Hello"}],
        "metadata": {"category": "test_cat"},
    })


def _invalid_json_prose() -> str:
    return "Here is a great tutoring conversation..."


def _invalid_json_missing_metadata() -> str:
    return json.dumps({"messages": [{"role": "user", "content": "Hi"}]})


# ---------------------------------------------------------------------------
# Core decoupling tests
# ---------------------------------------------------------------------------


class TestFormatRetriesDecoupledFromTurnBudget:
    """TASK-FPF1-003: Format gate failures must not consume the Coach turn budget."""

    @pytest.mark.asyncio
    async def test_two_format_failures_then_accept_is_accepted(self) -> None:
        """Target with 2 format failures then 1 Coach acceptance = accepted.

        With the old for-loop (max_turns=3), 2 format failures leave only 1
        Coach turn, which could accept. But this test ensures the new while-loop
        still works: 2 format retries + 1 coach_turn <= max_turns budget.
        """
        target = _make_target()
        # max_turns=1 means we only allow 1 real Coach evaluation.
        # The 2 format failures must NOT consume this budget.
        config = _MinimalConfig(max_turns=1, max_format_retries=3)
        checkpoint = _make_checkpoint()
        output_manager = _make_output_manager()
        write_tool = MagicMock()
        write_tool.invoke.return_value = "ok"

        player_call_count = 0

        async def player_side_effect(input_data):
            nonlocal player_call_count
            player_call_count += 1
            if player_call_count <= 2:
                # First two invocations: prose (fails format gate)
                return _make_agent_response(_invalid_json_prose())
            # Third invocation: valid JSON
            return _make_agent_response(_valid_example_json())

        player = AsyncMock()
        player.ainvoke.side_effect = player_side_effect

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

        # Should be accepted: 2 format retries + 1 coach acceptance
        assert result.accepted == 1, (
            "Target should be accepted: format retries don't consume turn budget"
        )
        assert result.rejected == 0
        # Player called 3 times (2 format failures + 1 success)
        assert player.ainvoke.call_count == 3
        # Coach called once (only the valid pass)
        assert coach.ainvoke.call_count == 1

    @pytest.mark.asyncio
    async def test_format_retries_do_not_decrement_coach_budget(self) -> None:
        """Format gate failures must leave the full coach turn budget available.

        Even with max_turns=1, format failures should not block the one Coach eval.
        """
        target = _make_target()
        config = _MinimalConfig(max_turns=1, max_format_retries=5)
        checkpoint = _make_checkpoint()
        output_manager = _make_output_manager()
        write_tool = MagicMock()
        write_tool.invoke.return_value = "ok"

        call_count = 0

        async def player_side_effect(_input):
            nonlocal call_count
            call_count += 1
            if call_count < 5:
                return _make_agent_response(_invalid_json_missing_metadata())
            return _make_agent_response(_valid_example_json())

        player = AsyncMock()
        player.ainvoke.side_effect = player_side_effect

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
        # 4 format failures + 1 coach turn = 5 total invocations
        assert player.ainvoke.call_count == 5
        assert coach.ainvoke.call_count == 1

    @pytest.mark.asyncio
    async def test_coach_receives_full_three_turns_despite_format_failures(
        self,
    ) -> None:
        """Coach still gets max_turns=3 evaluations even after format failures."""
        target = _make_target()
        config = _MinimalConfig(max_turns=3, max_format_retries=10)
        checkpoint = _make_checkpoint()
        output_manager = _make_output_manager()
        write_tool = MagicMock()
        write_tool.invoke.return_value = "ok"

        # Pattern: 2 format failures, then revise, then revise, then accept
        # = 2 format retries + 3 coach turns
        call_count = 0

        async def player_side_effect(_input):
            nonlocal call_count
            call_count += 1
            if call_count <= 2:
                return _make_agent_response(_invalid_json_prose())
            return _make_agent_response(_valid_example_json())

        player = AsyncMock()
        player.ainvoke.side_effect = player_side_effect

        coach_call_count = 0

        async def coach_side_effect(_input):
            nonlocal coach_call_count
            coach_call_count += 1
            if coach_call_count < 3:
                return _make_agent_response(REVISE_VERDICT_JSON)
            return _make_agent_response(VALID_VERDICT_JSON)

        coach = AsyncMock()
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

        # Accepted after 3 Coach evaluations (2 revise + 1 accept)
        assert result.accepted == 1
        assert coach.ainvoke.call_count == 3
        # 2 format failures + 3 coach turns = 5 total player invocations
        assert player.ainvoke.call_count == 5


# ---------------------------------------------------------------------------
# max_format_retries exhaustion tests
# ---------------------------------------------------------------------------


class TestMaxFormatRetriesExhaustion:
    """TASK-FPF1-003: max_format_retries exceeded causes target rejection."""

    @pytest.mark.asyncio
    async def test_exceeding_max_format_retries_rejects_target(self) -> None:
        """Target rejected when format gate fires more than max_format_retries times."""
        target = _make_target()
        # max_format_retries=2 means we allow 2 format failures; the 3rd breaks
        config = _MinimalConfig(max_turns=3, max_format_retries=2)
        checkpoint = _make_checkpoint()
        output_manager = _make_output_manager()

        # Player always returns prose (will never pass format gate)
        player = AsyncMock()
        player.ainvoke.return_value = _make_agent_response(_invalid_json_prose())

        coach = AsyncMock()

        result = await run_generation_loop(
            player=player,
            coach=coach,
            targets=[target],
            config=config,
            checkpoint=checkpoint,
            output_manager=output_manager,
            write_tool=MagicMock(),
        )

        assert result.rejected == 1
        assert result.accepted == 0
        # Coach never called (format gate always fired)
        assert coach.ainvoke.call_count == 0
        # Player called max_format_retries + 1 times (the extra call triggers the break)
        assert player.ainvoke.call_count == 3  # 2 retries allowed + 1 that exceeded

    @pytest.mark.asyncio
    async def test_max_format_retries_zero_rejects_on_first_failure(self) -> None:
        """With max_format_retries=0, the first format failure causes rejection."""
        target = _make_target()
        config = _MinimalConfig(max_turns=3, max_format_retries=0)
        checkpoint = _make_checkpoint()
        output_manager = _make_output_manager()

        player = AsyncMock()
        player.ainvoke.return_value = _make_agent_response(_invalid_json_prose())

        coach = AsyncMock()

        result = await run_generation_loop(
            player=player,
            coach=coach,
            targets=[target],
            config=config,
            checkpoint=checkpoint,
            output_manager=output_manager,
            write_tool=MagicMock(),
        )

        assert result.rejected == 1
        assert result.accepted == 0
        # Player called once (first failure exceeds max_format_retries=0)
        assert player.ainvoke.call_count == 1
        assert coach.ainvoke.call_count == 0

    @pytest.mark.asyncio
    async def test_format_retries_not_shared_across_targets(self) -> None:
        """Format retry counter resets between targets."""
        # Two targets: each has 2 format failures then success
        # max_format_retries=2 means 2 failures are allowed per target
        target1 = _make_target("cat_a")
        target2 = _make_target("cat_b")
        config = _MinimalConfig(max_turns=1, max_format_retries=2)
        checkpoint = _make_checkpoint()
        output_manager = _make_output_manager()
        write_tool = MagicMock()
        write_tool.invoke.return_value = "ok"

        total_player_calls = 0

        async def player_side_effect(_input):
            nonlocal total_player_calls
            total_player_calls += 1
            # Calls 1-2 (target 1 format failures), 3 (target 1 success),
            # calls 4-5 (target 2 format failures), 6 (target 2 success)
            if total_player_calls in (1, 2, 4, 5):
                return _make_agent_response(_invalid_json_prose())
            return _make_agent_response(_valid_example_json())

        player = AsyncMock()
        player.ainvoke.side_effect = player_side_effect

        coach = AsyncMock()
        coach.ainvoke.return_value = _make_agent_response(VALID_VERDICT_JSON)

        result = await run_generation_loop(
            player=player,
            coach=coach,
            targets=[target1, target2],
            config=config,
            checkpoint=checkpoint,
            output_manager=output_manager,
            write_tool=write_tool,
        )

        # Both targets accepted
        assert result.accepted == 2
        assert result.rejected == 0
        # 6 total player calls: 3 per target (2 format + 1 success)
        assert player.ainvoke.call_count == 6
        # 2 coach calls: one per target
        assert coach.ainvoke.call_count == 2


# ---------------------------------------------------------------------------
# Turn count reporting tests
# ---------------------------------------------------------------------------


class TestTurnCountReporting:
    """TASK-FPF1-003: turn count reporting in logs and return values."""

    @pytest.mark.asyncio
    async def test_total_turns_includes_format_retries(self) -> None:
        """GenerationResult.total_turns includes all Player invocations."""
        target = _make_target()
        config = _MinimalConfig(max_turns=1, max_format_retries=3)
        checkpoint = _make_checkpoint()
        output_manager = _make_output_manager()
        write_tool = MagicMock()
        write_tool.invoke.return_value = "ok"

        call_count = 0

        async def player_side_effect(_input):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return _make_agent_response(_invalid_json_prose())
            return _make_agent_response(_valid_example_json())

        player = AsyncMock()
        player.ainvoke.side_effect = player_side_effect

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
        # total_turns should reflect 2 Player invocations (1 format + 1 coach)
        assert result.total_turns == 2

    @pytest.mark.asyncio
    async def test_target_accepted_log_includes_coach_turns_and_invocations(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """target_accepted log includes both coach_turns and total_invocations."""
        target = _make_target()
        config = _MinimalConfig(max_turns=1, max_format_retries=3)
        checkpoint = _make_checkpoint()
        output_manager = _make_output_manager()
        write_tool = MagicMock()
        write_tool.invoke.return_value = "ok"

        call_count = 0

        async def player_side_effect(_input):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return _make_agent_response(_invalid_json_prose())
            return _make_agent_response(_valid_example_json())

        player = AsyncMock()
        player.ainvoke.side_effect = player_side_effect

        coach = AsyncMock()
        coach.ainvoke.return_value = _make_agent_response(VALID_VERDICT_JSON)

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

        accepted_logs = [
            r for r in caplog.records if "target_accepted" in r.message
        ]
        assert len(accepted_logs) == 1
        msg = accepted_logs[0].message
        assert "coach_turns=" in msg
        assert "total_invocations=" in msg

    @pytest.mark.asyncio
    async def test_format_gate_log_uses_total_invocations(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Pre-Coach format gate warning uses total_invocations for turn number."""
        target = _make_target()
        config = _MinimalConfig(max_turns=1, max_format_retries=3)
        checkpoint = _make_checkpoint()
        output_manager = _make_output_manager()

        call_count = 0

        async def player_side_effect(_input):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return _make_agent_response(_invalid_json_prose())
            return _make_agent_response(_valid_example_json())

        player = AsyncMock()
        player.ainvoke.side_effect = player_side_effect

        coach = AsyncMock()
        coach.ainvoke.return_value = _make_agent_response(VALID_VERDICT_JSON)

        write_tool = MagicMock()
        write_tool.invoke.return_value = "ok"

        with caplog.at_level(logging.WARNING, logger="entrypoint.generation_loop"):
            await run_generation_loop(
                player=player,
                coach=coach,
                targets=[target],
                config=config,
                checkpoint=checkpoint,
                output_manager=output_manager,
                write_tool=write_tool,
            )

        format_gate_logs = [
            r for r in caplog.records if "Pre-Coach format gate" in r.message
        ]
        assert len(format_gate_logs) == 1
        # turn=1 (first invocation) logged correctly
        assert "turn=1" in format_gate_logs[0].message


# ---------------------------------------------------------------------------
# Boundary: write/post-gen validation failures still count as coach turns
# ---------------------------------------------------------------------------


class TestWriteAndPostGenValidationStillConsumeCoachTurns:
    """Write validation and post-gen validation failures consume the coach budget."""

    @pytest.mark.asyncio
    async def test_write_failure_after_format_retry_counts_as_coach_turn(
        self,
    ) -> None:
        """Write validation failure still counts against coach_turn budget."""
        target = _make_target()
        # max_turns=1: only one Coach evaluation allowed.
        # Write failure should cause rejection (not retry another coach turn).
        config = _MinimalConfig(
            max_turns=1, max_write_attempts=1, max_format_retries=3
        )
        checkpoint = _make_checkpoint()
        output_manager = _make_output_manager()

        call_count = 0

        async def player_side_effect(_input):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return _make_agent_response(_invalid_json_prose())
            return _make_agent_response(_valid_example_json())

        player = AsyncMock()
        player.ainvoke.side_effect = player_side_effect

        coach = AsyncMock()
        coach.ainvoke.return_value = _make_agent_response(VALID_VERDICT_JSON)

        # Write tool always fails
        write_tool = MagicMock()
        write_tool.invoke.return_value = "Error: schema validation failed"

        result = await run_generation_loop(
            player=player,
            coach=coach,
            targets=[target],
            config=config,
            checkpoint=checkpoint,
            output_manager=output_manager,
            write_tool=write_tool,
        )

        # Rejected: write failure exhausted max_write_attempts
        assert result.rejected == 1
        assert result.accepted == 0
        # Coach was called once (the format retry didn't consume its turn)
        assert coach.ainvoke.call_count == 1
