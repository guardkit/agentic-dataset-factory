---
id: TASK-OR-002
title: Grade distribution in GOAL.md and orchestrator
status: completed
created: 2026-03-29T00:00:00Z
updated: 2026-03-29T00:00:00Z
completed: 2026-03-29T00:00:00Z
priority: critical
tags: [training-data, grade-diversity, goal-md, overnight-readiness]
task_type: implementation
complexity: 5
parent_review: TASK-REV-7617
feature_id: FEAT-OR
depends_on: []
wave: 1
implementation_mode: task-work
test_results:
  status: passed
  coverage: null
  last_run: 2026-03-29T00:00:00Z
  tests_passed: 521
  tests_failed: 0
  new_tests_added: 19
---

# Task: Grade Distribution in GOAL.md and Orchestrator

## Problem

12/13 train.jsonl examples target Grade 7 (92.3%). GOAL.md specifies valid
grade_target values as 4-9 plus null, but the Generation Targets table has no
per-category grade specification. The Player defaults to Grade 7 because the
Output Schema example uses `"grade_target": 7`.

## Solution

1. Add a `Grade Targets` column to GOAL.md's Generation Targets table
2. Extend `GenerationTarget` Pydantic model with `grade_targets: list[int | None]`
3. In the generation loop, distribute examples across grade targets (round-robin)
4. Pass `grade_target` as an explicit parameter in the Player prompt

## Implementation

### 1. Update GOAL.md Generation Targets Table

Add a `Grade Targets` column. Example:

| Category | Type | Count | Grade Targets |
|----------|------|-------|---------------|
| Literary analysis (single-turn) | reasoning | 90 | [5, 6, 7, 7, 8, 9] |
| Character analysis — Macbeth | reasoning | 80 | [4, 5, 6, 7, 8, 9] |
| Terminology and literary devices | direct | 50 | [null] |
| Encouragement and study skills | direct | 40 | [null] |

Reasoning targets get grade diversity. Direct/knowledge targets use null.

### 2. Extend GenerationTarget Model

In `domain_config/models.py`:

```python
class GenerationTarget(BaseModel):
    category: str = Field(min_length=1)
    type: Literal["reasoning", "direct"]
    count: int = Field(ge=1)
    grade_targets: list[int | None] = Field(
        default=[7],
        description="Grade targets to distribute across. Round-robin assignment."
    )
```

### 3. Update GOAL.md Parser

The parser that reads Generation Targets from GOAL.md needs to handle the new column.
Parse `[4, 5, 6, 7, 8, 9]` as a Python list.

### 4. Update Generation Loop

For each example within a category's count, select the next grade target:

```python
grade_target = target.grade_targets[example_index % len(target.grade_targets)]
```

Include `grade_target` in the Player prompt message:

```
Generate a training example for:
  Category: {category}
  Type: {type}
  Grade Target: {grade_target}  # NEW
```

### 5. Validate Grade in Metadata

The Coach or structural validator should check that the generated example's
`metadata.grade_target` matches the requested grade target.

## Files to Modify

- `domains/gcse-english-tutor/GOAL.md` — Add Grade Targets column
- `domain_config/models.py` — Extend GenerationTarget
- GOAL.md parser (find the file that reads Generation Targets table)
- `entrypoint/generation_loop.py` — Grade target selection + Player prompt

## Acceptance Criteria

- [x] GOAL.md has Grade Targets column for all 20 categories
- [x] GenerationTarget model accepts grade_targets field
- [x] Round-robin grade assignment distributes examples across targets
- [x] Player prompt includes explicit grade_target parameter
- [x] Generated examples have diverse grade_target values (not all Grade 7)
- [x] Direct-type categories use null for grade_target
- [x] Existing tests pass (no regressions)
- [x] New test: grade distribution produces expected spread

## Test Requirements

- Unit test: round-robin grade assignment for count=12, grades=[4,5,6,7,8,9] → 2 each
- Unit test: direct type with grade_targets=[null] → all null
- Unit test: GOAL.md parser handles new column format
- Integration: verify Player prompt includes grade_target
