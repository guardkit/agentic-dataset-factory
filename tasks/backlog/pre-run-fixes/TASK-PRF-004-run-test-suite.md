---
id: TASK-PRF-004
title: Run full test suite and document results
status: backlog
created: 2026-03-22T00:00:00Z
updated: 2026-03-22T00:00:00Z
priority: high
tags: [testing, verification, P1]
complexity: 3
parent_review: TASK-REV-A1B4
feature_id: FEAT-PRF
wave: 2
implementation_mode: task-work
dependencies: [TASK-PRF-001]
test_results:
  status: pending
  coverage: null
  last_run: null
---

# Task: Run Full Test Suite

## Description

Install dev dependencies and run the complete test suite to verify AutoBuild-generated code passes its own tests. This establishes a baseline before and after the model creation fix (TASK-PRF-001).

## Steps

1. Run `pip install -e ".[dev]"`
2. Run `pytest --tb=short -q` (all unit tests)
3. Run `pytest -m smoke --tb=short -v` (smoke tests)
4. Run `pytest -m seam --tb=short -v` (seam/contract tests)
5. Document all results (pass/fail counts, any failures with root cause)

## Acceptance Criteria

- [ ] Dev dependencies installed successfully
- [ ] All unit tests pass (or failures documented with root cause)
- [ ] All smoke tests pass
- [ ] Any failures are documented with root cause analysis
- [ ] Results baseline recorded for pre-fix and post-fix comparison

## Notes

- Run BEFORE TASK-PRF-001 fix to establish baseline, then AFTER to confirm fix
- Integration tests (`pytest -m integration`) require GB10 with vLLM — skip for now
- Test mocks for `create_model` in `agents/tests/test_player.py` may need updating after TASK-PRF-001

## Test Execution Log

[Automatically populated by /task-work]
