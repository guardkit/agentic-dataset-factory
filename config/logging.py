"""Structured JSON logging setup (ADR-ARCH-007).

Provides ``configure_logging()`` to install a JSON formatter on the root
logger, ensuring all log output is machine-readable structured JSON.

Called as step 2 of the startup sequence defined in
``docs/design/contracts/API-entrypoint.md``.

Example log output::

    {"level": "INFO", "message": "Starting generation"}
    {"event": "startup", "domain": "gcse-english-tutor", "targets": 1000}

References:
    - ``docs/architecture/decisions/ADR-ARCH-007-structured-json-logging.md``
    - ``docs/design/contracts/API-entrypoint.md`` (Progress Logging section)
"""

from __future__ import annotations

import json
import logging
from typing import Any

from config.models import LoggingConfig


class JsonFormatter(logging.Formatter):
    """Format log records as single-line JSON strings.

    Every log line is emitted as a JSON object with at least ``level``
    and ``message`` keys.  Additional context can be injected by passing
    an ``extra`` dict when logging::

        logger.info("startup", extra={"extra": {"event": "startup", "domain": "gcse"}})

    The ``extra`` dict values are merged into the top-level JSON payload,
    matching the progress logging format defined in API-entrypoint.md::

        {"event": "startup", "domain": "gcse-english-tutor", "targets": 1000}
    """

    def format(self, record: logging.LogRecord) -> str:  # noqa: A003
        """Return the log record as a single-line JSON string.

        Args:
            record: The log record to format.

        Returns:
            A JSON-serialised string containing ``level``, ``message``,
            and any extra fields.
        """
        payload: dict[str, Any] = {
            "level": record.levelname,
            "message": record.getMessage(),
        }
        if hasattr(record, "extra"):
            payload.update(record.extra)
        return json.dumps(payload, default=str)


def configure_logging(config: LoggingConfig) -> None:
    """Install structured JSON logging on the root logger.

    Replaces all existing root handlers with a single
    :class:`logging.StreamHandler` using :class:`JsonFormatter`,
    and sets the root logger level from *config*.

    This function is idempotent — calling it multiple times simply
    reconfigures the root logger.

    Args:
        config: A validated ``LoggingConfig`` instance.  The ``level``
            field determines the root logger level (DEBUG, INFO,
            WARNING, or ERROR).

    Example::

        from config.models import LoggingConfig

        configure_logging(LoggingConfig(level="DEBUG"))
    """
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(getattr(logging, config.level))


__all__ = ["JsonFormatter", "configure_logging"]
