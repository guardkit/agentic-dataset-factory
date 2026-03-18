# ADR-ARCH-006: Sequential Generation for v1

**Status:** Accepted
**Date:** 2026-03-16
**Deciders:** ML Engineer + /system-arch session

## Context

The generation pipeline produces ~1,000 training examples per domain run. Each example requires multiple Player-Coach cycles (generation + evaluation). We need to decide whether to run cycles sequentially or in parallel.

## Decision

Use sequential generation for v1 — one Player-Coach cycle at a time.

## Alternatives Considered

| Alternative | Why Rejected |
|-------------|-------------|
| Batch parallel (multiple concurrent cycles) | The Coach model (120B via vLLM) is the bottleneck; vLLM handles request queuing internally so parallelising the Player doesn't help. GPU memory management complexity not justified for v1. |

## Consequences

- (+) Simplest implementation — predictable, easy to debug
- (+) Predictable GPU memory usage on GB10
- (+) LangSmith traces are clean and sequential — easy to analyse
- (+) No concurrency bugs or race conditions in output file writes
- (-) ~25 hours for 1,000 examples with local Coach (acceptable for overnight runs)
- (-) Cannot exploit API-mode parallelism if multiple API calls could run concurrently

Can revisit for v2 if API-mode Coach becomes the primary path and throughput becomes a concern.
