"""Integration tests for parse_goal_md() — the public API for GOAL.md parsing.

TDD: RED phase — these tests define the expected behaviour for TASK-DC-005.
Covers all 36 BDD scenarios from features/domain-config/domain-config.feature
via the top-level parse_goal_md(goal_path) entry point.

Organisation:
- GoalMdBuilder: helper to construct GOAL.md variants for readable test setup
- TestParseGoalMdHappyPath: Group A key examples (BDD lines 21-79)
- TestParseGoalMdBoundary: Group B boundary conditions (BDD lines 84-140)
- TestParseGoalMdNegative: Group C negative cases (BDD lines 146-224)
- TestParseGoalMdEdgeCases: Group D edge cases (BDD lines 229-322)
- TestPublicApiExports: AC-005 export verification
"""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from domain_config import GoalConfig, GoalValidationError, parse_goal_md
from domain_config.models import (
    EvaluationCriterion,
    GenerationTarget,
    MetadataField,
    SourceDocument,
)


# ---------------------------------------------------------------------------
# GoalMdBuilder — readable test construction helper
# ---------------------------------------------------------------------------


class GoalMdBuilder:
    """Builder for GOAL.md content strings.

    Produces valid GOAL.md by default. Call ``.without_section(name)``
    or ``.with_<section>(text)`` to create variants for negative/boundary tests.
    """

    _DEFAULT_GOAL = (
        "Fine-tune a GCSE English Literature tutor that guides Year 10 "
        "students through AQA exam preparation using Socratic questioning "
        "and mark-scheme-aligned feedback."
    )

    _DEFAULT_SOURCE_DOCS = (
        "| File Pattern | Mode | Notes |\n"
        "|---|---|---|\n"
        "| mr-bruff-*.pdf | standard | Digital PDFs |\n"
        "| scanned-*.pdf | vlm | Scanned pages |\n"
    )

    _DEFAULT_SYSTEM_PROMPT = (
        "You are a GCSE English Literature tutor specialising in AQA exam "
        "preparation. Guide Year 10 students through poetry, prose, and "
        "drama analysis using Socratic questioning. Always reference "
        "assessment objectives and mark scheme criteria in your responses."
    )

    _DEFAULT_GEN_TARGETS = (
        "| Category | Type | Count |\n"
        "|---|---|---|\n"
        "| Literary analysis (single-turn) | reasoning | 200 |\n"
        "| Essay feedback (multi-turn) | reasoning | 250 |\n"
        "| Exam technique guidance | reasoning | 150 |\n"
        "| Poetry comparative questions | reasoning | 150 |\n"
        "| Factual recall / character / plot | direct | 100 |\n"
        "| Terminology definitions | direct | 75 |\n"
        "| Encouragement / session mgmt | direct | 75 |\n"
    )

    _DEFAULT_GEN_GUIDELINES = (
        "Generate training examples that demonstrate Socratic questioning "
        "technique for GCSE English Literature. Each example should reference "
        "specific texts from the AQA syllabus and align responses with "
        "assessment objectives (AO1-AO6). Use age-appropriate language."
    )

    _DEFAULT_EVAL_CRITERIA = (
        "| Criterion | Description | Weight |\n"
        "|---|---|---|\n"
        "| socratic_approach | Guides via questions rather than giving answers | 25% |\n"
        "| ao_accuracy | Correct application of assessment objectives | 25% |\n"
        "| mark_scheme_aligned | Analysis aligns with AQA marking criteria | 20% |\n"
        "| age_appropriate | Language suitable for Year 10 student | 15% |\n"
        "| factual_accuracy | No incorrect claims about texts or context | 15% |\n"
    )

    _DEFAULT_OUTPUT_SCHEMA = textwrap.dedent("""\
        ```json
        {
          "messages": [
            {"role": "system", "content": "You are a tutor."},
            {"role": "user", "content": "student msg"},
            {"role": "assistant", "content": "tutor response"}
          ],
          "metadata": {
            "layer": "behaviour",
            "type": "reasoning"
          }
        }
        ```
    """)

    _DEFAULT_METADATA_SCHEMA = (
        "| Field | Type | Required | Valid Values |\n"
        "|---|---|---|---|\n"
        "| layer | string | yes | behaviour, knowledge |\n"
        "| type | string | yes | reasoning, direct |\n"
        "| ao | array[string] | yes | AO1, AO2, AO3 |\n"
        "| text | string | yes | macbeth, a_christmas_carol |\n"
        "| topic | string | yes | character_analysis, essay_feedback |\n"
        "| grade_target | integer or null | yes | 4, 5, 6, 7, 8, 9 |\n"
        "| source | string | yes | synthetic, aqa_derived |\n"
        "| turns | integer | yes | |\n"
    )

    _DEFAULT_LAYER_ROUTING = (
        "| Layer | Destination |\n"
        "|---|---|\n"
        "| behaviour | output/train.jsonl |\n"
        "| knowledge | output/rag_index/knowledge.jsonl |\n"
    )

    _SECTION_ORDER = [
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

    def __init__(self) -> None:
        self._sections: dict[str, str] = {
            "Goal": self._DEFAULT_GOAL,
            "Source Documents": self._DEFAULT_SOURCE_DOCS,
            "System Prompt": self._DEFAULT_SYSTEM_PROMPT,
            "Generation Targets": self._DEFAULT_GEN_TARGETS,
            "Generation Guidelines": self._DEFAULT_GEN_GUIDELINES,
            "Evaluation Criteria": self._DEFAULT_EVAL_CRITERIA,
            "Output Schema": self._DEFAULT_OUTPUT_SCHEMA,
            "Metadata Schema": self._DEFAULT_METADATA_SCHEMA,
            "Layer Routing": self._DEFAULT_LAYER_ROUTING,
        }

    def with_goal(self, text: str) -> GoalMdBuilder:
        self._sections["Goal"] = text
        return self

    def with_source_documents(self, text: str) -> GoalMdBuilder:
        self._sections["Source Documents"] = text
        return self

    def with_system_prompt(self, text: str) -> GoalMdBuilder:
        self._sections["System Prompt"] = text
        return self

    def with_generation_targets(self, text: str) -> GoalMdBuilder:
        self._sections["Generation Targets"] = text
        return self

    def with_generation_guidelines(self, text: str) -> GoalMdBuilder:
        self._sections["Generation Guidelines"] = text
        return self

    def with_evaluation_criteria(self, text: str) -> GoalMdBuilder:
        self._sections["Evaluation Criteria"] = text
        return self

    def with_output_schema(self, text: str) -> GoalMdBuilder:
        self._sections["Output Schema"] = text
        return self

    def with_metadata_schema(self, text: str) -> GoalMdBuilder:
        self._sections["Metadata Schema"] = text
        return self

    def with_layer_routing(self, text: str) -> GoalMdBuilder:
        self._sections["Layer Routing"] = text
        return self

    def without_section(self, name: str) -> GoalMdBuilder:
        self._sections.pop(name, None)
        return self

    def build(self) -> str:
        """Render the GOAL.md markdown string."""
        parts: list[str] = []
        for section_name in self._SECTION_ORDER:
            if section_name in self._sections:
                parts.append(f"## {section_name}\n\n{self._sections[section_name]}")
        return "\n\n".join(parts) + "\n"

    def write_to(self, path: Path) -> Path:
        """Write the built GOAL.md to disk and return the path."""
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.build(), encoding="utf-8")
        return path


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def valid_goal_path() -> Path:
    """Path to the pre-built valid GOAL.md fixture."""
    return FIXTURES_DIR / "valid_goal.md"


