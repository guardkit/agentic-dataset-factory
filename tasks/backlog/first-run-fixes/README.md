# First Run Fixes (FEAT-FRF)

## Problem

The first end-to-end pipeline run (Qwen2.5-14B via vLLM on GB10) produced 0 accepted examples due to two P0 bugs:

1. **ChromaDB path mismatch** — `rag_retrieval` tool opens `./chroma` (ChromaDB default) instead of `./chroma_data` where data was ingested
2. **Array vs scalar validation** — `write_output` Step 9 checks `list not in list` for array metadata fields, which always fails

## Solution

Two targeted fixes, both isolated to the `src/tools/` layer:

- **FRF-001**: Pass `path="./chroma_data"` to `PersistentClient()` in rag_retrieval
- **FRF-002**: Add `isinstance(field_value, list)` branch in write_output Step 9 for element-wise validation

## Subtasks

| Task | Priority | Status | Wave |
|------|----------|--------|------|
| TASK-FRF-001 | P0 | backlog | 1 |
| TASK-FRF-002 | P0 | backlog | 1 |
| TASK-FRF-003 | P1 | backlog | 2 |

## Provenance

- Parent review: TASK-REV-E2A7
- Review report: `.claude/reviews/TASK-REV-E2A7-review-report.md`
