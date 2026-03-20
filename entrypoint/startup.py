"""Entrypoint startup — domain resolution and ChromaDB readiness check.

Implements startup steps 3-6 from the API-entrypoint contract:
- Step 3: Set LANGSMITH_PROJECT env var, warn if tracing without API key
- Step 4: Resolve domain directory path under ``domains/``
- Step 5: Validate GOAL.md exists within the domain directory
- Step 6: Verify ChromaDB collection contains indexed chunks

References:
    - ``docs/design/contracts/API-entrypoint.md`` (Startup Sequence steps 3-6)
    - ``features/entrypoint/entrypoint.feature`` (BDD scenarios)
    - ASSUM-004: LangSmith tracing non-blocking
    - DDR-003: Collection naming matches domain directory name
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from config.models import AgentConfig

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class DomainNotFoundError(Exception):
    """Domain directory does not exist under ``domains/``.

    Raised when the specified domain directory cannot be found at
    ``domains/{domain}/`` relative to the project root.

    Attributes:
        domain: The domain name that was not found.
    """

    def __init__(self, domain: str) -> None:
        self.domain = domain
        super().__init__(
            f"Domain directory not found: domains/{domain}/ — "
            f"ensure the domain '{domain}' exists under the domains/ directory"
        )


# ---------------------------------------------------------------------------
# Step 3: LangSmith configuration
# ---------------------------------------------------------------------------


def configure_langsmith(config: AgentConfig) -> None:
    """Set LANGSMITH_PROJECT env var and warn if tracing lacks an API key.

    Sets ``LANGSMITH_PROJECT`` to ``"adf-{config.domain}"``.  If
    ``LANGSMITH_TRACING`` is ``"true"`` but ``LANGSMITH_API_KEY`` is not
    set, logs a warning without blocking startup (ASSUM-004).

    Args:
        config: Validated agent configuration with a ``domain`` attribute.
    """
    os.environ["LANGSMITH_PROJECT"] = f"adf-{config.domain}"

    tracing_enabled = os.environ.get("LANGSMITH_TRACING", "").lower() == "true"
    api_key_present = bool(os.environ.get("LANGSMITH_API_KEY", ""))

    if tracing_enabled and not api_key_present:
        logger.warning(
            "LANGSMITH_TRACING is enabled but LANGSMITH_API_KEY is not set. "
            "Traces will not be sent to LangSmith. Set LANGSMITH_API_KEY in "
            "your .env file to enable tracing."
        )


# ---------------------------------------------------------------------------
# Steps 4-5: Domain path resolution and GOAL.md validation
# ---------------------------------------------------------------------------


def resolve_domain(domain: str, *, project_root: Path = Path(".")) -> Path:
    """Resolve and validate the domain directory path.

    Checks that ``domains/{domain}/`` exists and contains a ``GOAL.md``
    file.

    Args:
        domain: Domain directory name (e.g. ``"gcse-english-tutor"``).
        project_root: Project root directory.  Defaults to the current
            working directory.

    Returns:
        Resolved ``Path`` to the domain directory.

    Raises:
        DomainNotFoundError: If the domain directory does not exist.
        FileNotFoundError: If ``GOAL.md`` is missing from the domain
            directory.
    """
    domain_path = project_root / "domains" / domain

    if not domain_path.is_dir():
        raise DomainNotFoundError(domain)

    goal_path = domain_path / "GOAL.md"
    if not goal_path.is_file():
        raise FileNotFoundError(
            f"GOAL.md not found in domain directory: {goal_path} — "
            f"each domain must contain a GOAL.md file defining the "
            f"generation configuration"
        )

    return domain_path


# ---------------------------------------------------------------------------
# Step 6: ChromaDB collection readiness check
# ---------------------------------------------------------------------------


def verify_chromadb_collection(
    domain: str,
    *,
    client: object | None = None,
) -> object:
    """Verify that a ChromaDB collection exists and contains chunks.

    Connects to ChromaDB (via the provided *client* or by creating an
    embedded ``PersistentClient``), retrieves the collection named after
    the domain (DDR-003), and checks it has at least one indexed chunk.

    Args:
        domain: Domain name used as the ChromaDB collection name.
        client: Optional pre-initialised ChromaDB client.  When ``None``,
            a ``chromadb.PersistentClient`` is created with the default
            ``"./chroma_data"`` persist directory.

    Returns:
        The ChromaDB ``Collection`` object.

    Raises:
        ConnectionError: If the ChromaDB client cannot connect or the
            collection does not exist.
        RuntimeError: If the collection exists but contains zero chunks,
            with an actionable message suggesting the ingestion command.
    """
    if client is None:
        try:
            import chromadb

            client = chromadb.PersistentClient(path="./chroma_data")
        except Exception as exc:
            raise ConnectionError(
                f"ChromaDB client initialisation failed: {exc}. "
                f"Ensure ChromaDB is installed and the chroma_data directory "
                f"is accessible."
            ) from exc

    try:
        collection = client.get_collection(name=domain)  # type: ignore[union-attr]
    except Exception as exc:
        raise ConnectionError(
            f"ChromaDB collection '{domain}' not available: {exc}. "
            f"Run: python -m ingestion.ingest --domain {domain}"
        ) from exc

    chunk_count = collection.count()
    if chunk_count == 0:
        raise RuntimeError(
            f"No chunks found for '{domain}'. "
            f"Run: python -m ingestion.ingest --domain {domain}"
        )

    return collection


__all__ = [
    "DomainNotFoundError",
    "configure_langsmith",
    "resolve_domain",
    "verify_chromadb_collection",
]
