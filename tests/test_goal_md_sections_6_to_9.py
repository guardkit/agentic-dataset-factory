"""Tests for GOAL.md sections 6-9: Evaluation Criteria, Output Schema, Metadata Schema, Layer Routing.

TDD tests for TASK-GG-003. Validates the GCSE English tutor GOAL.md sections
against acceptance criteria:
- AC-001: Section 6 has 5 evaluation criteria, valid Python identifiers, weights sum to 100%
- AC-002: Section 6 each criterion has description and weight columns
- AC-003: Section 7 contains valid JSON code block with messages and metadata top-level keys
- AC-004: Section 8 markdown table has Field, Type, Required, Valid Values columns
- AC-005: Section 8 all fields have Required = yes
- AC-006: Section 8 text valid values include all AQA set text identifiers
- AC-007: Section 8 ao valid values are AO1 through AO6 only (not AO7+)
- AC-008: Section 8 grade_target valid values are 4-9 and null
- AC-009: Section 9 contains behaviour and knowledge rows with destinations
- AC-010: All modified files pass project-configured lint/format checks with zero errors
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

# Resolve project root relative to this test file
PROJECT_ROOT = Path(__file__).resolve().parent.parent
GOAL_MD_PATH = PROJECT_ROOT / "domains" / "gcse-english-tutor" / "GOAL.md"


@pytest.fixture(scope="module")
def goal_md_content() -> str:
    """Read GOAL.md content once for all tests."""
    assert GOAL_MD_PATH.is_file(), f"{GOAL_MD_PATH} does not exist"
    return GOAL_MD_PATH.read_text(encoding="utf-8")


def _extract_section(content: str, heading: str) -> str:
    """Extract the content of a section by its ## heading."""
    pattern = rf"^## {re.escape(heading)}\s*\n(.*?)(?=^## |\Z)"
    match = re.search(pattern, content, re.MULTILINE | re.DOTALL)
    assert match is not None, f"Section '## {heading}' not found in GOAL.md"
    return match.group(1).strip()


def _parse_markdown_table(section_text: str) -> list[dict[str, str]]:
    """Parse a markdown table into a list of dicts keyed by column headers."""
    lines = [
        line.strip()
        for line in section_text.splitlines()
        if line.strip().startswith("|")
    ]
    assert len(lines) >= 3, f"Expected at least 3 table lines (header, separator, data), got {len(lines)}"

    # Parse headers
    headers = [h.strip() for h in lines[0].split("|")[1:-1]]

    # Skip separator line (index 1)
    rows: list[dict[str, str]] = []
    for line in lines[2:]:
        cells = [c.strip() for c in line.split("|")[1:-1]]
        row = dict(zip(headers, cells))
        rows.append(row)

    return rows


def _extract_json_block(section_text: str) -> dict:
    """Extract and parse the first JSON code block from section text."""
    pattern = r"```json\s*\n(.*?)\n\s*```"
    match = re.search(pattern, section_text, re.DOTALL)
    assert match is not None, "No JSON code block found in section"
    return json.loads(match.group(1))


# ---------------------------------------------------------------------------
# Section 6: Evaluation Criteria
# ---------------------------------------------------------------------------


