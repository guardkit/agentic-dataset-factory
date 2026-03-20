"""Unit tests for prompt builder modules — TASK-AF-010.

Tests verify GOAL.md section injection, missing section error handling,
and base prompt precedence for both Player and Coach prompt builders.

Acceptance Criteria:
  AC-001: Player prompt tests verify all 6 GOAL.md sections are present
  AC-002: Coach prompt tests verify all 5 GOAL.md sections are present
  AC-003: Tests verify base prompt appears before injected content
  AC-004: Tests verify missing section raises error
  AC-005: Tests verify evaluation criteria names are present for criteria_met alignment
  AC-006: Tests are in tests/test_prompt_builders.py
"""

from __future__ import annotations

import pytest

from domain_config.models import (
    EvaluationCriterion,
    GenerationTarget,
    GoalConfig,
    MetadataField,
    SourceDocument,
)
from prompts.coach_prompts import COACH_BASE_PROMPT, build_coach_prompt
from prompts.player_prompts import PLAYER_BASE_PROMPT, build_player_prompt


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def valid_goal_config() -> GoalConfig:
    """A fully populated GoalConfig with known content for assertion."""
    return GoalConfig(
        goal=(
            "Train a GCSE English Literature tutor that uses Socratic questioning "
            "to guide students through literary analysis."
        ),
        source_documents=[
            SourceDocument(file_pattern="texts/*.pdf", mode="standard", notes="Core texts"),
        ],
        system_prompt=(
            "You are a GCSE English Literature tutor. Guide students using Socratic "
            "questioning. Never give answers directly — always ask probing questions "
            "that lead students to discover insights themselves."
        ),
        generation_targets=[
            GenerationTarget(
                category="Literary analysis (single-turn)", type="reasoning", count=50
            ),
        ],
        generation_guidelines=(
            "Generate training examples that demonstrate effective Socratic tutoring. "
            "Each example should model appropriate pedagogical techniques including "
            "scaffolded questioning and positive reinforcement."
        ),
        evaluation_criteria=[
            EvaluationCriterion(
                name="socratic_approach", description="Uses Socratic questioning", weight=0.3
            ),
            EvaluationCriterion(
                name="ao_accuracy", description="AO references are correct", weight=0.2
            ),
            EvaluationCriterion(
                name="mark_scheme_aligned", description="Aligns with mark scheme", weight=0.2
            ),
            EvaluationCriterion(
                name="age_appropriate", description="Age-appropriate language", weight=0.15
            ),
            EvaluationCriterion(
                name="factual_accuracy", description="Factually accurate", weight=0.15
            ),
        ],
        output_schema={
            "conversations": [
                {"from": "system", "value": "string"},
                {"from": "human", "value": "string"},
                {"from": "gpt", "value": "string"},
            ],
            "metadata": {},
        },
        metadata_schema=[
            MetadataField(
                field="layer", type="string", required=True,
                valid_values=["behaviour", "knowledge"],
            ),
            MetadataField(
                field="type", type="string", required=True,
                valid_values=["reasoning", "direct"],
            ),
            MetadataField(
                field="grade_target", type="integer", required=True, valid_values=[],
            ),
        ],
        layer_routing={
            "behaviour": "Pedagogical approach, questioning style, tone",
            "knowledge": "Subject-specific facts, quotes, context",
        },
    )


@pytest.fixture()
def _config_with_override(valid_goal_config: GoalConfig):
    """Factory for creating GoalConfig with overrides bypassing Pydantic validators."""
    def _make(**overrides: object) -> GoalConfig:
        data = valid_goal_config.model_dump()
        data.update(overrides)
        return GoalConfig.model_construct(**data)
    return _make


# ---------------------------------------------------------------------------
# AC-001: Player prompt tests verify all 6 GOAL.md sections are present
# ---------------------------------------------------------------------------


