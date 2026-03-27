---
id: TASK-TRF-025
title: JSON-string-aware brace matching in _extract_json_object
status: completed
created: 2026-03-27T16:00:00Z
updated: 2026-03-27T17:00:00Z
completed: 2026-03-27T17:00:00Z
priority: critical
tags: [json-extraction, generation-loop, eighth-run]
complexity: 3
parent_review: TASK-REV-TRF8
feature_id: FEAT-TRF8
depends_on: []
wave: 1
implementation_mode: task-work
test_results:
  status: passed
  coverage: null
  last_run: 2026-03-27T17:00:00Z
  total_tests: 59
  passed: 59
  failed: 0
  new_tests: 5
---

# Task: JSON-String-Aware Brace Matching in _extract_json_object

## Problem

The Try 3 brace-matching strategy in `_extract_json_object` (entrypoint/generation_loop.py:144-161) uses a naive character counter that treats ALL `{` and `}` as structural JSON delimiters. When the Player's training example contains text with unbalanced braces in string values (e.g., `"content": "What about {this?"`), the depth counter is thrown off:

- An unmatched `{` in a string increments depth, preventing it from ever returning to 0
- An unmatched `}` in a string decrements depth prematurely, extracting a truncated candidate

This caused 100% extraction failure in Run 8 (both Coach-accepted turns).

## Fix

Replace the naive brace counter (lines 144-161) with a JSON-string-aware scanner that tracks whether the current position is inside a quoted string:

```python
# Try 3: Find the first { ... } block that parses as valid JSON
# Use a JSON-string-aware scanner to ignore braces inside strings
in_string = False
escape_next = False
brace_depth = 0
start_idx = None

for i, ch in enumerate(content):
    if escape_next:
        escape_next = False
        continue
    if ch == '\\' and in_string:
        escape_next = True
        continue
    if ch == '"':
        in_string = not in_string
        continue
    if in_string:
        continue
    # Only count braces outside strings
    if ch == "{":
        if brace_depth == 0:
            start_idx = i
        brace_depth += 1
    elif ch == "}":
        brace_depth -= 1
        if brace_depth == 0 and start_idx is not None:
            candidate = content[start_idx : i + 1]
            try:
                parsed = json.loads(candidate)
                if isinstance(parsed, dict):
                    return candidate
            except (json.JSONDecodeError, TypeError):
                start_idx = None
```

## Files Modified

- `entrypoint/generation_loop.py` (lines 144-175)
- `entrypoint/tests/test_generation_loop.py` (added TestStringAwareBraceMatching class)

## Acceptance Criteria

- [x] Brace matcher tracks `in_string` state using `"` delimiter
- [x] Handles escaped quotes (`\"`) and escaped backslashes (`\\`) correctly
- [x] Existing tests pass unchanged
- [x] New test: JSON with unbalanced `{` in string value extracts correctly
- [x] New test: JSON with unbalanced `}` in string value extracts correctly
- [x] New test: JSON with escaped quotes in string value extracts correctly
- [x] New test: JSON with `\\{` in string value (escaped backslash + brace) extracts correctly
