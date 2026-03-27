"""Validation logic for generated training examples against the ShareGPT schema."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator


# ---------------------------------------------------------------------------
# Constrained value sets
# ---------------------------------------------------------------------------

TEXT_VALUES = (
    "macbeth",
    "a_christmas_carol",
    "an_inspector_calls",
    "power_conflict_poetry",
    "language_paper_1",
    "language_paper_2",
    "general",
    "unseen_poetry",
)

TOPIC_VALUES = (
    "character_analysis",
    "language_analysis",
    "structure_analysis",
    "essay_feedback",
    "exam_technique",
    "comparative",
    "factual_recall",
    "character_knowledge",
    "terminology",
    "encouragement",
)

AO_PATTERN = re.compile(r"^AO[1-6]$")


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


class Message(BaseModel):
    """A single chat message in ShareGPT format."""

    role: Literal["system", "user", "assistant"]
    content: str = Field(min_length=1)


class Metadata(BaseModel):
    """Per-example metadata describing provenance and pedagogical intent."""

    layer: Literal["behaviour", "knowledge"]
    type: Literal["reasoning", "direct"]
    ao: list[str] = Field(default_factory=list)
    text: Literal[
        "macbeth",
        "a_christmas_carol",
        "an_inspector_calls",
        "power_conflict_poetry",
        "language_paper_1",
        "language_paper_2",
        "general",
        "unseen_poetry",
    ]
    topic: Literal[
        "character_analysis",
        "language_analysis",
        "structure_analysis",
        "essay_feedback",
        "exam_technique",
        "comparative",
        "factual_recall",
        "character_knowledge",
        "terminology",
        "encouragement",
    ]
    grade_target: int | None = None
    source: Literal[
        "synthetic", "aqa_derived", "exam_board_adapted"
    ] = "synthetic"
    turns: int = Field(default=1, ge=1)

    @field_validator("ao")
    @classmethod
    def validate_ao_codes(cls, v: list[str]) -> list[str]:
        """Each element must match the pattern AO[1-6]."""
        for code in v:
            if not AO_PATTERN.match(code):
                raise ValueError(
                    f"Invalid AO code '{code}'; "
                    f"must match pattern AO[1-6]"
                )
        return v

    @field_validator("grade_target")
    @classmethod
    def validate_grade_target(
        cls, v: int | None,
    ) -> int | None:
        """If present, grade_target must be 4-9 inclusive."""
        if v is not None and not (4 <= v <= 9):
            raise ValueError(
                f"grade_target must be 4-9 inclusive, got {v}"
            )
        return v


class TrainingExample(BaseModel):
    """A complete training example: messages plus metadata."""

    messages: list[Message] = Field(min_length=2)
    metadata: Metadata

    @model_validator(mode="after")
    def validate_message_ordering(self) -> TrainingExample:
        """First message must be system; rest must alternate user/assistant."""
        msgs = self.messages
        if msgs[0].role != "system":
            raise ValueError(
                "First message must have role 'system'"
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


class GenerationTarget(BaseModel):
    """Specification for a single example to be generated."""

    text: str
    topic: str
    grade_target: int | None = None
    layer: Literal["behaviour", "knowledge"]
    type: Literal["reasoning", "direct"]
    ao: list[str] = Field(default_factory=list)
    turns: int = Field(default=1, ge=1)


class GenerationPlan(BaseModel):
    """A batch of generation targets."""

    generation_targets: list[GenerationTarget]


class RejectionRecord(BaseModel):
    """Record of a rejected generation attempt."""

    target: GenerationTarget
    reason: str
    raw_response: str | None = None
    timestamp: str


# ---------------------------------------------------------------------------
# Validation result
# ---------------------------------------------------------------------------


@dataclass
class ValidationResult:
    """Result of a validation check on a TrainingExample."""

    is_valid: bool
    reason: str | None = None
    route: str | None = None


# ---------------------------------------------------------------------------
# Think-block validation
# ---------------------------------------------------------------------------

_THINK_OPEN_RE = re.compile(r"<think>", re.IGNORECASE)
_THINK_BLOCK_RE = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)

# Matches a second <think> that should be </think>:
# <think>...content...<think> (malformed closing tag)
_MALFORMED_CLOSE_RE = re.compile(
    r"(<think>.*?)<think>", re.DOTALL | re.IGNORECASE
)


def normalise_think_closing_tags(content: str) -> str:
    """Fix malformed ``<think>`` closing tags in assistant content.

    Some models (e.g. Qwen3.5-35B) emit ``<think>`` as both opening and
    closing tag.  This function replaces the second ``<think>`` in such
    pairs with ``</think>``.

    Also handles the EOF pattern where ``<think>`` is opened but never
    closed — appends ``</think>`` at the end of content.

    The fix is idempotent — content with correct ``</think>`` tags is
    returned unchanged.
    """
    if "</think>" in content.lower():
        # Already has a proper closing tag — nothing to fix.
        return content
    # Fix <think>...<think> malformed closing pairs.
    result = _MALFORMED_CLOSE_RE.sub(r"\1</think>", content)
    # If still no </think> (EOF pattern: <think> opened, never closed),
    # append a closing tag.
    if "<think>" in result.lower() and "</think>" not in result.lower():
        result = result + "</think>"
    return result


def validate_think_block(example: TrainingExample) -> ValidationResult:
    """Validate think-block presence/absence based on example type.

    - type == "reasoning": every assistant message MUST contain <think>...</think>
    - type == "direct":    no assistant message may contain <think>
    """
    assistant_messages = [m for m in example.messages if m.role == "assistant"]

    if example.metadata.type == "reasoning":
        for msg in assistant_messages:
            if not _THINK_BLOCK_RE.search(msg.content):
                return ValidationResult(
                    is_valid=False,
                    reason="reasoning example missing <think>...</think> block",
                )
    else:  # "direct"
        for msg in assistant_messages:
            if _THINK_OPEN_RE.search(msg.content):
                return ValidationResult(
                    is_valid=False,
                    reason="direct example contains unexpected <think> block",
                )

    return ValidationResult(is_valid=True)


# ---------------------------------------------------------------------------
# Split ratio tracking
# ---------------------------------------------------------------------------


class SplitTracker:
    """Tracks the reasoning/direct split across a generation run (target 75/25)."""

    _TARGET_REASONING: float = 0.75

    def __init__(self) -> None:
        self._reasoning_count: int = 0
        self._direct_count: int = 0

    def track(self, example: TrainingExample) -> None:
        """Update running counts for the example's type."""
        if example.metadata.type == "reasoning":
            self._reasoning_count += 1
        else:
            self._direct_count += 1

    def ratio(self) -> tuple[float, float]:
        """Return (reasoning_pct, direct_pct); both 0.0 when no examples tracked."""
        total = self._reasoning_count + self._direct_count
        if total == 0:
            return (0.0, 0.0)
        reasoning_pct = self._reasoning_count / total
        return (reasoning_pct, 1.0 - reasoning_pct)

    def is_within_tolerance(self, tolerance: float = 0.05) -> bool:
        """Return True if reasoning% is within ±tolerance of 75%."""
        total = self._reasoning_count + self._direct_count
        if total == 0:
            return True
        reasoning_pct, _ = self.ratio()
        return abs(reasoning_pct - self._TARGET_REASONING) < tolerance

    def warning_message(self) -> str | None:
        """Return a human-readable warning if ratio drifted beyond tolerance, else None."""
        if self.is_within_tolerance():
            return None
        reasoning_pct, direct_pct = self.ratio()
        return (
            f"Split ratio drifted: {reasoning_pct:.1%} reasoning / "
            f"{direct_pct:.1%} direct (target 75/25, tolerance ±5%)"
        )


