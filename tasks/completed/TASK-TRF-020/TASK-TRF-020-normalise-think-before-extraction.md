---
id: TASK-TRF-020
title: Call normalise_think_closing_tags before JSON extraction in generation loop
status: completed
created: 2026-03-27T12:00:00Z
updated: 2026-03-27T13:00:00Z
completed: 2026-03-27T13:00:00Z
priority: critical
tags: [bug-fix, think-blocks, generation-loop, seventh-run]
complexity: 2
parent_review: TASK-REV-TRF7
feature_id: FEAT-TRF7
depends_on: []
wave: 1
implementation_mode: task-work
completed_location: tasks/completed/TASK-TRF-020/
test_results:
  status: passed
  coverage: null
  last_run: 2026-03-27T13:00:00Z
  tests_passed: 141
  tests_failed: 0
---

# Task: Call normalise_think_closing_tags Before JSON Extraction

## Problem

In `entrypoint/generation_loop.py` line 644, `_extract_example_json(player_content)` is called directly after Coach acceptance without first normalising think block closing tags. The Player generates training example JSON containing assistant messages with `<think>` blocks, and Qwen3.5-35B produces malformed closing tags (`<think>...<think>` instead of `<think>...</think>`).

The normaliser `normalise_think_closing_tags()` exists in `synthesis/validator.py` and is called in `src/tools/write_output.py:140`, but that runs AFTER JSON extraction -- a chicken-and-egg problem. The normaliser must run on the raw Player content BEFORE JSON extraction.

## Evidence (Run 7)

- 33 `<think>` opens, only 2 `</think>` closes in the run log
- 16 instances of `<think>...<think>` malformed close pattern (normaliser handles these)
- JSON extraction fails on turns 1 and 2 despite Coach accepting with score 5

## Fix

In `entrypoint/generation_loop.py`, import and call `normalise_think_closing_tags` on `player_content` before the `_extract_example_json` call (around line 644):

```python
from synthesis.validator import normalise_think_closing_tags

# Inside the turn loop, before extraction:
player_content = normalise_think_closing_tags(player_content)
example_json = _extract_example_json(player_content)
```

**Important**: The normaliser operates on string content. `player_content` is the full Player response string which contains a JSON object. The think blocks are inside JSON string values within that JSON. The normaliser's regex replacement of `<think>...<think>` to `<think>...</think>` is safe to apply to the raw string because `<think>` is not a JSON-significant character sequence.

## Acceptance Criteria

- [ ] `normalise_think_closing_tags` is called on `player_content` before `_extract_example_json`
- [ ] Import added to `entrypoint/generation_loop.py`
- [ ] Existing tests in `tests/test_coach_verdict_parser.py` and `entrypoint/tests/test_generation_loop.py` still pass
- [ ] New test: verify that player content with `<think>...<think>` pattern is normalised before extraction

## Files to Modify

- `entrypoint/generation_loop.py` (add import + normalisation call)
- `entrypoint/tests/test_generation_loop.py` (add test for normalisation before extraction)
