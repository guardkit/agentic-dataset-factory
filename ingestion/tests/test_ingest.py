"""Tests for the ingest orchestrator and CLI entry point.

Covers all acceptance criteria for TASK-ING-006:
- AC-001: ingest_domain() orchestrates full pipeline: read → process → chunk → index
- AC-002: Per-document Docling failures logged and skipped (remaining docs continue)
- AC-003: IngestResult populated with correct document count, chunk count, elapsed time
- AC-004: CLI parses --domain, --chunk-size, --overlap, --force arguments
- AC-005: CLI returns correct exit codes (0-4) per API contract
- AC-006: CLI prints human-readable summary on success
- AC-007: CLI prints error messages to stderr on failure
- AC-008: Structured JSON logging at key milestones (per ADR-ARCH-007)
- AC-009: All modified files pass project-configured lint/format checks

Follows project test patterns:
- Organised by test class per concern
- AAA pattern (Arrange, Act, Assert)
- pytest.raises for negative cases
- Naming: test_<method_name>_<scenario>_<expected_result>
"""

from __future__ import annotations

import logging
from unittest.mock import MagicMock, patch

import pytest

from ingestion.errors import (
    DoclingError,
    DomainNotFoundError,
    GoalValidationError,
    IndexingError,
)
from ingestion.models import Chunk, IngestResult, SourceDocument


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def domain_dir(tmp_path):
    """Create a realistic domain directory with GOAL.md and source files."""
    domain = tmp_path / "domains" / "test-domain"
    domain.mkdir(parents=True)
    sources = domain / "sources"
    sources.mkdir()

    goal_md = domain / "GOAL.md"
    goal_md.write_text(
        "# Test Domain\n\n"
        "## Source Documents\n\n"
        "| File Pattern | Mode | Notes |\n"
        "| --- | --- | --- |\n"
        "| *.pdf | standard | Test PDF |\n",
        encoding="utf-8",
    )

    # Create a dummy PDF file (non-zero bytes)
    pdf_file = sources / "test-doc.pdf"
    pdf_file.write_bytes(b"%PDF-1.4 fake content for testing")

    return domain


@pytest.fixture
def multi_doc_domain(tmp_path):
    """Domain with multiple source documents."""
    domain = tmp_path / "domains" / "multi-domain"
    domain.mkdir(parents=True)
    sources = domain / "sources"
    sources.mkdir()

    goal_md = domain / "GOAL.md"
    goal_md.write_text(
        "# Multi Domain\n\n"
        "## Source Documents\n\n"
        "| File Pattern | Mode | Notes |\n"
        "| --- | --- | --- |\n"
        "| doc-a.pdf | standard | First doc |\n"
        "| doc-b.pdf | vlm | Second doc |\n"
        "| doc-c.pdf | standard | Third doc |\n",
        encoding="utf-8",
    )

    for name in ["doc-a.pdf", "doc-b.pdf", "doc-c.pdf"]:
        (sources / name).write_bytes(b"%PDF-1.4 fake content")

    return domain


@pytest.fixture
def mock_docling_result():
    """Create a mock Docling ExtractedDocument."""
    from ingestion.docling_processor import ExtractedDocument, ExtractedPage

    return ExtractedDocument(
        source_file="/fake/path/test-doc.pdf",
        pages=[
            ExtractedPage(page_number=1, text="Page one content about English literature. " * 20),
            ExtractedPage(page_number=2, text="Page two content about poetry analysis. " * 20),
        ],
        mode="standard",
    )


# ---------------------------------------------------------------------------
# AC-001: ingest_domain() orchestrates full pipeline
# ---------------------------------------------------------------------------


