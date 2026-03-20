"""Tests for prompt builder modules.

TDD RED phase — tests written before implementation.
Covers all acceptance criteria from TASK-AF-002:
  AC-001: player_prompts.py contains PLAYER_BASE_PROMPT + build_player_prompt
  AC-002: coach_prompts.py contains COACH_BASE_PROMPT + build_coach_prompt
  AC-003: Builder functions validate required GOAL.md sections non-empty
  AC-004: Missing/empty required section raises error
  AC-005: Base prompt appears FIRST, GOAL.md content appended as domain context
  AC-006: Coach prompt includes all evaluation criteria names
  AC-007: GOAL.md content treated as domain context, not directives
  AC-008: prompts/__init__.py created
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


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def valid_goal_config() -> GoalConfig:
    """A fully populated GoalConfig for testing prompt builders."""
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
                field="layer", type="string", required=True, valid_values=["behaviour", "knowledge"]
            ),
            MetadataField(
                field="type", type="string", required=True, valid_values=["reasoning", "direct"]
            ),
            MetadataField(field="grade_target", type="integer", required=True, valid_values=[]),
        ],
        layer_routing={
            "behaviour": "Pedagogical approach, questioning style, tone",
            "knowledge": "Subject-specific facts, quotes, context",
        },
    )


@pytest.fixture()
def goal_config_missing_generation_guidelines(valid_goal_config: GoalConfig) -> GoalConfig:
    """GoalConfig where generation_guidelines is empty."""
    return valid_goal_config.model_copy(update={"generation_guidelines": ""}, deep=True)


@pytest.fixture()
def goal_config_missing_goal(valid_goal_config: GoalConfig) -> GoalConfig:
    """GoalConfig where goal is empty."""
    return valid_goal_config.model_copy(update={"goal": ""}, deep=True)


# ---------------------------------------------------------------------------
# AC-008: prompts/__init__.py exports
# ---------------------------------------------------------------------------


class TestPromptsPackage:
    """Verify prompts package is importable and exports the public API."""

    def test_package_is_importable(self) -> None:
        import prompts  # noqa: F401

    def test_exports_build_player_prompt(self) -> None:
        from prompts import build_player_prompt

        assert callable(build_player_prompt)

    def test_exports_build_coach_prompt(self) -> None:
        from prompts import build_coach_prompt

        assert callable(build_coach_prompt)

    def test_exports_player_base_prompt(self) -> None:
        from prompts import PLAYER_BASE_PROMPT

        assert isinstance(PLAYER_BASE_PROMPT, str)

    def test_exports_coach_base_prompt(self) -> None:
        from prompts import COACH_BASE_PROMPT

        assert isinstance(COACH_BASE_PROMPT, str)


# ---------------------------------------------------------------------------
# AC-001: player_prompts.py — PLAYER_BASE_PROMPT + build_player_prompt
# ---------------------------------------------------------------------------


class TestPlayerPrompts:
    """Verify player prompt constant and builder function."""

    def test_player_base_prompt_is_non_empty_string(self) -> None:
        from prompts.player_prompts import PLAYER_BASE_PROMPT

        assert isinstance(PLAYER_BASE_PROMPT, str)
        assert len(PLAYER_BASE_PROMPT) > 0

    def test_player_base_prompt_contains_role(self) -> None:
        from prompts.player_prompts import PLAYER_BASE_PROMPT

        assert (
            "training data generator" in PLAYER_BASE_PROMPT.lower()
            or "training example" in PLAYER_BASE_PROMPT.lower()
        )

    def test_player_base_prompt_mentions_tools(self) -> None:
        from prompts.player_prompts import PLAYER_BASE_PROMPT

        assert "rag_retrieval" in PLAYER_BASE_PROMPT
        assert "write_output" in PLAYER_BASE_PROMPT

    def test_player_base_prompt_mentions_sharegpt(self) -> None:
        from prompts.player_prompts import PLAYER_BASE_PROMPT

        assert "ShareGPT" in PLAYER_BASE_PROMPT or "sharegpt" in PLAYER_BASE_PROMPT.lower()

    def test_build_player_prompt_returns_string(self, valid_goal_config: GoalConfig) -> None:
        from prompts.player_prompts import build_player_prompt

        result = build_player_prompt(valid_goal_config)
        assert isinstance(result, str)

    def test_build_player_prompt_contains_base_prompt(self, valid_goal_config: GoalConfig) -> None:
        from prompts.player_prompts import PLAYER_BASE_PROMPT, build_player_prompt

        result = build_player_prompt(valid_goal_config)
        assert PLAYER_BASE_PROMPT in result

    def test_build_player_prompt_contains_goal_section(self, valid_goal_config: GoalConfig) -> None:
        from prompts.player_prompts import build_player_prompt

        result = build_player_prompt(valid_goal_config)
        assert valid_goal_config.goal in result

    def test_build_player_prompt_contains_system_prompt_section(
        self, valid_goal_config: GoalConfig
    ) -> None:
        from prompts.player_prompts import build_player_prompt

        result = build_player_prompt(valid_goal_config)
        assert valid_goal_config.system_prompt in result

    def test_build_player_prompt_contains_generation_guidelines(
        self, valid_goal_config: GoalConfig
    ) -> None:
        from prompts.player_prompts import build_player_prompt

        result = build_player_prompt(valid_goal_config)
        assert valid_goal_config.generation_guidelines in result

    def test_build_player_prompt_contains_output_schema(
        self, valid_goal_config: GoalConfig
    ) -> None:
        from prompts.player_prompts import build_player_prompt

        result = build_player_prompt(valid_goal_config)
        assert "output_schema" in result.lower() or "Output Schema" in result

    def test_build_player_prompt_contains_metadata_schema(
        self, valid_goal_config: GoalConfig
    ) -> None:
        from prompts.player_prompts import build_player_prompt

        result = build_player_prompt(valid_goal_config)
        assert "metadata_schema" in result.lower() or "Metadata Schema" in result

    def test_build_player_prompt_contains_layer_routing(
        self, valid_goal_config: GoalConfig
    ) -> None:
        from prompts.player_prompts import build_player_prompt

        result = build_player_prompt(valid_goal_config)
        assert "behaviour" in result
        assert "knowledge" in result


# ---------------------------------------------------------------------------
# AC-002: coach_prompts.py — COACH_BASE_PROMPT + build_coach_prompt
# ---------------------------------------------------------------------------


class TestCoachPrompts:
    """Verify coach prompt constant and builder function."""

    def test_coach_base_prompt_is_non_empty_string(self) -> None:
        from prompts.coach_prompts import COACH_BASE_PROMPT

        assert isinstance(COACH_BASE_PROMPT, str)
        assert len(COACH_BASE_PROMPT) > 0

    def test_coach_base_prompt_contains_evaluator_role(self) -> None:
        from prompts.coach_prompts import COACH_BASE_PROMPT

        assert (
            "quality evaluator" in COACH_BASE_PROMPT.lower()
            or "evaluator" in COACH_BASE_PROMPT.lower()
        )

    def test_coach_base_prompt_mentions_structured_json(self) -> None:
        from prompts.coach_prompts import COACH_BASE_PROMPT

        assert "JSON" in COACH_BASE_PROMPT or "json" in COACH_BASE_PROMPT

    def test_coach_base_prompt_mentions_criteria_met(self) -> None:
        from prompts.coach_prompts import COACH_BASE_PROMPT

        assert "criteria_met" in COACH_BASE_PROMPT

    def test_build_coach_prompt_returns_string(self, valid_goal_config: GoalConfig) -> None:
        from prompts.coach_prompts import build_coach_prompt

        result = build_coach_prompt(valid_goal_config)
        assert isinstance(result, str)

    def test_build_coach_prompt_contains_base_prompt(self, valid_goal_config: GoalConfig) -> None:
        from prompts.coach_prompts import COACH_BASE_PROMPT, build_coach_prompt

        result = build_coach_prompt(valid_goal_config)
        assert COACH_BASE_PROMPT in result

    def test_build_coach_prompt_contains_goal_section(self, valid_goal_config: GoalConfig) -> None:
        from prompts.coach_prompts import build_coach_prompt

        result = build_coach_prompt(valid_goal_config)
        assert valid_goal_config.goal in result

    def test_build_coach_prompt_contains_evaluation_criteria(
        self, valid_goal_config: GoalConfig
    ) -> None:
        from prompts.coach_prompts import build_coach_prompt

        result = build_coach_prompt(valid_goal_config)
        assert "Evaluation Criteria" in result

    def test_build_coach_prompt_contains_output_schema(self, valid_goal_config: GoalConfig) -> None:
        from prompts.coach_prompts import build_coach_prompt

        result = build_coach_prompt(valid_goal_config)
        assert "output_schema" in result.lower() or "Output Schema" in result

    def test_build_coach_prompt_contains_metadata_schema(
        self, valid_goal_config: GoalConfig
    ) -> None:
        from prompts.coach_prompts import build_coach_prompt

        result = build_coach_prompt(valid_goal_config)
        assert "metadata_schema" in result.lower() or "Metadata Schema" in result

    def test_build_coach_prompt_contains_layer_routing(self, valid_goal_config: GoalConfig) -> None:
        from prompts.coach_prompts import build_coach_prompt

        result = build_coach_prompt(valid_goal_config)
        assert "behaviour" in result
        assert "knowledge" in result


# ---------------------------------------------------------------------------
# AC-003 / AC-004: Validation — required sections must be non-empty
# ---------------------------------------------------------------------------


class TestPlayerPromptValidation:
    """Builder functions validate all required GOAL.md sections are non-empty."""

    @staticmethod
    def _config_with_override(base: GoalConfig, **overrides: object) -> GoalConfig:
        """Create a GoalConfig bypassing Pydantic validators for test scenarios."""
        data = base.model_dump()
        data.update(overrides)
        return GoalConfig.model_construct(**data)

    def test_raises_on_empty_goal(self, valid_goal_config: GoalConfig) -> None:
        from prompts.player_prompts import build_player_prompt

        config = self._config_with_override(valid_goal_config, goal="")
        with pytest.raises(ValueError, match="(?i)goal.*(empty|missing|required)"):
            build_player_prompt(config)

    def test_raises_on_empty_system_prompt(self, valid_goal_config: GoalConfig) -> None:
        from prompts.player_prompts import build_player_prompt

        config = self._config_with_override(valid_goal_config, system_prompt="")
        with pytest.raises(ValueError, match="(?i)system.prompt.*(empty|missing)"):
            build_player_prompt(config)

    def test_raises_on_empty_generation_guidelines(self, valid_goal_config: GoalConfig) -> None:
        from prompts.player_prompts import build_player_prompt

        config = self._config_with_override(valid_goal_config, generation_guidelines="")
        with pytest.raises(ValueError, match="(?i)generation.guidelines.*(empty|missing)"):
            build_player_prompt(config)

    def test_raises_on_empty_output_schema(self, valid_goal_config: GoalConfig) -> None:
        from prompts.player_prompts import build_player_prompt

        config = self._config_with_override(valid_goal_config, output_schema={})
        with pytest.raises(ValueError, match="(?i)output.schema.*(empty|missing)"):
            build_player_prompt(config)

    def test_raises_on_empty_metadata_schema(self, valid_goal_config: GoalConfig) -> None:
        from prompts.player_prompts import build_player_prompt

        config = self._config_with_override(valid_goal_config, metadata_schema=[])
        with pytest.raises(ValueError, match="(?i)metadata.schema.*(empty|missing)"):
            build_player_prompt(config)

    def test_raises_on_empty_layer_routing(self, valid_goal_config: GoalConfig) -> None:
        from prompts.player_prompts import build_player_prompt

        config = self._config_with_override(valid_goal_config, layer_routing={})
        with pytest.raises(ValueError, match="(?i)layer.routing.*(empty|missing)"):
            build_player_prompt(config)


class TestCoachPromptValidation:
    """Builder functions validate all required GOAL.md sections are non-empty."""

    @staticmethod
    def _config_with_override(base: GoalConfig, **overrides: object) -> GoalConfig:
        """Create a GoalConfig bypassing Pydantic validators for test scenarios."""
        data = base.model_dump()
        data.update(overrides)
        return GoalConfig.model_construct(**data)

    def test_raises_on_empty_goal(self, valid_goal_config: GoalConfig) -> None:
        from prompts.coach_prompts import build_coach_prompt

        config = self._config_with_override(valid_goal_config, goal="")
        with pytest.raises(ValueError, match="(?i)goal.*(empty|missing|required)"):
            build_coach_prompt(config)

    def test_raises_on_empty_evaluation_criteria(self, valid_goal_config: GoalConfig) -> None:
        from prompts.coach_prompts import build_coach_prompt

        config = self._config_with_override(valid_goal_config, evaluation_criteria=[])
        with pytest.raises(ValueError, match="(?i)evaluation.criteria.*(empty|missing)"):
            build_coach_prompt(config)

    def test_raises_on_empty_output_schema(self, valid_goal_config: GoalConfig) -> None:
        from prompts.coach_prompts import build_coach_prompt

        config = self._config_with_override(valid_goal_config, output_schema={})
        with pytest.raises(ValueError, match="(?i)output.schema.*(empty|missing)"):
            build_coach_prompt(config)

    def test_raises_on_empty_metadata_schema(self, valid_goal_config: GoalConfig) -> None:
        from prompts.coach_prompts import build_coach_prompt

        config = self._config_with_override(valid_goal_config, metadata_schema=[])
        with pytest.raises(ValueError, match="(?i)metadata.schema.*(empty|missing)"):
            build_coach_prompt(config)

    def test_raises_on_empty_layer_routing(self, valid_goal_config: GoalConfig) -> None:
        from prompts.coach_prompts import build_coach_prompt

        config = self._config_with_override(valid_goal_config, layer_routing={})
        with pytest.raises(ValueError, match="(?i)layer.routing.*(empty|missing)"):
            build_coach_prompt(config)


# ---------------------------------------------------------------------------
# AC-005: Base prompt appears FIRST
# ---------------------------------------------------------------------------


class TestPromptOrdering:
    """Base prompt must appear FIRST, GOAL.md content appended after."""

    def test_player_base_prompt_is_first(self, valid_goal_config: GoalConfig) -> None:
        from prompts.player_prompts import PLAYER_BASE_PROMPT, build_player_prompt

        result = build_player_prompt(valid_goal_config)
        base_index = result.index(PLAYER_BASE_PROMPT)
        goal_index = result.index(valid_goal_config.goal)
        assert base_index < goal_index, "Base prompt must appear before GOAL.md content"

    def test_coach_base_prompt_is_first(self, valid_goal_config: GoalConfig) -> None:
        from prompts.coach_prompts import COACH_BASE_PROMPT, build_coach_prompt

        result = build_coach_prompt(valid_goal_config)
        base_index = result.index(COACH_BASE_PROMPT)
        goal_index = result.index(valid_goal_config.goal)
        assert base_index < goal_index, "Base prompt must appear before GOAL.md content"


# ---------------------------------------------------------------------------
# AC-006: Coach prompt includes all evaluation criteria names
# ---------------------------------------------------------------------------


class TestCoachCriteriaNames:
    """Coach prompt must include all evaluation criteria names for criteria_met validation."""

    def test_all_criteria_names_present(self, valid_goal_config: GoalConfig) -> None:
        from prompts.coach_prompts import build_coach_prompt

        result = build_coach_prompt(valid_goal_config)
        for criterion in valid_goal_config.evaluation_criteria:
            assert criterion.name in result, (
                f"Criterion '{criterion.name}' not found in coach prompt"
            )

    def test_criteria_met_instruction_present(self, valid_goal_config: GoalConfig) -> None:
        from prompts.coach_prompts import build_coach_prompt

        result = build_coach_prompt(valid_goal_config)
        assert "criteria_met" in result, "Coach prompt must reference criteria_met for validation"


# ---------------------------------------------------------------------------
# AC-007: GOAL.md content treated as domain context, not directives
# ---------------------------------------------------------------------------


class TestDomainContextDelimitation:
    """GOAL.md content must be clearly delimited as domain context."""

    def test_player_prompt_has_domain_context_delimiter(
        self, valid_goal_config: GoalConfig
    ) -> None:
        from prompts.player_prompts import build_player_prompt

        result = build_player_prompt(valid_goal_config)
        # The GOAL.md section should be wrapped with a clear "domain context" label
        assert "domain context" in result.lower() or "DOMAIN CONTEXT" in result

    def test_coach_prompt_has_domain_context_delimiter(self, valid_goal_config: GoalConfig) -> None:
        from prompts.coach_prompts import build_coach_prompt

        result = build_coach_prompt(valid_goal_config)
        assert "domain context" in result.lower() or "DOMAIN CONTEXT" in result

    def test_player_goal_content_not_at_start(self, valid_goal_config: GoalConfig) -> None:
        """GOAL.md content should not be at the very start of the prompt."""
        from prompts.player_prompts import build_player_prompt

        result = build_player_prompt(valid_goal_config)
        assert not result.startswith(valid_goal_config.goal)

    def test_coach_goal_content_not_at_start(self, valid_goal_config: GoalConfig) -> None:
        from prompts.coach_prompts import build_coach_prompt

        result = build_coach_prompt(valid_goal_config)
        assert not result.startswith(valid_goal_config.goal)