class TestPlayerPromptSections:
    """Built player prompt contains all 6 injected GOAL.md sections."""

    def test_contains_base_player_instructions(self, valid_goal_config: GoalConfig) -> None:
        """Built prompt contains base player instructions."""
        result = build_player_prompt(valid_goal_config)
        assert PLAYER_BASE_PROMPT in result

    def test_contains_goal_section(self, valid_goal_config: GoalConfig) -> None:
        """Built prompt contains Goal section content."""
        result = build_player_prompt(valid_goal_config)
        assert valid_goal_config.goal in result

    def test_contains_system_prompt_section(self, valid_goal_config: GoalConfig) -> None:
        """Built prompt contains System Prompt section content."""
        result = build_player_prompt(valid_goal_config)
        assert valid_goal_config.system_prompt in result

    def test_contains_generation_guidelines_section(self, valid_goal_config: GoalConfig) -> None:
        """Built prompt contains Generation Guidelines section content."""
        result = build_player_prompt(valid_goal_config)
        assert valid_goal_config.generation_guidelines in result

    def test_contains_output_schema_section(self, valid_goal_config: GoalConfig) -> None:
        """Built prompt contains Output Schema section."""
        result = build_player_prompt(valid_goal_config)
        assert "## Output Schema" in result

    def test_contains_metadata_schema_section(self, valid_goal_config: GoalConfig) -> None:
        """Built prompt contains Metadata Schema section with field names."""
        result = build_player_prompt(valid_goal_config)
        assert "## Metadata Schema" in result
        for field in valid_goal_config.metadata_schema:
            assert field.field in result, (
                f"Metadata field '{field.field}' not found in player prompt"
            )

    def test_contains_layer_routing_section(self, valid_goal_config: GoalConfig) -> None:
        """Built prompt contains Layer Routing section with layer names."""
        result = build_player_prompt(valid_goal_config)
        assert "## Layer Routing" in result
        for layer in valid_goal_config.layer_routing:
            assert layer in result, f"Layer '{layer}' not found in player prompt"

    def test_all_six_section_headings_present(self, valid_goal_config: GoalConfig) -> None:
        """All 6 GOAL.md section headings are present in the built prompt."""
        result = build_player_prompt(valid_goal_config)
        expected_headings = [
            "## Goal",
            "## System Prompt",
            "## Generation Guidelines",
            "## Output Schema",
            "## Metadata Schema",
            "## Layer Routing",
        ]
        for heading in expected_headings:
            assert heading in result, f"Section heading '{heading}' not found in player prompt"


# ---------------------------------------------------------------------------
# AC-002: Coach prompt tests verify all 5 GOAL.md sections are present
# ---------------------------------------------------------------------------


class TestCoachPromptSections:
    """Built coach prompt contains all 5 injected GOAL.md sections."""

    def test_contains_base_coach_instructions(self, valid_goal_config: GoalConfig) -> None:
        """Built prompt contains base coach instructions."""
        result = build_coach_prompt(valid_goal_config)
        assert COACH_BASE_PROMPT in result

    def test_contains_goal_section(self, valid_goal_config: GoalConfig) -> None:
        """Built prompt contains Goal section content."""
        result = build_coach_prompt(valid_goal_config)
        assert valid_goal_config.goal in result

    def test_contains_evaluation_criteria_section(self, valid_goal_config: GoalConfig) -> None:
        """Built prompt contains Evaluation Criteria section."""
        result = build_coach_prompt(valid_goal_config)
        assert "## Evaluation Criteria" in result

    def test_contains_output_schema_section(self, valid_goal_config: GoalConfig) -> None:
        """Built prompt contains Output Schema section."""
        result = build_coach_prompt(valid_goal_config)
        assert "## Output Schema" in result

    def test_contains_metadata_schema_section(self, valid_goal_config: GoalConfig) -> None:
        """Built prompt contains Metadata Schema section with field names."""
        result = build_coach_prompt(valid_goal_config)
        assert "## Metadata Schema" in result
        for field in valid_goal_config.metadata_schema:
            assert field.field in result, (
                f"Metadata field '{field.field}' not found in coach prompt"
            )

    def test_contains_layer_routing_section(self, valid_goal_config: GoalConfig) -> None:
        """Built prompt contains Layer Routing section with layer names."""
        result = build_coach_prompt(valid_goal_config)
        assert "## Layer Routing" in result
        for layer in valid_goal_config.layer_routing:
            assert layer in result, f"Layer '{layer}' not found in coach prompt"

    def test_all_five_section_headings_present(self, valid_goal_config: GoalConfig) -> None:
        """All 5 GOAL.md section headings are present in the built prompt."""
        result = build_coach_prompt(valid_goal_config)
        expected_headings = [
            "## Goal",
            "## Evaluation Criteria",
            "## Output Schema",
            "## Metadata Schema",
            "## Layer Routing",
        ]
        for heading in expected_headings:
            assert heading in result, f"Section heading '{heading}' not found in coach prompt"

    def test_all_evaluation_criteria_names_present(self, valid_goal_config: GoalConfig) -> None:
        """All 5 evaluation criteria names are present in the prompt."""
        result = build_coach_prompt(valid_goal_config)
        for criterion in valid_goal_config.evaluation_criteria:
            assert criterion.name in result, (
                f"Criterion '{criterion.name}' not found in coach prompt"
            )


