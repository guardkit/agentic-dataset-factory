"""Tests for domain_config.validators — cross-section validation and error aggregation.

TDD approach: tests verify cross-section validation rules and error aggregation.

The validator checks rules from two sources:
- Rules 1-3 (min-length): validated from the raw ``sections`` dict, since
  Pydantic model-level constraints on GoalConfig may prevent construction
  of invalid instances. This allows aggregation of all failures.
- Rules 4-10 (structural): validated from the ``parsed`` GoalConfig instance.

Note on Pydantic model constraints:
  GoalConfig enforces ``min_length=50`` on goal, ``min_length=100`` on
  system_prompt/generation_guidelines, and ``min_length=3`` on evaluation_criteria.
  These model-level constraints cannot produce invalid GoalConfig instances for
  testing. Therefore, length-based rules are validated from the sections dict
  and structural rules that overlap Pydantic constraints (e.g. criteria count)
  are tested via the validator's parallel check.

BDD Scenario coverage:
- 84-88: Goal 50 chars (boundary pass)
- 90-96: Goal 49 chars (boundary fail)
- 98-103: System Prompt 100 chars (boundary pass)
- 105-110: System Prompt 99 chars (boundary fail)
- 113-117: Guidelines 100 chars (boundary pass)
- 119-124: 3 criteria (boundary pass)
- 127-132: 2 criteria (boundary fail)
- 137-140: 70% reasoning (boundary pass)
- 172-177: invalid mode (negative — Pydantic-level)
- 203-209: missing knowledge row (negative)
- 211-217: below 70% reasoning (negative)
- 253-260: multiple failures aggregated (edge-case)
- 280-286: keyword as criterion (negative — Pydantic-level)
- 298-304: percentages advisory (edge-case)
"""

from __future__ import annotations

import pytest

from domain_config.models import (
    EvaluationCriterion,
    GenerationTarget,
    GoalConfig,
    GoalValidationError,
    MetadataField,
    SourceDocument,
)
from domain_config.validators import validate_goal_config


# ---------------------------------------------------------------------------
# Helpers — build valid sections and GoalConfig baselines
# ---------------------------------------------------------------------------


def _make_sections(
    *,
    goal: str = "A" * 50,
    system_prompt: str = "B" * 100,
    generation_guidelines: str = "C" * 100,
    source_documents: str = "has rows",
    evaluation_criteria: str = "has rows",
    output_schema: str = "has json",
    metadata_schema: str = "has rows",
    layer_routing: str = "has rows",
    generation_targets: str = "has rows",
) -> dict[str, str]:
    """Build a sections dict with customisable raw section bodies."""
    return {
        "Goal": goal,
        "Source Documents": source_documents,
        "System Prompt": system_prompt,
        "Generation Targets": generation_targets,
        "Generation Guidelines": generation_guidelines,
        "Evaluation Criteria": evaluation_criteria,
        "Output Schema": output_schema,
        "Metadata Schema": metadata_schema,
        "Layer Routing": layer_routing,
    }


def _make_parsed(
    *,
    source_documents: list[SourceDocument] | None = None,
    generation_targets: list[GenerationTarget] | None = None,
    evaluation_criteria: list[EvaluationCriterion] | None = None,
    output_schema: dict | None = None,
    metadata_schema: list[MetadataField] | None = None,
    layer_routing: dict[str, str] | None = None,
) -> GoalConfig:
    """Build a valid GoalConfig with customisable structural fields.

    All text fields use valid defaults (meeting Pydantic min_length).
    Structural fields can be overridden for testing rules 4-10.
    """
    if source_documents is None:
        source_documents = [
            SourceDocument(file_pattern="*.pdf", mode="standard", notes=""),
        ]
    if generation_targets is None:
        generation_targets = [
            GenerationTarget(category="reasoning_cat", type="reasoning", count=70),
            GenerationTarget(category="direct_cat", type="direct", count=30),
        ]
    if evaluation_criteria is None:
        evaluation_criteria = [
            EvaluationCriterion(name="crit_a", description="First", weight=0.4),
            EvaluationCriterion(name="crit_b", description="Second", weight=0.3),
            EvaluationCriterion(name="crit_c", description="Third", weight=0.3),
        ]
    if output_schema is None:
        output_schema = {"messages": [], "metadata": {}}
    if metadata_schema is None:
        metadata_schema = [
            MetadataField(
                field="layer", type="string", required=True, valid_values=["behaviour"]
            ),
        ]
    if layer_routing is None:
        layer_routing = {
            "behaviour": "output/train.jsonl",
            "knowledge": "output/rag_index/knowledge.jsonl",
        }

    return GoalConfig(
        goal="A" * 50,
        source_documents=source_documents,
        system_prompt="B" * 100,
        generation_targets=generation_targets,
        generation_guidelines="C" * 100,
        evaluation_criteria=evaluation_criteria,
        output_schema=output_schema,
        metadata_schema=metadata_schema,
        layer_routing=layer_routing,
    )


