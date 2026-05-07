"""Docling PDF processor for standard and VLM extraction modes.

Wraps Docling's DocumentConverter to extract page-level text from PDF
documents.  Supports two modes:

- **standard**: text-based PDFs via Docling's default pipeline.
- **vlm**: scanned / image-heavy PDFs via Docling's VLM pipeline options.

Docling is lazy-imported (not at module level) because it is a heavy
dependency that should only be loaded when actually needed.

Raises:
    DoclingError: When Docling fails to process a document or when the
        input file is zero bytes.
    FileNotFoundError: When the supplied *file_path* does not exist.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

from ingestion.errors import DoclingError

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------


@dataclass
class ExtractedPage:
    """A single page of extracted text.

    Attributes:
        page_number: 1-based page index within the source document.
        text: Extracted text content for this page.
    """

    page_number: int
    text: str


@dataclass
class ExtractedDocument:
    """Result of processing a single PDF through Docling.

    Attributes:
        source_file: Absolute path (as string) of the source PDF.
        pages: Ordered list of :class:`ExtractedPage` instances.
        mode: The extraction mode used (``"standard"`` or ``"vlm"``).
    """

    source_file: str
    pages: list[ExtractedPage]
    mode: str  # "standard" or "vlm"


# ---------------------------------------------------------------------------
# Lazy import helpers
# ---------------------------------------------------------------------------


def _get_document_converter():
    """Lazy-import Docling's DocumentConverter.

    Returns:
        The ``DocumentConverter`` class from ``docling.document_converter``.

    Raises:
        DoclingError: If the ``docling`` package is not installed.
    """
    try:
        from docling.document_converter import DocumentConverter
    except ImportError as exc:
        raise DoclingError(
            "Docling is not installed. Install it with: pip install docling"
        ) from exc
    return DocumentConverter


def _build_converter(mode: str):
    """Build a Docling DocumentConverter for the given mode.

    Args:
        mode: ``"standard"`` or ``"vlm"``.

    Returns:
        An instantiated ``DocumentConverter`` configured for *mode*.
    """
    converter_cls = _get_document_converter()

    if mode == "vlm":
        try:
            from docling.datamodel.base_models import InputFormat
            from docling.datamodel.pipeline_options import VlmPipelineOptions
            from docling.document_converter import PdfFormatOption
            from docling.pipeline.vlm_pipeline import VlmPipeline

            return converter_cls(
                format_options={
                    InputFormat.PDF: PdfFormatOption(
                        pipeline_cls=VlmPipeline,
                        pipeline_options=VlmPipelineOptions(),
                    )
                }
            )
        except (ImportError, TypeError):
            # Fall back to default converter if VLM-specific options
            # are unavailable in this Docling version.
            return converter_cls()

    return converter_cls()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def process_document(
    file_path: Path,
    mode: str = "standard",
) -> ExtractedDocument:
    """Extract text from a PDF using Docling.

    Args:
        file_path: Path to the PDF file.
        mode: ``"standard"`` for text PDFs, ``"vlm"`` for scanned/image PDFs.

    Returns:
        :class:`ExtractedDocument` with page-level text extraction.

    Raises:
        FileNotFoundError: If *file_path* does not exist.
        DoclingError: If *file_path* is zero bytes or if Docling fails to
            process the document.
    """
    path = Path(file_path)

    # --- Pre-flight checks --------------------------------------------------
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")

    if path.stat().st_size == 0:
        raise DoclingError(f"Cannot process zero-byte file: {path} (0 bytes)")

    # --- Build converter and extract ----------------------------------------
    converter = _build_converter(mode)

    try:
        result = converter.convert(str(path))
    except DoclingError:
        raise
    except Exception as exc:
        raise DoclingError(f"Docling failed to process '{path}': {exc}") from exc

    # --- Build page list from result ----------------------------------------
    pages: list[ExtractedPage] = []

    doc = result.document

    # Aggregate text by page from document content items.
    # Each item has provenance info (prov) containing page_no.
    if hasattr(doc, "iterate_items"):
        page_texts: dict[int, list[str]] = {}
        for item, _level in doc.iterate_items():
            text = getattr(item, "text", None)
            if not text:
                continue
            prov_list = getattr(item, "prov", None)
            if prov_list:
                page_no = prov_list[0].page_no
            else:
                page_no = 1
            page_texts.setdefault(page_no, []).append(text)

        for page_no in sorted(page_texts):
            combined = "\n".join(page_texts[page_no])
            if combined.strip():
                pages.append(ExtractedPage(page_number=page_no, text=combined))

    return ExtractedDocument(
        source_file=str(path),
        pages=pages,
        mode=mode,
    )


__all__ = [
    "ExtractedDocument",
    "ExtractedPage",
    "process_document",
]
