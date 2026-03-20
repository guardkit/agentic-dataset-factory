"""Tests for tools.rag_retrieval — create_rag_retrieval_tool factory and rag_retrieval tool.

TDD RED phase: These tests define the contract for TASK-LCT-002.

Acceptance Criteria covered:
- AC-001: Factory returns a LangChain @tool-decorated callable
- AC-002: Collection name is bound at factory time, not passed per call
- AC-003: ChromaDB PersistentClient is lazily initialised on first call
- AC-004: Subsequent calls reuse the same client connection
- AC-005: Returns formatted chunks with source metadata
- AC-006: Validates n_results: 1 <= n_results <= 20
- AC-007: Default n_results is 5
- AC-008: Returns all available chunks if collection has fewer than n_results
- AC-009: Collection-not-found returns error string (not exception)
- AC-010: ChromaDB unavailable returns error string (not exception)
- AC-011: Handles chunks with missing source metadata gracefully
- AC-012: Collection name with path traversal characters is rejected at factory time
- AC-013: All errors returned as descriptive strings, never raised as exceptions (D7)
- AC-014: All modified files pass project-configured lint/format checks
"""

from __future__ import annotations

import ast
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from langchain_core.tools import BaseTool

from tools.rag_retrieval import create_rag_retrieval_tool


# ===========================================================================
# Helpers
# ===========================================================================


def _make_mock_collection(
    documents: list[str] | None = None,
    metadatas: list[dict[str, Any]] | None = None,
    ids: list[str] | None = None,
) -> MagicMock:
    """Build a mock ChromaDB collection that returns the given query results."""
    collection = MagicMock()
    result: dict[str, Any] = {
        "documents": [documents or []],
        "metadatas": [metadatas or []],
        "ids": [ids or []],
    }
    collection.query.return_value = result
    return collection


def _make_mock_client(collection: MagicMock | None = None) -> MagicMock:
    """Build a mock ChromaDB PersistentClient."""
    client = MagicMock()
    if collection is not None:
        client.get_collection.return_value = collection
    return client


# ===========================================================================
# AC-001: Factory returns a LangChain @tool-decorated callable
# ===========================================================================


class TestFactoryReturnsTool:
    """Verify the factory returns a LangChain tool-decorated callable."""

    def test_factory_returns_langchain_tool(self) -> None:
        """AC-001: create_rag_retrieval_tool returns a LangChain BaseTool."""
        tool_fn = create_rag_retrieval_tool("test-collection")
        assert isinstance(tool_fn, BaseTool)

    def test_returned_callable_has_tool_name(self) -> None:
        """AC-001: Returned callable has the LangChain tool name attribute."""
        tool_fn = create_rag_retrieval_tool("test-collection")
        assert hasattr(tool_fn, "name")
        assert tool_fn.name == "rag_retrieval"

    def test_returned_callable_has_tool_description(self) -> None:
        """AC-001: Returned callable has a tool description."""
        tool_fn = create_rag_retrieval_tool("test-collection")
        assert hasattr(tool_fn, "description")
        assert len(tool_fn.description) > 0


# ===========================================================================
# AC-002: Collection name bound at factory time
# ===========================================================================


class TestCollectionNameBinding:
    """Verify collection name is bound at factory time."""

    @pytest.mark.smoke
    @patch("tools.rag_retrieval.chromadb")
    def test_collection_name_used_in_query(self, mock_chromadb: MagicMock) -> None:
        """AC-002: Factory binds collection_name; it's not a per-call parameter."""
        collection = _make_mock_collection(
            documents=["chunk text"],
            metadatas=[{"source": "test.pdf", "page": "1"}],
            ids=["id1"],
        )
        client = _make_mock_client(collection)
        mock_chromadb.PersistentClient.return_value = client

        tool_fn = create_rag_retrieval_tool("my-special-collection")
        tool_fn.invoke({"query": "test query"})

        client.get_collection.assert_called_with(name="my-special-collection")

    def test_factory_call_signature_no_collection_param(self) -> None:
        """AC-002: The tool's invoke signature should not include collection_name."""
        tool_fn = create_rag_retrieval_tool("test-collection")
        # The tool schema args should only have query and n_results
        schema = tool_fn.args_schema
        field_names = set(schema.model_fields.keys())
        assert "collection_name" not in field_names
        assert "query" in field_names


# ===========================================================================
# AC-003: ChromaDB PersistentClient lazily initialised on first call
# ===========================================================================