def _make_parsed_with_criteria_count(count: int) -> GoalConfig:
    """Build GoalConfig bypassing Pydantic min_length=3 on evaluation_criteria.

    Uses model_construct() to create an instance that would fail normal
    Pydantic validation. This simulates the scenario where the validator
    is the second line of defence after Pydantic.
    """
    criteria = [
        EvaluationCriterion(name=f"crit_{i}", description=f"C{i}", weight=round(1.0 / max(count, 1), 2))
        for i in range(count)
    ]
    # model_construct bypasses Pydantic validators
    return GoalConfig.model_construct(
        goal="A" * 50,
        source_documents=[
            SourceDocument(file_pattern="*.pdf", mode="standard", notes=""),
        ],
        system_prompt="B" * 100,
        generation_targets=[
            GenerationTarget(category="reasoning_cat", type="reasoning", count=70),
            GenerationTarget(category="direct_cat", type="direct", count=30),
        ],
        generation_guidelines="C" * 100,
        evaluation_criteria=criteria,
        output_schema={"messages": [], "metadata": {}},
        metadata_schema=[
            MetadataField(
                field="layer", type="string", required=True, valid_values=["behaviour"]
            ),
        ],
        layer_routing={
            "behaviour": "output/train.jsonl",
            "knowledge": "output/rag_index/knowledge.jsonl",
        },
    )


@pytest.fixture
def valid_sections() -> dict[str, str]:
    """A valid sections dict that passes all validation rules."""
    return _make_sections()


@pytest.fixture
def valid_parsed() -> GoalConfig:
    """A valid GoalConfig that passes all validation rules."""
    return _make_parsed()


# ---------------------------------------------------------------------------
# TestValidateGoalConfigHappyPath
# ---------------------------------------------------------------------------


class TestValidateGoalConfigHappyPath:
    """validate_goal_config should return None for valid input."""

    def test_valid_input_passes(self, valid_sections, valid_parsed):
        result = validate_goal_config(valid_sections, valid_parsed)
        assert result is None


# ---------------------------------------------------------------------------
# TestGoalSectionLength — Rule 1: goal minimum 50 characters
# ---------------------------------------------------------------------------


class TestGoalSectionLength:
    """BDD Scenarios 84-88 (pass), 90-96 (fail).

    Length is validated from the sections dict, not the parsed GoalConfig.
    """

    @pytest.mark.boundary
    def test_goal_exactly_50_chars_passes(self, valid_parsed):
        """Boundary: 50 characters should pass."""
        sections = _make_sections(goal="X" * 50)
        validate_goal_config(sections, valid_parsed)

    @pytest.mark.boundary
    @pytest.mark.negative
    def test_goal_49_chars_fails(self, valid_parsed):
        """Boundary: 49 characters should fail."""
        sections = _make_sections(goal="X" * 49)
        with pytest.raises(GoalValidationError) as exc_info:
            validate_goal_config(sections, valid_parsed)
        assert any("Goal" in s and "50" in m for s, m in exc_info.value.failures)

    @pytest.mark.negative
    def test_goal_empty_fails(self, valid_parsed):
        """Empty goal should fail."""
        sections = _make_sections(goal="")
        with pytest.raises(GoalValidationError) as exc_info:
            validate_goal_config(sections, valid_parsed)
        assert any("Goal" in s for s, m in exc_info.value.failures)


# ---------------------------------------------------------------------------
# TestSystemPromptLength — Rule 2: system_prompt minimum 100 characters
# ---------------------------------------------------------------------------