# ---------------------------------------------------------------------------
# Duplicate detection
# ---------------------------------------------------------------------------


class DuplicateDetector:
    """Detects duplicate training examples via SHA-256 of assistant content."""

    def __init__(self) -> None:
        self._seen_hashes: set[str] = set()

    def _compute_hash(self, example: TrainingExample) -> str:
        combined = "".join(m.content for m in example.messages if m.role == "assistant")
        return hashlib.sha256(combined.encode()).hexdigest()

    def check(self, example: TrainingExample) -> bool:
        """Return True if this example is a duplicate; otherwise record it and return False."""
        h = self._compute_hash(example)
        if h in self._seen_hashes:
            return True
        self._seen_hashes.add(h)
        return False


# ---------------------------------------------------------------------------
# Output routing
# ---------------------------------------------------------------------------


def route_example(example: TrainingExample) -> str:
    """Return the output file path based on example layer."""
    if example.metadata.layer == "behaviour":
        return "output/train.jsonl"
    return "output/rag_index/knowledge.jsonl"


# ---------------------------------------------------------------------------
# Validation orchestrator
# ---------------------------------------------------------------------------


def validate_example(
    example: TrainingExample,
    split_tracker: SplitTracker,
    duplicate_detector: DuplicateDetector,
) -> ValidationResult:
    """Run all validation checks in order and return a ValidationResult.

    Check order: (schema via Pydantic already done) → think-block → duplicate
    → split tracking (updates state; appends warning to reason if drifted).
    """
    think_result = validate_think_block(example)
    if not think_result.is_valid:
        return think_result

    if duplicate_detector.check(example):
        return ValidationResult(is_valid=False, reason="duplicate content detected")

    split_tracker.track(example)
    route = route_example(example)
    warning = split_tracker.warning_message()

    return ValidationResult(is_valid=True, reason=warning, route=route)


__all__ = [
    "Message",
    "Metadata",
    "TrainingExample",
    "GenerationTarget",
    "GenerationPlan",
    "RejectionRecord",
    "ValidationResult",
    "normalise_think_closing_tags",
    "validate_think_block",
    "SplitTracker",
    "DuplicateDetector",
    "route_example",
    "validate_example",
]