# ---------------------------------------------------------------------------
# AC-003: Tests verify base prompt appears before injected content
# ---------------------------------------------------------------------------


class TestBasePromptPrecedence:
    """Base prompt appears before GOAL.md content — not overridden."""

    def test_player_base_prompt_before_goal_content(
        self, valid_goal_config: GoalConfig
    ) -> None:
        """Base player prompt appears before GOAL.md content."""
        result = build_player_prompt(valid_goal_config)
        base_index = result.index(PLAYER_BASE_PROMPT)
        goal_index = result.index(valid_goal_config.goal)
        assert base_index < goal_index, "Base prompt must appear before GOAL.md content"

    def test_coach_base_prompt_before_goal_content(
        self, valid_goal_config: GoalConfig
    ) -> None:
        """Base coach prompt appears before GOAL.md content."""
        result = build_coach_prompt(valid_goal_config)
        base_index = result.index(COACH_BASE_PROMPT)
        goal_index = result.index(valid_goal_config.goal)
        assert base_index < goal_index, "Base prompt must appear before GOAL.md content"

    def test_player_goal_content_does_not_override_base(
        self, valid_goal_config: GoalConfig
    ) -> None:
        """GOAL.md content with prompt-like instructions does not override base prompt.

        The built prompt must start with the base prompt, not the goal content.
        """
        result = build_player_prompt(valid_goal_config)
        assert result.startswith(PLAYER_BASE_PROMPT), (
            "Built prompt must start with the base prompt — GOAL.md content "
            "must not precede or override it"
        )

    def test_coach_goal_content_does_not_override_base(
        self, valid_goal_config: GoalConfig
    ) -> None:
        """GOAL.md content does not override base coach prompt."""
        result = build_coach_prompt(valid_goal_config)
        assert result.startswith(COACH_BASE_PROMPT), (
            "Built prompt must start with the base prompt — GOAL.md content "
            "must not precede or override it"
        )

    def test_player_domain_context_is_delimited(
        self, valid_goal_config: GoalConfig
    ) -> None:
        """GOAL.md content is labelled as domain context, not directives."""
        result = build_player_prompt(valid_goal_config)
        assert "DOMAIN CONTEXT" in result

    def test_coach_domain_context_is_delimited(
        self, valid_goal_config: GoalConfig
    ) -> None:
        """GOAL.md content is labelled as domain context, not directives."""
        result = build_coach_prompt(valid_goal_config)
        assert "DOMAIN CONTEXT" in result


# ---------------------------------------------------------------------------
# AC-004: Tests verify missing section raises error
# ---------------------------------------------------------------------------


