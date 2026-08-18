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

---

## Dated note — 2026-08-14: the v2 revisit condition arrived; batched legs shipped (sequential stays the default)

The named revisit condition ("if throughput becomes a concern") is now met, and a second,
harder condition arrived with it:

1. **Throughput** — the qa-verifier lane measured the cost of alternating Player/Coach seats
   per row: 82.3s + 22.5s cold loads PER ROW, a 15–24h floor per run
   (`domains/qa-verifier/RUNBOOK-qav-generation.md`, "batched legs" vs "co-residency").
2. **Mutually exclusive serving states** — the GCSE regeneration lane's teacher
   (DeepSeek-V4-Flash-0731, two-Spark TP=2 per its dgx-spark runbook) DRAINS the llama-swap
   Coach fleet for the whole serving session. Teacher legs and Coach legs cannot alternate at
   all: batched legs is REQUIRED there, not an optimisation.

**What shipped (additive — this ADR's decision stands for the default path):**

- A two-window batched-legs mode: `entrypoint/batch_loop.py` +
  `entrypoint/batch_state.py`, engaged ONLY by the `--batch` flag or a `batch:` config block
  (`config/models.py::BatchConfig`). Window 1 runs ALL Player/teacher legs (per-row outputs
  checkpointed to an append-only `.batch_state.jsonl` — a crash loses at most the in-flight
  row); the run then STOPS at the window boundary with a printed operator instruction (the
  serving drain/revive acts stay the operator's, per the serving runbooks — this repo never
  edits serving config); window 2 resumes via the extended `--resume` semantics and runs ALL
  Coach legs plus the existing acceptance/validation/write path. Coach-revise rows become the
  next pass's window 1, bounded by `generation.max_turns` (or `batch.max_passes`).
- The window-1 teacher seat rides the same `ModelConfig` seam as every agent
  (`batch.teacher`, falling back to `player`) — no model names in code.

**Sequential remains the default.** `run_generation_loop()` is untouched and byte-compatible;
domains without a `batch:` block (coach-agent, recruiter-agent, product-owner) behave exactly
as before.
