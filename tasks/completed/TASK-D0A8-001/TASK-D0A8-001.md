---
id: TASK-D0A8-001
title: Wire per-call LLM timeout to fix infinite HTTP wait
status: completed
created: 2026-04-01T20:00:00Z
updated: 2026-04-01T21:10:00Z
completed: 2026-04-01T21:10:00Z
completed_location: tasks/completed/TASK-D0A8-001/
priority: critical
tags: [timeout, httpx, langchain, resilience]
task_type: implementation
complexity: 4
parent_review: TASK-REV-D0A8
feature_id: FEAT-D0A8
wave: 1
implementation_mode: task-work
dependencies: []
test_results:
  status: passed
  coverage: null
  last_run: 2026-04-01T21:00:00Z
  tests_passed: 782
  tests_failed: 0
  new_tests_added: 4
---

# Task: Wire per-call LLM timeout to fix infinite HTTP wait

## Description

The `llm_timeout` config field (default 300s) is defined in `config/models.py` but never wired to the HTTP client. Worse, LangChain's `ChatOpenAI` passes `timeout=None` to the OpenAI SDK, which defeats the SDK's built-in 600s safety net (the `None` value is interpreted as "disable timeout" rather than "use default", due to the `NotGiven` sentinel pattern).

The effective HTTP timeout for all LLM calls is currently **infinite**. The only protection is the coarse per-target `asyncio.wait_for(timeout=600s)`.

## Root Cause (Validated)

```
LangChain ChatOpenAI (v1.1.12):
  request_timeout = Field(default=None)  ← default is None

OpenAI SDK (v2.29.0):
  def __init__(self, timeout=NOT_GIVEN):
      if is_given(timeout):
          self.timeout = timeout  ← None means "no timeout"
      else:
          self.timeout = DEFAULT_TIMEOUT  ← 600s (never reached)
```

Because `None` is not `NOT_GIVEN`, the SDK treats it as an explicit "disable timeout".

## Scope

Two approaches, in order of preference:

### Approach A: Pass timeout through `init_chat_model` (preferred)

In `agents/model_factory.py`, add `timeout` to the kwargs passed to `init_chat_model()`:

```python
def create_model(config, model_kwargs=None, extra_body=None):
    kwargs = {
        "model_provider": "openai",
        "temperature": config.temperature,
        "max_tokens": config.max_tokens,
        "timeout": config.llm_timeout,  # NEW: wire the timeout
    }
```

**Validation needed**: Confirm that `init_chat_model()` passes `timeout` through to `ChatOpenAI()` as `request_timeout`. If it doesn't, fall back to Approach B.

### Approach B: Wrap `ainvoke()` with `asyncio.wait_for` (guaranteed fix)

In `entrypoint/generation_loop.py`, modify `_invoke_with_retry()`:

```python
async def _invoke_with_retry(agent, input_data, *, max_retries, backoff_base, call_timeout=300):
    for attempt in range(1 + max_retries):
        try:
            return await asyncio.wait_for(
                agent.ainvoke(input_data),
                timeout=call_timeout,
            )
        except asyncio.TimeoutError:
            # Convert to TimeoutError for existing retry logic
            raise TimeoutError(f"LLM call timed out after {call_timeout}s")
        except (RuntimeError, OSError, TimeoutError, ...):
            # existing retry logic
```

Pass `call_timeout=config.llm_timeout` from the caller.

## Constraints

- MUST NOT modify format gate logic (TASK-FPF1-003 decoupled retries must remain)
- MUST NOT modify Coach structured output configuration
- MUST NOT change Player prompt or tools
- `TimeoutError` from per-call timeout MUST be retried by `_invoke_with_retry` (it already catches `TimeoutError`)

## Acceptance Criteria

- [x] `config.llm_timeout` (300s) is wired to the HTTP client or asyncio wrapper
- [x] A stuck LLM call is terminated after 300s (not 600s per-target timeout)
- [x] Existing retry logic handles the timeout (retries with backoff)
- [x] All existing tests pass (`pytest tests/ -v`)
- [x] Per-target timeout (600s) still works as an outer safety net

## Test Requirements

- Unit test: verify that a simulated timeout triggers retry in `_invoke_with_retry`
- Unit test: verify that `create_model()` passes timeout to the underlying client (if Approach A)
- Integration consideration: real vLLM calls should not be affected (300s is generous for ~40 tok/s generation)

## Files to Modify

- `agents/model_factory.py` (Approach A) or `entrypoint/generation_loop.py` (Approach B)
- `tests/` -- add timeout-related test cases