@pytest.fixture
def tmp_goal(tmp_path: Path) -> Path:
    """Return a path for a temporary GOAL.md file."""
    return tmp_path / "GOAL.md"


@pytest.fixture
def builder() -> GoalMdBuilder:
    """Return a fresh GoalMdBuilder with all defaults."""
    return GoalMdBuilder()


# ---------------------------------------------------------------------------
# Group A: Key Examples (BDD lines 21-79)
# ---------------------------------------------------------------------------


class TestParseGoalMdHappyPath:
    """Integration tests for the happy-path parse flow."""

    # BDD: Scenario lines 21-25
    def test_valid_goal_md_returns_complete_goal_config(
        self, valid_goal_path: Path
    ) -> None:
        """Parsing a valid GOAL.md produces a complete GoalConfig."""
        config = parse_goal_md(valid_goal_path)

        assert isinstance(config, GoalConfig)
        assert config.goal  # non-empty
        assert len(config.source_documents) >= 1
        assert config.system_prompt  # non-empty
        assert len(config.generation_targets) >= 1
        assert config.generation_guidelines  # non-empty
        assert len(config.evaluation_criteria) >= 3
        assert isinstance(config.output_schema, dict)
        assert len(config.metadata_schema) >= 1
        assert isinstance(config.layer_routing, dict)

    # BDD: Scenario lines 28-32
    def test_goal_section_parsed_as_free_text(
        self, valid_goal_path: Path
    ) -> None:
        """The Goal section contains the full text of the Goal section."""
        config = parse_goal_md(valid_goal_path)

        assert "GCSE English Literature tutor" in config.goal
        assert len(config.goal) >= 50

    # BDD: Scenario lines 36-40
    def test_source_documents_parsed_as_structured_data(
        self, valid_goal_path: Path
    ) -> None:
        """Each row is a SourceDocument with file_pattern, mode, and notes."""
        config = parse_goal_md(valid_goal_path)

        assert len(config.source_documents) == 3
        for doc in config.source_documents:
            assert isinstance(doc, SourceDocument)
            assert doc.file_pattern
            assert doc.mode in ("standard", "vlm")

    # BDD: Scenario lines 44-47
    def test_system_prompt_preserved_exactly(
        self, valid_goal_path: Path
    ) -> None:
        """System prompt is preserved as exact text."""
        config = parse_goal_md(valid_goal_path)

        assert "GCSE English Literature tutor" in config.system_prompt
        assert len(config.system_prompt) >= 100

    # BDD: Scenario lines 50-55
    def test_generation_targets_parsed(
        self, valid_goal_path: Path
    ) -> None:
        """Each row is a GenerationTarget with category, type, and count."""
        config = parse_goal_md(valid_goal_path)

        assert len(config.generation_targets) == 7
        for target in config.generation_targets:
            assert isinstance(target, GenerationTarget)
            assert target.type in ("reasoning", "direct")
            assert target.count >= 1

    # BDD: Scenario lines 58-63
    def test_evaluation_criteria_parsed(
        self, valid_goal_path: Path
    ) -> None:
        """Each row is an EvaluationCriterion with valid Python identifiers."""
        config = parse_goal_md(valid_goal_path)

        assert len(config.evaluation_criteria) == 5
        for criterion in config.evaluation_criteria:
            assert isinstance(criterion, EvaluationCriterion)
            assert criterion.name.isidentifier()

    # BDD: Scenario lines 66-71
    def test_output_schema_parsed_as_dict(
        self, valid_goal_path: Path
    ) -> None:
        """Output schema is a valid dict with messages and metadata keys."""
        config = parse_goal_md(valid_goal_path)

        assert isinstance(config.output_schema, dict)
        assert "messages" in config.output_schema
        assert "metadata" in config.output_schema

    # BDD: Scenario lines 75-79
    def test_layer_routing_parsed(
        self, valid_goal_path: Path
    ) -> None:
        """Layer routing maps behaviour and knowledge to destinations."""
        config = parse_goal_md(valid_goal_path)

        assert "behaviour" in config.layer_routing
        assert "knowledge" in config.layer_routing
        assert config.layer_routing["behaviour"]
        assert config.layer_routing["knowledge"]

    def test_metadata_schema_parsed(
        self, valid_goal_path: Path
    ) -> None:
        """Metadata schema is parsed into MetadataField instances."""
        config = parse_goal_md(valid_goal_path)

        assert len(config.metadata_schema) >= 1
        for field in config.metadata_schema:
            assert isinstance(field, MetadataField)
            assert field.field
            assert field.type


