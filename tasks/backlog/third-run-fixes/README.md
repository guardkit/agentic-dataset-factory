# Third Run Fixes (TASK-REV-FRF3)

## Problem Statement

The third end-to-end run (Nemotron 3 Nano 4B) confirmed that the tool_calls deserialization crash (Run 2) is fixed, but revealed 7 new issues: context window exhaustion at 16K, 8 leaked DeepAgents backend tools, Player bypassing Coach evaluation, `grade_target` type coercion bug, model too small for `<think>` blocks, and no retry cap on write failures.

## Solution Approach

1. **Switch to Qwen3.5-35B-A3B-FP8** — 262K context, BFCL-V4 67.3 (tool calling), native `<think>` support, 50 tok/s on GB10
2. **Remove FilesystemBackend** — eliminates 8 leaked tools, saves ~3K tokens/call
3. **Orchestrator-gated writes** — follow GuardKit pattern: Player generates, Coach evaluates, orchestrator writes
4. **Fix type coercion** — cast `field_value` to `str()` at validation boundary
5. **Add retry cap** — max 3 write failures per target

## Subtask Summary

| ID | Task | Wave | Priority | Complexity | Mode |
|----|------|------|----------|-----------|------|
| TRF-001 | Update vLLM script for Qwen3.5-35B | 1 | P0 | 2 | task-work |
| TRF-002 | Update agent-config.yaml | 1 | P0 | 1 | direct |
| TRF-003 | Remove FilesystemBackend from Player | 1 | P0 | 2 | task-work |
| TRF-004 | Fix grade_target type coercion | 1 | P0 | 1 | direct |
| TRF-005 | Orchestrator-gated writes (Coach bypass) | 2 | P1 | 5 | task-work |
| TRF-006 | Add write_output retry cap | 2 | P1 | 2 | task-work |
| TRF-007 | Fourth end-to-end run | 3 | P1 | 3 | direct |

## Review Source

- Review: [TASK-REV-FRF3-review-report.md](../../../.claude/reviews/TASK-REV-FRF3-review-report.md)
- Run log: `docs/reviews/first-run/vllm-nemotron3-nano-1.md`
