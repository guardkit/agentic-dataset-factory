---
id: TASK-ING-006
title: "Implement ingest orchestrator and CLI entry point"
task_type: feature
parent_review: TASK-REV-F479
feature_id: FEAT-ING
wave: 3
implementation_mode: task-work
complexity: 5
dependencies:
  - TASK-ING-002
  - TASK-ING-003
  - TASK-ING-004
  - TASK-ING-005
status: pending
priority: high
tags: [ingestion, orchestrator, cli]
created: 2026-03-19T00:00:00Z
updated: 2026-03-19T00:00:00Z
test_results:
  status: pending
  coverage: null
  last_run: null
---

# Task: Implement ingest orchestrator and CLI entry point

## Description

Implement `ingestion/ingest.py` containing the `ingest_domain()` orchestrator function and `ingestion/__main__.py` with the CLI entry point. The orchestrator ties together all pipeline components: goal reading → docling processing → chunking → ChromaDB indexing. The CLI wraps it with argparse.

## Function Contract

```python
def ingest_domain(
    domain_name: str,
    chunk_size: int = 512,
    overlap: int = 64,
    force: bool = False,
) -> IngestResult:
    """Run the full ingestion pipeline for a domain.

    Processing flow:
    1. Load GOAL.md → parse Source Documents table
    2. For each source document matching file patterns:
       a. Determine Docling mode (standard | vlm)
       b. Process through Docling → extract text
       c. Chunk via chunker.py (fixed-size with overlap)
       d. Assign chunk metadata (source_file, page_number, chunk_index)
    3. Create/replace ChromaDB collection named "{domain_name}"
    4. Index all chunks with embeddings + metadata
    5. Log summary: total documents, total chunks, collection name

    Args:
        domain_name: Name of domain directory under domains/
        chunk_size: Chunk size in characters (default 512)
        overlap: Chunk overlap in characters (default 64)
        force: Re-ingest even if collection exists

    Returns:
        IngestResult with statistics.

    Raises:
        DomainNotFoundError: Domain directory doesn't exist
        GoalValidationError: GOAL.md missing or Source Documents invalid
        IngestionError: Docling or ChromaDB failure
    """
```

## CLI Interface

```bash
python -m ingestion.ingest --domain <domain-name> [--chunk-size N] [--overlap N] [--force]
```

Exit codes per API contract:
- 0: Success
- 1: Domain not found
- 2: GOAL.md/Source Documents invalid
- 3: Docling failure
- 4: ChromaDB failure

## BDD Scenarios Covered

- Ingesting a standard PDF document into ChromaDB (@key-example @smoke) — end-to-end
- Processing multiple source documents in a single run (@key-example @smoke)
- Ingestion produces a summary of work completed (@key-example)
- Docling fails to process one document in a batch → continue with rest (@negative)
- Domain with exactly one source document (@boundary)

## Acceptance Criteria

- [ ] `ingest_domain()` orchestrates the full pipeline: read → process → chunk → index
- [ ] Per-document Docling failures are logged and skipped (remaining documents continue)
- [ ] `IngestResult` populated with correct document count, chunk count, elapsed time
- [ ] CLI parses `--domain`, `--chunk-size`, `--overlap`, `--force` arguments
- [ ] CLI returns correct exit codes (0-4) per API contract
- [ ] CLI prints human-readable summary on success
- [ ] CLI prints error messages to stderr on failure
- [ ] Structured JSON logging at key milestones (per ADR-ARCH-007)
- [ ] All modified files pass project-configured lint/format checks with zero errors

## Implementation Notes

- Use `argparse` for CLI (keep it thin — just parse args and call `ingest_domain()`)
- Use `time.monotonic()` for elapsed time measurement
- Structured logging: `structlog` or `logging` with JSON formatter per ADR-ARCH-007
- Process documents sequentially per ADR-ARCH-006 (no async/parallel)
- ChromaDB persist_directory: read from `agent-config.yaml` with fallback to `./chroma_data`
- Domains directory: `domains/{domain_name}/`
