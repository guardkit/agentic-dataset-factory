"""Tests for ingestion data models: Chunk, IngestResult, SourceDocument.

Follows the existing test patterns in domain_config/tests/test_models.py:
- Organised by test class per model
- AAA pattern (Arrange, Act, Assert)
- pytest.raises(ValidationError) for negative cases
- pytest.mark.parametrize for boundary / negative sweeps
- Naming: test_<method_name>_<scenario>_<expected_result>
"""

from __future__ import annotations

import dataclasses

import pytest
from pydantic import ValidationError

from ingestion.models import Chunk, IngestResult, SourceDocument


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def valid_chunk_kwargs():
    return {
        "text": "This is a chunk of text.",
        "metadata": {
            "source_file": "mr-bruff-language.pdf",
            "page_number": 42,
            "chunk_index": 3,
            "docling_mode": "standard",
            "domain": "gcse-english-tutor",
        },
    }


@pytest.fixture
def valid_ingest_result_kwargs():
    return {
        "domain": "gcse-english-tutor",
        "collection_name": "gcse-english-tutor",
        "documents_processed": 5,
        "chunks_created": 120,
        "elapsed_seconds": 12.5,
    }


@pytest.fixture
def valid_source_document_kwargs():
    return {
        "file_pattern": "mr-bruff-*.pdf",
        "mode": "standard",
        "notes": "Digital PDFs",
    }


# ---------------------------------------------------------------------------
# Chunk tests
# ---------------------------------------------------------------------------


class TestChunk:
    def test_construction_with_all_fields(self, valid_chunk_kwargs):
        chunk = Chunk(**valid_chunk_kwargs)
        assert chunk.text == "This is a chunk of text."
        assert chunk.metadata["source_file"] == "mr-bruff-language.pdf"
        assert chunk.metadata["page_number"] == 42
        assert chunk.metadata["chunk_index"] == 3
        assert chunk.metadata["docling_mode"] == "standard"
        assert chunk.metadata["domain"] == "gcse-english-tutor"

    def test_is_dataclass(self):
        assert dataclasses.is_dataclass(Chunk)

    def test_has_text_field(self):
        fields = {f.name for f in dataclasses.fields(Chunk)}
        assert "text" in fields

    def test_has_metadata_field(self):
        fields = {f.name for f in dataclasses.fields(Chunk)}
        assert "metadata" in fields

    def test_metadata_defaults_to_empty_dict(self):
        chunk = Chunk(text="hello")
        assert chunk.metadata == {}

    def test_metadata_default_is_distinct_per_instance(self):
        """Each Chunk should get its own dict, not share one."""
        a = Chunk(text="a")
        b = Chunk(text="b")
        a.metadata["key"] = "value"
        assert "key" not in b.metadata

    def test_empty_text_allowed(self):
        """Chunk is a simple dataclass — no validation on text."""
        chunk = Chunk(text="")
        assert chunk.text == ""

    def test_text_is_str(self, valid_chunk_kwargs):
        chunk = Chunk(**valid_chunk_kwargs)
        assert isinstance(chunk.text, str)

    def test_metadata_is_dict(self, valid_chunk_kwargs):
        chunk = Chunk(**valid_chunk_kwargs)
        assert isinstance(chunk.metadata, dict)

    def test_field_count(self):
        """Chunk should have exactly 2 fields: text and metadata."""
        assert len(dataclasses.fields(Chunk)) == 2


# ---------------------------------------------------------------------------
# IngestResult tests
# ---------------------------------------------------------------------------


