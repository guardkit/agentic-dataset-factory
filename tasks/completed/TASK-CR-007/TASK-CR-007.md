---
id: TASK-CR-007
title: Add structured outputs fallback on coach refusal
status: completed
created: 2026-04-08T00:00:00Z
updated: 2026-04-08T00:00:00Z
completed: 2026-04-08T00:00:00Z
priority: high
complexity: 5
tags: [coach, refusal, structured-outputs, vllm]
parent_review: TASK-REV-CC01
feature_id: FEAT-CR
wave: null
implementation_mode: standard
dependencies: [TASK-CR-006]
test_results:
  status: passed
  coverage: null
  last_run: 2026-04-08T00:00:00Z
  tests_added: 11
  tests_total: 625
---

# Task: Add structured outputs fallback on coach refusal

## Description

When a Coach refusal occurs (detected by TASK-CR-006), and the reframed-prompt retry also fails, attempt a **second fallback** that retries without the vLLM `structured_outputs` JSON schema constraint.

The hypothesis is that the combination of structured outputs mode + educational content evaluation triggers Qwen 3.5-35B's safety layer more aggressively than free-form text would. Without the JSON schema constraint, the model may produce a free-text response that can be parsed into a `CoachVerdict`.

### Current behaviour (after TASK-CR-006)

1. First attempt → refusal
2. Reframed prompt retry → refusal
3. Target rejected as `coach_refusal`

### Desired behaviour

1. First attempt → refusal
2. Reframed prompt retry (TASK-CR-006) → refusal
3. **New: Retry without structured_outputs constraint** → model responds with free-form text
4. Parse free-form text into `CoachVerdict` JSON
5. If parsing succeeds → use verdict normally
6. If parsing fails or model refuses again → reject as `coach_refusal`

### Implementation approach

The Coach agent is created with `extra_body={"structured_outputs": {"json": ...}}` in `agents/coach.py:86-90`. For the fallback retry, we need to invoke the LLM without this constraint. Options:

**Option A — Create a second Coach model instance** without `extra_body` at startup, use it only for fallback retries. Simple but doubles model objects.

**Option B — Direct LLM call** bypassing the DeepAgent for the fallback, using the underlying `ChatOpenAI` model without structured outputs. More surgical but couples the loop to LangChain internals.

**Option C — Pass extra_body override per-call** if the DeepAgent/LangChain API supports it. Cleanest but needs API investigation.

## Acceptance Criteria

- [ ] When both the initial call and reframed retry produce refusals, a third attempt is made without structured outputs
- [ ] The fallback attempt uses the same Coach system prompt but without JSON schema constraint
- [ ] Free-form text response is parsed into `CoachVerdict` using existing `_parse_coach_verdict()`
- [ ] If free-form parsing succeeds, the verdict is used normally
- [ ] If free-form parsing fails, target is rejected as `coach_refusal`
- [ ] Fallback usage is logged at INFO level with `coach_content_source: structured_outputs_fallback`
- [ ] Metrics track how many verdicts were recovered via the fallback path

## Test Requirements

- [ ] Unit test: fallback retry is triggered only after both initial + reframed retries fail with `CoachRefusalError`
- [ ] Unit test: free-form text containing valid JSON is successfully parsed
- [ ] Unit test: free-form text without valid JSON results in `coach_refusal` rejection
- [ ] Integration test: refusal → reframe retry → refusal → fallback → success path
- [ ] Integration test: refusal → reframe retry → refusal → fallback → refusal → rejection path

## Implementation Notes

Key files:
- `agents/coach.py` — structured outputs setup (line 80-93)
- `entrypoint/generation_loop.py` — coach invocation and retry logic (line 773+)
- `agents/model_factory.py` — model creation (for Option A)
