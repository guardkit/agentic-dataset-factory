"""Metadata consistency tests cross-validating GOAL.md against validator.py.

TASK-GG-004: Verify that the GOAL.md Metadata Schema section (source of truth
for the domain) stays consistent with the Pydantic enforcement layer in
synthesis/validator.py.  Catches drift between documentation and code.

Tests:
- AC-001: Test file created at tests/test_goal_md_consistency.py
- AC-002: GOAL.md text valid values match TEXT_VALUES in validator.py
- AC-003: GOAL.md topic valid values match TOPIC_VALUES in validator.py
- AC-004: GOAL.md ao valid values match AO_PATTERN (AO1-AO6)
- AC-005: GOAL.md grade_target range matches validator (4-9 + null)
- AC-006: GOAL.md layer values match Metadata.layer Literal type
- AC-007: GOAL.md type values match Metadata.type Literal type
- AC-008: All generation target categories appear in metadata topic valid values
- AC-009: All evaluation criterion names are valid Python identifiers
- AC-010: All tests pass with pytest tests/test_goal_md_consistency.py -v

Seam test:
- METADATA_VALID_VALUES contract from TASK-GG-003
"""

from __future__ import annotations

import re
import typing
from pathlib import Path

import pytest

from synthesis.validator import (
    AO_PATTERN,
    TEXT_VALUES,
    TOPIC_VALUES,
    Metadata,
)

# ---------------------------------------------------------------------------
# Paths & helpers
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parent.parent
GOAL_MD_PATH = PROJECT_ROOT / "domains" / "gcse-english-tutor" / "GOAL.md"

_IDENTIFIER_RE = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")


def _read_goal_md() -> str:
    """Read GOAL.md from disk once (cached via fixture below)."""
    assert GOAL_MD_PATH.is_file(), f"{GOAL_MD_PATH} does not exist"
    return GOAL_MD_PATH.read_text(encoding="utf-8")


def _extract_section(content: str, heading: str) -> str:
    """Extract the body of a ## heading from markdown."""
    pattern = rf"^## {re.escape(heading)}\s*\n(.*?)(?=^## |\Z)"
    match = re.search(pattern, content, re.MULTILINE | re.DOTALL)
    assert match is not None, f"Section '## {heading}' not found in GOAL.md"
    return match.group(1).strip()


def _parse_markdown_table(section_text: str) -> list[dict[str, str]]:
    """Parse a markdown table into a list of row-dicts keyed by header."""
    lines = [
        line.strip()
        for line in section_text.splitlines()
        if line.strip().startswith("|")
    ]
    assert len(lines) >= 3, (
        f"Expected at least 3 table lines (header, separator, data), got {len(lines)}"
    )
    headers = [h.strip() for h in lines[0].split("|")[1:-1]]
    rows: list[dict[str, str]] = []
    for line in lines[2:]:
        cells = [c.strip() for c in line.split("|")[1:-1]]
        rows.append(dict(zip(headers, cells)))
    return rows


def _get_literal_args(model_cls: type, field_name: str) -> set[str]:
    """Extract the set of allowed strings from a Pydantic Literal field.

    Works with both ``Literal["a", "b"]`` and ``typing.Optional[Literal[...]]``.
    """
    field_info = model_cls.model_fields[field_name]
    annotation = field_info.annotation
    # Unwrap Optional (Union[X, None])
    origin = typing.get_origin(annotation)
    if origin is typing.Union:
        args = [a for a in typing.get_args(annotation) if a is not type(None)]
        annotation = args[0] if args else annotation
    # Now extract Literal args
    if typing.get_origin(annotation) is typing.Literal:
        return set(typing.get_args(annotation))
    # Fallback: try get_args directly (for plain Literal at top level)
    literal_args = typing.get_args(annotation)
    if literal_args:
        return set(literal_args)
    raise AssertionError(
        f"Could not extract Literal args from {model_cls.__name__}.{field_name}"
    )


def _parse_comma_separated_values(raw: str) -> set[str]:
    """Split a comma-separated Valid Values cell, stripping whitespace & parenthetical notes."""
    values: set[str] = set()
    for part in raw.split(","):
        part = part.strip()
        # Strip parenthetical notes like "(can be empty)"
        part = re.sub(r"\(.*?\)", "", part).strip()
        if part:
            values.add(part)
    return values


