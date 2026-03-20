---
id: TASK-AF-005
title: "Create CoachVerdict Pydantic model"
task_type: declarative
parent_review: TASK-REV-DAA1
feature_id: FEAT-AF
wave: 1
implementation_mode: task-work
complexity: 2
dependencies: []
status: pending
tags: [pydantic, coach, verdict, rejection-schema]
---

# Task: Create CoachVerdict Pydantic model

## Description

Create `config/coach_verdict.py` containing the `CoachVerdict` Pydantic BaseModel representing the Coach rejection/acceptance schema. This model validates the structured JSON that the Coach agent returns for every evaluation.

## Requirements

Based on `docs/design/contracts/API-generation.md` and `docs/design/models/DM-coach-rejection.md`:

```python
class CoachVerdict(BaseModel):
    decision: Literal["accept", "revise"]
    score: int  # 1-5
    layer_correct: bool
    type_correct: bool
    criteria_met: dict[str, bool]
    issues: list[Issue]
    quality_assessment: str

class Issue(BaseModel):
    criterion: str
    severity: Literal["blocking", "minor"]
    description: str
    suggestion: str
```

### Acceptance Rule
An example is accepted when: decision == "accept", score >= 3, layer_correct == True, type_correct == True, no blocking severity issues.

## Acceptance Criteria

- [ ] `config/coach_verdict.py` contains `CoachVerdict` and `Issue` Pydantic BaseModels
- [ ] `decision` uses `Literal["accept", "revise"]`
- [ ] `score` uses `Field(ge=1, le=5)`
- [ ] `severity` uses `Literal["blocking", "minor"]`
- [ ] `criteria_met` is `dict[str, bool]`
- [ ] `issues` is `list[Issue]`
- [ ] A property or method `is_accepted` implements the acceptance rule
- [ ] All modified files pass project-configured lint/format checks with zero errors

## Implementation Notes

Follow existing Pydantic patterns from `synthesis/validator.py`.
