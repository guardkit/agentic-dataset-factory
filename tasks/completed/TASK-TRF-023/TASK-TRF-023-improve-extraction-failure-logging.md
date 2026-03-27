---
id: TASK-TRF-023
title: Improve JSON extraction failure logging (full content + tail)
status: completed
created: 2026-03-27T12:00:00Z
updated: 2026-03-27T12:00:00Z
completed: 2026-03-27T00:00:00Z
completed_location: tasks/completed/TASK-TRF-023/
priority: medium
tags: [observability, logging, generation-loop, seventh-run]
complexity: 1
parent_review: TASK-REV-TRF7
feature_id: FEAT-TRF7
depends_on: []
wave: 2
implementation_mode: direct
test_results:
  status: passed
  coverage: null
  last_run: 2026-03-27
---

# Task: Improve JSON Extraction Failure Logging

## Problem

When JSON extraction fails in `entrypoint/generation_loop.py:654-658`, the error message from `_extract_json_object` only includes the first 200 chars of raw content. This makes it impossible to determine:
- Whether the JSON was truncated (missing closing braces)
- What the last part of the content looks like
- The total content length

## Fix

Enhance the warning log at line 655-658 to include full content length and the last 200 chars:

```python
except ValueError as exc:
    logger.warning(
        "JSON extraction failed after Coach acceptance: %s\n"
        "Content length: %d chars | Last 200 chars: %s",
        exc,
        len(player_content),
        player_content[-200:],
    )
```

Also add `finish_reason` logging from vLLM responses to detect truncation at the HTTP level.

## Acceptance Criteria

- [x] Extraction failure log includes total content length
- [x] Extraction failure log includes last 200 chars of content
- [x] Existing tests still pass

## Files to Modify

- `entrypoint/generation_loop.py` (enhance warning log)