class TestLazyInitialisation:
    """Verify ChromaDB client is lazily initialised."""

    @patch("tools.rag_retrieval.chromadb")
    def test_no_client_on_factory_creation(self, mock_chromadb: MagicMock) -> None:
        """AC-003: Creating the tool does NOT instantiate PersistentClient."""
        create_rag_retrieval_tool("test-collection")
        mock_chromadb.PersistentClient.assert_not_called()

    @patch("tools.rag_retrieval.chromadb")
    def test_client_created_on_first_call(self, mock_chromadb: MagicMock) -> None:
        """AC-003: First invocation creates the PersistentClient."""
        collection = _make_mock_collection(
            documents=["text"],
            metadatas=[{"source": "f.pdf", "page": "1"}],
            ids=["id1"],
        )
        client = _make_mock_client(collection)
        mock_chromadb.PersistentClient.return_value = client

        tool_fn = create_rag_retrieval_tool("test-collection")
        tool_fn.invoke({"query": "test"})

        mock_chromadb.PersistentClient.assert_called_once()


# ===========================================================================
# AC-004: Subsequent calls reuse the same client connection
# ===========================================================================


class TestClientReuse:
    """Verify subsequent calls reuse the ChromaDB client."""

    @patch("tools.rag_retrieval.chromadb")
    def test_client_reused_across_calls(self, mock_chromadb: MagicMock) -> None:
        """AC-004: Multiple invocations reuse the same PersistentClient."""
        collection = _make_mock_collection(
            documents=["text"],
            metadatas=[{"source": "f.pdf", "page": "1"}],
            ids=["id1"],
        )
        client = _make_mock_client(collection)
        mock_chromadb.PersistentClient.return_value = client

        tool_fn = create_rag_retrieval_tool("test-collection")
        tool_fn.invoke({"query": "query 1"})
        tool_fn.invoke({"query": "query 2"})
        tool_fn.invoke({"query": "query 3"})

        # PersistentClient should only be called once
        mock_chromadb.PersistentClient.assert_called_once()


# ===========================================================================
# AC-005: Returns formatted chunks with source metadata
# ===========================================================================


class TestFormattedOutput:
    """Verify output formatting matches the specification."""

    @pytest.mark.smoke
    @patch("tools.rag_retrieval.chromadb")
    def test_single_chunk_format(self, mock_chromadb: MagicMock) -> None:
        """AC-005: Single chunk formatted with source and page."""
        collection = _make_mock_collection(
            documents=["Shakespeare uses metaphor here."],
            metadatas=[{"source": "mr-bruff.pdf", "page": "42"}],
            ids=["id1"],
        )
        client = _make_mock_client(collection)
        mock_chromadb.PersistentClient.return_value = client

        tool_fn = create_rag_retrieval_tool("test-collection")
        result = tool_fn.invoke({"query": "metaphor", "n_results": 1})

        assert "--- Chunk 1 (source: mr-bruff.pdf, p.42) ---" in result
        assert "Shakespeare uses metaphor here." in result

    @patch("tools.rag_retrieval.chromadb")
    def test_multiple_chunks_format(self, mock_chromadb: MagicMock) -> None:
        """AC-005: Multiple chunks each formatted with sequential numbering."""
        collection = _make_mock_collection(
            documents=["First chunk.", "Second chunk.", "Third chunk."],
            metadatas=[
                {"source": "file1.pdf", "page": "1"},
                {"source": "file2.pdf", "page": "5"},
                {"source": "file3.pdf", "page": "10"},
            ],
            ids=["id1", "id2", "id3"],
        )
        client = _make_mock_client(collection)
        mock_chromadb.PersistentClient.return_value = client

        tool_fn = create_rag_retrieval_tool("test-collection")
        result = tool_fn.invoke({"query": "test", "n_results": 3})

        assert "--- Chunk 1 (source: file1.pdf, p.1) ---" in result
        assert "First chunk." in result
        assert "--- Chunk 2 (source: file2.pdf, p.5) ---" in result
        assert "Second chunk." in result
        assert "--- Chunk 3 (source: file3.pdf, p.10) ---" in result
        assert "Third chunk." in result

    @patch("tools.rag_retrieval.chromadb")
    def test_empty_collection_returns_no_results_message(
        self, mock_chromadb: MagicMock
    ) -> None:
        """AC-005: Empty results return a descriptive message."""
        collection = _make_mock_collection(documents=[], metadatas=[], ids=[])
        client = _make_mock_client(collection)
        mock_chromadb.PersistentClient.return_value = client

        tool_fn = create_rag_retrieval_tool("test-collection")
        result = tool_fn.invoke({"query": "obscure query"})

        assert "no" in result.lower() or "0" in result


# ===========================================================================
# AC-006: Validates n_results: 1 <= n_results <= 20
# ===========================================================================