class TestSystemPromptLength:
    """BDD Scenarios 98-103 (pass), 105-110 (fail)."""

    @pytest.mark.boundary
    def test_system_prompt_exactly_100_chars_passes(self, valid_parsed):
        sections = _make_sections(system_prompt="S" * 100)
        validate_goal_config(sections, valid_parsed)

    @pytest.mark.boundary
    @pytest.mark.negative
    def test_system_prompt_99_chars_fails(self, valid_parsed):
        sections = _make_sections(system_prompt="S" * 99)
        with pytest.raises(GoalValidationError) as exc_info:
            validate_goal_config(sections, valid_parsed)
        assert any(
            "System Prompt" in s and "100" in m for s, m in exc_info.value.failures
        )


# ---------------------------------------------------------------------------
# TestGenerationGuidelinesLength — Rule 3: minimum 100 characters
# ---------------------------------------------------------------------------


class TestGenerationGuidelinesLength:
    """BDD Scenarios 113-117 (pass)."""

    @pytest.mark.boundary
    def test_guidelines_exactly_100_chars_passes(self, valid_parsed):
        sections = _make_sections(generation_guidelines="G" * 100)
        validate_goal_config(sections, valid_parsed)

    @pytest.mark.boundary
    @pytest.mark.negative
    def test_guidelines_99_chars_fails(self, valid_parsed):
        sections = _make_sections(generation_guidelines="G" * 99)
        with pytest.raises(GoalValidationError) as exc_info:
            validate_goal_config(sections, valid_parsed)
        assert any(
            "Generation Guidelines" in s and "100" in m
            for s, m in exc_info.value.failures
        )


# ---------------------------------------------------------------------------
# TestSourceDocuments — Rule 4: at least 1 entry
# ---------------------------------------------------------------------------


class TestSourceDocuments:
    """Source docs are enforced by Pydantic min_length=1 on GoalConfig.

    The validator provides a second defence layer for aggregated errors.
    """

    def test_one_source_doc_passes(self, valid_sections, valid_parsed):
        validate_goal_config(valid_sections, valid_parsed)

    @pytest.mark.negative
    def test_empty_source_docs_fails(self, valid_sections):
        """Use model_construct to bypass Pydantic min_length=1."""
        parsed = GoalConfig.model_construct(
            goal="A" * 50,
            source_documents=[],
            system_prompt="B" * 100,
            generation_targets=[
                GenerationTarget(category="r", type="reasoning", count=70),
                GenerationTarget(category="d", type="direct", count=30),
            ],
            generation_guidelines="C" * 100,
            evaluation_criteria=[
                EvaluationCriterion(name="crit_a", description="A", weight=0.4),
                EvaluationCriterion(name="crit_b", description="B", weight=0.3),
                EvaluationCriterion(name="crit_c", description="C", weight=0.3),
            ],
            output_schema={"messages": [], "metadata": {}},
            metadata_schema=[
                MetadataField(field="layer", type="string", required=True),
            ],
            layer_routing={"behaviour": "a", "knowledge": "b"},
        )
        with pytest.raises(GoalValidationError) as exc_info:
            validate_goal_config(valid_sections, parsed)
        assert any("Source Documents" in s for s, m in exc_info.value.failures)


# ---------------------------------------------------------------------------
# TestEvaluationCriteriaCount — Rule 5: at least 3 criteria
# ---------------------------------------------------------------------------


class TestEvaluationCriteriaCount:
    """BDD Scenarios 119-124 (pass), 127-132 (fail).

    Uses model_construct() to bypass Pydantic min_length=3 for negative tests.
    """

    @pytest.mark.boundary
    def test_exactly_3_criteria_passes(self, valid_sections):
        parsed = _make_parsed()  # Default has exactly 3 criteria
        validate_goal_config(valid_sections, parsed)

    @pytest.mark.boundary
    @pytest.mark.negative
    def test_2_criteria_fails(self, valid_sections):
        parsed = _make_parsed_with_criteria_count(2)
        with pytest.raises(GoalValidationError) as exc_info:
            validate_goal_config(valid_sections, parsed)
        assert any(
            "Evaluation Criteria" in s and "3" in m
            for s, m in exc_info.value.failures
        )

    @pytest.mark.negative
    def test_1_criterion_fails(self, valid_sections):
        parsed = _make_parsed_with_criteria_count(1)
        with pytest.raises(GoalValidationError) as exc_info:
            validate_goal_config(valid_sections, parsed)
        assert any(
            "Evaluation Criteria" in s for s, m in exc_info.value.failures
        )


