---
id: TASK-NRF-12C1
title: Add ValueError to per-target exception handler
status: completed
created: 2026-03-27T23:45:00Z
updated: 2026-03-28T00:00:00Z
completed: 2026-03-28T00:00:00Z
priority: critical
tags: [pipeline, bug-fix, coach-parsing, ninth-run]
task_type: feature
complexity: 1
parent_review: TASK-REV-1F3F
wave: 1
implementation_mode: task-work
dependencies: []
test_results:
  status: pending
  coverage: null
  last_run: null
---

# Task: Add ValueError to per-target exception handler

## Description

`_parse_coach_verdict()` raises `ValueError` when Coach returns non-JSON content, but the per-target exception handler at `generation_loop.py:1011` only catches `(RuntimeError, OSError, ValidationError)`. This causes a single Coach parsing failure to crash the entire pipeline instead of rejecting the target and continuing.

## Context

Identified in TASK-REV-1F3F review of run-9. The Coach intermittently returns Player-like reasoning text instead of a JSON verdict (stochastic model behaviour). The pipeline is designed to handle this via reject-and-continue, but the exception type is missing from the catch clause.

## Change

File: `entrypoint/generation_loop.py`
Line: 1011

```python
# BEFORE:
except (RuntimeError, OSError, ValidationError) as exc:

# AFTER:
except (RuntimeError, OSError, ValidationError, ValueError) as exc:
```

## Acceptance Criteria

- [x] `ValueError` added to the except tuple at line 1011
- [x] Existing tests pass (`pytest tests/ -v`)
- [x] Add test case: verify that `ValueError` from `_parse_coach_verdict` is caught and target is rejected (not pipeline crash)

## Test Requirements

- [x] Unit test: mock `_process_single_target` to raise `ValueError`, verify target is rejected and loop continues
- [x] Existing test suite passes unchanged (274 passed, 2 pre-existing failures unrelated to this change)

## Implementation Notes

This is a one-line fix. The `ValueError` is raised at two points in `_parse_coach_verdict()`:
1. Line 351: no JSON object found in response
2. Line 359-361: JSON found but CoachVerdict validation failed (wrapped as ValueError from ValidationError)

Both should be caught by the per-target handler and result in target rejection with `reason=llm_failure`.
