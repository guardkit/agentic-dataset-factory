---
id: TASK-ING-003
title: "Implement Docling processor for standard and VLM modes"
task_type: feature
parent_review: TASK-REV-F479
feature_id: FEAT-ING
wave: 2
implementation_mode: task-work
complexity: 5
dependencies:
  - TASK-ING-001
status: pending
priority: high
tags: [ingestion, docling, pdf-processing]
created: 2026-03-19T00:00:00Z
updated: 2026-03-19T00:00:00Z
test_results:
  status: pending
  coverage: null
  last_run: null
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
