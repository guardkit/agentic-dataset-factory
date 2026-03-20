---
complexity: 4
created: 2026-03-19 00:00:00+00:00
dependencies:
- TASK-ING-001
feature_id: FEAT-ING
id: TASK-ING-002
implementation_mode: task-work
parent_review: TASK-REV-F479
priority: high
status: design_approved
tags:
- ingestion
- chunking
- langchain
task_type: feature
test_results:
  coverage: null
  last_run: null
  status: pending
title: Implement chunker with RecursiveCharacterTextSplitter
updated: 2026-03-19 00:00:00+00:00
wave: 1
---

# Task: Implement chunker with RecursiveCharacterTextSplitter

## Description

Implement `ingestion/chunker.py` containing the `chunk_text()` function that splits extracted text into fixed-size chunks with overlap. Uses LangChain's `RecursiveCharacterTextSplitter` as specified in the API contract.

## Function Contract

```python
def chunk_text(
    text: str,
    chunk_size: int = 512,
    overlap: int = 64,
    source_metadata: dict | None = None,
) -> list[Chunk]:
    """Split text into fixed-size chunks with overlap.

    Uses RecursiveCharacterTextSplitter from LangChain.

    Args:
        text: Extracted text from Docling
        chunk_size: Target chunk size in tokens
        overlap: Overlap between consecutive chunks in tokens
        source_metadata: Metadata to attach to each chunk

    Returns:
        List of Chunk objects with text and metadata.
    """
```

## BDD Scenarios Covered

- Text is split into fixed-size chunks with overlap (@key-example @smoke)
- Document text shorter than the chunk size → exactly 1 chunk (@boundary)
- Single-page document produces at least one chunk (@boundary)
- Chunking with default chunk size of 512 tokens (@boundary)
- Chunking with default overlap of 64 tokens (@boundary)
- Custom chunk size overrides the default (@edge-case)
- Custom overlap overrides the default (@edge-case)

## Acceptance Criteria

- [ ] `chunk_text()` returns `list[Chunk]` with correct text segments
- [ ] Default chunk_size=512 and overlap=64 match API contract
- [ ] Text shorter than chunk_size produces exactly 1 chunk
- [ ] Empty text returns empty list (no chunks)
- [ ] `source_metadata` is copied into each chunk's metadata dict
- [ ] Each chunk's metadata includes sequential `chunk_index` (0-based)
- [ ] Custom chunk_size and overlap parameters are respected
- [ ] All modified files pass project-configured lint/format checks with zero errors

## Implementation Notes

- Import: `from langchain_text_splitters import RecursiveCharacterTextSplitter`
- The splitter operates on character count, not true token count — this is acceptable per ASSUM-001/002 which define "tokens" loosely as the configured value
- Pure function with no side effects — highly testable
- Add `langchain-text-splitters` to pyproject.toml dependencies