"""Ingestion pipeline for processing source documents into ChromaDB.

Public API -- all models and error classes are importable directly from
this package:

    from ingestion import Chunk, IngestResult, SourceDocument
    from ingestion import IngestionError, DoclingError, IndexingError
    from ingestion import chunk_text
    from ingestion import read_source_documents, resolve_source_files
    from ingestion import ChromaDBIndexer, CollectionExistsError
"""

from ingestion.chromadb_indexer import ChromaDBIndexer
from ingestion.chunker import chunk_text
from ingestion.errors import (
    CollectionExistsError,
    DoclingError,
    DomainNotFoundError,
    GoalValidationError,
    IndexingError,
    IngestionError,
)
from ingestion.goal_reader import read_source_documents, resolve_source_files
from ingestion.models import (
    Chunk,
    IngestResult,
    SourceDocument,
)

__all__ = [
    # Classes
    "ChromaDBIndexer",
    # Functions
    "chunk_text",
    "read_source_documents",
    "resolve_source_files",
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
    "CollectionExistsError",
]
