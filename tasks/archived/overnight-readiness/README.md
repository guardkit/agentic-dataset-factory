# Overnight Readiness — Feature Implementation (ARCHIVED)

> **Archived 2026-03-30**: Superseded by `tasks/backlog/long-run-1-fixes/` (FEAT-LR1),
> which is based on actual Long Run 1 production data (1000 targets).
> OR-001/OR-002 were completed. OR-006/OR-007 were completed and cross-referenced in LR1.
> OR-003/OR-004/OR-005 are superseded by LR1-001, LR1-002, and the completed overnight run.

## Problem

Run 12 (factory-run-1) revealed a 20% rejection rate (4/20 targets), with 15% caused by
Coach role confusion (JSON parsing failures). Grade target monoculture (92.3% Grade 7) and
essay feedback multi-turn compliance (50%) also need fixing before overnight production run.

## Source Review

- Parent review: TASK-REV-7617 (Revised v3 — History-Aware)
- Report: `.claude/reviews/TASK-REV-7617-review-report.md`

## Solution Approach

History-safe fixes that respect all prior architectural decisions:
- Coach reasoning stays **enabled** (Run 5 decision)
- Player content stays **intact** (Run 9 R2 withdrawal)
- `--reasoning-parser qwen3` stays **disabled** (Run 8 TRF-024)

## Subtasks

| Task | Description | Wave | Status | Method | Effort |
|------|-------------|------|--------|--------|--------|
| TASK-OR-001 | Coach retry with JSON reinforcement on parse failure | 1 | DONE (has bug) | task-work | 2-3h |
| TASK-OR-002 | Grade distribution in GOAL.md + orchestrator | 1 | DONE | task-work | 3-4h |
| **TASK-OR-006** | **Fix retry message format (dual system msg bug)** | **1.5** | **backlog** | **task-work** | **30m** |
| **TASK-OR-007** | **Add httpx.HTTPStatusError to exception handlers** | **1.5** | **backlog** | **task-work** | **30m** |
| TASK-OR-003 | Structural validation rules from GOAL.md | 2 | backlog | task-work | 4-5h |
| TASK-OR-004 | Structured output opt-in toggle (experimental) | 2 | backlog | task-work | 3-4h |
| TASK-OR-005 | Validation run + overnight config | 3 | backlog | direct | 1h |

## Execution Strategy

**Wave 1** (complete): TASK-OR-001 + TASK-OR-002 (~6h) — DONE
**Wave 1.5** (critical bugfix): TASK-OR-006 + TASK-OR-007 (~1h) — BLOCKS OVERNIGHT
**Wave 2** (quality improvements): TASK-OR-003 + TASK-OR-004 (~9h)
**Wave 3** (launch): TASK-OR-005 (validation + config)

### Critical Path to Overnight

TASK-OR-006 + TASK-OR-007 → TASK-OR-005 → overnight run.
Wave 2 tasks are NOT blocking overnight.

## Regression Guards

DO NOT:
- Disable Coach reasoning (`enable_thinking: false`) without quality study
- Strip Player Layer 1 thinking before Coach
- Re-enable `--reasoning-parser qwen3`
- Change Player/Coach prompts
