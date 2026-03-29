---
id: TASK-OR-007
title: Add httpx.HTTPStatusError to pipeline exception handlers
status: completed
created: 2026-03-29T11:00:00Z
updated: 2026-03-29T11:00:00Z
completed: 2026-03-29
priority: high
tags: [bugfix, resilience, exception-handling, overnight-readiness]
task_type: implementation
complexity: 2
parent_review: TASK-REV-R2A1
feature_id: FEAT-OR
depends_on: []
wave: 1
implementation_mode: task-work
test_results:
  status: passed
  coverage: null
  last_run: 2026-03-29
  tests_added: 9
  tests_total: 94
  all_passing: true
---

# Task: Add httpx.HTTPStatusError to Pipeline Exception Handlers

## Problem

When vLLM returns an HTTP error (400, 429, 500, etc.), it surfaces as
`httpx.HTTPStatusError`. This exception type is not caught by either:

1. `_invoke_with_retry()` (line 396) — catches `(RuntimeError, OSError, TimeoutError, ValidationError)`
2. Per-target handler (line 1076) — catches `(RuntimeError, OSError, ValidationError, ValueError)`

Any HTTP error from the LLM backend crashes the entire pipeline instead of
rejecting the individual target and continuing.

## Evidence

Factory-run-2 crash trace:
```
vLLM 400 → httpx.HTTPStatusError → misses _invoke_with_retry → misses per-target handler → PIPELINE CRASH
```

## Solution

Add `httpx.HTTPStatusError` to both exception handlers with appropriate retry
semantics.

### 1. `_invoke_with_retry()` (line 396)

```python
# Before:
except (RuntimeError, OSError, TimeoutError, ValidationError) as exc:

# After:
except (RuntimeError, OSError, TimeoutError, ValidationError, httpx.HTTPStatusError) as exc:
```

**Retry semantics for HTTP errors**:
- **429 (Rate Limit)**: RETRY with backoff (transient)
- **5xx (Server Error)**: RETRY with backoff (transient)
- **4xx (Client Error, except 429)**: Do NOT retry — fail fast (retrying won't help)

Add a guard inside the except block:

```python
except (RuntimeError, OSError, TimeoutError, ValidationError, httpx.HTTPStatusError) as exc:
    last_exc = exc
    # Don't retry client errors (except 429 rate limit)
    if isinstance(exc, httpx.HTTPStatusError):
        status = exc.response.status_code
        if 400 <= status < 500 and status != 429:
            raise  # Client error — retrying won't help
    if attempt < total_attempts - 1:
        # ... existing backoff logic
```

### 2. Per-target handler (line 1076)

```python
# Before:
except (RuntimeError, OSError, ValidationError, ValueError) as exc:

# After:
except (RuntimeError, OSError, ValidationError, ValueError, httpx.HTTPStatusError) as exc:
```

This is the safety net — any HTTP error that escapes `_invoke_with_retry` gets
caught here, the target is rejected with `llm_failure` reason, and the pipeline
continues to the next target.

### 3. Import

Add at the top of `entrypoint/generation_loop.py`:

```python
import httpx
```

## Architectural Alignment

This is an **additive extension** of the per-target exception handler pattern
established in Run 9 (TASK-REV-1F3F R1) when `ValueError` was added. Same
pattern, new exception type.

## Files Modified

- `entrypoint/generation_loop.py`:
  - Added `import httpx`
  - Added `httpx.HTTPStatusError` to `_invoke_with_retry` except clause
  - Added 4xx fail-fast guard
  - Added `httpx.HTTPStatusError` to per-target except clause

## Tests Added

- `tests/test_httpstatuserror_handling.py` (9 tests):
  - `test_http_400_not_retried` — 400 raises immediately, no retry
  - `test_http_422_not_retried` — 422 raises immediately, no retry
  - `test_http_429_retries_with_backoff` — 429 retries (3 attempts)
  - `test_http_500_retries_with_backoff` — 500 retries (3 attempts)
  - `test_http_502_retries` — 502 retries
  - `test_http_429_succeeds_on_retry` — 429 then success returns result
  - `test_http_400_rejects_target_not_crash` — per-target handler catches, pipeline continues
  - `test_http_500_rejects_target_not_crash` — per-target handler catches, pipeline continues
  - `test_all_http_errors_rejects_all_continues` — all targets error, all rejected, no crash

## Acceptance Criteria

- [x] `httpx.HTTPStatusError` caught in `_invoke_with_retry()`
- [x] 4xx errors (except 429) fail fast without retry
- [x] 429 and 5xx errors retry with backoff
- [x] `httpx.HTTPStatusError` caught in per-target handler
- [x] Target rejected with `llm_failure` reason on HTTP error
- [x] Pipeline continues to next target after HTTP error
- [x] Existing tests pass (no regressions)
