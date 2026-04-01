"""Pydantic models for agent configuration.

Provides ``ModelConfig``, ``GenerationConfig``, ``ChunkingConfig``,
``LoggingConfig``, and the top-level ``AgentConfig`` model for
``agent-config.yaml``.

``ModelConfig`` is the foundational data model used by both Player and
Coach agent factories.  Validates provider enum, model identifier, endpoint
URL (required for local provider), and temperature range.

``AgentConfig`` composes all sub-models into a single validated configuration
object.  Uses ``ConfigDict(extra="ignore")`` for forward compatibility
(ASSUM-003), logging a warning when unknown fields are encountered.

References:
    - ``docs/design/models/DM-agent-config.md``
    - ``docs/design/contracts/API-entrypoint.md``
    - ``docs/design/contracts/API-generation.md``
"""

from __future__ import annotations

import logging
from typing import Literal
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# ModelConfig (shared with agent-factories — TASK-AF-001)
# ---------------------------------------------------------------------------


class ModelConfig(BaseModel):
    """Configuration for a single LLM agent (Player or Coach).

    Attributes:
        provider: LLM provider — ``"local"``, ``"anthropic"``, or ``"openai"``.
        model: Model identifier string (e.g. ``"nemotron-3-super-120b"``).
        endpoint: API endpoint URL.  Required and must be a valid URL when
            ``provider == "local"``.  Defaults to ``""`` (cloud providers
            use their default API endpoints).
        temperature: Sampling temperature, 0.0-2.0 inclusive.  Defaults to 0.7.
    """

    provider: Literal["local", "anthropic", "openai"]
    model: str = Field(min_length=1, description="Model identifier; must not be empty.")
    endpoint: str = Field(
        default="",
        description=(
            "API endpoint URL. Required when provider is 'local'; "
            "cloud providers use their default endpoint when empty."
        ),
    )
    temperature: float = Field(
        default=0.7,
        ge=0.0,
        le=2.0,
        description="Sampling temperature (0.0-2.0 inclusive).",
    )
    max_tokens: int = Field(
        default=4096,
        ge=1,
        description="Maximum tokens for model completions.  Defaults to 4096.",
    )

    @model_validator(mode="after")
    def validate_local_endpoint(self) -> ModelConfig:
        """Ensure ``endpoint`` is present and a valid URL when provider is ``local``.

        Raises:
            ValueError: If provider is ``"local"`` and endpoint is empty or
                not a valid HTTP(S) URL.
        """
        if self.provider != "local":
            return self

        if not self.endpoint:
            raise ValueError(
                "endpoint is required when provider is 'local'; "
                "provide a valid HTTP(S) URL (e.g. 'http://localhost:8000/v1')"
            )

        parsed = urlparse(self.endpoint)
        if parsed.scheme not in ("http", "https") or not parsed.netloc:
            raise ValueError(
                f"endpoint must be a valid HTTP(S) URL when provider is 'local', "
                f"got '{self.endpoint}'"
            )

        return self


# ---------------------------------------------------------------------------
# GenerationConfig
# ---------------------------------------------------------------------------


class GenerationConfig(BaseModel):
    """Generation loop parameters.

    Controls Player-Coach cycle limits and LLM resilience settings
    (ADR-ARCH-010).

    Attributes:
        max_turns: Max Player-Coach cycles before discarding a target.
            Must be >= 1.
        llm_retry_attempts: Number of retries per LLM call on transient failure.
        llm_retry_backoff: Exponential backoff base in seconds.
        llm_timeout: Per-LLM-call timeout in seconds.
        target_timeout: Per-target timeout in seconds.
        max_write_attempts: Max write_output retries per target before rejection.
        max_format_retries: Max format correction retries per target before
            rejection (TASK-FPF1-003).
    """

    model_config = ConfigDict(extra="ignore")

    max_turns: int = Field(
        default=3,
        ge=1,
        description="Max Player-Coach cycles before discard; must be >= 1.",
    )
    llm_retry_attempts: int = Field(
        default=3,
        ge=0,
        description="Retries per LLM call on transient failure (ADR-ARCH-010).",
    )
    llm_retry_backoff: float = Field(
        default=2.0,
        ge=0.0,
        description="Exponential backoff base in seconds (ADR-ARCH-010).",
    )
    llm_timeout: int = Field(
        default=300,
        ge=1,
        description="Per-LLM-call timeout in seconds (ADR-ARCH-010).",
    )
    target_timeout: int = Field(
        default=600,
        ge=1,
        description="Per-target timeout in seconds (ADR-ARCH-010).",
    )
    max_write_attempts: int = Field(
        default=3,
        ge=1,
        description="Max write_output retries per target before rejection (TASK-TRF-006).",
    )
    max_format_retries: int = Field(
        default=3,
        ge=0,
        description="Max format correction retries per target before rejection (TASK-FPF1-003).",
    )

    @field_validator("max_turns", mode="after")
    @classmethod
    def validate_max_turns(cls, v: int) -> int:
        """Provide a clear error message when max_turns is below minimum."""
        if v < 1:
            raise ValueError(
                f"max_turns must be >= 1, got {v}; "
                "at least one Player-Coach cycle is required"
            )
        return v


