"""Config loader — yaml.safe_load + Pydantic parsing.

Loads ``agent-config.yaml`` using ``yaml.safe_load`` (ASSUM-005 — rejects
custom tags) and parses it into the Pydantic ``AgentConfig`` model.

References:
    - ``docs/design/contracts/API-entrypoint.md`` (Python Contract: Config Loading)
    - ``features/entrypoint/entrypoint.feature`` (BDD scenarios)
    - ASSUM-005: yaml.safe_load security
"""

from __future__ import annotations

import logging
from pathlib import Path

import yaml
from pydantic import ValidationError

from config.models import AgentConfig

logger = logging.getLogger(__name__)


class ConfigValidationError(Exception):
    """Configuration validation failed.

    Wraps a Pydantic ``ValidationError`` with a user-friendly message
    describing what went wrong during config parsing.  The original
    ``ValidationError`` is chained via ``raise ... from`` so callers
    can inspect the underlying field-level errors if needed.
    """


def load_config(path: Path = Path("agent-config.yaml")) -> AgentConfig:
    """Load and validate agent configuration from a YAML file.

    Reads the file at *path*, parses it with ``yaml.safe_load`` (security
    — ASSUM-005), and validates the resulting dict against the Pydantic
    ``AgentConfig`` model.

    Args:
        path: Path to the YAML configuration file.
            Defaults to ``Path("agent-config.yaml")``.

    Returns:
        A fully validated ``AgentConfig`` instance.

    Raises:
        FileNotFoundError: If *path* does not exist.
        ConfigValidationError: If the YAML content fails Pydantic
            validation.  The original ``ValidationError`` is chained
            as the ``__cause__``.
    """
    if not path.exists():
        raise FileNotFoundError(
            f"Configuration file not found: {path}  "
            f"Ensure the file exists at the expected location."
        )

    raw_text = path.read_text(encoding="utf-8")

    try:
        data = yaml.safe_load(raw_text)
    except yaml.YAMLError as exc:
        raise ConfigValidationError(f"Failed to parse YAML from {path}: {exc}") from exc

    if not isinstance(data, dict):
        raise ConfigValidationError(
            f"Configuration file {path} must contain a YAML mapping, got {type(data).__name__}"
        )

    try:
        return AgentConfig.model_validate(data)
    except ValidationError as exc:
        error_count = exc.error_count()
        error_summary = "; ".join(
            f"{'.'.join(str(loc) for loc in e['loc'])}: {e['msg']}" for e in exc.errors()
        )
        raise ConfigValidationError(
            f"Configuration validation failed with {error_count} error(s) "
            f"in {path}: {error_summary}"
        ) from exc


__all__ = [
    "ConfigValidationError",
    "load_config",
]
