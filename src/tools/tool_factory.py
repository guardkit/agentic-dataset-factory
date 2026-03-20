"""Factory functions for assembling Player and Coach tool lists.

Provides ``create_player_tools()`` and ``create_coach_tools()`` which return
the correct tool lists for the adversarial cooperation architecture:

- **Player** receives ``[rag_retrieval, write_output]`` (exactly 2 tools).
- **Coach** receives ``[]`` (always empty) — enforcing the D5 evaluation-only
  role constraint via tool access asymmetry.

Both factory functions validate their inputs at creation time, following the
fail-fast principle. Invalid configuration (empty collection name, invalid
output directory) raises ``ValueError`` before any tool is constructed.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Callable

from tools.rag_retrieval import create_rag_retrieval_tool
from tools.write_output import create_write_output_tool

if TYPE_CHECKING:
    from domain_config.models import MetadataField


# ---------------------------------------------------------------------------
# Input validation helpers
# ---------------------------------------------------------------------------


def _validate_collection_name(collection_name: str) -> None:
    """Validate that collection_name is a non-empty string.

    Args:
        collection_name: ChromaDB collection name to validate.

    Raises:
        ValueError: If collection_name is empty or not a string.
    """
    if not isinstance(collection_name, str) or not collection_name.strip():
        raise ValueError(
            "collection_name must be a non-empty string; provide a valid ChromaDB collection name"
        )


def _validate_output_dir(output_dir: Path) -> None:
    """Validate that output_dir is a valid, writable directory path.

    The directory does not need to exist yet (it will be created on first
    write), but the path must be a valid ``Path`` instance and must not
    resolve to an empty string.

    Args:
        output_dir: Output directory path to validate.

    Raises:
        ValueError: If output_dir is not a Path, resolves to empty string,
            or contains null bytes.
    """
    if not isinstance(output_dir, Path):
        raise ValueError(f"output_dir must be a Path instance, got {type(output_dir).__name__}")

    # Reject empty or whitespace-only paths
    path_str = str(output_dir)
    if not path_str or not path_str.strip():
        raise ValueError("output_dir must not be empty; provide a valid directory path")

    # Reject null bytes (security)
    if "\x00" in path_str:
        raise ValueError("output_dir must not contain null bytes")

    # Reject paths that are clearly not directories (e.g., empty Path(""))
    if output_dir == Path(""):
        raise ValueError("output_dir must not be empty; provide a valid directory path")


def _validate_metadata_schema(metadata_schema: list[MetadataField]) -> None:
    """Validate that metadata_schema is a non-None list.

    Args:
        metadata_schema: List of MetadataField definitions.

    Raises:
        ValueError: If metadata_schema is not a list.
    """
    if not isinstance(metadata_schema, list):
        raise ValueError(f"metadata_schema must be a list, got {type(metadata_schema).__name__}")


# ---------------------------------------------------------------------------
# Player tool factory
# ---------------------------------------------------------------------------


def create_player_tools(
    collection_name: str,
    output_dir: Path,
    metadata_schema: list[MetadataField],
) -> list[Callable]:
    """Create the tool list for the Player agent.

    Returns exactly 2 tools: ``rag_retrieval`` and ``write_output``, each
    bound to the provided configuration. The Player uses these tools to
    retrieve curriculum context and persist validated training examples.

    Args:
        collection_name: ChromaDB collection name for RAG retrieval.
            Must be non-empty; passed to ``create_rag_retrieval_tool``.
        output_dir: Root output directory for training example files.
            Passed to ``create_write_output_tool``.
        metadata_schema: List of :class:`MetadataField` definitions from
            GOAL.md. Passed to ``create_write_output_tool`` for validation.

    Returns:
        A list of exactly 2 LangChain ``@tool``-decorated callables:
        ``[rag_retrieval, write_output]``.

    Raises:
        ValueError: If any input fails validation (empty collection name,
            invalid output directory path, non-list metadata schema).
    """
    # Validate all inputs before creating any tools (fail-fast)
    _validate_collection_name(collection_name)
    _validate_output_dir(output_dir)
    _validate_metadata_schema(metadata_schema)

    rag_tool = create_rag_retrieval_tool(collection_name)
    write_tool = create_write_output_tool(output_dir, metadata_schema)

    return [rag_tool, write_tool]


# ---------------------------------------------------------------------------
# Coach tool factory
# ---------------------------------------------------------------------------


def create_coach_tools() -> list[Callable]:
    """Create the tool list for the Coach agent.

    Always returns an empty list. The Coach evaluates Player output via
    structured JSON feedback and must never have access to ``rag_retrieval``
    or ``write_output`` — this enforces the D5 evaluation-only role
    constraint through tool access asymmetry.

    Returns:
        An empty list ``[]``.
    """
    return []


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

__all__ = [
    "create_player_tools",
    "create_coach_tools",
]
