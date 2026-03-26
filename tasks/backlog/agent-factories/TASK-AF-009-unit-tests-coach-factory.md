---
id: TASK-AF-009
title: Unit tests for Coach factory
task_type: testing
parent_review: TASK-REV-DAA1
feature_id: FEAT-AF
wave: 3
implementation_mode: task-work
complexity: 3
dependencies:
- TASK-AF-004
status: in_review
tags:
- testing
- coach
- factory
- mock
- role-separation
- d5
autobuild_state:
  current_turn: 1
  max_turns: 35
  worktree_path: /Users/richardwoollcott/Projects/appmilla_github/agentic-dataset-factory/.guardkit/worktrees/FEAT-5AC9
  base_branch: main
  started_at: '2026-03-20T23:08:57.236402'
  last_updated: '2026-03-20T23:15:03.951086'
  turns:
  - turn: 1
    decision: approve
    feedback: null
    timestamp: '2026-03-20T23:08:57.236402'
    player_summary: Implementation via task-work delegation
    player_success: true
    coach_success: true
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
