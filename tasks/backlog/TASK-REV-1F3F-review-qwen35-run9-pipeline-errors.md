---
id: TASK-REV-1F3F
title: Review Qwen3.5 run-9 pipeline errors
status: review_complete
created: 2026-03-27T22:30:00Z
updated: 2026-03-27T22:30:00Z
priority: high
tags: [pipeline, qwen35, coach-parsing, second-run, debugging]
task_type: review
complexity: 5
review_results:
  score: null
  findings_count: 5
  recommendations_count: 1
  decision: implement
  revised: true
  report_path: .claude/reviews/TASK-REV-1F3F-review-report.md
test_results:
  status: pending
  coverage: null
  last_run: null
---

# Task: Review Qwen3.5 run-9 pipeline errors

## Description

Analyse the output in `docs/reviews/second-run/qwen35-run-9.md` from the second-run overnight batch.
The previous run (run-8) succeeded, but run-9 failed after completing only 2 of 20 targets.

## Source File

`docs/reviews/second-run/qwen35-run-9.md`

## Initial Findings

### What succeeded
- **Index 0** (Literary analysis, single-turn, reasoning): Accepted, score 5, 1 turn
- **Index 1** (Character analysis — Macbeth, reasoning): Accepted, score 5, 2 turns

### What failed
- **Index 2** (Character analysis — An Inspector Calls, reasoning): Pipeline crashed

### Error Details

The pipeline failed with:
```
Pipeline failed: Failed to parse CoachVerdict: no JSON object found in response.
Raw content (first 200 chars): 'The user wants me to generate a training example for:
- Category: Character analysis — An Inspector Calls
- Type: reasoning
- Count: 80

I need to create a ShareGPT conversation format with:
1. System'
```

**Root cause hypothesis — Coach role confusion**: The Coach agent (Qwen3.5-35B on vLLM) returned text that mimics the Player's thinking pattern instead of producing a JSON evaluation verdict. The Coach response starts with "The user wants me to generate a training example for..." which is Player-like reasoning, not a Coach evaluation.

The Player's output for index 2 included a long `</think>` reasoning preamble followed by a JSON training example, all sent as the `user` message to the Coach. The Coach model appears to have followed the pattern it saw in the input rather than adhering to its system prompt to return a structured JSON verdict.

### Key observations
1. The error is logged twice (lines 192-193), suggesting a retry or duplicate logging
2. The Coach successfully evaluated indices 0 and 1 — this failure is intermittent
3. The Player's output for index 2 was larger (4042 chars vs 3871 for index 0) and contained more reasoning preamble
4. The Coach completed with 896 completion tokens — it generated a full response, just the wrong type
5. Pipeline terminated immediately — no retry/fallback for Coach parsing failures
6. Model: Qwen/Qwen3.5-35B-A3B-FP8 on `promaxgb10-41b1:8002`

## Questions to investigate

1. Is the Coach receiving the Player's `</think>` reasoning text in the user message? Should it be stripped before sending to Coach?
2. Does the pipeline have retry logic for Coach verdict parsing failures? (Appears not — immediate crash)
3. Was Qwen3.5-35B-A3B-FP8 the same model used in run-8 (which succeeded)?
4. Is there a pattern in which targets trigger role confusion (longer Player outputs, specific categories)?
5. Should the pipeline implement a retry with a "reminder" system message when Coach returns non-JSON?

## Acceptance Criteria

- [x] Root cause of Coach role confusion confirmed or alternative hypothesis established
- [x] Comparison with run-8 to identify what changed (if anything)
- [x] Determine if this is a model-level issue (Qwen3.5 nondeterminism) or a pipeline issue (missing retry/stripping)
- [x] Recommendations for pipeline hardening documented
- [x] Decision on whether to re-run with fixes or workaround

## Test Requirements

- [ ] N/A — review task (no code changes)

## Implementation Notes

### Revised Review Findings (Deep Dive)

**Root cause confirmed as TWO independent issues:**

1. **Pipeline bug (the crash)**: `_parse_coach_verdict()` raises `ValueError` at `generation_loop.py:351`, but the per-target handler at line 1011 only catches `RuntimeError | OSError | ValidationError`. Verified by tracing the exception propagation through 5 levels of call stack — ValueError is completely unhandled until the catch-all `except Exception` at `agent.py:228`.

2. **Model behaviour (the trigger)**: Coach received Player's full output including Layer 1 model CoT (`<think>The user wants me to generate...</think>`) followed by the JSON training example. The Coach mimicked the Player's reasoning pattern instead of returning a JSON verdict. This is stochastic — same model succeeded for indices 0 and 1.

**What changed from run-8**: Only the GOAL.md target counts (1 → production values). Same model, same endpoint, same config. Run-8 processed 1 target; run-9 processes 20. More targets = higher probability of hitting intermittent Coach failure.

### Think Block History Review

Reviewed all 10 previous runs' handling of `<think>` blocks. Key prior decisions:
- **TRF-024 (run 8)**: DISABLED `--reasoning-parser qwen3` because it stripped Layer 2 think blocks from inside training example JSON strings
- **TRF-020/021 (run 7)**: Added `normalise_think_closing_tags()` before JSON extraction
- **TRF-029 (run 10)**: Added explicit `<think>` format instruction to Player prompt
- **TRF-027 (run 10)**: Coach prompt validates think block presence

**Initial R2/R3 recommendations (strip think blocks, add Coach retry) WITHDRAWN** after history review:
- Stripping Layer 1 thinking before Coach would require reliably distinguishing it from Layer 2 — risky and complex
- Coach retry adds token cost for marginal benefit
- With R1 applied, the pipeline already rejects and continues past Coach failures

### Final Recommendation

**One-line fix**: Add `ValueError` to except tuple at `generation_loop.py:1011`. Monitor rejection rate on re-run. If >5% Coach parsing rejections, then consider structured output or retry logic.

## Test Execution Log

[Automatically populated by /task-work]
