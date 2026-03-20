"""Tests for domain_config.parser — parse_table(), extract_json(), and split_sections().

TDD: RED phase — these tests define the expected behaviour for TASK-DC-002 and TASK-DC-003.
Follows the same conventions as test_models.py:
- Organised by test class per function
- AAA pattern (Arrange, Act, Assert)
- pytest.raises for negative cases
- pytest.mark.parametrize for sweeps
- Naming: test_<function>_<scenario>_<expected_result>
"""

from __future__ import annotations

import pytest

from domain_config.models import (
    EvaluationCriterion,
    GenerationTarget,
    GoalValidationError,
    MetadataField,
    SourceDocument,
)
from domain_config.parser import extract_json, parse_table, split_sections


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def source_documents_table() -> str:
    """Markdown table for Source Documents section."""
    return (
        "| File Pattern | Mode | Notes |\n"
        "|---|---|---|\n"
        "| mr-bruff-*.pdf | standard | Digital PDFs |\n"
        "| scanned-*.pdf | vlm | Scanned pages |\n"
    )


@pytest.fixture
def source_documents_column_map() -> dict[str, str]:
    return {
        "File Pattern": "file_pattern",
        "Mode": "mode",
        "Notes": "notes",
    }


@pytest.fixture
def generation_targets_table() -> str:
    return (
        "| Category | Type | Count |\n"
        "|---|---|---|\n"
        "| Literary analysis (single-turn) | reasoning | 200 |\n"
        "| Factual recall | direct | 100 |\n"
    )


@pytest.fixture
def generation_targets_column_map() -> dict[str, str]:
    return {
        "Category": "category",
        "Type": "type",
        "Count": "count",
    }


@pytest.fixture
def evaluation_criteria_table() -> str:
    return (
        "| Criterion | Description | Weight |\n"
        "|---|---|---|\n"
        "| socratic_approach | Guides via questions | 25% |\n"
        "| factual_accuracy | Correct content | 50% |\n"
        "| tone | Appropriate register | 25% |\n"
    )


@pytest.fixture
def evaluation_criteria_column_map() -> dict[str, str]:
    return {
        "Criterion": "name",
        "Description": "description",
        "Weight": "weight",
    }


@pytest.fixture
def metadata_schema_table() -> str:
    return (
        "| Field | Type | Required | Valid Values |\n"
        "|---|---|---|---|\n"
        "| layer | string | yes | behaviour, knowledge |\n"
        "| turns | integer | yes | |\n"
        "| topic | string | no | |\n"
    )


@pytest.fixture
def metadata_schema_column_map() -> dict[str, str]:
    return {
        "Field": "field",
        "Type": "type",
        "Required": "required",
        "Valid Values": "valid_values",
    }


@pytest.fixture
def layer_routing_table() -> str:
    return (
        "| Layer | Destination |\n"
        "|---|---|\n"
        "| behaviour | output/train.jsonl |\n"
        "| knowledge | output/rag_index/knowledge.jsonl |\n"
    )


@pytest.fixture
def valid_json_section() -> str:
    return (
        "Some intro text.\n"
        "\n"
        "```json\n"
        "{\n"
        '  "messages": [\n'
        '    {"role": "system", "content": "You are a tutor."}\n'
        "  ],\n"
        '  "metadata": {\n'
        '    "layer": "behaviour"\n'
        "  }\n"
        "}\n"
        "```\n"
    )


# ---------------------------------------------------------------------------
# parse_table — Source Documents
# ---------------------------------------------------------------------------


class TestParseTableSourceDocuments:
    """BDD Scenarios 36-40: Parsing the Source Documents table."""

    def test_parses_rows_into_source_document_list(
        self, source_documents_table, source_documents_column_map
    ):
        result = parse_table(source_documents_table, SourceDocument, source_documents_column_map)
        assert len(result) == 2
        assert all(isinstance(r, SourceDocument) for r in result)

    def test_first_row_values_correct(self, source_documents_table, source_documents_column_map):
        result = parse_table(source_documents_table, SourceDocument, source_documents_column_map)
        assert result[0].file_pattern == "mr-bruff-*.pdf"
        assert result[0].mode == "standard"
        assert result[0].notes == "Digital PDFs"

    def test_second_row_values_correct(self, source_documents_table, source_documents_column_map):
        result = parse_table(source_documents_table, SourceDocument, source_documents_column_map)
        assert result[1].file_pattern == "scanned-*.pdf"
        assert result[1].mode == "vlm"
        assert result[1].notes == "Scanned pages"