# ---------------------------------------------------------------------------
# Group B: Boundary Conditions (BDD lines 84-140)
# ---------------------------------------------------------------------------


class TestParseGoalMdBoundary:
    """Boundary condition tests for parse_goal_md()."""

    # BDD: Scenario lines 84-88 — Goal at exactly 50 chars passes
    def test_goal_exactly_50_chars_passes(
        self, builder: GoalMdBuilder, tmp_goal: Path
    ) -> None:
        goal_text = "A" * 50
        path = builder.with_goal(goal_text).write_to(tmp_goal)
        config = parse_goal_md(path)
        assert config.goal == goal_text

    # BDD: Scenario lines 91-96 — Goal at 49 chars fails
    def test_goal_49_chars_fails(
        self, builder: GoalMdBuilder, tmp_goal: Path
    ) -> None:
        goal_text = "A" * 49
        path = builder.with_goal(goal_text).write_to(tmp_goal)
        with pytest.raises(GoalValidationError) as exc_info:
            parse_goal_md(path)
        assert "Goal" in str(exc_info.value)

    # BDD: Scenario lines 98-103 — System Prompt at 100 chars passes
    def test_system_prompt_exactly_100_chars_passes(
        self, builder: GoalMdBuilder, tmp_goal: Path
    ) -> None:
        prompt_text = "B" * 100
        path = builder.with_system_prompt(prompt_text).write_to(tmp_goal)
        config = parse_goal_md(path)
        assert config.system_prompt == prompt_text

    # BDD: Scenario lines 105-110 — System Prompt at 99 chars fails
    def test_system_prompt_99_chars_fails(
        self, builder: GoalMdBuilder, tmp_goal: Path
    ) -> None:
        prompt_text = "B" * 99
        path = builder.with_system_prompt(prompt_text).write_to(tmp_goal)
        with pytest.raises(GoalValidationError) as exc_info:
            parse_goal_md(path)
        assert "System Prompt" in str(exc_info.value)

    # BDD: Scenario lines 113-117 — Generation Guidelines at 100 chars passes
    def test_generation_guidelines_exactly_100_chars_passes(
        self, builder: GoalMdBuilder, tmp_goal: Path
    ) -> None:
        guidelines_text = "C" * 100
        path = builder.with_generation_guidelines(guidelines_text).write_to(tmp_goal)
        config = parse_goal_md(path)
        assert config.generation_guidelines == guidelines_text

    # BDD: Scenario lines 119-124 — Exactly 3 evaluation criteria passes
    def test_exactly_3_evaluation_criteria_passes(
        self, builder: GoalMdBuilder, tmp_goal: Path
    ) -> None:
        table = (
            "| Criterion | Description | Weight |\n"
            "|---|---|---|\n"
            "| criterion_a | Description A | 40% |\n"
            "| criterion_b | Description B | 30% |\n"
            "| criterion_c | Description C | 30% |\n"
        )
        path = builder.with_evaluation_criteria(table).write_to(tmp_goal)
        config = parse_goal_md(path)
        assert len(config.evaluation_criteria) == 3

    # BDD: Scenario lines 127-132 — Only 2 evaluation criteria fails
    def test_only_2_evaluation_criteria_fails(
        self, builder: GoalMdBuilder, tmp_goal: Path
    ) -> None:
        table = (
            "| Criterion | Description | Weight |\n"
            "|---|---|---|\n"
            "| criterion_a | Description A | 50% |\n"
            "| criterion_b | Description B | 50% |\n"
        )
        path = builder.with_evaluation_criteria(table).write_to(tmp_goal)
        with pytest.raises(GoalValidationError) as exc_info:
            parse_goal_md(path)
        assert "Evaluation Criteria" in str(exc_info.value)

    # BDD: Scenario lines 137-140 — Exactly 70% reasoning passes
    def test_exactly_70_percent_reasoning_passes(
        self, builder: GoalMdBuilder, tmp_goal: Path
    ) -> None:
        table = (
            "| Category | Type | Count |\n"
            "|---|---|---|\n"
            "| Analysis | reasoning | 70 |\n"
            "| Recall | direct | 30 |\n"
        )
        path = builder.with_generation_targets(table).write_to(tmp_goal)
        config = parse_goal_md(path)
        reasoning_count = sum(
            t.count for t in config.generation_targets if t.type == "reasoning"
        )
        total = sum(t.count for t in config.generation_targets)
        assert reasoning_count / total * 100 >= 70

    # Below 70% reasoning — 69% fails
    def test_69_percent_reasoning_fails(
        self, builder: GoalMdBuilder, tmp_goal: Path
    ) -> None:
        table = (
            "| Category | Type | Count |\n"
            "|---|---|---|\n"
            "| Analysis | reasoning | 69 |\n"
            "| Recall | direct | 31 |\n"
        )
        path = builder.with_generation_targets(table).write_to(tmp_goal)
        with pytest.raises(GoalValidationError) as exc_info:
            parse_goal_md(path)
        assert "Generation Targets" in str(exc_info.value)


