---
id: TASK-ING-001
title: Create ingestion package, models, and error hierarchy
task_type: scaffolding
parent_review: TASK-REV-F479
feature_id: FEAT-ING
wave: 1
implementation_mode: direct
complexity: 3
dependencies: []
status: in_review
priority: high
tags:
- ingestion
- scaffolding
- models
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
  started_at: '2026-03-20T16:44:07.019643'
  last_updated: '2026-03-20T16:48:20.331650'
  turns:
  - turn: 1
    decision: approve
    feedback: null
    timestamp: '2026-03-20T16:44:07.019643'
    player_summary: 'Created the ingestion/ package with models, error hierarchy,
      and comprehensive tests. Chunk and IngestResult are @dataclass (matching API
      contract style). SourceDocument is a Pydantic BaseModel stub (consistent with
      domain_config pattern, to be replaced by domain_config.models.SourceDocument
      when FEAT-5606 lands). Error hierarchy: IngestionError(Exception) as base, with
      DomainNotFoundError, GoalValidationError, DoclingError, and IndexingError as
      direct children. __init__.py re-exports all public'
    player_success: true
    coach_success: true
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