# ---------------------------------------------------------------------------
# parse_table — Generation Targets
# ---------------------------------------------------------------------------


class TestParseTableGenerationTargets:
    """BDD Scenarios 50-56: Parsing the Generation Targets table."""

    def test_parses_rows_into_generation_target_list(
        self, generation_targets_table, generation_targets_column_map
    ):
        result = parse_table(
            generation_targets_table,
            GenerationTarget,
            generation_targets_column_map,
        )
        assert len(result) == 2
        assert all(isinstance(r, GenerationTarget) for r in result)

    def test_count_coerced_to_int(self, generation_targets_table, generation_targets_column_map):
        result = parse_table(
            generation_targets_table,
            GenerationTarget,
            generation_targets_column_map,
        )
        assert result[0].count == 200
        assert isinstance(result[0].count, int)

    def test_type_literal_values_preserved(
        self, generation_targets_table, generation_targets_column_map
    ):
        result = parse_table(
            generation_targets_table,
            GenerationTarget,
            generation_targets_column_map,
        )
        assert result[0].type == "reasoning"
        assert result[1].type == "direct"


# ---------------------------------------------------------------------------
# parse_table — Evaluation Criteria
# ---------------------------------------------------------------------------


class TestParseTableEvaluationCriteria:
    """BDD Scenarios 57-63: Parsing the Evaluation Criteria table."""

    def test_parses_rows_into_evaluation_criterion_list(
        self, evaluation_criteria_table, evaluation_criteria_column_map
    ):
        result = parse_table(
            evaluation_criteria_table,
            EvaluationCriterion,
            evaluation_criteria_column_map,
        )
        assert len(result) == 3
        assert all(isinstance(r, EvaluationCriterion) for r in result)

    def test_weight_percentage_converted_to_float(
        self, evaluation_criteria_table, evaluation_criteria_column_map
    ):
        """AC: Weight values parsed as float (e.g., '25%' -> 0.25)."""
        result = parse_table(
            evaluation_criteria_table,
            EvaluationCriterion,
            evaluation_criteria_column_map,
        )
        assert result[0].weight == 0.25
        assert result[1].weight == 0.50
        assert result[2].weight == 0.25

    def test_criterion_names_are_valid_identifiers(
        self, evaluation_criteria_table, evaluation_criteria_column_map
    ):
        result = parse_table(
            evaluation_criteria_table,
            EvaluationCriterion,
            evaluation_criteria_column_map,
        )
        for crit in result:
            assert crit.name.isidentifier()


# ---------------------------------------------------------------------------
# parse_table — Metadata Schema
# ---------------------------------------------------------------------------


class TestParseTableMetadataSchema:
    """BDD Scenarios: Metadata Schema table parsing."""

    def test_parses_rows_into_metadata_field_list(
        self, metadata_schema_table, metadata_schema_column_map
    ):
        result = parse_table(metadata_schema_table, MetadataField, metadata_schema_column_map)
        assert len(result) == 3
        assert all(isinstance(r, MetadataField) for r in result)

    def test_required_column_parsed_as_bool(
        self, metadata_schema_table, metadata_schema_column_map
    ):
        """AC: Required column parsed as bool (e.g., 'yes' -> True)."""
        result = parse_table(metadata_schema_table, MetadataField, metadata_schema_column_map)
        assert result[0].required is True
        assert result[1].required is True
        assert result[2].required is False

    def test_valid_values_parsed_as_list(self, metadata_schema_table, metadata_schema_column_map):
        """AC: Valid Values column parsed as list[str] (comma-separated)."""
        result = parse_table(metadata_schema_table, MetadataField, metadata_schema_column_map)
        assert result[0].valid_values == ["behaviour", "knowledge"]

    def test_empty_valid_values_gives_empty_list(
        self, metadata_schema_table, metadata_schema_column_map
    ):
        """AC: empty column -> empty list. BDD Scenario 317-322."""
        result = parse_table(metadata_schema_table, MetadataField, metadata_schema_column_map)
        assert result[1].valid_values == []
        assert result[2].valid_values == []


# ---------------------------------------------------------------------------
# parse_table — Layer Routing (dict[str, str])
# ---------------------------------------------------------------------------