# ---------------------------------------------------------------------------
# TestEvaluationCriteriaKeywords — Rule 6: no Python keywords
# ---------------------------------------------------------------------------


class TestEvaluationCriteriaKeywords:
    """BDD Scenarios 280-286 (keyword rejected).

    Pydantic field_validator already rejects keywords at model construction.
    These tests verify the model-level protection is in place.
    """

    @pytest.mark.negative
    @pytest.mark.parametrize("kw", ["class", "import", "return", "for", "if"])
    def test_python_keyword_as_criterion_name_rejected_by_model(self, kw):
        """Python reserved keywords should be rejected at model level."""
        with pytest.raises(Exception):
            EvaluationCriterion(name=kw, description="Test", weight=0.3)

    def test_valid_python_identifier_passes(self, valid_sections):
        """Valid Python identifiers should be accepted."""
        criteria = [
            EvaluationCriterion(name="socratic_approach", description="A", weight=0.4),
            EvaluationCriterion(name="text_quality", description="B", weight=0.3),
            EvaluationCriterion(name="accuracy", description="C", weight=0.3),
        ]
        parsed = _make_parsed(evaluation_criteria=criteria)
        validate_goal_config(valid_sections, parsed)

    @pytest.mark.negative
    def test_invalid_identifier_detected_by_validator(self, valid_sections):
        """Validator catches invalid identifiers that bypass Pydantic (model_construct)."""
        crit = EvaluationCriterion.model_construct(
            name="not-valid-id", description="Bad", weight=0.3
        )
        parsed = GoalConfig.model_construct(
            goal="A" * 50,
            source_documents=[
                SourceDocument(file_pattern="*.pdf", mode="standard", notes=""),
            ],
            system_prompt="B" * 100,
            generation_targets=[
                GenerationTarget(category="r", type="reasoning", count=70),
                GenerationTarget(category="d", type="direct", count=30),
            ],
            generation_guidelines="C" * 100,
            evaluation_criteria=[
                EvaluationCriterion(name="crit_a", description="A", weight=0.4),
                EvaluationCriterion(name="crit_b", description="B", weight=0.3),
                crit,
            ],
            output_schema={"messages": [], "metadata": {}},
            metadata_schema=[
                MetadataField(field="layer", type="string", required=True),
            ],
            layer_routing={"behaviour": "a", "knowledge": "b"},
        )
        with pytest.raises(GoalValidationError) as exc_info:
            validate_goal_config(valid_sections, parsed)
        assert any(
            "Evaluation Criteria" in s and "not-valid-id" in m
            for s, m in exc_info.value.failures
        )

    @pytest.mark.negative
    def test_keyword_name_detected_by_validator(self, valid_sections):
        """Validator catches keyword names that bypass Pydantic (model_construct)."""
        crit = EvaluationCriterion.model_construct(
            name="class", description="Bad keyword", weight=0.3
        )
        parsed = GoalConfig.model_construct(
            goal="A" * 50,
            source_documents=[
                SourceDocument(file_pattern="*.pdf", mode="standard", notes=""),
            ],
            system_prompt="B" * 100,
            generation_targets=[
                GenerationTarget(category="r", type="reasoning", count=70),
                GenerationTarget(category="d", type="direct", count=30),
            ],
            generation_guidelines="C" * 100,
            evaluation_criteria=[
                EvaluationCriterion(name="crit_a", description="A", weight=0.4),
                EvaluationCriterion(name="crit_b", description="B", weight=0.3),
                crit,
            ],
            output_schema={"messages": [], "metadata": {}},
            metadata_schema=[
                MetadataField(field="layer", type="string", required=True),
            ],
            layer_routing={"behaviour": "a", "knowledge": "b"},
        )
        with pytest.raises(GoalValidationError) as exc_info:
            validate_goal_config(valid_sections, parsed)
        assert any(
            "Evaluation Criteria" in s and "class" in m
            for s, m in exc_info.value.failures
        )


# ---------------------------------------------------------------------------
# TestOutputSchemaKeys — Rule 7: messages and metadata keys
# ---------------------------------------------------------------------------


