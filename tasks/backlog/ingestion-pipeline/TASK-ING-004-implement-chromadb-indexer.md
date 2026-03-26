---
id: TASK-ING-004
title: Implement ChromaDB indexer with collection CRUD and batch upsert
task_type: feature
parent_review: TASK-REV-F479
feature_id: FEAT-ING
wave: 2
implementation_mode: task-work
complexity: 5
dependencies:
- TASK-ING-001
status: in_review
priority: high
tags:
- ingestion
- chromadb
- indexing
created: 2026-03-19 00:00:00+00:00
updated: 2026-03-19 00:00:00+00:00
test_results:
  status: pending
  coverage: null
  last_run: null
autobuild_state:
  current_turn: 1
  max_turns: 35
  worktree_path: /Users/richardwoollcott/Projects/appmilla_github/agentic-dataset-factory/.guardkit/worktrees/FEAT-F59D
  base_branch: main
  started_at: '2026-03-20T16:48:21.493647'
  last_updated: '2026-03-20T17:03:00.577963'
  turns:
  - turn: 1
    decision: approve
    feedback: null
    timestamp: '2026-03-20T16:48:21.493647'
    player_summary: Implementation via task-work delegation
    player_success: true
    coach_success: true
---

# Task: Implement ChromaDB indexer with collection CRUD and batch upsert

## Description

Implement `ingestion/chromadb_indexer.py` that manages ChromaDB collection lifecycle and batch chunk indexing. Uses `PersistentClient` per ADR-ARCH-004, with collection-per-domain naming, force replacement support, and configurable batch sizes.

## Function Contracts

```python
class ChromaDBIndexer:
    def __init__(self, persist_directory: str = "./chroma_data"):
        """Initialize ChromaDB PersistentClient."""

    def collection_exists(self, collection_name: str) -> bool:
        """Check if a collection already exists."""

    def create_or_replace_collection(
        self, collection_name: str, force: bool = False
    ) -> Collection:
        """Create collection, optionally replacing existing one.

        Returns:
            ChromaDB Collection object.

        Raises:
            CollectionExistsError: If collection exists and force=False.
            IndexingError: If ChromaDB is unavailable.
        """

    def index_chunks(
        self,
        collection: Collection,
        chunks: list[Chunk],
        batch_size: int = 500,
    ) -> int:
        """Index chunks into collection with batch upsert.

        Returns:
            Number of chunks successfully indexed.

        Raises:
            IndexingError: If ChromaDB indexing fails.
        """
```

## BDD Scenarios Covered

- ChromaDB collection is named after the domain (@key-example @smoke)
- Chunks carry source metadata after indexing (@key-example @smoke)
- Re-ingesting with force replaces the existing collection (@boundary)
- Collection already exists and force is not enabled → skip (@negative)
- ChromaDB is unavailable during indexing (@negative)
- Indexed data persists across pipeline restarts (@edge-case)
- Embedding fails for a specific chunk during indexing (@edge-case)
- Re-ingestion with force while generation pipeline could be reading (@edge-case)

## Acceptance Criteria

- [ ] `ChromaDBIndexer` uses `PersistentClient` with configurable persist_directory
- [ ] `collection_exists()` correctly detects existing collections
- [ ] `create_or_replace_collection()` creates new collection when none exists
- [ ] `create_or_replace_collection()` with `force=True` deletes and recreates existing collection
- [ ] `create_or_replace_collection()` with `force=False` raises `CollectionExistsError` if collection exists
- [ ] `index_chunks()` indexes chunks with correct metadata (source_file, page_number, chunk_index, docling_mode, domain)
- [ ] `index_chunks()` uses configurable batch_size for batch operations
- [ ] `index_chunks()` handles individual chunk embedding failures gracefully (log + skip)
- [ ] Force re-ingestion logs a warning about concurrent access safety (ASSUM-004)
- [ ] ChromaDB connection failure raises `IndexingError` with descriptive message
- [ ] All modified files pass project-configured lint/format checks with zero errors

## Implementation Notes

- `chromadb.PersistentClient(path=persist_directory)` per ADR-ARCH-004
- Default embedding function: ChromaDB's built-in all-MiniLM-L6-v2
- Batch indexing: `collection.add(ids=[...], documents=[...], metadatas=[...])` in batch_size chunks
- Generate chunk IDs as `{domain}_{source_file}_{chunk_index}` for deterministic deduplication
- Add `chromadb` to pyproject.toml dependencies
- Add `CollectionExistsError(IngestionError)` to `errors.py`
