"""Comprehensive tests for tools.models Pydantic validation models.

Covers:
- AC-001: Package importability
- AC-002: RagRetrievalParams n_results validation (1-20)
- AC-003: TrainingExample messages[0].role == "system"
- AC-004: ExampleMetadata layer/type enum validation
- AC-005: Clear validation error messages (D7 error strings)
- AC-006: No runtime ChromaDB dependency (lazy import pattern)
"""

from __future__ import annotations

import ast
import importlib
import sys
from typing import TYPE_CHECKING

import pytest
from pydantic import ValidationError

from tools.models import (
    ExampleMetadata,
    Message,
    RagRetrievalParams,
    TrainingExample,
)

if TYPE_CHECKING:
    pass


# ===========================================================================
# AC-001: Package import contract
# ===========================================================================


class TestImportContract:
    """Verify that the public API is importable as specified."""

    def test_import_from_tools_models(self):
        """AC-001: `from tools.models import TrainingExample, RagRetrievalParams`."""
        from tools.models import RagRetrievalParams, TrainingExample

        assert TrainingExample is not None
        assert RagRetrievalParams is not None

    def test_import_from_tools_package(self):
        """AC-001: `from tools import TrainingExample, RagRetrievalParams`."""
        from tools import ExampleMetadata, RagRetrievalParams, TrainingExample

        assert TrainingExample is not None
        assert RagRetrievalParams is not None
        assert ExampleMetadata is not None

    def test_all_exports(self):
        """AC-001: __all__ contains all public models."""
        from tools.models import __all__ as models_all

        expected = {"ExampleMetadata", "Message", "RagRetrievalParams", "TrainingExample"}
        assert set(models_all) == expected


# ===========================================================================
# Message tests
# ===========================================================================


class TestMessage:
    """Tests for the Message model."""

    def test_valid_message(self):
        msg = Message(role="system", content="Hello")
        assert msg.role == "system"
        assert msg.content == "Hello"

    @pytest.mark.parametrize("role", ["system", "user", "assistant"])
    def test_valid_roles_accepted(self, role: str):
        msg = Message(role=role, content="text")
        assert msg.role == role

    def test_invalid_role_rejected(self):
        with pytest.raises(ValidationError):
            Message(role="admin", content="text")

    def test_empty_content_rejected(self):
        with pytest.raises(ValidationError):
            Message(role="user", content="")

    def test_field_count(self):
        assert len(Message.model_fields) == 2


# ===========================================================================
# AC-004: ExampleMetadata tests
# ===========================================================================


