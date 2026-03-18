"""Tests for prompt templates."""

from __future__ import annotations

from dataclasses import fields

import pytest

from synthesis.templates import (
    TUTOR_SYSTEM_PROMPT,
    PromptPair,
    build_direct_prompt,
    build_multiturn_prompt,
    build_reasoning_prompt,
    select_template,
)
from synthesis.validator import GenerationTarget


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def reasoning_target() -> GenerationTarget:
    return GenerationTarget(
        text="macbeth",
        topic="character_analysis",
        grade_target=7,
        layer="behaviour",
        type="reasoning",
        ao=["AO1", "AO2"],
    )


@pytest.fixture()
def multiturn_target() -> GenerationTarget:
    return GenerationTarget(
        text="a_christmas_carol",
        topic="essay_feedback",
        grade_target=6,
        layer="behaviour",
        type="reasoning",
        ao=["AO1", "AO2"],
    )


@pytest.fixture()
def direct_target() -> GenerationTarget:
    return GenerationTarget(
        text="an_inspector_calls",
        topic="factual_recall",
        grade_target=None,
        layer="knowledge",
        type="direct",
    )


# ---------------------------------------------------------------------------
# PromptPair tests
# ---------------------------------------------------------------------------


class TestPromptPair:
    def test_has_system_prompt_field(self):
        field_names = {f.name for f in fields(PromptPair)}
        assert "system_prompt" in field_names

    def test_has_user_prompt_field(self):
        field_names = {f.name for f in fields(PromptPair)}
        assert "user_prompt" in field_names

    def test_construction(self):
        pair = PromptPair(system_prompt="sys", user_prompt="user")
        assert pair.system_prompt == "sys"
        assert pair.user_prompt == "user"

    def test_fields_are_strings(self):
        pair = PromptPair(system_prompt="sys", user_prompt="user")
        assert isinstance(pair.system_prompt, str)
        assert isinstance(pair.user_prompt, str)


# ---------------------------------------------------------------------------
# TUTOR_SYSTEM_PROMPT tests
# ---------------------------------------------------------------------------


class TestTutorSystemPrompt:
    def test_is_string(self):
        assert isinstance(TUTOR_SYSTEM_PROMPT, str)

    def test_contains_gcse_tutor_role(self):
        assert "GCSE English tutor" in TUTOR_SYSTEM_PROMPT

    def test_contains_aqa_reference(self):
        assert "AQA" in TUTOR_SYSTEM_PROMPT

    def test_contains_socratic_reference(self):
        assert "Socratic" in TUTOR_SYSTEM_PROMPT

    def test_non_empty(self):
        assert len(TUTOR_SYSTEM_PROMPT) > 0


# ---------------------------------------------------------------------------
# build_reasoning_prompt tests
# ---------------------------------------------------------------------------


class TestBuildReasoningPrompt:
    def test_returns_prompt_pair(self, reasoning_target):
        result = build_reasoning_prompt(reasoning_target)
        assert isinstance(result, PromptPair)

    def test_system_prompt_is_non_empty_string(self, reasoning_target):
        result = build_reasoning_prompt(reasoning_target)
        assert isinstance(result.system_prompt, str)
        assert len(result.system_prompt) > 0

    def test_user_prompt_contains_text(self, reasoning_target):
        result = build_reasoning_prompt(reasoning_target)
        assert "macbeth" in result.user_prompt

    def test_user_prompt_contains_topic(self, reasoning_target):
        result = build_reasoning_prompt(reasoning_target)
        assert "character_analysis" in result.user_prompt

    def test_user_prompt_contains_grade_target(self, reasoning_target):
        result = build_reasoning_prompt(reasoning_target)
        assert "7" in result.user_prompt

    def test_includes_return_only_json_instruction(self, reasoning_target):
        result = build_reasoning_prompt(reasoning_target)
        assert "Return only the JSON object, no preamble" in result.user_prompt

    def test_includes_think_block_instruction(self, reasoning_target):
        result = build_reasoning_prompt(reasoning_target)
        assert "<think>" in result.user_prompt

    def test_includes_tutor_system_prompt(self, reasoning_target):
        result = build_reasoning_prompt(reasoning_target)
        assert TUTOR_SYSTEM_PROMPT in result.user_prompt

    def test_null_grade_target_renders_as_null(self):
        target = GenerationTarget(
            text="macbeth",
            topic="language_analysis",
            grade_target=None,
            layer="behaviour",
            type="reasoning",
        )
        result = build_reasoning_prompt(target)
        assert "null" in result.user_prompt

    def test_user_prompt_is_string(self, reasoning_target):
        result = build_reasoning_prompt(reasoning_target)
        assert isinstance(result.user_prompt, str)


# ---------------------------------------------------------------------------
# build_multiturn_prompt tests
# ---------------------------------------------------------------------------