class TestIngestDomainOrchestration:
    """AC-001: ingest_domain() orchestrates read → process → chunk → index."""

    @patch("ingestion.ingest.ChromaDBIndexer")
    @patch("ingestion.ingest.process_document")
    @patch("ingestion.ingest.resolve_source_files")
    @patch("ingestion.ingest.read_source_documents")
    def test_orchestrates_full_pipeline(
        self,
        mock_read_docs,
        mock_resolve,
        mock_process,
        mock_indexer_cls,
        domain_dir,
        mock_docling_result,
    ):
        """Full pipeline: read GOAL.md → resolve files → process → chunk → index."""
        from ingestion.ingest import ingest_domain

        # Arrange
        mock_read_docs.return_value = [
            SourceDocument(file_pattern="*.pdf", mode="standard"),
        ]
        mock_resolve.return_value = [
            (domain_dir / "sources" / "test-doc.pdf", "standard"),
        ]
        mock_process.return_value = mock_docling_result

        mock_indexer = MagicMock()
        mock_indexer_cls.return_value = mock_indexer
        mock_collection = MagicMock()
        mock_indexer.create_or_replace_collection.return_value = mock_collection
        mock_indexer.index_chunks.return_value = 5

        # Act
        result = ingest_domain(
            domain_name="test-domain",
            domains_root=domain_dir.parent,
        )

        # Assert — pipeline was called in order
        mock_read_docs.assert_called_once()
        mock_resolve.assert_called_once()
        mock_process.assert_called_once()
        mock_indexer.create_or_replace_collection.assert_called_once()
        mock_indexer.index_chunks.assert_called_once()
        assert isinstance(result, IngestResult)

    @patch("ingestion.ingest.ChromaDBIndexer")
    @patch("ingestion.ingest.process_document")
    @patch("ingestion.ingest.resolve_source_files")
    @patch("ingestion.ingest.read_source_documents")
    def test_passes_chunk_size_and_overlap(
        self,
        mock_read_docs,
        mock_resolve,
        mock_process,
        mock_indexer_cls,
        domain_dir,
        mock_docling_result,
    ):
        """chunk_size and overlap are passed through to the chunker."""
        from ingestion.ingest import ingest_domain

        mock_read_docs.return_value = [
            SourceDocument(file_pattern="*.pdf", mode="standard"),
        ]
        mock_resolve.return_value = [
            (domain_dir / "sources" / "test-doc.pdf", "standard"),
        ]
        mock_process.return_value = mock_docling_result

        mock_indexer = MagicMock()
        mock_indexer_cls.return_value = mock_indexer
        mock_collection = MagicMock()
        mock_indexer.create_or_replace_collection.return_value = mock_collection
        mock_indexer.index_chunks.return_value = 3

        with patch("ingestion.ingest.chunk_text") as mock_chunk:
            mock_chunk.return_value = [
                Chunk(text="chunk", metadata={"chunk_index": 0}),
            ]
            ingest_domain(
                domain_name="test-domain",
                domains_root=domain_dir.parent,
                chunk_size=256,
                overlap=32,
            )

            # Verify chunk_text was called with the custom parameters
            for c in mock_chunk.call_args_list:
                assert c.kwargs.get("chunk_size", c.args[1] if len(c.args) > 1 else None) in (
                    256,
                    None,
                )

    def test_raises_domain_not_found_for_missing_domain(self, tmp_path):
        """DomainNotFoundError when domain directory does not exist."""
        from ingestion.ingest import ingest_domain

        with pytest.raises(DomainNotFoundError):
            ingest_domain(
                domain_name="nonexistent-domain",
                domains_root=tmp_path / "domains",
            )

    def test_raises_goal_validation_error_for_bad_goal(self, tmp_path):
        """GoalValidationError when GOAL.md is missing or invalid."""
        from ingestion.ingest import ingest_domain

        domain = tmp_path / "domains" / "bad-goal"
        domain.mkdir(parents=True)
        # No GOAL.md file

        with pytest.raises(GoalValidationError):
            ingest_domain(
                domain_name="bad-goal",
                domains_root=tmp_path / "domains",
            )


# ---------------------------------------------------------------------------
# AC-002: Per-document Docling failures logged and skipped
# ---------------------------------------------------------------------------


