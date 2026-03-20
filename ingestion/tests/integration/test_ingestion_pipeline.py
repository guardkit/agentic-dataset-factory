"""Integration tests covering 8 BDD smoke scenarios for the ingestion pipeline.

TASK-ING-007: Exercises the full ingestion pipeline end-to-end, from GOAL.md
reading through Docling processing, text chunking, and ChromaDB indexing.

BDD Smoke Scenarios:
  1. Ingesting a standard PDF document into ChromaDB
  2. Ingesting a scanned PDF document via VLM mode (mocked)
  3. Processing multiple source documents in a single run
  4. Chunks carry source metadata after indexing
  5. Text is split into fixed-size chunks with overlap
  6. ChromaDB collection is named after the domain
  7. Domain directory does not exist → DomainNotFoundError
  8. GOAL.md is missing from the domain directory → GoalValidationError

Uses pytest tmp_path for isolation, mocked Docling for reproducibility,
and real ChromaDB PersistentClient with temporary persist directories.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import chromadb
import pytest

from ingestion.chromadb_indexer import ChromaDBIndexer
from ingestion.chunker import chunk_text
from ingestion.docling_processor import ExtractedDocument, ExtractedPage
from ingestion.errors import DomainNotFoundError, GoalValidationError
from ingestion.ingest import ingest_domain
from ingestion.models import Chunk, IngestResult


# ---------------------------------------------------------------------------
# Markers
# ---------------------------------------------------------------------------

pytestmark = [pytest.mark.integration]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_LONG_TEXT = (
    "The study of English literature encompasses a wide range of texts, periods, "
    "and genres. From the medieval period through to contemporary writing, students "
    "engage with poetry, prose, and drama to develop critical analytical skills. "
    "Understanding literary techniques such as metaphor, simile, alliteration, and "
    "personification allows readers to appreciate the craft behind effective writing. "
    "Close reading of texts reveals layers of meaning and authorial intent that "
    "surface-level reading may miss. The examination of context — historical, social, "
    "cultural, and biographical — enriches interpretation and supports nuanced argument "
    "construction. Assessment requires students to produce extended analytical responses "
    "demonstrating knowledge of the text and the ability to sustain a coherent argument. "
)
"""~700 characters of plausible page text — long enough to produce multiple chunks."""


def _make_domain(
    tmp_path: Path,
    domain_name: str,
    *,
    source_docs: list[tuple[str, str]] | None = None,
    create_goal: bool = True,
    create_sources_dir: bool = True,
) -> Path:
    """Build a minimal domain directory for integration tests.

    Args:
        tmp_path: pytest temporary directory.
        domain_name: Name of the domain sub-directory.
        source_docs: List of (filename, mode) pairs. Dummy PDF files are
            created for each entry in the ``sources/`` directory.
        create_goal: Whether to write a GOAL.md with the Source Documents table.
        create_sources_dir: Whether to create the ``sources/`` directory.

    Returns:
        Path to the domain directory (``tmp_path / domain_name``).
    """
    domain = tmp_path / domain_name
    domain.mkdir(parents=True)

    if source_docs is None:
        source_docs = [("test-doc.pdf", "standard")]

    if create_sources_dir:
        sources = domain / "sources"
        sources.mkdir()
        for filename, _mode in source_docs:
            (sources / filename).write_bytes(b"%PDF-1.4 fake content for integration testing")

    if create_goal:
        rows = "\n".join(
            f"| {fname} | {mode} | integration test |" for fname, mode in source_docs
        )
        goal_text = (
            f"# {domain_name}\n\n"
            "## Source Documents\n\n"
            "| File Pattern | Mode | Notes |\n"
            "| --- | --- | --- |\n"
            f"{rows}\n"
        )
        (domain / "GOAL.md").write_text(goal_text, encoding="utf-8")

    return domain


def _mock_process_document(pages_text: list[str], mode: str = "standard"):
    """Return a function that simulates Docling extraction.

    Args:
        pages_text: List of text strings, one per page.
        mode: Docling mode to record in the result.

    Returns:
        A callable matching the ``process_document`` signature.
    """

    def _process(file_path: Path, mode: str = mode) -> ExtractedDocument:
        pages = [
            ExtractedPage(page_number=i + 1, text=text)
            for i, text in enumerate(pages_text)
        ]
        return ExtractedDocument(
            source_file=str(file_path),
            pages=pages,
            mode=mode,
        )

    return _process


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def chromadb_dir(tmp_path: Path) -> Path:
    """Provide an isolated temporary directory for ChromaDB persistence."""
    db_dir = tmp_path / "chroma_data"
    db_dir.mkdir()
    return db_dir


# ---------------------------------------------------------------------------
# Scenario 1: Ingesting a standard PDF document into ChromaDB
# ---------------------------------------------------------------------------


class TestStandardPDFIngestion:
    """BDD smoke: Ingesting a standard PDF document into ChromaDB."""

    @patch("ingestion.ingest.process_document")
    def test_standard_pdf_produces_indexed_chunks(
        self, mock_process, tmp_path: Path, chromadb_dir: Path
    ):
        """Full pipeline with standard mode PDF produces chunks in ChromaDB."""
        domain = _make_domain(
            tmp_path, "std-domain", source_docs=[("english-lit.pdf", "standard")]
        )
        mock_process.side_effect = _mock_process_document([_LONG_TEXT])

        result = ingest_domain(
            domain_name="std-domain",
            domains_root=tmp_path,
            persist_directory=str(chromadb_dir),
            force=True,
        )

        assert isinstance(result, IngestResult)
        assert result.documents_processed == 1
        assert result.chunks_created >= 1
        assert result.collection_name == "std-domain"

        # Verify chunks actually exist in ChromaDB
        client = chromadb.PersistentClient(path=str(chromadb_dir))
        collection = client.get_collection("std-domain")
        stored = collection.get()
        assert len(stored["ids"]) == result.chunks_created


# ---------------------------------------------------------------------------
# Scenario 2: Ingesting a scanned PDF document via VLM mode
# ---------------------------------------------------------------------------


class TestVLMPDFIngestion:
    """BDD smoke: Ingesting a scanned PDF document via VLM mode."""

    @patch("ingestion.ingest.process_document")
    def test_vlm_mode_pdf_produces_indexed_chunks(
        self, mock_process, tmp_path: Path, chromadb_dir: Path
    ):
        """VLM mode document is processed and indexed (Docling mocked)."""
        domain = _make_domain(
            tmp_path, "vlm-domain", source_docs=[("scanned-paper.pdf", "vlm")]
        )

        vlm_text = (
            "This text was extracted from a scanned document using optical character "
            "recognition. The original document contained handwritten annotations and "
            "printed text that has been digitised for further processing. " * 5
        )

        def vlm_processor(file_path: Path, mode: str = "vlm") -> ExtractedDocument:
            return ExtractedDocument(
                source_file=str(file_path),
                pages=[ExtractedPage(page_number=1, text=vlm_text)],
                mode="vlm",
            )

        mock_process.side_effect = vlm_processor

        result = ingest_domain(
            domain_name="vlm-domain",
            domains_root=tmp_path,
            persist_directory=str(chromadb_dir),
            force=True,
        )

        assert result.documents_processed == 1
        assert result.chunks_created >= 1

        # Verify the metadata records vlm mode
        client = chromadb.PersistentClient(path=str(chromadb_dir))
        collection = client.get_collection("vlm-domain")
        stored = collection.get(include=["metadatas"])
        for meta in stored["metadatas"]:
            assert meta["docling_mode"] == "vlm"


# ---------------------------------------------------------------------------
# Scenario 3: Processing multiple source documents in a single run
# ---------------------------------------------------------------------------


class TestMultipleDocuments:
    """BDD smoke: Processing multiple source documents in a single run."""

    @patch("ingestion.ingest.process_document")
    def test_three_documents_all_indexed(
        self, mock_process, tmp_path: Path, chromadb_dir: Path
    ):
        """3 documents in a single run — all indexed into the same collection."""
        docs = [
            ("doc-alpha.pdf", "standard"),
            ("doc-beta.pdf", "standard"),
            ("doc-gamma.pdf", "standard"),
        ]
        domain = _make_domain(tmp_path, "multi-domain", source_docs=docs)

        page_texts = {
            "doc-alpha.pdf": "Alpha document content about Shakespeare's plays. " * 15,
            "doc-beta.pdf": "Beta document discussing Romantic poetry movements. " * 15,
            "doc-gamma.pdf": "Gamma document analysing modern prose techniques. " * 15,
        }

        def multi_processor(file_path: Path, mode: str = "standard") -> ExtractedDocument:
            fname = Path(file_path).name
            text = page_texts.get(fname, "Fallback content. " * 15)
            return ExtractedDocument(
                source_file=str(file_path),
                pages=[ExtractedPage(page_number=1, text=text)],
                mode=mode,
            )

        mock_process.side_effect = multi_processor

        result = ingest_domain(
            domain_name="multi-domain",
            domains_root=tmp_path,
            persist_directory=str(chromadb_dir),
            force=True,
        )

        assert result.documents_processed == 3
        assert result.chunks_created >= 3  # at least 1 chunk per doc

        # All chunks in a single collection
        client = chromadb.PersistentClient(path=str(chromadb_dir))
        collection = client.get_collection("multi-domain")
        stored = collection.get()
        assert len(stored["ids"]) == result.chunks_created


# ---------------------------------------------------------------------------
# Scenario 4: Chunks carry source metadata after indexing
# ---------------------------------------------------------------------------


class TestChunkMetadata:
    """BDD smoke: Chunks carry source metadata after indexing."""

    @patch("ingestion.ingest.process_document")
    def test_metadata_fields_present_on_indexed_chunks(
        self, mock_process, tmp_path: Path, chromadb_dir: Path
    ):
        """Each indexed chunk includes all 5 required metadata fields."""
        domain = _make_domain(
            tmp_path, "meta-domain", source_docs=[("curriculum.pdf", "standard")]
        )
        mock_process.side_effect = _mock_process_document([_LONG_TEXT])

        result = ingest_domain(
            domain_name="meta-domain",
            domains_root=tmp_path,
            persist_directory=str(chromadb_dir),
            force=True,
        )

        assert result.chunks_created >= 1

        client = chromadb.PersistentClient(path=str(chromadb_dir))
        collection = client.get_collection("meta-domain")
        stored = collection.get(include=["metadatas"])

        required_keys = {"source_file", "page_number", "chunk_index", "docling_mode", "domain"}

        for meta in stored["metadatas"]:
            present_keys = set(meta.keys())
            missing = required_keys - present_keys
            assert not missing, f"Missing metadata fields: {missing}. Got: {meta}"
            assert meta["domain"] == "meta-domain"
            assert meta["docling_mode"] == "standard"
            assert isinstance(meta["page_number"], int)
            assert isinstance(meta["chunk_index"], int)
            assert meta["source_file"] == "curriculum.pdf"


# ---------------------------------------------------------------------------
# Scenario 5: Text is split into fixed-size chunks with overlap
# ---------------------------------------------------------------------------


class TestChunkSizeAndOverlap:
    """BDD smoke: Text is split into fixed-size chunks with overlap."""

    def test_chunks_respect_configured_size(self):
        """Each chunk's length is approximately the configured chunk size."""
        chunk_size = 200
        overlap = 40
        long_text = _LONG_TEXT * 3  # ~2100 chars — should produce multiple chunks

        chunks = chunk_text(text=long_text, chunk_size=chunk_size, overlap=overlap)

        assert len(chunks) >= 2, "Expected multiple chunks from long text"
        for chunk in chunks:
            # Allow some flexibility due to word-boundary splitting
            assert len(chunk.text) <= chunk_size + 50, (
                f"Chunk too long: {len(chunk.text)} chars (limit ~{chunk_size})"
            )

    def test_consecutive_chunks_overlap(self):
        """Consecutive chunks share overlapping content."""
        chunk_size = 200
        overlap = 40
        long_text = _LONG_TEXT * 3

        chunks = chunk_text(text=long_text, chunk_size=chunk_size, overlap=overlap)

        assert len(chunks) >= 2, "Need at least 2 chunks to test overlap"
        for i in range(len(chunks) - 1):
            current_text = chunks[i].text
            next_text = chunks[i + 1].text
            # RecursiveCharacterTextSplitter splits on semantic boundaries and
            # the overlap region may not align to exact word boundaries. Check
            # that the beginning of the next chunk appears within the current
            # chunk, confirming shared content.
            next_start_words = next_text.split()[:3]
            next_start_phrase = " ".join(next_start_words)
            assert next_start_phrase in current_text, (
                f"Chunks {i} and {i + 1} show no overlap. "
                f"Current ends with: '{current_text[-60:]}', "
                f"Next starts with: '{next_text[:60]}'"
            )

    def test_chunk_index_metadata_is_sequential(self):
        """chunk_index metadata is assigned sequentially starting from 0."""
        chunks = chunk_text(
            text=_LONG_TEXT * 3,
            chunk_size=200,
            overlap=40,
            source_metadata={"source_file": "test.pdf", "domain": "test"},
        )
        indices = [c.metadata["chunk_index"] for c in chunks]
        assert indices == list(range(len(chunks)))


