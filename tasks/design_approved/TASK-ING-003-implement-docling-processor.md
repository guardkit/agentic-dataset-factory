---
complexity: 5
created: 2026-03-19 00:00:00+00:00
dependencies:
- TASK-ING-001
feature_id: FEAT-ING
id: TASK-ING-003
implementation_mode: task-work
parent_review: TASK-REV-F479
priority: high
status: design_approved
tags:
- ingestion
- docling
- pdf-processing
task_type: feature
test_results:
  coverage: null
  last_run: null
  status: pending
title: Implement Docling processor for standard and VLM modes
updated: 2026-03-19 00:00:00+00:00
wave: 2
---

# Task: Implement Docling processor for standard and VLM modes

## Description

Implement `ingestion/docling_processor.py` that wraps Docling PDF extraction for both standard and VLM modes. The processor takes a file path and mode, returns extracted text with page-level metadata. Uses lazy imports for Docling since it's a heavy dependency.

## Function Contract

```python
@dataclass
class ExtractedPage:
    page_number: int
    text: str

@dataclass
class ExtractedDocument:
    source_file: str
    pages: list[ExtractedPage]
    mode: str  # "standard" or "vlm"

def process_document(
    file_path: Path,
    mode: str = "standard",
) -> ExtractedDocument:
    """Extract text from a PDF using Docling.

    Args:
        file_path: Path to the PDF file
        mode: "standard" for text PDFs, "vlm" for scanned/image PDFs

    Returns:
        ExtractedDocument with page-level text extraction.

    Raises:
        DoclingError: If Docling fails to process the document
        FileNotFoundError: If file_path does not exist
    """
```

## BDD Scenarios Covered

- Ingesting a standard PDF document into ChromaDB (@key-example @smoke)
- Ingesting a scanned PDF document via VLM mode (@key-example @smoke)
- Domain with both standard and VLM source documents (@edge-case)
- Docling fails to process one document in a batch (@negative)
- Docling extracts empty text from an image-only PDF in standard mode (@edge-case)
- PDF with embedded scripts is processed safely (@edge-case)
- Source document is a zero-byte PDF file (@edge-case @negative)

## Acceptance Criteria

- [ ] `process_document()` extracts text from standard PDFs
- [ ] `process_document()` extracts text from scanned PDFs using VLM mode
- [ ] Returns `ExtractedDocument` with page-level text and page numbers
- [ ] Raises `DoclingError` on processing failure (not generic Exception)
- [ ] Raises `FileNotFoundError` for non-existent files
- [ ] Zero-byte files raise `DoclingError` with descriptive message
- [ ] Empty extraction result (image-only PDF in standard mode) returns ExtractedDocument with empty pages list
- [ ] Docling is lazy-imported (not at module level)
- [ ] All modified files pass project-configured lint/format checks with zero errors

## Implementation Notes

- Lazy import pattern: `def _get_docling(): from docling.document_converter import DocumentConverter; ...`
- Docling standard mode: `DocumentConverter().convert(file_path)`
- Docling VLM mode: requires `PipelineOptions` with VLM configuration
- Add `docling` to pyproject.toml dependencies
- Catch Docling exceptions and wrap in `DoclingError` with source file context