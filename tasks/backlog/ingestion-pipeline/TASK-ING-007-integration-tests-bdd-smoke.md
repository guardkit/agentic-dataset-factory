---
id: TASK-ING-007
title: "Integration tests covering BDD smoke scenarios"
task_type: testing
parent_review: TASK-REV-F479
feature_id: FEAT-ING
wave: 4
implementation_mode: task-work
complexity: 5
dependencies:
  - TASK-ING-006
status: pending
priority: high
tags: [ingestion, testing, integration, bdd]
created: 2026-03-19T00:00:00Z
updated: 2026-03-19T00:00:00Z
test_results:
  status: pending
  coverage: null
  last_run: null
---

# Task: Integration tests covering BDD smoke scenarios

## Description

Create integration tests that exercise the full ingestion pipeline end-to-end, covering the 8 smoke-tagged BDD scenarios from the feature spec. Tests use temporary directories with fixture PDFs and an in-memory or temporary ChromaDB instance.

## Test Structure

```
tests/
└── integration/
    └── test_ingestion_pipeline.py
```

## BDD Smoke Scenarios to Cover

1. **Ingesting a standard PDF document into ChromaDB** — full pipeline with standard mode PDF
2. **Ingesting a scanned PDF document via VLM mode** — full pipeline with VLM mode (can mock Docling VLM if hardware unavailable)
3. **Processing multiple source documents in a single run** — 3 documents, all indexed
4. **Chunks carry source metadata after indexing** — verify metadata fields (source_file, page_number, chunk_index, docling_mode)
5. **Text is split into fixed-size chunks with overlap** — verify chunk sizes and overlap
6. **ChromaDB collection is named after the domain** — verify collection naming
7. **Domain directory does not exist** — verify DomainNotFoundError
8. **GOAL.md is missing from the domain directory** — verify GoalValidationError

## Acceptance Criteria

- [ ] All 8 smoke scenarios have corresponding test functions
- [ ] Tests use temporary directories for domain fixtures (no side effects)
- [ ] Tests use temporary ChromaDB persist_directory (cleaned up after test)
- [ ] Test fixtures include minimal valid PDF files for standard mode testing
- [ ] VLM mode test can be skipped with `@pytest.mark.skipif` if Docling VLM not available
- [ ] Negative tests verify correct exception types and messages
- [ ] Metadata assertions verify all 5 fields (source_file, page_number, chunk_index, docling_mode, domain)
- [ ] Tests pass in CI without GPU access (VLM tests skippable)

## Implementation Notes

- Use `pytest` with `tmp_path` fixture for temporary directories
- Create minimal PDF fixtures using `reportlab` or include small static test PDFs in `tests/fixtures/`
- For Docling mocking: use `unittest.mock.patch` to mock `docling_processor.process_document` when testing without real PDFs
- ChromaDB: use `PersistentClient` with `tmp_path` as persist_directory for isolation
- Consider `@pytest.mark.integration` marker for CI pipeline filtering
- Add `reportlab` (or equivalent) to dev dependencies if generating test PDFs
