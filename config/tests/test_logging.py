"""Tests for config.logging — structured JSON logging (ADR-ARCH-007).

Covers all acceptance criteria for TASK-EP-003:

- AC-001: Structured JSON logging active after ``configure_logging()`` call
- AC-002: Log level set from config
- AC-003: JSON format output on all log lines
- AC-004: Works with Python standard ``logging`` module
"""

from __future__ import annotations

import json
import logging
from typing import Any

import pytest

from config.logging import JsonFormatter, configure_logging
from config.models import LoggingConfig


# ---------------------------------------------------------------------------
# AC-001: Structured JSON logging active after configure_logging() call
# ---------------------------------------------------------------------------


class TestConfigureLoggingActivation:
    """AC-001: Structured JSON logging is active after configure_logging()."""

    def test_root_logger_has_json_formatter_after_configure(self) -> None:
        """Root logger handler uses JsonFormatter after configuration."""
        configure_logging(LoggingConfig())
        root = logging.getLogger()
        assert len(root.handlers) == 1
        handler = root.handlers[0]
        assert isinstance(handler.formatter, JsonFormatter)

    def test_root_logger_has_stream_handler_after_configure(self) -> None:
        """Root logger uses StreamHandler after configuration."""
        configure_logging(LoggingConfig())
        root = logging.getLogger()
        assert len(root.handlers) == 1
        assert isinstance(root.handlers[0], logging.StreamHandler)

    def test_previous_handlers_replaced(self) -> None:
        """Any pre-existing handlers are replaced, not accumulated."""
        root = logging.getLogger()
        # Add a dummy handler before configuring
        dummy = logging.StreamHandler()
        root.addHandler(dummy)
        pre_count = len(root.handlers)

        configure_logging(LoggingConfig())

        assert len(root.handlers) == 1
        assert root.handlers[0] is not dummy

    def test_idempotent_reconfiguration(self) -> None:
        """Calling configure_logging() twice results in exactly one handler."""
        configure_logging(LoggingConfig())
        configure_logging(LoggingConfig(level="DEBUG"))

        root = logging.getLogger()
        assert len(root.handlers) == 1
        assert isinstance(root.handlers[0].formatter, JsonFormatter)


# ---------------------------------------------------------------------------
# AC-002: Log level set from config
# ---------------------------------------------------------------------------


class TestLogLevelFromConfig:
    """AC-002: Root logger level is set from LoggingConfig.level."""

    @pytest.mark.parametrize(
        ("config_level", "expected_level"),
        [
            ("DEBUG", logging.DEBUG),
            ("INFO", logging.INFO),
            ("WARNING", logging.WARNING),
            ("ERROR", logging.ERROR),
        ],
        ids=["debug", "info", "warning", "error"],
    )
    def test_level_set_from_config(
        self, config_level: str, expected_level: int
    ) -> None:
        """BDD: 'Structured logging is configured from the config file'."""
        configure_logging(LoggingConfig(level=config_level))
        root = logging.getLogger()
        assert root.level == expected_level

    def test_default_level_is_info(self) -> None:
        """Default LoggingConfig sets root logger to INFO."""
        configure_logging(LoggingConfig())
        root = logging.getLogger()
        assert root.level == logging.INFO

    def test_debug_level_allows_debug_messages(self, capfd: pytest.CaptureFixture[str]) -> None:
        """When level is DEBUG, debug messages are emitted."""
        configure_logging(LoggingConfig(level="DEBUG"))
        test_logger = logging.getLogger("test.debug_check")
        test_logger.debug("debug visible")

        captured = capfd.readouterr()
        assert "debug visible" in captured.err

    def test_error_level_suppresses_info_messages(self, capfd: pytest.CaptureFixture[str]) -> None:
        """When level is ERROR, info messages are suppressed."""
        configure_logging(LoggingConfig(level="ERROR"))
        test_logger = logging.getLogger("test.error_check")
        test_logger.info("should not appear")

        captured = capfd.readouterr()
        assert "should not appear" not in captured.err


# ---------------------------------------------------------------------------
# AC-003: JSON format output on all log lines
# ---------------------------------------------------------------------------


