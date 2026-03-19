# ADR-ARCH-010: Overnight Run Resilience (Retry, Checkpoint, Timeout)

> Status: **Accepted**
> Date: 2026-03-18
> Related: ADR-ARCH-006 (sequential generation), ADR-ARCH-008 (start fresh), DDR-003 (3-turn limit)

## Context

The generation pipeline runs overnight (~25 hours for 1,000 targets at ~90s/turn on GB10). Three failure modes are unaddressed:

1. **Transient LLM failures** — vLLM can return 503s under memory pressure, and cloud APIs rate-limit. A single unhandled failure kills the run on one failed call out of ~2,000+.
2. **No checkpoint/resume** — ADR-ARCH-008 cleans output on restart, so a crash at target 800/1,000 loses all progress. The 800 accepted examples in `train.jsonl` are deleted on re-run.
3. **Hung LLM calls** — vLLM OOM or deadlock blocks the pipeline indefinitely. With no per-target timeout, the entire overnight run stalls on a single target.

## Decision

Add three resilience mechanisms, all configurable via `agent-config.yaml`:

### 1. LLM Retry with Exponential Backoff

```yaml
generation:
  llm_retry_attempts: 3       # Retries per LLM call
  llm_retry_backoff: 2.0      # Exponential backoff base (seconds)
  llm_timeout: 300             # Per-call timeout (seconds)
```

Use LangChain's native `max_retries` where available (ChatOpenAI, ChatAnthropic both support it). For local vLLM, wrap with equivalent retry logic.

### 2. Checkpoint/Resume

- Write `output/.checkpoint` containing the last completed target index after each target (accepted or rejected).
- Add `--resume` flag to entrypoint. Resume mode:
  - Skips output directory clean
  - Reads existing output file line counts
  - Continues generation from checkpoint index
- Default behaviour remains `--fresh` (ADR-ARCH-008 unchanged).

### 3. Per-Target Timeout

```yaml
generation:
  target_timeout: 600          # Seconds — discard target if exceeded
```

On timeout: log to `rejected.jsonl` with `"reason": "timeout"`, continue to next target.

## Rationale

- **Retry:** A 25-hour run makes ~2,000+ LLM calls. Even 99.9% reliability means ~2 transient failures per run. Without retry, the run dies.
- **Checkpoint:** Re-running 25 hours because of a failure at hour 20 is unacceptable. Append-mode output means accepted examples survive — only the generation loop state needs checkpointing.
- **Timeout:** A single hung target should not block 999 remaining targets. 600 seconds (10 minutes) is generous — typical max is ~4.5 minutes (3 turns × 90s).

## Alternatives Considered

- **No resilience (current state):** Acceptable for short test runs but not for overnight production runs.
- **Full job scheduler (Celery, etc.):** Over-engineered for a single-machine modular monolith.
- **Automatic resume without flag:** Risk of silently appending to stale output. Explicit `--resume` vs `--fresh` is safer.

## Consequences

- Overnight runs survive transient LLM failures without human intervention
- A failed 25-hour run can resume from where it stopped, saving hours
- Individual hung targets don't block the remaining pipeline
- Adds 4 config fields to `agent-config.yaml` `generation:` section
- Checkpoint file (`output/.checkpoint`) is an implementation detail — does not change output format
- `--resume` vs `--fresh` is an explicit user choice, not automatic
