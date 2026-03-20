---
complexity: 5
dependencies:
- TASK-LCT-001
feature_id: FEAT-LCT
id: TASK-LCT-002
implementation_mode: task-work
parent_review: TASK-REV-723B
priority: high
status: design_approved
tags:
- langchain-tools
- rag-retrieval
- chromadb
task_type: feature
title: Implement create_rag_retrieval_tool factory and rag_retrieval tool
wave: 2
---

# Task: Implement create_rag_retrieval_tool factory and rag_retrieval tool

## Description

Implement the `create_rag_retrieval_tool(collection_name: str)` factory function that returns a LangChain `@tool`-decorated `rag_retrieval` function. The tool retrieves curriculum chunks from ChromaDB relevant to a generation target query.

## Deliverables

1. `src/tools/rag_retrieval.py` — Factory + tool implementation
   - `create_rag_retrieval_tool(collection_name: str) -> Callable`
   - Inner `rag_retrieval(query: str, n_results: int = 5) -> str`

## Acceptance Criteria

- [ ] Factory returns a LangChain `@tool`-decorated callable
- [ ] Collection name is bound at factory time, not passed per call
- [ ] ChromaDB `PersistentClient` is lazily initialised on first call
- [ ] Subsequent calls reuse the same client connection
- [ ] Returns formatted chunks with source metadata: `--- Chunk N (source: file.pdf, p.X) ---`
- [ ] Validates n_results: 1 ≤ n_results ≤ 20 (returns error string if out of range)
- [ ] Default n_results is 5
- [ ] Returns all available chunks if collection has fewer than n_results
- [ ] Collection-not-found returns error string (not exception)
- [ ] ChromaDB unavailable returns error string (not exception)
- [ ] Handles chunks with missing source metadata gracefully (returns available info)
- [ ] Collection name with path traversal characters is rejected at factory time
- [ ] All errors returned as descriptive strings, never raised as exceptions (D7)
- [ ] All modified files pass project-configured lint/format checks with zero errors

## Seam Tests

The following seam test validates the integration contract with the ingestion pipeline (FEAT-F59D) which populates the ChromaDB collection this tool queries.

```python
"""Seam test: verify ChromaDB collection interface from ingestion pipeline."""
import pytest


@pytest.mark.seam
@pytest.mark.integration_contract("CHROMADB_COLLECTION")
def test_chromadb_collection_queryable():
    """Verify ChromaDB collection exists and is queryable.

    Contract: Collection populated by ingestion pipeline must be queryable
    via PersistentClient with collection name matching domain config.
    Producer: FEAT-F59D (Ingestion Pipeline)
    """
    # Producer side: collection created by ingestion
    collection_name = ""  # e.g., from domain config

    # Consumer side: verify collection is queryable
    assert collection_name, "Collection name must not be empty"
    # assert collection.count() > 0, "Collection must have indexed chunks"
```

## Reference

- API contract: `docs/design/contracts/API-tools.md` (Tool 1: rag_retrieval)
- BDD scenarios: `features/langchain-tools/langchain-tools.feature` (Groups A-D rag_retrieval scenarios)
- Architecture: ADR-ARCH-004 (ChromaDB embedded PersistentClient)

## Implementation Notes

- Use `chromadb.PersistentClient` — lazy init inside closure, stored as nonlocal variable
- Format: `--- Chunk {i} (source: {filename}, p.{page}) ---\n{text}\n`
- ChromaDB is an optional dependency — use lazy import pattern
- Security: validate collection_name contains only alphanumeric, hyphens, underscores