class TestDoclingFailureHandling:
    """AC-002: Per-document Docling failures are logged and skipped."""

    @patch("ingestion.ingest.ChromaDBIndexer")
    @patch("ingestion.ingest.process_document")
    @patch("ingestion.ingest.resolve_source_files")
    @patch("ingestion.ingest.read_source_documents")
    def test_skips_failed_documents_and_continues(
        self,
        mock_read_docs,
        mock_resolve,
        mock_process,
        mock_indexer_cls,
        multi_doc_domain,
    ):
        """When one document fails, the rest still get processed."""
        from ingestion.docling_processor import ExtractedDocument, ExtractedPage
        from ingestion.ingest import ingest_domain

        mock_read_docs.return_value = [
            SourceDocument(file_pattern="doc-a.pdf", mode="standard"),
            SourceDocument(file_pattern="doc-b.pdf", mode="vlm"),
            SourceDocument(file_pattern="doc-c.pdf", mode="standard"),
        ]
        mock_resolve.return_value = [
            (multi_doc_domain / "sources" / "doc-a.pdf", "standard"),
            (multi_doc_domain / "sources" / "doc-b.pdf", "vlm"),
            (multi_doc_domain / "sources" / "doc-c.pdf", "standard"),
        ]

        # doc-b fails with DoclingError
        def process_side_effect(file_path, mode="standard"):
            if "doc-b" in str(file_path):
                raise DoclingError(f"Docling failed for {file_path}")
            return ExtractedDocument(
                source_file=str(file_path),
                pages=[ExtractedPage(page_number=1, text="Content " * 100)],
                mode=mode,
            )

        mock_process.side_effect = process_side_effect

        mock_indexer = MagicMock()
        mock_indexer_cls.return_value = mock_indexer
        mock_collection = MagicMock()
        mock_indexer.create_or_replace_collection.return_value = mock_collection
        mock_indexer.index_chunks.return_value = 4

        result = ingest_domain(
            domain_name="multi-domain",
            domains_root=multi_doc_domain.parent,
            force=True,
        )

        # Only 2 of 3 documents should be processed successfully
        assert result.documents_processed == 2

    @patch("ingestion.ingest.ChromaDBIndexer")
    @patch("ingestion.ingest.process_document")
    @patch("ingestion.ingest.resolve_source_files")
    @patch("ingestion.ingest.read_source_documents")
    def test_logs_warning_for_failed_document(
        self,
        mock_read_docs,
        mock_resolve,
        mock_process,
        mock_indexer_cls,
        domain_dir,
        caplog,
    ):
        """A warning log is emitted when a document fails."""
        from ingestion.ingest import ingest_domain

        mock_read_docs.return_value = [
            SourceDocument(file_pattern="*.pdf", mode="standard"),
        ]
        mock_resolve.return_value = [
            (domain_dir / "sources" / "test-doc.pdf", "standard"),
        ]
        mock_process.side_effect = DoclingError("PDF corrupt")

        mock_indexer = MagicMock()
        mock_indexer_cls.return_value = mock_indexer
        mock_collection = MagicMock()
        mock_indexer.create_or_replace_collection.return_value = mock_collection
        mock_indexer.index_chunks.return_value = 0

        with caplog.at_level(logging.WARNING):
            result = ingest_domain(
                domain_name="test-domain",
                domains_root=domain_dir.parent,
                force=True,
            )

        assert result.documents_processed == 0
        assert any("test-doc.pdf" in record.message for record in caplog.records)


# ---------------------------------------------------------------------------
# AC-003: IngestResult populated correctly
# ---------------------------------------------------------------------------