# ---------------------------------------------------------------------------
# Group C: Negative Cases (BDD lines 146-224)
# ---------------------------------------------------------------------------


class TestParseGoalMdNegative:
    """Negative case tests for parse_goal_md()."""

    # BDD: Scenario lines 146-162 — Missing each required section
    @pytest.mark.parametrize(
        "section",
        [
            "Goal",
            "Source Documents",
            "System Prompt",
            "Generation Targets",
            "Generation Guidelines",
            "Evaluation Criteria",
            "Output Schema",
            "Metadata Schema",
            "Layer Routing",
        ],
    )
    def test_missing_section_raises_validation_error(
        self, section: str, builder: GoalMdBuilder, tmp_goal: Path
    ) -> None:
        path = builder.without_section(section).write_to(tmp_goal)
        with pytest.raises(GoalValidationError) as exc_info:
            parse_goal_md(path)
        assert section in str(exc_info.value)

    # BDD: Scenario lines 166-169 — File not found
    def test_file_not_found_raises_validation_error(self, tmp_path: Path) -> None:
        missing_path = tmp_path / "nonexistent" / "GOAL.md"
        with pytest.raises(GoalValidationError) as exc_info:
            parse_goal_md(missing_path)
        assert "not found" in str(exc_info.value).lower() or "File not found" in str(
            exc_info.value
        )

    # BDD: Scenario lines 172-177 — Invalid mode value
    def test_invalid_source_document_mode_raises_error(
        self, builder: GoalMdBuilder, tmp_goal: Path
    ) -> None:
        table = (
            "| File Pattern | Mode | Notes |\n"
            "|---|---|---|\n"
            "| scan.pdf | ocr | Bad mode |\n"
        )
        path = builder.with_source_documents(table).write_to(tmp_goal)
        with pytest.raises((GoalValidationError, Exception)):
            parse_goal_md(path)

    # BDD: Scenario lines 180-185 — Invalid Python identifier
    def test_invalid_criterion_identifier_raises_error(
        self, builder: GoalMdBuilder, tmp_goal: Path
    ) -> None:
        table = (
            "| Criterion | Description | Weight |\n"
            "|---|---|---|\n"
            "| socratic-approach | Guides via questions | 34% |\n"
            "| ao_accuracy | Correct AO application | 33% |\n"
            "| factual_accuracy | No incorrect claims | 33% |\n"
        )
        path = builder.with_evaluation_criteria(table).write_to(tmp_goal)
        with pytest.raises((GoalValidationError, Exception)):
            parse_goal_md(path)

    # BDD: Scenario lines 188-193 — Malformed JSON
    def test_malformed_json_raises_error(
        self, builder: GoalMdBuilder, tmp_goal: Path
    ) -> None:
        schema = textwrap.dedent("""\
            ```json
            { "messages": [, "metadata": {} }
            ```
        """)
        path = builder.with_output_schema(schema).write_to(tmp_goal)
        with pytest.raises(GoalValidationError) as exc_info:
            parse_goal_md(path)
        assert "Output Schema" in str(exc_info.value)

    # BDD: Scenario lines 196-201 — Missing required keys
    def test_output_schema_missing_messages_key_raises_error(
        self, builder: GoalMdBuilder, tmp_goal: Path
    ) -> None:
        schema = textwrap.dedent("""\
            ```json
            {
              "metadata": {"layer": "behaviour"}
            }
            ```
        """)
        path = builder.with_output_schema(schema).write_to(tmp_goal)
        with pytest.raises(GoalValidationError) as exc_info:
            parse_goal_md(path)
        assert "messages" in str(exc_info.value).lower()

    # BDD: Scenario lines 203-209 — Layer Routing missing knowledge
    def test_layer_routing_missing_knowledge_raises_error(
        self, builder: GoalMdBuilder, tmp_goal: Path
    ) -> None:
        table = (
            "| Layer | Destination |\n"
            "|---|---|\n"
            "| behaviour | output/train.jsonl |\n"
        )
        path = builder.with_layer_routing(table).write_to(tmp_goal)
        with pytest.raises(GoalValidationError) as exc_info:
            parse_goal_md(path)
        assert "knowledge" in str(exc_info.value).lower()

    # BDD: Scenario lines 211-217 — Reasoning below 70%
    def test_reasoning_below_70_percent_raises_error(
        self, builder: GoalMdBuilder, tmp_goal: Path
    ) -> None:
        table = (
            "| Category | Type | Count |\n"
            "|---|---|---|\n"
            "| Analysis | reasoning | 60 |\n"
            "| Recall | direct | 40 |\n"
        )
        path = builder.with_generation_targets(table).write_to(tmp_goal)
        with pytest.raises(GoalValidationError) as exc_info:
            parse_goal_md(path)
        assert "70%" in str(exc_info.value) or "reasoning" in str(
            exc_info.value
        ).lower()

    # BDD: Scenario lines 220-224 — Empty file
    def test_empty_file_raises_validation_error(
        self, tmp_goal: Path
    ) -> None:
        tmp_goal.parent.mkdir(parents=True, exist_ok=True)
        tmp_goal.write_text("", encoding="utf-8")
        with pytest.raises(GoalValidationError) as exc_info:
            parse_goal_md(tmp_goal)
        assert "No sections found" in str(exc_info.value) or "Missing" in str(
            exc_info.value
        )


