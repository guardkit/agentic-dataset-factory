---
id: TASK-TRF-017
title: Update test_player_factory.py to match new create_agent pattern
status: completed
created: 2026-03-27T00:00:00Z
updated: 2026-03-27T14:05:00Z
completed: 2026-03-27T14:05:00Z
completed_location: tasks/completed/TASK-TRF-017/
priority: critical
tags: [fix, tests, player, sixth-run]
complexity: 2
parent_review: TASK-REV-TRF6
feature_id: FEAT-TRF6
wave: 1
implementation_mode: task-work
depends_on: [TASK-TRF-016]
test_results:
  status: passed
  coverage: null
  last_run: 2026-03-27T14:00:00Z
  tests_total: 19
  tests_passed: 19
  tests_failed: 0
---

# Task: Update test_player_factory.py to Match New create_agent Pattern

## Description

After TASK-TRF-016 switches the Player from `create_deep_agent` to `create_agent`, the test suite at `tests/test_player_factory.py` needs to be updated to match.

### Changes Required

**File: `tests/test_player_factory.py`**

Mirror the Coach test pattern in `tests/test_coach_factory.py`:

1. Patch `create_agent` at its import site (not `create_deep_agent`)
2. Verify `create_agent` is called with `tools=[rag_retrieval]` (not empty like Coach)
3. Verify middleware list contains `MemoryMiddleware` and `PatchToolCallsMiddleware`
4. Verify middleware list does NOT contain `FilesystemMiddleware`
5. Verify `MemoryMiddleware` has correct `sources` parameter for memory injection
6. Remove any assertions about `FilesystemBackend` being passed as `backend` param to `create_deep_agent`

## Acceptance Criteria

- [x] Tests verify `create_agent` is called (not `create_deep_agent`)
- [x] Tests verify `tools=[rag_retrieval]` is passed
- [x] Tests verify `FilesystemMiddleware` is NOT in middleware stack
- [x] Tests verify `MemoryMiddleware` IS in middleware stack
- [x] All tests pass: `pytest tests/test_player_factory.py -v` (19/19 passed)

## Context

Coach test reference: `tests/test_coach_factory.py`