class TestParseTableLayerRouting:
    """BDD Scenarios 75-79: Parsing the Layer Routing table to dict."""

    def test_parses_layer_routing_as_dict(self, layer_routing_table):
        column_map = {"Layer": "key", "Destination": "value"}
        result = parse_table(layer_routing_table, dict, column_map)
        assert isinstance(result, dict)
        assert result["behaviour"] == "output/train.jsonl"
        assert result["knowledge"] == "output/rag_index/knowledge.jsonl"


# ---------------------------------------------------------------------------
# parse_table — Formatting Edge Cases
# ---------------------------------------------------------------------------


class TestParseTableFormatting:
    """BDD Scenario 237-241: Formatting variations."""

    def test_handles_inconsistent_alignment(self, source_documents_column_map):
        """AC: handles inconsistent column alignment and trailing whitespace."""
        table = (
            "|  File Pattern  |  Mode  |  Notes  |\n"
            "| --- | --- | --- |\n"
            "|mr-bruff-*.pdf  |standard  | Digital PDFs   |\n"
        )
        result = parse_table(table, SourceDocument, source_documents_column_map)
        assert len(result) == 1
        assert result[0].file_pattern == "mr-bruff-*.pdf"
        assert result[0].mode == "standard"
        assert result[0].notes == "Digital PDFs"

    def test_trims_all_cell_values(self, source_documents_column_map):
        """AC: trims all cell values."""
        table = (
            "| File Pattern | Mode | Notes |\n"
            "|---|---|---|\n"
            "|  extra-spaces.pdf  |  standard  |  some notes  |\n"
        )
        result = parse_table(table, SourceDocument, source_documents_column_map)
        assert result[0].file_pattern == "extra-spaces.pdf"
        assert result[0].mode == "standard"
        assert result[0].notes == "some notes"

    def test_handles_missing_trailing_pipe(self, source_documents_column_map):
        """AC: handles missing trailing pipes in table rows."""
        table = (
            "| File Pattern | Mode | Notes |\n|---|---|---|\n| no-trailing.pdf | standard | notes\n"
        )
        result = parse_table(table, SourceDocument, source_documents_column_map)
        assert len(result) == 1
        assert result[0].file_pattern == "no-trailing.pdf"

    def test_skips_separator_row(self, source_documents_column_map):
        """AC: skips the separator row (|---|---|)."""
        table = (
            "| File Pattern | Mode | Notes |\n"
            "|:---:|:---:|:---:|\n"
            "| file.pdf | standard | notes |\n"
        )
        result = parse_table(table, SourceDocument, source_documents_column_map)
        assert len(result) == 1
        assert result[0].file_pattern == "file.pdf"

    def test_empty_table_returns_empty_list(self, source_documents_column_map):
        """Table with only header and separator, no data rows."""
        table = "| File Pattern | Mode | Notes |\n|---|---|---|\n"
        result = parse_table(table, SourceDocument, source_documents_column_map)
        assert result == []

    def test_extra_blank_lines_ignored(self, source_documents_column_map):
        """Tables may have blank lines around them."""
        table = (
            "\n\n"
            "| File Pattern | Mode | Notes |\n"
            "|---|---|---|\n"
            "| file.pdf | standard | notes |\n"
            "\n\n"
        )
        result = parse_table(table, SourceDocument, source_documents_column_map)
        assert len(result) == 1

    def test_weight_without_percent_sign(self):
        """Weight given as plain decimal should also work."""
        table = (
            "| Criterion | Description | Weight |\n|---|---|---|\n| accuracy | Correct | 0.5 |\n"
        )
        column_map = {
            "Criterion": "name",
            "Description": "description",
            "Weight": "weight",
        }
        result = parse_table(table, EvaluationCriterion, column_map)
        assert result[0].weight == 0.5


# ---------------------------------------------------------------------------
# extract_json — Happy Path
# ---------------------------------------------------------------------------


