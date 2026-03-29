"""Tests for entrypoint.generation_loop — Player-Coach adversarial generation cycle.

Covers all acceptance criteria for TASK-EP-007 and TASK-TRF-005:
- AC-001: Sequential target processing (one at a time per ADR-ARCH-006)
- AC-002: Player-Coach cycle with up to max_turns revisions
- AC-003: max_turns=1 gives exactly one attempt
- AC-004: Rejected targets logged to rejected.jsonl with rejection history
- AC-005: Per-target timeout discards and continues
- AC-006: Transient LLM failures retried with backoff
- AC-007: All retries exhausted: target discarded, pipeline continues
- AC-008: Checkpoint written after each target
- AC-009: Structured JSON progress logging at key milestones
- AC-010: GenerationResult returned with statistics
- AC-011: All modified files pass lint/format checks
- TRF-005-001: Player response → Coach accepts → orchestrator writes
- TRF-005-002: Player response → Coach rejects → no write occurs
- TRF-005-003: Coach accepts but write_output validation fails → treated as rejection
- TRF-005-004: JSON extraction from Player response (code fences, raw JSON)
"""

from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from config.coach_verdict import CoachVerdict, Issue
from config.models import GenerationConfig
from domain_config.models import GenerationTarget


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_target(category: str = "Literary analysis", type_: str = "reasoning",
                 count: int = 1) -> GenerationTarget:
    """Create a GenerationTarget for testing."""
    return GenerationTarget(category=category, type=type_, count=count)


def _make_accept_verdict() -> CoachVerdict:
    """Create an accepting CoachVerdict."""
    return CoachVerdict(
        decision="accept",
        score=4,
        layer_correct=True,
        type_correct=True,
        criteria_met={"accuracy": True},
        issues=[],
        quality_assessment="Good example",
    )


def _make_reject_verdict(reason: str = "Needs improvement") -> CoachVerdict:
    """Create a rejecting CoachVerdict."""
    return CoachVerdict(
        decision="revise",
        score=2,
        layer_correct=True,
        type_correct=True,
        criteria_met={"accuracy": False},
        issues=[
            Issue(
                criterion="accuracy",
                severity="blocking",
                description=reason,
                suggestion="Fix it",
            )
        ],
        quality_assessment=reason,
    )


def _make_generation_config(**overrides: Any) -> GenerationConfig:
    """Create a GenerationConfig with optional overrides."""
    defaults = {
        "max_turns": 3,
        "llm_retry_attempts": 3,
        "llm_retry_backoff": 2.0,
        "llm_timeout": 300,
        "target_timeout": 600,
    }
    defaults.update(overrides)
    return GenerationConfig(**defaults)


def _make_mock_player(responses: list[str] | None = None) -> MagicMock:
    """Create a mock Player DeepAgent.

    The mock simulates DeepAgent.ainvoke() returning a dict with
    ``messages`` containing the agent's response.
    """
    player = AsyncMock()
    if responses is None:
        responses = ['{"messages": [], "metadata": {"layer": "behaviour"}}']

    side_effects = []
    for resp in responses:
        side_effects.append({"messages": [MagicMock(content=resp)]})
    player.ainvoke.side_effect = side_effects
    return player


def _make_mock_coach(verdicts: list[CoachVerdict] | None = None) -> MagicMock:
    """Create a mock Coach DeepAgent returning structured verdicts."""
    coach = AsyncMock()
    if verdicts is None:
        verdicts = [_make_accept_verdict()]

    side_effects = []
    for v in verdicts:
        side_effects.append({"messages": [MagicMock(content=v.model_dump_json())]})
    coach.ainvoke.side_effect = side_effects
    return coach


def _make_mock_write_tool(return_value: str = "Written to output/train.jsonl (example #1)") -> MagicMock:
    """Create a mock write_output tool for the orchestrator."""
    write_tool = MagicMock()
    write_tool.invoke.return_value = return_value
    return write_tool


# Valid JSON example that the Player would return
_VALID_EXAMPLE_JSON = json.dumps({
    "messages": [
        {"role": "system", "content": "You are a tutor."},
        {"role": "user", "content": "What is a metaphor?"},
        {"role": "assistant", "content": "A metaphor is a figure of speech."},
    ],
    "metadata": {
        "layer": "behaviour",
        "type": "direct",
    },
})


# ---------------------------------------------------------------------------
# AC-001: Sequential target processing (one at a time per ADR-ARCH-006)
# ---------------------------------------------------------------------------


class TestSequentialTargetProcessing:
    """AC-001: Targets are processed one at a time, sequentially."""

    @pytest.mark.asyncio
    async def test_targets_processed_in_order(self, tmp_path: Path) -> None:
        """Each target is processed sequentially, not concurrently."""
        from entrypoint.generation_loop import run_generation_loop

        targets = [_make_target(category=f"Cat-{i}") for i in range(3)]
        config = _make_generation_config(max_turns=1, target_timeout=60)

        # Track order of player invocations
        invocation_order: list[int] = []
        call_count = 0

        async def track_invocation(*args: Any, **kwargs: Any) -> dict:
            nonlocal call_count
            idx = call_count
            call_count += 1
            invocation_order.append(idx)
            return {"messages": [MagicMock(content=_VALID_EXAMPLE_JSON)]}

        player = AsyncMock()
        player.ainvoke.side_effect = track_invocation

        coach = _make_mock_coach([_make_accept_verdict()] * 3)
        checkpoint = MagicMock()
        output_mgr = MagicMock()
        output_mgr.rejected_fh = MagicMock()
        write_tool = _make_mock_write_tool()

        await run_generation_loop(
            player=player,
            coach=coach,
            targets=targets,
            config=config,
            checkpoint=checkpoint,
            output_manager=output_mgr,
            write_tool=write_tool,
            start_index=0,
        )

        assert invocation_order == [0, 1, 2]

    @pytest.mark.asyncio
    async def test_all_targets_are_processed(self, tmp_path: Path) -> None:
        """All targets in the list are processed."""
        from entrypoint.generation_loop import run_generation_loop

        targets = [_make_target(category=f"Cat-{i}") for i in range(5)]
        config = _make_generation_config(max_turns=1, target_timeout=60)

        player = AsyncMock()
        player.ainvoke.return_value = {"messages": [MagicMock(content=_VALID_EXAMPLE_JSON)]}
        coach = _make_mock_coach([_make_accept_verdict()] * 5)
        checkpoint = MagicMock()
        output_mgr = MagicMock()
        output_mgr.rejected_fh = MagicMock()
        write_tool = _make_mock_write_tool()

        result = await run_generation_loop(
            player=player,
            coach=coach,
            targets=targets,
            config=config,
            checkpoint=checkpoint,
            output_manager=output_mgr,
            write_tool=write_tool,
            start_index=0,
        )

        assert result.total_targets == 5


# ---------------------------------------------------------------------------
# AC-002: Player-Coach cycle with up to max_turns revisions
# ---------------------------------------------------------------------------


class TestPlayerCoachCycle:
    """AC-002: Player-Coach cycle with up to max_turns revisions."""

    @pytest.mark.asyncio
    async def test_accepted_on_first_turn(self, tmp_path: Path) -> None:
        """BDD: Generation loop processes a target — accepted on first turn."""
        from entrypoint.generation_loop import run_generation_loop

        targets = [_make_target()]
        config = _make_generation_config(max_turns=3, target_timeout=60)

        player = AsyncMock()
        player.ainvoke.return_value = {"messages": [MagicMock(content=_VALID_EXAMPLE_JSON)]}
        coach = _make_mock_coach([_make_accept_verdict()])
        checkpoint = MagicMock()
        output_mgr = MagicMock()
        output_mgr.rejected_fh = MagicMock()
        write_tool = _make_mock_write_tool()

        result = await run_generation_loop(
            player=player,
            coach=coach,
            targets=targets,
            config=config,
            checkpoint=checkpoint,
            output_manager=output_mgr,
            write_tool=write_tool,
            start_index=0,
        )

        assert result.accepted == 1
        assert result.rejected == 0

    @pytest.mark.asyncio
    async def test_accepted_after_revision(self, tmp_path: Path) -> None:
        """Player revises after rejection, accepted on second turn."""
        from entrypoint.generation_loop import run_generation_loop

        targets = [_make_target()]
        config = _make_generation_config(max_turns=3, target_timeout=60)

        # Player called twice: first attempt + revision
        player = AsyncMock()
        player.ainvoke.return_value = {"messages": [MagicMock(content=_VALID_EXAMPLE_JSON)]}

        # Coach rejects first, accepts second
        coach = _make_mock_coach([_make_reject_verdict(), _make_accept_verdict()])
        checkpoint = MagicMock()
        output_mgr = MagicMock()
        output_mgr.rejected_fh = MagicMock()
        write_tool = _make_mock_write_tool()

        result = await run_generation_loop(
            player=player,
            coach=coach,
            targets=targets,
            config=config,
            checkpoint=checkpoint,
            output_manager=output_mgr,
            write_tool=write_tool,
            start_index=0,
        )

        assert result.accepted == 1
        assert result.rejected == 0
        assert result.total_turns >= 2


# ---------------------------------------------------------------------------
# AC-003: max_turns=1 gives exactly one attempt
# ---------------------------------------------------------------------------


