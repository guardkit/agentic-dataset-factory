---
id: TASK-OR-006
title: Fix coach retry message format — merge reinforcement into user message
status: completed
created: 2026-03-29T11:00:00Z
updated: 2026-03-29T14:30:00Z
completed: 2026-03-29T14:30:00Z
priority: critical
tags: [bugfix, coach-retry, message-format, overnight-readiness]
task_type: implementation
complexity: 2
parent_review: TASK-REV-R2A1
feature_id: FEAT-OR
depends_on: []
wave: 1
implementation_mode: task-work
completed_location: tasks/completed/TASK-OR-006/
test_results:
  status: passed
  coverage: null
  last_run: 2026-03-29T14:30:00Z
---

# Task: Fix Coach Retry Message Format

## Problem

TASK-OR-001 implemented coach retry with JSON reinforcement, but the retry path
crashes the pipeline with HTTP 400 from vLLM. Root cause (confirmed from framework
source at `langchain/agents/factory.py:1270-1271`):

1. Retry builds `{messages: [system(reinforcement), user(player)]}`
2. `create_agent()` **unconditionally prepends** the Coach's system_prompt on every `ainvoke()`
3. vLLM receives `[system, system, user]` — rejects with "System message must be at the beginning"

### Framework Contract (source-verified)

```python
# langchain/agents/factory.py:1270-1271
messages = request.messages          # our ainvoke() input
if request.system_message:
    messages = [request.system_message, *messages]  # ALWAYS prepends
```

**Rule**: Never pass `system` role messages in `ainvoke()` input. The framework
owns system message injection. Additional instructions must use `user` role.

## Solution

Change the retry reinforcement from a `system` message to a merged `user` message
(Option B from TASK-REV-R2A1 review).

### Before (broken — `entrypoint/generation_loop.py:742-759`)

```python
retry_input: dict[str, Any] = {
    "messages": [
        {
            "role": "system",
            "content": (
                "IMPORTANT: Your previous response was not "
                "valid JSON. You MUST respond with ONLY a "
                "JSON object matching the CoachVerdict schema."
                " No prose, no reasoning text, no markdown. "
                "Start your response with { and end with }."
            ),
        },
        {
            "role": "user",
            "content": player_content,
        },
    ]
}
```

### After (fixed)

```python
retry_input: dict[str, Any] = {
    "messages": [
        {
            "role": "user",
            "content": (
                "IMPORTANT: Your previous response was not "
                "valid JSON. You MUST respond with ONLY a "
                "JSON object matching the CoachVerdict schema."
                " No prose, no reasoning text, no markdown. "
                "Start your response with { and end with }."
                "\n\n" + player_content
            ),
        },
    ]
}
```

### Why This Works

- Input: `{messages: [user(reinforcement + player)]}`
- Framework prepends: `[system(coach_prompt+AGENTS.md), user(reinforcement + player)]`
- vLLM receives: `[system, user]` — valid, 200 OK

## Architectural Constraints (all preserved)

| Constraint | Source | Status |
|-----------|--------|--------|
| Coach reasoning stays enabled | Run 5 (TASK-REV-TRF5) | PRESERVED — no reasoning config changes |
| Layer 1 thinking flows intact | Run 9 R2 (TASK-REV-1F3F) | PRESERVED — player_content unchanged |
| Single retry only | Run 9 R3 (TASK-REV-1F3F) | PRESERVED — coach_retried flag unchanged |
| No prompt changes | Multiple runs | PRESERVED — only retry message format changes |
| Structured output stays P2 | Run 12 (TASK-REV-7617) | PRESERVED — not affected |

## Files to Modify

- `entrypoint/generation_loop.py` — Lines 742-759: change retry_input message format

## Test Updates

Update `tests/test_coach_retry_json_reinforcement.py`:
- `test_retry_reinforcement_message_format`: Assert `messages[0]["role"] == "user"` (was "system")
- Assert single message in retry input (was two messages)
- Assert content contains both reinforcement text AND player_content
- All other retry tests should pass unchanged (they test behaviour, not message format)

## Acceptance Criteria

- [ ] Retry input contains single `user` message (no `system` messages)
- [ ] Reinforcement text prepended to player_content in the user message
- [ ] Existing 35 retry tests pass (with format assertion updates)
- [ ] No regressions in main test suite

## Test Requirements

- Update: `test_retry_reinforcement_message_format` — verify user role, single message, merged content
- New: `test_retry_input_has_no_system_messages` — explicitly assert no system messages in retry_input
- Existing: all other retry tests should pass without changes
