"""Domain configuration models for GOAL.md parsing and validation.

Public API — all models, the validation exception, and the top-level
parser are importable directly from this package:

    from domain_config import parse_goal_md, GoalConfig, GoalValidationError
"""

from domain_config.models import (
    EvaluationCriterion,
    GenerationTarget,
    GoalConfig,
    GoalValidationError,
    MetadataField,
    SourceDocument,
)
from domain_config.parser import parse_goal_md

__all__ = [
    "parse_goal_md",
    "GoalValidationError",
    "SourceDocument",
    "GenerationTarget",
    "EvaluationCriterion",
    "MetadataField",
    "GoalConfig",
]