class TestMaxTurnsOne:
    """AC-003: max_turns=1 gives exactly one attempt."""

    @pytest.mark.asyncio
    async def test_max_turns_one_accepted(self, tmp_path: Path) -> None:
        """BDD: Generation with max_turns set to 1 — accepted."""
        from entrypoint.generation_loop import run_generation_loop

        targets = [_make_target()]
        config = _make_generation_config(max_turns=1, target_timeout=60)

        player = AsyncMock()
        player.ainvoke.return_value = {"messages": [MagicMock(content=_VALID_EXAMPLE_JSON)]}
        coach = _make_mock_coach([_make_accept_verdict()])
        checkpoint = MagicMock()
        output_mgr = MagicMock()
        output_mgr.rejected_fh = MagicMock()
        write_tool = _make_mock_write_tool()

        result = await run_generation_loop(
            player=player,
            coach=coach,
            targets=targets,
            config=config,
            checkpoint=checkpoint,
            output_manager=output_mgr,
            write_tool=write_tool,
            start_index=0,
        )

        assert result.accepted == 1
        assert result.total_turns == 1

    @pytest.mark.asyncio
    async def test_max_turns_one_rejected(self, tmp_path: Path) -> None:
        """BDD: Generation with max_turns set to 1 — rejected after one attempt."""
        from entrypoint.generation_loop import run_generation_loop

        targets = [_make_target()]
        config = _make_generation_config(max_turns=1, target_timeout=60)

        player = AsyncMock()
        player.ainvoke.return_value = {"messages": [MagicMock(content=_VALID_EXAMPLE_JSON)]}
        coach = _make_mock_coach([_make_reject_verdict()])
        checkpoint = MagicMock()
        output_mgr = MagicMock()
        output_mgr.rejected_fh = MagicMock()
        write_tool = _make_mock_write_tool()

        result = await run_generation_loop(
            player=player,
            coach=coach,
            targets=targets,
            config=config,
            checkpoint=checkpoint,
            output_manager=output_mgr,
            write_tool=write_tool,
            start_index=0,
        )

        assert result.rejected == 1
        assert result.accepted == 0
        assert result.total_turns == 1
        # Player should only be invoked once
        assert player.ainvoke.call_count == 1


# ---------------------------------------------------------------------------
# AC-004: Rejected targets logged to rejected.jsonl with rejection history
# ---------------------------------------------------------------------------


class TestRejectedTargetLogging:
    """AC-004: Rejected targets logged to rejected.jsonl."""

    @pytest.mark.asyncio
    async def test_rejected_target_written_to_rejected_fh(self) -> None:
        """BDD: Target rejected after exhausting all turns."""
        from entrypoint.generation_loop import run_generation_loop

        targets = [_make_target()]
        config = _make_generation_config(max_turns=2, target_timeout=60)

        player = AsyncMock()
        player.ainvoke.return_value = {"messages": [MagicMock(content=_VALID_EXAMPLE_JSON)]}
        coach = _make_mock_coach([_make_reject_verdict("Bad"), _make_reject_verdict("Still bad")])
        checkpoint = MagicMock()
        output_mgr = MagicMock()
        rejected_lines: list[str] = []
        output_mgr.rejected_fh = MagicMock()
        output_mgr.rejected_fh.write = MagicMock(side_effect=lambda s: rejected_lines.append(s))
        write_tool = _make_mock_write_tool()

        await run_generation_loop(
            player=player,
            coach=coach,
            targets=targets,
            config=config,
            checkpoint=checkpoint,
            output_manager=output_mgr,
            write_tool=write_tool,
            start_index=0,
        )

        # At least one line written to rejected_fh
        assert len(rejected_lines) >= 1
        # Parse the rejection record
        record = json.loads(rejected_lines[0].strip())
        assert "rejection_history" in record

    @pytest.mark.asyncio
    async def test_rejection_history_contains_all_verdicts(self) -> None:
        """Rejection history includes Coach verdicts from all turns."""
        from entrypoint.generation_loop import run_generation_loop

        targets = [_make_target()]
        config = _make_generation_config(max_turns=3, target_timeout=60)

        player = AsyncMock()
        player.ainvoke.return_value = {"messages": [MagicMock(content=_VALID_EXAMPLE_JSON)]}
        verdicts = [_make_reject_verdict(f"Issue turn {i}") for i in range(3)]
        coach = _make_mock_coach(verdicts)
        checkpoint = MagicMock()
        output_mgr = MagicMock()
        rejected_lines: list[str] = []
        output_mgr.rejected_fh = MagicMock()
        output_mgr.rejected_fh.write = MagicMock(side_effect=lambda s: rejected_lines.append(s))
        write_tool = _make_mock_write_tool()

        await run_generation_loop(
            player=player,
            coach=coach,
            targets=targets,
            config=config,
            checkpoint=checkpoint,
            output_manager=output_mgr,
            write_tool=write_tool,
            start_index=0,
        )

        record = json.loads(rejected_lines[0].strip())
        assert len(record["rejection_history"]) == 3


# ---------------------------------------------------------------------------
# AC-005: Per-target timeout discards and continues
# ---------------------------------------------------------------------------


class TestPerTargetTimeout:
    """AC-005: Per-target timeout discards and continues."""

    @pytest.mark.asyncio
    async def test_timeout_target_is_rejected(self) -> None:
        """BDD: Target exceeding the per-target timeout."""
        from entrypoint.generation_loop import run_generation_loop

        targets = [_make_target(category="Slow"), _make_target(category="Fast")]
        config = _make_generation_config(max_turns=3, target_timeout=1)

        call_count = 0

        async def slow_then_fast(*args: Any, **kwargs: Any) -> dict:
            nonlocal call_count
            call_count += 1
            if call_count <= 1:
                # First target takes too long
                await asyncio.sleep(5)
            return {"messages": [MagicMock(content=_VALID_EXAMPLE_JSON)]}

        player = AsyncMock()
        player.ainvoke.side_effect = slow_then_fast
        coach = _make_mock_coach([_make_accept_verdict()] * 3)
        checkpoint = MagicMock()
        output_mgr = MagicMock()
        rejected_lines: list[str] = []
        output_mgr.rejected_fh = MagicMock()
        output_mgr.rejected_fh.write = MagicMock(side_effect=lambda s: rejected_lines.append(s))
        write_tool = _make_mock_write_tool()

        result = await run_generation_loop(
            player=player,
            coach=coach,
            targets=targets,
            config=config,
            checkpoint=checkpoint,
            output_manager=output_mgr,
            write_tool=write_tool,
            start_index=0,
        )

        # First target timed out → rejected, second accepted
        assert result.rejected >= 1
        # Pipeline continued to process the second target
        assert result.total_targets == 2
        # Timeout rejection logged
        assert len(rejected_lines) >= 1
        timeout_record = json.loads(rejected_lines[0].strip())
        assert timeout_record.get("reason") == "timeout"


# ---------------------------------------------------------------------------
# AC-006: Transient LLM failures retried with backoff
# ---------------------------------------------------------------------------


class TestTransientLLMRetry:
    """AC-006: Transient LLM failures retried with backoff."""

    @pytest.mark.asyncio
    async def test_transient_failure_retried(self) -> None:
        """BDD: Transient LLM failure is retried."""
        from entrypoint.generation_loop import run_generation_loop

        targets = [_make_target()]
        config = _make_generation_config(max_turns=1, target_timeout=30)

        call_count = 0

        async def fail_then_succeed(*args: Any, **kwargs: Any) -> dict:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise RuntimeError("Transient LLM error")
            return {"messages": [MagicMock(content=_VALID_EXAMPLE_JSON)]}

        player = AsyncMock()
        player.ainvoke.side_effect = fail_then_succeed
        coach = _make_mock_coach([_make_accept_verdict()])
        checkpoint = MagicMock()
        output_mgr = MagicMock()
        output_mgr.rejected_fh = MagicMock()
        write_tool = _make_mock_write_tool()

        result = await run_generation_loop(
            player=player,
            coach=coach,
            targets=targets,
            config=config,
            checkpoint=checkpoint,
            output_manager=output_mgr,
            write_tool=write_tool,
            start_index=0,
        )

        # Player was invoked more than once (retry happened)
        assert call_count >= 2
        assert result.accepted == 1


# ---------------------------------------------------------------------------
# AC-007: All retries exhausted: target discarded, pipeline continues
# ---------------------------------------------------------------------------


class TestRetriesExhausted:
    """AC-007: All retries exhausted: target discarded, pipeline continues."""

    @pytest.mark.asyncio
    async def test_all_retries_exhausted_continues(self) -> None:
        """BDD: All LLM retries exhausted."""
        from entrypoint.generation_loop import run_generation_loop

        targets = [_make_target(category="Failing"), _make_target(category="Working")]
        config = _make_generation_config(
            max_turns=1, target_timeout=30, llm_retry_attempts=2,
        )

        call_count = 0

        async def always_fail_then_succeed(*args: Any, **kwargs: Any) -> dict:
            nonlocal call_count
            call_count += 1
            # First 3 calls fail (1 original + 2 retries for first target)
            if call_count <= 3:
                raise RuntimeError("Persistent LLM error")
            return {"messages": [MagicMock(content=_VALID_EXAMPLE_JSON)]}

        player = AsyncMock()
        player.ainvoke.side_effect = always_fail_then_succeed
        coach = _make_mock_coach([_make_accept_verdict()] * 3)
        checkpoint = MagicMock()
        output_mgr = MagicMock()
        rejected_lines: list[str] = []
        output_mgr.rejected_fh = MagicMock()
        output_mgr.rejected_fh.write = MagicMock(side_effect=lambda s: rejected_lines.append(s))
        write_tool = _make_mock_write_tool()

        result = await run_generation_loop(
            player=player,
            coach=coach,
            targets=targets,
            config=config,
            checkpoint=checkpoint,
            output_manager=output_mgr,
            write_tool=write_tool,
            start_index=0,
        )

        # First target failed, second succeeded
        assert result.rejected >= 1
        assert result.total_targets == 2
        # Pipeline continued to second target
        assert result.accepted >= 1