# ---------------------------------------------------------------------------
# ChunkingConfig
# ---------------------------------------------------------------------------


class ChunkingConfig(BaseModel):
    """Ingestion chunking parameters.

    Attributes:
        chunk_size: Tokens per chunk.  Must be > 0.
        overlap: Token overlap between chunks.  Must be >= 0 and < chunk_size.
    """

    model_config = ConfigDict(extra="ignore")

    chunk_size: int = Field(
        default=512,
        gt=0,
        description="Tokens per chunk; must be > 0.",
    )
    overlap: int = Field(
        default=64,
        ge=0,
        description="Token overlap between chunks; must be >= 0 and < chunk_size.",
    )

    @model_validator(mode="after")
    def validate_overlap_less_than_chunk_size(self) -> ChunkingConfig:
        """Ensure overlap is strictly less than chunk_size.

        Raises:
            ValueError: If overlap >= chunk_size.
        """
        if self.overlap >= self.chunk_size:
            raise ValueError(
                f"overlap must be less than chunk_size, "
                f"got overlap={self.overlap} with chunk_size={self.chunk_size}"
            )
        return self


# ---------------------------------------------------------------------------
# LoggingConfig
# ---------------------------------------------------------------------------

_VALID_LOG_LEVELS = frozenset({"DEBUG", "INFO", "WARNING", "ERROR"})


class LoggingConfig(BaseModel):
    """Logging configuration.

    Attributes:
        level: Log level — one of ``DEBUG``, ``INFO``, ``WARNING``, ``ERROR``.
        format: Log format — must be ``"json"`` per ADR-ARCH-007.
    """

    model_config = ConfigDict(extra="ignore")

    level: str = Field(
        default="INFO",
        description="Log level; must be DEBUG, INFO, WARNING, or ERROR.",
    )
    format: str = Field(
        default="json",
        description="Log format; must be 'json' (ADR-ARCH-007).",
    )

    @field_validator("level", mode="after")
    @classmethod
    def validate_level(cls, v: str) -> str:
        """Restrict level to standard Python logging levels.

        Raises:
            ValueError: If level is not one of DEBUG, INFO, WARNING, ERROR.
        """
        if v not in _VALID_LOG_LEVELS:
            raise ValueError(
                f"level must be one of {sorted(_VALID_LOG_LEVELS)}, got '{v}'"
            )
        return v

    @field_validator("format", mode="after")
    @classmethod
    def validate_format(cls, v: str) -> str:
        """Enforce JSON-only log format per ADR-ARCH-007.

        Raises:
            ValueError: If format is not ``"json"``.
        """
        if v != "json":
            raise ValueError(
                f"format must be 'json' (ADR-ARCH-007), got '{v}'"
            )
        return v


# ---------------------------------------------------------------------------
# AgentConfig (top-level)
# ---------------------------------------------------------------------------


class AgentConfig(BaseModel):
    """Top-level configuration model for ``agent-config.yaml``.

    Composes all sub-configuration models into a single validated object.
    Uses ``ConfigDict(extra="ignore")`` for forward compatibility (ASSUM-003);
    unknown fields are silently dropped but a warning is logged.

    Attributes:
        domain: Domain directory name under ``domains/``.  Required.
        player: Player agent model configuration.
        coach: Coach agent model configuration.
        generation: Generation loop parameters.
        chunking: Ingestion chunking parameters.
        logging: Logging configuration.
    """

    model_config = ConfigDict(extra="ignore")

    domain: str = Field(
        min_length=1,
        description="Domain directory name under domains/; required.",
    )
    player: ModelConfig
    coach: ModelConfig
    generation: GenerationConfig = Field(default_factory=GenerationConfig)
    chunking: ChunkingConfig = Field(default_factory=ChunkingConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)

    def __init__(self, **data: object) -> None:
        """Log a warning for any unknown fields before Pydantic ignores them."""
        known_fields = set(AgentConfig.model_fields.keys())
        provided_fields = set(data.keys())
        unknown = provided_fields - known_fields
        if unknown:
            logger.warning(
                "Unknown fields in AgentConfig will be ignored: %s",
                ", ".join(sorted(unknown)),
            )
        super().__init__(**data)


__all__ = [
    "AgentConfig",
    "ChunkingConfig",
    "GenerationConfig",
    "LoggingConfig",
    "ModelConfig",
]
