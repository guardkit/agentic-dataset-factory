"""Text chunking using LangChain's RecursiveCharacterTextSplitter.

Provides the ``chunk_text()`` function which splits extracted text into
fixed-size chunks with configurable overlap. Each chunk is returned as a
:class:`~ingestion.models.Chunk` dataclass with provenance metadata.

Typical usage::

    from ingestion.chunker import chunk_text

    chunks = chunk_text(
        text=extracted_text,
        chunk_size=512,
        overlap=64,
        source_metadata={"source_file": "doc.pdf", "domain": "gcse-english-tutor"},
    )
"""

from __future__ import annotations

import logging

from langchain_text_splitters import RecursiveCharacterTextSplitter

from ingestion.models import Chunk

logger = logging.getLogger(__name__)


def chunk_text(
    text: str,
    chunk_size: int = 512,
    overlap: int = 64,
    source_metadata: dict | None = None,
) -> list[Chunk]:
    """Split text into fixed-size chunks with overlap.

    Uses RecursiveCharacterTextSplitter from LangChain.

    Args:
        text: Extracted text from Docling.
        chunk_size: Target chunk size in characters (maps to the ``tokens``
            concept per ASSUM-001/002).
        overlap: Overlap between consecutive chunks in characters.
        source_metadata: Metadata to attach to each chunk. When provided,
            a **copy** is merged into each chunk's metadata dict so that
            mutations to one chunk's metadata do not affect others.

    Returns:
        List of Chunk objects with text and metadata. Empty list if
        *text* is empty or whitespace-only.

    Raises:
        ValueError: If *chunk_size* is not positive or *overlap* is negative
            or greater than or equal to *chunk_size*.
    """
    if not text or not text.strip():
        return []

    if chunk_size <= 0:
        msg = f"chunk_size must be positive, got {chunk_size}"
        raise ValueError(msg)

    if overlap < 0:
        msg = f"overlap must be non-negative, got {overlap}"
        raise ValueError(msg)

    if overlap >= chunk_size:
        msg = f"overlap ({overlap}) must be less than chunk_size ({chunk_size})"
        raise ValueError(msg)

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=overlap,
        length_function=len,
        strip_whitespace=True,
    )

    raw_chunks: list[str] = splitter.split_text(text)

    chunks: list[Chunk] = []
    for index, chunk_text_segment in enumerate(raw_chunks):
        metadata: dict = {}
        if source_metadata is not None:
            metadata.update(source_metadata)
        metadata["chunk_index"] = index
        chunks.append(Chunk(text=chunk_text_segment, metadata=metadata))

    logger.debug(
        "Chunked %d characters into %d chunks (chunk_size=%d, overlap=%d)",
        len(text),
        len(chunks),
        chunk_size,
        overlap,
    )

    return chunks


__all__ = ["chunk_text"]