# ---------------------------------------------------------------------------
# AC-008: Checkpoint written after each target
# ---------------------------------------------------------------------------


class TestCheckpointWrittenAfterTarget:
    """AC-008: Checkpoint written after each target."""

    @pytest.mark.asyncio
    async def test_checkpoint_saved_for_each_target(self) -> None:
        """Checkpoint.save() called after each target completion."""
        from entrypoint.generation_loop import run_generation_loop

        targets = [_make_target(category=f"Cat-{i}") for i in range(3)]
        config = _make_generation_config(max_turns=1, target_timeout=60)

        player = AsyncMock()
        player.ainvoke.return_value = {"messages": [MagicMock(content=_VALID_EXAMPLE_JSON)]}
        coach = _make_mock_coach([_make_accept_verdict()] * 3)
        checkpoint = MagicMock()
        output_mgr = MagicMock()
        output_mgr.rejected_fh = MagicMock()
        write_tool = _make_mock_write_tool()

        await run_generation_loop(
            player=player,
            coach=coach,
            targets=targets,
            config=config,
            checkpoint=checkpoint,
            output_manager=output_mgr,
            write_tool=write_tool,
            start_index=0,
        )

        # checkpoint.save() called 3 times with indices 0, 1, 2
        assert checkpoint.save.call_count == 3
        checkpoint.save.assert_any_call(0)
        checkpoint.save.assert_any_call(1)
        checkpoint.save.assert_any_call(2)


# ---------------------------------------------------------------------------
# AC-009: Structured JSON progress logging at key milestones
# ---------------------------------------------------------------------------


class TestProgressLogging:
    """AC-009: Structured JSON progress logging at key milestones."""

    @pytest.mark.asyncio
    async def test_target_start_logged(self, caplog: pytest.LogCaptureFixture) -> None:
        """Log 'target_start' at beginning of each target."""
        from entrypoint.generation_loop import run_generation_loop

        targets = [_make_target()]
        config = _make_generation_config(max_turns=1, target_timeout=60)

        player = AsyncMock()
        player.ainvoke.return_value = {"messages": [MagicMock(content=_VALID_EXAMPLE_JSON)]}
        coach = _make_mock_coach([_make_accept_verdict()])
        checkpoint = MagicMock()
        output_mgr = MagicMock()
        output_mgr.rejected_fh = MagicMock()
        write_tool = _make_mock_write_tool()

        with caplog.at_level(logging.INFO):
            await run_generation_loop(
                player=player,
                coach=coach,
                targets=targets,
                config=config,
                checkpoint=checkpoint,
                output_manager=output_mgr,
                write_tool=write_tool,
                start_index=0,
            )

        assert any("target_start" in msg for msg in caplog.messages)

    @pytest.mark.asyncio
    async def test_turn_complete_logged(self, caplog: pytest.LogCaptureFixture) -> None:
        """Log 'turn_complete' after each Player-Coach cycle."""
        from entrypoint.generation_loop import run_generation_loop

        targets = [_make_target()]
        config = _make_generation_config(max_turns=1, target_timeout=60)

        player = AsyncMock()
        player.ainvoke.return_value = {"messages": [MagicMock(content=_VALID_EXAMPLE_JSON)]}
        coach = _make_mock_coach([_make_accept_verdict()])
        checkpoint = MagicMock()
        output_mgr = MagicMock()
        output_mgr.rejected_fh = MagicMock()
        write_tool = _make_mock_write_tool()

        with caplog.at_level(logging.INFO):
            await run_generation_loop(
                player=player,
                coach=coach,
                targets=targets,
                config=config,
                checkpoint=checkpoint,
                output_manager=output_mgr,
                write_tool=write_tool,
                start_index=0,
            )

        assert any("turn_complete" in msg for msg in caplog.messages)

    @pytest.mark.asyncio
    async def test_target_accepted_logged(self, caplog: pytest.LogCaptureFixture) -> None:
        """Log 'target_accepted' when Coach accepts."""
        from entrypoint.generation_loop import run_generation_loop

        targets = [_make_target()]
        config = _make_generation_config(max_turns=1, target_timeout=60)

        player = AsyncMock()
        player.ainvoke.return_value = {"messages": [MagicMock(content=_VALID_EXAMPLE_JSON)]}
        coach = _make_mock_coach([_make_accept_verdict()])
        checkpoint = MagicMock()
        output_mgr = MagicMock()
        output_mgr.rejected_fh = MagicMock()
        write_tool = _make_mock_write_tool()

        with caplog.at_level(logging.INFO):
            await run_generation_loop(
                player=player,
                coach=coach,
                targets=targets,
                config=config,
                checkpoint=checkpoint,
                output_manager=output_mgr,
                write_tool=write_tool,
                start_index=0,
            )

        assert any("target_accepted" in msg for msg in caplog.messages)

    @pytest.mark.asyncio
    async def test_target_rejected_logged(self, caplog: pytest.LogCaptureFixture) -> None:
        """Log 'target_rejected' when target exhausts all turns."""
        from entrypoint.generation_loop import run_generation_loop

        targets = [_make_target()]
        config = _make_generation_config(max_turns=1, target_timeout=60)

        player = AsyncMock()
        player.ainvoke.return_value = {"messages": [MagicMock(content=_VALID_EXAMPLE_JSON)]}
        coach = _make_mock_coach([_make_reject_verdict()])
        checkpoint = MagicMock()
        output_mgr = MagicMock()
        output_mgr.rejected_fh = MagicMock()
        write_tool = _make_mock_write_tool()

        with caplog.at_level(logging.INFO):
            await run_generation_loop(
                player=player,
                coach=coach,
                targets=targets,
                config=config,
                checkpoint=checkpoint,
                output_manager=output_mgr,
                write_tool=write_tool,
                start_index=0,
            )

        assert any("target_rejected" in msg for msg in caplog.messages)

    @pytest.mark.asyncio
    async def test_complete_logged(self, caplog: pytest.LogCaptureFixture) -> None:
        """Log 'complete' at end of generation."""
        from entrypoint.generation_loop import run_generation_loop

        targets = [_make_target()]
        config = _make_generation_config(max_turns=1, target_timeout=60)

        player = AsyncMock()
        player.ainvoke.return_value = {"messages": [MagicMock(content=_VALID_EXAMPLE_JSON)]}
        coach = _make_mock_coach([_make_accept_verdict()])
        checkpoint = MagicMock()
        output_mgr = MagicMock()
        output_mgr.rejected_fh = MagicMock()
        write_tool = _make_mock_write_tool()

        with caplog.at_level(logging.INFO):
            await run_generation_loop(
                player=player,
                coach=coach,
                targets=targets,
                config=config,
                checkpoint=checkpoint,
                output_manager=output_mgr,
                write_tool=write_tool,
                start_index=0,
            )

        assert any("complete" in msg for msg in caplog.messages)


# ---------------------------------------------------------------------------
# AC-010: GenerationResult returned with statistics
# ---------------------------------------------------------------------------


class TestGenerationResult:
    """AC-010: GenerationResult returned with correct statistics."""

    @pytest.mark.asyncio
    async def test_result_has_all_fields(self) -> None:
        """GenerationResult dataclass has required fields."""
        from entrypoint.generation_loop import GenerationResult

        result = GenerationResult(
            total_targets=10,
            accepted=7,
            rejected=3,
            total_turns=20,
            elapsed_seconds=120.5,
        )
        assert result.total_targets == 10
        assert result.accepted == 7
        assert result.rejected == 3
        assert result.total_turns == 20
        assert result.elapsed_seconds == 120.5

    @pytest.mark.asyncio
    async def test_result_statistics_correct_mixed(self) -> None:
        """Statistics correct with mix of accepted and rejected targets."""
        from entrypoint.generation_loop import run_generation_loop

        targets = [_make_target(category=f"Cat-{i}") for i in range(3)]
        config = _make_generation_config(max_turns=1, target_timeout=60)

        player = AsyncMock()
        player.ainvoke.return_value = {"messages": [MagicMock(content=_VALID_EXAMPLE_JSON)]}
        # First two accepted, third rejected
        coach = _make_mock_coach([
            _make_accept_verdict(),
            _make_accept_verdict(),
            _make_reject_verdict(),
        ])
        checkpoint = MagicMock()
        output_mgr = MagicMock()
        output_mgr.rejected_fh = MagicMock()
        write_tool = _make_mock_write_tool()

        result = await run_generation_loop(
            player=player,
            coach=coach,
            targets=targets,
            config=config,
            checkpoint=checkpoint,
            output_manager=output_mgr,
            write_tool=write_tool,
            start_index=0,
        )

        assert result.total_targets == 3
        assert result.accepted == 2
        assert result.rejected == 1
        assert result.total_turns == 3
        assert result.elapsed_seconds > 0

    @pytest.mark.asyncio
    async def test_result_elapsed_seconds_positive(self) -> None:
        """elapsed_seconds is positive after running."""
        from entrypoint.generation_loop import run_generation_loop

        targets = [_make_target()]
        config = _make_generation_config(max_turns=1, target_timeout=60)

        player = AsyncMock()
        player.ainvoke.return_value = {"messages": [MagicMock(content=_VALID_EXAMPLE_JSON)]}
        coach = _make_mock_coach([_make_accept_verdict()])
        checkpoint = MagicMock()
        output_mgr = MagicMock()
        output_mgr.rejected_fh = MagicMock()
        write_tool = _make_mock_write_tool()

        result = await run_generation_loop(
            player=player,
            coach=coach,
            targets=targets,
            config=config,
            checkpoint=checkpoint,
            output_manager=output_mgr,
            write_tool=write_tool,
            start_index=0,
        )

        assert result.elapsed_seconds > 0


