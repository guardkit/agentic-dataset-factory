---
id: TASK-TRF-003
title: Remove FilesystemBackend from Player (fix tool leakage)
status: completed
created: 2026-03-26T00:00:00Z
updated: 2026-03-26T00:00:00Z
completed: 2026-03-26T00:00:00Z
completed_location: tasks/completed/TASK-TRF-003/
priority: critical
tags: [architecture, tool-leakage, deepagents, security]
complexity: 2
task_type: implementation
parent_review: TASK-REV-FRF3
feature_id: FEAT-TRF
wave: 1
implementation_mode: task-work
depends_on: []
test_results:
  status: pass
  coverage: null
  last_run: 2026-03-26
---

# Task: Remove FilesystemBackend from Player (Fix Tool Leakage)

## Description

Remove `FilesystemBackend` from the Player agent factory. The DeepAgents SDK's `FilesystemMiddleware` injects 8 backend tools (ls, read_file, write_file, edit_file, glob, grep, execute, write_todos) when a real `FilesystemBackend` is provided. These tools waste ~3,000 tokens of context and give the Player unintended filesystem access.

Root cause validated via SDK source trace: `deepagents/middleware/filesystem.py:404-503` always injects its tool list when a backend is present.

## Changes Required

### `agents/player.py`

```python
# BEFORE (lines 57-64):
model = create_model(model_config)
backend = FilesystemBackend(root_dir=".")
return create_deep_agent(
    model=model,
    tools=tools,
    system_prompt=system_prompt,
    memory=memory,
    backend=backend,
)

# AFTER:
model = create_model(model_config)
return create_deep_agent(
    model=model,
    tools=tools,
    system_prompt=system_prompt,
    memory=memory,
    backend=None,
)
```

Also remove the import:
```python
# REMOVE:
from deepagents.backends import FilesystemBackend
```

### `agents/tests/test_player.py`

Update all test methods that patch `FilesystemBackend`:
- Remove `patch("agents.player.FilesystemBackend")` from test decorators
- Update assertions to verify `backend=None` is passed to `create_deep_agent`
- Add a new test `test_no_filesystem_backend_import` (mirror the Coach's `TestNoFilesystemBackendImport`) that verifies `FilesystemBackend` is not imported in the Player module

## Acceptance Criteria

- [x] `FilesystemBackend` import removed from `agents/player.py`
- [x] `backend=None` passed to `create_deep_agent` in `create_player()`
- [x] All existing Player factory tests pass (updated for no backend)
- [x] New test verifies `FilesystemBackend` is NOT imported in `agents/player.py`
- [x] New test verifies `backend` kwarg is `None` in `create_deep_agent` call

## Impact

- Saves ~3,000 tokens per API call (8 tool schemas removed)
- Eliminates security risk of Player reading/writing arbitrary files
- Directly addresses TASK-REV-FRF3 Finding F5

## Test Execution Log

```
14 passed, 0 failed in 2.41s

Tests:
  TestCreatePlayerSignature (2) - PASSED
  TestCreatePlayerDelegation (2) - PASSED
  TestCreatePlayerModel (1) - PASSED
  TestCreatePlayerBackend::test_backend_is_none - PASSED
  TestCreatePlayerTools (1) - PASSED
  TestCreatePlayerSystemPrompt (1) - PASSED
  TestCreatePlayerMemory (1) - PASSED
  TestCreatePlayerValidation (2) - PASSED
  TestNoFilesystemBackendImport (2) - PASSED (AST + text grep)
  TestCreatePlayerSeam (1) - PASSED
```
