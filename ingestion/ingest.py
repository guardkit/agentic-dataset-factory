"""Ingest orchestrator and CLI entry point for the ingestion pipeline.

Orchestrates the full ingestion pipeline: GOAL.md reading → Docling processing
→ text chunking → ChromaDB indexing.  The CLI wraps the orchestrator with
argparse for command-line usage.

Public API:
    - ``ingest_domain()`` — run the full pipeline for a domain
    - ``build_parser()`` — create the argparse ArgumentParser
    - ``cli_main()`` — CLI entry point (parse args, call orchestrator, handle errors)

Usage::

    python -m ingestion.ingest --domain gcse-english-tutor [--chunk-size 512] [--overlap 64] [--force]

Exit codes:
    0 — success
    1 — domain not found
    2 — GOAL.md / Source Documents invalid
    3 — Docling failure (all documents failed)
    4 — ChromaDB failure
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
from pathlib import Path

from ingestion.chromadb_indexer import ChromaDBIndexer
from ingestion.chunker import chunk_text
from ingestion.docling_processor import ExtractedDocument, process_document
from ingestion.errors import (
    CollectionExistsError,
    DoclingError,
    DomainNotFoundError,
    GoalValidationError,
    IndexingError,
)
from ingestion.goal_reader import read_source_documents, resolve_source_files
from ingestion.models import Chunk, IngestResult

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Default configuration
# ---------------------------------------------------------------------------

_DEFAULT_PERSIST_DIR = "./chroma_data"
_DEFAULT_DOMAINS_ROOT = Path("domains")


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------


def ingest_domain(
    domain_name: str,
    chunk_size: int = 512,
    overlap: int = 64,
    force: bool = False,
    domains_root: Path | None = None,
    persist_directory: str = _DEFAULT_PERSIST_DIR,
) -> IngestResult:
    """Run the full ingestion pipeline for a domain.

    Processing flow:
    1. Load GOAL.md → parse Source Documents table
    2. For each source document matching file patterns:
       a. Determine Docling mode (standard | vlm)
       b. Process through Docling → extract text
       c. Chunk via chunker.py (fixed-size with overlap)
       d. Assign chunk metadata (source_file, page_number, chunk_index)
    3. Create/replace ChromaDB collection named "{domain_name}"
    4. Index all chunks with embeddings + metadata
    5. Log summary: total documents, total chunks, collection name

    Args:
        domain_name: Name of domain directory under domains/.
        chunk_size: Chunk size in characters (default 512).
        overlap: Chunk overlap in characters (default 64).
        force: Re-ingest even if collection exists.
        domains_root: Root directory containing domain folders.
            Defaults to ``domains/`` relative to CWD.
        persist_directory: ChromaDB persist directory.
            Defaults to ``./chroma_data``.

    Returns:
        IngestResult with statistics.

    Raises:
        DomainNotFoundError: Domain directory doesn't exist.
        GoalValidationError: GOAL.md missing or Source Documents invalid.
        IndexingError: ChromaDB failure.
    """
    start_time = time.monotonic()

    root = Path(domains_root) if domains_root is not None else _DEFAULT_DOMAINS_ROOT
    domain_path = root / domain_name

    logger.info(
        "Ingestion started for domain '%s' (chunk_size=%d, overlap=%d, force=%s)",
        domain_name,
        chunk_size,
        overlap,
        force,
    )

    # Step 1: Read GOAL.md and resolve source files
    source_documents = read_source_documents(domain_path)
    resolved_files = resolve_source_files(domain_path, source_documents)

    logger.info(
        "Resolved %d source files for domain '%s'",
        len(resolved_files),
        domain_name,
    )

    # Step 2: Process each document through Docling and chunk
    all_chunks: list[Chunk] = []
    documents_processed = 0

    for file_path, mode in resolved_files:
        try:
            logger.info("Processing '%s' (mode=%s)", file_path.name, mode)
            extracted: ExtractedDocument = process_document(file_path, mode=mode)

            # Chunk each page and collect results
            for page in extracted.pages:
                source_metadata = {
                    "source_file": file_path.name,
                    "page_number": page.page_number,
                    "docling_mode": mode,
                    "domain": domain_name,
                }
                page_chunks = chunk_text(
                    text=page.text,
                    chunk_size=chunk_size,
                    overlap=overlap,
                    source_metadata=source_metadata,
                )
                all_chunks.extend(page_chunks)

            documents_processed += 1
            logger.info(
                "Processed '%s': %d pages extracted",
                file_path.name,
                len(extracted.pages),
            )

        except (DoclingError, FileNotFoundError) as exc:
            logger.warning(
                "Skipping '%s': %s",
                file_path.name,
                exc,
            )
            continue

    logger.info(
        "Document processing complete: %d/%d documents, %d chunks generated",
        documents_processed,
        len(resolved_files),
        len(all_chunks),
    )

    # Step 3: Create/replace ChromaDB collection and index chunks
    indexer = ChromaDBIndexer(persist_directory=persist_directory)
    collection = indexer.create_or_replace_collection(domain_name, force=force)

    chunks_indexed = indexer.index_chunks(collection, all_chunks)

    elapsed = time.monotonic() - start_time

    result = IngestResult(
        domain=domain_name,
        collection_name=domain_name,
        documents_processed=documents_processed,
        chunks_created=chunks_indexed,
        elapsed_seconds=round(elapsed, 2),
    )

    logger.info(
        "Ingestion complete for domain '%s': %d documents, %d chunks, %.2fs elapsed",
        result.domain,
        result.documents_processed,
        result.chunks_created,
        result.elapsed_seconds,
    )

    return result


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    """Create the argparse parser for the ingest CLI.

    Returns:
        Configured ArgumentParser with --domain, --chunk-size, --overlap, --force.
    """
    parser = argparse.ArgumentParser(
        prog="python -m ingestion.ingest",
        description="Ingest domain source documents into ChromaDB.",
    )
    parser.add_argument(
        "--domain",
        required=True,
        help="Name of the domain directory under domains/",
    )
    parser.add_argument(
        "--chunk-size",
        type=int,
        default=512,
        help="Chunk size in characters (default: 512)",
    )
    parser.add_argument(
        "--overlap",
        type=int,
        default=64,
        help="Chunk overlap in characters (default: 64)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        default=False,
        help="Re-ingest even if collection already exists",
    )
    return parser


def cli_main(argv: list[str] | None = None) -> int:
    """CLI entry point: parse arguments, run orchestrator, handle errors.

    Args:
        argv: Command-line arguments (defaults to sys.argv[1:]).

    Returns:
        Exit code: 0=success, 1=domain not found, 2=GOAL.md invalid,
        3=Docling failure, 4=ChromaDB failure.
    """
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        result = ingest_domain(
            domain_name=args.domain,
            chunk_size=args.chunk_size,
            overlap=args.overlap,
            force=args.force,
        )

        # Print human-readable summary to stdout
        print(
            f"Ingestion complete for '{result.domain}':\n"
            f"  Collection: {result.collection_name}\n"
            f"  Documents processed: {result.documents_processed}\n"
            f"  Chunks created: {result.chunks_created}\n"
            f"  Elapsed: {result.elapsed_seconds:.2f}s"
        )
        return 0

    except DomainNotFoundError as exc:
        print(f"Error: Domain not found — {exc}", file=sys.stderr)
        return 1

    except GoalValidationError as exc:
        print(f"Error: GOAL.md validation failed — {exc}", file=sys.stderr)
        return 2

    except DoclingError as exc:
        print(f"Error: Docling processing failed — {exc}", file=sys.stderr)
        return 3

    except (IndexingError, CollectionExistsError) as exc:
        print(f"Error: ChromaDB indexing failed — {exc}", file=sys.stderr)
        return 4


def main() -> None:
    """Entry point for ``python -m ingestion.ingest``."""
    sys.exit(cli_main())


if __name__ == "__main__":
    main()
