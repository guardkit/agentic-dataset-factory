"""Structural smoke tests for GOAL.md — TASK-GG-005.

Lightweight tests that validate the structural integrity of the GCSE English
GOAL.md file *without* depending on the ``domain_config`` parser module or
``src.goal_parser``.  They use only simple string matching, regex, and the
standard library so they can run before any parser is implemented.

Tests cover the contract expectations from
``docs/design/contracts/API-domain-config.md``:

1.  All 9 required sections present
2.  Source Documents table format and no path-traversal patterns
3.  Generation Targets sum to 1,000 with ≥ 70 % reasoning
4.  System Prompt ≥ 100 characters
5.  Generation Guidelines ≥ 100 characters
6.  Output Schema is valid JSON with ``messages`` and ``metadata`` keys
7.  Evaluation Criteria weights sum to ~100 % (±1 %)
8.  Layer Routing contains ``behaviour`` and ``knowledge`` entries
9.  No path traversal in source document file patterns
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parent.parent
GOAL_MD_PATH = PROJECT_ROOT / "domains" / "gcse-english-tutor" / "GOAL.md"

REQUIRED_SECTIONS = [
    "Goal",
    "Source Documents",
    "System Prompt",
    "Generation Targets",
    "Generation Guidelines",
    "Evaluation Criteria",
    "Output Schema",
    "Metadata Schema",
    "Layer Routing",
]

# ---------------------------------------------------------------------------
# Helpers — intentionally parser-independent
# ---------------------------------------------------------------------------


def _read_goal_md() -> str:
    """Read the GOAL.md file content, failing fast if it's missing."""
    if not GOAL_MD_PATH.is_file():
        raise FileNotFoundError(f"GOAL.md not found at {GOAL_MD_PATH}")
    return GOAL_MD_PATH.read_text(encoding="utf-8")


def _extract_section(content: str, heading: str) -> str:
    """Extract body text under a ``## <heading>`` until the next ``##`` or EOF."""
    pattern = rf"^## {re.escape(heading)}\s*\n(.*?)(?=^## |\Z)"
    match = re.search(pattern, content, re.MULTILINE | re.DOTALL)
    if match is None:
        raise ValueError(f"Section '## {heading}' not found in GOAL.md")
    return match.group(1).strip()


def _parse_table_rows(section_text: str) -> list[list[str]]:
    """Return data rows from a markdown table as lists of stripped cell values.

    Skips the header and separator lines — returns only data rows.
    """
    table_lines = [
        line.strip()
        for line in section_text.splitlines()
        if line.strip().startswith("|")
    ]
    if len(table_lines) < 3:
        return []
    # Skip header (index 0) and separator (index 1)
    rows: list[list[str]] = []
    for line in table_lines[2:]:
        cells = [c.strip() for c in line.split("|")[1:-1]]
        rows.append(cells)
    return rows


def _parse_table_dicts(section_text: str) -> list[dict[str, str]]:
    """Return data rows from a markdown table as dicts keyed by header names."""
    table_lines = [
        line.strip()
        for line in section_text.splitlines()
        if line.strip().startswith("|")
    ]
    if len(table_lines) < 3:
        return []
    headers = [h.strip() for h in table_lines[0].split("|")[1:-1]]
    result: list[dict[str, str]] = []
    for line in table_lines[2:]:
        cells = [c.strip() for c in line.split("|")[1:-1]]
        result.append(dict(zip(headers, cells)))
    return result


def _extract_json_block(section_text: str) -> dict:
    """Extract and parse the first ``json`` fenced code block."""
    pattern = r"```json\s*\n(.*?)\n\s*```"
    match = re.search(pattern, section_text, re.DOTALL)
    if match is None:
        raise ValueError("No ```json code block found in section text")
    return json.loads(match.group(1))


# ---------------------------------------------------------------------------
# Fixture
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def goal_md_content() -> str:
    """Load GOAL.md once for the entire module."""
    return _read_goal_md()


# ---------------------------------------------------------------------------
# Section presence
# ---------------------------------------------------------------------------


@pytest.mark.smoke
class TestAllSectionsPresent:
    """Verify that all 9 required ``## Section`` headings exist."""

    @pytest.mark.parametrize("heading", REQUIRED_SECTIONS)
    def test_section_heading_present(self, goal_md_content: str, heading: str) -> None:
        """Each required section heading must appear in GOAL.md."""
        pattern = rf"^## {re.escape(heading)}\s*$"
        assert re.search(pattern, goal_md_content, re.MULTILINE), (
            f"Missing required section heading '## {heading}'"
        )


# ---------------------------------------------------------------------------
# Generation Targets
# ---------------------------------------------------------------------------


@pytest.mark.smoke
class TestGenerationTargets:
    """Validate Generation Targets table sums and reasoning split."""

    def test_targets_sum_to_2500(self, goal_md_content: str) -> None:
        """Generation target counts must sum to exactly 2,500."""
        section = _extract_section(goal_md_content, "Generation Targets")
        rows = _parse_table_rows(section)
        assert len(rows) > 0, "Generation Targets table has no data rows"

        total = 0
        for row in rows:
            # Count is column index 3 (Category|Type|Layer|Count|Grades)
            count_str = row[3].replace(",", "").strip()
            total += int(count_str)

        assert total == 2500, (
            f"Generation Targets sum to {total}, expected exactly 2,500"
        )

    def test_reasoning_percentage_gte_70(self, goal_md_content: str) -> None:
        """Reasoning examples must be >= 70 % of total."""
        section = _extract_section(goal_md_content, "Generation Targets")
        rows = _parse_table_rows(section)

        reasoning_count = 0
        total_count = 0
        for row in rows:
            type_val = row[1].strip().lower()
            count = int(row[3].replace(",", "").strip())
            total_count += count
            if type_val == "reasoning":
                reasoning_count += count

        assert total_count > 0, "No generation target rows found"
        ratio = reasoning_count / total_count
        assert ratio >= 0.70, (
            f"Reasoning ratio is {ratio:.1%}, expected >= 70%"
        )