def _get_metadata_field_valid_values(
    rows: list[dict[str, str]], field_name: str
) -> set[str]:
    """Find a field row in the Metadata Schema table and parse its valid values."""
    field_row = next((r for r in rows if r["Field"] == field_name), None)
    assert field_row is not None, (
        f"Missing '{field_name}' field in Metadata Schema table"
    )
    return _parse_comma_separated_values(field_row["Valid Values"])


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def goal_md_content() -> str:
    """Read GOAL.md content once for all tests in this module."""
    return _read_goal_md()


@pytest.fixture(scope="module")
def metadata_schema_rows(goal_md_content: str) -> list[dict[str, str]]:
    """Parse the Metadata Schema table from GOAL.md."""
    section = _extract_section(goal_md_content, "Metadata Schema")
    return _parse_markdown_table(section)


# ---------------------------------------------------------------------------
# AC-002: text valid values match TEXT_VALUES
# ---------------------------------------------------------------------------


class TestTextValuesConsistency:
    """GOAL.md text valid values ↔ validator.py TEXT_VALUES."""

    def test_goal_md_text_values_match_validator_text_values(
        self, metadata_schema_rows: list[dict[str, str]]
    ) -> None:
        """AC-002: GOAL.md text values must match TEXT_VALUES exactly."""
        goal_text_values = _get_metadata_field_valid_values(
            metadata_schema_rows, "text"
        )
        validator_text_values = set(TEXT_VALUES)
        assert goal_text_values == validator_text_values, (
            f"text value mismatch.\n"
            f"  In GOAL.md only: {goal_text_values - validator_text_values}\n"
            f"  In validator.py only: {validator_text_values - goal_text_values}"
        )

    def test_validator_text_values_subset_of_goal_md(
        self, metadata_schema_rows: list[dict[str, str]]
    ) -> None:
        """TEXT_VALUES in validator.py must be a subset of GOAL.md text values."""
        goal_text_values = _get_metadata_field_valid_values(
            metadata_schema_rows, "text"
        )
        assert set(TEXT_VALUES).issubset(goal_text_values), (
            f"validator.py TEXT_VALUES has values not in GOAL.md: "
            f"{set(TEXT_VALUES) - goal_text_values}"
        )

    def test_metadata_model_text_literal_matches_text_values(self) -> None:
        """Metadata.text Literal args must equal TEXT_VALUES tuple."""
        literal_args = _get_literal_args(Metadata, "text")
        assert literal_args == set(TEXT_VALUES), (
            f"Metadata.text Literal drift.\n"
            f"  Literal only: {literal_args - set(TEXT_VALUES)}\n"
            f"  TEXT_VALUES only: {set(TEXT_VALUES) - literal_args}"
        )


# ---------------------------------------------------------------------------
# AC-003: topic valid values match TOPIC_VALUES
# ---------------------------------------------------------------------------


class TestTopicValuesConsistency:
    """GOAL.md topic valid values ↔ validator.py TOPIC_VALUES."""

    def test_goal_md_topic_values_match_validator_topic_values(
        self, metadata_schema_rows: list[dict[str, str]]
    ) -> None:
        """AC-003: GOAL.md topic values must match TOPIC_VALUES exactly."""
        goal_topic_values = _get_metadata_field_valid_values(
            metadata_schema_rows, "topic"
        )
        validator_topic_values = set(TOPIC_VALUES)
        assert goal_topic_values == validator_topic_values, (
            f"topic value mismatch.\n"
            f"  In GOAL.md only: {goal_topic_values - validator_topic_values}\n"
            f"  In validator.py only: {validator_topic_values - goal_topic_values}"
        )

    def test_validator_topic_values_subset_of_goal_md(
        self, metadata_schema_rows: list[dict[str, str]]
    ) -> None:
        """TOPIC_VALUES in validator.py must be a subset of GOAL.md topic values."""
        goal_topic_values = _get_metadata_field_valid_values(
            metadata_schema_rows, "topic"
        )
        assert set(TOPIC_VALUES).issubset(goal_topic_values), (
            f"validator.py TOPIC_VALUES has values not in GOAL.md: "
            f"{set(TOPIC_VALUES) - goal_topic_values}"
        )

    def test_metadata_model_topic_literal_matches_topic_values(self) -> None:
        """Metadata.topic Literal args must equal TOPIC_VALUES tuple."""
        literal_args = _get_literal_args(Metadata, "topic")
        assert literal_args == set(TOPIC_VALUES), (
            f"Metadata.topic Literal drift.\n"
            f"  Literal only: {literal_args - set(TOPIC_VALUES)}\n"
            f"  TOPIC_VALUES only: {set(TOPIC_VALUES) - literal_args}"
        )