class TestNResultsValidation:
    """Verify n_results validation returns error strings."""

    @patch("tools.rag_retrieval.chromadb")
    def test_n_results_zero_returns_error(self, mock_chromadb: MagicMock) -> None:
        """AC-006: n_results=0 returns error string."""
        tool_fn = create_rag_retrieval_tool("test-collection")
        result = tool_fn.invoke({"query": "test", "n_results": 0})
        assert "error" in result.lower()

    @patch("tools.rag_retrieval.chromadb")
    def test_n_results_negative_returns_error(self, mock_chromadb: MagicMock) -> None:
        """AC-006: Negative n_results returns error string."""
        tool_fn = create_rag_retrieval_tool("test-collection")
        result = tool_fn.invoke({"query": "test", "n_results": -5})
        assert "error" in result.lower()

    @patch("tools.rag_retrieval.chromadb")
    def test_n_results_above_max_returns_error(self, mock_chromadb: MagicMock) -> None:
        """AC-006: n_results=21 returns error string."""
        tool_fn = create_rag_retrieval_tool("test-collection")
        result = tool_fn.invoke({"query": "test", "n_results": 21})
        assert "error" in result.lower()

    @patch("tools.rag_retrieval.chromadb")
    def test_n_results_boundary_1_accepted(self, mock_chromadb: MagicMock) -> None:
        """AC-006: n_results=1 is accepted."""
        collection = _make_mock_collection(
            documents=["text"],
            metadatas=[{"source": "f.pdf", "page": "1"}],
            ids=["id1"],
        )
        client = _make_mock_client(collection)
        mock_chromadb.PersistentClient.return_value = client

        tool_fn = create_rag_retrieval_tool("test-collection")
        result = tool_fn.invoke({"query": "test", "n_results": 1})
        assert "error" not in result.lower()

    @patch("tools.rag_retrieval.chromadb")
    def test_n_results_boundary_20_accepted(self, mock_chromadb: MagicMock) -> None:
        """AC-006: n_results=20 is accepted."""
        collection = _make_mock_collection(
            documents=["text"],
            metadatas=[{"source": "f.pdf", "page": "1"}],
            ids=["id1"],
        )
        client = _make_mock_client(collection)
        mock_chromadb.PersistentClient.return_value = client

        tool_fn = create_rag_retrieval_tool("test-collection")
        result = tool_fn.invoke({"query": "test", "n_results": 20})
        assert "error" not in result.lower()

    @patch("tools.rag_retrieval.chromadb")
    def test_n_results_does_not_raise_exception(self, mock_chromadb: MagicMock) -> None:
        """AC-013: Validation errors returned as strings, not exceptions."""
        tool_fn = create_rag_retrieval_tool("test-collection")
        # Should NOT raise, should return error string
        result = tool_fn.invoke({"query": "test", "n_results": 100})
        assert isinstance(result, str)
        assert "error" in result.lower()


# ===========================================================================
# AC-007: Default n_results is 5
# ===========================================================================


class TestDefaultNResults:
    """Verify default n_results behavior."""

    @pytest.mark.smoke
    @patch("tools.rag_retrieval.chromadb")
    def test_default_n_results_is_5(self, mock_chromadb: MagicMock) -> None:
        """AC-007: When n_results not provided, defaults to 5."""
        collection = _make_mock_collection(
            documents=["text"],
            metadatas=[{"source": "f.pdf", "page": "1"}],
            ids=["id1"],
        )
        client = _make_mock_client(collection)
        mock_chromadb.PersistentClient.return_value = client

        tool_fn = create_rag_retrieval_tool("test-collection")
        tool_fn.invoke({"query": "test"})

        # Verify the collection.query was called with n_results=5
        collection.query.assert_called_once()
        call_kwargs = collection.query.call_args
        assert call_kwargs.kwargs.get("n_results") == 5 or call_kwargs[1].get("n_results") == 5


# ===========================================================================
# AC-008: Returns all available chunks if fewer than n_results
# ===========================================================================


class TestFewerChunksThanRequested:
    """Verify behavior when collection has fewer chunks than requested."""

    @patch("tools.rag_retrieval.chromadb")
    def test_returns_available_when_fewer_than_requested(
        self, mock_chromadb: MagicMock
    ) -> None:
        """AC-008: If collection has 2 chunks but 5 requested, return 2."""
        collection = _make_mock_collection(
            documents=["chunk one", "chunk two"],
            metadatas=[
                {"source": "a.pdf", "page": "1"},
                {"source": "b.pdf", "page": "2"},
            ],
            ids=["id1", "id2"],
        )
        client = _make_mock_client(collection)
        mock_chromadb.PersistentClient.return_value = client

        tool_fn = create_rag_retrieval_tool("test-collection")
        result = tool_fn.invoke({"query": "test", "n_results": 5})

        assert "Chunk 1" in result
        assert "Chunk 2" in result
        assert "chunk one" in result
        assert "chunk two" in result
        # Should NOT contain Chunk 3 etc.
        assert "Chunk 3" not in result