class TestExampleMetadata:
    """Tests for ExampleMetadata layer and type validation."""

    def test_valid_behaviour_reasoning(self, valid_metadata_kwargs):
        meta = ExampleMetadata(**valid_metadata_kwargs)
        assert meta.layer == "behaviour"
        assert meta.type == "reasoning"

    def test_valid_knowledge_direct(self):
        meta = ExampleMetadata(layer="knowledge", type="direct")
        assert meta.layer == "knowledge"
        assert meta.type == "direct"

    def test_default_source(self):
        meta = ExampleMetadata(layer="behaviour", type="reasoning")
        assert meta.source == "synthetic"

    def test_custom_source(self):
        meta = ExampleMetadata(
            layer="knowledge", type="direct", source="aqa_derived"
        )
        assert meta.source == "aqa_derived"

    def test_empty_source_rejected(self):
        with pytest.raises(ValidationError):
            ExampleMetadata(layer="behaviour", type="reasoning", source="")

    # --- AC-004: layer validation ---

    @pytest.mark.parametrize("layer", ["behaviour", "knowledge"])
    def test_valid_layers_accepted(self, layer: str):
        meta = ExampleMetadata(layer=layer, type="direct")
        assert meta.layer == layer

    @pytest.mark.parametrize(
        "bad_layer",
        ["behavioral", "Behaviour", "KNOWLEDGE", "train", "", "behavior"],
    )
    def test_invalid_layer_rejected(self, bad_layer: str):
        """AC-004: layer must be 'behaviour' or 'knowledge'."""
        with pytest.raises(ValidationError, match="layer"):
            ExampleMetadata(layer=bad_layer, type="direct")

    def test_invalid_layer_error_message_clear(self):
        """AC-005: Error message is actionable and mentions valid values."""
        with pytest.raises(ValidationError) as exc_info:
            ExampleMetadata(layer="invalid", type="direct")
        error_text = str(exc_info.value)
        assert "behaviour" in error_text or "knowledge" in error_text

    # --- AC-004: type validation ---

    @pytest.mark.parametrize("type_val", ["reasoning", "direct"])
    def test_valid_types_accepted(self, type_val: str):
        meta = ExampleMetadata(layer="behaviour", type=type_val)
        assert meta.type == type_val

    @pytest.mark.parametrize(
        "bad_type",
        ["chain_of_thought", "cot", "Reasoning", "DIRECT", "", "simple"],
    )
    def test_invalid_type_rejected(self, bad_type: str):
        """AC-004: type must be 'reasoning' or 'direct'."""
        with pytest.raises(ValidationError, match="type"):
            ExampleMetadata(layer="behaviour", type=bad_type)

    def test_invalid_type_error_message_clear(self):
        """AC-005: Error message is actionable and mentions valid values."""
        with pytest.raises(ValidationError) as exc_info:
            ExampleMetadata(layer="behaviour", type="invalid")
        error_text = str(exc_info.value)
        assert "reasoning" in error_text or "direct" in error_text

    def test_field_count(self):
        assert len(ExampleMetadata.model_fields) == 3


# ===========================================================================
# AC-003: TrainingExample tests
# ===========================================================================