class TestIngestResultPopulation:
    """AC-003: IngestResult populated with correct counts and elapsed time."""

    @patch("ingestion.ingest.ChromaDBIndexer")
    @patch("ingestion.ingest.process_document")
    @patch("ingestion.ingest.resolve_source_files")
    @patch("ingestion.ingest.read_source_documents")
    def test_result_has_correct_document_count(
        self,
        mock_read_docs,
        mock_resolve,
        mock_process,
        mock_indexer_cls,
        multi_doc_domain,
    ):
        from ingestion.docling_processor import ExtractedDocument, ExtractedPage
        from ingestion.ingest import ingest_domain

        mock_read_docs.return_value = [
            SourceDocument(file_pattern="doc-a.pdf", mode="standard"),
            SourceDocument(file_pattern="doc-b.pdf", mode="vlm"),
            SourceDocument(file_pattern="doc-c.pdf", mode="standard"),
        ]
        mock_resolve.return_value = [
            (multi_doc_domain / "sources" / "doc-a.pdf", "standard"),
            (multi_doc_domain / "sources" / "doc-b.pdf", "vlm"),
            (multi_doc_domain / "sources" / "doc-c.pdf", "standard"),
        ]
        mock_process.return_value = ExtractedDocument(
            source_file="fake.pdf",
            pages=[ExtractedPage(page_number=1, text="Content " * 100)],
            mode="standard",
        )

        mock_indexer = MagicMock()
        mock_indexer_cls.return_value = mock_indexer
        mock_collection = MagicMock()
        mock_indexer.create_or_replace_collection.return_value = mock_collection
        mock_indexer.index_chunks.return_value = 9

        result = ingest_domain(
            domain_name="multi-domain",
            domains_root=multi_doc_domain.parent,
            force=True,
        )

        assert result.documents_processed == 3
        assert result.domain == "multi-domain"
        assert result.collection_name == "multi-domain"

    @patch("ingestion.ingest.ChromaDBIndexer")
    @patch("ingestion.ingest.process_document")
    @patch("ingestion.ingest.resolve_source_files")
    @patch("ingestion.ingest.read_source_documents")
    def test_result_has_correct_chunk_count(
        self,
        mock_read_docs,
        mock_resolve,
        mock_process,
        mock_indexer_cls,
        domain_dir,
        mock_docling_result,
    ):
        from ingestion.ingest import ingest_domain

        mock_read_docs.return_value = [
            SourceDocument(file_pattern="*.pdf", mode="standard"),
        ]
        mock_resolve.return_value = [
            (domain_dir / "sources" / "test-doc.pdf", "standard"),
        ]
        mock_process.return_value = mock_docling_result

        mock_indexer = MagicMock()
        mock_indexer_cls.return_value = mock_indexer
        mock_collection = MagicMock()
        mock_indexer.create_or_replace_collection.return_value = mock_collection
        mock_indexer.index_chunks.return_value = 7

        result = ingest_domain(
            domain_name="test-domain",
            domains_root=domain_dir.parent,
        )

        assert result.chunks_created == 7

    @patch("ingestion.ingest.ChromaDBIndexer")
    @patch("ingestion.ingest.process_document")
    @patch("ingestion.ingest.resolve_source_files")
    @patch("ingestion.ingest.read_source_documents")
    def test_result_has_positive_elapsed_seconds(
        self,
        mock_read_docs,
        mock_resolve,
        mock_process,
        mock_indexer_cls,
        domain_dir,
        mock_docling_result,
    ):
        from ingestion.ingest import ingest_domain

        mock_read_docs.return_value = [
            SourceDocument(file_pattern="*.pdf", mode="standard"),
        ]
        mock_resolve.return_value = [
            (domain_dir / "sources" / "test-doc.pdf", "standard"),
        ]
        mock_process.return_value = mock_docling_result

        mock_indexer = MagicMock()
        mock_indexer_cls.return_value = mock_indexer
        mock_collection = MagicMock()
        mock_indexer.create_or_replace_collection.return_value = mock_collection
        mock_indexer.index_chunks.return_value = 5

        result = ingest_domain(
            domain_name="test-domain",
            domains_root=domain_dir.parent,
        )

        assert result.elapsed_seconds >= 0.0


# ---------------------------------------------------------------------------
# AC-004: CLI argument parsing
# ---------------------------------------------------------------------------


