---
id: TASK-DC-005
title: Implement parse_goal_md public API and integration tests
task_type: testing
parent_review: TASK-REV-DC5D
feature_id: FEAT-5606
wave: 3
implementation_mode: task-work
complexity: 4
dependencies:
- TASK-DC-004
status: in_review
priority: high
tags:
- domain-config
- api
- testing
- integration
created: 2026-03-19 00:00:00+00:00
updated: 2026-03-19 00:00:00+00:00
test_results:
  status: pending
  coverage: null
  last_run: null
autobuild_state:
  current_turn: 1
  max_turns: 35
  worktree_path: /Users/richardwoollcott/Projects/appmilla_github/agentic-dataset-factory/.guardkit/worktrees/FEAT-5606
  base_branch: main
  started_at: '2026-03-20T15:12:26.850414'
  last_updated: '2026-03-20T15:21:59.966632'
  turns:
  - turn: 1
    decision: approve
    feedback: null
    timestamp: '2026-03-20T15:12:26.850414'
    player_summary: Implementation via task-work delegation
    player_success: true
    coach_success: true
---

# Task: Implement parse_goal_md public API and integration tests

## Description

Implement the top-level `parse_goal_md(goal_path: Path) -> GoalConfig` function that composes the section splitter, table/JSON parsers, and validators into a single public API. Write comprehensive integration tests covering the 36 BDD scenarios from the feature spec.

## Module Location

```
domain_config/
├── __init__.py      ← export parse_goal_md, GoalConfig, GoalValidationError
├── parser.py        ← add parse_goal_md() function
```

## Function Signature

```python
def parse_goal_md(goal_path: Path) -> GoalConfig:
    """Parse and validate a GOAL.md file.

    Args:
        goal_path: Path to the GOAL.md file.

    Returns:
        Validated GoalConfig instance.

    Raises:
        GoalValidationError: If file not found, empty, missing sections, or validation fails.
    """
```

## Orchestration Flow

```
1. Read file (handle FileNotFoundError → GoalValidationError)
2. Check empty (raise if empty)
3. split_sections(content) → dict[str, str]
4. Parse each section using parse_table() / extract_json() / raw text
5. Construct GoalConfig from parsed sections
6. validate_goal_config(sections, config)
7. Return config
```

## Test Structure

```
tests/
├── test_domain_config/
│   ├── __init__.py
│   ├── conftest.py           ← fixtures: valid GOAL.md, minimal GOAL.md, builders
│   ├── test_parse_goal_md.py ← integration tests (happy path + error cases)
│   ├── test_models.py        ← unit tests for models (from TASK-DC-001)
│   └── fixtures/
│       └── valid_goal.md     ← sample valid GOAL.md file
```

## Acceptance Criteria

- [ ] `parse_goal_md()` reads file from disk and returns `GoalConfig`
- [ ] File not found raises `GoalValidationError` with descriptive message
- [ ] Empty file raises `GoalValidationError` indicating no sections found
- [ ] All 9 sections parsed and assembled into `GoalConfig`
- [ ] Public API exported from `domain_config.__init__`: `parse_goal_md`, `GoalConfig`, `GoalValidationError`
- [ ] Integration test with valid GOAL.md fixture returns complete `GoalConfig`
- [ ] Integration tests cover boundary conditions (50/49 chars, 100/99 chars, 3/2 criteria, 70%/69% reasoning)
- [ ] Integration tests cover negative cases (missing sections, invalid mode, invalid identifier, malformed JSON, missing keys, missing layer, below 70%)
- [ ] Integration tests cover edge cases (whitespace variations, embedded headings, Unicode, percentage mismatch, nested fences, empty Valid Values)
- [ ] `pyproject.toml` updated: `testpaths` includes domain_config tests
- [ ] All tests pass with `pytest -v`

## Implementation Notes

- Create a `valid_goal.md` fixture file based on the GCSE English tutor example in [API-domain-config.md](../../../docs/design/contracts/API-domain-config.md)
- Use pytest fixtures to build GOAL.md variants (missing sections, short content, etc.)
- Consider a builder pattern: `GoalMdBuilder().with_goal("...").without_section("Source Documents").build()` for readable test construction
- The 36 BDD scenarios from `features/domain-config/domain-config.feature` should map to individual test functions
- Update `pyproject.toml` testpaths if needed to include the new test directory
