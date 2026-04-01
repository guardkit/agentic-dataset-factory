---
id: TASK-FPF1-003
title: Decouple format correction retries from turn budget
status: completed
created: 2026-03-31T00:00:00Z
updated: 2026-03-31T00:00:00Z
completed: 2026-03-31T00:00:00Z
priority: medium
tags: [generation-loop, turn-budget, format-gate, regression-fix]
complexity: 4
task_type: implementation
parent_review: TASK-REV-FPF1
feature_id: FEAT-FPF1
wave: 2
implementation_mode: task-work
dependencies: [TASK-FPF1-001, TASK-FPF1-002]
completed_location: tasks/completed/TASK-FPF1-003/
test_results:
  status: passed
  tests_total: 27
  tests_passed: 27
  tests_failed: 0
  last_run: 2026-03-31T00:00:00Z
---

# Task: Decouple format correction retries from turn budget

## Description

Currently the turn loop uses `for turn in range(config.max_turns)` with `continue`
when the format gate fires. Each format gate `continue` consumes a turn from the
3-turn budget, reducing the number of Coach evaluations the target can receive.

In the TASK-REV-FPF1 run, 68 format gate blocks consumed 68 turns. Combined with
write validation failures, targets exhausted their budget before getting meaningful
Coach feedback.

This task restructures the loop so format correction retries don't count toward the
turn budget. Only turns where the Coach actually evaluates count.

## Changes Required

### File: `entrypoint/generation_loop.py`

Replace the `for turn in range(config.max_turns)` loop (starting at approx line 657)
with a while-loop that separates format retries from Coach turns:

```python
coach_turn = 0
format_retries = 0
max_format_retries = config.max_turns  # Allow up to max_turns format retries

while coach_turn < config.max_turns:
    # ... Player generates ...

    # Format gate (does NOT consume a coach_turn)
    try:
        extracted = _extract_json_object(player_content)
        data = json.loads(extracted)
        if "messages" not in data or "metadata" not in data:
            raise ValueError("missing required keys")
    except ValueError:
        format_retries += 1
        if format_retries > max_format_retries:
            # Give up on format correction — count as exhausted
            break
        coach_feedback = "FORMAT ERROR: ..."
        continue

    # Coach evaluates — THIS counts as a turn
    coach_turn += 1
    # ... rest of Coach evaluation, extraction, write validation ...
```

### Key design decisions

1. **Format retries are bounded** by `max_format_retries` (default: same as max_turns)
   to prevent infinite loops on hopeless targets
2. **Coach turns remain at 3** — preserving the quality guarantee
3. **Total Player invocations** can be up to `max_turns + max_format_retries` (6 by
   default), but this is bounded and predictable
4. **Write validation failures** still consume a coach_turn (they represent quality
   issues the Coach should have caught)
5. **Post-gen validation failures** still consume a coach_turn (structural defects)

### Update turn reporting

The `turns_used` return value and `target_tokens` logging need to account for the
new counting:
- `turns_used` should report total Player invocations (for token accounting)
- `coach_turns` should report Coach evaluations (for quality metrics)
- Log both: `"target_complete: index=%d, coach_turns=%d, total_invocations=%d"`

## Acceptance Criteria

- [x] Turn loop restructured as while-loop with separate format retry counter
- [x] Format gate failures do NOT increment coach_turn counter
- [x] Format retries bounded by configurable max_format_retries
- [x] Coach turns still bounded by config.max_turns (default 3)
- [x] Write validation failures still count as a coach_turn
- [x] Post-gen validation failures still count as a coach_turn
- [x] Turn reporting updated to show both coach_turns and total_invocations
- [x] All existing generation loop tests pass
- [x] New test: target with 2 format failures + 1 Coach accept = accepted (not rejected)
- [x] New test: target with max_format_retries exceeded = rejected
- [x] New test: turn count reporting correct for mixed format/coach turns

## Key Files

- `entrypoint/generation_loop.py` (lines 657-957: `_process_single_target`)
- `config/models.py` (add `max_format_retries` to GenerationConfig if desired)
- Generation loop tests

## Dependencies

This task depends on TASK-FPF1-002 (format gate key validation) being complete,
as the format gate check logic should include the key validation.

## Risk

Medium complexity — the turn loop is the core of the pipeline. Careful testing
with edge cases (all-format-fail, mix of format+coach, write validation fail after
format retry) is essential. Consider running the full 77-target test suite after
implementation.
