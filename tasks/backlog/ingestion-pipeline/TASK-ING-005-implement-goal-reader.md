---
id: TASK-ING-005
title: Implement GOAL.md Source Documents reader
task_type: feature
parent_review: TASK-REV-F479
feature_id: FEAT-ING
wave: 2
implementation_mode: direct
complexity: 3
dependencies:
- TASK-ING-001
status: in_review
priority: high
tags:
- ingestion
- goal-md
- file-resolution
created: 2026-03-19 00:00:00+00:00
updated: 2026-03-19 00:00:00+00:00
consumer_context:
- task: TASK-DC-001
  consumes: SourceDocument
  framework: Pydantic v2 BaseModel
  driver: pydantic
  format_note: SourceDocument model with file_pattern (str), mode (Literal['standard',
    'vlm']), and notes (str) fields. Until TASK-DC-001 completes, use the stub in
    ingestion/models.py
test_results:
  status: pending
  coverage: null
  last_run: null
autobuild_state:
  current_turn: 1
  max_turns: 35
  worktree_path: /Users/richardwoollcott/Projects/appmilla_github/agentic-dataset-factory/.guardkit/worktrees/FEAT-F59D
  base_branch: main
  started_at: '2026-03-20T16:48:21.488025'
  last_updated: '2026-03-20T16:59:45.662156'
  turns:
  - turn: 1
    decision: approve
    feedback: null
    timestamp: '2026-03-20T16:48:21.488025'
    player_summary: 'Implemented ingestion/goal_reader.py with two public functions:
      read_source_documents() and resolve_source_files(). The module parses the Source
      Documents markdown table from GOAL.md using regex-based section extraction and
      table parsing, then resolves glob patterns against the sources/ directory. Security
      measures include path traversal detection via regex and realpath-based prefix
      checking. All functions use the existing error hierarchy (DomainNotFoundError,
      GoalValidationError) from ingestion'
    player_success: true
    coach_success: true
---

# Task: Implement GOAL.md Source Documents reader

## Description

Implement `ingestion/goal_reader.py` that reads the Source Documents section from a domain's GOAL.md file and resolves file patterns against the `sources/` directory. This module bridges the GOAL.md parser (FEAT-5606) with the ingestion pipeline.

## Function Contracts

```python
def read_source_documents(domain_path: Path) -> list[SourceDocument]:
    """Read Source Documents from GOAL.md in the given domain directory.

    Args:
        domain_path: Path to domain directory (e.g., domains/gcse-english-tutor/)

    Returns:
        List of SourceDocument objects from the Source Documents table.

    Raises:
        DomainNotFoundError: If domain_path does not exist
        GoalValidationError: If GOAL.md is missing or Source Documents section is invalid
    """

def resolve_source_files(
    domain_path: Path,
    source_documents: list[SourceDocument],
) -> list[tuple[Path, str]]:
    """Resolve file patterns to actual file paths in sources/ directory.

    Args:
        domain_path: Path to domain directory
        source_documents: Parsed SourceDocument list from GOAL.md

    Returns:
        List of (file_path, mode) tuples for matched files.

    Raises:
        GoalValidationError: If no files match any patterns
    """
```

## BDD Scenarios Covered

- Processing multiple source documents in a single run (@key-example @smoke)
- File patterns with glob wildcards match the correct source files (@edge-case)
- Domain directory does not exist (@negative @smoke)
- GOAL.md is missing from the domain directory (@negative @smoke)
- Source Documents section in GOAL.md is malformed (@negative)
- Sources directory contains no matching files (@negative)
- Source file with path traversal in filename is rejected (@edge-case @negative)
- Domain with both standard and VLM source documents (@edge-case)

## Acceptance Criteria

- [ ] `read_source_documents()` parses Source Documents from GOAL.md
- [ ] `resolve_source_files()` expands glob patterns against `sources/` directory
- [ ] Missing domain directory raises `DomainNotFoundError`
- [ ] Missing GOAL.md raises `GoalValidationError`
- [ ] Malformed Source Documents section raises `GoalValidationError`
- [ ] No matching files raises `GoalValidationError` with descriptive message
- [ ] Path traversal patterns (e.g., `../`, `..\\`) in filenames are rejected with error logged
- [ ] Resolved files are returned as (absolute_path, mode) tuples
- [ ] All modified files pass project-configured lint/format checks with zero errors

## Seam Tests

The following seam test validates the integration contract with the producer task. Implement this test to verify the boundary before integration.

```python
"""Seam test: verify SourceDocument contract from TASK-DC-001."""
import pytest


@pytest.mark.seam
@pytest.mark.integration_contract("SourceDocument")
def test_source_document_format():
    """Verify SourceDocument matches the expected format.

    Contract: SourceDocument model with file_pattern (str), mode (Literal['standard', 'vlm']), and notes (str) fields
    Producer: TASK-DC-001
    """
    # Producer side: import SourceDocument (stub or real)
    from ingestion.models import SourceDocument

    # Consumer side: verify fields match contract
    doc = SourceDocument(file_pattern="*.pdf", mode="standard", notes="test")
    assert hasattr(doc, "file_pattern"), "SourceDocument must have file_pattern field"
    assert hasattr(doc, "mode"), "SourceDocument must have mode field"
    assert doc.mode in ("standard", "vlm"), f"mode must be 'standard' or 'vlm', got: {doc.mode}"
    assert hasattr(doc, "notes"), "SourceDocument must have notes field"
```

## Implementation Notes

- **Initial implementation:** Use stub `SourceDocument` from `ingestion/models.py` and manually parse the Source Documents markdown table from GOAL.md
- **Future migration:** Once FEAT-5606 completes, replace with `from domain_config import load_goal_config; config.source_documents`
- Use `pathlib.Path.glob()` for file pattern resolution
- Security: validate all resolved paths are within `domain_path/sources/` (no path traversal)
- Use `os.path.realpath()` + prefix check to prevent symlink-based traversal
