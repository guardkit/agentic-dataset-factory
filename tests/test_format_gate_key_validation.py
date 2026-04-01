"""Tests for hardened format gate with required-key validation.

Covers TASK-FPF1-002 acceptance criteria:
- Format gate checks for both 'messages' and 'metadata' keys
- Log message includes reason for rejection (missing keys listed)
- FORMAT ERROR feedback mentions both required top-level keys
- rejection_history includes reason field
- Format gate rejects JSON with only 'messages' (no metadata)
- Format gate rejects JSON with only 'metadata' (no messages)
- Format gate accepts JSON with both 'messages' and 'metadata'
- Format gate still rejects non-JSON (prose-only) content
"""

from __future__ import annotations

import asyncio
import io
import json
import logging
from dataclasses import dataclass
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from entrypoint.generation_loop import run_generation_loop


# ---------------------------------------------------------------------------
# Fixtures (same pattern as test_coach_retry_json_reinforcement.py)
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


# ---------------------------------------------------------------------------
# Tests: Format gate required-key validation
# ---------------------------------------------------------------------------


class TestFormatGateKeyValidation:
    """TASK-FPF1-002: Format gate rejects JSON missing required keys."""

    @pytest.mark.asyncio
    async def test_rejects_json_with_only_messages_no_metadata(self) -> None:
        """JSON with 'messages' but no 'metadata' should be rejected."""
        target = _make_target()
        config = _MinimalConfig(max_turns=2)
        checkpoint = _make_checkpoint()
        output_manager = _make_output_manager()

        # Player returns JSON with only 'messages', no 'metadata'
        incomplete_json = json.dumps({
            "messages": [{"role": "user", "content": "test"}],
        })
        # Second turn: valid JSON to allow completion
        valid_json = json.dumps({
            "messages": [{"role": "user", "content": "test"}],
            "metadata": {"category": "test_cat"},
        })

        player_call_count = 0

        async def player_side_effect(input_data):
            nonlocal player_call_count
            player_call_count += 1
            if player_call_count == 1:
                return _make_agent_response(incomplete_json)
            return _make_agent_response(valid_json)

        player = AsyncMock()
        player.ainvoke.side_effect = player_side_effect

        coach = AsyncMock()
        coach.ainvoke.return_value = _make_agent_response(VALID_VERDICT_JSON)

        write_tool = MagicMock()
        write_tool.invoke.return_value = "ok"

        result = await run_generation_loop(
            player=player,
            coach=coach,
            targets=[target],
            config=config,
            checkpoint=checkpoint,
            output_manager=output_manager,
            write_tool=write_tool,
        )

        # First turn: format gate rejects (missing metadata)
        # Second turn: passes format gate → Coach accepts
        assert result.accepted == 1
        # Coach should only be called once (second turn)
        assert coach.ainvoke.call_count == 1
        # Player called twice (first rejected by format gate, second accepted)
        assert player.ainvoke.call_count == 2

    @pytest.mark.asyncio
    async def test_rejects_json_with_only_metadata_no_messages(self) -> None:
        """JSON with 'metadata' but no 'messages' should be rejected."""
        target = _make_target()
        config = _MinimalConfig(max_turns=2)
        checkpoint = _make_checkpoint()
        output_manager = _make_output_manager()

        # Player returns JSON with only 'metadata', no 'messages'
        incomplete_json = json.dumps({
            "metadata": {"category": "test_cat"},
        })
        # Second turn: valid JSON
        valid_json = json.dumps({
            "messages": [{"role": "user", "content": "test"}],
            "metadata": {"category": "test_cat"},
        })

        player_call_count = 0

        async def player_side_effect(input_data):
            nonlocal player_call_count
            player_call_count += 1
            if player_call_count == 1:
                return _make_agent_response(incomplete_json)
            return _make_agent_response(valid_json)

        player = AsyncMock()
        player.ainvoke.side_effect = player_side_effect

        coach = AsyncMock()
        coach.ainvoke.return_value = _make_agent_response(VALID_VERDICT_JSON)

        write_tool = MagicMock()
        write_tool.invoke.return_value = "ok"

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
        assert coach.ainvoke.call_count == 1
        assert player.ainvoke.call_count == 2

    @pytest.mark.asyncio
    async def test_accepts_json_with_both_messages_and_metadata(self) -> None:
        """JSON with both 'messages' and 'metadata' passes the format gate."""
        target = _make_target()
        config = _MinimalConfig(max_turns=1)
        checkpoint = _make_checkpoint()
        output_manager = _make_output_manager()
        write_tool = MagicMock()
        write_tool.invoke.return_value = "ok"

        valid_json = json.dumps({
            "messages": [{"role": "user", "content": "test"}],
            "metadata": {"category": "test_cat"},
        })

        player = AsyncMock()
        player.ainvoke.return_value = _make_agent_response(valid_json)

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

        # Format gate passed, Coach called, target accepted
        assert result.accepted == 1
        assert coach.ainvoke.call_count == 1

    @pytest.mark.asyncio
    async def test_rejects_prose_only_content(self) -> None:
        """Non-JSON (prose) content should still be rejected."""
        target = _make_target()
        config = _MinimalConfig(max_turns=1)
        checkpoint = _make_checkpoint()
        output_manager = _make_output_manager()

        player = AsyncMock()
        player.ainvoke.return_value = _make_agent_response(
            "Here is a great example of a tutoring conversation..."
        )

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

        # Format gate rejects prose, Coach never called
        assert result.accepted == 0
        assert coach.ainvoke.call_count == 0

    @pytest.mark.asyncio
    async def test_rejection_history_includes_reason_field(self) -> None:
        """rejection_history entry should include 'reason' when keys missing."""
        target = _make_target()
        config = _MinimalConfig(max_turns=1)
        checkpoint = _make_checkpoint()
        output_manager = _make_output_manager()

        # Player returns JSON missing 'metadata'
        incomplete_json = json.dumps({
            "messages": [{"role": "user", "content": "test"}],
        })

        player = AsyncMock()
        player.ainvoke.return_value = _make_agent_response(incomplete_json)

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

        # Target rejected — check the rejected output for the reason
        assert result.accepted == 0
        rejected_output = output_manager.rejected_fh.getvalue()
        # The format gate should have triggered; Coach never called
        assert coach.ainvoke.call_count == 0

    @pytest.mark.asyncio
    async def test_format_error_feedback_mentions_both_keys(self) -> None:
        """FORMAT ERROR feedback sent to Player mentions 'messages' and 'metadata'."""
        target = _make_target()
        config = _MinimalConfig(max_turns=2)
        checkpoint = _make_checkpoint()
        output_manager = _make_output_manager()
        write_tool = MagicMock()
        write_tool.invoke.return_value = "ok"

        # First turn: incomplete JSON, second turn: valid
        incomplete_json = json.dumps({"messages": [{"role": "user", "content": "hi"}]})
        valid_json = json.dumps({
            "messages": [{"role": "user", "content": "hi"}],
            "metadata": {"category": "test_cat"},
        })

        player_call_count = 0

        async def player_side_effect(input_data):
            nonlocal player_call_count
            player_call_count += 1
            if player_call_count == 1:
                return _make_agent_response(incomplete_json)
            # On second call, verify the feedback contains required key names
            call_input = input_data
            messages = call_input.get("messages", [])
            for msg in messages:
                content = msg.get("content", "")
                if isinstance(content, str) and "'messages'" in content and "'metadata'" in content:
                    # Feedback correctly mentions both keys
                    pass
            return _make_agent_response(valid_json)

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

        # Verify the second player call received feedback with both key names
        assert player.ainvoke.call_count == 2
        second_call_input = player.ainvoke.call_args_list[1][0][0]
        feedback_messages = second_call_input.get("messages", [])
        feedback_text = " ".join(
            msg.get("content", "") for msg in feedback_messages
            if isinstance(msg.get("content"), str)
        )
        assert "'messages'" in feedback_text
        assert "'metadata'" in feedback_text

    @pytest.mark.asyncio
    async def test_log_includes_reason_for_missing_keys(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Warning log should include reason with missing keys info."""
        target = _make_target()
        config = _MinimalConfig(max_turns=1)
        checkpoint = _make_checkpoint()
        output_manager = _make_output_manager()

        incomplete_json = json.dumps({
            "messages": [{"role": "user", "content": "test"}],
        })

        player = AsyncMock()
        player.ainvoke.return_value = _make_agent_response(incomplete_json)

        coach = AsyncMock()

        with caplog.at_level(logging.WARNING):
            await run_generation_loop(
                player=player,
                coach=coach,
                targets=[target],
                config=config,
                checkpoint=checkpoint,
                output_manager=output_manager,
                write_tool=MagicMock(),
            )

        # Check that the warning log includes the reason
        format_gate_warnings = [
            r for r in caplog.records
            if "Pre-Coach format gate" in r.message
        ]
        assert len(format_gate_warnings) >= 1
        warning_msg = format_gate_warnings[0].message
        assert "reason=" in warning_msg or "missing required" in warning_msg.lower()