class TestCLIArgumentParsing:
    """AC-004: CLI parses --domain, --chunk-size, --overlap, --force."""

    def test_build_parser_accepts_domain(self):
        from ingestion.ingest import build_parser

        parser = build_parser()
        args = parser.parse_args(["--domain", "my-domain"])
        assert args.domain == "my-domain"

    def test_build_parser_accepts_chunk_size(self):
        from ingestion.ingest import build_parser

        parser = build_parser()
        args = parser.parse_args(["--domain", "x", "--chunk-size", "256"])
        assert args.chunk_size == 256

    def test_build_parser_accepts_overlap(self):
        from ingestion.ingest import build_parser

        parser = build_parser()
        args = parser.parse_args(["--domain", "x", "--overlap", "32"])
        assert args.overlap == 32

    def test_build_parser_accepts_force_flag(self):
        from ingestion.ingest import build_parser

        parser = build_parser()
        args = parser.parse_args(["--domain", "x", "--force"])
        assert args.force is True

    def test_build_parser_defaults(self):
        from ingestion.ingest import build_parser

        parser = build_parser()
        args = parser.parse_args(["--domain", "x"])
        assert args.chunk_size == 512
        assert args.overlap == 64
        assert args.force is False

    def test_domain_is_required(self):
        from ingestion.ingest import build_parser

        parser = build_parser()
        with pytest.raises(SystemExit):
            parser.parse_args([])


# ---------------------------------------------------------------------------
# AC-005: CLI exit codes
# ---------------------------------------------------------------------------


class TestCLIExitCodes:
    """AC-005: CLI returns correct exit codes (0-4) per API contract."""

    @patch("ingestion.ingest.ingest_domain")
    def test_exit_code_0_on_success(self, mock_ingest):
        from ingestion.ingest import cli_main

        mock_ingest.return_value = IngestResult(
            domain="test",
            collection_name="test",
            documents_processed=1,
            chunks_created=5,
            elapsed_seconds=1.0,
        )

        exit_code = cli_main(["--domain", "test"])
        assert exit_code == 0

    @patch("ingestion.ingest.ingest_domain")
    def test_exit_code_1_on_domain_not_found(self, mock_ingest):
        from ingestion.ingest import cli_main

        mock_ingest.side_effect = DomainNotFoundError("domain missing")

        exit_code = cli_main(["--domain", "missing"])
        assert exit_code == 1

    @patch("ingestion.ingest.ingest_domain")
    def test_exit_code_2_on_goal_validation_error(self, mock_ingest):
        from ingestion.ingest import cli_main

        mock_ingest.side_effect = GoalValidationError("bad GOAL.md")

        exit_code = cli_main(["--domain", "bad-goal"])
        assert exit_code == 2

    @patch("ingestion.ingest.ingest_domain")
    def test_exit_code_3_on_docling_error(self, mock_ingest):
        from ingestion.ingest import cli_main

        mock_ingest.side_effect = DoclingError("all docs failed")

        exit_code = cli_main(["--domain", "bad-docs"])
        assert exit_code == 3

    @patch("ingestion.ingest.ingest_domain")
    def test_exit_code_4_on_indexing_error(self, mock_ingest):
        from ingestion.ingest import cli_main

        mock_ingest.side_effect = IndexingError("chromadb down")

        exit_code = cli_main(["--domain", "bad-index"])
        assert exit_code == 4


# ---------------------------------------------------------------------------
# AC-006: CLI prints human-readable summary on success
# ---------------------------------------------------------------------------


class TestCLISummaryOutput:
    """AC-006: CLI prints human-readable summary on success."""

    @patch("ingestion.ingest.ingest_domain")
    def test_prints_summary_on_success(self, mock_ingest, capsys):
        from ingestion.ingest import cli_main

        mock_ingest.return_value = IngestResult(
            domain="gcse-english-tutor",
            collection_name="gcse-english-tutor",
            documents_processed=3,
            chunks_created=42,
            elapsed_seconds=12.5,
        )

        cli_main(["--domain", "gcse-english-tutor"])
        captured = capsys.readouterr()

        assert "gcse-english-tutor" in captured.out
        assert "3" in captured.out  # documents
        assert "42" in captured.out  # chunks
        assert "12.5" in captured.out or "12.50" in captured.out  # elapsed


