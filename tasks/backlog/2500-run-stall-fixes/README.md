# Feature: 2500-Run Stall Fixes

## Problem Statement

The 2500-target GCSE English tutor generation run (Qwen3.5-35B-A3B-FP8 on GB10) stalled at index 1405 of 2500. Root cause analysis (TASK-REV-D0A8) identified three issues:

1. **Mac sleep killed the process** -- the generation loop ran on a Mac laptop which suspended twice during the 28-hour run, with the final suspension being terminal
2. **No per-call HTTP timeout** -- LangChain passes `timeout=None` to the OpenAI SDK, defeating its built-in 600s safety net, leaving only the coarse per-target 600s timeout
3. **41% format gate failure rate** -- the Player model outputs reasoning text instead of JSON, wasting ~40% of compute on retries

## Solution Approach

Apply 3 targeted fixes, write a learnings document, then resume from checkpoint 1404:

1. Wire `config.llm_timeout` (300s) into the HTTP client to restore per-call timeout protection
2. Lower Player temperature from 0.6 to 0.4 to reduce reasoning-text leakage
3. Run on GB10 directly with tmux (not Mac over Tailscale) to eliminate sleep/suspend risk
4. Resume the run from checkpoint 1404 for the remaining 1,094 targets
5. Document findings as a learnings reference for future runs

## Subtask Summary

| Task | Description | Wave | Mode |
|------|-------------|------|------|
| TASK-D0A8-001 | Wire per-call LLM timeout | 1 | task-work |
| TASK-D0A8-002 | Reduce Player temperature to 0.4 | 1 | direct |
| TASK-D0A8-003 | GB10 setup instructions and run script | 1 | task-work |
| TASK-D0A8-005 | Write learnings document | 1 | direct |
| TASK-D0A8-004 | Resume generation run | 2 | manual |

## Architectural Constraints

All tasks must comply with these binding decisions from prior reviews:

| Constraint | Source |
|-----------|--------|
| Do NOT apply structured output to Player | TASK-LR1-001, TASK-REV-649A |
| Do NOT add BAD/GOOD examples to Player prompt | TASK-FPF1-001 (revert) |
| Coach reasoning must stay ENABLED | Run 5 decision (TASK-REV-7617) |
| Format retries decoupled from Coach turns | TASK-FPF1-003 |
| Checkpoint resume via append mode | ADR-ARCH-010 |

## Parent Review

- **TASK-REV-D0A8**: [Review Report](../../docs/reviews/TASK-REV-D0A8-review-report.md)
