---
id: TASK-OR-001
title: Coach retry with JSON reinforcement on parse failure
status: completed
created: 2026-03-29T00:00:00Z
updated: 2026-03-29T00:00:00Z
completed: 2026-03-29T00:00:00Z
priority: critical
tags: [coach, json-parsing, retry, overnight-readiness]
task_type: implementation
complexity: 4
parent_review: TASK-REV-7617
feature_id: FEAT-OR
depends_on: []
wave: 1
implementation_mode: task-work
test_results:
  status: passed
  tests_total: 35
  tests_passed: 35
  tests_failed: 0
  coverage: null
  last_run: 2026-03-29T00:00:00Z
---

# Task: Coach Retry with JSON Reinforcement on Parse Failure

## Problem

Coach role confusion causes 15% rejection rate (3/20 targets in Run 12). When
`_parse_coach_verdict()` raises `ValueError`, the target is immediately rejected.
No retry is attempted.

The 15% rate exceeds the 5% threshold set in TASK-REV-1F3F R3 as the trigger
for implementing retry logic.

## Solution

When `_parse_coach_verdict()` raises `ValueError`, retry the Coach invocation
**once** with an explicit JSON-only system message reinforcement prepended to
the conversation.

## Regression Guards

- **DO NOT** disable Coach reasoning (`enable_thinking: false`) — Run 5 explicitly
  rejected this as "counter to architectural intent"
- **DO NOT** strip Player Layer 1 thinking from Coach input — Run 9 withdrew this
  recommendation as "too fragile"
- **DO NOT** add complex retry loops — single retry with reinforcement is sufficient
  per TASK-REV-1F3F R3

## Implementation

In `entrypoint/generation_loop.py`, within the per-target Player-Coach loop:

1. After `_parse_coach_verdict()` raises `ValueError` on the first attempt:
2. Log the parse failure at INFO level
3. Re-invoke the Coach with the same input but prepend a reinforcement system message
4. If the retry succeeds, continue with the verdict as normal
5. If the retry also fails, reject the target (existing behaviour)

```python
# Pseudocode — inside the Coach evaluation block
try:
    verdict = _parse_coach_verdict(coach_content)
except ValueError as parse_exc:
    if not coach_retried:
        coach_retried = True
        logger.info(
            "Coach JSON parse failed (index=%d, turn=%d), retrying with "
            "JSON reinforcement: %s",
            absolute_index, turn, parse_exc,
        )
        # Build reinforcement message
        reinforcement_msg = {
            "role": "system",
            "content": (
                "IMPORTANT: Your previous response was not valid JSON. "
                "You MUST respond with ONLY a JSON object matching the "
                "CoachVerdict schema. No prose, no reasoning text, no "
                "markdown. Start your response with { and end with }."
            ),
        }
        # Re-invoke Coach with reinforcement
        retry_input = {
            "messages": [
                reinforcement_msg,
                {"role": "user", "content": player_content},
            ]
        }
        coach_response = await _invoke_with_retry(
            coach, retry_input,
            max_retries=config.llm_retry_attempts,
            backoff_base=config.llm_retry_backoff,
        )
        coach_content = _extract_coach_content(coach_response)
        verdict = _parse_coach_verdict(coach_content)
        # If this also fails, ValueError propagates to the existing
        # except handler and target is rejected
    else:
        raise  # Already retried, let it propagate
```

## Files to Modify

- `entrypoint/generation_loop.py` — Add retry logic around `_parse_coach_verdict()` call

## Acceptance Criteria

- [ ] Single retry on Coach JSON parse failure with reinforcement message
- [ ] Retry logged at INFO level with target index and turn number
- [ ] If retry succeeds, verdict is used normally (acceptance/revision continues)
- [ ] If retry fails, target rejected with `llm_failure` reason (existing behaviour)
- [ ] Coach reasoning remains enabled (no `enable_thinking` changes)
- [ ] Player content passed to Coach unchanged (no Layer 1 stripping)
- [ ] Token usage for retry logged (observable in pipeline output)
- [ ] Existing tests pass (no regressions)
- [ ] New test: mock Coach returning prose on first call, JSON on retry

## Test Requirements

- Unit test: `_parse_coach_verdict` raises ValueError → retry invoked → succeeds
- Unit test: `_parse_coach_verdict` raises ValueError → retry invoked → also fails → target rejected
- Unit test: `_parse_coach_verdict` succeeds first time → no retry
- Integration: verify retry message format matches CoachVerdict schema instructions
