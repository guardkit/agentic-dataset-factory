"""Tests for docling_processor module.

Covers all acceptance criteria for TASK-ING-003:
- AC-001: process_document() extracts text from standard PDFs
- AC-002: process_document() extracts text from scanned PDFs using VLM mode
- AC-003: Returns ExtractedDocument with page-level text and page numbers
- AC-004: Raises DoclingError on processing failure
- AC-005: Raises FileNotFoundError for non-existent files
- AC-006: Zero-byte files raise DoclingError with descriptive message
- AC-007: Empty extraction (image-only PDF in standard mode) returns empty pages
- AC-008: Docling is lazy-imported (not at module level)
- AC-009: All modified files pass lint/format checks

Testing strategy: Mock Docling entirely since it's a heavy external dependency.
Tests verify the wiring, error handling, and lazy-import pattern.
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from ingestion.errors import DoclingError


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def tmp_pdf(tmp_path: Path) -> Path:
    """Create a minimal non-empty file to act as a PDF for testing."""
    pdf = tmp_path / "sample.pdf"
    pdf.write_bytes(b"%PDF-1.4 fake content for testing")
    return pdf


@pytest.fixture()
def zero_byte_pdf(tmp_path: Path) -> Path:
    """Create a zero-byte file."""
    pdf = tmp_path / "empty.pdf"
    pdf.write_bytes(b"")
    return pdf


@pytest.fixture()
def mock_docling_standard():
    """Mock Docling DocumentConverter for standard mode.

    Returns a converter whose convert() produces a result with
    two pages of text.
    """
    mock_page_1 = MagicMock()
    mock_page_1.text = "Page one text content."

    mock_page_2 = MagicMock()
    mock_page_2.text = "Page two text content."

    mock_result = MagicMock()
    mock_result.document = MagicMock()
    mock_result.document.pages = {1: mock_page_1, 2: mock_page_2}
    mock_result.document.export_to_text.return_value = (
        "Page one text content.\nPage two text content."
    )

    mock_converter_instance = MagicMock()
    mock_converter_instance.convert.return_value = mock_result

    mock_converter_cls = MagicMock(return_value=mock_converter_instance)

    return mock_converter_cls, mock_result


@pytest.fixture()
def mock_docling_vlm():
    """Mock Docling DocumentConverter for VLM mode.

    Returns a converter whose convert() produces a result with
    one page of VLM-extracted text.
    """
    mock_page_1 = MagicMock()
    mock_page_1.text = "VLM extracted text from scanned page."

    mock_result = MagicMock()
    mock_result.document = MagicMock()
    mock_result.document.pages = {1: mock_page_1}
    mock_result.document.export_to_text.return_value = "VLM extracted text from scanned page."

    mock_converter_instance = MagicMock()
    mock_converter_instance.convert.return_value = mock_result

    mock_converter_cls = MagicMock(return_value=mock_converter_instance)

    return mock_converter_cls, mock_result


@pytest.fixture()
def mock_docling_empty():
    """Mock Docling for empty extraction (image-only PDF in standard mode)."""
    mock_result = MagicMock()
    mock_result.document = MagicMock()
    mock_result.document.pages = {}
    mock_result.document.export_to_text.return_value = ""

    mock_converter_instance = MagicMock()
    mock_converter_instance.convert.return_value = mock_result

    mock_converter_cls = MagicMock(return_value=mock_converter_instance)

    return mock_converter_cls, mock_result


# ---------------------------------------------------------------------------
# AC-001: process_document() extracts text from standard PDFs
# ---------------------------------------------------------------------------


class TestStandardModeExtraction:
    """AC-001: process_document() extracts text from standard PDFs."""

    def test_process_document_standard_mode_extracts_text(
        self, tmp_pdf: Path, mock_docling_standard
    ):
        """Standard mode extracts text from text-based PDFs."""
        mock_converter_cls, mock_result = mock_docling_standard

        with patch.dict(
            "sys.modules",
            {
                "docling": MagicMock(),
                "docling.document_converter": MagicMock(DocumentConverter=mock_converter_cls),
            },
        ):
            from ingestion.docling_processor import process_document

            result = process_document(tmp_pdf, mode="standard")

        assert result.mode == "standard"
        assert len(result.pages) == 2
        assert result.pages[0].text == "Page one text content."
        assert result.pages[1].text == "Page two text content."

    def test_process_document_default_mode_is_standard(self, tmp_pdf: Path, mock_docling_standard):
        """Default mode should be 'standard' when not specified."""
        mock_converter_cls, _ = mock_docling_standard

        with patch.dict(
            "sys.modules",
            {
                "docling": MagicMock(),
                "docling.document_converter": MagicMock(DocumentConverter=mock_converter_cls),
            },
        ):
            from ingestion.docling_processor import process_document

            result = process_document(tmp_pdf)

        assert result.mode == "standard"


# ---------------------------------------------------------------------------
# AC-002: process_document() extracts text from scanned PDFs using VLM mode
# ---------------------------------------------------------------------------


class TestVLMModeExtraction:
    """AC-002: process_document() extracts text from scanned PDFs using VLM mode."""

    def test_process_document_vlm_mode_extracts_text(self, tmp_pdf: Path, mock_docling_vlm):
        """VLM mode extracts text from scanned/image PDFs."""
        mock_converter_cls, _ = mock_docling_vlm

        with patch.dict(
            "sys.modules",
            {
                "docling": MagicMock(),
                "docling.document_converter": MagicMock(DocumentConverter=mock_converter_cls),
                "docling.pipeline.standard_pdf_pipeline": MagicMock(),
            },
        ):
            from ingestion.docling_processor import process_document

            result = process_document(tmp_pdf, mode="vlm")

        assert result.mode == "vlm"
        assert len(result.pages) >= 1
        assert "VLM" in result.pages[0].text or len(result.pages[0].text) > 0


# ---------------------------------------------------------------------------
# AC-003: Returns ExtractedDocument with page-level text and page numbers
# ---------------------------------------------------------------------------


class TestExtractedDocumentStructure:
    """AC-003: Returns ExtractedDocument with page-level text and page numbers."""

    def test_returns_extracted_document_type(self, tmp_pdf: Path, mock_docling_standard):
        """Return type must be ExtractedDocument."""
        mock_converter_cls, _ = mock_docling_standard

        with patch.dict(
            "sys.modules",
            {
                "docling": MagicMock(),
                "docling.document_converter": MagicMock(DocumentConverter=mock_converter_cls),
            },
        ):
            from ingestion.docling_processor import (
                ExtractedDocument,
                process_document,
            )

            result = process_document(tmp_pdf, mode="standard")

        assert isinstance(result, ExtractedDocument)

    def test_extracted_document_has_source_file(self, tmp_pdf: Path, mock_docling_standard):
        """ExtractedDocument.source_file matches the input filename."""
        mock_converter_cls, _ = mock_docling_standard

        with patch.dict(
            "sys.modules",
            {
                "docling": MagicMock(),
                "docling.document_converter": MagicMock(DocumentConverter=mock_converter_cls),
            },
        ):
            from ingestion.docling_processor import process_document

            result = process_document(tmp_pdf, mode="standard")

        assert result.source_file == str(tmp_pdf)

    def test_pages_have_sequential_page_numbers(self, tmp_pdf: Path, mock_docling_standard):
        """Each ExtractedPage has the correct page_number."""
        mock_converter_cls, _ = mock_docling_standard

        with patch.dict(
            "sys.modules",
            {
                "docling": MagicMock(),
                "docling.document_converter": MagicMock(DocumentConverter=mock_converter_cls),
            },
        ):
            from ingestion.docling_processor import process_document

            result = process_document(tmp_pdf, mode="standard")

        assert result.pages[0].page_number == 1
        assert result.pages[1].page_number == 2

    def test_extracted_page_is_dataclass(self, tmp_pdf: Path, mock_docling_standard):
        """ExtractedPage must be a dataclass."""
        mock_converter_cls, _ = mock_docling_standard

        with patch.dict(
            "sys.modules",
            {
                "docling": MagicMock(),
                "docling.document_converter": MagicMock(DocumentConverter=mock_converter_cls),
            },
        ):
            from ingestion.docling_processor import ExtractedPage, process_document

            result = process_document(tmp_pdf, mode="standard")

        import dataclasses

        assert dataclasses.is_dataclass(result.pages[0])
        assert isinstance(result.pages[0], ExtractedPage)


# ---------------------------------------------------------------------------
# AC-004: Raises DoclingError on processing failure
# ---------------------------------------------------------------------------


class TestDoclingErrorOnFailure:
    """AC-004: Raises DoclingError on processing failure (not generic Exception)."""

    def test_raises_docling_error_on_conversion_failure(self, tmp_pdf: Path):
        """DoclingError raised when Docling conversion fails."""
        mock_converter_instance = MagicMock()
        mock_converter_instance.convert.side_effect = RuntimeError("Docling crash")
        mock_converter_cls = MagicMock(return_value=mock_converter_instance)

        with patch.dict(
            "sys.modules",
            {
                "docling": MagicMock(),
                "docling.document_converter": MagicMock(DocumentConverter=mock_converter_cls),
            },
        ):
            from ingestion.docling_processor import process_document

            with pytest.raises(DoclingError) as exc_info:
                process_document(tmp_pdf, mode="standard")

        assert str(tmp_pdf) in str(exc_info.value) or "sample.pdf" in str(exc_info.value)

    def test_docling_error_wraps_original_exception(self, tmp_pdf: Path):
        """DoclingError should include context about the source file."""
        mock_converter_instance = MagicMock()
        mock_converter_instance.convert.side_effect = ValueError("bad format")
        mock_converter_cls = MagicMock(return_value=mock_converter_instance)

        with patch.dict(
            "sys.modules",
            {
                "docling": MagicMock(),
                "docling.document_converter": MagicMock(DocumentConverter=mock_converter_cls),
            },
        ):
            from ingestion.docling_processor import process_document

            with pytest.raises(DoclingError):
                process_document(tmp_pdf, mode="standard")

    def test_docling_error_is_ingestion_error_subclass(self, tmp_pdf: Path):
        """DoclingError should be catchable as IngestionError."""
        from ingestion.errors import IngestionError

        mock_converter_instance = MagicMock()
        mock_converter_instance.convert.side_effect = RuntimeError("fail")
        mock_converter_cls = MagicMock(return_value=mock_converter_instance)

        with patch.dict(
            "sys.modules",
            {
                "docling": MagicMock(),
                "docling.document_converter": MagicMock(DocumentConverter=mock_converter_cls),
            },
        ):
            from ingestion.docling_processor import process_document

            with pytest.raises(IngestionError):
                process_document(tmp_pdf, mode="standard")


# ---------------------------------------------------------------------------
# AC-005: Raises FileNotFoundError for non-existent files
# ---------------------------------------------------------------------------


class TestFileNotFoundError:
    """AC-005: Raises FileNotFoundError for non-existent files."""

    def test_raises_file_not_found_for_missing_file(self, tmp_path: Path):
        """FileNotFoundError raised for non-existent file path."""
        missing = tmp_path / "does_not_exist.pdf"

        from ingestion.docling_processor import process_document

        with pytest.raises(FileNotFoundError):
            process_document(missing, mode="standard")

    def test_file_not_found_error_includes_path(self, tmp_path: Path):
        """FileNotFoundError message should include the file path."""
        missing = tmp_path / "missing.pdf"

        from ingestion.docling_processor import process_document

        with pytest.raises(FileNotFoundError, match="missing.pdf"):
            process_document(missing)


# ---------------------------------------------------------------------------
# AC-006: Zero-byte files raise DoclingError with descriptive message
# ---------------------------------------------------------------------------


class TestZeroByteFile:
    """AC-006: Zero-byte files raise DoclingError with descriptive message."""

    def test_zero_byte_raises_docling_error(self, zero_byte_pdf: Path):
        """Zero-byte file should raise DoclingError, not pass silently."""
        from ingestion.docling_processor import process_document

        with pytest.raises(DoclingError):
            process_document(zero_byte_pdf, mode="standard")

    def test_zero_byte_error_message_is_descriptive(self, zero_byte_pdf: Path):
        """Error message should mention zero-byte or empty."""
        from ingestion.docling_processor import process_document

        with pytest.raises(DoclingError, match=r"(?i)(zero.byte|empty|0 bytes)"):
            process_document(zero_byte_pdf, mode="standard")


# ---------------------------------------------------------------------------
# AC-007: Empty extraction returns ExtractedDocument with empty pages list
# ---------------------------------------------------------------------------


class TestEmptyExtraction:
    """AC-007: Image-only PDF in standard mode returns ExtractedDocument with empty pages."""

    def test_empty_extraction_returns_empty_pages(self, tmp_pdf: Path, mock_docling_empty):
        """Image-only PDF in standard mode returns empty pages list."""
        mock_converter_cls, _ = mock_docling_empty

        with patch.dict(
            "sys.modules",
            {
                "docling": MagicMock(),
                "docling.document_converter": MagicMock(DocumentConverter=mock_converter_cls),
            },
        ):
            from ingestion.docling_processor import (
                ExtractedDocument,
                process_document,
            )

            result = process_document(tmp_pdf, mode="standard")

        assert isinstance(result, ExtractedDocument)
        assert result.pages == []

    def test_empty_extraction_preserves_metadata(self, tmp_pdf: Path, mock_docling_empty):
        """Even with empty pages, source_file and mode are set correctly."""
        mock_converter_cls, _ = mock_docling_empty

        with patch.dict(
            "sys.modules",
            {
                "docling": MagicMock(),
                "docling.document_converter": MagicMock(DocumentConverter=mock_converter_cls),
            },
        ):
            from ingestion.docling_processor import process_document

            result = process_document(tmp_pdf, mode="standard")

        assert result.source_file == str(tmp_pdf)
        assert result.mode == "standard"


# ---------------------------------------------------------------------------
# AC-008: Docling is lazy-imported (not at module level)
# ---------------------------------------------------------------------------


class TestLazyImport:
    """AC-008: Docling is lazy-imported (not at module level)."""

    def test_docling_not_imported_at_module_level(self):
        """Importing docling_processor should NOT import docling itself."""
        # Remove docling_processor from cache to force fresh import
        modules_to_remove = [
            key for key in sys.modules if key.startswith("ingestion.docling_processor")
        ]
        for key in modules_to_remove:
            del sys.modules[key]

        # Ensure docling is NOT in sys.modules
        docling_modules = [key for key in sys.modules if key.startswith("docling")]
        for key in docling_modules:
            del sys.modules[key]

        # Import the module
        import ingestion.docling_processor  # noqa: F401

        # Verify docling was NOT imported as a side effect
        docling_imported = any(key.startswith("docling") for key in sys.modules)
        assert not docling_imported, (
            "docling should not be imported at module level; "
            "found in sys.modules after importing docling_processor"
        )

    def test_module_source_has_no_toplevel_docling_import(self):
        """Verify the source file has no top-level 'import docling' or 'from docling'."""
        import ingestion.docling_processor as mod

        source_path = Path(mod.__file__)
        source = source_path.read_text()

        # Check that no top-level import of docling exists
        # (imports inside functions are fine)
        lines = source.split("\n")
        for i, line in enumerate(lines):
            stripped = line.strip()
            # Skip blank, comment, or indented lines (inside functions)
            if not stripped or stripped.startswith("#"):
                continue
            # Only check top-level lines (no leading whitespace)
            if line and not line[0].isspace():
                assert not stripped.startswith("import docling"), (
                    f"Top-level 'import docling' found at line {i + 1}"
                )
                assert not stripped.startswith("from docling"), (
                    f"Top-level 'from docling' found at line {i + 1}"
                )
