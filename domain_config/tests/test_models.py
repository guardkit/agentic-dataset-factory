"""Tests for domain_config Pydantic models and GoalValidationError.

Follows the existing test patterns in synthesis/tests/test_validator.py:
- Organised by test class per model
- AAA pattern (Arrange, Act, Assert)
- pytest.raises(ValidationError) for negative cases
- pytest.mark.parametrize for boundary / negative sweeps
- Naming: test_<method_name>_<scenario>_<expected_result>
"""

import keyword

import pytest
from pydantic import ValidationError

from domain_config import (
    EvaluationCriterion,
    GenerationTarget,
    GoalConfig,
    GoalValidationError,
    MetadataField,
    SourceDocument,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def valid_source_document_kwargs():
    return {
        "file_pattern": "mr-bruff-*.pdf",
        "mode": "standard",
        "notes": "Digital PDFs",
    }


@pytest.fixture
def valid_generation_target_kwargs():
    return {
        "category": "Literary analysis (single-turn)",
        "type": "reasoning",
        "count": 200,
    }


@pytest.fixture
def valid_evaluation_criterion_kwargs():
    return {
        "name": "socratic_approach",
        "description": "Tutor guides via questions rather than giving answers",
        "weight": 0.25,
    }


@pytest.fixture
def valid_metadata_field_kwargs():
    return {
        "field": "layer",
        "type": "string",
        "required": True,
        "valid_values": ["behaviour", "knowledge"],
    }


@pytest.fixture
def valid_goal_config_kwargs(
    valid_source_document_kwargs,
    valid_generation_target_kwargs,
    valid_evaluation_criterion_kwargs,
    valid_metadata_field_kwargs,
):
    """Minimal valid GoalConfig kwargs."""
    return {
        "goal": "A" * 50,  # Exactly 50 chars — boundary
        "source_documents": [
            SourceDocument(**valid_source_document_kwargs),
        ],
        "system_prompt": "B" * 100,  # Exactly 100 chars — boundary
        "generation_targets": [
            GenerationTarget(**valid_generation_target_kwargs),
        ],
        "generation_guidelines": "C" * 100,  # Exactly 100 chars — boundary
        "evaluation_criteria": [
            EvaluationCriterion(
                name="criterion_a",
                description="First criterion",
                weight=0.4,
            ),
            EvaluationCriterion(
                name="criterion_b",
                description="Second criterion",
                weight=0.3,
            ),
            EvaluationCriterion(
                name="criterion_c",
                description="Third criterion",
                weight=0.3,
            ),
        ],
        "output_schema": {
            "messages": [],
            "metadata": {},
        },
        "metadata_schema": [
            MetadataField(**valid_metadata_field_kwargs),
        ],
        "layer_routing": {
            "behaviour": "output/train.jsonl",
            "knowledge": "output/rag_index/knowledge.jsonl",
        },
    }


# ---------------------------------------------------------------------------
# GoalValidationError tests
# ---------------------------------------------------------------------------


class TestGoalValidationError:
    def test_attributes_stored(self):
        err = GoalValidationError(
            section="Goal", message="too short"
        )
        assert err.section == "Goal"
        assert err.message == "too short"

    def test_str_includes_section_and_message(self):
        err = GoalValidationError(
            section="Source Documents",
            message="at least one row required",
        )
        assert "Source Documents" in str(err)
        assert "at least one row required" in str(err)

    def test_is_exception(self):
        err = GoalValidationError(section="Goal", message="x")
        assert isinstance(err, Exception)

    def test_can_be_raised_and_caught(self):
        with pytest.raises(GoalValidationError) as exc_info:
            raise GoalValidationError(
                section="System Prompt",
                message="minimum 100 characters",
            )
        assert exc_info.value.section == "System Prompt"
        assert exc_info.value.message == "minimum 100 characters"


# ---------------------------------------------------------------------------
# SourceDocument tests
# ---------------------------------------------------------------------------


class TestSourceDocument:
    def test_valid_standard_mode(self, valid_source_document_kwargs):
        doc = SourceDocument(**valid_source_document_kwargs)
        assert doc.file_pattern == "mr-bruff-*.pdf"
        assert doc.mode == "standard"
        assert doc.notes == "Digital PDFs"

    def test_valid_vlm_mode(self):
        doc = SourceDocument(
            file_pattern="scanned-*.pdf",
            mode="vlm",
            notes="Scanned pages",
        )
        assert doc.mode == "vlm"

    def test_notes_default_empty(self):
        doc = SourceDocument(
            file_pattern="file.pdf", mode="standard"
        )
        assert doc.notes == ""

    @pytest.mark.parametrize("mode", ["standard", "vlm"])
    def test_valid_modes_accepted(self, mode):
        doc = SourceDocument(
            file_pattern="x.pdf", mode=mode
        )
        assert doc.mode == mode

    @pytest.mark.parametrize(
        "bad_mode",
        ["ocr", "OCR", "Standard", "VLM", "auto", "", "pdf"],
    )
    def test_invalid_mode_rejected(self, bad_mode):
        with pytest.raises(ValidationError):
            SourceDocument(
                file_pattern="x.pdf", mode=bad_mode
            )

    def test_empty_file_pattern_rejected(self):
        with pytest.raises(ValidationError):
            SourceDocument(file_pattern="", mode="standard")


# ---------------------------------------------------------------------------
# GenerationTarget tests
# ---------------------------------------------------------------------------


class TestGenerationTarget:
    def test_valid_reasoning_target(
        self, valid_generation_target_kwargs
    ):
        target = GenerationTarget(
            **valid_generation_target_kwargs
        )
        assert target.category == "Literary analysis (single-turn)"
        assert target.type == "reasoning"
        assert target.count == 200

    def test_valid_direct_target(self):
        target = GenerationTarget(
            category="Factual recall",
            type="direct",
            count=100,
        )
        assert target.type == "direct"
        assert target.count == 100

    @pytest.mark.parametrize("type_val", ["reasoning", "direct"])
    def test_valid_types_accepted(self, type_val):
        target = GenerationTarget(
            category="cat", type=type_val, count=1
        )
        assert target.type == type_val

    @pytest.mark.parametrize(
        "bad_type",
        ["Reasoning", "DIRECT", "chain_of_thought", "", "cot"],
    )
    def test_invalid_type_rejected(self, bad_type):
        with pytest.raises(ValidationError):
            GenerationTarget(
                category="cat", type=bad_type, count=1
            )

    def test_zero_count_rejected(self):
        with pytest.raises(ValidationError):
            GenerationTarget(
                category="cat", type="reasoning", count=0
            )

    def test_negative_count_rejected(self):
        with pytest.raises(ValidationError):
            GenerationTarget(
                category="cat", type="reasoning", count=-5
            )

    def test_count_one_accepted(self):
        target = GenerationTarget(
            category="cat", type="reasoning", count=1
        )
        assert target.count == 1

    def test_empty_category_rejected(self):
        with pytest.raises(ValidationError):
            GenerationTarget(
                category="", type="reasoning", count=10
            )

    # -- grade_targets field --

    def test_grade_targets_default(self):
        target = GenerationTarget(
            category="cat", type="reasoning", count=1
        )
        assert target.grade_targets == [7]

    def test_grade_targets_explicit(self):
        target = GenerationTarget(
            category="cat", type="reasoning", count=1,
            grade_targets=[4, 5, 6, 7, 8, 9],
        )
        assert target.grade_targets == [4, 5, 6, 7, 8, 9]

    def test_grade_targets_null_values(self):
        target = GenerationTarget(
            category="cat", type="direct", count=1,
            grade_targets=[None],
        )
        assert target.grade_targets == [None]

    def test_grade_targets_mixed_int_and_null(self):
        target = GenerationTarget(
            category="cat", type="reasoning", count=1,
            grade_targets=[5, None, 8],
        )
        assert target.grade_targets == [5, None, 8]

    def test_grade_targets_empty_rejected(self):
        with pytest.raises(ValidationError, match="empty"):
            GenerationTarget(
                category="cat", type="reasoning", count=1,
                grade_targets=[],
            )

    @pytest.mark.parametrize("bad_grade", [3, 10, 0, -1, 100])
    def test_grade_targets_out_of_range_rejected(self, bad_grade):
        with pytest.raises(ValidationError, match="out of range"):
            GenerationTarget(
                category="cat", type="reasoning", count=1,
                grade_targets=[bad_grade],
            )

    def test_grade_targets_boundary_4_accepted(self):
        target = GenerationTarget(
            category="cat", type="reasoning", count=1,
            grade_targets=[4],
        )
        assert target.grade_targets == [4]

    def test_grade_targets_boundary_9_accepted(self):
        target = GenerationTarget(
            category="cat", type="reasoning", count=1,
            grade_targets=[9],
        )
        assert target.grade_targets == [9]


# ---------------------------------------------------------------------------
# EvaluationCriterion tests
# ---------------------------------------------------------------------------


class TestEvaluationCriterion:
    def test_valid_criterion(
        self, valid_evaluation_criterion_kwargs
    ):
        crit = EvaluationCriterion(
            **valid_evaluation_criterion_kwargs
        )
        assert crit.name == "socratic_approach"
        assert crit.weight == 0.25

    def test_valid_python_identifier_accepted(self):
        crit = EvaluationCriterion(
            name="factual_accuracy",
            description="desc",
            weight=0.1,
        )
        assert crit.name == "factual_accuracy"

    @pytest.mark.parametrize(
        "bad_name",
        [
            "socratic-approach",   # hyphen
            "123abc",              # starts with digit
            "has space",           # space
            "has.dot",             # dot
            "a+b",                 # operator
        ],
    )
    def test_invalid_identifier_rejected(self, bad_name):
        with pytest.raises(ValidationError, match="identifier"):
            EvaluationCriterion(
                name=bad_name, description="desc", weight=0.1
            )

    def test_empty_name_rejected(self):
        """Empty string is caught by min_length before the
        identifier validator."""
        with pytest.raises(ValidationError):
            EvaluationCriterion(
                name="", description="desc", weight=0.1
            )

    @pytest.mark.parametrize(
        "kw",
        [
            "class",
            "return",
            "import",
            "def",
            "if",
            "for",
            "while",
            "True",
            "False",
            "None",
        ],
    )
    def test_python_keyword_rejected(self, kw):
        with pytest.raises(ValidationError, match="keyword"):
            EvaluationCriterion(
                name=kw, description="desc", weight=0.1
            )

    def test_underscore_name_accepted(self):
        """Single underscore is a valid identifier, not a keyword."""
        crit = EvaluationCriterion(
            name="_private", description="desc", weight=0.1
        )
        assert crit.name == "_private"

    def test_weight_zero_accepted(self):
        crit = EvaluationCriterion(
            name="crit", description="desc", weight=0.0
        )
        assert crit.weight == 0.0

    def test_weight_one_accepted(self):
        crit = EvaluationCriterion(
            name="crit", description="desc", weight=1.0
        )
        assert crit.weight == 1.0

    def test_weight_negative_rejected(self):
        with pytest.raises(ValidationError):
            EvaluationCriterion(
                name="crit", description="desc", weight=-0.1
            )

    def test_weight_above_one_rejected(self):
        with pytest.raises(ValidationError):
            EvaluationCriterion(
                name="crit", description="desc", weight=1.01
            )

    def test_empty_description_rejected(self):
        with pytest.raises(ValidationError):
            EvaluationCriterion(
                name="crit", description="", weight=0.5
            )

    def test_builtin_name_accepted(self):
        """Built-in names (e.g. 'list', 'dict') are identifiers
        and not keywords, so they should be accepted."""
        crit = EvaluationCriterion(
            name="list", description="desc", weight=0.1
        )
        assert crit.name == "list"

    def test_all_keywords_are_covered(self):
        """Ensure our validator catches every Python keyword."""
        for kw in keyword.kwlist:
            with pytest.raises(ValidationError):
                EvaluationCriterion(
                    name=kw, description="desc", weight=0.1
                )


# ---------------------------------------------------------------------------
# MetadataField tests
# ---------------------------------------------------------------------------


class TestMetadataField:
    def test_valid_field(self, valid_metadata_field_kwargs):
        mf = MetadataField(**valid_metadata_field_kwargs)
        assert mf.field == "layer"
        assert mf.type == "string"
        assert mf.required is True
        assert mf.valid_values == ["behaviour", "knowledge"]

    def test_empty_valid_values_accepted(self):
        mf = MetadataField(
            field="turns",
            type="integer",
            required=True,
            valid_values=[],
        )
        assert mf.valid_values == []

    def test_default_valid_values_empty_list(self):
        mf = MetadataField(
            field="turns", type="integer", required=True
        )
        assert mf.valid_values == []

    def test_required_false_accepted(self):
        mf = MetadataField(
            field="optional_field",
            type="string",
            required=False,
        )
        assert mf.required is False

    def test_empty_field_name_rejected(self):
        with pytest.raises(ValidationError):
            MetadataField(
                field="", type="string", required=True
            )

    def test_empty_type_rejected(self):
        with pytest.raises(ValidationError):
            MetadataField(
                field="layer", type="", required=True
            )


# ---------------------------------------------------------------------------
# GoalConfig tests
# ---------------------------------------------------------------------------


class TestGoalConfig:
    def test_valid_config(self, valid_goal_config_kwargs):
        config = GoalConfig(**valid_goal_config_kwargs)
        assert len(config.goal) == 50
        assert len(config.source_documents) == 1
        assert len(config.system_prompt) == 100
        assert len(config.generation_targets) == 1
        assert len(config.generation_guidelines) == 100
        assert len(config.evaluation_criteria) == 3
        assert "messages" in config.output_schema
        assert "metadata" in config.output_schema
        assert len(config.metadata_schema) == 1
        assert "behaviour" in config.layer_routing
        assert "knowledge" in config.layer_routing

    def test_all_nine_fields_present(
        self, valid_goal_config_kwargs
    ):
        GoalConfig(**valid_goal_config_kwargs)
        expected_fields = {
            "goal",
            "source_documents",
            "system_prompt",
            "generation_targets",
            "generation_guidelines",
            "evaluation_criteria",
            "output_schema",
            "metadata_schema",
            "layer_routing",
        }
        assert set(GoalConfig.model_fields.keys()) == expected_fields

    # -- Goal boundary --

    def test_goal_exactly_50_chars_accepted(
        self, valid_goal_config_kwargs
    ):
        valid_goal_config_kwargs["goal"] = "X" * 50
        config = GoalConfig(**valid_goal_config_kwargs)
        assert len(config.goal) == 50

    def test_goal_49_chars_rejected(
        self, valid_goal_config_kwargs
    ):
        valid_goal_config_kwargs["goal"] = "X" * 49
        with pytest.raises(ValidationError):
            GoalConfig(**valid_goal_config_kwargs)

    def test_goal_empty_rejected(
        self, valid_goal_config_kwargs
    ):
        valid_goal_config_kwargs["goal"] = ""
        with pytest.raises(ValidationError):
            GoalConfig(**valid_goal_config_kwargs)

    # -- System Prompt boundary --

    def test_system_prompt_exactly_100_chars_accepted(
        self, valid_goal_config_kwargs
    ):
        valid_goal_config_kwargs["system_prompt"] = "Y" * 100
        config = GoalConfig(**valid_goal_config_kwargs)
        assert len(config.system_prompt) == 100

    def test_system_prompt_99_chars_rejected(
        self, valid_goal_config_kwargs
    ):
        valid_goal_config_kwargs["system_prompt"] = "Y" * 99
        with pytest.raises(ValidationError):
            GoalConfig(**valid_goal_config_kwargs)

    # -- Generation Guidelines boundary --

    def test_generation_guidelines_exactly_100_accepted(
        self, valid_goal_config_kwargs
    ):
        valid_goal_config_kwargs[
            "generation_guidelines"
        ] = "Z" * 100
        config = GoalConfig(**valid_goal_config_kwargs)
        assert len(config.generation_guidelines) == 100

    def test_generation_guidelines_99_rejected(
        self, valid_goal_config_kwargs
    ):
        valid_goal_config_kwargs[
            "generation_guidelines"
        ] = "Z" * 99
        with pytest.raises(ValidationError):
            GoalConfig(**valid_goal_config_kwargs)

    # -- source_documents minimum --

    def test_empty_source_documents_rejected(
        self, valid_goal_config_kwargs
    ):
        valid_goal_config_kwargs["source_documents"] = []
        with pytest.raises(ValidationError):
            GoalConfig(**valid_goal_config_kwargs)

    # -- evaluation_criteria minimum --

    def test_exactly_3_criteria_accepted(
        self, valid_goal_config_kwargs
    ):
        """Already has exactly 3 in the fixture."""
        config = GoalConfig(**valid_goal_config_kwargs)
        assert len(config.evaluation_criteria) == 3

    def test_2_criteria_rejected(
        self, valid_goal_config_kwargs
    ):
        valid_goal_config_kwargs["evaluation_criteria"] = [
            EvaluationCriterion(
                name="a", description="d", weight=0.5
            ),
            EvaluationCriterion(
                name="b", description="d", weight=0.5
            ),
        ]
        with pytest.raises(ValidationError):
            GoalConfig(**valid_goal_config_kwargs)

    # -- output_schema --

    def test_output_schema_accepts_dict(
        self, valid_goal_config_kwargs
    ):
        config = GoalConfig(**valid_goal_config_kwargs)
        assert isinstance(config.output_schema, dict)

    def test_output_schema_empty_dict_accepted(
        self, valid_goal_config_kwargs
    ):
        valid_goal_config_kwargs["output_schema"] = {}
        config = GoalConfig(**valid_goal_config_kwargs)
        assert config.output_schema == {}

    # -- layer_routing --

    def test_layer_routing_accepts_dict(
        self, valid_goal_config_kwargs
    ):
        config = GoalConfig(**valid_goal_config_kwargs)
        assert isinstance(config.layer_routing, dict)

    # -- metadata_schema --

    def test_metadata_schema_accepts_empty_list(
        self, valid_goal_config_kwargs
    ):
        valid_goal_config_kwargs["metadata_schema"] = []
        config = GoalConfig(**valid_goal_config_kwargs)
        assert config.metadata_schema == []

    # -- Field types --

    def test_field_types_correct(
        self, valid_goal_config_kwargs
    ):
        config = GoalConfig(**valid_goal_config_kwargs)
        assert isinstance(config.goal, str)
        assert isinstance(config.source_documents, list)
        assert isinstance(
            config.source_documents[0], SourceDocument
        )
        assert isinstance(config.system_prompt, str)
        assert isinstance(config.generation_targets, list)
        assert isinstance(
            config.generation_targets[0], GenerationTarget
        )
        assert isinstance(config.generation_guidelines, str)
        assert isinstance(config.evaluation_criteria, list)
        assert isinstance(
            config.evaluation_criteria[0], EvaluationCriterion
        )
        assert isinstance(config.output_schema, dict)
        assert isinstance(config.metadata_schema, list)
        assert isinstance(
            config.metadata_schema[0], MetadataField
        )
        assert isinstance(config.layer_routing, dict)

    # -- Missing required fields --

    def test_missing_goal_rejected(
        self, valid_goal_config_kwargs
    ):
        del valid_goal_config_kwargs["goal"]
        with pytest.raises(ValidationError):
            GoalConfig(**valid_goal_config_kwargs)

    def test_missing_source_documents_rejected(
        self, valid_goal_config_kwargs
    ):
        del valid_goal_config_kwargs["source_documents"]
        with pytest.raises(ValidationError):
            GoalConfig(**valid_goal_config_kwargs)

    def test_missing_system_prompt_rejected(
        self, valid_goal_config_kwargs
    ):
        del valid_goal_config_kwargs["system_prompt"]
        with pytest.raises(ValidationError):
            GoalConfig(**valid_goal_config_kwargs)

    def test_missing_evaluation_criteria_rejected(
        self, valid_goal_config_kwargs
    ):
        del valid_goal_config_kwargs["evaluation_criteria"]
        with pytest.raises(ValidationError):
            GoalConfig(**valid_goal_config_kwargs)


# ---------------------------------------------------------------------------
# Import contract tests
# ---------------------------------------------------------------------------


class TestImports:
    def test_all_models_importable_from_package(self):
        """All public names should be importable from domain_config."""
        from domain_config import (
            EvaluationCriterion,
            GenerationTarget,
            GoalConfig,
            GoalValidationError,
            MetadataField,
            SourceDocument,
        )

        assert all(
            cls is not None
            for cls in [
                SourceDocument,
                GenerationTarget,
                EvaluationCriterion,
                MetadataField,
                GoalConfig,
                GoalValidationError,
            ]
        )

    def test_all_models_importable_from_models_module(self):
        """All public names should also be importable from
        domain_config.models."""
        from domain_config.models import (
            EvaluationCriterion,
            GenerationTarget,
            GoalConfig,
            GoalValidationError,
            MetadataField,
            SourceDocument,
        )

        assert all(
            cls is not None
            for cls in [
                SourceDocument,
                GenerationTarget,
                EvaluationCriterion,
                MetadataField,
                GoalConfig,
                GoalValidationError,
            ]
        )

    def test_goal_validation_error_is_exception(self):
        assert issubclass(GoalValidationError, Exception)


# ---------------------------------------------------------------------------
# Acceptance criteria verification tests (AC-002 through AC-006)
# Each test directly verifies one acceptance criterion by inspecting
# the model class definitions and runtime behaviour.
# ---------------------------------------------------------------------------


class TestAC002_PydanticModelsMatchContract:
    """AC-002: All 5 Pydantic models match the API contract field types."""

    def test_source_document_fields_match_contract(self):
        """SourceDocument: file_pattern(str), mode(Literal), notes(str)."""
        doc = SourceDocument(
            file_pattern="*.pdf", mode="standard", notes="n"
        )
        assert isinstance(doc.file_pattern, str)
        assert isinstance(doc.mode, str)
        assert doc.mode in ("standard", "vlm")
        assert isinstance(doc.notes, str)
        # Verify exact field names from API contract
        assert set(SourceDocument.model_fields.keys()) == {
            "file_pattern", "mode", "notes",
        }

    def test_generation_target_fields_match_contract(self):
        """GenerationTarget: category(str), type(Literal), count(int), grade_targets(list)."""
        t = GenerationTarget(
            category="cat", type="reasoning", count=10
        )
        assert isinstance(t.category, str)
        assert isinstance(t.type, str)
        assert t.type in ("reasoning", "direct")
        assert isinstance(t.count, int)
        assert isinstance(t.grade_targets, list)
        assert set(GenerationTarget.model_fields.keys()) == {
            "category", "type", "count", "grade_targets",
        }

    def test_evaluation_criterion_fields_match_contract(self):
        """EvaluationCriterion: name(str), description(str), weight(float)."""
        c = EvaluationCriterion(
            name="crit_name", description="desc", weight=0.5
        )
        assert isinstance(c.name, str)
        assert isinstance(c.description, str)
        assert isinstance(c.weight, float)
        assert set(EvaluationCriterion.model_fields.keys()) == {
            "name", "description", "weight",
        }

    def test_metadata_field_fields_match_contract(self):
        """MetadataField: field(str), type(str), required(bool),
        valid_values(list[str])."""
        mf = MetadataField(
            field="f", type="string", required=True,
            valid_values=["a"],
        )
        assert isinstance(mf.field, str)
        assert isinstance(mf.type, str)
        assert isinstance(mf.required, bool)
        assert isinstance(mf.valid_values, list)
        assert set(MetadataField.model_fields.keys()) == {
            "field", "type", "required", "valid_values",
        }

    def test_goal_config_fields_match_contract(self):
        """GoalConfig: all 9 fields with correct types."""
        assert set(GoalConfig.model_fields.keys()) == {
            "goal", "source_documents", "system_prompt",
            "generation_targets", "generation_guidelines",
            "evaluation_criteria", "output_schema",
            "metadata_schema", "layer_routing",
        }

    def test_all_five_models_are_pydantic_base_model(self):
        """All 5 models must be Pydantic BaseModel subclasses."""
        from pydantic import BaseModel
        for model_cls in [
            SourceDocument, GenerationTarget,
            EvaluationCriterion, MetadataField, GoalConfig,
        ]:
            assert issubclass(model_cls, BaseModel), (
                f"{model_cls.__name__} is not a BaseModel"
            )


class TestAC003_SourceDocumentModeLiteral:
    """AC-003: SourceDocument.mode constrained to Literal["standard","vlm"]."""

    def test_standard_accepted(self):
        doc = SourceDocument(
            file_pattern="f.pdf", mode="standard"
        )
        assert doc.mode == "standard"

    def test_vlm_accepted(self):
        doc = SourceDocument(
            file_pattern="f.pdf", mode="vlm"
        )
        assert doc.mode == "vlm"

    def test_ocr_rejected(self):
        with pytest.raises(ValidationError):
            SourceDocument(
                file_pattern="f.pdf", mode="ocr"
            )

    def test_arbitrary_string_rejected(self):
        with pytest.raises(ValidationError):
            SourceDocument(
                file_pattern="f.pdf", mode="anything_else"
            )


class TestAC004_GenerationTargetTypeLiteral:
    """AC-004: GenerationTarget.type constrained to
    Literal["reasoning","direct"]."""

    def test_reasoning_accepted(self):
        t = GenerationTarget(
            category="c", type="reasoning", count=1
        )
        assert t.type == "reasoning"

    def test_direct_accepted(self):
        t = GenerationTarget(
            category="c", type="direct", count=1
        )
        assert t.type == "direct"

    def test_invalid_type_rejected(self):
        with pytest.raises(ValidationError):
            GenerationTarget(
                category="c", type="invalid", count=1
            )


class TestAC005_EvaluationCriterionNameValidation:
    """AC-005: EvaluationCriterion.name validated as Python identifier
    and not a keyword."""

    def test_valid_identifier_accepted(self):
        c = EvaluationCriterion(
            name="socratic_approach", description="d", weight=0.1
        )
        assert c.name == "socratic_approach"
        assert c.name.isidentifier()

    def test_hyphenated_name_rejected_as_not_identifier(self):
        with pytest.raises(ValidationError, match="identifier"):
            EvaluationCriterion(
                name="socratic-approach", description="d",
                weight=0.1,
            )

    def test_keyword_class_rejected(self):
        with pytest.raises(ValidationError, match="keyword"):
            EvaluationCriterion(
                name="class", description="d", weight=0.1
            )

    def test_keyword_import_rejected(self):
        with pytest.raises(ValidationError, match="keyword"):
            EvaluationCriterion(
                name="import", description="d", weight=0.1
            )

    def test_uses_str_isidentifier(self):
        """Verify the validator uses str.isidentifier()."""
        # "123" is not a valid identifier per str.isidentifier()
        assert not "123".isidentifier()
        with pytest.raises(ValidationError):
            EvaluationCriterion(
                name="123", description="d", weight=0.1
            )

    def test_uses_keyword_iskeyword(self):
        """Verify the validator uses keyword.iskeyword()."""
        assert keyword.iskeyword("for")
        with pytest.raises(ValidationError):
            EvaluationCriterion(
                name="for", description="d", weight=0.1
            )


class TestAC006_GoalValidationErrorException:
    """AC-006: GoalValidationError exception class with section and
    message attributes."""

    def test_is_exception_subclass(self):
        assert issubclass(GoalValidationError, Exception)

    def test_has_section_attribute(self):
        err = GoalValidationError(
            section="Goal", message="too short"
        )
        assert hasattr(err, "section")
        assert err.section == "Goal"

    def test_has_message_attribute(self):
        err = GoalValidationError(
            section="Goal", message="too short"
        )
        assert hasattr(err, "message")
        assert err.message == "too short"

    def test_constructor_signature(self):
        """Constructor takes exactly section and message params."""
        import inspect
        sig = inspect.signature(GoalValidationError.__init__)
        params = list(sig.parameters.keys())
        assert "self" in params
        assert "section" in params
        assert "message" in params

    def test_raise_and_catch(self):
        with pytest.raises(GoalValidationError) as exc_info:
            raise GoalValidationError(
                section="Source Documents",
                message="at least one row required",
            )
        assert exc_info.value.section == "Source Documents"
        assert exc_info.value.message == "at least one row required"
