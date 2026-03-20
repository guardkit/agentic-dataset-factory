"""Error hierarchy for the ingestion pipeline.

Defines a structured exception hierarchy for all ingestion failure modes:
- IngestionError: base class for all ingestion pipeline failures
- DomainNotFoundError: domain directory does not exist
- GoalValidationError: GOAL.md missing or Source Documents section invalid
- DoclingError: Docling processing failure for a specific document
- IndexingError: ChromaDB indexing failure
- CollectionExistsError: ChromaDB collection already exists when force=False
"""

from __future__ import annotations


class IngestionError(Exception):
    """Base error for ingestion pipeline failures.

    All ingestion-specific exceptions inherit from this class so callers
    can catch ``IngestionError`` to handle any pipeline failure generically.
    """


class DomainNotFoundError(IngestionError):
    """Domain directory does not exist.

    Raised when the specified domain directory cannot be found under the
    ``domains/`` tree.
    """


class GoalValidationError(IngestionError):
    """GOAL.md missing or Source Documents section invalid.

    Raised when a domain's GOAL.md file is absent or when its Source
    Documents section cannot be parsed or fails validation.
    """


class DoclingError(IngestionError):
    """Docling processing failure for a specific document.

    Raised when Docling fails to extract text from a source document.
    """


class IndexingError(IngestionError):
    """ChromaDB indexing failure.

    Raised when chunk indexing into ChromaDB fails due to connection
    errors or other ChromaDB issues.
    """


class CollectionExistsError(IngestionError):
    """ChromaDB collection already exists when force=False.

    Raised when ``create_or_replace_collection()`` is called with
    ``force=False`` but the target collection already exists.
    """


__all__ = [
    "IngestionError",
    "DomainNotFoundError",
    "GoalValidationError",
    "DoclingError",
    "IndexingError",
    "CollectionExistsError",
]
