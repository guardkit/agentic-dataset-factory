---
id: TASK-GG-004
title: Write metadata consistency tests cross-validating GOAL.md against validator.py
task_type: testing
parent_review: TASK-REV-843F
feature_id: FEAT-GG
wave: 2
implementation_mode: task-work
complexity: 4
dependencies:
- TASK-GG-002
- TASK-GG-003
status: in_review
estimated_minutes: 60
consumer_context:
- task: TASK-GG-003
  consumes: METADATA_VALID_VALUES
  framework: pytest + synthesis.validator Pydantic models
  driver: pydantic
  format_note: Text and topic valid values in GOAL.md Metadata Schema table must be
    a superset of Literal values in synthesis/validator.py Metadata model
autobuild_state:
  current_turn: 1
  max_turns: 35
  worktree_path: /Users/richardwoollcott/Projects/appmilla_github/agentic-dataset-factory/.guardkit/worktrees/FEAT-FBBC
  base_branch: main
  started_at: '2026-03-21T07:13:25.500546'
  last_updated: '2026-03-21T07:17:41.734466'
  turns:
  - turn: 1
    decision: approve
    feedback: null
    timestamp: '2026-03-21T07:13:25.500546'
    player_summary: Implementation via task-work delegation
    player_success: true
    coach_success: true
---

# Task: Write metadata consistency tests cross-validating GOAL.md against validator.py

## Description

Create pytest tests that parse the GOAL.md Metadata Schema section and verify that every valid value listed matches the corresponding Pydantic `Literal` types in `synthesis/validator.py`. This catches drift between the GOAL.md (source of truth for the domain) and the code (enforcement layer).

Tests should:
1. Parse the Metadata Schema table from GOAL.md
2. Extract valid values for `text`, `topic`, `ao`, `layer`, `type`, `grade_target`, `source`
3. Compare against `TEXT_VALUES`, `TOPIC_VALUES`, `AO_PATTERN`, and `Metadata` model Literal types in `synthesis/validator.py`
4. Verify Generation Targets categories appear in topic valid values
5. Verify evaluation criterion names are valid Python identifiers

## Acceptance Criteria

- [ ] Test file created at `tests/test_goal_md_consistency.py`
- [ ] Test verifies GOAL.md `text` valid values match `TEXT_VALUES` in validator.py
- [ ] Test verifies GOAL.md `topic` valid values match `TOPIC_VALUES` in validator.py
- [ ] Test verifies GOAL.md `ao` valid values match `AO_PATTERN` (AO1-AO6)
- [ ] Test verifies GOAL.md `grade_target` range matches validator (4-9 + null)
- [ ] Test verifies GOAL.md `layer` values match Metadata.layer Literal type
- [ ] Test verifies GOAL.md `type` values match Metadata.type Literal type
- [ ] Test verifies all generation target categories appear in metadata topic valid values
- [ ] Test verifies all evaluation criterion names are valid Python identifiers (match `^[a-zA-Z_][a-zA-Z0-9_]*$`)
- [ ] All tests pass with `pytest tests/test_goal_md_consistency.py -v`

## Seam Tests

The following seam test validates the integration contract with the producer task. Implement this test to verify the boundary before integration.

```python
"""Seam test: verify METADATA_VALID_VALUES contract from TASK-GG-003."""
import pytest


@pytest.mark.seam
@pytest.mark.integration_contract("METADATA_VALID_VALUES")
def test_metadata_valid_values_superset():
    """Verify GOAL.md metadata valid values are a superset of validator.py Literals.

    Contract: Text and topic valid values in GOAL.md Metadata Schema table
    must be a superset of Literal values in synthesis/validator.py Metadata model.
    Producer: TASK-GG-003
    """
    from synthesis.validator import TEXT_VALUES, TOPIC_VALUES

    # Parse GOAL.md metadata schema table to extract valid values
    goal_md_text_values = set()  # Extract from GOAL.md parsing
    goal_md_topic_values = set()  # Extract from GOAL.md parsing

    assert set(TEXT_VALUES).issubset(goal_md_text_values), (
        f"validator.py TEXT_VALUES contains values not in GOAL.md: "
        f"{set(TEXT_VALUES) - goal_md_text_values}"
    )
    assert set(TOPIC_VALUES).issubset(goal_md_topic_values), (
        f"validator.py TOPIC_VALUES contains values not in GOAL.md: "
        f"{set(TOPIC_VALUES) - goal_md_topic_values}"
    )
```

## Implementation Notes

- Use simple regex or string parsing to extract table rows from GOAL.md (no dependency on the parser module which is FEAT-5606)
- Tests should read GOAL.md from disk using `Path("domains/gcse-english-tutor/GOAL.md")`
- Keep parsing minimal — just enough to extract valid values from markdown tables
