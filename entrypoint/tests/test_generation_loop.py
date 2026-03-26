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