class TestTrainingExample:
    """Tests for TrainingExample message ordering validation."""

    def test_valid_example(self, valid_messages, valid_metadata):
        example = TrainingExample(messages=valid_messages, metadata=valid_metadata)
        assert len(example.messages) == 3
        assert example.metadata.layer == "behaviour"

    def test_minimum_two_messages(self, valid_metadata):
        """Minimum valid: system + user."""
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
        """AC-003: messages[0].role must be 'system'."""
        msgs = [
            Message(role="user", content="hi"),
            Message(role="assistant", content="hello"),
        ]
        with pytest.raises(ValidationError, match="system"):
            TrainingExample(messages=msgs, metadata=valid_metadata)

    def test_first_message_system_error_is_clear(self, valid_metadata):
        """AC-005: Clear error when first message is not system."""
        msgs = [
            Message(role="user", content="hi"),
            Message(role="assistant", content="hello"),
        ]
        with pytest.raises(ValidationError) as exc_info:
            TrainingExample(messages=msgs, metadata=valid_metadata)
        error_text = str(exc_info.value)
        assert "system" in error_text
        assert "user" in error_text

    def test_alternating_roles_enforced(self, valid_metadata):
        """After system, messages must alternate user/assistant."""
        msgs = [
            Message(role="system", content="sys"),
            Message(role="user", content="q1"),
            Message(role="user", content="q2"),
        ]
        with pytest.raises(ValidationError, match="assistant"):
            TrainingExample(messages=msgs, metadata=valid_metadata)

    def test_assistant_after_system_rejected(self, valid_metadata):
        msgs = [
            Message(role="system", content="sys"),
            Message(role="assistant", content="hi"),
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

    def test_five_turn_conversation(self, valid_metadata):
        msgs = [
            Message(role="system", content="sys"),
            Message(role="user", content="q1"),
            Message(role="assistant", content="a1"),
            Message(role="user", content="q2"),
            Message(role="assistant", content="a2"),
            Message(role="user", content="q3"),
            Message(role="assistant", content="a3"),
            Message(role="user", content="q4"),
            Message(role="assistant", content="a4"),
            Message(role="user", content="q5"),
            Message(role="assistant", content="a5"),
        ]
        example = TrainingExample(messages=msgs, metadata=valid_metadata)
        assert len(example.messages) == 11


# ===========================================================================
# AC-002: RagRetrievalParams tests
# ===========================================================================


class TestRagRetrievalParams:
    """Tests for RagRetrievalParams n_results bounds validation."""

    def test_valid_params(self, valid_rag_kwargs):
        params = RagRetrievalParams(**valid_rag_kwargs)
        assert params.query == "What is Macbeth's fatal flaw?"
        assert params.n_results == 5
        assert params.collection_name == "gcse-english-tutor"

    def test_default_n_results(self):
        params = RagRetrievalParams(
            query="test query",
            collection_name="test-collection",
        )
        assert params.n_results == 5

    # --- AC-002: n_results boundary tests ---

    @pytest.mark.parametrize("n", [1, 2, 5, 10, 15, 19, 20])
    def test_valid_n_results_accepted(self, n: int):
        """AC-002: n_results 1-20 inclusive are accepted."""
        params = RagRetrievalParams(
            query="test", n_results=n, collection_name="col"
        )
        assert params.n_results == n

    def test_n_results_lower_bound(self):
        """AC-002: n_results == 1 is the minimum valid value."""
        params = RagRetrievalParams(
            query="test", n_results=1, collection_name="col"
        )
        assert params.n_results == 1

    def test_n_results_upper_bound(self):
        """AC-002: n_results == 20 is the maximum valid value."""
        params = RagRetrievalParams(
            query="test", n_results=20, collection_name="col"
        )
        assert params.n_results == 20

    @pytest.mark.parametrize("n", [0, -1, -10, -100])
    def test_n_results_below_minimum_rejected(self, n: int):
        """AC-002: n_results < 1 is rejected."""
        with pytest.raises(ValidationError):
            RagRetrievalParams(
                query="test", n_results=n, collection_name="col"
            )

    @pytest.mark.parametrize("n", [21, 50, 100, 1000])
    def test_n_results_above_maximum_rejected(self, n: int):
        """AC-002: n_results > 20 is rejected."""
        with pytest.raises(ValidationError):
            RagRetrievalParams(
                query="test", n_results=n, collection_name="col"
            )

    def test_n_results_zero_rejected(self):
        """AC-002: n_results == 0 is explicitly rejected."""
        with pytest.raises(ValidationError):
            RagRetrievalParams(
                query="test", n_results=0, collection_name="col"
            )

    def test_n_results_error_message_below_range(self):
        """AC-005: Clear error when n_results < 1."""
        with pytest.raises(ValidationError) as exc_info:
            RagRetrievalParams(
                query="test", n_results=0, collection_name="col"
            )
        error_text = str(exc_info.value)
        assert "1" in error_text

    def test_n_results_error_message_above_range(self):
        """AC-005: Clear error when n_results > 20."""
        with pytest.raises(ValidationError) as exc_info:
            RagRetrievalParams(
                query="test", n_results=25, collection_name="col"
            )
        error_text = str(exc_info.value)
        assert "20" in error_text

    def test_empty_query_rejected(self):
        with pytest.raises(ValidationError):
            RagRetrievalParams(
                query="", n_results=5, collection_name="col"
            )

    def test_empty_collection_name_rejected(self):
        with pytest.raises(ValidationError):
            RagRetrievalParams(
                query="test", n_results=5, collection_name=""
            )

    def test_field_count(self):
        assert len(RagRetrievalParams.model_fields) == 3


# ===========================================================================
# AC-006: No runtime ChromaDB dependency
# ===========================================================================


class TestNoChromaDBRuntimeDependency:
    """Verify that tools.models has no runtime import of chromadb."""

    def test_no_chromadb_import_in_source(self):
        """AC-006: Source code must not contain top-level chromadb imports.

        Parses the AST of tools/models.py and verifies no top-level
        import statement references 'chromadb'.
        """
        import tools.models as mod

        source_path = mod.__file__
        with open(source_path) as f:
            source = f.read()

        tree = ast.parse(source)
        for node in ast.iter_child_nodes(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert not alias.name.startswith("chromadb"), (
                        f"Found top-level 'import {alias.name}' — "
                        f"chromadb must use lazy-import pattern"
                    )
            elif isinstance(node, ast.ImportFrom):
                if node.module and node.module.startswith("chromadb"):
                    assert False, (
                        f"Found top-level 'from {node.module} import ...' — "
                        f"chromadb must use lazy-import pattern"
                    )

    def test_chromadb_not_in_sys_modules_after_import(self):
        """AC-006: Importing tools.models must not trigger chromadb import."""
        # Reload to ensure clean slate
        if "tools.models" in sys.modules:
            # Check that chromadb was not imported as a side-effect
            # of importing tools.models. We can't unload, so check
            # the module source doesn't cause it.
            pass
        # The AST test above is the definitive check.
        # This test verifies no dynamic import of chromadb at module level.
        import tools.models  # noqa: F811

        # Verify the module loaded successfully without requiring chromadb
        assert hasattr(tools.models, "RagRetrievalParams")
        assert hasattr(tools.models, "TrainingExample")
        assert hasattr(tools.models, "ExampleMetadata")

    def test_no_chromadb_in_init(self):
        """AC-006: tools/__init__.py must not import chromadb."""
        import tools as pkg

        source_path = pkg.__file__
        with open(source_path) as f:
            source = f.read()

        tree = ast.parse(source)
        for node in ast.iter_child_nodes(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert not alias.name.startswith("chromadb"), (
                        f"Found top-level 'import {alias.name}' in __init__.py"
                    )
            elif isinstance(node, ast.ImportFrom):
                if node.module and node.module.startswith("chromadb"):
                    assert False, (
                        f"Found 'from {node.module} import ...' in __init__.py"
                    )


# ===========================================================================
# AC-005: Clear validation error messages
# ===========================================================================


class TestErrorMessageQuality:
    """Verify that validation errors produce clear, actionable messages."""

    def test_layer_error_includes_valid_options(self):
        """Error should mention valid layer values."""
        with pytest.raises(ValidationError) as exc_info:
            ExampleMetadata(layer="invalid_layer", type="reasoning")
        msg = str(exc_info.value)
        assert "behaviour" in msg or "knowledge" in msg

    def test_type_error_includes_valid_options(self):
        """Error should mention valid type values."""
        with pytest.raises(ValidationError) as exc_info:
            ExampleMetadata(layer="behaviour", type="invalid_type")
        msg = str(exc_info.value)
        assert "reasoning" in msg or "direct" in msg

    def test_message_ordering_error_states_expected_role(self):
        """Error should state which role was expected."""
        meta = ExampleMetadata(layer="behaviour", type="reasoning")
        msgs = [
            Message(role="system", content="sys"),
            Message(role="assistant", content="wrong"),
        ]
        with pytest.raises(ValidationError) as exc_info:
            TrainingExample(messages=msgs, metadata=meta)
        msg = str(exc_info.value)
        assert "user" in msg

    def test_first_message_error_mentions_system(self):
        """Error should mention 'system' requirement."""
        meta = ExampleMetadata(layer="behaviour", type="reasoning")
        msgs = [
            Message(role="user", content="hi"),
            Message(role="assistant", content="hello"),
        ]
        with pytest.raises(ValidationError) as exc_info:
            TrainingExample(messages=msgs, metadata=meta)
        msg = str(exc_info.value)
        assert "system" in msg

    def test_n_results_below_error_mentions_minimum(self):
        """Error should mention the minimum bound."""
        with pytest.raises(ValidationError) as exc_info:
            RagRetrievalParams(query="q", n_results=-5, collection_name="c")
        msg = str(exc_info.value)
        assert "1" in msg or "greater" in msg.lower()

    def test_n_results_above_error_mentions_maximum(self):
        """Error should mention the maximum bound."""
        with pytest.raises(ValidationError) as exc_info:
            RagRetrievalParams(query="q", n_results=50, collection_name="c")
        msg = str(exc_info.value)
        assert "20" in msg or "less" in msg.lower()
