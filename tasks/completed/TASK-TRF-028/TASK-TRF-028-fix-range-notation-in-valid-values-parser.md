---
id: TASK-TRF-028
title: Add range notation detection to _coerce_valid_values parser
status: completed
created: 2026-03-27T18:00:00Z
updated: 2026-03-27T19:00:00Z
completed: 2026-03-27T19:00:00Z
priority: critical
tags: [parser, metadata-schema, validation, ninth-run]
complexity: 2
parent_review: TASK-REV-TRF9
feature_id: FEAT-TRF9
depends_on: []
wave: 1
implementation_mode: task-work
test_results:
  status: passed
  tests_total: 56
  tests_passed: 56
  tests_failed: 0
  last_run: 2026-03-27T19:00:00Z
---

# Task: Add Range Notation Detection to _coerce_valid_values Parser

## Problem

`_coerce_valid_values` in `domain_config/parser.py:86-94` treats ALL non-empty Valid Values cells as comma-separated enumerations. This fails for fields like `turns` where the GOAL.md uses range notation:

```markdown
| turns | integer | yes | 1+ (number of conversation turns) |
```

The parser produces `valid_values = ["1+ (number of conversation turns)"]`. Then `write_output` Step 9 checks `str(1) in ["1+ (number of conversation turns)"]` → False → validation fails.

This is the sole blocker that prevented the pipeline's first successful training example in Run 9.

## Root Cause

The validation architecture only supports enumerated values. Range constraints like "any integer >= 1" cannot be expressed via `valid_values`. The Pydantic model (`synthesis/validator.py:88: turns: int = Field(ge=1)`) already enforces the actual range — the `write_output` enum check is redundant and incorrect for this field.

## Fix

Add range notation detection to `_coerce_valid_values`. When the cell starts with a range pattern (e.g., `1+`, `0+`), return an empty list so the enumeration check is skipped. The GOAL.md stays unchanged.

```python
import re

_RANGE_NOTATION_RE = re.compile(r"^\d+\+")

def _coerce_valid_values(raw: str) -> list[str]:
    """Parse a comma-separated cell into a list of stripped strings.

    An empty or whitespace-only cell returns an empty list.
    Range notations like '1+' or '0+' return an empty list because
    they express constraints, not enumerations — the Pydantic model
    handles range validation.
    """
    stripped = raw.strip()
    if not stripped:
        return []
    if _RANGE_NOTATION_RE.match(stripped):
        return []
    return [v.strip() for v in stripped.split(",") if v.strip()]
```

## Files to Modify

- `domain_config/parser.py` (lines 86-94)
- `domain_config/tests/test_parse_goal_md.py` (add tests)

## Acceptance Criteria

- [x] `_coerce_valid_values("1+ (number of conversation turns)")` returns `[]`
- [x] `_coerce_valid_values("0+")` returns `[]`
- [x] `_coerce_valid_values("behaviour, knowledge")` still returns `["behaviour", "knowledge"]`
- [x] `_coerce_valid_values("4, 5, 6, 7, 8, 9, null")` still returns `["4", "5", "6", "7", "8", "9", "null"]`
- [x] `_coerce_valid_values("")` still returns `[]`
- [x] Existing tests pass unchanged
- [x] Full GOAL.md parse produces `turns.valid_values == []`
- [ ] `write_output` validation passes for `metadata.turns = 1` (runtime verification — depends on full pipeline run)

## Test Cases

```python
class TestCoerceValidValuesRangeNotation:
    def test_range_1_plus_returns_empty(self):
        assert _coerce_valid_values("1+") == []

    def test_range_0_plus_returns_empty(self):
        assert _coerce_valid_values("0+") == []

    def test_range_with_description_returns_empty(self):
        assert _coerce_valid_values("1+ (number of conversation turns)") == []

    def test_enum_still_works(self):
        assert _coerce_valid_values("behaviour, knowledge") == ["behaviour", "knowledge"]

    def test_numeric_enum_still_works(self):
        assert _coerce_valid_values("4, 5, 6, 7, 8, 9, null") == ["4", "5", "6", "7", "8", "9", "null"]

    def test_empty_returns_empty(self):
        assert _coerce_valid_values("") == []
        assert _coerce_valid_values("   ") == []
```

## Why Not Just Clear the GOAL.md Cell

- Loses documentation — `| turns | integer | yes | |` tells the reader nothing
- Pushes domain knowledge out of the domain config
- Fragile — someone adding documentation back reintroduces the bug
- The parser should be smart enough to distinguish enums from ranges