class TestEvaluationCriteria:
    """AC-001 and AC-002: Evaluation Criteria section validation."""

    EXPECTED_CRITERIA = {
        "socratic_approach": 25,
        "ao_accuracy": 25,
        "mark_scheme_aligned": 20,
        "age_appropriate": 15,
        "factual_accuracy": 15,
    }

    def test_section_6_has_exactly_5_criteria(self, goal_md_content: str) -> None:
        """AC-001: Section 6 has 5 evaluation criteria."""
        section = _extract_section(goal_md_content, "Evaluation Criteria")
        rows = _parse_markdown_table(section)
        assert len(rows) == 5, f"Expected 5 criteria, got {len(rows)}"

    def test_all_criterion_names_are_valid_python_identifiers(
        self, goal_md_content: str
    ) -> None:
        """AC-001: All criterion names are valid Python identifiers (no hyphens)."""
        section = _extract_section(goal_md_content, "Evaluation Criteria")
        rows = _parse_markdown_table(section)
        for row in rows:
            name = row["Criterion"]
            assert name.isidentifier(), (
                f"Criterion name '{name}' is not a valid Python identifier"
            )
            assert "-" not in name, (
                f"Criterion name '{name}' contains hyphens"
            )

    def test_weights_sum_to_100_percent(self, goal_md_content: str) -> None:
        """AC-001: Weights sum to 100%."""
        section = _extract_section(goal_md_content, "Evaluation Criteria")
        rows = _parse_markdown_table(section)
        total = 0
        for row in rows:
            weight_str = row["Weight"].rstrip("%").strip()
            total += int(weight_str)
        assert total == 100, f"Weights sum to {total}%, expected 100%"

    def test_each_criterion_has_description_and_weight(
        self, goal_md_content: str
    ) -> None:
        """AC-002: Each criterion has a description and a weight column."""
        section = _extract_section(goal_md_content, "Evaluation Criteria")
        rows = _parse_markdown_table(section)
        for row in rows:
            assert "Description" in row, "Missing 'Description' column"
            assert "Weight" in row, "Missing 'Weight' column"
            assert len(row["Description"]) > 0, (
                f"Criterion '{row['Criterion']}' has empty description"
            )
            assert len(row["Weight"]) > 0, (
                f"Criterion '{row['Criterion']}' has empty weight"
            )

    def test_expected_criteria_present(self, goal_md_content: str) -> None:
        """All 5 expected criteria are present with correct weights."""
        section = _extract_section(goal_md_content, "Evaluation Criteria")
        rows = _parse_markdown_table(section)
        found = {row["Criterion"]: int(row["Weight"].rstrip("%").strip()) for row in rows}
        for name, weight in self.EXPECTED_CRITERIA.items():
            assert name in found, f"Missing criterion '{name}'"
            assert found[name] == weight, (
                f"Criterion '{name}' weight is {found[name]}%, expected {weight}%"
            )


# ---------------------------------------------------------------------------
# Section 7: Output Schema
# ---------------------------------------------------------------------------


class TestOutputSchema:
    """AC-003: Output Schema section validation."""

    def test_contains_valid_json_code_block(self, goal_md_content: str) -> None:
        """AC-003: Contains valid JSON code block."""
        section = _extract_section(goal_md_content, "Output Schema")
        schema = _extract_json_block(section)
        assert isinstance(schema, dict), "JSON root must be an object"

    def test_json_has_messages_key(self, goal_md_content: str) -> None:
        """AC-003: JSON has 'messages' top-level key."""
        section = _extract_section(goal_md_content, "Output Schema")
        schema = _extract_json_block(section)
        assert "messages" in schema, "Missing 'messages' top-level key"

    def test_json_has_metadata_key(self, goal_md_content: str) -> None:
        """AC-003: JSON has 'metadata' top-level key."""
        section = _extract_section(goal_md_content, "Output Schema")
        schema = _extract_json_block(section)
        assert "metadata" in schema, "Missing 'metadata' top-level key"

    def test_messages_is_array(self, goal_md_content: str) -> None:
        """Messages should be an array with system, user, assistant roles."""
        section = _extract_section(goal_md_content, "Output Schema")
        schema = _extract_json_block(section)
        assert isinstance(schema["messages"], list), "messages must be a list"
        roles = [m["role"] for m in schema["messages"]]
        assert "system" in roles, "Missing 'system' role in messages"
        assert "user" in roles, "Missing 'user' role in messages"
        assert "assistant" in roles, "Missing 'assistant' role in messages"

    def test_metadata_is_object(self, goal_md_content: str) -> None:
        """Metadata should be an object."""
        section = _extract_section(goal_md_content, "Output Schema")
        schema = _extract_json_block(section)
        assert isinstance(schema["metadata"], dict), "metadata must be a dict"


# ---------------------------------------------------------------------------
# Section 8: Metadata Schema
# ---------------------------------------------------------------------------


