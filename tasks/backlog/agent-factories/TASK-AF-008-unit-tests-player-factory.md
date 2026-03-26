---
id: TASK-AF-008
title: Unit tests for Player factory
task_type: testing
parent_review: TASK-REV-DAA1
feature_id: FEAT-AF
wave: 3
implementation_mode: task-work
complexity: 3
dependencies:
- TASK-AF-003
status: in_review
tags:
- testing
- player
- factory
- mock
- create-deep-agent
autobuild_state:
  current_turn: 1
  max_turns: 35
  worktree_path: /Users/richardwoollcott/Projects/appmilla_github/agentic-dataset-factory/.guardkit/worktrees/FEAT-5AC9
  base_branch: main
  started_at: '2026-03-20T23:08:57.234310'
  last_updated: '2026-03-20T23:14:50.110782'
  turns:
  - turn: 1
    decision: approve
    feedback: null
    timestamp: '2026-03-20T23:08:57.234310'
    player_summary: Implementation via task-work delegation
    player_success: true
    coach_success: true
---

# Task: Unit tests for Player factory

## Description

Write unit tests for the Player factory using the exemplar testing methodology: patch `create_deep_agent` at the import site, inspect `call_args` kwargs to verify correct wiring.

## Test Cases

### Key Examples
- `create_player()` calls `create_deep_agent` with correct kwargs
- Tools list contains exactly `rag_retrieval` and `write_output`
- `FilesystemBackend` is instantiated and passed as `backend` kwarg
- `system_prompt` is passed through
- `memory` list is passed through
- Model config fields are translated correctly

### Negative Cases
- Empty system prompt → validation error

### Module-Level Assertions
- `FilesystemBackend` IS imported in `agents/player.py` (contrast with Coach)
- `create_deep_agent` IS imported in `agents/player.py`

## Acceptance Criteria

- [ ] Tests mock `create_deep_agent` at the import site (`agents.player.create_deep_agent`)
- [ ] Tests verify `call_args` keyword arguments for tools, backend, system_prompt, memory
- [ ] Tests verify `FilesystemBackend` is in the `backend` kwarg
- [ ] Tests verify tools list contains exactly 2 tools
- [ ] Module-level import assertion: `hasattr(player_module, 'FilesystemBackend')` or equivalent
- [ ] Tests are in `tests/test_player_factory.py`

## Implementation Notes

Follow the exemplar testing patterns from `.claude/agents/pytest-factory-test-specialist.md`. Use `unittest.mock.patch` with the patch-at-import-site pattern.
