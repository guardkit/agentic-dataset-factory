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
        grounded: Whether the Player retrieves from a RAG corpus.  ``True``
            (default) keeps the book-grounded modes (architect, tutor)
            unchanged.  ``False`` enables the no-book **generative** mode (PO
            Phase 1): the Player is built with no rag_retrieval tool, the
            ChromaDB readiness check is skipped, and no "Curriculum Context"
            is pre-fetched or injected.
        limit: Optional cap on the number of expanded targets to process.
            ``None`` (default) processes every target.  Set a small value
            (e.g. 8) to run a smoke over a subset without editing GOAL.md's
            count table.  Applied after target expansion, before the
            ``start_index`` resume slice.  When set, the expanded targets are
            round-robin interleaved across categories first, so a small cap
            spans all categories rather than only the first.
        modes: Optional list of generation modes to round-robin across targets
            (by absolute index), injected into the Player message so a
            corpus-free generative run deliberately spans multiple no-corpus
            PO modes (e.g. idea/greenfield/evolve/impact/scope) instead of
            defaulting every example to one mode.  ``None`` (default) leaves
            mode selection to the Player (grounded architect/tutor unchanged).
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
    grounded: bool = Field(
        default=True,
        description=(
            "Whether the Player retrieves from a RAG corpus. False enables the "
            "no-book generative mode (no rag tool, no ChromaDB check, no "
            "pre-fetched curriculum context)."
        ),
    )
    limit: int | None = Field(
        default=None,
        ge=1,
        description=(
            "Optional cap on expanded targets processed (smoke runs). None "
            "processes every target."
        ),
    )
    modes: list[str] | None = Field(
        default=None,
        description=(
            "Optional generation modes to round-robin across targets and "
            "inject into the Player message (corpus-free generative runs). "
            "None leaves mode choice to the Player."
        ),
    )
    require_fenced_json: bool = Field(
        default=False,
        description=(
            "When True, the pre-Coach format gate also requires the last "
            "assistant message to contain a parseable ```json fenced object "
            "(strict json.loads) — for domains whose assistant content is a "
            "```json block after <think> (e.g. product-owner ProductRoadmap). "
            "False (default) leaves prose-output domains (architect/tutor) "
            "unaffected."
        ),
    )
    output_validator: str | None = Field(
        default=None,
        description=(
            "Optional per-domain output validator hook (2026-08-18, Rich's "
            "word): '<path/to/module.py>:<callable>' relative to the project "
            "root, or '<dotted.module>:<callable>'. The callable takes "
            "(assistant_content: str, metadata: dict) and returns "
            "(ok: bool, error_text: str); the pre-Coach format gate calls it "
            "on the last assistant message of every Player turn and a row is "
            "accepted ONLY if it validates — a failing row takes the same "
            "retry/reject path as malformed JSON with error_text in the "
            "rejection reason. None (default) leaves every domain unchanged. "
            "E.g. domains/product-owner/po_schemas.py:validate_assistant_content."
        ),
    )

    @field_validator("output_validator", mode="after")
    @classmethod
    def validate_output_validator(cls, v: str | None) -> str | None:
        """Require the '<module>:<callable>' shape (both halves non-empty)."""
        if v is None:
            return v
        spec = v.strip()
        if not spec:
            return None
        module_part, sep, func_part = spec.rpartition(":")
        if not sep or not module_part.strip() or not func_part.strip():
            raise ValueError(
                "output_validator must be '<path/to/module.py>:<callable>' or "
                f"'<dotted.module>:<callable>', got {v!r}"
            )
        return spec

    @field_validator("modes", mode="after")
    @classmethod
    def validate_modes(cls, v: list[str] | None) -> list[str] | None:
        """Reject an empty modes list (None disables; a list must be non-empty)."""
        if v is not None and len(v) == 0:
            raise ValueError(
                "modes must be a non-empty list when set, or omitted/null to "
                "leave mode selection to the Player"
            )
        return v

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
# BatchConfig (two-window batched-legs mode — ADR-ARCH-006 dated note)
# ---------------------------------------------------------------------------


class BatchConfig(BaseModel):
    """Two-window batched-legs mode configuration (opt-in, additive).

    Batch mode splits a run into windows at the orchestration level:
    window 1 runs ALL Player/teacher legs (outputs checkpointed per row),
    window 2 runs ALL Coach legs plus the acceptance/write path.  The run
    stops at each window boundary so the OPERATOR can switch the serving
    posture (needed when the teacher and the Coach fleet cannot co-reside
    — e.g. a two-node tensor-parallel teacher that drains llama-swap while
    it serves).  Sequential mode remains the default; existing domains are
    unaffected when this block is absent.

    Attributes:
        enabled: Engage batch mode from config (equivalent to the
            ``--batch`` CLI flag).  Defaults to ``False`` — sequential.
        teacher: Optional window-1 Player/teacher seat model configuration
            (the same ``ModelConfig`` seam as ``player``/``coach``; no code
            assumes model names).  ``None`` uses the ``player`` block.
        max_passes: Optional cap on Player-Coach passes per row (one pass =
            window 1 + window 2).  ``None`` uses ``generation.max_turns``,
            matching sequential revision semantics.
        operator_note: Optional free-text appended to the window-boundary
            operator instructions (e.g. the serving runbook to follow).
    """

    model_config = ConfigDict(extra="ignore")

    enabled: bool = Field(
        default=False,
        description=(
            "Engage two-window batch mode. False (default) keeps the "
            "sequential loop (ADR-ARCH-006)."
        ),
    )
    teacher: ModelConfig | None = Field(
        default=None,
        description=(
            "Window-1 Player/teacher seat model config; None uses the "
            "player block (same ModelConfig seam)."
        ),
    )
    max_passes: int | None = Field(
        default=None,
        ge=1,
        description=(
            "Max Player-Coach passes per row in batch mode; None uses "
            "generation.max_turns."
        ),
    )
    operator_note: str = Field(
        default="",
        description=(
            "Free text appended to window-boundary operator instructions "
            "(e.g. which serving runbook governs the drain/revive acts)."
        ),
    )