# ---------------------------------------------------------------------------
# Scenario 6: ChromaDB collection is named after the domain
# ---------------------------------------------------------------------------


class TestCollectionNaming:
    """BDD smoke: ChromaDB collection is named after the domain."""

    @patch("ingestion.ingest.process_document")
    def test_collection_named_after_domain(
        self, mock_process, tmp_path: Path, chromadb_dir: Path
    ):
        """The ChromaDB collection uses the domain name."""
        domain_name = "gcse-english-tutor"
        domain = _make_domain(
            tmp_path, domain_name, source_docs=[("syllabus.pdf", "standard")]
        )
        mock_process.side_effect = _mock_process_document([_LONG_TEXT])

        result = ingest_domain(
            domain_name=domain_name,
            domains_root=tmp_path,
            persist_directory=str(chromadb_dir),
            force=True,
        )

        assert result.collection_name == domain_name

        # Verify the collection actually exists in ChromaDB with the right name
        client = chromadb.PersistentClient(path=str(chromadb_dir))
        collection = client.get_collection(domain_name)
        assert collection.name == domain_name
        assert collection.count() == result.chunks_created
        assert collection.count() >= 1


# ---------------------------------------------------------------------------
# Scenario 7: Domain directory does not exist → DomainNotFoundError
# ---------------------------------------------------------------------------


