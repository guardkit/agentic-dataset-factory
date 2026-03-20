---
id: TASK-DC-001
title: Create domain_config package and Pydantic models
task_type: declarative
parent_review: TASK-REV-DC5D
feature_id: FEAT-5606
wave: 1
implementation_mode: direct
complexity: 3
dependencies: []
status: in_review
priority: high
tags:
- domain-config
- pydantic
- models
created: 2026-03-19 00:00:00+00:00
updated: 2026-03-19 00:00:00+00:00
test_results:
  status: pending
  coverage: null
  last_run: null
autobuild_state:
  current_turn: 3
  max_turns: 35
  worktree_path: /Users/richardwoollcott/Projects/appmilla_github/agentic-dataset-factory/.guardkit/worktrees/FEAT-5606
  base_branch: main
  started_at: '2026-03-20T10:54:46.700377'
  last_updated: '2026-03-20T11:07:21.248096'
  turns:
  - turn: 1
    decision: feedback
    feedback: "- Not all acceptance criteria met:\n  \u2022 All 5 Pydantic models\
      \ match the API contract field types exactly\n  \u2022 `SourceDocument.mode`\
      \ constrained to `Literal[\"standard\", \"vlm\"]`\n  \u2022 `GenerationTarget.type`\
      \ constrained to `Literal[\"reasoning\", \"direct\"]`\n  \u2022 `EvaluationCriterion.name`\
      \ validated as Python identifier + not keyword\n  \u2022 `GoalValidationError`\
      \ exception class with `section` and `message` attributes"
    timestamp: '2026-03-20T10:54:46.700377'
    player_summary: '[RECOVERED via player_report] Original error: Cancelled: Cancelled
      via cancel scope 122fe1910 by <Task pending name=''Task-100'' coro=<<async_generator_athrow
      without __name__>()>>'
    player_success: true
    coach_success: true
  - turn: 2
    decision: feedback
    feedback: "- Not all acceptance criteria met:\n  \u2022 All 5 Pydantic models\
      \ match the API contract field types exactly\n  \u2022 `SourceDocument.mode`\
      \ constrained to `Literal[\"standard\", \"vlm\"]`\n  \u2022 `GenerationTarget.type`\
      \ constrained to `Literal[\"reasoning\", \"direct\"]`\n  \u2022 `EvaluationCriterion.name`\
      \ validated as Python identifier + not keyword\n  \u2022 `GoalValidationError`\
      \ exception class with `section` and `message` attributes"
    timestamp: '2026-03-20T11:00:31.617674'
    player_summary: '[RECOVERED via player_report] Original error: Cancelled: Cancelled
      via cancel scope 1231444d0 by <Task pending name=''Task-199'' coro=<<async_generator_athrow
      without __name__>()>>'
    player_success: true
    coach_success: true
  - turn: 3
    decision: approve
    feedback: null
    timestamp: '2026-03-20T11:03:41.588734'
    player_summary: '[RECOVERED via player_report] Original error: Cancelled: Cancelled
      via cancel scope 123145190 by <Task pending name=''Task-212'' coro=<<async_generator_athrow
      without __name__>()>>'
    player_success: true
    coach_success: true
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