class TestExtractJsonHappyPath:
    """BDD Scenarios 66-71: Parsing the Output Schema section."""

    def test_extracts_valid_json_block(self, valid_json_section):
        """AC: finds the first ```json block and parses it."""
        result = extract_json(valid_json_section)
        assert isinstance(result, dict)
        assert "messages" in result
        assert "metadata" in result

    def test_messages_key_structure(self, valid_json_section):
        result = extract_json(valid_json_section)
        assert isinstance(result["messages"], list)
        assert len(result["messages"]) == 1
        assert result["messages"][0]["role"] == "system"

    def test_metadata_key_structure(self, valid_json_section):
        result = extract_json(valid_json_section)
        assert isinstance(result["metadata"], dict)
        assert result["metadata"]["layer"] == "behaviour"

    def test_required_keys_validated(self):
        """AC: validates required top-level keys (messages, metadata)."""
        section = '```json\n{"only_one_key": true}\n```\n'
        with pytest.raises(GoalValidationError) as exc_info:
            extract_json(section)
        assert (
            "messages" in str(exc_info.value).lower() or "metadata" in str(exc_info.value).lower()
        )

    def test_missing_messages_key_raises(self):
        section = '```json\n{"metadata": {}}\n```\n'
        with pytest.raises(GoalValidationError):
            extract_json(section)

    def test_missing_metadata_key_raises(self):
        section = '```json\n{"messages": []}\n```\n'
        with pytest.raises(GoalValidationError):
            extract_json(section)


# ---------------------------------------------------------------------------
# extract_json — Edge Cases
# ---------------------------------------------------------------------------


class TestExtractJsonEdgeCases:
    """BDD Scenarios 309-314: Nested code fences and backtick handling."""

    def test_handles_backticks_in_json_strings(self):
        """AC: handles string values containing backticks within the JSON."""
        section = (
            "```json\n"
            "{\n"
            '  "messages": [{"role": "user", "content": "Use `code` here"}],\n'
            '  "metadata": {"note": "has `backtick` values"}\n'
            "}\n"
            "```\n"
        )
        result = extract_json(section)
        assert "`code`" in result["messages"][0]["content"]
        assert "`backtick`" in result["metadata"]["note"]

    def test_finds_first_json_block_when_multiple_present(self):
        """Only the first ```json block should be used."""
        section = (
            "```json\n"
            '{"messages": [{"role": "system", "content": "first"}], "metadata": {}}\n'
            "```\n"
            "\n"
            "```json\n"
            '{"messages": [{"role": "system", "content": "second"}], "metadata": {}}\n'
            "```\n"
        )
        result = extract_json(section)
        assert result["messages"][0]["content"] == "first"

    def test_json_block_with_surrounding_text(self):
        """JSON block buried in other text content."""
        section = (
            "Here is the output schema:\n"
            "\n"
            "The following JSON defines the structure:\n"
            "\n"
            "```json\n"
            '{"messages": [], "metadata": {}}\n'
            "```\n"
            "\n"
            "Additional notes here.\n"
        )
        result = extract_json(section)
        assert "messages" in result
        assert "metadata" in result


# ---------------------------------------------------------------------------
# extract_json — Error Cases
# ---------------------------------------------------------------------------


class TestExtractJsonErrors:
    """Negative cases for extract_json."""

    def test_no_json_block_raises_goal_validation_error(self):
        """AC: raises GoalValidationError for missing JSON block."""
        section = "No code block here, just plain text."
        with pytest.raises(GoalValidationError) as exc_info:
            extract_json(section)
        assert "Output Schema" in exc_info.value.section

    def test_malformed_json_raises_goal_validation_error(self):
        """AC: raises GoalValidationError for malformed JSON with descriptive message."""
        section = '```json\n{"messages": [broken json}\n```\n'
        with pytest.raises(GoalValidationError) as exc_info:
            extract_json(section)
        assert "Output Schema" in exc_info.value.section

    def test_empty_json_block_raises(self):
        """Empty code block should raise."""
        section = "```json\n```\n"
        with pytest.raises(GoalValidationError):
            extract_json(section)

    def test_error_message_is_descriptive(self):
        """Error message should help the user understand what went wrong."""
        section = "No JSON here."
        with pytest.raises(GoalValidationError) as exc_info:
            extract_json(section)
        assert len(exc_info.value.message) > 10  # not a trivial message


# ---------------------------------------------------------------------------
# Import contract for parser module
# ---------------------------------------------------------------------------


class TestParserImports:
    """Verify parse_table, extract_json, and split_sections are importable."""

    def test_parse_table_importable(self):
        from domain_config.parser import parse_table

        assert callable(parse_table)

    def test_extract_json_importable(self):
        from domain_config.parser import extract_json

        assert callable(extract_json)

    def test_split_sections_importable(self):
        from domain_config.parser import split_sections

        assert callable(split_sections)


# ---------------------------------------------------------------------------
# Fixtures for split_sections
# ---------------------------------------------------------------------------

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


