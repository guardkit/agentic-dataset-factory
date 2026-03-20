---
complexity: 3
dependencies:
- TASK-AF-004
feature_id: FEAT-AF
id: TASK-AF-009
implementation_mode: task-work
parent_review: TASK-REV-DAA1
status: design_approved
tags:
- testing
- coach
- factory
- mock
- role-separation
- d5
task_type: testing
title: Unit tests for Coach factory
wave: 3
---

# Task: Unit tests for Coach factory

## Description

Write unit tests for the Coach factory verifying the D5 invariant (no tools, no backend) using the exemplar testing methodology.

## Test Cases

### Key Examples
- `create_coach()` calls `create_deep_agent` with `tools=[]`
- NO `backend` kwarg passed to `create_deep_agent`
- `system_prompt` is passed through
- `memory` list is passed through
- Model config fields are translated correctly

### Negative/Structural Tests
- Coach factory signature does NOT accept a `tools` parameter (inspect signature)
- `FilesystemBackend` is NOT imported in `agents/coach.py` (module-level check)

### Edge Cases
- Coach with different provider than Player → both work independently
- Coach with different temperature than Player → correctly passed through
- Default Coach temperature (0.3) applied when not specified

## Acceptance Criteria

- [ ] Tests mock `create_deep_agent` at the import site (`agents.coach.create_deep_agent`)
- [ ] Tests verify `tools=[]` in `call_args`
- [ ] Tests verify `backend` is NOT in `call_args` kwargs (or is `None`)
- [ ] Module-level import assertion: `FilesystemBackend` NOT in `agents/coach.py` attributes
- [ ] Signature inspection test: `create_coach` has no `tools` parameter
- [ ] Tests are in `tests/test_coach_factory.py`

## Implementation Notes

The module-level import check is the second layer of enforcement for D5. Use `inspect.signature(create_coach)` to verify the tools parameter is absent.