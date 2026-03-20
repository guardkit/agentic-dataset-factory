"""Ingestion pipeline for processing source documents into ChromaDB.

Public API -- all models and error classes are importable directly from
this package:

    from ingestion import Chunk, IngestResult, SourceDocument
    from ingestion import IngestionError, DoclingError, IndexingError
"""

from ingestion.errors import (
    DoclingError,
    DomainNotFoundError,
    GoalValidationError,
    IndexingError,
    IngestionError,
)
from ingestion.models import (
    Chunk,
    IngestResult,
    SourceDocument,
)

__all__ = [
    # Models
    "Chunk",
    "IngestResult",
    "SourceDocument",
    # Errors
    "IngestionError",
    "DomainNotFoundError",
    "GoalValidationError",
    "DoclingError",
    "IndexingError",
]