class TestOutputSchemaKeys:
    def test_valid_output_schema_passes(self, valid_sections):
        parsed = _make_parsed(output_schema={"messages": [], "metadata": {}})
        validate_goal_config(valid_sections, parsed)

    @pytest.mark.negative
    def test_missing_messages_key_fails(self, valid_sections):
        """BDD Scenarios 195-201."""
        parsed = _make_parsed(output_schema={"metadata": {}})
        with pytest.raises(GoalValidationError) as exc_info:
            validate_goal_config(valid_sections, parsed)
        assert any(
            "Output Schema" in s and "messages" in m
            for s, m in exc_info.value.failures
        )

    @pytest.mark.negative
    def test_missing_metadata_key_fails(self, valid_sections):
        parsed = _make_parsed(output_schema={"messages": []})
        with pytest.raises(GoalValidationError) as exc_info:
            validate_goal_config(valid_sections, parsed)
        assert any(
            "Output Schema" in s and "metadata" in m
            for s, m in exc_info.value.failures
        )

    @pytest.mark.negative
    def test_missing_both_keys_fails(self, valid_sections):
        parsed = _make_parsed(output_schema={"other": "stuff"})
        with pytest.raises(GoalValidationError) as exc_info:
            validate_goal_config(valid_sections, parsed)
        failures = exc_info.value.failures
        output_failures = [(s, m) for s, m in failures if "Output Schema" in s]
        assert len(output_failures) >= 1
        failure_text = " ".join(m for _, m in output_failures)
        assert "messages" in failure_text
        assert "metadata" in failure_text


# ---------------------------------------------------------------------------
# TestMetadataSchemaRequired — Rule 8: all fields required = True
# ---------------------------------------------------------------------------


class TestMetadataSchemaRequired:
    def test_all_required_true_passes(self, valid_sections):
        metadata = [
            MetadataField(
                field="layer", type="string", required=True, valid_values=["behaviour"]
            ),
            MetadataField(field="source_page", type="integer", required=True),
        ]
        parsed = _make_parsed(metadata_schema=metadata)
        validate_goal_config(valid_sections, parsed)

    @pytest.mark.negative
    def test_field_with_required_false_fails(self, valid_sections):
        metadata = [
            MetadataField(
                field="layer", type="string", required=True, valid_values=["behaviour"]
            ),
            MetadataField(field="source_page", type="integer", required=False),
        ]
        parsed = _make_parsed(metadata_schema=metadata)
        with pytest.raises(GoalValidationError) as exc_info:
            validate_goal_config(valid_sections, parsed)
        assert any(
            "Metadata Schema" in s and "source_page" in m
            for s, m in exc_info.value.failures
        )

    @pytest.mark.negative
    def test_multiple_fields_with_required_false_all_reported(self, valid_sections):
        """Each non-required field should generate its own failure."""
        metadata = [
            MetadataField(field="layer", type="string", required=False),
            MetadataField(field="source_page", type="integer", required=False),
        ]
        parsed = _make_parsed(metadata_schema=metadata)
        with pytest.raises(GoalValidationError) as exc_info:
            validate_goal_config(valid_sections, parsed)
        meta_failures = [
            (s, m) for s, m in exc_info.value.failures if "Metadata Schema" in s
        ]
        assert len(meta_failures) == 2
        failure_text = " ".join(m for _, m in meta_failures)
        assert "layer" in failure_text
        assert "source_page" in failure_text


# ---------------------------------------------------------------------------
# TestLayerRouting — Rule 9: behaviour and knowledge both required
# ---------------------------------------------------------------------------


class TestLayerRouting:
    """BDD Scenarios 203-209 (missing knowledge)."""

    def test_both_layers_present_passes(self, valid_sections):
        parsed = _make_parsed(
            layer_routing={
                "behaviour": "output/train.jsonl",
                "knowledge": "output/rag_index/knowledge.jsonl",
            }
        )
        validate_goal_config(valid_sections, parsed)

    @pytest.mark.negative
    def test_missing_knowledge_fails(self, valid_sections):
        parsed = _make_parsed(
            layer_routing={"behaviour": "output/train.jsonl"}
        )
        with pytest.raises(GoalValidationError) as exc_info:
            validate_goal_config(valid_sections, parsed)
        assert any(
            "Layer Routing" in s and "knowledge" in m
            for s, m in exc_info.value.failures
        )

    @pytest.mark.negative
    def test_missing_behaviour_fails(self, valid_sections):
        parsed = _make_parsed(
            layer_routing={"knowledge": "output/rag_index/knowledge.jsonl"}
        )
        with pytest.raises(GoalValidationError) as exc_info:
            validate_goal_config(valid_sections, parsed)
        assert any(
            "Layer Routing" in s and "behaviour" in m
            for s, m in exc_info.value.failures
        )

    @pytest.mark.negative
    def test_both_missing_fails(self, valid_sections):
        parsed = _make_parsed(layer_routing={"other": "value"})
        with pytest.raises(GoalValidationError) as exc_info:
            validate_goal_config(valid_sections, parsed)
        failures = exc_info.value.failures
        layer_failures = [(s, m) for s, m in failures if "Layer Routing" in s]
        assert len(layer_failures) >= 1
        failure_text = " ".join(m for _, m in layer_failures)
        assert "behaviour" in failure_text
        assert "knowledge" in failure_text


