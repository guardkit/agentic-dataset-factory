"""ChromaDB indexer with collection CRUD and batch upsert.

Manages ChromaDB collection lifecycle and batch chunk indexing. Uses
``PersistentClient`` per ADR-ARCH-004, with collection-per-domain naming,
force replacement support, and configurable batch sizes.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import chromadb

from ingestion.errors import CollectionExistsError, IndexingError
from ingestion.models import Chunk

if TYPE_CHECKING:
    from chromadb.api.models.Collection import Collection

logger = logging.getLogger(__name__)


class ChromaDBIndexer:
    """Manages ChromaDB collection lifecycle and batch chunk indexing.

    Uses ``chromadb.PersistentClient`` for embedded, persistent storage
    per ADR-ARCH-004. Collections are named after domains and can be
    force-replaced for re-ingestion.

    Args:
        persist_directory: Filesystem path for ChromaDB storage.
            Defaults to ``./chroma_data``.

    Raises:
        IndexingError: If the ChromaDB client cannot be initialised.
    """

    def __init__(self, persist_directory: str = "./chroma_data") -> None:
        try:
            self._client = chromadb.PersistentClient(path=persist_directory)
        except Exception as exc:
            raise IndexingError(
                f"ChromaDB client initialisation failed: {exc}"
            ) from exc

    def collection_exists(self, collection_name: str) -> bool:
        """Check if a collection already exists.

        Args:
            collection_name: Name of the collection to check.

        Returns:
            True if the collection exists, False otherwise.
        """
        existing = [c.name for c in self._client.list_collections()]
        return collection_name in existing

    def create_or_replace_collection(
        self, collection_name: str, force: bool = False
    ) -> Collection:
        """Create a collection, optionally replacing an existing one.

        When *force* is ``True`` and the collection already exists, it is
        deleted and recreated. A warning is logged about potential concurrent
        access safety per ASSUM-004.

        Args:
            collection_name: Name for the ChromaDB collection (typically
                the domain name).
            force: If ``True``, delete an existing collection before
                recreating it. If ``False`` (default), raise
                ``CollectionExistsError`` when the collection already exists.

        Returns:
            The ChromaDB ``Collection`` object.

        Raises:
            CollectionExistsError: If the collection exists and *force*
                is ``False``.
            IndexingError: If ChromaDB is unavailable or the operation fails.
        """
        try:
            exists = self.collection_exists(collection_name)

            if exists and not force:
                raise CollectionExistsError(
                    f"Collection '{collection_name}' already exists. "
                    f"Use force=True to replace it."
                )

            if exists and force:
                logger.warning(
                    "Force-replacing collection '%s'. If a concurrent process "
                    "(e.g. generation pipeline) is reading this collection, "
                    "data may be temporarily unavailable (ASSUM-004).",
                    collection_name,
                )
                self._client.delete_collection(name=collection_name)

            return self._client.create_collection(name=collection_name)
        except (CollectionExistsError, IndexingError):
            raise
        except Exception as exc:
            raise IndexingError(
                f"Failed to create collection '{collection_name}': {exc}"
            ) from exc

    def index_chunks(
        self,
        collection: Collection,
        chunks: list[Chunk],
        batch_size: int = 500,
    ) -> int:
        """Index chunks into a collection with batch upsert.

        Processes chunks in batches of *batch_size*. If a batch fails
        (e.g. embedding error), the error is logged and that batch is
        skipped; remaining batches continue.

        Chunk IDs are deterministic: ``{domain}_{source_file}_{chunk_index}``.

        Args:
            collection: ChromaDB ``Collection`` to index into.
            chunks: List of ``Chunk`` objects with text and metadata.
            batch_size: Number of chunks per batch operation. Defaults to 500.

        Returns:
            Number of chunks successfully indexed.

        Raises:
            IndexingError: If a non-recoverable ChromaDB error occurs.
        """
        if not chunks:
            return 0

        indexed_count = 0

        for start in range(0, len(chunks), batch_size):
            batch = chunks[start : start + batch_size]

            ids = []
            documents = []
            metadatas = []

            for chunk in batch:
                domain = chunk.metadata.get("domain", "unknown")
                source_file = chunk.metadata.get("source_file", "unknown")
                chunk_index = chunk.metadata.get("chunk_index", 0)
                chunk_id = f"{domain}_{source_file}_{chunk_index}"

                ids.append(chunk_id)
                documents.append(chunk.text)
                metadatas.append(chunk.metadata)

            try:
                collection.add(
                    ids=ids,
                    documents=documents,
                    metadatas=metadatas,
                )
                indexed_count += len(batch)
            except Exception as exc:
                logger.warning(
                    "Failed to index batch of %d chunks (start=%d) into "
                    "collection '%s': %s. Skipping batch.",
                    len(batch),
                    start,
                    collection.name,
                    exc,
                )

        return indexed_count
