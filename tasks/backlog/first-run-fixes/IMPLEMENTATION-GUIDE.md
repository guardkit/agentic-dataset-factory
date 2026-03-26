# Implementation Guide: First Run Fixes (FEAT-FRF)

## Source Review

- Review task: TASK-REV-E2A7
- Review report: `.claude/reviews/TASK-REV-E2A7-review-report.md`
- Source logs: `docs/reviews/first-run/vllm-qwen-25-1.md`

## Wave Breakdown

### Wave 1: P0 Bug Fixes (2 tasks — parallel)

These two tasks are independent and can run in parallel. They fix the two bugs that blocked all output on the first run.

| Task | Title | Mode | Complexity | Files |
|------|-------|------|------------|-------|
| TASK-FRF-001 | Fix rag_retrieval ChromaDB path | task-work | 2 | `src/tools/rag_retrieval.py`, `src/tools/tool_factory.py` |
| TASK-FRF-002 | Fix write_output array validation | task-work | 3 | `src/tools/write_output.py`, `domains/gcse-english-tutor/GOAL.md` |

**No file conflicts between tasks — safe for parallel execution.**

### Wave 2: Validation (1 task — sequential after Wave 1)

| Task | Title | Mode | Complexity | Depends On |
|------|-------|------|------------|------------|
| TASK-FRF-003 | Second end-to-end run | manual | 4 | TASK-FRF-001, TASK-FRF-002 |

Requires GB10 hardware available with vLLM running on port 8002.

## Execution Strategy

```
Wave 1 (parallel):  FRF-001 (ChromaDB path fix) ─┐
                    FRF-002 (array validation)  ─┘
                                                  │
Wave 2 (sequential): FRF-003 (second run)  ───────  (after both fixes, requires GB10)
```

## Implementation Modes

- **task-work**: FRF-001, FRF-002 — use `/task-work` for full quality gates
- **manual**: FRF-003 — requires GB10 hardware, human-operated

## Risk Assessment

Both Wave 1 fixes are low-risk, isolated changes:
- FRF-001: Adding a path parameter to an existing factory — no behavioral change to other callers
- FRF-002: Adding array-element validation alongside existing scalar validation — the `isinstance(field_value, list)` check only activates for list values, so scalar fields are unaffected
