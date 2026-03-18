# ADR-ARCH-008: Start Fresh on Re-run

**Status:** Accepted
**Date:** 2026-03-16
**Deciders:** ML Engineer + /system-arch session

## Context

If a generation run is interrupted and restarted, the pipeline needs a strategy for handling existing output. Options include appending (risking duplicates), resuming from a checkpoint, or starting fresh.

## Decision

Start fresh on re-run — clean the output directory before starting a new generation run. No append/dedup logic.

## Alternatives Considered

| Alternative | Why Rejected |
|-------------|-------------|
| Append mode with deduplication | Complex dedup logic; risk of subtle duplicates; harder to reason about dataset composition |
| Checkpoint/resume | Requires persistent state tracking per generation target; significant implementation complexity for v1 |

## Consequences

- (+) Most robust — no duplicates, no stale state, no instability
- (+) Simplest implementation — no checkpoint tracking or dedup logic
- (+) Output is always a complete, consistent dataset
- (-) A failed run at example 999/1000 requires regenerating all 1,000 (mitigated by overnight run tolerance)
- (-) Cannot incrementally add examples to an existing dataset (must re-run full pipeline)