class TestIngestResult:
    def test_construction_with_all_fields(self, valid_ingest_result_kwargs):
        result = IngestResult(**valid_ingest_result_kwargs)
        assert result.domain == "gcse-english-tutor"
        assert result.collection_name == "gcse-english-tutor"
        assert result.documents_processed == 5
        assert result.chunks_created == 120
        assert result.elapsed_seconds == 12.5

    def test_is_dataclass(self):
        assert dataclasses.is_dataclass(IngestResult)

    def test_has_domain_field(self):
        fields = {f.name for f in dataclasses.fields(IngestResult)}
        assert "domain" in fields

    def test_has_collection_name_field(self):
        fields = {f.name for f in dataclasses.fields(IngestResult)}
        assert "collection_name" in fields

    def test_has_documents_processed_field(self):
        fields = {f.name for f in dataclasses.fields(IngestResult)}
        assert "documents_processed" in fields

    def test_has_chunks_created_field(self):
        fields = {f.name for f in dataclasses.fields(IngestResult)}
        assert "chunks_created" in fields

    def test_has_elapsed_seconds_field(self):
        fields = {f.name for f in dataclasses.fields(IngestResult)}
        assert "elapsed_seconds" in fields

    def test_field_count_matches_api_contract(self):
        """IngestResult has exactly 5 fields per API contract."""
        assert len(dataclasses.fields(IngestResult)) == 5

    @pytest.mark.parametrize(
        "field_name,expected_type",
        [
            ("domain", str),
            ("collection_name", str),
            ("documents_processed", int),
            ("chunks_created", int),
            ("elapsed_seconds", float),
        ],
    )
    def test_field_types_match_contract(
        self, valid_ingest_result_kwargs, field_name, expected_type
    ):
        result = IngestResult(**valid_ingest_result_kwargs)
        assert isinstance(getattr(result, field_name), expected_type)

    def test_zero_documents_processed(self):
        result = IngestResult(
            domain="d",
            collection_name="d",
            documents_processed=0,
            chunks_created=0,
            elapsed_seconds=0.0,
        )
        assert result.documents_processed == 0
        assert result.chunks_created == 0

    def test_elapsed_seconds_float_precision(self):
        result = IngestResult(
            domain="d",
            collection_name="d",
            documents_processed=1,
            chunks_created=10,
            elapsed_seconds=0.123456789,
        )
        assert result.elapsed_seconds == pytest.approx(0.123456789)


# ---------------------------------------------------------------------------
# SourceDocument (stub) tests
# ---------------------------------------------------------------------------


class TestSourceDocument:
    def test_valid_standard_mode(self, valid_source_document_kwargs):
        doc = SourceDocument(**valid_source_document_kwargs)
        assert doc.file_pattern == "mr-bruff-*.pdf"
        assert doc.mode == "standard"
        assert doc.notes == "Digital PDFs"

    def test_valid_vlm_mode(self):
        doc = SourceDocument(
            file_pattern="scanned-*.pdf",
            mode="vlm",
            notes="Scanned pages",
        )
        assert doc.mode == "vlm"

    def test_notes_default_empty(self):
        doc = SourceDocument(file_pattern="file.pdf", mode="standard")
        assert doc.notes == ""

    def test_has_file_pattern_field(self):
        assert "file_pattern" in SourceDocument.model_fields

    def test_has_mode_field(self):
        assert "mode" in SourceDocument.model_fields

    def test_has_notes_field(self):
        assert "notes" in SourceDocument.model_fields

    def test_field_count(self):
        """SourceDocument stub has exactly 3 fields."""
        assert len(SourceDocument.model_fields) == 3

    @pytest.mark.parametrize("mode", ["standard", "vlm"])
    def test_valid_modes_accepted(self, mode):
        doc = SourceDocument(file_pattern="x.pdf", mode=mode)
        assert doc.mode == mode

    @pytest.mark.parametrize(
        "bad_mode",
        ["ocr", "OCR", "Standard", "VLM", "auto", "", "pdf"],
    )
    def test_invalid_mode_rejected(self, bad_mode):
        with pytest.raises(ValidationError):
            SourceDocument(file_pattern="x.pdf", mode=bad_mode)

    def test_empty_file_pattern_rejected(self):
        with pytest.raises(ValidationError):
            SourceDocument(file_pattern="", mode="standard")

    def test_is_pydantic_base_model(self):
        from pydantic import BaseModel

        assert issubclass(SourceDocument, BaseModel)


# ---------------------------------------------------------------------------
# Import contract tests (AC-001, AC-007)
# ---------------------------------------------------------------------------


class TestImportContracts:
    def test_chunk_importable_from_ingestion_models(self):
        from ingestion.models import Chunk

        assert Chunk is not None

    def test_ingest_result_importable_from_ingestion_models(self):
        from ingestion.models import IngestResult

        assert IngestResult is not None

    def test_source_document_importable_from_ingestion_models(self):
        from ingestion.models import SourceDocument

        assert SourceDocument is not None

    def test_all_models_importable_from_package(self):
        """All public names should be importable from ingestion."""
        from ingestion import Chunk, IngestResult, SourceDocument

        assert all(
            cls is not None
            for cls in [Chunk, IngestResult, SourceDocument]
        )

    def test_all_models_in_package_all(self):
        import ingestion

        for name in ["Chunk", "IngestResult", "SourceDocument"]:
            assert name in ingestion.__all__
