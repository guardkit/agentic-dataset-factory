"""Tests for domain_config.parser — parse_table() and extract_json().

TDD: RED phase — these tests define the expected behaviour for TASK-DC-003.
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
from domain_config.parser import extract_json, parse_table


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
    """Verify parse_table and extract_json are importable."""

    def test_parse_table_importable(self):
        from domain_config.parser import parse_table

        assert callable(parse_table)

    def test_extract_json_importable(self):
        from domain_config.parser import extract_json

        assert callable(extract_json)
