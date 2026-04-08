"""Pydantic models for parsed GOAL.md domain configuration.

Defines the data models that represent a validated GOAL.md file:
- SourceDocument: file pattern with Docling processing mode
- GenerationTarget: category/type/count for dataset composition
- EvaluationCriterion: Coach rubric criterion with identifier validation
- MetadataField: metadata schema field definition
- GoalConfig: top-level container for all 9 GOAL.md sections
- GoalValidationError: exception for validation failures
"""

from __future__ import annotations

import keyword
from typing import Literal

from pydantic import BaseModel, Field, field_validator


# ---------------------------------------------------------------------------
# Exception
# ---------------------------------------------------------------------------


class GoalValidationError(Exception):
    """Raised when GOAL.md fails validation.

    Attributes:
        section: The GOAL.md section that failed validation.
        message: A human-readable description of the validation failure.
    """

    def __init__(self, section: str, message: str) -> None:
        self.section = section
        self.message = message
        super().__init__(f"[{section}] {message}")


# ---------------------------------------------------------------------------
# Sub-models
# ---------------------------------------------------------------------------


class SourceDocument(BaseModel):
    """A source document entry from the Source Documents table.

    Defines a file pattern for Docling ingestion with the processing mode.
    """

    file_pattern: str = Field(min_length=1)
    mode: Literal["standard", "vlm"]
    notes: str = ""


class GenerationTarget(BaseModel):
    """A generation target from the Generation Targets table.

    Defines a category of training examples with type, layer, and count.
    The ``grade_targets`` list controls which grade levels are assigned
    to generated examples via round-robin distribution.
    """

    category: str = Field(min_length=1)
    type: Literal["reasoning", "direct"]
    layer: Literal["behaviour", "knowledge"] = "behaviour"
    count: int = Field(ge=1)
    grade_targets: list[int | None] = Field(
        default=[7],
        description="Grade targets to distribute across. Round-robin assignment.",
    )

    @field_validator("grade_targets")
    @classmethod
    def validate_grade_targets(cls, v: list[int | None]) -> list[int | None]:
        """Grade targets must be non-empty; integers must be 4-9."""
        if not v:
            raise ValueError("grade_targets must not be empty")
        for item in v:
            if item is not None and (item < 4 or item > 9):
                raise ValueError(
                    f"Grade target {item} out of range; must be 4-9 or null"
                )
        return v


class EvaluationCriterion(BaseModel):
    """A single evaluation criterion from the Evaluation Criteria table.

    The criterion name must be a valid Python identifier (used as a key
    in the Coach rejection schema's ``criteria_met`` dict) and must not
    be a Python reserved keyword.
    """

    name: str = Field(min_length=1)
    description: str = Field(min_length=1)
    weight: float = Field(ge=0.0, le=1.0)
    layer: Literal["behaviour", "knowledge", "all"] = "all"

    @field_validator("name")
    @classmethod
    def validate_name_is_identifier(cls, v: str) -> str:
        """Name must be a valid Python identifier and not a keyword."""
        if not v.isidentifier():
            raise ValueError(
                f"Criterion name '{v}' is not a valid Python identifier"
            )
        if keyword.iskeyword(v):
            raise ValueError(
                f"Criterion name '{v}' must not be a Python "
                f"reserved keyword"
            )
        return v


class MetadataField(BaseModel):
    """A field definition from the Metadata Schema table."""

    field: str = Field(min_length=1)
    type: str = Field(min_length=1)
    required: bool
    valid_values: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Top-level model
# ---------------------------------------------------------------------------


class GoalConfig(BaseModel):
    """Parsed and validated GOAL.md — the central domain configuration.

    Contains all 9 required sections from a domain's GOAL.md file.
    """

    goal: str = Field(min_length=50)
    source_documents: list[SourceDocument] = Field(min_length=1)
    system_prompt: str = Field(min_length=100)
    generation_targets: list[GenerationTarget] = Field(min_length=1)
    generation_guidelines: str = Field(min_length=100)
    evaluation_criteria: list[EvaluationCriterion] = Field(min_length=3)
    output_schema: dict
    metadata_schema: list[MetadataField]
    layer_routing: dict[str, str]


__all__ = [
    "GoalValidationError",
    "SourceDocument",
    "GenerationTarget",
    "EvaluationCriterion",
    "MetadataField",
    "GoalConfig",
]