# ---------------------------------------------------------------------------
# AC-004: ao valid values match AO_PATTERN (AO1-AO6)
# ---------------------------------------------------------------------------


class TestAoValuesConsistency:
    """GOAL.md ao valid values ↔ validator.py AO_PATTERN."""

    EXPECTED_AO_VALUES = {"AO1", "AO2", "AO3", "AO4", "AO5", "AO6"}

    def test_goal_md_ao_values_match_ao_pattern(
        self, metadata_schema_rows: list[dict[str, str]]
    ) -> None:
        """AC-004: GOAL.md ao values must be exactly AO1-AO6."""
        ao_row = next(
            (r for r in metadata_schema_rows if r["Field"] == "ao"), None
        )
        assert ao_row is not None, "Missing 'ao' field in Metadata Schema"
        raw = ao_row["Valid Values"]
        ao_values: set[str] = set()
        for part in raw.split(","):
            part = part.strip()
            ao_match = re.match(r"^(AO\d+)", part)
            if ao_match:
                ao_values.add(ao_match.group(1))
        assert ao_values == self.EXPECTED_AO_VALUES, (
            f"ao value mismatch.\n"
            f"  In GOAL.md: {ao_values}\n"
            f"  Expected: {self.EXPECTED_AO_VALUES}"
        )

    def test_ao_pattern_accepts_all_goal_md_values(self) -> None:
        """AC-004: AO_PATTERN regex must accept AO1 through AO6."""
        for code in self.EXPECTED_AO_VALUES:
            assert AO_PATTERN.match(code), (
                f"AO_PATTERN does not accept '{code}'"
            )

    def test_ao_pattern_rejects_ao7_and_above(self) -> None:
        """AC-004: AO_PATTERN must reject AO7+."""
        for num in range(7, 12):
            assert not AO_PATTERN.match(f"AO{num}"), (
                f"AO_PATTERN should reject 'AO{num}'"
            )


# ---------------------------------------------------------------------------
# AC-005: grade_target range matches validator (4-9 + null)
# ---------------------------------------------------------------------------


class TestGradeTargetConsistency:
    """GOAL.md grade_target ↔ validator.py validate_grade_target."""

    def test_goal_md_grade_target_range(
        self, metadata_schema_rows: list[dict[str, str]]
    ) -> None:
        """AC-005: GOAL.md grade_target valid values must be 4-9 and null."""
        gt_row = next(
            (r for r in metadata_schema_rows if r["Field"] == "grade_target"),
            None,
        )
        assert gt_row is not None, "Missing 'grade_target' in Metadata Schema"
        raw = gt_row["Valid Values"]
        # Check all grades 4-9 present
        for grade in range(4, 10):
            assert str(grade) in raw, (
                f"Missing grade {grade} in GOAL.md grade_target valid values"
            )
        # Check null present
        assert "null" in raw.lower(), (
            "Missing 'null' in GOAL.md grade_target valid values"
        )

    def test_validator_accepts_grades_4_to_9(self) -> None:
        """AC-005: Metadata validator must accept grade_target 4 through 9."""
        for grade in range(4, 10):
            m = Metadata(
                layer="behaviour",
                type="reasoning",
                text="macbeth",
                topic="character_analysis",
                grade_target=grade,
                source="synthetic",
            )
            assert m.grade_target == grade

    def test_validator_accepts_null_grade_target(self) -> None:
        """AC-005: Metadata validator must accept null (None) grade_target."""
        m = Metadata(
            layer="behaviour",
            type="reasoning",
            text="macbeth",
            topic="character_analysis",
            grade_target=None,
            source="synthetic",
        )
        assert m.grade_target is None

    def test_validator_rejects_grade_outside_range(self) -> None:
        """AC-005: Metadata validator must reject grade_target outside 4-9."""
        for bad_grade in [1, 2, 3, 10, 11, 0, -1]:
            with pytest.raises(Exception):
                Metadata(
                    layer="behaviour",
                    type="reasoning",
                    text="macbeth",
                    topic="character_analysis",
                    grade_target=bad_grade,
                    source="synthetic",
                )


