# Implementation Guide — Overnight Readiness

## Source Review

TASK-REV-7617 (Revised v3 — History-Aware)

## Regression Guards

These constraints are derived from 12 runs of iterative development and MUST be
respected by all implementation tasks:

| Constraint | Source | Reason |
|-----------|--------|--------|
| Coach reasoning stays ENABLED | TASK-REV-TRF5 (Run 5) | "Coach needs to reason deeply about example quality" |
| Player content passed to Coach unchanged | TASK-REV-1F3F R2 (Run 9) | Stripping Layer 1 is fragile, withdrawn |
| `--reasoning-parser qwen3` stays DISABLED | TRF-024 (Run 8) | Breaks Layer 2 think blocks in training data |
| Player/Coach prompts unchanged | TASK-REV-1F3F (Run 9) | Working correctly for 85% of targets |
| No complex retry loops | TASK-REV-1F3F R3 (Run 9) | Single retry is sufficient |

## Execution Strategy

### Wave 1: Pre-Overnight Minimum (~6h) — COMPLETE

| Task | Description | Effort | Status |
|------|-------------|--------|--------|
| TASK-OR-001 | Coach retry with JSON reinforcement | 2-3h | DONE (has bug) |
| TASK-OR-002 | Grade distribution in GOAL.md | 3-4h | DONE |

### Wave 1.5: Critical Bugfixes (~1h) — BLOCKS OVERNIGHT

TASK-REV-R2A1 review found two bugs in the TASK-OR-001 retry path. Execute in parallel:

| Task | Description | Effort | Method |
|------|-------------|--------|--------|
| TASK-OR-006 | Fix retry message format (dual system msg) | 30m | /task-work |
| TASK-OR-007 | Add httpx.HTTPStatusError to exception handlers | 30m | /task-work |

**Root cause (source-verified)**: `create_agent()` unconditionally prepends
`system_prompt` on every `ainvoke()` call (`langchain/agents/factory.py:1270-1271`).
The retry passed a `system` message in the input → dual system messages → vLLM 400.
Additionally, `httpx.HTTPStatusError` is not caught by either exception handler,
so the 400 crashes the pipeline instead of rejecting the target.

### Wave 2: Quality Improvements (~9h)

Execute after Wave 1.5 validated. Can be parallel:

| Task | Description | Effort | Method |
|------|-------------|--------|--------|
| TASK-OR-003 | Structural validation rules | 4-5h | /task-work |
| TASK-OR-004 | Structured output opt-in | 3-4h | /task-work |

### Wave 3: Launch

| Task | Description | Effort | Method |
|------|-------------|--------|--------|
| TASK-OR-005 | Validation run + overnight config | 1h | direct |

**Critical path**: OR-006 + OR-007 → OR-005 → overnight. Wave 2 is NOT blocking.

## Expected Outcomes

| Metric | Current (Run 12) | After Wave 1.5 | After Wave 2 |
|--------|-------------------|----------------|-------------|
| Rejection rate | 20% | ~5% | ~1% |
| Grade diversity | 92.3% Grade 7 | Distributed across 4-9 | Same |
| Multi-turn essay | 50% compliant | 50% (unchanged) | 100% |
| Pipeline crashes | Yes (Run 2) | None | None |
| Overnight capacity | ~340 targets/10h | Same | Same |