# ---------------------------------------------------------------------------
# Group D: Edge Cases (BDD lines 229-322)
# ---------------------------------------------------------------------------


class TestParseGoalMdEdgeCases:
    """Edge case tests for parse_goal_md()."""

    # BDD: Scenario lines 229-234 — Whitespace variations
    def test_whitespace_variations_in_headings(
        self, builder: GoalMdBuilder, tmp_goal: Path
    ) -> None:
        """Headings with extra whitespace should still parse correctly."""
        content = builder.build()
        # Add extra blank lines between heading and content
        content = content.replace("## Goal\n\n", "## Goal  \n\n\n")
        content = content.replace(
            "## System Prompt\n\n", "## System Prompt\n\n\n\n"
        )
        tmp_goal.parent.mkdir(parents=True, exist_ok=True)
        tmp_goal.write_text(content, encoding="utf-8")
        config = parse_goal_md(tmp_goal)
        assert isinstance(config, GoalConfig)

    # BDD: Scenario lines 237-241 — Table formatting variations
    def test_table_formatting_variations(
        self, builder: GoalMdBuilder, tmp_goal: Path
    ) -> None:
        """Tables with inconsistent formatting should still parse."""
        table = (
            "|  File Pattern   |  Mode   |  Notes   |\n"
            "|---|---|---|\n"
            "|  mr-bruff-*.pdf   |  standard   |  Digital PDFs   |\n"
            "|scanned-*.pdf|vlm|Scanned pages|\n"
        )
        path = builder.with_source_documents(table).write_to(tmp_goal)
        config = parse_goal_md(path)
        assert len(config.source_documents) == 2
        assert config.source_documents[0].file_pattern == "mr-bruff-*.pdf"

    # BDD: Scenario lines 244-249 — Error includes section name
    def test_validation_error_includes_section_name(
        self, builder: GoalMdBuilder, tmp_goal: Path
    ) -> None:
        """Validation error identifies the specific failing section."""
        goal_text = "A" * 10  # Too short
        path = builder.with_goal(goal_text).write_to(tmp_goal)
        with pytest.raises(GoalValidationError) as exc_info:
            parse_goal_md(path)
        assert "Goal" in str(exc_info.value)

    # BDD: Scenario lines 253-260 — Multiple validation failures
    def test_multiple_validation_failures_reported_together(
        self, builder: GoalMdBuilder, tmp_goal: Path
    ) -> None:
        """Multiple failures are aggregated and reported together."""
        path = (
            builder.with_goal("A" * 10)  # Too short
            .with_system_prompt("B" * 10)  # Too short
            .with_evaluation_criteria(
                "| Criterion | Description | Weight |\n"
                "|---|---|---|\n"
                "| only_one | Single criterion | 100% |\n"
            )
            .write_to(tmp_goal)
        )
        with pytest.raises(GoalValidationError) as exc_info:
            parse_goal_md(path)
        error_msg = str(exc_info.value)
        # All three should be reported
        assert "Goal" in error_msg
        assert "System Prompt" in error_msg
        assert "Evaluation Criteria" in error_msg

    # BDD: Scenario lines 264-267 — Metadata all required=True
    def test_metadata_all_fields_required_true(
        self, valid_goal_path: Path
    ) -> None:
        """All MetadataField instances should have required=True."""
        config = parse_goal_md(valid_goal_path)
        for field in config.metadata_schema:
            assert field.required is True, (
                f"Field '{field.field}' should have required=True"
            )

    # BDD: Scenario lines 272-277 — Embedded headings
    def test_embedded_heading_not_treated_as_section(
        self, builder: GoalMdBuilder, tmp_goal: Path
    ) -> None:
        """Embedded ## headings within content should not create new sections."""
        guidelines = (
            "Generate training examples that demonstrate Socratic questioning "
            "technique for GCSE English Literature. Each example should reference "
            "specific texts from the AQA syllabus.\n\n"
            "## Example Approach\n\n"
            "Use open-ended questions that prompt students to think critically "
            "about the text. This is part of the Generation Guidelines content."
        )
        path = builder.with_generation_guidelines(guidelines).write_to(tmp_goal)
        config = parse_goal_md(path)
        assert "## Example Approach" in config.generation_guidelines

    # BDD: Scenario lines 280-286 — Python keyword as criterion name
    def test_python_keyword_criterion_name_raises_error(
        self, builder: GoalMdBuilder, tmp_goal: Path
    ) -> None:
        """Criterion named 'class' (a keyword) should raise error."""
        table = (
            "| Criterion | Description | Weight |\n"
            "|---|---|---|\n"
            "| class | Class-based criterion | 34% |\n"
            "| ao_accuracy | Correct AO application | 33% |\n"
            "| factual_accuracy | No incorrect claims | 33% |\n"
        )
        path = builder.with_evaluation_criteria(table).write_to(tmp_goal)
        with pytest.raises((GoalValidationError, Exception)):
            parse_goal_md(path)

    # BDD: Scenario lines 292-295 — Unicode characters
    def test_unicode_characters_preserved(
        self, builder: GoalMdBuilder, tmp_goal: Path
    ) -> None:
        """Unicode characters in content should be preserved exactly."""
        goal_text = (
            "Fine-tune a model that handles curly quotes \u201cliterature\u201d, "
            "em-dashes \u2014 and accented characters like caf\u00e9, na\u00efve, "
            "and r\u00e9sum\u00e9 correctly in all responses."
        )
        path = builder.with_goal(goal_text).write_to(tmp_goal)
        config = parse_goal_md(path)
        assert "\u201c" in config.goal
        assert "\u2014" in config.goal
        assert "caf\u00e9" in config.goal

    # BDD: Scenario lines 298-304 — Percentage mismatch (counts authoritative)
    def test_percentage_mismatch_uses_counts(
        self, builder: GoalMdBuilder, tmp_goal: Path
    ) -> None:
        """Counts are authoritative, not percentages. 75% reasoning passes."""
        table = (
            "| Category | Type | Count | % of total |\n"
            "|---|---|---|---|\n"
            "| Analysis | reasoning | 750 | 50% |\n"
            "| Recall | direct | 250 | 47% |\n"
        )
        path = builder.with_generation_targets(table).write_to(tmp_goal)
        config = parse_goal_md(path)
        # Counts: 750 reasoning / 1000 total = 75% (passes)
        # Even though listed percentages are wrong
        reasoning = sum(
            t.count for t in config.generation_targets if t.type == "reasoning"
        )
        total = sum(t.count for t in config.generation_targets)
        assert reasoning / total * 100 >= 70

    # BDD: Scenario lines 309-314 — Nested code fences in Output Schema
    def test_nested_code_fences_in_output_schema(
        self, builder: GoalMdBuilder, tmp_goal: Path
    ) -> None:
        """JSON with backtick-containing strings should parse correctly."""
        schema = (
            "```json\n"
            "{\n"
            '  "messages": [\n'
            '    {"role": "system", "content": "Use `markdown` in responses"}\n'
            "  ],\n"
            '  "metadata": {"layer": "behaviour"}\n'
            "}\n"
            "```\n"
        )
        path = builder.with_output_schema(schema).write_to(tmp_goal)
        config = parse_goal_md(path)
        assert "messages" in config.output_schema

    # BDD: Scenario lines 317-322 — Empty Valid Values column
    def test_empty_valid_values_column(
        self, builder: GoalMdBuilder, tmp_goal: Path
    ) -> None:
        """Fields with empty Valid Values produce empty lists."""
        table = (
            "| Field | Type | Required | Valid Values |\n"
            "|---|---|---|---|\n"
            "| layer | string | yes | behaviour, knowledge |\n"
            "| turns | integer | yes | |\n"
            "| source | string | yes | synthetic |\n"
        )
        path = builder.with_metadata_schema(table).write_to(tmp_goal)
        config = parse_goal_md(path)
        # Find the 'turns' field — should have empty valid_values
        turns_field = next(
            f for f in config.metadata_schema if f.field == "turns"
        )
        assert turns_field.valid_values == []


