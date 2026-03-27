---
id: TASK-TRF-010
title: Add token usage logging from vLLM API responses
status: completed
created: 2026-03-26T00:00:00Z
updated: 2026-03-26T12:00:00Z
completed: 2026-03-26T12:00:00Z
completed_location: tasks/completed/TASK-TRF-010/
priority: low
tags: [enhancement, observability, logging, P2]
complexity: 2
task_type: implementation
parent_review: TASK-REV-TRF4
feature_id: FEAT-TRF
wave: 1
implementation_mode: direct
depends_on: []
test_results:
  status: passed
  coverage: null
  last_run: 2026-03-26T12:00:00Z
---

# Task: Add Token Usage Logging

## Description

The pipeline does not log token usage statistics (prompt_tokens, completion_tokens, total_tokens) from vLLM API responses. This makes it impossible to assess context window utilisation, track costs, or diagnose context overflow issues.

## Implementation

After each LLM API call, log the `response.usage` object at INFO level:

```python
logger.info(
    "LLM usage",
    agent=agent_role,
    prompt_tokens=response.usage.prompt_tokens,
    completion_tokens=response.usage.completion_tokens,
    total_tokens=response.usage.total_tokens,
)
```

Also log cumulative per-target totals and a summary at pipeline completion.

## Files to Modify

- `entrypoint/generation_loop.py` — After `_invoke_with_retry()` calls, extract and log usage

## Acceptance Criteria

- [x] Token usage logged for each LLM call (Player and Coach)
- [x] Per-target cumulative totals logged at target completion
- [x] Pipeline summary includes total tokens consumed
- [x] Existing tests pass

## Test Execution Log

- 39 passed (34 existing + 5 new) in 5.30s
- 18 integration smoke tests passed
- Pre-existing failure in test_goal_md_sections_1_to_5 (unrelated)
