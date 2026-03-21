"""Parser for GOAL.md domain configuration files.

Provides utilities for parsing and validating GOAL.md sections used by the
generation pipeline. Each domain directory contains a GOAL.md with 9 required
sections that configure the Player-Coach adversarial cooperation loop.

References:
    - docs/design/contracts/API-domain-config.md — section format specifications
    - docs/research/gcse-tutor-training-data-format.md — canonical content source
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


class GoalParseError(Exception):
    """Raised when GOAL.md parsing fails."""

    def __init__(self, section: str, message: str) -> None:
        self.section = section
        super().__init__(f"Section '{section}': {message}")


@dataclass
class SourceDocument:
    """A single source document entry from the Source Documents table."""

    file_pattern: str
    mode: str
    notes: str = ""


@dataclass
class GenerationTarget:
    """A single generation target entry from the Generation Targets table."""

    category: str
    type: str
    count: int


@dataclass
class GoalSections:
    """Parsed sections from a GOAL.md file."""

    raw_sections: dict[str, str] = field(default_factory=dict)

    @property
    def goal(self) -> str:
        """Return the Goal section content, stripping HTML comments."""
        return self._strip_comments(self.raw_sections.get("Goal", ""))

    @property
    def system_prompt(self) -> str:
        """Return the System Prompt section content, stripping HTML comments."""
        return self._strip_comments(self.raw_sections.get("System Prompt", ""))

    @property
    def generation_guidelines(self) -> str:
        """Return the Generation Guidelines section content, stripping HTML comments."""
        return self._strip_comments(
            self.raw_sections.get("Generation Guidelines", "")
        )

    @staticmethod
    def _strip_comments(text: str) -> str:
        """Remove HTML comments from markdown text."""
        lines = [
            line for line in text.splitlines()
            if not line.strip().startswith("<!--")
            and not line.strip().endswith("-->")
        ]
        return "\n".join(lines).strip()


def parse_sections(content: str) -> dict[str, str]:
    """Parse markdown content into sections keyed by level-2 heading name.

    Args:
        content: Raw markdown text.

    Returns:
        Dictionary mapping heading names to their body text.

    Raises:
        GoalParseError: If no level-2 headings are found.
    """
    result: dict[str, str] = {}
    current_heading: str | None = None
    current_lines: list[str] = []

    for line in content.splitlines():
        stripped = line.strip()
        if stripped.startswith("## "):
            if current_heading is not None:
                result[current_heading] = "\n".join(current_lines)
            current_heading = stripped[3:].strip()
            current_lines = []
        elif current_heading is not None:
            current_lines.append(line)

    if current_heading is not None:
        result[current_heading] = "\n".join(current_lines)

    if not result:
        raise GoalParseError("(root)", "No level-2 headings found in content")

    return result


def parse_markdown_table(
    section_content: str,
    *,
    skip_header: bool = True,
) -> list[list[str]]:
    """Parse a markdown table into a list of rows, each row a list of cell values.

    Args:
        section_content: Markdown text containing a pipe-delimited table.
        skip_header: If True, skip the header row and separator row.

    Returns:
        List of data rows, each row is a list of stripped cell strings.
    """
    table_lines = [
        line.strip() for line in section_content.splitlines()
        if line.strip().startswith("|")
    ]

    if not table_lines:
        return []

    rows: list[list[str]] = []
    header_seen = False
    separator_seen = False

    for line in table_lines:
        cells = [cell.strip() for cell in line.split("|") if cell.strip()]

        if not cells:
            continue

        if skip_header and not header_seen:
            header_seen = True
            continue

        if skip_header and not separator_seen:
            # Check if this is a separator row (contains ---)
            if all(re.match(r"^-+$", cell.strip()) for cell in cells):
                separator_seen = True
                continue
            separator_seen = True  # No separator found, treat as data

        rows.append(cells)

    return rows


def parse_source_documents(section_content: str) -> list[SourceDocument]:
    """Parse the Source Documents section into structured entries.

    Args:
        section_content: Content of the Source Documents section.

    Returns:
        List of SourceDocument entries.

    Raises:
        GoalParseError: If a mode value is not 'standard' or 'vlm'.
    """
    valid_modes = {"standard", "vlm"}
    rows = parse_markdown_table(section_content)
    documents: list[SourceDocument] = []

    for row in rows:
        if len(row) < 2:
            continue

        file_pattern = row[0]
        mode = row[1]
        notes = row[2] if len(row) >= 3 else ""

        if mode not in valid_modes:
            raise GoalParseError(
                "Source Documents",
                f"Invalid mode '{mode}'. Must be 'standard' or 'vlm'.",
            )

        documents.append(SourceDocument(
            file_pattern=file_pattern,
            mode=mode,
            notes=notes,
        ))

    return documents


def validate_file_patterns(documents: list[SourceDocument]) -> None:
    """Validate that source document file patterns are safe.

    Checks that patterns do not contain path traversal (..) or absolute paths.

    Args:
        documents: List of SourceDocument entries to validate.

    Raises:
        GoalParseError: If a file pattern is unsafe.
    """
    for doc in documents:
        if ".." in doc.file_pattern:
            raise GoalParseError(
                "Source Documents",
                f"File pattern '{doc.file_pattern}' contains '..' path traversal.",
            )
        if doc.file_pattern.startswith("/"):
            raise GoalParseError(
                "Source Documents",
                f"File pattern '{doc.file_pattern}' is an absolute path.",
            )


def parse_generation_targets(section_content: str) -> list[GenerationTarget]:
    """Parse the Generation Targets section into structured entries.

    Args:
        section_content: Content of the Generation Targets section.

    Returns:
        List of GenerationTarget entries.

    Raises:
        GoalParseError: If a type value is invalid or count is not an integer.
    """
    valid_types = {"reasoning", "direct"}
    rows = parse_markdown_table(section_content)
    targets: list[GenerationTarget] = []

    for row in rows:
        if len(row) < 3:
            continue

        category = row[0]
        type_val = row[1]
        count_str = row[2]

        try:
            count = int(count_str)
        except ValueError:
            continue  # Skip non-numeric rows (e.g. total summary)

        if type_val not in valid_types:
            raise GoalParseError(
                "Generation Targets",
                f"Invalid type '{type_val}'. Must be 'reasoning' or 'direct'.",
            )

        targets.append(GenerationTarget(
            category=category,
            type=type_val,
            count=count,
        ))

    return targets


def validate_generation_targets(
    targets: list[GenerationTarget],
    *,
    expected_total: int = 1000,
    min_reasoning_ratio: float = 0.75,
) -> None:
    """Validate generation targets meet the required constraints.

    Args:
        targets: List of GenerationTarget entries.
        expected_total: Expected total count (default 1000).
        min_reasoning_ratio: Minimum ratio of reasoning examples (default 0.75).

    Raises:
        GoalParseError: If validation fails.
    """
    total = sum(t.count for t in targets)
    if total != expected_total:
        raise GoalParseError(
            "Generation Targets",
            f"Total count is {total}, expected exactly {expected_total}.",
        )

    reasoning_count = sum(t.count for t in targets if t.type == "reasoning")
    if total > 0:
        ratio = reasoning_count / total
        if ratio < min_reasoning_ratio:
            raise GoalParseError(
                "Generation Targets",
                f"Reasoning ratio is {ratio:.1%}, "
                f"expected >= {min_reasoning_ratio:.0%}.",
            )


def validate_section_content(
    section_name: str,
    content: str,
    *,
    min_length: int = 100,
    required_terms: list[str] | None = None,
) -> None:
    """Validate that a section's content meets minimum requirements.

    Args:
        section_name: Name of the section being validated.
        content: Stripped section content.
        min_length: Minimum character length required.
        required_terms: List of terms that must appear (case-insensitive).

    Raises:
        GoalParseError: If validation fails.
    """
    if len(content) < min_length:
        raise GoalParseError(
            section_name,
            f"Content is only {len(content)} characters, minimum is {min_length}.",
        )

    if required_terms:
        content_lower = content.lower()
        for term in required_terms:
            if term.lower() not in content_lower:
                raise GoalParseError(
                    section_name,
                    f"Required term '{term}' not found in section content.",
                )


def load_goal_md(path: Path) -> GoalSections:
    """Load and parse a GOAL.md file into sections.

    Args:
        path: Path to the GOAL.md file.

    Returns:
        GoalSections with parsed content.

    Raises:
        FileNotFoundError: If the GOAL.md file does not exist.
        GoalParseError: If parsing fails.
    """
    if not path.is_file():
        raise FileNotFoundError(f"GOAL.md not found at {path}")

    content = path.read_text(encoding="utf-8")
    raw_sections = parse_sections(content)

    return GoalSections(raw_sections=raw_sections)