class TestJsonFormatOutput:
    """AC-003: All log lines are valid JSON with expected fields."""

    def test_log_output_is_valid_json(self, capfd: pytest.CaptureFixture[str]) -> None:
        """Every log line is parseable as JSON."""
        configure_logging(LoggingConfig())
        test_logger = logging.getLogger("test.json_output")
        test_logger.info("test message")

        captured = capfd.readouterr()
        line = captured.err.strip()
        parsed = json.loads(line)
        assert isinstance(parsed, dict)

    def test_log_output_contains_level_field(self, capfd: pytest.CaptureFixture[str]) -> None:
        """JSON output includes 'level' key."""
        configure_logging(LoggingConfig())
        test_logger = logging.getLogger("test.level_field")
        test_logger.warning("test warning")

        captured = capfd.readouterr()
        parsed = json.loads(captured.err.strip())
        assert parsed["level"] == "WARNING"

    def test_log_output_contains_message_field(self, capfd: pytest.CaptureFixture[str]) -> None:
        """JSON output includes 'message' key."""
        configure_logging(LoggingConfig())
        test_logger = logging.getLogger("test.message_field")
        test_logger.info("hello world")

        captured = capfd.readouterr()
        parsed = json.loads(captured.err.strip())
        assert parsed["message"] == "hello world"

    def test_extra_fields_merged_into_json(self, capfd: pytest.CaptureFixture[str]) -> None:
        """Extra dict values are merged into top-level JSON payload.

        Matches API-entrypoint.md progress logging format::

            {"event": "startup", "domain": "gcse-english-tutor", "targets": 1000}
        """
        configure_logging(LoggingConfig())
        test_logger = logging.getLogger("test.extra_fields")
        test_logger.info(
            "startup",
            extra={"extra": {"event": "startup", "domain": "gcse-english-tutor", "targets": 1000}},
        )

        captured = capfd.readouterr()
        parsed = json.loads(captured.err.strip())
        assert parsed["event"] == "startup"
        assert parsed["domain"] == "gcse-english-tutor"
        assert parsed["targets"] == 1000

    def test_multiple_log_lines_all_valid_json(self, capfd: pytest.CaptureFixture[str]) -> None:
        """Multiple log lines are each independently valid JSON."""
        configure_logging(LoggingConfig())
        test_logger = logging.getLogger("test.multi_line")
        test_logger.info("first")
        test_logger.warning("second")
        test_logger.error("third")

        captured = capfd.readouterr()
        lines = [ln for ln in captured.err.strip().split("\n") if ln.strip()]
        assert len(lines) == 3
        for line in lines:
            parsed = json.loads(line)
            assert "level" in parsed
            assert "message" in parsed

    @pytest.mark.parametrize(
        ("level_method", "expected_level"),
        [
            ("debug", "DEBUG"),
            ("info", "INFO"),
            ("warning", "WARNING"),
            ("error", "ERROR"),
        ],
        ids=["debug", "info", "warning", "error"],
    )
    def test_all_log_levels_produce_json(
        self,
        level_method: str,
        expected_level: str,
        capfd: pytest.CaptureFixture[str],
    ) -> None:
        """Every log level produces valid JSON with correct level field."""
        configure_logging(LoggingConfig(level="DEBUG"))
        test_logger = logging.getLogger("test.all_levels")
        getattr(test_logger, level_method)(f"{level_method} message")

        captured = capfd.readouterr()
        # Find the line for our specific message
        for line in captured.err.strip().split("\n"):
            parsed = json.loads(line)
            if f"{level_method} message" in parsed.get("message", ""):
                assert parsed["level"] == expected_level
                return
        pytest.fail(f"Log line for {level_method} not found in output")


# ---------------------------------------------------------------------------
# AC-004: Works with Python standard logging module
# ---------------------------------------------------------------------------


class TestStandardLoggingModuleIntegration:
    """AC-004: configure_logging works with Python standard logging module."""

    def test_uses_root_logger(self) -> None:
        """configure_logging configures the root logger."""
        configure_logging(LoggingConfig())
        root = logging.getLogger()
        assert len(root.handlers) == 1

    def test_child_loggers_inherit_json_format(self, capfd: pytest.CaptureFixture[str]) -> None:
        """Child loggers inherit the JSON formatter from root."""
        configure_logging(LoggingConfig())
        child = logging.getLogger("myapp.module.submodule")
        child.info("child message")

        captured = capfd.readouterr()
        parsed = json.loads(captured.err.strip())
        assert parsed["message"] == "child message"
        assert parsed["level"] == "INFO"

    def test_getlogger_pattern_works(self, capfd: pytest.CaptureFixture[str]) -> None:
        """Standard logging.getLogger(__name__) pattern emits JSON."""
        configure_logging(LoggingConfig())
        module_logger = logging.getLogger("config.tests.test_logging")
        module_logger.info("module log")

        captured = capfd.readouterr()
        parsed = json.loads(captured.err.strip())
        assert parsed["message"] == "module log"

    def test_log_record_string_formatting(self, capfd: pytest.CaptureFixture[str]) -> None:
        """Standard %-style formatting in log messages works."""
        configure_logging(LoggingConfig())
        test_logger = logging.getLogger("test.format")
        test_logger.info("Count: %d items at %.2f each", 5, 3.14)

        captured = capfd.readouterr()
        parsed = json.loads(captured.err.strip())
        assert parsed["message"] == "Count: 5 items at 3.14 each"


# ---------------------------------------------------------------------------
# JsonFormatter unit tests
# ---------------------------------------------------------------------------


