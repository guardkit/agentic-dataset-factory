---
id: TASK-DC-001
title: "Create domain_config package and Pydantic models"
task_type: declarative
parent_review: TASK-REV-DC5D
feature_id: FEAT-5606
wave: 1
implementation_mode: direct
complexity: 3
dependencies: []
status: pending
priority: high
tags: [domain-config, pydantic, models]
created: 2026-03-19T00:00:00Z
updated: 2026-03-19T00:00:00Z
test_results:
  status: pending
  coverage: null
  last_run: null
---

# Task: Create domain_config package and Pydantic models

## Description

Create the `domain_config/` package with Pydantic v2 models for all data structures defined in the API contract. This is the foundation task — all other tasks depend on these models.

## Models to Create

Based on [API-domain-config.md](../../../docs/design/contracts/API-domain-config.md) and [DM-goal-schema.md](../../../docs/design/models/DM-goal-schema.md):

1. **SourceDocument** — `file_pattern: str`, `mode: Literal["standard", "vlm"]`, `notes: str = ""`
2. **GenerationTarget** — `category: str`, `type: Literal["reasoning", "direct"]`, `count: int`
3. **EvaluationCriterion** — `name: str`, `description: str`, `weight: float`
   - `name` must be a valid Python identifier AND not a reserved keyword
4. **MetadataField** — `field: str`, `type: str`, `required: bool`, `valid_values: list[str]`
5. **GoalConfig** — top-level model with all 9 fields
6. **GoalValidationError** — custom exception with `section: str` and `message: str`

## Package Structure

```
domain_config/
├── __init__.py      ← public API exports
├── models.py        ← Pydantic models + GoalValidationError
```

## Acceptance Criteria

- [ ] `domain_config/` package created with `__init__.py` and `models.py`
- [ ] All 5 Pydantic models match the API contract field types exactly
- [ ] `SourceDocument.mode` constrained to `Literal["standard", "vlm"]`
- [ ] `GenerationTarget.type` constrained to `Literal["reasoning", "direct"]`
- [ ] `EvaluationCriterion.name` validated as Python identifier + not keyword
- [ ] `GoalValidationError` exception class with `section` and `message` attributes
- [ ] `GoalConfig` model with all 9 fields typed correctly
- [ ] Models importable from `domain_config` package root
- [ ] Unit tests for model construction and field validation

## Implementation Notes

- Use `from __future__ import annotations` for forward references
- Follow existing pattern in `synthesis/validator.py` (Pydantic BaseModel with field_validator)
- Use `pydantic.field_validator` for `EvaluationCriterion.name` validation
- Use `keyword.iskeyword()` + `str.isidentifier()` for criterion name checks
- `pyproject.toml` already includes `pydantic>=2.0`
