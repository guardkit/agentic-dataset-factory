"""Factory and tool for RAG retrieval from ChromaDB collections.

Provides ``create_rag_retrieval_tool(collection_name)`` which returns a
LangChain ``@tool``-decorated function that queries a ChromaDB collection
for curriculum chunks relevant to a generation target.

**No top-level chromadb import.** The ``chromadb`` package is imported lazily
inside the tool closure on first invocation, following the project's
lazy-import pattern for optional dependencies.
"""

from __future__ import annotations

import logging
import re
from typing import Any, Callable

from langchain_core.tools import tool

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Collection name validation
# ---------------------------------------------------------------------------

_VALID_COLLECTION_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]*$")


def _validate_collection_name(name: str) -> None:
    """Validate that a collection name is safe and well-formed.

    Accepts only alphanumeric characters, hyphens, and underscores.
    Must start with an alphanumeric character and be non-empty.

    Args:
        name: The collection name to validate.

    Raises:
        ValueError: If the name is empty, or contains path traversal
            or other disallowed characters.
    """
    if not name:
        raise ValueError(
            "collection name must not be empty; "
            "provide a non-empty alphanumeric name"
        )
    if not _VALID_COLLECTION_NAME_RE.match(name):
        raise ValueError(
            f"collection name '{name}' contains disallowed characters; "
            f"only alphanumeric characters, hyphens, and underscores are allowed "
            f"(must start with alphanumeric)"
        )


# ---------------------------------------------------------------------------
# Chunk formatting
# ---------------------------------------------------------------------------


def _format_chunk(index: int, document: str, metadata: dict[str, Any] | None) -> str:
    """Format a single retrieved chunk with source metadata header.

    Args:
        index: 1-based chunk index.
        document: The chunk text content.
        metadata: Optional metadata dict with 'source' and 'page' keys.

    Returns:
        Formatted chunk string with header and content.
    """
    meta = metadata or {}
    source = meta.get("source", "unknown")
    page = meta.get("page", "?")
    return f"--- Chunk {index} (source: {source}, p.{page}) ---\n{document}\n"


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


# Lazy-import holder: chromadb is imported inside the closure, not at module level.
# This variable exists so that tests can patch `tools.rag_retrieval.chromadb`.
chromadb: Any = None


def create_rag_retrieval_tool(
    collection_name: str,
    persist_directory: str = "./chroma_data",
) -> Callable:
    """Create a LangChain tool that retrieves chunks from a ChromaDB collection.

    The collection name is bound at factory time; callers of the returned tool
    only need to supply a query string and optional ``n_results``.

    ChromaDB ``PersistentClient`` is lazily initialised on the first tool
    invocation and reused for all subsequent calls.

    Args:
        collection_name: Name of the ChromaDB collection to query.
            Must contain only alphanumeric characters, hyphens, and
            underscores. Path traversal characters are rejected.
        persist_directory: Path to the ChromaDB persistence directory.
            Defaults to ``"./chroma_data"`` to match the ingestion pipeline.

    Returns:
        A LangChain ``@tool``-decorated callable with signature
        ``(query: str, n_results: int = 5) -> str``.

    Raises:
        ValueError: If ``collection_name`` is empty or contains
            disallowed characters (path traversal, spaces, etc.).
    """
    _validate_collection_name(collection_name)

    # Nonlocal state for lazy client initialisation (AC-003, AC-004)
    client_holder: list[Any] = []  # mutable container for nonlocal assignment

    def _get_client() -> Any:
        """Return the ChromaDB PersistentClient, creating it on first call."""
        if not client_holder:
            global chromadb
            if chromadb is None:
                import chromadb as _chromadb

                chromadb = _chromadb
            client_holder.append(chromadb.PersistentClient(path=persist_directory))
        return client_holder[0]

    @tool
    def rag_retrieval(query: str, n_results: int = 5) -> str:
        """Retrieve curriculum chunks from ChromaDB relevant to the generation target.

        Args:
            query: Natural language query describing what content to retrieve.
                   e.g., "Macbeth Act 1 Scene 7 ambition soliloquy"
            n_results: Number of chunks to return (default 5, max 20)

        Returns:
            Formatted string of retrieved chunks with source metadata.
            On error: Returns error string describing the failure.
        """
        # --- AC-006: Validate n_results bounds ---
        if not isinstance(n_results, int) or n_results < 1:
            return (
                f"Error: n_results must be between 1 and 20 inclusive, "
                f"got {n_results}. Provide a value >= 1."
            )
        if n_results > 20:
            return (
                f"Error: n_results must be between 1 and 20 inclusive, "
                f"got {n_results}. Maximum 20 results supported."
            )

        try:
            db_client = _get_client()
        except Exception as exc:
            logger.warning("ChromaDB client init failed: %s", exc)
            return f"Error: ChromaDB unavailable — {exc}"

        try:
            db_collection = db_client.get_collection(name=collection_name)
        except Exception as exc:
            logger.warning("Collection '%s' not found: %s", collection_name, exc)
            return (
                f"Error: ChromaDB collection '{collection_name}' "
                f"not found — {exc}"
            )

        try:
            results = db_collection.query(
                query_texts=[query],
                n_results=n_results,
            )
        except Exception as exc:
            logger.warning("ChromaDB query failed: %s", exc)
            return f"Error: ChromaDB query failed — {exc}"

        # --- AC-008: Return whatever chunks are available ---
        documents = results.get("documents", [[]])[0]
        metadatas = results.get("metadatas", [[]])[0]

        if not documents:
            return (
                f"No results found for query '{query}' "
                f"in collection '{collection_name}'."
            )

        # --- AC-005: Format chunks with source metadata ---
        formatted_chunks: list[str] = []
        for i, doc in enumerate(documents, start=1):
            meta = metadatas[i - 1] if i - 1 < len(metadatas) else None
            formatted_chunks.append(_format_chunk(i, doc, meta))

        return "\n".join(formatted_chunks)

    return rag_retrieval


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

__all__ = ["create_rag_retrieval_tool"]