class TestPlayerMissingSectionErrors:
    """Missing or empty required player sections raise ValueError, not silent degradation."""

    @staticmethod
    def _config_with_override(base: GoalConfig, **overrides: object) -> GoalConfig:
        data = base.model_dump()
        data.update(overrides)
        return GoalConfig.model_construct(**data)

    def test_missing_goal_raises_error(self, valid_goal_config: GoalConfig) -> None:
        config = self._config_with_override(valid_goal_config, goal="")
        with pytest.raises(ValueError, match="(?i)goal.*(empty|missing|required|incomplete)"):
            build_player_prompt(config)

    def test_missing_system_prompt_raises_error(self, valid_goal_config: GoalConfig) -> None:
        config = self._config_with_override(valid_goal_config, system_prompt="")
        with pytest.raises(ValueError, match="(?i)system.prompt.*(empty|missing|incomplete)"):
            build_player_prompt(config)

    def test_missing_generation_guidelines_raises_error(
        self, valid_goal_config: GoalConfig
    ) -> None:
        """Missing Generation Guidelines section → error raised."""
        config = self._config_with_override(valid_goal_config, generation_guidelines="")
        with pytest.raises(
            ValueError, match="(?i)generation.guidelines.*(empty|missing|incomplete)"
        ):
            build_player_prompt(config)

    def test_missing_output_schema_raises_error(self, valid_goal_config: GoalConfig) -> None:
        config = self._config_with_override(valid_goal_config, output_schema={})
        with pytest.raises(ValueError, match="(?i)output.schema.*(empty|missing|incomplete)"):
            build_player_prompt(config)

    def test_missing_metadata_schema_raises_error(self, valid_goal_config: GoalConfig) -> None:
        config = self._config_with_override(valid_goal_config, metadata_schema=[])
        with pytest.raises(ValueError, match="(?i)metadata.schema.*(empty|missing|incomplete)"):
            build_player_prompt(config)

    def test_missing_layer_routing_raises_error(self, valid_goal_config: GoalConfig) -> None:
        config = self._config_with_override(valid_goal_config, layer_routing={})
        with pytest.raises(ValueError, match="(?i)layer.routing.*(empty|missing|incomplete)"):
            build_player_prompt(config)

    def test_partial_parse_errors_not_silent(self, valid_goal_config: GoalConfig) -> None:
        """Partial GOAL.md parse (missing section) → error, not silent degradation."""
        config = self._config_with_override(valid_goal_config, generation_guidelines="")
        with pytest.raises(ValueError):
            build_player_prompt(config)


class TestCoachMissingSectionErrors:
    """Missing or empty required coach sections raise ValueError."""

    @staticmethod
    def _config_with_override(base: GoalConfig, **overrides: object) -> GoalConfig:
        data = base.model_dump()
        data.update(overrides)
        return GoalConfig.model_construct(**data)

    def test_missing_goal_raises_error(self, valid_goal_config: GoalConfig) -> None:
        config = self._config_with_override(valid_goal_config, goal="")
        with pytest.raises(ValueError, match="(?i)goal.*(empty|missing|required|incomplete)"):
            build_coach_prompt(config)

    def test_missing_evaluation_criteria_raises_error(
        self, valid_goal_config: GoalConfig
    ) -> None:
        """Missing Evaluation Criteria section → error raised."""
        config = self._config_with_override(valid_goal_config, evaluation_criteria=[])
        with pytest.raises(
            ValueError, match="(?i)evaluation.criteria.*(empty|missing|incomplete)"
        ):
            build_coach_prompt(config)

    def test_missing_output_schema_raises_error(self, valid_goal_config: GoalConfig) -> None:
        config = self._config_with_override(valid_goal_config, output_schema={})
        with pytest.raises(ValueError, match="(?i)output.schema.*(empty|missing|incomplete)"):
            build_coach_prompt(config)

    def test_missing_metadata_schema_raises_error(self, valid_goal_config: GoalConfig) -> None:
        config = self._config_with_override(valid_goal_config, metadata_schema=[])
        with pytest.raises(ValueError, match="(?i)metadata.schema.*(empty|missing|incomplete)"):
            build_coach_prompt(config)

    def test_missing_layer_routing_raises_error(self, valid_goal_config: GoalConfig) -> None:
        config = self._config_with_override(valid_goal_config, layer_routing={})
        with pytest.raises(ValueError, match="(?i)layer.routing.*(empty|missing|incomplete)"):
            build_coach_prompt(config)


