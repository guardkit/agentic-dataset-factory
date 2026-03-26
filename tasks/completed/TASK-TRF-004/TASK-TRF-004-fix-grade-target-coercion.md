---
id: TASK-TRF-004
title: Fix grade_target type coercion in write_output validation
status: completed
created: 2026-03-26T00:00:00Z
updated: 2026-03-26T00:00:00Z
completed: 2026-03-26T00:00:00Z
priority: critical
tags: [bug-fix, validation, type-coercion]
complexity: 1
task_type: implementation
parent_review: TASK-REV-FRF3
feature_id: FEAT-TRF
wave: 1
implementation_mode: direct
depends_on: []
test_results:
  status: passed
  coverage: null
  last_run: 2026-03-26T00:00:00Z
  total_tests: 65
  passed: 65
  failed: 0
---

# Task: Fix grade_target Type Coercion in write_output Validation

## Description

The `write_output` tool's Step 9 metadata validation fails for `grade_target` because the model sends an integer (`7`) but `valid_values` are strings (`["4", "5", "6", "7", ...]`). The comparison `7 not in ["4", "5", ...]` always fails because `int != str`.

Root cause: `domain_config/parser.py:86-94` `_coerce_valid_values()` returns all values as strings (correct for parsing markdown tables). The fix belongs in `write_output.py` at the validation boundary where external (model-generated) input is checked.

## Changes Required

### `src/tools/write_output.py` (line ~163-164)

```python
# BEFORE:
else:
    if field_value not in valid_values:

# AFTER:
else:
    if str(field_value) not in valid_values:
```

### `src/tools/tests/test_write_output.py`

Add test cases:
- `test_integer_grade_target_accepted` — passes `grade_target: 7` (int), expects success
- `test_string_grade_target_accepted` — passes `grade_target: "7"` (str), expects success
- `test_invalid_grade_target_rejected` — passes `grade_target: 3` (not in valid values), expects error
- `test_null_grade_target_accepted` — passes `grade_target: null`, expects success (null is valid)

## Acceptance Criteria

- [x] `str(field_value)` cast applied in `write_output.py` Step 9
- [x] Integer metadata values now pass validation against string valid_values
- [x] All 4 new test cases pass
- [x] All existing `test_write_output.py` tests still pass

## Test Execution Log

- 65/65 tests passed (0 failures, 0 skipped)
- 4 new tests in `TestGradeTargetTypeCoercion` class all passing
- 61 existing tests unaffected (no regressions)
- Execution time: 0.30s
