"""GOAL.md Source Documents reader for the ingestion pipeline.

Reads the Source Documents section from a domain's GOAL.md file and resolves
file patterns against the ``sources/`` directory.  This module bridges the
GOAL.md parser (domain_config) with the ingestion pipeline.

Public API:
    - ``read_source_documents(domain_path)`` -- parse Source Documents from GOAL.md
    - ``resolve_source_files(domain_path, source_documents)`` -- expand glob patterns

Future migration: once FEAT-5606 completes, ``read_source_documents`` can
delegate to ``domain_config.parse_goal_md`` instead of parsing the table
inline.
"""

from __future__ import annotations

import logging
import os
import re
from pathlib import Path

from ingestion.errors import DomainNotFoundError, GoalValidationError
from ingestion.models import SourceDocument

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

_SEPARATOR_RE = re.compile(r"^\|?\s*:?-+:?\s*(\|\s*:?-+:?\s*)*\|?\s*$")
"""Matches markdown table separator rows like ``|---|---|`` or ``| :---: | :---: |``."""

_PATH_TRAVERSAL_RE = re.compile(r"(^|[\\/])\.\.($|[\\/])")
"""Matches ``../`` or ``..\\`` path traversal sequences."""


def _parse_row(line: str) -> list[str]:
    """Split a markdown table row on ``|`` and strip each cell."""
    stripped = line.strip()
    if not stripped:
        return []
    cells = stripped.split("|")
    if cells and cells[0].strip() == "":
        cells = cells[1:]
    if cells and cells[-1].strip() == "":
        cells = cells[:-1]
    return [c.strip() for c in cells]


def _is_separator(line: str) -> bool:
    """Return True if *line* is a markdown table separator row."""
    return bool(_SEPARATOR_RE.match(line.strip()))


def _has_path_traversal(filename: str) -> bool:
    """Return True if *filename* contains path traversal patterns."""
    return bool(_PATH_TRAVERSAL_RE.search(filename))


def _extract_source_documents_section(goal_text: str) -> str:
    """Extract the Source Documents section body from raw GOAL.md text.

    Uses a regex to find ``## Source Documents`` and capture everything
    up to the next ``## `` heading or end of file.

    Raises:
        GoalValidationError: If the section is missing.
    """
    pattern = r"^##\s+Source Documents\s*$(.*?)(?=^##\s|\Z)"
    match = re.search(pattern, goal_text, re.MULTILINE | re.DOTALL)
    if match is None:
        raise GoalValidationError("GOAL.md is missing the '## Source Documents' section")
    return match.group(1).strip()


