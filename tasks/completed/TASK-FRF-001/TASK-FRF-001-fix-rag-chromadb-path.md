---
id: TASK-FRF-001
title: Fix rag_retrieval ChromaDB path mismatch
status: completed
created: 2026-03-25T00:00:00Z
updated: 2026-03-25T12:00:00Z
completed: 2026-03-25T12:00:00Z
priority: critical
tags: [bug-fix, rag, chromadb, p0]
complexity: 2
parent_review: TASK-REV-E2A7
feature_id: FEAT-FRF
wave: 1
implementation_mode: task-work
dependencies: []
test_results:
  status: pass
  coverage: null
  last_run: 2026-03-25T12:00:00Z
---

# Task: Fix rag_retrieval ChromaDB Path Mismatch

## Description

The `rag_retrieval` tool at `src/tools/rag_retrieval.py:122` calls `chromadb.PersistentClient()` with no `path` argument. ChromaDB defaults to `./chroma`, but data was ingested to `./chroma_data`. This means the tool opens an empty database and fails with "Collection not found" on every call.

## Root Cause

See review report: `.claude/reviews/TASK-REV-E2A7-review-report.md` — Finding 1.

Three ChromaDB clients exist in the codebase:
- `ingestion/chromadb_indexer.py:39` — `path=persist_directory` (default `"./chroma_data"`) — CORRECT
- `entrypoint/startup.py:155` — `path="./chroma_data"` — CORRECT
- `src/tools/rag_retrieval.py:122` — `PersistentClient()` (no path) — **BUG**

## Changes Required

1. **`src/tools/rag_retrieval.py`**: Add `persist_directory` parameter to `create_rag_retrieval_tool()` factory. Pass it to `PersistentClient(path=persist_directory)` in the `_get_client()` closure. Default to `"./chroma_data"`.

2. **`src/tools/tool_factory.py`**: Pass `persist_directory` through `create_player_tools()` to `create_rag_retrieval_tool()`. Accept it as an optional parameter with default `"./chroma_data"`.

3. **Update tests**: `ingestion/tests/test_chromadb_indexer.py` and any rag_retrieval tests should verify the path is passed correctly.

## Acceptance Criteria

- [x] `create_rag_retrieval_tool()` accepts optional `persist_directory` parameter (default `"./chroma_data"`)
- [x] `PersistentClient(path=persist_directory)` used instead of `PersistentClient()`
- [x] `create_player_tools()` passes `persist_directory` through
- [x] Existing unit tests pass
- [x] New test verifies PersistentClient receives the correct path argument

## Files to Modify

- `src/tools/rag_retrieval.py` (primary — ~3 line change)
- `src/tools/tool_factory.py` (pass-through parameter)
- Tests for rag_retrieval tool