class TestMetadataSchema:
    """AC-004 through AC-008: Metadata Schema section validation."""

    EXPECTED_TEXT_VALUES = {
        "macbeth",
        "a_christmas_carol",
        "an_inspector_calls",
        "power_conflict_poetry",
        "language_paper_1",
        "language_paper_2",
        "general",
        "unseen_poetry",
    }

    EXPECTED_AO_VALUES = {"AO1", "AO2", "AO3", "AO4", "AO5", "AO6"}

    def test_table_has_required_columns(self, goal_md_content: str) -> None:
        """AC-004: Markdown table with Field, Type, Required, Valid Values columns."""
        section = _extract_section(goal_md_content, "Metadata Schema")
        rows = _parse_markdown_table(section)
        assert len(rows) > 0, "Metadata Schema table has no data rows"
        for row in rows:
            assert "Field" in row, "Missing 'Field' column"
            assert "Type" in row, "Missing 'Type' column"
            assert "Required" in row, "Missing 'Required' column"
            assert "Valid Values" in row, "Missing 'Valid Values' column"

    def test_all_fields_required_yes(self, goal_md_content: str) -> None:
        """AC-005: All fields have Required = yes."""
        section = _extract_section(goal_md_content, "Metadata Schema")
        rows = _parse_markdown_table(section)
        for row in rows:
            assert row["Required"].lower() == "yes", (
                f"Field '{row['Field']}' has Required='{row['Required']}', expected 'yes'"
            )

    def test_text_valid_values_include_all_aqa_set_texts(
        self, goal_md_content: str
    ) -> None:
        """AC-006: text valid values include all AQA set text identifiers."""
        section = _extract_section(goal_md_content, "Metadata Schema")
        rows = _parse_markdown_table(section)
        text_row = next((r for r in rows if r["Field"] == "text"), None)
        assert text_row is not None, "Missing 'text' field in Metadata Schema"
        valid_values = {v.strip() for v in text_row["Valid Values"].split(",")}
        for expected in self.EXPECTED_TEXT_VALUES:
            assert expected in valid_values, (
                f"Missing AQA set text identifier '{expected}' in text valid values. "
                f"Found: {valid_values}"
            )

    def test_ao_valid_values_are_ao1_through_ao6_only(
        self, goal_md_content: str
    ) -> None:
        """AC-007: ao valid values are AO1 through AO6 only (not AO7+)."""
        section = _extract_section(goal_md_content, "Metadata Schema")
        rows = _parse_markdown_table(section)
        ao_row = next((r for r in rows if r["Field"] == "ao"), None)
        assert ao_row is not None, "Missing 'ao' field in Metadata Schema"
        # Extract AO values from the valid values string
        ao_values = set()
        for part in ao_row["Valid Values"].split(","):
            part = part.strip()
            # Match AO pattern, ignoring parenthetical notes like "(can be empty)"
            ao_match = re.match(r"^(AO\d+)", part)
            if ao_match:
                ao_values.add(ao_match.group(1))
        # Must contain exactly AO1-AO6
        for expected in self.EXPECTED_AO_VALUES:
            assert expected in ao_values, f"Missing '{expected}' in ao valid values"
        # Must not contain AO7+
        for val in ao_values:
            num = int(val[2:])
            assert 1 <= num <= 6, f"Invalid AO value '{val}' — only AO1-AO6 allowed"

    def test_grade_target_valid_values_are_4_to_9_and_null(
        self, goal_md_content: str
    ) -> None:
        """AC-008: grade_target valid values are 4-9 and null."""
        section = _extract_section(goal_md_content, "Metadata Schema")
        rows = _parse_markdown_table(section)
        gt_row = next((r for r in rows if r["Field"] == "grade_target"), None)
        assert gt_row is not None, "Missing 'grade_target' field in Metadata Schema"
        valid_values_str = gt_row["Valid Values"]
        # Check for numeric values 4-9
        for grade in range(4, 10):
            assert str(grade) in valid_values_str, (
                f"Missing grade {grade} in grade_target valid values"
            )
        # Check for null
        assert "null" in valid_values_str.lower(), (
            "Missing 'null' in grade_target valid values"
        )
        # Check no grades outside 4-9 (e.g., 1, 2, 3, 10)
        for bad_grade in [1, 2, 3, 10]:
            # Use word boundary to avoid matching substrings like '1' inside '15'
            assert not re.search(rf"\b{bad_grade}\b", valid_values_str), (
                f"Unexpected grade {bad_grade} in grade_target valid values"
            )

    def test_has_all_expected_fields(self, goal_md_content: str) -> None:
        """Metadata Schema has all expected fields."""
        section = _extract_section(goal_md_content, "Metadata Schema")
        rows = _parse_markdown_table(section)
        field_names = {row["Field"] for row in rows}
        expected_fields = {"layer", "type", "ao", "text", "topic", "grade_target", "source", "turns"}
        for field in expected_fields:
            assert field in field_names, f"Missing field '{field}' in Metadata Schema"


