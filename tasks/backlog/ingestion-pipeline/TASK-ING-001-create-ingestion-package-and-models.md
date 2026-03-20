---
id: TASK-ING-001
title: "Create ingestion package, models, and error hierarchy"
task_type: scaffolding
parent_review: TASK-REV-F479
feature_id: FEAT-ING
wave: 1
implementation_mode: direct
complexity: 3
dependencies: []
status: pending
priority: high
tags: [ingestion, scaffolding, models]
created: 2026-03-19T00:00:00Z
updated: 2026-03-19T00:00:00Z
test_results:
  status: pending
  coverage: null
  last_run: null
---

# Task: Create ingestion package, models, and error hierarchy

## Description

Create the `ingestion/` package with data models and error classes that form the foundation for all other ingestion tasks. This includes the `Chunk` dataclass, `IngestResult` dataclass, and the error hierarchy (`IngestionError`, `DoclingError`, `IndexingError`, `DomainNotFoundError`, `GoalValidationError`).

## Package Structure

```
ingestion/
├── __init__.py          # Public API exports
├── __main__.py          # Stub: `python -m ingestion.ingest` entry point (implemented in TASK-ING-006)
├── models.py            # Chunk, IngestResult, SourceDocument stub
└── errors.py            # Error hierarchy
```

## Models to Create

Based on [API-ingestion.md](../../../docs/design/contracts/API-ingestion.md):

1. **Chunk** — `text: str`, `metadata: dict` (source_file, page_number, chunk_index, docling_mode, domain)
2. **IngestResult** — `domain: str`, `collection_name: str`, `documents_processed: int`, `chunks_created: int`, `elapsed_seconds: float`
3. **SourceDocument** (stub) — `file_pattern: str`, `mode: Literal["standard", "vlm"]`, `notes: str = ""`
   - Note: This is a temporary stub. Once TASK-DC-001 (FEAT-5606) is implemented, replace with `from domain_config.models import SourceDocument`

## Error Hierarchy

```python
class IngestionError(Exception):
    """Base error for ingestion pipeline failures."""

class DomainNotFoundError(IngestionError):
    """Domain directory does not exist."""

class GoalValidationError(IngestionError):
    """GOAL.md missing or Source Documents section invalid."""

class DoclingError(IngestionError):
    """Docling processing failure for a specific document."""

class IndexingError(IngestionError):
    """ChromaDB indexing failure."""
```

## Acceptance Criteria

- [ ] `ingestion/` package is importable (`from ingestion.models import Chunk, IngestResult`)
- [ ] All error classes are importable (`from ingestion.errors import IngestionError, ...`)
- [ ] `Chunk` dataclass has `text` and `metadata` fields
- [ ] `IngestResult` dataclass matches the API contract fields
- [ ] `SourceDocument` stub has `file_pattern`, `mode`, and `notes` fields
- [ ] Error hierarchy has correct inheritance chain
- [ ] `__init__.py` exports public API
- [ ] Unit tests for model construction and error instantiation

## Implementation Notes

- Use `@dataclass` for `Chunk` and `IngestResult` (matching API contract style)
- Use Pydantic `BaseModel` for `SourceDocument` stub (consistent with FEAT-5606 pattern)
- Keep `__main__.py` as a placeholder that prints usage instructions
