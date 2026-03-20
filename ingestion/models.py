"""Data models for the ingestion pipeline.

Defines the core data structures used across the ingestion pipeline:
- Chunk: a text fragment with provenance metadata
- IngestResult: summary statistics from a completed ingestion run
- SourceDocument: stub Pydantic model for file patterns (to be replaced
  by domain_config.models.SourceDocument once FEAT-5606 lands)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Dataclasses (match API contract style)
# ---------------------------------------------------------------------------


@dataclass
class Chunk:
    """A text chunk with provenance metadata.

    Attributes:
        text: The chunk text content.
        metadata: Provenance metadata dict with keys: source_file,
            page_number, chunk_index, docling_mode, domain.
    """

    text: str
    metadata: dict = field(default_factory=dict)


@dataclass
class IngestResult:
    """Summary statistics from a completed ingestion run.

    Matches the API contract fields from API-ingestion.md.

    Attributes:
        domain: Name of the domain that was ingested.
        collection_name: ChromaDB collection name.
        documents_processed: Number of source documents successfully processed.
        chunks_created: Total number of chunks indexed.
        elapsed_seconds: Wall-clock time for the ingestion run.
    """

    domain: str
    collection_name: str
    documents_processed: int
    chunks_created: int
    elapsed_seconds: float


# ---------------------------------------------------------------------------
# Pydantic stub (consistent with FEAT-5606 / domain_config pattern)
# ---------------------------------------------------------------------------


class SourceDocument(BaseModel):
    """A source document entry from the Source Documents table (stub).

    Defines a file pattern for Docling ingestion with the processing mode.
    This is a temporary stub. Once TASK-DC-001 (FEAT-5606) is implemented,
    replace with ``from domain_config.models import SourceDocument``.
    """

    file_pattern: str = Field(min_length=1)
    mode: Literal["standard", "vlm"]
    notes: str = ""


__all__ = [
    "Chunk",
    "IngestResult",
    "SourceDocument",
]
