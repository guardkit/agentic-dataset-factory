"""Test that ValueError from _parse_coach_verdict is caught by per-target handler.

Covers TASK-NRF-12C1 acceptance criteria:
- ValueError added to the except tuple at generation_loop.py:1011
- ValueError from _parse_coach_verdict results in target rejection (not pipeline crash)
- Pipeline continues processing remaining targets after ValueError
"""

from __future__ import annotations

import asyncio
import io
import json
from dataclasses import dataclass
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from entrypoint.generation_loop import run_generation_loop


@dataclass
class _MinimalConfig:
    """Minimal config stub for run_generation_loop."""

    max_turns: int = 3
    target_timeout: int = 60
    llm_retry_max: int = 1
    llm_retry_backoff: float = 0.0


def _make_target(category: str = "test_cat", type_: str = "reasoning") -> MagicMock:
    """Create a mock GenerationTarget."""
    t = MagicMock()
    t.category = category
    t.type = type_
    t.count = 1
    return t


def _make_output_manager() -> MagicMock:
    """Create a mock OutputFileManager with writable rejected_fh."""
    om = MagicMock()
    om.rejected_fh = io.StringIO()
    return om


def _make_checkpoint() -> MagicMock:
    """Create a mock CheckpointManager."""
    cp = MagicMock()
    cp.save = MagicMock()
    return cp


class TestValueErrorCaughtByPerTargetHandler:
    """TASK-NRF-12C1: ValueError must be caught and target rejected."""

    @pytest.mark.asyncio
    async def test_valueerror_rejects_target_and_continues(self) -> None:
        """ValueError from _process_single_target → target rejected, loop continues."""
        targets = [_make_target("cat_a"), _make_target("cat_b")]
        config = _MinimalConfig()
        checkpoint = _make_checkpoint()
        output_manager = _make_output_manager()
        write_tool = MagicMock()

        # First target raises ValueError (simulating Coach non-JSON response),
        # second target succeeds normally.
        async def side_effect(*args, **kwargs):
            call_count = mock_process.call_count
            if call_count == 1:
                raise ValueError("no JSON object found in response")
            # Second target accepted
            return (True, 1, [])

        with patch(
            "entrypoint.generation_loop._process_single_target",
            new_callable=AsyncMock,
        ) as mock_process:
            mock_process.side_effect = side_effect

            result = await run_generation_loop(
                player=MagicMock(),
                coach=MagicMock(),
                targets=targets,
                config=config,
                checkpoint=checkpoint,
                output_manager=output_manager,
                write_tool=write_tool,
            )

        # First target rejected via ValueError, second accepted
        assert result.rejected == 1
        assert result.accepted == 1
        assert result.total_targets == 2

        # Both targets were processed (loop did not crash on first)
        assert mock_process.call_count == 2

        # Checkpoint saved for both targets
        assert checkpoint.save.call_count == 2

        # Rejection record written to rejected_fh
        rejected_output = output_manager.rejected_fh.getvalue()
        assert rejected_output, "Expected rejection record to be written"
        record = json.loads(rejected_output.strip())
        assert "llm_failure" in record["reason"]
        assert "ValueError" in record["reason"] or "no JSON" in record["reason"]

    @pytest.mark.asyncio
    async def test_valueerror_does_not_crash_pipeline(self) -> None:
        """All targets raising ValueError → all rejected, no unhandled exception."""
        targets = [_make_target() for _ in range(3)]
        config = _MinimalConfig()
        checkpoint = _make_checkpoint()
        output_manager = _make_output_manager()

        with patch(
            "entrypoint.generation_loop._process_single_target",
            new_callable=AsyncMock,
            side_effect=ValueError("Coach returned reasoning text, not JSON"),
        ):
            result = await run_generation_loop(
                player=MagicMock(),
                coach=MagicMock(),
                targets=targets,
                config=config,
                checkpoint=checkpoint,
                output_manager=output_manager,
                write_tool=MagicMock(),
            )

        # All targets rejected, none crashed the pipeline
        assert result.rejected == 3
        assert result.accepted == 0
        assert result.total_targets == 3
