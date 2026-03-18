"""Tests for Pydantic validation models."""

import pytest
from pydantic import ValidationError

from synthesis.validator import (
    GenerationPlan,
    GenerationTarget,
    Message,
    Metadata,
    RejectionRecord,
    TrainingExample,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def valid_metadata_kwargs():
    return {
        "layer": "behaviour",
        "type": "reasoning",
        "ao": ["AO1", "AO3"],
        "text": "macbeth",
        "topic": "character_analysis",
        "grade_target": 7,
        "source": "synthetic",
        "turns": 1,
    }


@pytest.fixture
def valid_metadata(valid_metadata_kwargs):
    return Metadata(**valid_metadata_kwargs)


@pytest.fixture
def valid_messages():
    return [
        Message(role="system", content="You are a tutor."),
        Message(role="user", content="Explain Macbeth."),
        Message(role="assistant", content="Macbeth is a tragedy..."),
    ]


@pytest.fixture
def valid_generation_target():
    return GenerationTarget(
        text="macbeth",
        topic="character_analysis",
        grade_target=7,
        layer="behaviour",
        type="reasoning",
    )


# ---------------------------------------------------------------------------
# Message tests
# ---------------------------------------------------------------------------


class TestMessage:
    def test_valid_message(self):
        msg = Message(role="system", content="Hello")
        assert msg.role == "system"
        assert msg.content == "Hello"

    @pytest.mark.parametrize("role", ["system", "user", "assistant"])
    def test_valid_roles(self, role):
        msg = Message(role=role, content="text")
        assert msg.role == role

    def test_invalid_role_rejected(self):
        with pytest.raises(ValidationError):
            Message(role="admin", content="text")

    def test_empty_content_rejected(self):
        with pytest.raises(ValidationError):
            Message(role="user", content="")


# ---------------------------------------------------------------------------
# Metadata tests
# ---------------------------------------------------------------------------


class TestMetadata:
    def test_valid_metadata(self, valid_metadata_kwargs):
        meta = Metadata(**valid_metadata_kwargs)
        assert meta.layer == "behaviour"
        assert meta.ao == ["AO1", "AO3"]
        assert meta.grade_target == 7

    def test_defaults(self):
        meta = Metadata(
            layer="knowledge",
            type="direct",
            text="general",
            topic="encouragement",
        )
        assert meta.ao == []
        assert meta.source == "synthetic"
        assert meta.turns == 1
        assert meta.grade_target is None

    def test_empty_ao_list_allowed(self, valid_metadata_kwargs):
        valid_metadata_kwargs["ao"] = []
        meta = Metadata(**valid_metadata_kwargs)
        assert meta.ao == []

    @pytest.mark.parametrize("code", ["AO1", "AO2", "AO3", "AO4", "AO5", "AO6"])
    def test_valid_ao_codes(self, valid_metadata_kwargs, code):
        valid_metadata_kwargs["ao"] = [code]
        meta = Metadata(**valid_metadata_kwargs)
        assert meta.ao == [code]

    @pytest.mark.parametrize("bad_code", ["AO0", "AO7", "AO", "ao1", "A01", "XX1", "AO12"])
    def test_invalid_ao_codes_rejected(self, valid_metadata_kwargs, bad_code):
        valid_metadata_kwargs["ao"] = [bad_code]
        with pytest.raises(ValidationError, match="AO code"):
            Metadata(**valid_metadata_kwargs)

    def test_invalid_text_rejected(self, valid_metadata_kwargs):
        valid_metadata_kwargs["text"] = "hamlet"
        with pytest.raises(ValidationError):
            Metadata(**valid_metadata_kwargs)

    def test_invalid_topic_rejected(self, valid_metadata_kwargs):
        valid_metadata_kwargs["topic"] = "unknown_topic"
        with pytest.raises(ValidationError):
            Metadata(**valid_metadata_kwargs)

    def test_grade_target_null_allowed(self, valid_metadata_kwargs):
        valid_metadata_kwargs["grade_target"] = None
        meta = Metadata(**valid_metadata_kwargs)
        assert meta.grade_target is None

    @pytest.mark.parametrize("grade", [4, 5, 6, 7, 8, 9])
    def test_valid_grade_targets(self, valid_metadata_kwargs, grade):
        valid_metadata_kwargs["grade_target"] = grade
        meta = Metadata(**valid_metadata_kwargs)
        assert meta.grade_target == grade

    @pytest.mark.parametrize("grade", [0, 1, 2, 3, 10, 11, -1, 100])
    def test_invalid_grade_targets_rejected(self, valid_metadata_kwargs, grade):
        valid_metadata_kwargs["grade_target"] = grade
        with pytest.raises(ValidationError, match="grade_target"):
            Metadata(**valid_metadata_kwargs)

    def test_invalid_layer_rejected(self, valid_metadata_kwargs):
        valid_metadata_kwargs["layer"] = "invalid"
        with pytest.raises(ValidationError):
            Metadata(**valid_metadata_kwargs)

    def test_invalid_type_rejected(self, valid_metadata_kwargs):
        valid_metadata_kwargs["type"] = "invalid"
        with pytest.raises(ValidationError):
            Metadata(**valid_metadata_kwargs)

    def test_turns_zero_rejected(self, valid_metadata_kwargs):
        valid_metadata_kwargs["turns"] = 0
        with pytest.raises(ValidationError):
            Metadata(**valid_metadata_kwargs)

    def test_negative_turns_rejected(self, valid_metadata_kwargs):
        valid_metadata_kwargs["turns"] = -1
        with pytest.raises(ValidationError):
            Metadata(**valid_metadata_kwargs)

    def test_invalid_source_rejected(self, valid_metadata_kwargs):
        valid_metadata_kwargs["source"] = "manual"
        with pytest.raises(ValidationError):
            Metadata(**valid_metadata_kwargs)


# ---------------------------------------------------------------------------
# TrainingExample tests
# ---------------------------------------------------------------------------


class TestTrainingExample:
    def test_valid_example(self, valid_messages, valid_metadata):
        example = TrainingExample(messages=valid_messages, metadata=valid_metadata)
        assert len(example.messages) == 3
        assert example.metadata.layer == "behaviour"

    def test_minimum_two_messages(self, valid_metadata):
        msgs = [
            Message(role="system", content="sys"),
            Message(role="user", content="hi"),
        ]
        example = TrainingExample(messages=msgs, metadata=valid_metadata)
        assert len(example.messages) == 2

    def test_single_message_rejected(self, valid_metadata):
        with pytest.raises(ValidationError):
            TrainingExample(
                messages=[Message(role="system", content="sys")],
                metadata=valid_metadata,
            )

    def test_empty_messages_rejected(self, valid_metadata):
        with pytest.raises(ValidationError):
            TrainingExample(messages=[], metadata=valid_metadata)

    def test_first_message_must_be_system(self, valid_metadata):
        msgs = [
            Message(role="user", content="hi"),
            Message(role="assistant", content="hello"),
        ]
        with pytest.raises(ValidationError, match="system"):
            TrainingExample(messages=msgs, metadata=valid_metadata)

    def test_alternating_user_assistant(self, valid_metadata):
        msgs = [
            Message(role="system", content="sys"),
            Message(role="user", content="q1"),
            Message(role="user", content="q2"),  # wrong: should be assistant
        ]
        with pytest.raises(ValidationError, match="assistant"):
            TrainingExample(messages=msgs, metadata=valid_metadata)

    def test_assistant_after_system_rejected(self, valid_metadata):
        msgs = [
            Message(role="system", content="sys"),
            Message(role="assistant", content="hi"),  # wrong: should be user
        ]
        with pytest.raises(ValidationError, match="user"):
            TrainingExample(messages=msgs, metadata=valid_metadata)

    def test_multi_turn_valid(self, valid_metadata):
        msgs = [
            Message(role="system", content="sys"),
            Message(role="user", content="q1"),
            Message(role="assistant", content="a1"),
            Message(role="user", content="q2"),
            Message(role="assistant", content="a2"),
        ]
        example = TrainingExample(messages=msgs, metadata=valid_metadata)
        assert len(example.messages) == 5


# ---------------------------------------------------------------------------
# GenerationTarget tests
# ---------------------------------------------------------------------------


class TestGenerationTarget:
    def test_valid_target(self, valid_generation_target):
        assert valid_generation_target.text == "macbeth"
        assert valid_generation_target.ao == []
        assert valid_generation_target.turns == 1

    def test_defaults(self):
        target = GenerationTarget(
            text="macbeth",
            topic="character_analysis",
            grade_target=None,
            layer="knowledge",
            type="direct",
        )
        assert target.ao == []
        assert target.turns == 1
        assert target.grade_target is None

    def test_with_ao_and_turns(self):
        target = GenerationTarget(
            text="macbeth",
            topic="character_analysis",
            grade_target=5,
            layer="behaviour",
            type="reasoning",
            ao=["AO1", "AO2"],
            turns=3,
        )
        assert target.ao == ["AO1", "AO2"]
        assert target.turns == 3


# ---------------------------------------------------------------------------
# GenerationPlan tests
# ---------------------------------------------------------------------------


class TestGenerationPlan:
    def test_valid_plan(self, valid_generation_target):
        plan = GenerationPlan(generation_targets=[valid_generation_target])
        assert len(plan.generation_targets) == 1

    def test_empty_plan(self):
        plan = GenerationPlan(generation_targets=[])
        assert len(plan.generation_targets) == 0


# ---------------------------------------------------------------------------
# RejectionRecord tests
# ---------------------------------------------------------------------------


class TestRejectionRecord:
    def test_valid_record(self, valid_generation_target):
        record = RejectionRecord(
            target=valid_generation_target,
            reason="malformed_content",
            raw_response='{"bad": "json"}',
            timestamp="2025-01-15T10:30:00Z",
        )
        assert record.reason == "malformed_content"
        assert record.raw_response == '{"bad": "json"}'

    def test_null_raw_response(self, valid_generation_target):
        record = RejectionRecord(
            target=valid_generation_target,
            reason="api_error",
            timestamp="2025-01-15T10:30:00Z",
        )
        assert record.raw_response is None


# ---------------------------------------------------------------------------
# Import contract test
# ---------------------------------------------------------------------------


class TestImports:
    def test_all_models_importable(self):
        from synthesis.validator import (
            GenerationPlan,
            GenerationTarget,
            Message,
            Metadata,
            RejectionRecord,
            TrainingExample,
        )

        assert all(
            cls is not None
            for cls in [
                Message,
                Metadata,
                TrainingExample,
                GenerationTarget,
                GenerationPlan,
                RejectionRecord,
            ]
        )