# ---------------------------------------------------------------------------
# Section 9: Layer Routing
# ---------------------------------------------------------------------------


class TestLayerRouting:
    """AC-009: Layer Routing section validation."""

    def test_contains_behaviour_row(self, goal_md_content: str) -> None:
        """AC-009: Contains 'behaviour' row with destination."""
        section = _extract_section(goal_md_content, "Layer Routing")
        rows = _parse_markdown_table(section)
        behaviour_row = next(
            (r for r in rows if r.get("Layer", "").strip() == "behaviour"), None
        )
        assert behaviour_row is not None, "Missing 'behaviour' row in Layer Routing"
        assert len(behaviour_row.get("Destination", "").strip()) > 0, (
            "behaviour row has empty Destination"
        )

    def test_contains_knowledge_row(self, goal_md_content: str) -> None:
        """AC-009: Contains 'knowledge' row with destination."""
        section = _extract_section(goal_md_content, "Layer Routing")
        rows = _parse_markdown_table(section)
        knowledge_row = next(
            (r for r in rows if r.get("Layer", "").strip() == "knowledge"), None
        )
        assert knowledge_row is not None, "Missing 'knowledge' row in Layer Routing"
        assert len(knowledge_row.get("Destination", "").strip()) > 0, (
            "knowledge row has empty Destination"
        )

    def test_behaviour_routes_to_train_jsonl(self, goal_md_content: str) -> None:
        """behaviour layer routes to output/train.jsonl."""
        section = _extract_section(goal_md_content, "Layer Routing")
        rows = _parse_markdown_table(section)
        behaviour_row = next(
            (r for r in rows if r.get("Layer", "").strip() == "behaviour"), None
        )
        assert behaviour_row is not None
        assert "train.jsonl" in behaviour_row["Destination"], (
            f"behaviour destination should include 'train.jsonl', got '{behaviour_row['Destination']}'"
        )

    def test_knowledge_routes_to_rag_index(self, goal_md_content: str) -> None:
        """knowledge layer routes to rag_index/knowledge.jsonl."""
        section = _extract_section(goal_md_content, "Layer Routing")
        rows = _parse_markdown_table(section)
        knowledge_row = next(
            (r for r in rows if r.get("Layer", "").strip() == "knowledge"), None
        )
        assert knowledge_row is not None
        assert "knowledge.jsonl" in knowledge_row["Destination"], (
            f"knowledge destination should include 'knowledge.jsonl', got '{knowledge_row['Destination']}'"
        )

    def test_layer_routing_has_classification_rules(
        self, goal_md_content: str
    ) -> None:
        """Layer Routing section should include classification rules."""
        section = _extract_section(goal_md_content, "Layer Routing")
        # Should have some text explaining the routing rules
        assert "behaviour" in section.lower()
        assert "knowledge" in section.lower()


# ---------------------------------------------------------------------------
# Cross-section consistency
# ---------------------------------------------------------------------------


class TestCrossSectionConsistency:
    """Verify consistency between sections."""

    def test_no_todo_comments_in_sections_6_to_9(
        self, goal_md_content: str
    ) -> None:
        """Sections 6-9 should have no remaining TODO comments."""
        for heading in [
            "Evaluation Criteria",
            "Output Schema",
            "Metadata Schema",
            "Layer Routing",
        ]:
            section = _extract_section(goal_md_content, heading)
            assert "TODO" not in section, (
                f"Section '{heading}' still contains a TODO comment"
            )