# ---------------------------------------------------------------------------
# GatesConfig (per-sample dataset gates — fabrication quote gate + dedup)
# ---------------------------------------------------------------------------


class QuoteGateConfig(BaseModel):
    """Per-sample quote-verification (fabrication) gate configuration.

    The gate extracts quoted spans from an accepted sample's assistant
    turns and verifies each against the sample's subject corpus (windowed
    similarity — see ``gates.quote_gate``).  A failed sample routes back
    into the revise loop with the fabricated span named in the Coach
    feedback.  Subjects with NO configured corpus are counted
    ``unverifiable`` (loud in the gate report) — never silently blocked.

    Attributes:
        enabled: Engage the quote gate.  Defaults to ``False`` (opt-in
            even within a ``gates:`` block — it needs corpus stores).
        corpus_stores: Mapping of subject name to a ChromaDB persist
            directory (the directory containing ``chroma.sqlite3``).
            Read READ-ONLY via sqlite ``immutable=1`` — never a live
            service.
        subject_key: Metadata key on the generated example that names its
            subject.  Defaults to ``"subject"``.
        default_subject: Subject assumed when the metadata key is absent
            (e.g. ``"english"`` for a single-subject domain).  ``None``
            (default) counts such samples unverifiable.
        match_threshold: Windowed-similarity ratio at or above which a
            quoted span counts as verified.  Defaults to 0.95.
        min_quote_words: Spans shorter than this many words are not
            treated as quotations.  Defaults to 4.
    """

    model_config = ConfigDict(extra="ignore")

    enabled: bool = Field(
        default=False,
        description="Engage the per-sample quote-verification gate.",
    )
    corpus_stores: dict[str, str] = Field(
        default_factory=dict,
        description=(
            "Subject name -> ChromaDB persist directory (read-only sqlite "
            "immutable=1; never a live service)."
        ),
    )
    subject_key: str = Field(
        default="subject",
        min_length=1,
        description="Example-metadata key naming the sample's subject.",
    )
    default_subject: str | None = Field(
        default=None,
        description=(
            "Subject assumed when the metadata key is absent; None counts "
            "such samples unverifiable."
        ),
    )
    match_threshold: float = Field(
        default=0.95,
        gt=0.0,
        le=1.0,
        description="Windowed-similarity verification threshold.",
    )
    min_quote_words: int = Field(
        default=4,
        ge=1,
        description="Minimum words for a span to count as a quotation.",
    )


class DedupConfig(BaseModel):
    """Duplicate-detection wiring for the live loop.

    Wires the (previously orphaned) ``synthesis.validator.DuplicateDetector``
    into the orchestrator choke point.  Defaults to ``True`` — ON for any
    run that declares a ``gates:`` block; runs without the block are
    entirely unaffected (``AgentConfig.gates`` defaults to ``None``).
    """

    model_config = ConfigDict(extra="ignore")

    enabled: bool = Field(
        default=True,
        description=(
            "Reject duplicate assistant content at the choke point "
            "(default ON within a gates block)."
        ),
    )


class GatesConfig(BaseModel):
    """Per-sample gates applied between Coach acceptance and the write.

    Absent from ``agent-config.yaml`` (the default), NO gate machinery is
    constructed and both loops behave exactly as before — existing
    domains are byte-compatible.  Declaring the block turns dedup on by
    default; the quote gate is opted into explicitly with its corpus
    stores.

    Attributes:
        quote_gate: Per-sample quote-verification gate (opt-in).
        dedup: Duplicate detection (default ON within this block).
    """

    model_config = ConfigDict(extra="ignore")

    quote_gate: QuoteGateConfig = Field(default_factory=QuoteGateConfig)
    dedup: DedupConfig = Field(default_factory=DedupConfig)


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
        batch: Two-window batched-legs mode (opt-in; sequential default).
        gates: Per-sample gates (quote-verification + dedup).  ``None``
            (default — block absent) constructs no gate machinery, keeping
            existing domains byte-compatible.
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
    batch: BatchConfig = Field(default_factory=BatchConfig)
    gates: GatesConfig | None = Field(
        default=None,
        description=(
            "Per-sample gates block; absent (None) leaves both loops "
            "exactly as before."
        ),
    )
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
    "BatchConfig",
    "ChunkingConfig",
    "DedupConfig",
    "GatesConfig",
    "GenerationConfig",
    "LoggingConfig",
    "ModelConfig",
    "QuoteGateConfig",
]
