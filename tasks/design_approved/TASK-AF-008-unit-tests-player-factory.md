---
complexity: 3
dependencies:
- TASK-AF-003
feature_id: FEAT-AF
id: TASK-AF-008
implementation_mode: task-work
parent_review: TASK-REV-DAA1
status: design_approved
tags:
- testing
- player
- factory
- mock
- create-deep-agent
task_type: testing
title: Unit tests for Player factory
wave: 3
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