# ---------------------------------------------------------------------------
# TestReasoningSplit — Rule 10: reasoning >= 70% of generation targets
# ---------------------------------------------------------------------------


class TestReasoningSplit:
    """BDD Scenarios 137-140 (pass), 211-217 (fail), 298-304 (advisory)."""

    @pytest.mark.boundary
    def test_exactly_70_percent_reasoning_passes(self):
        """Boundary: 70/100 reasoning should pass."""
        targets = [
            GenerationTarget(category="reasoning_cat", type="reasoning", count=70),
            GenerationTarget(category="direct_cat", type="direct", count=30),
        ]
        sections = _make_sections()
        parsed = _make_parsed(generation_targets=targets)
        validate_goal_config(sections, parsed)

    @pytest.mark.boundary
    @pytest.mark.negative
    def test_69_percent_reasoning_fails(self):
        """Boundary: 69/100 reasoning should fail."""
        targets = [
            GenerationTarget(category="reasoning_cat", type="reasoning", count=69),
            GenerationTarget(category="direct_cat", type="direct", count=31),
        ]
        sections = _make_sections()
        parsed = _make_parsed(generation_targets=targets)
        with pytest.raises(GoalValidationError) as exc_info:
            validate_goal_config(sections, parsed)
        assert any(
            "Generation Targets" in s and "70" in m
            for s, m in exc_info.value.failures
        )

    @pytest.mark.negative
    def test_60_percent_reasoning_fails(self):
        """60% reasoning should fail. BDD Scenarios 211-217."""
        targets = [
            GenerationTarget(category="reasoning_cat", type="reasoning", count=60),
            GenerationTarget(category="direct_cat", type="direct", count=40),
        ]
        sections = _make_sections()
        parsed = _make_parsed(generation_targets=targets)
        with pytest.raises(GoalValidationError) as exc_info:
            validate_goal_config(sections, parsed)
        assert any(
            "Generation Targets" in s for s, m in exc_info.value.failures
        )

    def test_100_percent_reasoning_passes(self):
        """All reasoning should pass."""
        targets = [
            GenerationTarget(category="reasoning_cat", type="reasoning", count=100),
        ]
        sections = _make_sections()
        parsed = _make_parsed(generation_targets=targets)
        validate_goal_config(sections, parsed)

    @pytest.mark.parametrize(
        "reasoning_count,direct_count",
        [
            (700, 300),  # exactly 70%
            (7, 3),  # exactly 70% small counts
            (71, 29),  # just above 70%
        ],
    )
    def test_various_counts_at_or_above_70_percent_pass(
        self, reasoning_count, direct_count
    ):
        """BDD Scenario 298-304: counts are authoritative, not percentages."""
        targets = [
            GenerationTarget(
                category="reasoning_cat", type="reasoning", count=reasoning_count
            ),
            GenerationTarget(
                category="direct_cat", type="direct", count=direct_count
            ),
        ]
        sections = _make_sections()
        parsed = _make_parsed(generation_targets=targets)
        validate_goal_config(sections, parsed)


# ---------------------------------------------------------------------------
# TestErrorAggregation — multiple failures reported together
# ---------------------------------------------------------------------------


