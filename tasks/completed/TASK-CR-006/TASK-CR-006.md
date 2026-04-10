---
id: TASK-CR-006
title: Add refusal detection and retry with reframed prompt
status: completed
created: 2026-04-08T00:00:00Z
updated: 2026-04-08T12:00:00Z
completed: 2026-04-08T12:00:00Z
completed_location: tasks/completed/TASK-CR-006/
priority: high
complexity: 5
tags: [coach, refusal, retry, vllm]
parent_review: TASK-REV-CC01
feature_id: FEAT-CR
wave: null
implementation_mode: standard
dependencies: []
test_results:
  status: passed
  coverage: null
  last_run: 2026-04-08T12:00:00Z
---

# Task: Add refusal detection and retry with reframed prompt

## Description

In `_extract_coach_content()` (`entrypoint/generation_loop.py:496-568`), detect the `refusal` key in `additional_kwargs` and log the refusal reason text. Then add a refusal-specific retry path in the coach invocation section (~line 773-860) that reframes the prompt as a "quality assessment" rather than content evaluation, to avoid triggering Qwen 3.5-35B's safety layer.

This should be a **new retry mechanism separate from the existing JSON parse retry** (which handles `ValueError` from `_parse_coach_verdict`).

### Current behaviour

1. Coach returns `content=''` with `additional_kwargs={'refusal': '...'}`
2. `_extract_coach_content()` checks 4 fallback paths, finds nothing
3. Raises generic `ValueError` — no refusal-specific logging or handling
4. Target rejected as `llm_failure`

### Desired behaviour

1. `_extract_coach_content()` detects `refusal` key in `additional_kwargs`
2. Logs the refusal reason at WARNING level
3. Raises a **distinct exception** (e.g., `CoachRefusalError`) instead of generic `ValueError`
4. Caller catches `CoachRefusalError` and retries with a reframed prompt that:
   - Emphasises the Coach's role as a "quality assessor" / "rubric evaluator"
   - Avoids reproducing the Player's content verbatim (summarise or reference it)
   - Explicitly states "you are not generating this content, only scoring it"
5. If the retry also refuses, reject as `coach_refusal` (distinct from `llm_failure`)

## Acceptance Criteria

- [x] New `CoachRefusalError` exception class (or similar) distinguishes refusals from other extraction failures
- [x] `_extract_coach_content()` detects `additional_kwargs['refusal']` and raises `CoachRefusalError` with the refusal reason
- [x] Refusal reason is logged at WARNING level
- [x] Coach invocation loop catches `CoachRefusalError` and retries once with a reframed prompt
- [x] Reframed prompt emphasises assessment/scoring role, not content reproduction
- [x] If retry also refuses, target is rejected with reason `coach_refusal` (not `llm_failure`)
- [x] Refusal count is tracked in generation summary stats
- [x] Existing JSON parse retry path is unaffected

## Test Requirements

- [x] Unit test: `_extract_coach_content()` raises `CoachRefusalError` when `additional_kwargs` contains `refusal` key
- [x] Unit test: `_extract_coach_content()` still raises `ValueError` for empty content without refusal key
- [x] Unit test: reframed prompt includes assessment framing language
- [ ] Integration test: refusal → retry → success path (deferred to integration test suite)
- [ ] Integration test: refusal → retry → refusal → rejection path with `coach_refusal` reason (deferred to integration test suite)

## Implementation Notes

Key files:
- `entrypoint/generation_loop.py` — `_extract_coach_content()` (line 496) and coach invocation (line 773)
- `tests/test_coach_verdict_parser.py` — existing empty-content test (line 263)
