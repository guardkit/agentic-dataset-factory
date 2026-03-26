---
id: TASK-TRF-006
title: Add write_output retry cap (3 per target)
status: completed
created: 2026-03-26T00:00:00Z
updated: 2026-03-26T00:00:00Z
completed: 2026-03-26T00:00:00Z
completed_location: tasks/completed/TASK-TRF-006/
priority: high
tags: [resilience, token-budget, retry]
complexity: 2
task_type: implementation
parent_review: TASK-REV-FRF3
feature_id: FEAT-TRF
wave: 2
implementation_mode: task-work
depends_on: [TASK-TRF-005]
test_results:
  status: passed
  coverage: null
  last_run: 2026-03-26
---

# Task: Add write_output Retry Cap (3 Per Target)

## Description

In Run 3, the Player retried `write_output` 7 times in a loop with no cap, burning context tokens until the context window was exhausted. After TASK-TRF-005 moves write authority to the orchestrator, the retry cap should be implemented in the generation loop's write-after-accept logic.

If `write_output` validation fails after Coach acceptance (e.g. missing `<think>` block, invalid metadata), the orchestrator should retry up to 3 times by feeding the error back to the Player for revision. After 3 write failures, the target should be rejected.

## Changes Required

### `entrypoint/generation_loop.py`

Add a `write_attempts` counter inside `_process_single_target()`:

```python
MAX_WRITE_ATTEMPTS = 3

# Inside the turn loop, after verdict.is_accepted:
if verdict.is_accepted:
    write_result = write_tool.invoke({"example_json": player_content})
    if write_result.startswith("Error:"):
        write_attempts += 1
        if write_attempts >= MAX_WRITE_ATTEMPTS:
            logger.warning("Write failed %d times, rejecting target %d", write_attempts, target_index)
            return False, turn + 1, rejection_history
        coach_feedback = f"Write validation failed: {write_result}. Fix and resubmit."
        continue
    return True, turn + 1, rejection_history
```

### `config/models.py`

Add `max_write_attempts: int = 3` to `GenerationConfig` so it's configurable via `agent-config.yaml`.

## Acceptance Criteria

- [x] Write retry counter implemented in generation loop
- [x] After 3 write failures, target is rejected (not retried forever)
- [x] `max_write_attempts` configurable in `GenerationConfig`
- [x] Rejection record includes write failure history
- [x] Test: 3 consecutive write failures → target rejected
- [x] Test: Write succeeds on 2nd attempt → target accepted

## Test Execution Log

[Automatically populated by /task-work]