# ---------------------------------------------------------------------------
# AC-006: layer values match Metadata.layer Literal type
# ---------------------------------------------------------------------------


class TestLayerValuesConsistency:
    """GOAL.md layer ↔ Metadata.layer Literal type."""

    def test_goal_md_layer_values_match_metadata_literal(
        self, metadata_schema_rows: list[dict[str, str]]
    ) -> None:
        """AC-006: GOAL.md layer values must match Metadata.layer Literal."""
        goal_layer_values = _get_metadata_field_valid_values(
            metadata_schema_rows, "layer"
        )
        literal_layer_values = _get_literal_args(Metadata, "layer")
        assert goal_layer_values == literal_layer_values, (
            f"layer value mismatch.\n"
            f"  In GOAL.md only: {goal_layer_values - literal_layer_values}\n"
            f"  In Metadata.layer only: {literal_layer_values - goal_layer_values}"
        )


# ---------------------------------------------------------------------------
# AC-007: type values match Metadata.type Literal type
# ---------------------------------------------------------------------------


class TestTypeValuesConsistency:
    """GOAL.md type ↔ Metadata.type Literal type."""

    def test_goal_md_type_values_match_metadata_literal(
        self, metadata_schema_rows: list[dict[str, str]]
    ) -> None:
        """AC-007: GOAL.md type values must match Metadata.type Literal."""
        goal_type_values = _get_metadata_field_valid_values(
            metadata_schema_rows, "type"
        )
        literal_type_values = _get_literal_args(Metadata, "type")
        assert goal_type_values == literal_type_values, (
            f"type value mismatch.\n"
            f"  In GOAL.md only: {goal_type_values - literal_type_values}\n"
            f"  In Metadata.type only: {literal_type_values - goal_type_values}"
        )


# ---------------------------------------------------------------------------
# AC-008: Generation target categories appear in topic valid values
# ---------------------------------------------------------------------------


class TestGenerationTargetTopicConsistency:
    """Generation Targets categories → metadata topic valid values."""

    # Mapping from Generation Targets Category text to expected topic value
    _CATEGORY_TO_TOPIC: dict[str, str] = {
        "Literary analysis": "character_analysis",
        "Essay feedback": "essay_feedback",
        "Exam technique guidance": "exam_technique",
        "Poetry comparative questions": "comparative",
        "Factual recall / character / plot": "factual_recall",
        "Terminology definitions": "terminology",
        "Encouragement / session management": "encouragement",
    }

    def test_generation_target_categories_in_topic_values(
        self, goal_md_content: str, metadata_schema_rows: list[dict[str, str]]
    ) -> None:
        """AC-008: Every generation target category maps to a metadata topic value."""
        # Parse Generation Targets table
        gen_section = _extract_section(goal_md_content, "Generation Targets")
        gen_rows = _parse_markdown_table(gen_section)
        gen_categories = {row["Category"].strip() for row in gen_rows}
        assert len(gen_categories) > 0, "No generation target categories found"

        # Get topic valid values from Metadata Schema
        goal_topic_values = _get_metadata_field_valid_values(
            metadata_schema_rows, "topic"
        )

        # Verify each category has a corresponding topic
        for category in gen_categories:
            # Find the base category name (before parenthetical qualifiers)
            base = category.split("(")[0].strip()
            expected_topic = self._CATEGORY_TO_TOPIC.get(base)
            assert expected_topic is not None, (
                f"Generation target category '{category}' has no known "
                f"topic mapping. Known: {list(self._CATEGORY_TO_TOPIC.keys())}"
            )
            assert expected_topic in goal_topic_values, (
                f"Topic '{expected_topic}' (from category '{category}') "
                f"not in GOAL.md topic valid values: {goal_topic_values}"
            )

    def test_generation_target_topics_in_validator_topic_values(
        self, goal_md_content: str
    ) -> None:
        """AC-008: Every mapped topic value exists in validator.py TOPIC_VALUES."""
        validator_topics = set(TOPIC_VALUES)
        for topic in self._CATEGORY_TO_TOPIC.values():
            assert topic in validator_topics, (
                f"Mapped topic '{topic}' not in validator.py TOPIC_VALUES"
            )


# ---------------------------------------------------------------------------
# AC-009: Evaluation criterion names are valid Python identifiers
# ---------------------------------------------------------------------------


