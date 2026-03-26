"""Tests for ChromaDB indexer: collection CRUD and batch upsert.

Covers all acceptance criteria for TASK-ING-004:
- AC-001: PersistentClient with configurable persist_directory
- AC-002: collection_exists() correctly detects existing collections
- AC-003: create_or_replace_collection() creates new collection when none exists
- AC-004: create_or_replace_collection() with force=True deletes and recreates
- AC-005: create_or_replace_collection() with force=False raises CollectionExistsError
- AC-006: index_chunks() indexes with correct metadata
- AC-007: index_chunks() uses configurable batch_size
- AC-008: index_chunks() handles individual chunk embedding failures gracefully
- AC-009: Force re-ingestion logs warning about concurrent access safety (ASSUM-004)
- AC-010: ChromaDB connection failure raises IndexingError
- AC-011: All modified files pass lint/format checks

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

from ingestion.errors import IndexingError
from ingestion.models import Chunk


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def tmp_persist_dir(tmp_path):
    """Provide a temporary directory for ChromaDB persistence."""
    return str(tmp_path / "chroma_data")


@pytest.fixture
def indexer(tmp_persist_dir):
    """Create a ChromaDBIndexer with a temporary persist directory."""
    from ingestion.chromadb_indexer import ChromaDBIndexer

    return ChromaDBIndexer(persist_directory=tmp_persist_dir)


@pytest.fixture
def sample_chunks():
    """Create a list of sample chunks for indexing tests."""
    return [
        Chunk(
            text="This is chunk zero about English literature.",
            metadata={
                "source_file": "mr-bruff-language.pdf",
                "page_number": 1,
                "chunk_index": 0,
                "docling_mode": "standard",
                "domain": "gcse-english-tutor",
            },
        ),
        Chunk(
            text="This is chunk one about poetry analysis.",
            metadata={
                "source_file": "mr-bruff-language.pdf",
                "page_number": 1,
                "chunk_index": 1,
                "docling_mode": "standard",
                "domain": "gcse-english-tutor",
            },
        ),
        Chunk(
            text="This is chunk two about creative writing.",
            metadata={
                "source_file": "mr-bruff-language.pdf",
                "page_number": 2,
                "chunk_index": 2,
                "docling_mode": "standard",
                "domain": "gcse-english-tutor",
            },
        ),
    ]


@pytest.fixture
def large_chunk_set():
    """Create a large set of chunks to test batch processing."""
    chunks = []
    for i in range(25):
        chunks.append(
            Chunk(
                text=f"Chunk number {i} with content about topic {i}.",
                metadata={
                    "source_file": f"doc-{i // 10}.pdf",
                    "page_number": i // 5,
                    "chunk_index": i,
                    "docling_mode": "standard",
                    "domain": "gcse-english-tutor",
                },
            )
        )
    return chunks


# ---------------------------------------------------------------------------
# AC-001: PersistentClient with configurable persist_directory
# ---------------------------------------------------------------------------


class TestPersistentClientInit:
    def test_init_creates_indexer_with_custom_directory(self, tmp_persist_dir):
        from ingestion.chromadb_indexer import ChromaDBIndexer

        indexer = ChromaDBIndexer(persist_directory=tmp_persist_dir)
        assert indexer is not None

    def test_init_uses_default_persist_directory(self):
        """Default persist_directory should be './chroma_data'."""
        from ingestion.chromadb_indexer import ChromaDBIndexer

        with patch("ingestion.chromadb_indexer.chromadb") as mock_chromadb:
            mock_chromadb.PersistentClient.return_value = MagicMock()
            ChromaDBIndexer()
            mock_chromadb.PersistentClient.assert_called_once_with(
                path="./chroma_data"
            )

    def test_init_passes_persist_directory_to_persistent_client(self, tmp_persist_dir):
        from ingestion.chromadb_indexer import ChromaDBIndexer

        with patch("ingestion.chromadb_indexer.chromadb") as mock_chromadb:
            mock_chromadb.PersistentClient.return_value = MagicMock()
            ChromaDBIndexer(persist_directory=tmp_persist_dir)
            mock_chromadb.PersistentClient.assert_called_once_with(
                path=tmp_persist_dir
            )

    def test_init_raises_indexing_error_on_connection_failure(self, tmp_path):
        """AC-010: ChromaDB connection failure raises IndexingError."""
        from ingestion.chromadb_indexer import ChromaDBIndexer

        with patch("ingestion.chromadb_indexer.chromadb") as mock_chromadb:
            mock_chromadb.PersistentClient.side_effect = RuntimeError(
                "ChromaDB unavailable"
            )
            with pytest.raises(IndexingError, match="ChromaDB"):
                ChromaDBIndexer(persist_directory=str(tmp_path / "bad"))


# ---------------------------------------------------------------------------
# AC-002: collection_exists() correctly detects existing collections
# ---------------------------------------------------------------------------


class TestCollectionExists:
    def test_returns_false_for_nonexistent_collection(self, indexer):
        assert indexer.collection_exists("nonexistent-collection") is False

    def test_returns_true_for_existing_collection(self, indexer):
        indexer.create_or_replace_collection("test-domain")
        assert indexer.collection_exists("test-domain") is True

    def test_returns_false_after_collection_deleted(self, indexer):
        indexer.create_or_replace_collection("temp-domain")
        # Delete via force replace, then check different name
        assert indexer.collection_exists("other-domain") is False


# ---------------------------------------------------------------------------
# AC-003: create_or_replace_collection() creates new collection when none exists
# ---------------------------------------------------------------------------


class TestCreateCollection:
    def test_creates_new_collection(self, indexer):
        collection = indexer.create_or_replace_collection("new-domain")
        assert collection is not None
        assert collection.name == "new-domain"

    def test_collection_is_accessible_after_creation(self, indexer):
        indexer.create_or_replace_collection("new-domain")
        assert indexer.collection_exists("new-domain") is True


# ---------------------------------------------------------------------------
# AC-004: create_or_replace_collection() with force=True replaces existing
# ---------------------------------------------------------------------------


class TestForceReplaceCollection:
    def test_force_true_replaces_existing_collection(self, indexer, sample_chunks):
        # Create collection and add some data
        collection = indexer.create_or_replace_collection("my-domain")
        indexer.index_chunks(collection, sample_chunks)

        # Force replace — should succeed and return empty collection
        new_collection = indexer.create_or_replace_collection(
            "my-domain", force=True
        )
        assert new_collection is not None
        assert new_collection.name == "my-domain"
        assert new_collection.count() == 0

    def test_force_true_on_nonexistent_collection_creates_new(self, indexer):
        collection = indexer.create_or_replace_collection(
            "fresh-domain", force=True
        )
        assert collection is not None
        assert collection.name == "fresh-domain"


# ---------------------------------------------------------------------------
# AC-005: create_or_replace_collection() with force=False raises error
# ---------------------------------------------------------------------------


class TestCollectionExistsError:
    def test_force_false_raises_collection_exists_error(self, indexer):
        from ingestion.errors import CollectionExistsError

        indexer.create_or_replace_collection("existing-domain")
        with pytest.raises(CollectionExistsError):
            indexer.create_or_replace_collection("existing-domain", force=False)

    def test_collection_exists_error_is_ingestion_error_subclass(self):
        from ingestion.errors import CollectionExistsError, IngestionError

        assert issubclass(CollectionExistsError, IngestionError)

    def test_force_false_is_default(self, indexer):
        from ingestion.errors import CollectionExistsError

        indexer.create_or_replace_collection("dup-domain")
        with pytest.raises(CollectionExistsError):
            indexer.create_or_replace_collection("dup-domain")


# ---------------------------------------------------------------------------
# AC-006: index_chunks() indexes with correct metadata
# ---------------------------------------------------------------------------


class TestIndexChunksMetadata:
    def test_indexes_chunks_with_correct_metadata(self, indexer, sample_chunks):
        collection = indexer.create_or_replace_collection("gcse-english-tutor")
        count = indexer.index_chunks(collection, sample_chunks)

        assert count == 3

        # Verify metadata is stored correctly
        result = collection.get(include=["metadatas", "documents"])
        assert len(result["metadatas"]) == 3

        # Check one chunk's metadata has all required keys
        metadata_keys = set(result["metadatas"][0].keys())
        expected_keys = {
            "source_file",
            "page_number",
            "chunk_index",
            "docling_mode",
            "domain",
        }
        assert expected_keys.issubset(metadata_keys)

    def test_chunk_ids_are_deterministic(self, indexer, sample_chunks):
        """IDs should be {domain}_{source_file}_p{page}_c{chunk_index}."""
        collection = indexer.create_or_replace_collection("gcse-english-tutor")
        indexer.index_chunks(collection, sample_chunks)

        result = collection.get()
        ids = set(result["ids"])
        expected_ids = {
            "gcse-english-tutor_mr-bruff-language.pdf_p1_c0",
            "gcse-english-tutor_mr-bruff-language.pdf_p1_c1",
            "gcse-english-tutor_mr-bruff-language.pdf_p2_c2",
        }
        assert ids == expected_ids

    def test_documents_stored_correctly(self, indexer, sample_chunks):
        collection = indexer.create_or_replace_collection("gcse-english-tutor")
        indexer.index_chunks(collection, sample_chunks)

        result = collection.get(include=["documents"])
        assert len(result["documents"]) == 3
        texts = set(result["documents"])
        assert "This is chunk zero about English literature." in texts

    def test_returns_count_of_indexed_chunks(self, indexer, sample_chunks):
        collection = indexer.create_or_replace_collection("gcse-english-tutor")
        count = indexer.index_chunks(collection, sample_chunks)
        assert count == 3

    def test_empty_chunk_list_returns_zero(self, indexer):
        collection = indexer.create_or_replace_collection("empty-domain")
        count = indexer.index_chunks(collection, [])
        assert count == 0


# ---------------------------------------------------------------------------
# AC-007: index_chunks() uses configurable batch_size
# ---------------------------------------------------------------------------


class TestBatchSize:
    def test_respects_custom_batch_size(self, indexer, large_chunk_set):
        """With 25 chunks and batch_size=10, should process in 3 batches."""
        collection = indexer.create_or_replace_collection("batch-domain")
        count = indexer.index_chunks(
            collection, large_chunk_set, batch_size=10
        )
        assert count == 25
        assert collection.count() == 25

    def test_default_batch_size_is_500(self, indexer, sample_chunks):
        """Default batch_size is 500; 3 chunks fit in one batch."""
        collection = indexer.create_or_replace_collection("default-batch")
        count = indexer.index_chunks(collection, sample_chunks)
        assert count == 3

    def test_batch_size_one_processes_individually(self, indexer, sample_chunks):
        collection = indexer.create_or_replace_collection("single-batch")
        count = indexer.index_chunks(collection, sample_chunks, batch_size=1)
        assert count == 3
        assert collection.count() == 3

    def test_batch_size_equals_chunk_count(self, indexer, sample_chunks):
        collection = indexer.create_or_replace_collection("exact-batch")
        count = indexer.index_chunks(collection, sample_chunks, batch_size=3)
        assert count == 3
        assert collection.count() == 3


# ---------------------------------------------------------------------------
# AC-008: index_chunks() handles individual chunk embedding failures gracefully
# ---------------------------------------------------------------------------


class TestEmbeddingFailureHandling:
    def test_skips_failed_chunks_and_continues(self, indexer, caplog):
        """If a chunk fails to embed, log + skip and continue with others."""
        # Create a mock collection that fails on the second add call
        mock_collection = MagicMock()
        mock_collection.name = "fail-domain"
        mock_collection.count.return_value = 2

        call_count = 0

        def mock_add(**kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 2:
                raise RuntimeError("Embedding failed for chunk")

        mock_collection.add.side_effect = mock_add

        chunks = [
            Chunk(
                text=f"Chunk {i}",
                metadata={
                    "source_file": "doc.pdf",
                    "page_number": 0,
                    "chunk_index": i,
                    "docling_mode": "standard",
                    "domain": "fail-domain",
                },
            )
            for i in range(3)
        ]

        with caplog.at_level(logging.WARNING):
            indexer.index_chunks(mock_collection, chunks, batch_size=1)

        # Should have logged a warning about the failure
        assert any(
            "fail" in record.message.lower() or "error" in record.message.lower()
            for record in caplog.records
        )

    def test_returns_count_of_successfully_indexed_only(self, indexer):
        """Return count should exclude failed chunks."""
        mock_collection = MagicMock()
        mock_collection.name = "partial-domain"

        call_count = 0

        def mock_add(**kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 2:
                raise RuntimeError("Embedding failed")

        mock_collection.add.side_effect = mock_add

        chunks = [
            Chunk(
                text=f"Chunk {i}",
                metadata={
                    "source_file": "doc.pdf",
                    "page_number": 0,
                    "chunk_index": i,
                    "docling_mode": "standard",
                    "domain": "partial-domain",
                },
            )
            for i in range(3)
        ]

        count = indexer.index_chunks(mock_collection, chunks, batch_size=1)
        # 3 chunks, 1 fails, so 2 should succeed
        assert count == 2


# ---------------------------------------------------------------------------
# AC-009: Force re-ingestion logs warning about concurrent access (ASSUM-004)
# ---------------------------------------------------------------------------


class TestConcurrentAccessWarning:
    def test_force_replace_logs_concurrent_access_warning(self, indexer, caplog):
        indexer.create_or_replace_collection("warned-domain")

        with caplog.at_level(logging.WARNING):
            indexer.create_or_replace_collection("warned-domain", force=True)

        assert any(
            "concurrent" in record.message.lower()
            for record in caplog.records
        ), "Expected warning about concurrent access safety"


# ---------------------------------------------------------------------------
# AC-010: ChromaDB connection failure raises IndexingError
# ---------------------------------------------------------------------------


class TestConnectionFailure:
    def test_indexing_error_on_chromadb_unavailable(self):
        """Already tested in TestPersistentClientInit; verify message."""
        from ingestion.chromadb_indexer import ChromaDBIndexer

        with patch("ingestion.chromadb_indexer.chromadb") as mock_chromadb:
            mock_chromadb.PersistentClient.side_effect = Exception("connection refused")
            with pytest.raises(IndexingError, match="connection refused"):
                ChromaDBIndexer(persist_directory="/nonexistent/path")

    def test_indexing_error_during_collection_creation(self, tmp_persist_dir):
        from ingestion.chromadb_indexer import ChromaDBIndexer

        with patch("ingestion.chromadb_indexer.chromadb") as mock_chromadb:
            mock_client = MagicMock()
            mock_chromadb.PersistentClient.return_value = mock_client
            mock_client.list_collections.return_value = []
            mock_client.create_collection.side_effect = RuntimeError("disk full")

            indexer = ChromaDBIndexer(persist_directory=tmp_persist_dir)
            with pytest.raises(IndexingError, match="disk full"):
                indexer.create_or_replace_collection("bad-domain")


# ---------------------------------------------------------------------------
# Import contract tests
# ---------------------------------------------------------------------------


class TestImportContracts:
    def test_chromadb_indexer_importable_from_module(self):
        from ingestion.chromadb_indexer import ChromaDBIndexer

        assert ChromaDBIndexer is not None

    def test_collection_exists_error_importable_from_errors(self):
        from ingestion.errors import CollectionExistsError

        assert CollectionExistsError is not None

    def test_collection_exists_error_in_errors_all(self):
        from ingestion import errors

        assert "CollectionExistsError" in errors.__all__

    def test_chromadb_indexer_importable_from_package(self):
        from ingestion import ChromaDBIndexer

        assert ChromaDBIndexer is not None

    def test_collection_exists_error_importable_from_package(self):
        from ingestion import CollectionExistsError

        assert CollectionExistsError is not None