# ---------------------------------------------------------------------------
# Start index / resume support
# ---------------------------------------------------------------------------


class TestStartIndex:
    """Verify start_index skips already-processed targets."""

    @pytest.mark.asyncio
    async def test_start_index_skips_targets(self) -> None:
        """start_index=2 skips first two targets."""
        from entrypoint.generation_loop import run_generation_loop

        targets = [_make_target(category=f"Cat-{i}") for i in range(5)]
        config = _make_generation_config(max_turns=1, target_timeout=60)

        player = AsyncMock()
        player.ainvoke.return_value = {"messages": [MagicMock(content=_VALID_EXAMPLE_JSON)]}
        coach = _make_mock_coach([_make_accept_verdict()] * 5)
        checkpoint = MagicMock()
        output_mgr = MagicMock()
        output_mgr.rejected_fh = MagicMock()
        write_tool = _make_mock_write_tool()

        result = await run_generation_loop(
            player=player,
            coach=coach,
            targets=targets,
            config=config,
            checkpoint=checkpoint,
            output_manager=output_mgr,
            write_tool=write_tool,
            start_index=2,
        )

        # Only 3 targets processed (indices 2, 3, 4)
        assert result.total_targets == 3
        assert player.ainvoke.call_count == 3


# ---------------------------------------------------------------------------
# TASK-TRF-005: Orchestrator-gated writes
# ---------------------------------------------------------------------------


class TestOrchestratorGatedWrites:
    """TASK-TRF-005: Orchestrator calls write_tool only after Coach acceptance."""

    @pytest.mark.asyncio
    async def test_coach_accepts_orchestrator_writes(self) -> None:
        """TRF-005-001: Player response → Coach accepts → orchestrator writes."""
        from entrypoint.generation_loop import run_generation_loop

        targets = [_make_target()]
        config = _make_generation_config(max_turns=1, target_timeout=60)

        player = AsyncMock()
        player.ainvoke.return_value = {
            "messages": [MagicMock(content=_VALID_EXAMPLE_JSON)]
        }
        coach = _make_mock_coach([_make_accept_verdict()])
        checkpoint = MagicMock()
        output_mgr = MagicMock()
        output_mgr.rejected_fh = MagicMock()
        write_tool = _make_mock_write_tool()

        result = await run_generation_loop(
            player=player,
            coach=coach,
            targets=targets,
            config=config,
            checkpoint=checkpoint,
            output_manager=output_mgr,
            write_tool=write_tool,
            start_index=0,
        )

        assert result.accepted == 1
        # write_tool.invoke was called by the orchestrator
        write_tool.invoke.assert_called_once()
        # The call should contain the extracted example JSON
        call_args = write_tool.invoke.call_args
        assert "example_json" in call_args[0][0]

    @pytest.mark.asyncio
    async def test_coach_rejects_no_write(self) -> None:
        """TRF-005-002: Player response → Coach rejects → no write occurs."""
        from entrypoint.generation_loop import run_generation_loop

        targets = [_make_target()]
        config = _make_generation_config(max_turns=1, target_timeout=60)

        player = AsyncMock()
        player.ainvoke.return_value = {
            "messages": [MagicMock(content=_VALID_EXAMPLE_JSON)]
        }
        coach = _make_mock_coach([_make_reject_verdict()])
        checkpoint = MagicMock()
        output_mgr = MagicMock()
        output_mgr.rejected_fh = MagicMock()
        write_tool = _make_mock_write_tool()

        result = await run_generation_loop(
            player=player,
            coach=coach,
            targets=targets,
            config=config,
            checkpoint=checkpoint,
            output_manager=output_mgr,
            write_tool=write_tool,
            start_index=0,
        )

        assert result.rejected == 1
        # write_tool.invoke should NOT have been called
        write_tool.invoke.assert_not_called()

    @pytest.mark.asyncio
    async def test_write_validation_fails_treated_as_rejection(self) -> None:
        """TRF-005-003: Coach accepts but write_output validation fails → treated as rejection."""
        from entrypoint.generation_loop import run_generation_loop

        targets = [_make_target()]
        # max_turns=1 so it rejects after the write failure
        config = _make_generation_config(max_turns=1, target_timeout=60)

        player = AsyncMock()
        player.ainvoke.return_value = {
            "messages": [MagicMock(content=_VALID_EXAMPLE_JSON)]
        }
        coach = _make_mock_coach([_make_accept_verdict()])
        checkpoint = MagicMock()
        output_mgr = MagicMock()
        output_mgr.rejected_fh = MagicMock()

        # write_tool returns an error
        write_tool = MagicMock()
        write_tool.invoke.return_value = "Error: Invalid metadata.layer value 'invalid'"

        result = await run_generation_loop(
            player=player,
            coach=coach,
            targets=targets,
            config=config,
            checkpoint=checkpoint,
            output_manager=output_mgr,
            write_tool=write_tool,
            start_index=0,
        )

        # Treated as rejection despite Coach acceptance
        assert result.accepted == 0
        assert result.rejected == 1
        # write_tool.invoke was called (but returned error)
        write_tool.invoke.assert_called_once()

    @pytest.mark.asyncio
    async def test_write_failure_allows_retry_on_next_turn(self) -> None:
        """Write failure on turn 1 allows Player to revise on turn 2."""
        from entrypoint.generation_loop import run_generation_loop

        targets = [_make_target()]
        config = _make_generation_config(max_turns=2, target_timeout=60)

        player = AsyncMock()
        player.ainvoke.return_value = {
            "messages": [MagicMock(content=_VALID_EXAMPLE_JSON)]
        }
        # Coach accepts both times
        coach = _make_mock_coach([_make_accept_verdict(), _make_accept_verdict()])
        checkpoint = MagicMock()
        output_mgr = MagicMock()
        output_mgr.rejected_fh = MagicMock()

        # First write fails, second succeeds
        write_tool = MagicMock()
        write_tool.invoke.side_effect = [
            "Error: Missing required field 'messages'",
            "Written to output/train.jsonl (example #1)",
        ]

        result = await run_generation_loop(
            player=player,
            coach=coach,
            targets=targets,
            config=config,
            checkpoint=checkpoint,
            output_manager=output_mgr,
            write_tool=write_tool,
            start_index=0,
        )

        assert result.accepted == 1
        assert write_tool.invoke.call_count == 2


# ---------------------------------------------------------------------------
# TASK-TRF-005: JSON extraction from Player response
# ---------------------------------------------------------------------------


class TestExtractExampleJson:
    """TASK-TRF-005: Extract JSON example from Player response content."""

    def test_extract_raw_json(self) -> None:
        """Extract valid JSON that is the entire response."""
        from entrypoint.generation_loop import _extract_example_json

        raw = '{"messages": [], "metadata": {}}'
        result = _extract_example_json(raw)
        assert json.loads(result) == {"messages": [], "metadata": {}}

    def test_extract_from_code_fences(self) -> None:
        """Extract JSON from markdown code fences."""
        from entrypoint.generation_loop import _extract_example_json

        raw = 'Here is the example:\n```json\n{"messages": [], "metadata": {}}\n```\nDone.'
        result = _extract_example_json(raw)
        assert json.loads(result) == {"messages": [], "metadata": {}}

    def test_extract_from_surrounding_text(self) -> None:
        """Extract JSON embedded in surrounding text."""
        from entrypoint.generation_loop import _extract_example_json

        raw = 'Generated example: {"messages": [{"role": "system", "content": "hi"}], "metadata": {"layer": "behaviour"}} — that is the result.'
        result = _extract_example_json(raw)
        parsed = json.loads(result)
        assert "messages" in parsed
        assert "metadata" in parsed

    def test_invalid_content_raises_value_error(self) -> None:
        """Raise ValueError if no valid JSON can be extracted."""
        from entrypoint.generation_loop import _extract_example_json

        with pytest.raises(ValueError, match="Failed to extract JSON"):
            _extract_example_json("No JSON here at all, just plain text.")

    def test_extract_from_code_fences_without_json_tag(self) -> None:
        """Extract JSON from code fences without 'json' language tag."""
        from entrypoint.generation_loop import _extract_example_json

        raw = '```\n{"messages": [], "metadata": {}}\n```'
        result = _extract_example_json(raw)
        assert json.loads(result) == {"messages": [], "metadata": {}}


# ---------------------------------------------------------------------------
# TASK-TRF-025: JSON-string-aware brace matching
# ---------------------------------------------------------------------------