# ---------------------------------------------------------------------------
# AC-005: Tests verify evaluation criteria names present for criteria_met
# ---------------------------------------------------------------------------


class TestEvaluationCriteriaAlignment:
    """Coach prompt includes all evaluation criteria names for criteria_met validation."""

    def test_all_five_criteria_names_in_prompt(self, valid_goal_config: GoalConfig) -> None:
        """All 5 evaluation criteria names are present in the coach prompt."""
        result = build_coach_prompt(valid_goal_config)
        expected_names = [
            "socratic_approach",
            "ao_accuracy",
            "mark_scheme_aligned",
            "age_appropriate",
            "factual_accuracy",
        ]
        for name in expected_names:
            assert name in result, (
                f"Criterion name '{name}' must be present in coach prompt "
                f"for criteria_met dict alignment"
            )

    def test_criteria_met_reference_in_prompt(self, valid_goal_config: GoalConfig) -> None:
        """Coach prompt references criteria_met so Coach populates it correctly."""
        result = build_coach_prompt(valid_goal_config)
        assert "criteria_met" in result

    def test_criteria_names_appear_in_domain_context(
        self, valid_goal_config: GoalConfig
    ) -> None:
        """Criteria names appear in the DOMAIN CONTEXT section (not just base prompt)."""
        result = build_coach_prompt(valid_goal_config)
        domain_context_start = result.index("DOMAIN CONTEXT")
        domain_section = result[domain_context_start:]
        for criterion in valid_goal_config.evaluation_criteria:
            assert criterion.name in domain_section, (
                f"Criterion '{criterion.name}' should appear in DOMAIN CONTEXT section"
            )


# ---------------------------------------------------------------------------
# Edge Cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    """Edge case tests for prompt builder robustness."""

    @staticmethod
    def _config_with_override(base: GoalConfig, **overrides: object) -> GoalConfig:
        data = base.model_dump()
        data.update(overrides)
        return GoalConfig.model_construct(**data)

    def test_memory_supplements_not_replaces_system_prompt(
        self, valid_goal_config: GoalConfig
    ) -> None:
        """Memory content supplements but does not replace system prompt.

        The built prompt contains both the base prompt AND the injected system
        prompt from GOAL.md — the system prompt section augments the base, it
        does not replace it.
        """
        result = build_player_prompt(valid_goal_config)
        # Both the base prompt AND the GOAL.md system prompt must be present
        assert PLAYER_BASE_PROMPT in result, "Base prompt must be present (not replaced)"
        assert valid_goal_config.system_prompt in result, (
            "GOAL.md system prompt must supplement, not replace, the base"
        )

    def test_player_prompt_is_string(self, valid_goal_config: GoalConfig) -> None:
        """build_player_prompt returns a str."""
        result = build_player_prompt(valid_goal_config)
        assert isinstance(result, str)

    def test_coach_prompt_is_string(self, valid_goal_config: GoalConfig) -> None:
        """build_coach_prompt returns a str."""
        result = build_coach_prompt(valid_goal_config)
        assert isinstance(result, str)

    def test_partial_coach_parse_errors_not_silent(
        self, valid_goal_config: GoalConfig
    ) -> None:
        """Partial GOAL.md parse (missing section) → error, not silent degradation."""
        config = self._config_with_override(valid_goal_config, evaluation_criteria=[])
        with pytest.raises(ValueError):
            build_coach_prompt(config)
