"""Pydantic validation models for LangChain tool parameters.

This module provides strict validation models used by LangChain tools for
RAG retrieval, training example construction, and example metadata. All
models produce clear, actionable validation error messages suitable for
D7 error strings.

**No runtime dependency on ChromaDB.** Any ChromaDB interaction must use
the lazy-import pattern (import inside the function that needs it).
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator


# ---------------------------------------------------------------------------
# Message model (ShareGPT format)
# ---------------------------------------------------------------------------


class Message(BaseModel):
    """A single chat message in ShareGPT format.

    Attributes:
        role: One of ``"system"``, ``"user"``, or ``"assistant"``.
        content: Non-empty message text.
    """

    role: Literal["system", "user", "assistant"]
    content: str = Field(
        min_length=1,
        description="Message text; must not be empty.",
    )


# ---------------------------------------------------------------------------
# ExampleMetadata
# ---------------------------------------------------------------------------


class ExampleMetadata(BaseModel):
    """Metadata describing a training example's pedagogical intent and provenance.

    Attributes:
        layer: Must be ``"behaviour"`` or ``"knowledge"``.
        type: Must be ``"reasoning"`` or ``"direct"``.
        source: Data provenance label. Defaults to ``"synthetic"``.
    """

    layer: Literal["behaviour", "knowledge"] = Field(
        description=(
            "Training layer; must be 'behaviour' or 'knowledge'."
        ),
    )
    type: Literal["reasoning", "direct"] = Field(
        description=(
            "Example type; must be 'reasoning' or 'direct'."
        ),
    )
    source: str = Field(
        default="synthetic",
        min_length=1,
        description="Data provenance label.",
    )

    # --- custom validators for clear error messages ---

    @field_validator("layer", mode="before")
    @classmethod
    def validate_layer(cls, v: str) -> str:
        """Reject invalid layer values with an actionable message."""
        allowed = {"behaviour", "knowledge"}
        if v not in allowed:
            raise ValueError(
                f"Invalid layer '{v}'; must be one of {sorted(allowed)}"
            )
        return v

    @field_validator("type", mode="before")
    @classmethod
    def validate_type(cls, v: str) -> str:
        """Reject invalid type values with an actionable message."""
        allowed = {"reasoning", "direct"}
        if v not in allowed:
            raise ValueError(
                f"Invalid type '{v}'; must be one of {sorted(allowed)}"
            )
        return v


# ---------------------------------------------------------------------------
# TrainingExample
# ---------------------------------------------------------------------------


class TrainingExample(BaseModel):
    """A complete training example: messages plus metadata.

    Validates that:
    - At least two messages are present (system + one user/assistant turn).
    - The first message has ``role == "system"``.
    - Subsequent messages alternate ``user`` / ``assistant``.

    Attributes:
        messages: Ordered list of chat messages (min length 2).
        metadata: Associated :class:`ExampleMetadata`.
    """

    messages: list[Message] = Field(
        min_length=2,
        description="Ordered chat messages; minimum 2 required.",
    )
    metadata: ExampleMetadata

    @model_validator(mode="after")
    def validate_message_ordering(self) -> TrainingExample:
        """Enforce system-first and alternating user/assistant ordering."""
        msgs = self.messages
        if msgs[0].role != "system":
            raise ValueError(
                f"First message must have role 'system', "
                f"got '{msgs[0].role}'"
            )
        expected_role: Literal["user", "assistant"] = "user"
        for i, msg in enumerate(msgs[1:], start=1):
            if msg.role != expected_role:
                raise ValueError(
                    f"Message at index {i} must have role "
                    f"'{expected_role}', got '{msg.role}'"
                )
            expected_role = (
                "assistant" if expected_role == "user" else "user"
            )
        return self


# ---------------------------------------------------------------------------
# RagRetrievalParams
# ---------------------------------------------------------------------------


class RagRetrievalParams(BaseModel):
    """Parameters for a RAG retrieval query against a vector store.

    Validates that ``n_results`` is between 1 and 20 inclusive and that
    the query text is non-empty.

    **No runtime dependency on ChromaDB.** Tools that perform the actual
    retrieval must import ``chromadb`` lazily inside their function body.

    Attributes:
        query: Non-empty search query text.
        n_results: Number of results to retrieve (1-20 inclusive).
        collection_name: Target ChromaDB collection name.
    """

    query: str = Field(
        min_length=1,
        description="Search query text; must not be empty.",
    )
    n_results: int = Field(
        default=5,
        ge=1,
        le=20,
        description="Number of results to retrieve (1-20 inclusive).",
    )
    collection_name: str = Field(
        min_length=1,
        description="Target ChromaDB collection name.",
    )

    @field_validator("n_results")
    @classmethod
    def validate_n_results_range(cls, v: int) -> int:
        """Provide a clear error message when n_results is out of range."""
        if v < 1:
            raise ValueError(
                f"n_results must be >= 1, got {v}; "
                f"at least one result is required"
            )
        if v > 20:
            raise ValueError(
                f"n_results must be <= 20, got {v}; "
                f"maximum 20 results supported to avoid excessive latency"
            )
        return v


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

__all__ = [
    "ExampleMetadata",
    "Message",
    "RagRetrievalParams",
    "TrainingExample",
]