class TestBuildMultiturnPrompt:
    def test_returns_prompt_pair(self, multiturn_target):
        result = build_multiturn_prompt(multiturn_target)
        assert isinstance(result, PromptPair)

    def test_user_prompt_contains_text(self, multiturn_target):
        result = build_multiturn_prompt(multiturn_target)
        assert "a_christmas_carol" in result.user_prompt

    def test_user_prompt_contains_topic(self, multiturn_target):
        result = build_multiturn_prompt(multiturn_target)
        assert "essay_feedback" in result.user_prompt

    def test_user_prompt_contains_grade_target(self, multiturn_target):
        result = build_multiturn_prompt(multiturn_target)
        assert "6" in result.user_prompt

    def test_requests_4_plus_messages_after_system(self, multiturn_target):
        result = build_multiturn_prompt(multiturn_target)
        assert "4 or more messages after the system message" in result.user_prompt

    def test_requests_think_blocks_in_each_assistant_turn(self, multiturn_target):
        result = build_multiturn_prompt(multiturn_target)
        assert "<think>" in result.user_prompt

    def test_includes_return_only_json_instruction(self, multiturn_target):
        result = build_multiturn_prompt(multiturn_target)
        assert "Return only the JSON object, no preamble" in result.user_prompt

    def test_includes_tutor_system_prompt(self, multiturn_target):
        result = build_multiturn_prompt(multiturn_target)
        assert TUTOR_SYSTEM_PROMPT in result.user_prompt

    def test_ao_list_included_in_prompt(self, multiturn_target):
        result = build_multiturn_prompt(multiturn_target)
        assert "AO1" in result.user_prompt
        assert "AO2" in result.user_prompt

    def test_empty_ao_falls_back_to_description(self):
        target = GenerationTarget(
            text="macbeth",
            topic="essay_feedback",
            grade_target=5,
            layer="behaviour",
            type="reasoning",
            ao=[],
        )
        result = build_multiturn_prompt(target)
        assert "all relevant AOs" in result.user_prompt


# ---------------------------------------------------------------------------
# build_direct_prompt tests
# ---------------------------------------------------------------------------


class TestBuildDirectPrompt:
    def test_returns_prompt_pair(self, direct_target):
        result = build_direct_prompt(direct_target)
        assert isinstance(result, PromptPair)

    def test_user_prompt_contains_text(self, direct_target):
        result = build_direct_prompt(direct_target)
        assert "an_inspector_calls" in result.user_prompt

    def test_user_prompt_contains_topic(self, direct_target):
        result = build_direct_prompt(direct_target)
        assert "factual_recall" in result.user_prompt

    def test_includes_return_only_json_instruction(self, direct_target):
        result = build_direct_prompt(direct_target)
        assert "Return only the JSON object, no preamble" in result.user_prompt

    def test_no_think_block_instruction(self, direct_target):
        result = build_direct_prompt(direct_target)
        assert "NOT include a <think> block" in result.user_prompt

    def test_includes_tutor_system_prompt(self, direct_target):
        result = build_direct_prompt(direct_target)
        assert TUTOR_SYSTEM_PROMPT in result.user_prompt

    def test_null_grade_target_renders_as_null(self, direct_target):
        result = build_direct_prompt(direct_target)
        assert "null" in result.user_prompt

    def test_user_prompt_is_string(self, direct_target):
        result = build_direct_prompt(direct_target)
        assert isinstance(result.user_prompt, str)


# ---------------------------------------------------------------------------
# select_template tests
# ---------------------------------------------------------------------------


class TestSelectTemplate:
    def test_reasoning_essay_feedback_returns_multiturn(self, multiturn_target):
        fn = select_template(multiturn_target)
        assert fn is build_multiturn_prompt

    def test_reasoning_character_analysis_returns_reasoning(self, reasoning_target):
        fn = select_template(reasoning_target)
        assert fn is build_reasoning_prompt

    def test_reasoning_language_analysis_returns_reasoning(self):
        target = GenerationTarget(
            text="macbeth",
            topic="language_analysis",
            grade_target=5,
            layer="behaviour",
            type="reasoning",
        )
        fn = select_template(target)
        assert fn is build_reasoning_prompt

    def test_reasoning_exam_technique_returns_reasoning(self):
        target = GenerationTarget(
            text="language_paper_1",
            topic="exam_technique",
            grade_target=6,
            layer="behaviour",
            type="reasoning",
        )
        fn = select_template(target)
        assert fn is build_reasoning_prompt

    def test_reasoning_structure_analysis_returns_reasoning(self):
        target = GenerationTarget(
            text="macbeth",
            topic="structure_analysis",
            grade_target=7,
            layer="behaviour",
            type="reasoning",
        )
        fn = select_template(target)
        assert fn is build_reasoning_prompt

    def test_direct_factual_recall_returns_direct(self, direct_target):
        fn = select_template(direct_target)
        assert fn is build_direct_prompt

    def test_direct_terminology_returns_direct(self):
        target = GenerationTarget(
            text="general",
            topic="terminology",
            grade_target=None,
            layer="knowledge",
            type="direct",
        )
        fn = select_template(target)
        assert fn is build_direct_prompt

    def test_direct_encouragement_returns_direct(self):
        target = GenerationTarget(
            text="general",
            topic="encouragement",
            grade_target=None,
            layer="behaviour",
            type="direct",
        )
        fn = select_template(target)
        assert fn is build_direct_prompt

    def test_selected_function_is_callable(self, reasoning_target):
        fn = select_template(reasoning_target)
        assert callable(fn)

    def test_selected_function_returns_prompt_pair(self, reasoning_target):
        fn = select_template(reasoning_target)
        result = fn(reasoning_target)
        assert isinstance(result, PromptPair)

    def test_multiturn_selected_function_returns_prompt_pair(self, multiturn_target):
        fn = select_template(multiturn_target)
        result = fn(multiturn_target)
        assert isinstance(result, PromptPair)

    def test_direct_selected_function_returns_prompt_pair(self, direct_target):
        fn = select_template(direct_target)
        result = fn(direct_target)
        assert isinstance(result, PromptPair)


# ---------------------------------------------------------------------------
# Import contract test
# ---------------------------------------------------------------------------


class TestImports:
    def test_all_exports_importable(self):
        from synthesis.templates import (
            TUTOR_SYSTEM_PROMPT,
            PromptPair,
            build_direct_prompt,
            build_multiturn_prompt,
            build_reasoning_prompt,
            select_template,
        )

        assert all(
            obj is not None
            for obj in [
                TUTOR_SYSTEM_PROMPT,
                PromptPair,
                build_direct_prompt,
                build_multiturn_prompt,
                build_reasoning_prompt,
                select_template,
            ]
        )
