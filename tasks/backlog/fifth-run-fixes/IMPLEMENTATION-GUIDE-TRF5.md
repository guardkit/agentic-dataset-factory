# Implementation Guide: Fifth Run Fixes (TASK-REV-TRF5)

## Problem Statement

The fifth pipeline run with Qwen3.5-35B-A3B-FP8 failed to complete any targets due to two interacting P0 issues: (1) Coach response content is empty because vLLM's reasoning parser splits think blocks into `reasoning_content` which LangChain's ChatOpenAI discards, and (2) all 8 DeepAgents platform tools are leaked to both agents because `backend=None` doesn't disable FilesystemMiddleware.

Additionally, langchain-skills were lost from `~/.claude/` on 2026-03-17 and need restoring before implementation begins.

## Solution Approach

5 implementation tasks across 3 waves, addressing findings from TASK-REV-TRF5 review.

## Execution Strategy

### Wave 0: Prerequisites (before any code changes)

| Task | Title | Priority | Mode | Effort |
|------|-------|----------|------|--------|
| TASK-TRF-011 | Restore langchain-skills from backup | P0 Critical | direct | 5m |

**Must complete before Wave 1.** Restores Claude Code's expert DeepAgents knowledge.

### Wave 1: P0 Blockers (parallel — independent code areas)

| Task | Title | Priority | Mode | Effort |
|------|-------|----------|------|--------|
| TASK-TRF-012 | Fix Coach tool leakage + revert Player to FilesystemBackend | P0 Critical | task-work | 2-4h |
| TASK-TRF-013 | Fix Coach reasoning content extraction | P0 Critical | task-work | 2-3h |

**Parallel execution**: These tasks touch different code areas:
- TASK-TRF-012 modifies `agents/coach.py` (bypass create_deep_agent) and `agents/player.py` (revert to FilesystemBackend)
- TASK-TRF-013 modifies `entrypoint/generation_loop.py` (reasoning content fallback)

**Note**: Fixing TASK-TRF-012 alone may resolve TASK-TRF-013's symptom indirectly — if the Coach has no leaked tools, it may output JSON directly in `content`. Both fixes should be implemented for defense in depth.

### Wave 2: Quality & Performance (parallel — after Wave 1 verified)

| Task | Title | Priority | Mode | Effort |
|------|-------|----------|------|--------|
| TASK-TRF-014 | Cap Player rag_retrieval loops | P1 High | task-work | 1h |
| TASK-TRF-015 | Investigate example truncation | P2 Medium | task-work | 1h |

**These depend on Wave 1 being complete** — the pipeline must be functional before performance tuning.

### Critical Path

```
Wave 0: TASK-TRF-011 (restore skills, 5m)
    ↓
Wave 1: TASK-TRF-012 (tool leakage) ‖ TASK-TRF-013 (reasoning content)
    ↓ both complete
Wave 2: TASK-TRF-014 (tool loops) ‖ TASK-TRF-015 (truncation)
    ↓
Sixth pipeline run (validation)
```

**TASK-TRF-012 is the highest-value single fix.** If only one task can be done, do this one — it may resolve both P0 issues.

## Post-Fix Validation

After implementing Wave 1 (minimum):

1. Re-run pipeline with 1 target: `python agent.py`
2. Verify Coach has 0 tools (check log for tool schemas)
3. Verify Coach verdict parses successfully (no empty-content errors)
4. Verify at least 1 target reaches accept/reject outcome
5. Check token usage logging shows reasonable Coach prompt tokens (should be ~3K less without leaked tool schemas)
6. If all pass → proceed to Wave 2, then overnight 1,000-target run

## Provenance

- Parent review: TASK-REV-TRF5
- Review report: `.claude/reviews/TASK-REV-TRF5-review-report.md`
- Feature ID: FEAT-TRF5
- Previous fixes: TASK-TRF-001 through TASK-TRF-010 (from TASK-REV-FRF3 and TASK-REV-TRF4)
- Exemplar repo: `deepagents-player-coach-exemplar` (original correct design)