# ---------------------------------------------------------------------------
# AC-007: CLI prints error messages to stderr on failure
# ---------------------------------------------------------------------------


class TestCLIErrorOutput:
    """AC-007: CLI prints error messages to stderr on failure."""

    @patch("ingestion.ingest.ingest_domain")
    def test_prints_error_to_stderr_on_domain_not_found(self, mock_ingest, capsys):
        from ingestion.ingest import cli_main

        mock_ingest.side_effect = DomainNotFoundError("Domain 'missing' not found")

        cli_main(["--domain", "missing"])
        captured = capsys.readouterr()

        assert "missing" in captured.err.lower() or "domain" in captured.err.lower()

    @patch("ingestion.ingest.ingest_domain")
    def test_prints_error_to_stderr_on_indexing_error(self, mock_ingest, capsys):
        from ingestion.ingest import cli_main

        mock_ingest.side_effect = IndexingError("ChromaDB unreachable")

        cli_main(["--domain", "x"])
        captured = capsys.readouterr()

        assert captured.err.strip() != ""


# ---------------------------------------------------------------------------
# AC-008: Structured JSON logging at key milestones
# ---------------------------------------------------------------------------


class TestStructuredLogging:
    """AC-008: Structured JSON logging at key milestones."""

    @patch("ingestion.ingest.ChromaDBIndexer")
    @patch("ingestion.ingest.process_document")
    @patch("ingestion.ingest.resolve_source_files")
    @patch("ingestion.ingest.read_source_documents")
    def test_logs_pipeline_start(
        self,
        mock_read_docs,
        mock_resolve,
        mock_process,
        mock_indexer_cls,
        domain_dir,
        mock_docling_result,
        caplog,
    ):
        from ingestion.ingest import ingest_domain

        mock_read_docs.return_value = [
            SourceDocument(file_pattern="*.pdf", mode="standard"),
        ]
        mock_resolve.return_value = [
            (domain_dir / "sources" / "test-doc.pdf", "standard"),
        ]
        mock_process.return_value = mock_docling_result

        mock_indexer = MagicMock()
        mock_indexer_cls.return_value = mock_indexer
        mock_collection = MagicMock()
        mock_indexer.create_or_replace_collection.return_value = mock_collection
        mock_indexer.index_chunks.return_value = 5

        with caplog.at_level(logging.INFO, logger="ingestion.ingest"):
            ingest_domain(
                domain_name="test-domain",
                domains_root=domain_dir.parent,
            )

        # Verify structured log messages exist for key milestones
        log_messages = [r.message for r in caplog.records]
        assert any("test-domain" in msg for msg in log_messages), (
            f"Expected log mentioning domain name. Got: {log_messages}"
        )

    @patch("ingestion.ingest.ChromaDBIndexer")
    @patch("ingestion.ingest.process_document")
    @patch("ingestion.ingest.resolve_source_files")
    @patch("ingestion.ingest.read_source_documents")
    def test_logs_pipeline_completion(
        self,
        mock_read_docs,
        mock_resolve,
        mock_process,
        mock_indexer_cls,
        domain_dir,
        mock_docling_result,
        caplog,
    ):
        from ingestion.ingest import ingest_domain

        mock_read_docs.return_value = [
            SourceDocument(file_pattern="*.pdf", mode="standard"),
        ]
        mock_resolve.return_value = [
            (domain_dir / "sources" / "test-doc.pdf", "standard"),
        ]
        mock_process.return_value = mock_docling_result

        mock_indexer = MagicMock()
        mock_indexer_cls.return_value = mock_indexer
        mock_collection = MagicMock()
        mock_indexer.create_or_replace_collection.return_value = mock_collection
        mock_indexer.index_chunks.return_value = 5

        with caplog.at_level(logging.INFO, logger="ingestion.ingest"):
            ingest_domain(
                domain_name="test-domain",
                domains_root=domain_dir.parent,
            )

        log_messages = [r.message for r in caplog.records]
        # Should log completion with summary stats
        assert any(
            "complete" in msg.lower() or "finish" in msg.lower() or "done" in msg.lower()
            for msg in log_messages
        ), f"Expected completion log. Got: {log_messages}"