class TestDomainNotFound:
    """BDD smoke: Domain directory does not exist → DomainNotFoundError."""

    def test_missing_domain_raises_domain_not_found_error(
        self, tmp_path: Path, chromadb_dir: Path
    ):
        """DomainNotFoundError raised when domain directory is absent."""
        with pytest.raises(DomainNotFoundError, match="not found"):
            ingest_domain(
                domain_name="nonexistent-domain",
                domains_root=tmp_path,
                persist_directory=str(chromadb_dir),
            )

    def test_error_message_includes_domain_path(self, tmp_path: Path, chromadb_dir: Path):
        """The error message references the domain path for debugging."""
        with pytest.raises(DomainNotFoundError) as exc_info:
            ingest_domain(
                domain_name="phantom-domain",
                domains_root=tmp_path,
                persist_directory=str(chromadb_dir),
            )
        assert "phantom-domain" in str(exc_info.value)


# ---------------------------------------------------------------------------
# Scenario 8: GOAL.md is missing → GoalValidationError
# ---------------------------------------------------------------------------


class TestMissingGoalMd:
    """BDD smoke: GOAL.md is missing from domain directory → GoalValidationError."""

    def test_missing_goal_md_raises_goal_validation_error(
        self, tmp_path: Path, chromadb_dir: Path
    ):
        """GoalValidationError raised when GOAL.md is absent from domain directory."""
        _make_domain(
            tmp_path, "no-goal-domain", create_goal=False, create_sources_dir=True
        )

        with pytest.raises(GoalValidationError, match="GOAL.md"):
            ingest_domain(
                domain_name="no-goal-domain",
                domains_root=tmp_path,
                persist_directory=str(chromadb_dir),
            )

    def test_error_message_references_domain_directory(
        self, tmp_path: Path, chromadb_dir: Path
    ):
        """The error message names the domain directory for debugging."""
        _make_domain(
            tmp_path, "broken-domain", create_goal=False, create_sources_dir=True
        )

        with pytest.raises(GoalValidationError) as exc_info:
            ingest_domain(
                domain_name="broken-domain",
                domains_root=tmp_path,
                persist_directory=str(chromadb_dir),
            )
        assert "broken-domain" in str(exc_info.value)
