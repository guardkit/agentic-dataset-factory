"""Test that httpx.HTTPStatusError is caught by both exception handlers.

Covers TASK-OR-007 acceptance criteria:
- httpx.HTTPStatusError caught in _invoke_with_retry()
- 4xx errors (except 429) fail fast without retry
- 429 and 5xx errors retry with backoff
- httpx.HTTPStatusError caught in per-target handler
- Target rejected with llm_failure reason on HTTP error
- Pipeline continues to next target after HTTP error
"""

from __future__ import annotations

import asyncio
import io
import json
from dataclasses import dataclass
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from entrypoint.generation_loop import _invoke_with_retry, run_generation_loop


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_http_error(status_code: int) -> httpx.HTTPStatusError:
    """Create an httpx.HTTPStatusError with the given status code."""
    request = httpx.Request("POST", "http://localhost:8000/v1/chat/completions")
    response = httpx.Response(status_code, request=request)
    return httpx.HTTPStatusError(
        f"Server error {status_code}",
        request=request,
        response=response,
    )


@dataclass
class _MinimalConfig:
    """Minimal config stub for run_generation_loop."""

    max_turns: int = 3
    target_timeout: int = 60
    llm_retry_max: int = 2
    llm_retry_backoff: float = 0.0


def _make_target(category: str = "test_cat", type_: str = "reasoning") -> MagicMock:
    """Create a mock GenerationTarget."""
    t = MagicMock()
    t.category = category
    t.type = type_
    t.count = 1
    t.grade_targets = [7]
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


# ---------------------------------------------------------------------------
# Tests for _invoke_with_retry — HTTP error handling
# ---------------------------------------------------------------------------


class TestInvokeWithRetryHTTPErrors:
    """TASK-OR-007: _invoke_with_retry catches httpx.HTTPStatusError."""

    @pytest.mark.asyncio
    async def test_http_400_not_retried(self) -> None:
        """400 Bad Request should raise immediately without retry."""
        agent = AsyncMock()
        agent.ainvoke.side_effect = _make_http_error(400)

        with pytest.raises(httpx.HTTPStatusError) as exc_info:
            await _invoke_with_retry(
                agent, {"input": "test"}, max_retries=2, backoff_base=0.0
            )

        assert exc_info.value.response.status_code == 400
        # Should NOT retry — only 1 call
        assert agent.ainvoke.call_count == 1

    @pytest.mark.asyncio
    async def test_http_422_not_retried(self) -> None:
        """422 Unprocessable Entity should raise immediately without retry."""
        agent = AsyncMock()
        agent.ainvoke.side_effect = _make_http_error(422)

        with pytest.raises(httpx.HTTPStatusError):
            await _invoke_with_retry(
                agent, {"input": "test"}, max_retries=2, backoff_base=0.0
            )

        assert agent.ainvoke.call_count == 1

    @pytest.mark.asyncio
    async def test_http_429_retries_with_backoff(self) -> None:
        """429 Rate Limit should be retried (transient)."""
        agent = AsyncMock()
        agent.ainvoke.side_effect = _make_http_error(429)

        with pytest.raises(httpx.HTTPStatusError):
            await _invoke_with_retry(
                agent, {"input": "test"}, max_retries=2, backoff_base=0.0
            )

        # Should retry: 1 initial + 2 retries = 3 total
        assert agent.ainvoke.call_count == 3

    @pytest.mark.asyncio
    async def test_http_500_retries_with_backoff(self) -> None:
        """500 Internal Server Error should be retried (transient)."""
        agent = AsyncMock()
        agent.ainvoke.side_effect = _make_http_error(500)

        with pytest.raises(httpx.HTTPStatusError):
            await _invoke_with_retry(
                agent, {"input": "test"}, max_retries=2, backoff_base=0.0
            )

        # Should retry: 1 initial + 2 retries = 3 total
        assert agent.ainvoke.call_count == 3

    @pytest.mark.asyncio
    async def test_http_502_retries(self) -> None:
        """502 Bad Gateway should be retried."""
        agent = AsyncMock()
        agent.ainvoke.side_effect = _make_http_error(502)

        with pytest.raises(httpx.HTTPStatusError):
            await _invoke_with_retry(
                agent, {"input": "test"}, max_retries=1, backoff_base=0.0
            )

        assert agent.ainvoke.call_count == 2

    @pytest.mark.asyncio
    async def test_http_429_succeeds_on_retry(self) -> None:
        """429 on first call, success on retry → returns result."""
        agent = AsyncMock()
        agent.ainvoke.side_effect = [
            _make_http_error(429),
            {"output": "success"},
        ]

        result = await _invoke_with_retry(
            agent, {"input": "test"}, max_retries=1, backoff_base=0.0
        )

        assert result == {"output": "success"}
        assert agent.ainvoke.call_count == 2


# ---------------------------------------------------------------------------
# Tests for per-target handler — HTTP error handling
# ---------------------------------------------------------------------------


class TestPerTargetHandlerHTTPErrors:
    """TASK-OR-007: Per-target handler catches httpx.HTTPStatusError."""

    @pytest.mark.asyncio
    async def test_http_400_rejects_target_not_crash(self) -> None:
        """HTTP 400 from _process_single_target → target rejected, pipeline continues."""
        targets = [_make_target("cat_a"), _make_target("cat_b")]
        config = _MinimalConfig()
        checkpoint = _make_checkpoint()
        output_manager = _make_output_manager()
        write_tool = MagicMock()

        call_count = 0

        async def side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise _make_http_error(400)
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

        # First target rejected via HTTPStatusError, second accepted
        assert result.rejected == 1
        assert result.accepted == 1
        assert result.total_targets == 2

        # Both targets were processed (pipeline did not crash)
        assert mock_process.call_count == 2

        # Rejection record written
        rejected_output = output_manager.rejected_fh.getvalue()
        assert rejected_output, "Expected rejection record to be written"
        record = json.loads(rejected_output.strip())
        assert "llm_failure" in record["reason"]

    @pytest.mark.asyncio
    async def test_http_500_rejects_target_not_crash(self) -> None:
        """HTTP 500 from _process_single_target → target rejected, pipeline continues."""
        targets = [_make_target("cat_a"), _make_target("cat_b")]
        config = _MinimalConfig()
        checkpoint = _make_checkpoint()
        output_manager = _make_output_manager()

        call_count = 0

        async def side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise _make_http_error(500)
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
                write_tool=MagicMock(),
            )

        assert result.rejected == 1
        assert result.accepted == 1
        assert result.total_targets == 2
        assert mock_process.call_count == 2

    @pytest.mark.asyncio
    async def test_all_http_errors_rejects_all_continues(self) -> None:
        """All targets raising HTTPStatusError → all rejected, no crash."""
        targets = [_make_target() for _ in range(3)]
        config = _MinimalConfig()
        checkpoint = _make_checkpoint()
        output_manager = _make_output_manager()

        with patch(
            "entrypoint.generation_loop._process_single_target",
            new_callable=AsyncMock,
            side_effect=_make_http_error(503),
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

        assert result.rejected == 3
        assert result.accepted == 0
        assert result.total_targets == 3