class TestEvaluationCriterionIdentifiers:
    """Evaluation criterion names must be valid Python identifiers."""

    def test_all_criterion_names_are_valid_identifiers(
        self, goal_md_content: str
    ) -> None:
        """AC-009: Every criterion name matches ^[a-zA-Z_][a-zA-Z0-9_]*$."""
        section = _extract_section(goal_md_content, "Evaluation Criteria")
        rows = _parse_markdown_table(section)
        assert len(rows) > 0, "No evaluation criteria found"
        for row in rows:
            name = row["Criterion"]
            assert _IDENTIFIER_RE.match(name), (
                f"Criterion name '{name}' is not a valid Python identifier "
                f"(must match ^[a-zA-Z_][a-zA-Z0-9_]*$)"
            )

    def test_no_hyphens_in_criterion_names(
        self, goal_md_content: str
    ) -> None:
        """AC-009: Criterion names must not contain hyphens."""
        section = _extract_section(goal_md_content, "Evaluation Criteria")
        rows = _parse_markdown_table(section)
        for row in rows:
            name = row["Criterion"]
            assert "-" not in name, (
                f"Criterion name '{name}' contains hyphens — "
                f"not a valid Python identifier"
            )


# ---------------------------------------------------------------------------
# Seam test: METADATA_VALID_VALUES contract from TASK-GG-003
# ---------------------------------------------------------------------------


@pytest.mark.seam
@pytest.mark.integration_contract("METADATA_VALID_VALUES")
class TestMetadataValidValuesContract:
    """Seam test: GOAL.md values are a superset of validator.py Literals.

    Contract: Text and topic valid values in GOAL.md Metadata Schema table
    must be a superset of Literal values in synthesis/validator.py Metadata model.
    Producer: TASK-GG-003
    """

    def test_text_values_superset(
        self, metadata_schema_rows: list[dict[str, str]]
    ) -> None:
        """GOAL.md text values are a superset of validator.py TEXT_VALUES."""
        goal_text_values = _get_metadata_field_valid_values(
            metadata_schema_rows, "text"
        )
        assert set(TEXT_VALUES).issubset(goal_text_values), (
            f"validator.py TEXT_VALUES contains values not in GOAL.md: "
            f"{set(TEXT_VALUES) - goal_text_values}"
        )

    def test_topic_values_superset(
        self, metadata_schema_rows: list[dict[str, str]]
    ) -> None:
        """GOAL.md topic values are a superset of validator.py TOPIC_VALUES."""
        goal_topic_values = _get_metadata_field_valid_values(
            metadata_schema_rows, "topic"
        )
        assert set(TOPIC_VALUES).issubset(goal_topic_values), (
            f"validator.py TOPIC_VALUES contains values not in GOAL.md: "
            f"{set(TOPIC_VALUES) - goal_topic_values}"
        )

    def test_layer_values_superset(
        self, metadata_schema_rows: list[dict[str, str]]
    ) -> None:
        """GOAL.md layer values are a superset of Metadata.layer Literal."""
        goal_layer_values = _get_metadata_field_valid_values(
            metadata_schema_rows, "layer"
        )
        literal_layer_values = _get_literal_args(Metadata, "layer")
        assert literal_layer_values.issubset(goal_layer_values), (
            f"Metadata.layer Literal has values not in GOAL.md: "
            f"{literal_layer_values - goal_layer_values}"
        )

    def test_type_values_superset(
        self, metadata_schema_rows: list[dict[str, str]]
    ) -> None:
        """GOAL.md type values are a superset of Metadata.type Literal."""
        goal_type_values = _get_metadata_field_valid_values(
            metadata_schema_rows, "type"
        )
        literal_type_values = _get_literal_args(Metadata, "type")
        assert literal_type_values.issubset(goal_type_values), (
            f"Metadata.type Literal has values not in GOAL.md: "
            f"{literal_type_values - goal_type_values}"
        )

    def test_source_values_superset(
        self, metadata_schema_rows: list[dict[str, str]]
    ) -> None:
        """GOAL.md source values are a superset of Metadata.source Literal."""
        goal_source_values = _get_metadata_field_valid_values(
            metadata_schema_rows, "source"
        )
        literal_source_values = _get_literal_args(Metadata, "source")
        assert literal_source_values.issubset(goal_source_values), (
            f"Metadata.source Literal has values not in GOAL.md: "
            f"{literal_source_values - goal_source_values}"
        )