class TestStringAwareBraceMatching:
    """TASK-TRF-025: Brace matcher ignores braces inside JSON string values."""

    def test_unbalanced_open_brace_in_string(self) -> None:
        """Unmatched { inside a string value does not break extraction."""
        from entrypoint.generation_loop import _extract_json_object

        raw = 'Some text {"key": "value with { unclosed"}'
        result = _extract_json_object(raw)
        assert json.loads(result) == {"key": "value with { unclosed"}

    def test_unbalanced_close_brace_in_string(self) -> None:
        """Unmatched } inside a string value does not break extraction."""
        from entrypoint.generation_loop import _extract_json_object

        raw = '{"key": "value with } close"}'
        result = _extract_json_object(raw)
        assert json.loads(result) == {"key": "value with } close"}

    def test_escaped_quote_in_string(self) -> None:
        """Escaped quotes inside strings do not toggle string state."""
        from entrypoint.generation_loop import _extract_json_object

        raw = r'{"key": "value with \" escaped quote"}'
        result = _extract_json_object(raw)
        parsed = json.loads(result)
        assert parsed["key"] == 'value with " escaped quote'

    def test_training_example_with_braces_in_content(self) -> None:
        """Simulates the actual failure from Run 8."""
        from entrypoint.generation_loop import _extract_json_object

        raw = (
            '{"messages": [{"role": "assistant", "content": "What about {this?"}],'
            ' "metadata": {"type": "reasoning"}}'
        )
        result = _extract_json_object(raw)
        parsed = json.loads(result)
        assert parsed["messages"][0]["content"] == "What about {this?"

    def test_escaped_backslash_before_brace(self) -> None:
        r"""Escaped backslash \\{ means the brace is NOT escaped."""
        from entrypoint.generation_loop import _extract_json_object

        # In JSON: "value\\" is a string ending with a literal backslash.
        # The { after the closing quote is structural.
        raw = r'{"a": "val\\"}'
        result = _extract_json_object(raw)
        parsed = json.loads(result)
        assert parsed["a"] == "val\\"


# ---------------------------------------------------------------------------
# TASK-TRF-015: Player content extraction (content blocks support)
# ---------------------------------------------------------------------------


class TestExtractPlayerContent:
    """TASK-TRF-015: Extract Player content handling string and block formats."""

    def test_extract_string_content(self) -> None:
        """Standard string content is returned as-is."""
        from entrypoint.generation_loop import _extract_player_content

        msg = MagicMock()
        msg.content = '{"messages": [], "metadata": {}}'
        response = {"messages": [msg]}
        result = _extract_player_content(response)
        assert result == '{"messages": [], "metadata": {}}'

    def test_extract_content_blocks(self) -> None:
        """Content blocks list is concatenated into a single string."""
        from entrypoint.generation_loop import _extract_player_content

        msg = MagicMock()
        msg.content = [
            {"type": "text", "text": '{"messages": [{"role": "system", '},
            {"type": "text", "text": '"content": "hello"}], "metadata": {}}'},
        ]
        response = {"messages": [msg]}
        result = _extract_player_content(response)
        parsed = json.loads(result)
        assert "messages" in parsed
        assert parsed["messages"][0]["role"] == "system"

    def test_extract_ignores_non_text_blocks(self) -> None:
        """Non-text content blocks (e.g. reasoning) are skipped."""
        from entrypoint.generation_loop import _extract_player_content

        msg = MagicMock()
        msg.content = [
            {"type": "reasoning", "text": "thinking..."},
            {"type": "text", "text": '{"messages": [], "metadata": {}}'},
        ]
        response = {"messages": [msg]}
        result = _extract_player_content(response)
        assert "thinking" not in result
        assert json.loads(result) == {"messages": [], "metadata": {}}

    def test_empty_content_raises_value_error(self) -> None:
        """Raise ValueError when content is empty or None."""
        from entrypoint.generation_loop import _extract_player_content

        msg = MagicMock()
        msg.content = ""
        response = {"messages": [msg]}
        with pytest.raises(ValueError, match="no extractable content"):
            _extract_player_content(response)

    def test_empty_blocks_list_raises_value_error(self) -> None:
        """Raise ValueError when content blocks list has no text or reasoning."""
        from entrypoint.generation_loop import _extract_player_content

        msg = MagicMock()
        msg.content = [{"type": "image", "url": "http://example.com/img.png"}]
        msg.additional_kwargs = {}
        response = {"messages": [msg]}
        with pytest.raises(ValueError, match="no extractable content"):
            _extract_player_content(response)


# ---------------------------------------------------------------------------
# TASK-TRF-026: reasoning_content fallback in _extract_player_content
# ---------------------------------------------------------------------------


class TestExtractPlayerContentReasoningFallback:
    """TASK-TRF-026: Player extractor handles reasoning_content like Coach."""

    def test_reasoning_content_only_returns_it(self) -> None:
        """Empty content + reasoning_content returns reasoning_content."""
        from entrypoint.generation_loop import _extract_player_content

        msg = MagicMock()
        msg.content = ""
        msg.additional_kwargs = {"reasoning_content": "Thought about the problem."}
        response = {"messages": [msg]}
        result = _extract_player_content(response)
        assert result == "Thought about the problem."

    def test_content_plus_reasoning_content_merged(self) -> None:
        """Both content and reasoning_content present returns merged result."""
        from entrypoint.generation_loop import _extract_player_content

        msg = MagicMock()
        msg.content = '{"messages": [], "metadata": {}}'
        msg.additional_kwargs = {"reasoning_content": "Let me think..."}
        response = {"messages": [msg]}
        result = _extract_player_content(response)
        # String content is non-empty so Path 1 returns it directly
        # (reasoning_content merge only happens when content is empty/whitespace)
        assert result == '{"messages": [], "metadata": {}}'

    def test_whitespace_content_plus_reasoning_returns_reasoning(self) -> None:
        """Whitespace-only content + reasoning_content returns reasoning_content."""
        from entrypoint.generation_loop import _extract_player_content

        msg = MagicMock()
        msg.content = "   "
        msg.additional_kwargs = {"reasoning_content": "Deep reasoning here."}
        response = {"messages": [msg]}
        result = _extract_player_content(response)
        assert result == "Deep reasoning here."

    def test_content_blocks_reasoning_type(self) -> None:
        """Content blocks with type=reasoning are extracted as fallback."""
        from entrypoint.generation_loop import _extract_player_content

        msg = MagicMock()
        msg.content = [
            {"type": "reasoning", "text": "Step 1: analyse the problem."},
            {"type": "reasoning", "text": " Step 2: solve it."},
        ]
        msg.additional_kwargs = {}
        response = {"messages": [msg]}
        result = _extract_player_content(response)
        assert "Step 1" in result
        assert "Step 2" in result

    def test_no_content_no_reasoning_raises(self) -> None:
        """No content and no reasoning_content still raises ValueError."""
        from entrypoint.generation_loop import _extract_player_content

        msg = MagicMock()
        msg.content = ""
        msg.additional_kwargs = {}
        response = {"messages": [msg]}
        with pytest.raises(ValueError, match="no extractable content"):
            _extract_player_content(response)

    def test_no_additional_kwargs_attr(self) -> None:
        """Message without additional_kwargs attribute doesn't crash."""
        from entrypoint.generation_loop import _extract_player_content

        msg = MagicMock(spec=[])  # No attributes at all
        msg.content = ""
        response = {"messages": [msg]}
        with pytest.raises(ValueError, match="no extractable content"):
            _extract_player_content(response)

    def test_content_only_no_reasoning_returns_content(self) -> None:
        """Standard content with no reasoning_content returns content unchanged."""
        from entrypoint.generation_loop import _extract_player_content

        msg = MagicMock()
        msg.content = '{"messages": [], "metadata": {}}'
        msg.additional_kwargs = {}
        response = {"messages": [msg]}
        result = _extract_player_content(response)
        assert result == '{"messages": [], "metadata": {}}'


# ---------------------------------------------------------------------------
# TASK-TRF-006: Write retry cap (3 per target)
# ---------------------------------------------------------------------------