def _parse_source_documents_table(section_body: str) -> list[SourceDocument]:
    """Parse a markdown table from the Source Documents section body.

    Expects a table with at least ``File Pattern`` and ``Mode`` columns.

    Returns:
        List of validated ``SourceDocument`` instances.

    Raises:
        GoalValidationError: If the table is malformed, missing required
            columns, or contains no valid data rows.
    """
    lines = [ln for ln in section_body.splitlines() if ln.strip()]

    if not lines:
        raise GoalValidationError("Source Documents section is empty -- expected a markdown table")

    # --- Parse header row ---
    header_cells = _parse_row(lines[0])
    if not header_cells:
        raise GoalValidationError("Source Documents section has no table header row")

    # Build column_map: header text -> column index
    column_map: dict[str, str] = {
        "File Pattern": "file_pattern",
        "Mode": "mode",
        "Notes": "notes",
    }
    col_index_to_field: dict[int, str] = {}
    for idx, header in enumerate(header_cells):
        if header in column_map:
            col_index_to_field[idx] = column_map[header]

    # Validate required columns are present
    mapped_fields = set(col_index_to_field.values())
    if "file_pattern" not in mapped_fields or "mode" not in mapped_fields:
        raise GoalValidationError(
            "Source Documents table missing required columns: expected 'File Pattern' and 'Mode'"
        )

    # --- Parse data rows ---
    documents: list[SourceDocument] = []
    for line in lines[1:]:
        if _is_separator(line):
            continue
        cells = _parse_row(line)
        if not cells:
            continue

        kwargs: dict[str, str] = {}
        for col_idx, field_name in col_index_to_field.items():
            if col_idx < len(cells):
                kwargs[field_name] = cells[col_idx]
            else:
                kwargs[field_name] = ""

        try:
            doc = SourceDocument(**kwargs)
            documents.append(doc)
        except Exception as exc:
            raise GoalValidationError(f"Invalid Source Documents row: {exc}") from exc

    if not documents:
        raise GoalValidationError("Source Documents table contains no valid data rows")

    return documents


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def read_source_documents(domain_path: Path) -> list[SourceDocument]:
    """Read Source Documents from GOAL.md in the given domain directory.

    Args:
        domain_path: Path to domain directory (e.g., ``domains/gcse-english-tutor/``).

    Returns:
        List of ``SourceDocument`` objects from the Source Documents table.

    Raises:
        DomainNotFoundError: If *domain_path* does not exist.
        GoalValidationError: If GOAL.md is missing or Source Documents
            section is invalid.
    """
    domain_path = Path(domain_path)

    if not domain_path.is_dir():
        raise DomainNotFoundError(f"Domain directory not found: {domain_path}")

    goal_path = domain_path / "GOAL.md"
    if not goal_path.is_file():
        raise GoalValidationError(f"GOAL.md not found in domain directory: {domain_path}")

    goal_text = goal_path.read_text(encoding="utf-8")
    section_body = _extract_source_documents_section(goal_text)
    return _parse_source_documents_table(section_body)


def resolve_source_files(
    domain_path: Path,
    source_documents: list[SourceDocument],
) -> list[tuple[Path, str]]:
    """Resolve file patterns to actual file paths in the ``sources/`` directory.

    For each ``SourceDocument``, expands its ``file_pattern`` glob against
    ``domain_path/sources/`` and pairs each matched file with the document's
    ``mode``.

    Security: all resolved paths are verified to be within
    ``domain_path/sources/`` using ``os.path.realpath()`` prefix checking.
    Files whose names contain path traversal sequences (``../``, ``..\\``)
    are rejected and logged as errors.

    Args:
        domain_path: Path to domain directory.
        source_documents: Parsed ``SourceDocument`` list from GOAL.md.

    Returns:
        List of ``(absolute_path, mode)`` tuples for matched files.

    Raises:
        GoalValidationError: If no files match any patterns.
    """
    domain_path = Path(domain_path)
    sources_dir = domain_path / "sources"

    if not sources_dir.is_dir():
        raise GoalValidationError(f"Sources directory not found: {sources_dir}")

    # Canonical path of the sources directory for prefix checking.
    sources_real = os.path.realpath(sources_dir)

    resolved: list[tuple[Path, str]] = []
    seen: set[str] = set()

    for doc in source_documents:
        pattern = doc.file_pattern

        # Reject patterns that themselves contain path traversal
        if _has_path_traversal(pattern):
            logger.error("Rejecting file pattern with path traversal: %s", pattern)
            continue

        matched_files = sorted(sources_dir.glob(pattern))

        for file_path in matched_files:
            if not file_path.is_file():
                continue

            # Check filename for path traversal
            if _has_path_traversal(file_path.name):
                logger.error(
                    "Rejecting file with path traversal in name: %s",
                    file_path.name,
                )
                continue

            # Verify the resolved real path is within sources_dir
            file_real = os.path.realpath(file_path)
            if not file_real.startswith(sources_real + os.sep) and file_real != sources_real:
                logger.error(
                    "Rejecting file outside sources directory: %s (resolved to %s)",
                    file_path,
                    file_real,
                )
                continue

            # De-duplicate (a file may match multiple patterns)
            if file_real not in seen:
                seen.add(file_real)
                resolved.append((Path(file_real).resolve(), doc.mode))

    if not resolved:
        patterns = [d.file_pattern for d in source_documents]
        raise GoalValidationError(
            f"No source files found matching patterns {patterns} in {sources_dir}"
        )

    return resolved


__all__ = [
    "read_source_documents",
    "resolve_source_files",
]