# ===========================================================================
# AC-009: Collection-not-found returns error string
# ===========================================================================


class TestCollectionNotFound:
    """Verify collection-not-found is returned as error string."""

    @pytest.mark.smoke
    @patch("tools.rag_retrieval.chromadb")
    def test_collection_not_found_returns_error_string(
        self, mock_chromadb: MagicMock
    ) -> None:
        """AC-009: Non-existent collection returns error string, not exception."""
        client = MagicMock()
        client.get_collection.side_effect = ValueError(
            "Collection nonexistent not found"
        )
        mock_chromadb.PersistentClient.return_value = client

        tool_fn = create_rag_retrieval_tool("nonexistent")
        result = tool_fn.invoke({"query": "test"})

        assert isinstance(result, str)
        assert "error" in result.lower()
        assert "nonexistent" in result.lower()

    @patch("tools.rag_retrieval.chromadb")
    def test_collection_not_found_does_not_raise(
        self, mock_chromadb: MagicMock
    ) -> None:
        """AC-013: Collection-not-found must not raise an exception."""
        client = MagicMock()
        client.get_collection.side_effect = ValueError("Collection not found")
        mock_chromadb.PersistentClient.return_value = client

        tool_fn = create_rag_retrieval_tool("missing-col")
        # Must not raise
        result = tool_fn.invoke({"query": "test"})
        assert isinstance(result, str)


# ===========================================================================
# AC-010: ChromaDB unavailable returns error string
# ===========================================================================


class TestChromaDBUnavailable:
    """Verify ChromaDB connection failures return error strings."""

    @patch("tools.rag_retrieval.chromadb")
    def test_chromadb_connection_error_returns_string(
        self, mock_chromadb: MagicMock
    ) -> None:
        """AC-010: ChromaDB unavailable returns error string."""
        mock_chromadb.PersistentClient.side_effect = ConnectionError(
            "Cannot connect to ChromaDB"
        )

        tool_fn = create_rag_retrieval_tool("test-collection")
        result = tool_fn.invoke({"query": "test"})

        assert isinstance(result, str)
        assert "error" in result.lower()

    @patch("tools.rag_retrieval.chromadb")
    def test_chromadb_unavailable_does_not_raise(
        self, mock_chromadb: MagicMock
    ) -> None:
        """AC-013: ChromaDB unavailable must not raise."""
        mock_chromadb.PersistentClient.side_effect = RuntimeError("DB down")

        tool_fn = create_rag_retrieval_tool("test-collection")
        result = tool_fn.invoke({"query": "test"})
        assert isinstance(result, str)


# ===========================================================================
# AC-011: Handles chunks with missing source metadata gracefully
# ===========================================================================


class TestMissingMetadata:
    """Verify graceful handling of missing chunk metadata."""

    @patch("tools.rag_retrieval.chromadb")
    def test_missing_source_key(self, mock_chromadb: MagicMock) -> None:
        """AC-011: Chunk without 'source' key still returns content."""
        collection = _make_mock_collection(
            documents=["text without source"],
            metadatas=[{"page": "5"}],  # no 'source' key
            ids=["id1"],
        )
        client = _make_mock_client(collection)
        mock_chromadb.PersistentClient.return_value = client

        tool_fn = create_rag_retrieval_tool("test-collection")
        result = tool_fn.invoke({"query": "test"})

        assert "text without source" in result
        assert "Chunk 1" in result

    @patch("tools.rag_retrieval.chromadb")
    def test_missing_page_key(self, mock_chromadb: MagicMock) -> None:
        """AC-011: Chunk without 'page' key still returns content."""
        collection = _make_mock_collection(
            documents=["text without page"],
            metadatas=[{"source": "file.pdf"}],  # no 'page' key
            ids=["id1"],
        )
        client = _make_mock_client(collection)
        mock_chromadb.PersistentClient.return_value = client

        tool_fn = create_rag_retrieval_tool("test-collection")
        result = tool_fn.invoke({"query": "test"})

        assert "text without page" in result
        assert "file.pdf" in result

    @patch("tools.rag_retrieval.chromadb")
    def test_empty_metadata(self, mock_chromadb: MagicMock) -> None:
        """AC-011: Chunk with empty metadata dict still returns content."""
        collection = _make_mock_collection(
            documents=["text with no metadata"],
            metadatas=[{}],
            ids=["id1"],
        )
        client = _make_mock_client(collection)
        mock_chromadb.PersistentClient.return_value = client

        tool_fn = create_rag_retrieval_tool("test-collection")
        result = tool_fn.invoke({"query": "test"})

        assert "text with no metadata" in result

    @patch("tools.rag_retrieval.chromadb")
    def test_none_metadata(self, mock_chromadb: MagicMock) -> None:
        """AC-011: Chunk with None metadata still returns content."""
        collection = _make_mock_collection(
            documents=["text with none metadata"],
            metadatas=[None],
            ids=["id1"],
        )
        client = _make_mock_client(collection)
        mock_chromadb.PersistentClient.return_value = client

        tool_fn = create_rag_retrieval_tool("test-collection")
        result = tool_fn.invoke({"query": "test"})

        assert "text with none metadata" in result


