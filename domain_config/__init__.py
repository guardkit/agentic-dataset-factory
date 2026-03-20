"""Domain configuration models for GOAL.md parsing and validation.

Public API — all models and the validation exception are importable
directly from this package:

    from domain_config import GoalConfig, SourceDocument, GoalValidationError
"""

from domain_config.models import (
    EvaluationCriterion,
    GenerationTarget,
    GoalConfig,
    GoalValidationError,
    MetadataField,
    SourceDocument,
)

__all__ = [
    "GoalValidationError",
    "SourceDocument",
    "GenerationTarget",
    "EvaluationCriterion",
    "MetadataField",
    "GoalConfig",
]