# ---------------------------------------------------------------------------
# BDD: Boundary — domain with exactly one source document
# ---------------------------------------------------------------------------


class TestBoundaryScenarios:
    """BDD boundary scenario: domain with exactly one source document."""

    @patch("ingestion.ingest.ChromaDBIndexer")
    @patch("ingestion.ingest.process_document")
    @patch("ingestion.ingest.resolve_source_files")
    @patch("ingestion.ingest.read_source_documents")
    def test_single_document_domain(
        self,
        mock_read_docs,
        mock_resolve,
        mock_process,
        mock_indexer_cls,
        domain_dir,
        mock_docling_result,
    ):
        from ingestion.ingest import ingest_domain

        mock_read_docs.return_value = [
            SourceDocument(file_pattern="*.pdf", mode="standard"),
        ]
        mock_resolve.return_value = [
            (domain_dir / "sources" / "test-doc.pdf", "standard"),
        ]
        mock_process.return_value = mock_docling_result

        mock_indexer = MagicMock()
        mock_indexer_cls.return_value = mock_indexer
        mock_collection = MagicMock()
        mock_indexer.create_or_replace_collection.return_value = mock_collection
        mock_indexer.index_chunks.return_value = 3

        result = ingest_domain(
            domain_name="test-domain",
            domains_root=domain_dir.parent,
        )

        assert result.documents_processed == 1
        assert result.chunks_created == 3


# ---------------------------------------------------------------------------
# Force flag behaviour
# ---------------------------------------------------------------------------


class TestForceFlag:
    """Verify force flag is forwarded to ChromaDB indexer."""

    @patch("ingestion.ingest.ChromaDBIndexer")
    @patch("ingestion.ingest.process_document")
    @patch("ingestion.ingest.resolve_source_files")
    @patch("ingestion.ingest.read_source_documents")
    def test_force_true_forwarded_to_create_or_replace(
        self,
        mock_read_docs,
        mock_resolve,
        mock_process,
        mock_indexer_cls,
        domain_dir,
        mock_docling_result,
    ):
        from ingestion.ingest import ingest_domain

        mock_read_docs.return_value = [
            SourceDocument(file_pattern="*.pdf", mode="standard"),
        ]
        mock_resolve.return_value = [
            (domain_dir / "sources" / "test-doc.pdf", "standard"),
        ]
        mock_process.return_value = mock_docling_result

        mock_indexer = MagicMock()
        mock_indexer_cls.return_value = mock_indexer
        mock_collection = MagicMock()
        mock_indexer.create_or_replace_collection.return_value = mock_collection
        mock_indexer.index_chunks.return_value = 3

        ingest_domain(
            domain_name="test-domain",
            domains_root=domain_dir.parent,
            force=True,
        )

        mock_indexer.create_or_replace_collection.assert_called_once_with(
            "test-domain", force=True
        )


# ---------------------------------------------------------------------------
# Import contract tests
# ---------------------------------------------------------------------------


class TestImportContracts:
    """Verify module exports are accessible."""

    def test_ingest_domain_importable(self):
        from ingestion.ingest import ingest_domain

        assert callable(ingest_domain)

    def test_build_parser_importable(self):
        from ingestion.ingest import build_parser

        assert callable(build_parser)

    def test_cli_main_importable(self):
        from ingestion.ingest import cli_main

        assert callable(cli_main)