# ===========================================================================
# AC-012: Path traversal rejection at factory time
# ===========================================================================


class TestPathTraversalRejection:
    """Verify collection names with path traversal characters are rejected."""

    @pytest.mark.parametrize(
        "bad_name",
        [
            "../etc/passwd",
            "collection/../secret",
            "col/../../root",
            "test/path",
            "col\\name",
            "col..name",  # double dots
            "col name",  # spaces
            "col;drop",  # semicolons
            "col$var",  # dollar signs
        ],
    )
    def test_path_traversal_rejected_at_factory_time(self, bad_name: str) -> None:
        """AC-012: Path traversal chars rejected at factory creation time."""
        with pytest.raises(ValueError, match="collection"):
            create_rag_retrieval_tool(bad_name)

    @pytest.mark.parametrize(
        "good_name",
        [
            "valid-collection",
            "valid_collection",
            "ValidCollection123",
            "gcse-english-tutor",
            "my_collection_v2",
        ],
    )
    def test_valid_collection_names_accepted(self, good_name: str) -> None:
        """AC-012: Valid collection names (alphanumeric, hyphens, underscores) pass."""
        tool_fn = create_rag_retrieval_tool(good_name)
        assert isinstance(tool_fn, BaseTool)

    def test_empty_collection_name_rejected(self) -> None:
        """AC-012: Empty collection name is rejected."""
        with pytest.raises(ValueError):
            create_rag_retrieval_tool("")


# ===========================================================================
# AC-013: All errors as descriptive strings (D7)
# ===========================================================================


@pytest.mark.smoke
class TestD7ErrorStrings:
    """Verify all error paths return descriptive strings, never raise."""

    @patch("tools.rag_retrieval.chromadb")
    def test_query_exception_returns_string(self, mock_chromadb: MagicMock) -> None:
        """AC-013: Exception during query returns error string."""
        collection = MagicMock()
        collection.query.side_effect = RuntimeError("Query failed internally")
        client = _make_mock_client(collection)
        mock_chromadb.PersistentClient.return_value = client

        tool_fn = create_rag_retrieval_tool("test-collection")
        result = tool_fn.invoke({"query": "test"})

        assert isinstance(result, str)
        assert "error" in result.lower()

    @patch("tools.rag_retrieval.chromadb")
    def test_error_messages_are_descriptive(self, mock_chromadb: MagicMock) -> None:
        """AC-013: Error strings contain useful information."""
        mock_chromadb.PersistentClient.side_effect = OSError("Disk full")

        tool_fn = create_rag_retrieval_tool("test-collection")
        result = tool_fn.invoke({"query": "test"})

        # Should contain some context about what went wrong
        assert len(result) > 10


# ===========================================================================
# Lazy import pattern verification
# ===========================================================================


class TestLazyImportPattern:
    """Verify chromadb is not imported at module level."""

    def test_no_toplevel_chromadb_import_in_rag_retrieval(self) -> None:
        """Source must not contain top-level chromadb imports."""
        import tools.rag_retrieval as mod

        source_path = mod.__file__
        with open(source_path) as f:
            source = f.read()

        tree = ast.parse(source)
        for node in ast.iter_child_nodes(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert not alias.name.startswith("chromadb"), (
                        f"Found top-level 'import {alias.name}' — "
                        f"chromadb must use lazy-import pattern"
                    )
            elif isinstance(node, ast.ImportFrom):
                if node.module and node.module.startswith("chromadb"):
                    pytest.fail(
                        f"Found top-level 'from {node.module} import ...' — "
                        f"chromadb must use lazy-import pattern"
                    )