# ---------------------------------------------------------------------------
# System Prompt
# ---------------------------------------------------------------------------


@pytest.mark.smoke
class TestSystemPrompt:
    """Validate System Prompt minimum length."""

    def test_system_prompt_min_100_chars(self, goal_md_content: str) -> None:
        """System Prompt section must be at least 100 characters."""
        section = _extract_section(goal_md_content, "System Prompt")
        assert len(section) >= 100, (
            f"System Prompt is {len(section)} characters, expected >= 100"
        )


# ---------------------------------------------------------------------------
# Generation Guidelines
# ---------------------------------------------------------------------------


@pytest.mark.smoke
class TestGenerationGuidelines:
    """Validate Generation Guidelines minimum length."""

    def test_generation_guidelines_min_100_chars(self, goal_md_content: str) -> None:
        """Generation Guidelines section must be at least 100 characters."""
        section = _extract_section(goal_md_content, "Generation Guidelines")
        assert len(section) >= 100, (
            f"Generation Guidelines is {len(section)} characters, expected >= 100"
        )


# ---------------------------------------------------------------------------
# Output Schema
# ---------------------------------------------------------------------------


@pytest.mark.smoke
class TestOutputSchema:
    """Validate Output Schema contains valid JSON with required keys."""

    def test_output_schema_valid_json(self, goal_md_content: str) -> None:
        """Output Schema must contain a valid JSON code block."""
        section = _extract_section(goal_md_content, "Output Schema")
        schema = _extract_json_block(section)
        assert isinstance(schema, dict), "Output Schema JSON root must be an object"

    def test_output_schema_has_messages_key(self, goal_md_content: str) -> None:
        """Output Schema JSON must have a ``messages`` top-level key."""
        section = _extract_section(goal_md_content, "Output Schema")
        schema = _extract_json_block(section)
        assert "messages" in schema, "Missing 'messages' key in Output Schema JSON"

    def test_output_schema_has_metadata_key(self, goal_md_content: str) -> None:
        """Output Schema JSON must have a ``metadata`` top-level key."""
        section = _extract_section(goal_md_content, "Output Schema")
        schema = _extract_json_block(section)
        assert "metadata" in schema, "Missing 'metadata' key in Output Schema JSON"


# ---------------------------------------------------------------------------
# Evaluation Criteria
# ---------------------------------------------------------------------------


@pytest.mark.smoke
class TestEvaluationCriteria:
    """Validate Evaluation Criteria weights sum to ~100 %."""

    def test_weights_sum_to_100_within_tolerance(self, goal_md_content: str) -> None:
        """Evaluation criteria weights must sum to 100 % (±1 %)."""
        section = _extract_section(goal_md_content, "Evaluation Criteria")
        rows = _parse_table_dicts(section)
        assert len(rows) > 0, "Evaluation Criteria table has no data rows"

        total = 0
        for row in rows:
            weight_str = row["Weight"].rstrip("%").strip()
            total += int(weight_str)

        assert abs(total - 100) <= 1, (
            f"Evaluation criteria weights sum to {total}%, expected 100% (±1%)"
        )


# ---------------------------------------------------------------------------
# Layer Routing
# ---------------------------------------------------------------------------


@pytest.mark.smoke
class TestLayerRouting:
    """Validate Layer Routing contains behaviour and knowledge entries."""

    def test_layer_routing_has_behaviour(self, goal_md_content: str) -> None:
        """Layer Routing table must contain a ``behaviour`` row."""
        section = _extract_section(goal_md_content, "Layer Routing")
        rows = _parse_table_dicts(section)
        layers = [r.get("Layer", "").strip().lower() for r in rows]
        assert "behaviour" in layers, (
            f"Missing 'behaviour' row in Layer Routing. Found layers: {layers}"
        )

    def test_layer_routing_has_knowledge(self, goal_md_content: str) -> None:
        """Layer Routing table must contain a ``knowledge`` row."""
        section = _extract_section(goal_md_content, "Layer Routing")
        rows = _parse_table_dicts(section)
        layers = [r.get("Layer", "").strip().lower() for r in rows]
        assert "knowledge" in layers, (
            f"Missing 'knowledge' row in Layer Routing. Found layers: {layers}"
        )


# ---------------------------------------------------------------------------
# Source Documents — path traversal guard
# ---------------------------------------------------------------------------


@pytest.mark.smoke
class TestSourceDocumentsSecurity:
    """Validate no path traversal in source document file patterns."""

    def test_no_path_traversal_in_file_patterns(self, goal_md_content: str) -> None:
        """Source document file patterns must not contain '..' (path traversal)."""
        section = _extract_section(goal_md_content, "Source Documents")
        rows = _parse_table_rows(section)
        assert len(rows) > 0, "Source Documents table has no data rows"

        for row in rows:
            file_pattern = row[0].strip()
            assert ".." not in file_pattern, (
                f"Path traversal detected in source document pattern: '{file_pattern}'"
            )
