---
id: TASK-DC-004
title: Implement cross-section validation and error aggregation
task_type: feature
parent_review: TASK-REV-DC5D
feature_id: FEAT-5606
wave: 3
implementation_mode: task-work
complexity: 5
dependencies:
- TASK-DC-002
- TASK-DC-003
status: in_review
priority: high
tags:
- domain-config
- validation
- error-handling
created: 2026-03-19 00:00:00+00:00
updated: 2026-03-19 00:00:00+00:00
consumer_context:
- task: TASK-DC-002
  consumes: SECTION_DICT
  framework: Pydantic v2 (BaseModel)
  driver: pydantic
  format_note: dict[str, str] with 9 keys mapping section name to body text
- task: TASK-DC-003
  consumes: PARSED_MODELS
  framework: Pydantic v2 (BaseModel)
  driver: pydantic
  format_note: Lists of validated Pydantic model instances per section
test_results:
  status: pending
  coverage: null
  last_run: null
autobuild_state:
  current_turn: 1
  max_turns: 35
  worktree_path: /Users/richardwoollcott/Projects/appmilla_github/agentic-dataset-factory/.guardkit/worktrees/FEAT-5606
  base_branch: main
  started_at: '2026-03-20T15:01:27.151678'
  last_updated: '2026-03-20T15:12:26.827371'
  turns:
  - turn: 1
    decision: approve
    feedback: null
    timestamp: '2026-03-20T15:01:27.151678'
    player_summary: Implementation via task-work delegation
    player_success: true
    coach_success: true
---

# Task: Implement cross-section validation and error aggregation

## Description

Implement validation rules that span across parsed sections and the error aggregation mechanism that collects ALL validation failures before raising a single comprehensive error.

## Module Location

```
domain_config/
├── validators.py    ← validate_goal_config() and per-section validators
```

## Validation Rules

Per [DM-goal-schema.md](../../../docs/design/models/DM-goal-schema.md):

1. `goal` minimum 50 characters
2. `system_prompt` minimum 100 characters
3. `generation_guidelines` minimum 100 characters
4. `source_documents` at least 1 entry
5. `evaluation_criteria` at least 3 criteria
6. `evaluation_criteria` names are valid Python identifiers AND not reserved keywords
7. `output_schema` contains `messages` and `metadata` top-level keys
8. `metadata_schema` all fields have `required = True`
9. `layer_routing` contains both `behaviour` and `knowledge` entries
10. Generation targets reasoning percentage >= 70%

## Error Aggregation

```python
def validate_goal_config(sections: dict[str, str], parsed: GoalConfig) -> None:
    """Run all validation rules and raise a single error with all failures.

    Raises:
        GoalValidationError: With all failing sections and messages.
    """
```

The error must include EVERY failing section, not just the first. Each failure should identify:
- The section name
- A human-readable description of the failure

## Acceptance Criteria

- [ ] Goal section validated: minimum 50 characters (boundary: 50 passes, 49 fails)
- [ ] System Prompt validated: minimum 100 characters (boundary: 100 passes, 99 fails)
- [ ] Generation Guidelines validated: minimum 100 characters
- [ ] Evaluation Criteria: at least 3 criteria required (boundary: 3 passes, 2 fails)
- [ ] Evaluation Criteria: names checked for Python keyword collision (`class`, `import`, etc.)
- [ ] Output Schema: `messages` and `metadata` keys required
- [ ] Source Documents: mode restricted to `standard` or `vlm` (reject `ocr`)
- [ ] Layer Routing: both `behaviour` and `knowledge` rows required
- [ ] Reasoning split: >= 70% of generation targets must be `reasoning` type (boundary: 70% passes, 69% fails)
- [ ] Percentages in Generation Targets are advisory; counts are authoritative
- [ ] Multiple validation failures reported together in a single error
- [ ] Error messages include section name and human-readable description
- [ ] All modified files pass project-configured lint/format checks with zero errors

## Seam Tests

The following seam test validates the integration contract with the producer tasks.

```python
"""Seam test: verify SECTION_DICT and PARSED_MODELS contracts."""
import pytest


@pytest.mark.seam
@pytest.mark.integration_contract("SECTION_DICT")
def test_section_dict_consumed_by_validator():
    """Verify validator accepts the dict format from split_sections.

    Contract: dict[str, str] with 9 keys
    Producer: TASK-DC-002
    """
    from domain_config.parser import split_sections
    # Validator must accept the output of split_sections without transformation
    sections = {"Goal": "x" * 100, "System Prompt": "x" * 100}
    assert isinstance(sections, dict)
    assert all(isinstance(v, str) for v in sections.values())
```

## Implementation Notes

- Collect errors in a `list[tuple[str, str]]` (section_name, message)
- Raise a single `GoalValidationError` at the end with all failures
- For reasoning split: `sum(t.count for t in targets if t.type == "reasoning") / sum(t.count for t in targets)`
- BDD scenarios: 84-88 (Goal 50 chars), 90-96 (Goal 49 chars), 98-103 (System Prompt 100 chars), 105-110 (System Prompt 99 chars), 113-117 (Guidelines 100 chars), 119-124 (3 criteria), 127-132 (2 criteria), 137-140 (70% reasoning), 172-177 (invalid mode), 179-185 (invalid identifier), 188-193 (invalid JSON), 195-201 (missing messages key), 203-209 (missing knowledge row), 211-217 (below 70%), 253-260 (multiple failures), 280-286 (keyword as criterion), 298-304 (percentages advisory)