def _build_goal_md(sections: list[tuple[str, str]]) -> str:
    """Build a minimal GOAL.md string from (heading, body) pairs."""
    parts = []
    for heading, body in sections:
        parts.append(f"## {heading}\n{body}")
    return "\n".join(parts)


@pytest.fixture
def valid_goal_md() -> str:
    """A well-formed GOAL.md with all 9 sections."""
    return _build_goal_md([(name, f"Content for {name}.\n") for name in REQUIRED_SECTIONS])


@pytest.fixture
def minimal_goal_md() -> str:
    """Minimal GOAL.md with very short bodies."""
    return _build_goal_md([(name, "x" * 100 + "\n") for name in REQUIRED_SECTIONS])


# ---------------------------------------------------------------------------
# split_sections — Happy Path (BDD Scenarios 21-25)
# ---------------------------------------------------------------------------


class TestSplitSectionsHappyPath:
    """AC: Splits on known section headings, returns dict[str, str]."""

    def test_returns_dict_with_nine_keys(self, valid_goal_md):
        result = split_sections(valid_goal_md)
        assert isinstance(result, dict)
        assert len(result) == 9

    def test_all_required_keys_present(self, valid_goal_md):
        result = split_sections(valid_goal_md)
        for name in REQUIRED_SECTIONS:
            assert name in result, f"Missing key: {name}"

    def test_section_body_is_string(self, valid_goal_md):
        result = split_sections(valid_goal_md)
        for name in REQUIRED_SECTIONS:
            assert isinstance(result[name], str)

    def test_section_body_content_correct(self, valid_goal_md):
        result = split_sections(valid_goal_md)
        assert "Content for Goal." in result["Goal"]
        assert "Content for Layer Routing." in result["Layer Routing"]

    def test_section_bodies_stripped(self, valid_goal_md):
        result = split_sections(valid_goal_md)
        for name, body in result.items():
            assert body == body.strip(), f"Section '{name}' body not stripped"


# ---------------------------------------------------------------------------
# split_sections — Whitespace Variations (BDD Scenarios 229-234)
# ---------------------------------------------------------------------------


class TestSplitSectionsWhitespace:
    """AC: Handles inconsistent whitespace around headings."""

    def test_extra_blank_lines_around_headings(self):
        """Extra blank lines before/after headings should not break parsing."""
        content = "\n\n## Goal\n\nGoal body.\n\n\n## Source Documents\n\nDocs body.\n"
        # Add remaining sections
        for name in REQUIRED_SECTIONS[2:]:
            content += f"\n\n## {name}\n\n{name} body.\n"
        result = split_sections(content)
        assert "Goal body." in result["Goal"]
        assert "Docs body." in result["Source Documents"]

    def test_trailing_spaces_on_heading_line(self):
        """Headings with trailing spaces should still be recognised."""
        content = ""
        for name in REQUIRED_SECTIONS:
            content += f"## {name}   \n{name} body.\n"
        result = split_sections(content)
        assert len(result) == 9

    def test_no_blank_line_between_heading_and_body(self):
        """Body text immediately following heading (no blank line) is valid."""
        content = ""
        for name in REQUIRED_SECTIONS:
            content += f"## {name}\nImmediate body for {name}.\n"
        result = split_sections(content)
        assert "Immediate body for Goal." in result["Goal"]


# ---------------------------------------------------------------------------
# split_sections — Embedded Headings (BDD Scenarios 272-277)
# ---------------------------------------------------------------------------


class TestSplitSectionsEmbeddedHeadings:
    """AC: Embedded ## headings within section content are preserved as content."""

    def test_embedded_h2_not_treated_as_boundary(self):
        """An ## heading that is NOT one of the 9 known sections stays as body content."""
        content = "## Goal\nThe goal.\n## Sub-heading within Goal\nMore goal content.\n"
        for name in REQUIRED_SECTIONS[1:]:
            content += f"## {name}\n{name} body.\n"
        result = split_sections(content)
        assert "## Sub-heading within Goal" in result["Goal"]
        assert "More goal content." in result["Goal"]

    def test_embedded_h3_preserved_in_body(self):
        """### headings inside sections are always preserved as content."""
        content = "## Goal\n### Sub-subsection\nNested content.\n"
        for name in REQUIRED_SECTIONS[1:]:
            content += f"## {name}\n{name} body.\n"
        result = split_sections(content)
        assert "### Sub-subsection" in result["Goal"]
        assert "Nested content." in result["Goal"]

    def test_embedded_heading_matching_section_name_in_content(self):
        """An ## heading that matches a known section name inside body content of another section.

        This is a tricky edge case: if Goal section body contains '## Source Documents' as text,
        it should be treated as a new section boundary (this is the whitelist approach).
        """
        content = "## Goal\nSome goal text.\n## Source Documents\nDocs body.\n"
        for name in REQUIRED_SECTIONS[2:]:
            content += f"## {name}\n{name} body.\n"
        result = split_sections(content)
        # "Some goal text." should be in Goal, "Docs body." in Source Documents
        assert "Some goal text." in result["Goal"]
        assert "Docs body." in result["Source Documents"]


