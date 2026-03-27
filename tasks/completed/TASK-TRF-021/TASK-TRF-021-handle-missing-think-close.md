---
id: TASK-TRF-021
title: Extend normalise_think_closing_tags to handle missing close tags (EOF pattern)
status: completed
created: 2026-03-27T12:00:00Z
updated: 2026-03-27T16:05:00Z
completed: 2026-03-27T16:05:00Z
completed_location: tasks/completed/TASK-TRF-021/
priority: critical
tags: [bug-fix, think-blocks, validator, seventh-run]
complexity: 3
parent_review: TASK-REV-TRF7
feature_id: FEAT-TRF7
depends_on: []
wave: 1
implementation_mode: task-work
test_results:
  status: passed
  coverage: 100
  last_run: 2026-03-27T16:00:00Z
---

# Task: Handle Missing Think Close Tags (EOF Pattern)

## Problem

`normalise_think_closing_tags()` in `synthesis/validator.py:197-210` handles the `<think>...<think>` malformed close pattern but does NOT handle the case where `<think>` is opened with no closing tag at all.

Run 7 analysis shows:
- 16 instances of `<think>...<think>` (handled by current normaliser)
- **15 instances of `<think>...EOF`** (NOT handled -- no closing tag of any kind)

The current logic:
1. If `</think>` exists in content, return unchanged (early exit)
2. Replace `<think>...<think>` with `<think>...</think>`

After step 2, if no `<think>...<think>` pair was found (because the model just opened `<think>` and kept writing), the content still has no closing tag.

## Fix

Extend `normalise_think_closing_tags()` to handle the EOF pattern. After the existing malformed-close fix, check if there are still unclosed `<think>` tags and close them:

```python
def normalise_think_closing_tags(content: str) -> str:
    if "</think>" in content.lower():
        return content
    # Existing: fix <think>...<think> pairs
    result = _MALFORMED_CLOSE_RE.sub(r"\1</think>", content)
    # NEW: if still no </think> after malformed-close fix,
    # find the last <think> and close it before any trailing visible text
    if "<think>" in result.lower() and "</think>" not in result.lower():
        # Append </think> after the last <think> block content
        last_open = result.lower().rfind("<think>")
        if last_open >= 0:
            # Insert </think> at end of content
            result = result + "</think>"
    return result
```

**Edge cases to handle**:
- Multiple `<think>` opens with no closes (nested or sequential)
- `<think>` at the very end of content (empty think block)
- Mixed: some `<think>...<think>` pairs AND some `<think>...EOF`

## Acceptance Criteria

- [ ] `normalise_think_closing_tags` handles `<think>...EOF` pattern (no closing tag at all)
- [ ] Existing tests still pass (malformed close, correct tags unchanged, idempotent)
- [ ] New tests added for:
  - `<think>reasoning content with no close tag` -> appends `</think>`
  - `<think>block1<think><think>block2` (mixed patterns)
  - `<think>` at end of string (edge case)
  - Content with `</think>` already present (unchanged -- existing test)

## Files to Modify

- `synthesis/validator.py` (extend `normalise_think_closing_tags`)
- `synthesis/tests/test_validation_logic.py` (add new test cases to `TestNormaliseThinkClosingTags`)