# ---------------------------------------------------------------------------
# Range Notation in _coerce_valid_values (TASK-TRF-028)
# ---------------------------------------------------------------------------


class TestCoerceValidValuesRangeNotation:
    """Unit tests for range notation detection in _coerce_valid_values."""

    def test_range_1_plus_returns_empty(self) -> None:
        from domain_config.parser import _coerce_valid_values

        assert _coerce_valid_values("1+") == []

    def test_range_0_plus_returns_empty(self) -> None:
        from domain_config.parser import _coerce_valid_values

        assert _coerce_valid_values("0+") == []

    def test_range_with_description_returns_empty(self) -> None:
        from domain_config.parser import _coerce_valid_values

        assert _coerce_valid_values("1+ (number of conversation turns)") == []

    def test_enum_still_works(self) -> None:
        from domain_config.parser import _coerce_valid_values

        assert _coerce_valid_values("behaviour, knowledge") == [
            "behaviour",
            "knowledge",
        ]

    def test_numeric_enum_still_works(self) -> None:
        from domain_config.parser import _coerce_valid_values

        assert _coerce_valid_values("4, 5, 6, 7, 8, 9, null") == [
            "4",
            "5",
            "6",
            "7",
            "8",
            "9",
            "null",
        ]

    def test_empty_returns_empty(self) -> None:
        from domain_config.parser import _coerce_valid_values

        assert _coerce_valid_values("") == []
        assert _coerce_valid_values("   ") == []

    def test_range_in_full_goal_parse(
        self, builder: GoalMdBuilder, tmp_goal: Path
    ) -> None:
        """Full GOAL.md parse produces turns.valid_values == [] for range notation."""
        table = (
            "| Field | Type | Required | Valid Values |\n"
            "|---|---|---|---|\n"
            "| layer | string | yes | behaviour, knowledge |\n"
            "| type | string | yes | reasoning, direct |\n"
            "| ao | array[string] | yes | AO1, AO2, AO3 |\n"
            "| text | string | yes | macbeth, a_christmas_carol |\n"
            "| topic | string | yes | character_analysis, essay_feedback |\n"
            "| grade_target | integer or null | yes | 4, 5, 6, 7, 8, 9 |\n"
            "| source | string | yes | synthetic, aqa_derived |\n"
            "| turns | integer | yes | 1+ (number of conversation turns) |\n"
        )
        path = builder.with_metadata_schema(table).write_to(tmp_goal)
        config = parse_goal_md(path)
        turns_field = next(
            f for f in config.metadata_schema if f.field == "turns"
        )
        assert turns_field.valid_values == []


# ---------------------------------------------------------------------------
# AC-005: Public API Exports
# ---------------------------------------------------------------------------


class TestPublicApiExports:
    """Verify that parse_goal_md is exported from domain_config."""

    def test_parse_goal_md_importable_from_package(self) -> None:
        """parse_goal_md should be importable from domain_config directly."""
        from domain_config import parse_goal_md as fn

        assert callable(fn)

    def test_goal_config_importable(self) -> None:
        from domain_config import GoalConfig as cls

        assert cls is not None

    def test_goal_validation_error_importable(self) -> None:
        from domain_config import GoalValidationError as cls

        assert cls is not None