class TestWriteRetryCap:
    """TASK-TRF-006: Write retry cap prevents infinite write loops."""

    @pytest.mark.asyncio
    async def test_three_write_failures_rejects_target(self) -> None:
        """3 consecutive write failures → target rejected."""
        from entrypoint.generation_loop import run_generation_loop

        targets = [_make_target()]
        # Allow enough turns for 3 write attempts
        config = _make_generation_config(max_turns=5, target_timeout=60)

        player = AsyncMock()
        player.ainvoke.return_value = {
            "messages": [MagicMock(content=_VALID_EXAMPLE_JSON)]
        }
        # Coach accepts every time
        coach = _make_mock_coach([_make_accept_verdict()] * 5)
        checkpoint = MagicMock()
        output_mgr = MagicMock()
        output_mgr.rejected_fh = MagicMock()

        # write_tool always fails
        write_tool = MagicMock()
        write_tool.invoke.return_value = "Error: Invalid metadata"

        result = await run_generation_loop(
            player=player,
            coach=coach,
            targets=targets,
            config=config,
            checkpoint=checkpoint,
            output_manager=output_mgr,
            write_tool=write_tool,
            start_index=0,
        )

        assert result.accepted == 0
        assert result.rejected == 1
        # Should stop after 3 write attempts, not exhaust all 5 turns
        assert write_tool.invoke.call_count == 3

    @pytest.mark.asyncio
    async def test_write_succeeds_on_second_attempt(self) -> None:
        """Write succeeds on 2nd attempt → target accepted."""
        from entrypoint.generation_loop import run_generation_loop

        targets = [_make_target()]
        config = _make_generation_config(max_turns=5, target_timeout=60)

        player = AsyncMock()
        player.ainvoke.return_value = {
            "messages": [MagicMock(content=_VALID_EXAMPLE_JSON)]
        }
        # Coach accepts every time
        coach = _make_mock_coach([_make_accept_verdict()] * 5)
        checkpoint = MagicMock()
        output_mgr = MagicMock()
        output_mgr.rejected_fh = MagicMock()

        # First write fails, second succeeds
        write_tool = MagicMock()
        write_tool.invoke.side_effect = [
            "Error: Missing required field",
            "Written to output/train.jsonl (example #1)",
        ]

        result = await run_generation_loop(
            player=player,
            coach=coach,
            targets=targets,
            config=config,
            checkpoint=checkpoint,
            output_manager=output_mgr,
            write_tool=write_tool,
            start_index=0,
        )

        assert result.accepted == 1
        assert result.rejected == 0
        assert write_tool.invoke.call_count == 2

    @pytest.mark.asyncio
    async def test_rejection_record_includes_write_failures(self) -> None:
        """Rejection record includes write failure history."""
        from entrypoint.generation_loop import run_generation_loop

        targets = [_make_target()]
        config = _make_generation_config(max_turns=5, target_timeout=60)

        player = AsyncMock()
        player.ainvoke.return_value = {
            "messages": [MagicMock(content=_VALID_EXAMPLE_JSON)]
        }
        coach = _make_mock_coach([_make_accept_verdict()] * 5)
        checkpoint = MagicMock()
        output_mgr = MagicMock()
        rejected_lines: list[str] = []
        output_mgr.rejected_fh = MagicMock()
        output_mgr.rejected_fh.write = MagicMock(
            side_effect=lambda s: rejected_lines.append(s)
        )

        write_tool = MagicMock()
        write_tool.invoke.return_value = "Error: Invalid metadata"

        await run_generation_loop(
            player=player,
            coach=coach,
            targets=targets,
            config=config,
            checkpoint=checkpoint,
            output_manager=output_mgr,
            write_tool=write_tool,
            start_index=0,
        )

        assert len(rejected_lines) == 1
        record = json.loads(rejected_lines[0].strip())
        # Rejection history should contain write_error entries
        write_errors = [
            r for r in record["rejection_history"] if "write_error" in r
        ]
        assert len(write_errors) == 3

    @pytest.mark.asyncio
    async def test_max_write_attempts_configurable(self) -> None:
        """max_write_attempts is configurable via GenerationConfig."""
        from entrypoint.generation_loop import run_generation_loop

        targets = [_make_target()]
        # Set max_write_attempts to 2 (custom)
        config = _make_generation_config(
            max_turns=5, target_timeout=60, max_write_attempts=2
        )

        player = AsyncMock()
        player.ainvoke.return_value = {
            "messages": [MagicMock(content=_VALID_EXAMPLE_JSON)]
        }
        coach = _make_mock_coach([_make_accept_verdict()] * 5)
        checkpoint = MagicMock()
        output_mgr = MagicMock()
        output_mgr.rejected_fh = MagicMock()

        write_tool = MagicMock()
        write_tool.invoke.return_value = "Error: Invalid metadata"

        result = await run_generation_loop(
            player=player,
            coach=coach,
            targets=targets,
            config=config,
            checkpoint=checkpoint,
            output_manager=output_mgr,
            write_tool=write_tool,
            start_index=0,
        )

        assert result.rejected == 1
        # Should stop after 2 attempts (custom config), not 3
        assert write_tool.invoke.call_count == 2


# ---------------------------------------------------------------------------
# TASK-TRF-010: Token usage logging
# ---------------------------------------------------------------------------


def _make_msg_with_usage(
    content: str,
    prompt_tokens: int = 0,
    completion_tokens: int = 0,
) -> MagicMock:
    """Create a mock message with response_metadata containing token usage."""
    msg = MagicMock(content=content)
    if prompt_tokens or completion_tokens:
        msg.response_metadata = {
            "token_usage": {
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": prompt_tokens + completion_tokens,
            }
        }
    else:
        msg.response_metadata = {}
    return msg