class TestErrorAggregation:
    """BDD Scenarios 253-260: multiple failures are reported together."""

    def test_multiple_failures_aggregated(self):
        """Goal too short + System Prompt too short + only 1 criterion.

        BDD Scenario 253-260: Multiple validation failures are reported together.
        """
        sections = _make_sections(goal="X" * 10, system_prompt="Y" * 10)
        parsed = _make_parsed_with_criteria_count(1)
        with pytest.raises(GoalValidationError) as exc_info:
            validate_goal_config(sections, parsed)
        failures = exc_info.value.failures
        sections_failed = {s for s, m in failures}
        assert "Goal" in sections_failed
        assert "System Prompt" in sections_failed
        assert "Evaluation Criteria" in sections_failed

    def test_error_has_failures_attribute(self):
        """GoalValidationError must expose failures as list[tuple[str, str]]."""
        sections = _make_sections(goal="X" * 10)
        parsed = _make_parsed()
        with pytest.raises(GoalValidationError) as exc_info:
            validate_goal_config(sections, parsed)
        assert hasattr(exc_info.value, "failures")
        assert isinstance(exc_info.value.failures, list)
        for item in exc_info.value.failures:
            assert isinstance(item, tuple)
            assert len(item) == 2

    def test_error_message_includes_all_sections(self):
        """The str() of the error should mention all failing sections."""
        sections = _make_sections(goal="X" * 10, system_prompt="Y" * 10)
        parsed = _make_parsed()
        with pytest.raises(GoalValidationError) as exc_info:
            validate_goal_config(sections, parsed)
        error_str = str(exc_info.value)
        assert "Goal" in error_str
        assert "System Prompt" in error_str

    def test_single_failure_still_uses_failures_attribute(self):
        """Even a single failure should populate the failures attribute."""
        sections = _make_sections(goal="X" * 10)
        parsed = _make_parsed()
        with pytest.raises(GoalValidationError) as exc_info:
            validate_goal_config(sections, parsed)
        assert len(exc_info.value.failures) == 1
        section, msg = exc_info.value.failures[0]
        assert section == "Goal"
        assert "50" in msg

    def test_no_failures_does_not_raise(self, valid_sections, valid_parsed):
        """Valid input should not raise."""
        validate_goal_config(valid_sections, valid_parsed)

    def test_all_structural_failures_aggregated(self):
        """Every structural rule failure should be aggregated together."""
        sections = _make_sections(
            goal="X" * 10,
            system_prompt="Y" * 10,
            generation_guidelines="Z" * 10,
        )
        parsed = GoalConfig.model_construct(
            goal="A" * 50,
            source_documents=[],
            system_prompt="B" * 100,
            generation_targets=[
                GenerationTarget(category="d", type="direct", count=100),
            ],
            generation_guidelines="C" * 100,
            evaluation_criteria=[
                EvaluationCriterion(name="crit_a", description="A", weight=1.0),
            ],
            output_schema={"other": "stuff"},
            metadata_schema=[
                MetadataField(field="layer", type="string", required=False),
            ],
            layer_routing={"other": "value"},
        )
        with pytest.raises(GoalValidationError) as exc_info:
            validate_goal_config(sections, parsed)
        failures = exc_info.value.failures
        sections_failed = {s for s, m in failures}
        # All of these should be reported
        assert "Goal" in sections_failed
        assert "System Prompt" in sections_failed
        assert "Generation Guidelines" in sections_failed
        assert "Source Documents" in sections_failed
        assert "Evaluation Criteria" in sections_failed
        assert "Output Schema" in sections_failed
        assert "Metadata Schema" in sections_failed
        assert "Layer Routing" in sections_failed
        assert "Generation Targets" in sections_failed


# ---------------------------------------------------------------------------
# TestSeamContract — integration contracts
# ---------------------------------------------------------------------------


class TestSeamContract:
    """Seam tests verifying SECTION_DICT and PARSED_MODELS contracts."""

    @pytest.mark.seam
    @pytest.mark.integration_contract("SECTION_DICT")
    def test_section_dict_consumed_by_validator(self):
        """Verify validator accepts the dict format from split_sections.

        Contract: dict[str, str] with 9 keys
        Producer: TASK-DC-002
        """
        sections = _make_sections()
        parsed = _make_parsed()
        validate_goal_config(sections, parsed)
        assert isinstance(sections, dict)
        assert all(isinstance(v, str) for v in sections.values())

    @pytest.mark.seam
    @pytest.mark.integration_contract("PARSED_MODELS")
    def test_parsed_models_consumed_by_validator(self):
        """Verify validator accepts GoalConfig from parse_table/extract_json.

        Contract: GoalConfig with validated Pydantic model instances
        Producer: TASK-DC-003
        """
        parsed = _make_parsed()
        sections = _make_sections()
        validate_goal_config(sections, parsed)
        assert isinstance(parsed, GoalConfig)
