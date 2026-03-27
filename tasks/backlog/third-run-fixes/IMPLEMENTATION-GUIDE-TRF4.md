# Implementation Guide: Fourth Run Fixes (TASK-REV-TRF4)

## Problem Statement

The fourth pipeline run with Qwen3.5-35B-A3B-FP8 failed to complete any targets due to a Coach verdict parsing bug. Additionally, the Player agent did not call its RAG tool, and token usage is not logged.

## Solution Approach

3 implementation tasks addressing findings from TASK-REV-TRF4 review.

## Execution Strategy

### Wave 1 (all tasks — no dependencies between them)

| Task | Title | Priority | Mode | Effort |
|------|-------|----------|------|--------|
| TASK-TRF-008 | Fix Coach verdict parser preamble handling | P0 Critical | task-work | 1-2h |
| TASK-TRF-009 | Investigate missing rag_retrieval calls | P1 High | task-work | 2-4h |
| TASK-TRF-010 | Add token usage logging | P2 Low | direct | 30m |

**Parallel execution**: All 3 tasks touch different code areas and can run concurrently.

- TASK-TRF-008 modifies `_parse_coach_verdict()` in generation_loop.py
- TASK-TRF-009 investigates Player tool binding in agents/player.py and tools/
- TASK-TRF-010 adds logging after `_invoke_with_retry()` calls

### Critical Path

**TASK-TRF-008 is the only blocker for the next pipeline run.** The pipeline cannot complete any targets until the Coach verdict parser is fixed.

TASK-TRF-009 and TASK-TRF-010 improve quality and observability but do not block execution.

## Post-Fix Validation

After implementing TASK-TRF-008 (minimum) or all three tasks:

1. Re-run pipeline with 1 target: `python agent.py`
2. Verify Coach verdict parses successfully
3. Verify at least 1 target reaches accept/reject outcome
4. Check train.jsonl or rejected.jsonl has content
5. If all pass → proceed to overnight 1,000-target run

## Provenance

- Parent review: TASK-REV-TRF4
- Review report: `.claude/reviews/TASK-REV-TRF4-review-report.md`
- Feature ID: FEAT-TRF
- Previous fixes: TASK-TRF-001 through TASK-TRF-007 (from TASK-REV-FRF3)