class TestTokenUsageLogging:
    """TASK-TRF-010: Token usage logged for each LLM call and pipeline summary."""

    @pytest.mark.asyncio
    async def test_token_usage_logged_per_call(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Token usage is logged for each Player and Coach LLM call."""
        from entrypoint.generation_loop import run_generation_loop

        targets = [_make_target()]
        config = _make_generation_config(max_turns=1, target_timeout=60)

        player = AsyncMock()
        player.ainvoke.return_value = {
            "messages": [
                _make_msg_with_usage(_VALID_EXAMPLE_JSON, prompt_tokens=100, completion_tokens=50)
            ]
        }

        coach = AsyncMock()
        coach.ainvoke.return_value = {
            "messages": [
                _make_msg_with_usage(
                    _make_accept_verdict().model_dump_json(),
                    prompt_tokens=80,
                    completion_tokens=30,
                )
            ]
        }

        checkpoint = MagicMock()
        output_mgr = MagicMock()
        output_mgr.rejected_fh = MagicMock()
        write_tool = _make_mock_write_tool()

        with caplog.at_level(logging.INFO):
            await run_generation_loop(
                player=player,
                coach=coach,
                targets=targets,
                config=config,
                checkpoint=checkpoint,
                output_manager=output_mgr,
                write_tool=write_tool,
                start_index=0,
            )

        log_text = caplog.text
        assert "LLM usage: agent=player" in log_text
        assert "prompt_tokens=100" in log_text
        assert "completion_tokens=50" in log_text
        assert "LLM usage: agent=coach" in log_text
        assert "prompt_tokens=80" in log_text
        assert "completion_tokens=30" in log_text

    @pytest.mark.asyncio
    async def test_per_target_cumulative_tokens_logged(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Per-target cumulative token totals are logged at target completion."""
        from entrypoint.generation_loop import run_generation_loop

        targets = [_make_target()]
        config = _make_generation_config(max_turns=1, target_timeout=60)

        player = AsyncMock()
        player.ainvoke.return_value = {
            "messages": [
                _make_msg_with_usage(_VALID_EXAMPLE_JSON, prompt_tokens=200, completion_tokens=100)
            ]
        }

        coach = AsyncMock()
        coach.ainvoke.return_value = {
            "messages": [
                _make_msg_with_usage(
                    _make_accept_verdict().model_dump_json(),
                    prompt_tokens=150,
                    completion_tokens=60,
                )
            ]
        }

        checkpoint = MagicMock()
        output_mgr = MagicMock()
        output_mgr.rejected_fh = MagicMock()
        write_tool = _make_mock_write_tool()

        with caplog.at_level(logging.INFO):
            await run_generation_loop(
                player=player,
                coach=coach,
                targets=targets,
                config=config,
                checkpoint=checkpoint,
                output_manager=output_mgr,
                write_tool=write_tool,
                start_index=0,
            )

        log_text = caplog.text
        # Per-target cumulative: player(200+100) + coach(150+60) = 350 prompt, 160 completion
        assert "target_tokens: index=0" in log_text
        assert "prompt_tokens=350" in log_text
        assert "completion_tokens=160" in log_text

    @pytest.mark.asyncio
    async def test_pipeline_summary_includes_total_tokens(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Pipeline summary logs total tokens consumed across all targets."""
        from entrypoint.generation_loop import run_generation_loop

        targets = [_make_target(category="Cat-0"), _make_target(category="Cat-1")]
        config = _make_generation_config(max_turns=1, target_timeout=60)

        call_count = 0

        async def player_side_effect(*args: Any, **kwargs: Any) -> dict:
            nonlocal call_count
            call_count += 1
            return {
                "messages": [
                    _make_msg_with_usage(_VALID_EXAMPLE_JSON, prompt_tokens=100, completion_tokens=50)
                ]
            }

        player = AsyncMock()
        player.ainvoke.side_effect = player_side_effect

        coach = AsyncMock()
        verdict_json = _make_accept_verdict().model_dump_json()
        coach.ainvoke.side_effect = [
            {"messages": [_make_msg_with_usage(verdict_json, prompt_tokens=80, completion_tokens=30)]},
            {"messages": [_make_msg_with_usage(verdict_json, prompt_tokens=80, completion_tokens=30)]},
        ]

        checkpoint = MagicMock()
        output_mgr = MagicMock()
        output_mgr.rejected_fh = MagicMock()
        write_tool = _make_mock_write_tool()

        with caplog.at_level(logging.INFO):
            result = await run_generation_loop(
                player=player,
                coach=coach,
                targets=targets,
                config=config,
                checkpoint=checkpoint,
                output_manager=output_mgr,
                write_tool=write_tool,
                start_index=0,
            )

        log_text = caplog.text
        # 2 targets * (100+80) prompt = 360, 2 * (50+30) completion = 160
        assert "pipeline_tokens:" in log_text
        assert "prompt_tokens=360" in log_text
        assert "completion_tokens=160" in log_text
        assert "total_tokens=520" in log_text

    @pytest.mark.asyncio
    async def test_generation_result_includes_token_usage(self) -> None:
        """GenerationResult.token_usage contains cumulative token stats."""
        from entrypoint.generation_loop import run_generation_loop

        targets = [_make_target()]
        config = _make_generation_config(max_turns=1, target_timeout=60)

        player = AsyncMock()
        player.ainvoke.return_value = {
            "messages": [
                _make_msg_with_usage(_VALID_EXAMPLE_JSON, prompt_tokens=500, completion_tokens=200)
            ]
        }

        coach = AsyncMock()
        coach.ainvoke.return_value = {
            "messages": [
                _make_msg_with_usage(
                    _make_accept_verdict().model_dump_json(),
                    prompt_tokens=300,
                    completion_tokens=100,
                )
            ]
        }

        checkpoint = MagicMock()
        output_mgr = MagicMock()
        output_mgr.rejected_fh = MagicMock()
        write_tool = _make_mock_write_tool()

        result = await run_generation_loop(
            player=player,
            coach=coach,
            targets=targets,
            config=config,
            checkpoint=checkpoint,
            output_manager=output_mgr,
            write_tool=write_tool,
            start_index=0,
        )

        assert result.token_usage is not None
        assert result.token_usage.prompt_tokens == 800
        assert result.token_usage.completion_tokens == 300
        assert result.token_usage.total_tokens == 1100

    @pytest.mark.asyncio
    async def test_no_usage_data_gracefully_handled(self) -> None:
        """When response has no token usage metadata, logging is skipped gracefully."""
        from entrypoint.generation_loop import run_generation_loop

        targets = [_make_target()]
        config = _make_generation_config(max_turns=1, target_timeout=60)

        # Standard mock without response_metadata (like existing tests)
        player = _make_mock_player([_VALID_EXAMPLE_JSON])
        coach = _make_mock_coach([_make_accept_verdict()])

        checkpoint = MagicMock()
        output_mgr = MagicMock()
        output_mgr.rejected_fh = MagicMock()
        write_tool = _make_mock_write_tool()

        result = await run_generation_loop(
            player=player,
            coach=coach,
            targets=targets,
            config=config,
            checkpoint=checkpoint,
            output_manager=output_mgr,
            write_tool=write_tool,
            start_index=0,
        )

        # Should still work fine with zero tokens
        assert result.accepted == 1
        assert result.token_usage is not None
        assert result.token_usage.total_tokens == 0


# ---------------------------------------------------------------------------
# TASK-TRF-009: Orchestrator RAG pre-fetch
# ---------------------------------------------------------------------------


def _make_mock_rag_tool(
    return_value: str = "--- Chunk 1 (source: doc.pdf, p.1) ---\nSample curriculum content.\n",
) -> MagicMock:
    """Create a mock rag_retrieval tool for the orchestrator."""
    rag_tool = MagicMock()
    rag_tool.invoke.return_value = return_value
    return rag_tool


class TestRagPreFetch:
    """TASK-TRF-009: Orchestrator pre-fetches RAG context before Player turn."""

    @pytest.mark.asyncio
    async def test_rag_tool_called_once_per_target(self) -> None:
        """rag_tool.invoke is called once per target when rag_tool is provided."""
        from entrypoint.generation_loop import run_generation_loop

        targets = [_make_target(category="Poetry"), _make_target(category="Drama")]
        config = _make_generation_config(max_turns=1, target_timeout=60)

        player = AsyncMock()
        player.ainvoke.return_value = {"messages": [MagicMock(content=_VALID_EXAMPLE_JSON)]}
        coach = _make_mock_coach([_make_accept_verdict()] * 2)
        checkpoint = MagicMock()
        output_mgr = MagicMock()
        output_mgr.rejected_fh = MagicMock()
        write_tool = _make_mock_write_tool()
        rag_tool = _make_mock_rag_tool()

        await run_generation_loop(
            player=player,
            coach=coach,
            targets=targets,
            config=config,
            checkpoint=checkpoint,
            output_manager=output_mgr,
            write_tool=write_tool,
            start_index=0,
            rag_tool=rag_tool,
        )

        assert rag_tool.invoke.call_count == 2

    @pytest.mark.asyncio
    async def test_rag_context_injected_into_player_message(self) -> None:
        """RAG context appears in the Player's input message."""
        from entrypoint.generation_loop import run_generation_loop

        targets = [_make_target(category="Poetry", type_="reasoning")]
        config = _make_generation_config(max_turns=1, target_timeout=60)

        player = AsyncMock()
        player.ainvoke.return_value = {"messages": [MagicMock(content=_VALID_EXAMPLE_JSON)]}
        coach = _make_mock_coach([_make_accept_verdict()])
        checkpoint = MagicMock()
        output_mgr = MagicMock()
        output_mgr.rejected_fh = MagicMock()
        write_tool = _make_mock_write_tool()
        rag_tool = _make_mock_rag_tool("Relevant curriculum chunk about poetry.")

        await run_generation_loop(
            player=player,
            coach=coach,
            targets=targets,
            config=config,
            checkpoint=checkpoint,
            output_manager=output_mgr,
            write_tool=write_tool,
            start_index=0,
            rag_tool=rag_tool,
        )

        # Check the message sent to the Player contains the RAG context
        player_call = player.ainvoke.call_args
        player_msg = player_call[0][0]["messages"][0]["content"]
        assert "Curriculum Context" in player_msg
        assert "Relevant curriculum chunk about poetry." in player_msg

    @pytest.mark.asyncio
    async def test_rag_query_uses_target_category_and_type(self) -> None:
        """RAG query is built from target.category and target.type."""
        from entrypoint.generation_loop import run_generation_loop

        targets = [_make_target(category="Shakespearean tragedy", type_="reasoning")]
        config = _make_generation_config(max_turns=1, target_timeout=60)

        player = AsyncMock()
        player.ainvoke.return_value = {"messages": [MagicMock(content=_VALID_EXAMPLE_JSON)]}
        coach = _make_mock_coach([_make_accept_verdict()])
        checkpoint = MagicMock()
        output_mgr = MagicMock()
        output_mgr.rejected_fh = MagicMock()
        write_tool = _make_mock_write_tool()
        rag_tool = _make_mock_rag_tool()

        await run_generation_loop(
            player=player,
            coach=coach,
            targets=targets,
            config=config,
            checkpoint=checkpoint,
            output_manager=output_mgr,
            write_tool=write_tool,
            start_index=0,
            rag_tool=rag_tool,
        )

        rag_call = rag_tool.invoke.call_args
        assert rag_call[0][0]["query"] == "Shakespearean tragedy reasoning"

    @pytest.mark.asyncio
    async def test_rag_failure_does_not_block_generation(self) -> None:
        """If rag_tool returns an error, generation proceeds without RAG context."""
        from entrypoint.generation_loop import run_generation_loop

        targets = [_make_target()]
        config = _make_generation_config(max_turns=1, target_timeout=60)

        player = AsyncMock()
        player.ainvoke.return_value = {"messages": [MagicMock(content=_VALID_EXAMPLE_JSON)]}
        coach = _make_mock_coach([_make_accept_verdict()])
        checkpoint = MagicMock()
        output_mgr = MagicMock()
        output_mgr.rejected_fh = MagicMock()
        write_tool = _make_mock_write_tool()

        # RAG tool returns an error string
        rag_tool = _make_mock_rag_tool("Error: ChromaDB unavailable — connection refused")

        result = await run_generation_loop(
            player=player,
            coach=coach,
            targets=targets,
            config=config,
            checkpoint=checkpoint,
            output_manager=output_mgr,
            write_tool=write_tool,
            start_index=0,
            rag_tool=rag_tool,
        )

        # Generation should still succeed
        assert result.accepted == 1

        # Player message should NOT contain the error string as context
        player_msg = player.ainvoke.call_args[0][0]["messages"][0]["content"]
        assert "Curriculum Context" not in player_msg

    @pytest.mark.asyncio
    async def test_rag_exception_does_not_block_generation(self) -> None:
        """If rag_tool raises an exception, generation proceeds without RAG context."""
        from entrypoint.generation_loop import run_generation_loop

        targets = [_make_target()]
        config = _make_generation_config(max_turns=1, target_timeout=60)

        player = AsyncMock()
        player.ainvoke.return_value = {"messages": [MagicMock(content=_VALID_EXAMPLE_JSON)]}
        coach = _make_mock_coach([_make_accept_verdict()])
        checkpoint = MagicMock()
        output_mgr = MagicMock()
        output_mgr.rejected_fh = MagicMock()
        write_tool = _make_mock_write_tool()

        # RAG tool raises an exception
        rag_tool = MagicMock()
        rag_tool.invoke.side_effect = RuntimeError("ChromaDB crashed")

        result = await run_generation_loop(
            player=player,
            coach=coach,
            targets=targets,
            config=config,
            checkpoint=checkpoint,
            output_manager=output_mgr,
            write_tool=write_tool,
            start_index=0,
            rag_tool=rag_tool,
        )

        # Generation should still succeed
        assert result.accepted == 1

    @pytest.mark.asyncio
    async def test_no_rag_tool_backward_compatible(self) -> None:
        """When rag_tool is not provided (None), loop works as before."""
        from entrypoint.generation_loop import run_generation_loop

        targets = [_make_target()]
        config = _make_generation_config(max_turns=1, target_timeout=60)

        player = AsyncMock()
        player.ainvoke.return_value = {"messages": [MagicMock(content=_VALID_EXAMPLE_JSON)]}
        coach = _make_mock_coach([_make_accept_verdict()])
        checkpoint = MagicMock()
        output_mgr = MagicMock()
        output_mgr.rejected_fh = MagicMock()
        write_tool = _make_mock_write_tool()

        result = await run_generation_loop(
            player=player,
            coach=coach,
            targets=targets,
            config=config,
            checkpoint=checkpoint,
            output_manager=output_mgr,
            write_tool=write_tool,
            start_index=0,
            # rag_tool not passed — defaults to None
        )

        assert result.accepted == 1

        # Player message should NOT contain RAG context section
        player_msg = player.ainvoke.call_args[0][0]["messages"][0]["content"]
        assert "Curriculum Context" not in player_msg


class TestBuildPlayerMessageWithRag:
    """TASK-TRF-009: _build_player_message with rag_context parameter."""

    def test_rag_context_included_when_provided(self) -> None:
        """RAG context appears in message when provided."""
        from entrypoint.generation_loop import _build_player_message

        target = _make_target(category="Poetry", type_="reasoning")
        msg = _build_player_message(target, None, rag_context="Chunk about poetry.")

        assert "Curriculum Context" in msg
        assert "Chunk about poetry." in msg

    def test_no_rag_context_when_none(self) -> None:
        """No RAG section appears when rag_context is None."""
        from entrypoint.generation_loop import _build_player_message

        target = _make_target(category="Poetry", type_="reasoning")
        msg = _build_player_message(target, None, rag_context=None)

        assert "Curriculum Context" not in msg

    def test_rag_context_before_coach_feedback(self) -> None:
        """RAG context appears before Coach feedback in the message."""
        from entrypoint.generation_loop import _build_player_message

        target = _make_target()
        msg = _build_player_message(
            target,
            coach_feedback="Fix the example.",
            rag_context="Relevant chunk.",
        )

        rag_pos = msg.index("Curriculum Context")
        feedback_pos = msg.index("Coach Feedback")
        assert rag_pos < feedback_pos


# ---------------------------------------------------------------------------
# TASK-TRF-020: normalise_think_closing_tags before JSON extraction
# ---------------------------------------------------------------------------


class TestNormaliseThinkBeforeExtraction:
    """TASK-TRF-020: Malformed think tags are normalised before JSON extraction."""

    @pytest.mark.asyncio
    async def test_malformed_think_tags_normalised_before_extraction(self) -> None:
        """Player content with <think>...<think> is normalised so JSON extraction succeeds."""
        from entrypoint.generation_loop import run_generation_loop

        # JSON with malformed think tags inside an assistant message value
        malformed_json = json.dumps({
            "messages": [
                {"role": "system", "content": "You are a tutor."},
                {"role": "user", "content": "What is a metaphor?"},
                {
                    "role": "assistant",
                    "content": "<think>Let me reason about this<think> A metaphor is a figure of speech.",
                },
            ],
            "metadata": {
                "layer": "behaviour",
                "type": "reasoning",
            },
        })

        targets = [_make_target()]
        config = _make_generation_config(max_turns=1, target_timeout=60)

        player = AsyncMock()
        player.ainvoke.return_value = {
            "messages": [MagicMock(content=malformed_json)]
        }
        coach = _make_mock_coach([_make_accept_verdict()])
        checkpoint = MagicMock()
        output_mgr = MagicMock()
        output_mgr.rejected_fh = MagicMock()
        write_tool = _make_mock_write_tool()

        result = await run_generation_loop(
            player=player,
            coach=coach,
            targets=targets,
            config=config,
            checkpoint=checkpoint,
            output_manager=output_mgr,
            write_tool=write_tool,
            start_index=0,
        )

        assert result.accepted == 1
        # write_tool should have been called with normalised content
        write_tool.invoke.assert_called_once()
        call_json = write_tool.invoke.call_args[0][0]["example_json"]
        assert "</think>" in call_json
        # The malformed double-open pattern should be fixed
        assert "<think>Let me reason about this<think>" not in call_json


# ---------------------------------------------------------------------------
# TASK-TRF-030: JSON string repair pre-processing
# ---------------------------------------------------------------------------


class TestRepairJsonStrings:
    """TASK-TRF-030: Repair literal newlines/tabs inside JSON string values."""

    def test_repair_literal_newline_in_string(self) -> None:
        """Literal newline inside a JSON string is escaped to \\n."""
        from entrypoint.generation_loop import _repair_json_strings

        bad = '{"content": "Hello\nWorld"}'
        repaired = _repair_json_strings(bad)
        assert json.loads(repaired) == {"content": "Hello\nWorld"}

    def test_repair_preserves_structural_newlines(self) -> None:
        """Newlines between JSON tokens (structural) are preserved."""
        from entrypoint.generation_loop import _repair_json_strings

        good = '{\n  "key": "value"\n}'
        repaired = _repair_json_strings(good)
        assert json.loads(repaired) == {"key": "value"}

    def test_repair_handles_escaped_quotes(self) -> None:
        """Escaped quotes inside strings do not confuse the state machine."""
        from entrypoint.generation_loop import _repair_json_strings

        s = '{"content": "She said \\"hello\\"\\nand left"}'
        repaired = _repair_json_strings(s)
        parsed = json.loads(repaired)
        assert "hello" in parsed["content"]

    def test_repair_tab_in_string(self) -> None:
        """Literal tab inside a JSON string is escaped to \\t."""
        from entrypoint.generation_loop import _repair_json_strings

        bad = '{"content": "col1\tcol2"}'
        repaired = _repair_json_strings(bad)
        assert json.loads(repaired) == {"content": "col1\tcol2"}

    def test_repair_multiple_newlines_in_string(self) -> None:
        """Multiple literal newlines in a single string value are all escaped."""
        from entrypoint.generation_loop import _repair_json_strings

        bad = '{"content": "line1\nline2\nline3"}'
        repaired = _repair_json_strings(bad)
        parsed = json.loads(repaired)
        assert parsed["content"] == "line1\nline2\nline3"

    def test_repair_mixed_structural_and_string_newlines(self) -> None:
        """Structural newlines preserved while in-string newlines escaped."""
        from entrypoint.generation_loop import _repair_json_strings

        bad = '{\n  "content": "Hello\nWorld",\n  "key": "val"\n}'
        repaired = _repair_json_strings(bad)
        parsed = json.loads(repaired)
        assert parsed["content"] == "Hello\nWorld"
        assert parsed["key"] == "val"

    def test_repair_empty_string(self) -> None:
        """Empty input returns empty output."""
        from entrypoint.generation_loop import _repair_json_strings

        assert _repair_json_strings("") == ""

    def test_no_strings_passthrough(self) -> None:
        """JSON with no string values passes through unchanged."""
        from entrypoint.generation_loop import _repair_json_strings

        good = '{"count": 42, "flag": true}'
        repaired = _repair_json_strings(good)
        assert json.loads(repaired) == {"count": 42, "flag": True}


class TestRepairIntegrationWithExtraction:
    """TASK-TRF-030: Repair is applied during JSON extraction."""

    def test_extract_json_with_literal_newline_in_string(self) -> None:
        """_extract_json_object succeeds when string value has literal newline."""
        from entrypoint.generation_loop import _extract_json_object

        raw = '{"messages": [], "metadata": {"note": "line1\nline2"}}'
        result = _extract_json_object(raw)
        parsed = json.loads(result)
        assert parsed["metadata"]["note"] == "line1\nline2"

    def test_extract_from_fence_with_literal_newline(self) -> None:
        """Code-fence extraction succeeds with literal newline in string."""
        from entrypoint.generation_loop import _extract_json_object

        raw = (
            "Here is the example:\n"
            "```json\n"
            '{"content": "Great question!\nLet\'s explore this together..."}\n'
            "```\n"
        )
        result = _extract_json_object(raw)
        parsed = json.loads(result)
        assert "Great question!" in parsed["content"]

    def test_extract_brace_match_with_literal_newline(self) -> None:
        """Brace-matching extraction succeeds with literal newline in string."""
        from entrypoint.generation_loop import _extract_json_object

        raw = 'Some text {"key": "hello\nworld"} more text'
        result = _extract_json_object(raw)
        parsed = json.loads(result)
        assert parsed["key"] == "hello\nworld"


# ---------------------------------------------------------------------------
# TASK-OR-002: Grade target distribution in player message
# ---------------------------------------------------------------------------


class TestGradeDistribution:
    """TASK-OR-002: Grade target round-robin and player message injection."""

    def test_grade_target_in_player_message(self) -> None:
        """Player message includes explicit grade_target parameter."""
        from entrypoint.generation_loop import _build_player_message

        target = _make_target(category="Poetry", type_="reasoning")
        msg = _build_player_message(target, None, grade_target=8)
        assert "Grade Target: 8" in msg

    def test_null_grade_displays_correctly(self) -> None:
        """null grade_target displays as grade-agnostic."""
        from entrypoint.generation_loop import _build_player_message

        target = _make_target(category="Terminology", type_="direct")
        msg = _build_player_message(target, None, grade_target=None)
        assert "null (grade-agnostic)" in msg

    def test_default_grade_target_is_7(self) -> None:
        """Default grade_target parameter is 7 (backward compat)."""
        from entrypoint.generation_loop import _build_player_message

        target = _make_target()
        msg = _build_player_message(target, None)
        assert "Grade Target: 7" in msg

    def test_count_not_in_player_message(self) -> None:
        """Count field should NOT appear in player message (replaced by grade)."""
        from entrypoint.generation_loop import _build_player_message

        target = _make_target(count=90)
        msg = _build_player_message(target, None)
        assert "Count:" not in msg

    def test_round_robin_distribution_even(self) -> None:
        """Round-robin distributes 12 examples evenly across 6 grades."""
        grades = [4, 5, 6, 7, 8, 9]
        target = GenerationTarget(
            category="test", type="reasoning", count=12,
            grade_targets=grades,
        )
        assigned = [
            target.grade_targets[i % len(target.grade_targets)]
            for i in range(12)
        ]
        # Each grade should appear exactly twice
        for g in grades:
            assert assigned.count(g) == 2

    def test_round_robin_direct_type_all_null(self) -> None:
        """Direct-type targets with grade_targets=[null] produce all null."""
        target = GenerationTarget(
            category="test", type="direct", count=5,
            grade_targets=[None],
        )
        assigned = [
            target.grade_targets[i % len(target.grade_targets)]
            for i in range(5)
        ]
        assert all(g is None for g in assigned)
