---
id: TASK-TRF-008
title: Fix Coach verdict parser to handle preamble text before JSON
status: completed
created: 2026-03-26T00:00:00Z
updated: 2026-03-26T12:00:00Z
completed: 2026-03-26T12:05:00Z
completed_location: tasks/completed/TASK-TRF-008/
priority: critical
tags: [bug-fix, coach, parsing, P0]
complexity: 3
task_type: implementation
parent_review: TASK-REV-TRF4
feature_id: FEAT-TRF
wave: 1
implementation_mode: task-work
depends_on: []
test_results:
  status: passed
  coverage: null
  last_run: 2026-03-26T12:00:00Z
  tests_passed: 17
  tests_failed: 0
---

# Task: Fix Coach Verdict Parser to Handle Preamble Text

## Description

The `_parse_coach_verdict()` function in `entrypoint/generation_loop.py:140-180` fails when the Coach model returns explanatory text before a markdown code fence containing the JSON verdict.

**Current behaviour**: The parser checks `if content.startswith("```")` (line 159). When the Coach returns preamble text like "I can see the training example..." before the code fence, this check is `False` and the fence-stripping is skipped. The entire raw text then hits `model_validate_json()` and fails with:

```
Failed to parse CoachVerdict from response: 1 validation error for CoachVerdict
  Invalid JSON: expected ident at line 1 column 2
```

**Required behaviour**: Extract JSON from the response regardless of surrounding text, using the same robust 3-try strategy already implemented in `_extract_example_json()` (lines 94-137 in the same file).

## Root Cause

Qwen3.5-35B-A3B-FP8 at temperature 0.3 returns Coach verdicts in this format:

```
I can see the training example in your message. Let me evaluate it against the criteria.

```json
{
  "decision": "revise",
  "score": 4,
  "layer_correct": true,
  "type_correct": false,
  ...
}
```​
```

The parser only handles the case where the response starts with `` ``` ``.

## Implementation

Replace the current `_parse_coach_verdict()` implementation with robust JSON extraction:

1. **Try 1**: Direct parse — `model_validate_json(content.strip())`
2. **Try 2**: Regex code fence extraction — `re.compile(r"```(?:json)?\s*\n(.*?)```", re.DOTALL)`
3. **Try 3**: Brace-matching `{...}` extraction (same as `_extract_example_json`)
4. Validate extracted JSON against `CoachVerdict` schema

Consider extracting the shared JSON-extraction logic into a private helper `_extract_json_object()` used by both functions to avoid duplication.

## Files to Modify

- `entrypoint/generation_loop.py` — `_parse_coach_verdict()` function (lines 140-180)

## Acceptance Criteria

- [x] Coach responses with preamble text + code fence are parsed correctly
- [x] Coach responses with bare JSON (no fence) still work
- [x] Coach responses with code fence at start of response still work
- [x] Invalid JSON still raises `ValueError` with helpful error message
- [x] Existing tests pass
- [x] New unit tests cover: bare JSON, fenced JSON, preamble + fenced JSON, invalid content

## Test Execution Log

17 passed in 0.06s (tests/test_coach_verdict_parser.py)
242/244 existing tests pass (2 pre-existing failures in test_goal_md_sections_1_to_5.py unrelated to this change)