class TestJsonFormatter:
    """Unit tests for the JsonFormatter class."""

    def _make_record(
        self,
        message: str = "test",
        level: int = logging.INFO,
        extra: dict[str, Any] | None = None,
    ) -> logging.LogRecord:
        """Create a LogRecord for testing."""
        record = logging.LogRecord(
            name="test",
            level=level,
            pathname="test.py",
            lineno=1,
            msg=message,
            args=(),
            exc_info=None,
        )
        if extra is not None:
            record.extra = extra  # type: ignore[attr-defined]
        return record

    def test_format_returns_valid_json(self) -> None:
        formatter = JsonFormatter()
        record = self._make_record()
        result = formatter.format(record)
        parsed = json.loads(result)
        assert isinstance(parsed, dict)

    def test_format_includes_level(self) -> None:
        formatter = JsonFormatter()
        record = self._make_record(level=logging.ERROR)
        result = formatter.format(record)
        parsed = json.loads(result)
        assert parsed["level"] == "ERROR"

    def test_format_includes_message(self) -> None:
        formatter = JsonFormatter()
        record = self._make_record(message="hello world")
        result = formatter.format(record)
        parsed = json.loads(result)
        assert parsed["message"] == "hello world"

    def test_format_merges_extra_fields(self) -> None:
        formatter = JsonFormatter()
        record = self._make_record(
            extra={"event": "startup", "domain": "gcse"}
        )
        result = formatter.format(record)
        parsed = json.loads(result)
        assert parsed["event"] == "startup"
        assert parsed["domain"] == "gcse"

    def test_format_without_extra_has_only_level_and_message(self) -> None:
        formatter = JsonFormatter()
        record = self._make_record()
        result = formatter.format(record)
        parsed = json.loads(result)
        assert set(parsed.keys()) == {"level", "message"}

    def test_format_output_is_single_line(self) -> None:
        formatter = JsonFormatter()
        record = self._make_record(message="multi\nline\nmessage")
        result = formatter.format(record)
        assert "\n" not in result

    def test_format_handles_non_serialisable_extra(self) -> None:
        """Non-JSON-serialisable extras use str() fallback."""
        formatter = JsonFormatter()
        record = self._make_record(
            extra={"timestamp": object()}
        )
        result = formatter.format(record)
        # Should not raise; default=str handles it
        parsed = json.loads(result)
        assert "timestamp" in parsed


# ---------------------------------------------------------------------------
# Progress logging format compatibility (API-entrypoint.md)
# ---------------------------------------------------------------------------


class TestProgressLoggingFormat:
    """Verify log output matches API-entrypoint.md progress logging examples."""

    def test_startup_event_format(self, capfd: pytest.CaptureFixture[str]) -> None:
        """Match: {"event": "startup", "domain": "gcse-english-tutor", "targets": 1000}."""
        configure_logging(LoggingConfig())
        test_logger = logging.getLogger("test.progress.startup")
        test_logger.info(
            "startup",
            extra={"extra": {
                "event": "startup",
                "domain": "gcse-english-tutor",
                "targets": 1000,
            }},
        )

        captured = capfd.readouterr()
        parsed = json.loads(captured.err.strip())
        assert parsed["event"] == "startup"
        assert parsed["domain"] == "gcse-english-tutor"
        assert parsed["targets"] == 1000

    def test_progress_event_format(self, capfd: pytest.CaptureFixture[str]) -> None:
        """Match: {"event": "progress", "accepted": 500, ...}."""
        configure_logging(LoggingConfig())
        test_logger = logging.getLogger("test.progress.progress")
        test_logger.info(
            "progress",
            extra={"extra": {
                "event": "progress",
                "accepted": 500,
                "rejected": 23,
                "remaining": 477,
                "elapsed_hours": 12.5,
            }},
        )

        captured = capfd.readouterr()
        parsed = json.loads(captured.err.strip())
        assert parsed["event"] == "progress"
        assert parsed["accepted"] == 500
        assert parsed["rejected"] == 23

    def test_complete_event_format(self, capfd: pytest.CaptureFixture[str]) -> None:
        """Match: {"event": "complete", "accepted": 977, ...}."""
        configure_logging(LoggingConfig())
        test_logger = logging.getLogger("test.progress.complete")
        test_logger.info(
            "complete",
            extra={"extra": {
                "event": "complete",
                "accepted": 977,
                "rejected": 23,
                "total_turns": 2154,
                "elapsed_hours": 25.1,
            }},
        )

        captured = capfd.readouterr()
        parsed = json.loads(captured.err.strip())
        assert parsed["event"] == "complete"
        assert parsed["accepted"] == 977
        assert parsed["total_turns"] == 2154


# ---------------------------------------------------------------------------
# Fixture: Reset root logger after each test
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _reset_root_logger() -> None:
    """Reset the root logger to avoid test pollution."""
    root = logging.getLogger()
    original_handlers = root.handlers[:]
    original_level = root.level
    yield  # type: ignore[misc]
    root.handlers = original_handlers
    root.setLevel(original_level)