# ---------------------------------------------------------------------------
# split_sections — Missing Sections (BDD Scenarios 146-162)
# ---------------------------------------------------------------------------


class TestSplitSectionsMissing:
    """AC: Raises GoalValidationError identifying each missing section."""

    def test_one_missing_section_raises(self):
        """Missing a single section raises GoalValidationError."""
        content = _build_goal_md(
            [(name, f"{name} body.\n") for name in REQUIRED_SECTIONS if name != "Layer Routing"]
        )
        with pytest.raises(GoalValidationError) as exc_info:
            split_sections(content)
        assert "Layer Routing" in str(exc_info.value)

    def test_multiple_missing_sections_all_reported(self):
        """AC: Reports ALL missing sections at once (not just the first)."""
        missing = {"Goal", "Output Schema", "Layer Routing"}
        content = _build_goal_md(
            [(name, f"{name} body.\n") for name in REQUIRED_SECTIONS if name not in missing]
        )
        with pytest.raises(GoalValidationError) as exc_info:
            split_sections(content)
        error_msg = str(exc_info.value)
        for name in missing:
            assert name in error_msg, f"Missing section '{name}' not mentioned in error"

    def test_missing_section_error_is_goal_validation_error(self):
        content = _build_goal_md([(name, f"{name} body.\n") for name in REQUIRED_SECTIONS[:5]])
        with pytest.raises(GoalValidationError):
            split_sections(content)


# ---------------------------------------------------------------------------
# split_sections — Empty File (BDD Scenarios 220-224)
# ---------------------------------------------------------------------------


class TestSplitSectionsEmptyFile:
    """AC: Empty GOAL.md raises error indicating no sections found."""

    def test_empty_string_raises(self):
        with pytest.raises(GoalValidationError) as exc_info:
            split_sections("")
        assert (
            "no sections found" in str(exc_info.value).lower()
            or "missing" in str(exc_info.value).lower()
        )

    def test_whitespace_only_raises(self):
        with pytest.raises(GoalValidationError):
            split_sections("   \n\n  \n")

    def test_content_without_any_known_headings_raises(self):
        """Content with text but no known ## headings raises."""
        with pytest.raises(GoalValidationError):
            split_sections("Some random text\nwithout any headings.\n")


# ---------------------------------------------------------------------------
# split_sections — Unicode
# ---------------------------------------------------------------------------


class TestSplitSectionsUnicode:
    """AC: Unicode content preserved exactly."""

    def test_unicode_content_preserved(self):
        unicode_body = "This section has émojis: 🎓📚 and accented chars: café, naïve.\n"
        content = ""
        for name in REQUIRED_SECTIONS:
            if name == "Goal":
                content += f"## {name}\n{unicode_body}"
            else:
                content += f"## {name}\n{name} body.\n"
        result = split_sections(content)
        assert "émojis: 🎓📚" in result["Goal"]
        assert "café" in result["Goal"]
        assert "naïve" in result["Goal"]


# ---------------------------------------------------------------------------
# split_sections — Seam Test (integration contract)
# ---------------------------------------------------------------------------


@pytest.mark.seam
@pytest.mark.integration_contract("SECTION_DICT")
class TestSectionDictContract:
    """Seam test: verify split_sections output contract.

    Contract: dict[str, str] with exactly 9 keys.
    Producer: TASK-DC-002
    """

    def test_section_dict_keys(self):
        content = "\n".join(
            f"## {name}\n{'x' * 100}"
            for name in [
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
        )
        result = split_sections(content)
        assert isinstance(result, dict)
        assert len(result) == 9
        assert "Goal" in result
        assert "Layer Routing" in result
