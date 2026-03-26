"""Tests for the tool factory module (create_player_tools, create_coach_tools, create_write_tool).

Covers acceptance criteria:
- AC-001: create_player_tools returns exactly 1 tool [rag_retrieval] (TASK-TRF-005)
- AC-002: create_coach_tools returns [] — always empty list
- AC-003: Coach cannot access rag_retrieval or write_output through any code path
- AC-004: Tools are properly bound to their configuration
- AC-005: Factory validates inputs (non-empty collection name, valid output dir path)
- AC-006: All modified files pass project-configured lint/format checks
- AC-007: create_write_tool returns a write_output tool for orchestrator use (TASK-TRF-005)
"""

from __future__ import annotations

import inspect
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from domain_config.models import MetadataField
from tools.tool_factory import (
    _validate_collection_name,
    _validate_metadata_schema,
    _validate_output_dir,
    create_coach_tools,
    create_player_tools,
    create_write_tool,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def valid_collection_name() -> str:
    return "gcse-english-tutor"


@pytest.fixture
def valid_output_dir(tmp_path: Path) -> Path:
    return tmp_path / "output"


@pytest.fixture
def valid_metadata_schema() -> list[MetadataField]:
    return [
        MetadataField(
            field="layer",
            type="str",
            required=True,
            valid_values=["behaviour", "knowledge"],
        ),
        MetadataField(
            field="type",
            type="str",
            required=True,
            valid_values=["reasoning", "direct"],
        ),
        MetadataField(
            field="source",
            type="str",
            required=False,
            valid_values=[],
        ),
    ]


@pytest.fixture
def empty_metadata_schema() -> list[MetadataField]:
    return []


# ---------------------------------------------------------------------------
# AC-001: create_player_tools() returns [rag_retrieval] — exactly 1 tool
# ---------------------------------------------------------------------------


class TestAC001PlayerToolsReturnsExactlyOneTool:
    """AC-001: create_player_tools() returns [rag_retrieval] — exactly 1 tool (TASK-TRF-005)."""

    @patch("tools.tool_factory.create_rag_retrieval_tool")
    def test_returns_list_of_length_one(
        self,
        mock_rag_factory: MagicMock,
        valid_collection_name: str,
    ) -> None:
        mock_rag_factory.return_value = MagicMock(name="rag_retrieval")

        tools = create_player_tools(
            collection_name=valid_collection_name,
        )

        assert isinstance(tools, list)
        assert len(tools) == 1

    @patch("tools.tool_factory.create_rag_retrieval_tool")
    def test_first_tool_is_rag_retrieval(
        self,
        mock_rag_factory: MagicMock,
        valid_collection_name: str,
    ) -> None:
        rag_sentinel = MagicMock(name="rag_retrieval")
        mock_rag_factory.return_value = rag_sentinel

        tools = create_player_tools(
            collection_name=valid_collection_name,
        )

        assert tools[0] is rag_sentinel

    @patch("tools.tool_factory.create_rag_retrieval_tool")
    def test_write_output_not_in_player_tools(
        self,
        mock_rag_factory: MagicMock,
        valid_collection_name: str,
    ) -> None:
        """TASK-TRF-005: write_output must NOT be in Player's tool list."""
        mock_rag_factory.return_value = MagicMock(name="rag_retrieval")

        tools = create_player_tools(
            collection_name=valid_collection_name,
        )

        tool_names = [getattr(t, "name", None) for t in tools]
        assert "write_output" not in tool_names

    @patch("tools.tool_factory.create_rag_retrieval_tool")
    def test_rag_factory_called_with_collection_name_and_persist_directory(
        self,
        mock_rag_factory: MagicMock,
        valid_collection_name: str,
    ) -> None:
        mock_rag_factory.return_value = MagicMock()

        create_player_tools(
            collection_name=valid_collection_name,
        )

        mock_rag_factory.assert_called_once_with(valid_collection_name, "./chroma_data")

    @patch("tools.tool_factory.create_rag_retrieval_tool")
    def test_rag_factory_called_with_custom_persist_directory(
        self,
        mock_rag_factory: MagicMock,
        valid_collection_name: str,
    ) -> None:
        mock_rag_factory.return_value = MagicMock()

        create_player_tools(
            collection_name=valid_collection_name,
            persist_directory="/custom/db",
        )

        mock_rag_factory.assert_called_once_with(valid_collection_name, "/custom/db")

    def test_player_tools_no_output_dir_param(self) -> None:
        """TASK-TRF-005: create_player_tools no longer accepts output_dir."""
        sig = inspect.signature(create_player_tools)
        assert "output_dir" not in sig.parameters

    def test_player_tools_no_metadata_schema_param(self) -> None:
        """TASK-TRF-005: create_player_tools no longer accepts metadata_schema."""
        sig = inspect.signature(create_player_tools)
        assert "metadata_schema" not in sig.parameters


# ---------------------------------------------------------------------------
# AC-002: create_coach_tools() returns [] — always empty list
# ---------------------------------------------------------------------------


@pytest.mark.smoke
class TestAC002CoachToolsReturnsEmptyList:
    """AC-002: create_coach_tools() returns [] — always empty list."""

    def test_returns_empty_list(self) -> None:
        tools = create_coach_tools()
        assert tools == []

    def test_returns_list_type(self) -> None:
        tools = create_coach_tools()
        assert isinstance(tools, list)

    def test_returns_list_of_length_zero(self) -> None:
        tools = create_coach_tools()
        assert len(tools) == 0

    def test_accepts_no_arguments(self) -> None:
        """Coach factory takes zero parameters — no tools can be injected."""
        sig = inspect.signature(create_coach_tools)
        params = [
            p
            for p in sig.parameters.values()
            if p.default is inspect.Parameter.empty
            and p.kind
            not in (
                inspect.Parameter.VAR_POSITIONAL,
                inspect.Parameter.VAR_KEYWORD,
            )
        ]
        assert len(params) == 0

    def test_returns_new_list_each_call(self) -> None:
        """Each invocation returns a fresh list (not a shared mutable reference)."""
        tools_a = create_coach_tools()
        tools_b = create_coach_tools()
        assert tools_a is not tools_b

    def test_multiple_calls_all_return_empty(self) -> None:
        """Verify idempotent behaviour across 100 calls."""
        for _ in range(100):
            assert create_coach_tools() == []


# ---------------------------------------------------------------------------
# AC-003: Coach cannot access rag_retrieval or write_output
# ---------------------------------------------------------------------------


@pytest.mark.smoke
class TestAC003CoachCannotAccessTools:
    """AC-003: Coach cannot access rag_retrieval or write_output through any code path."""

    def test_coach_tools_has_no_rag_retrieval(self) -> None:
        tools = create_coach_tools()
        tool_names = [getattr(t, "name", None) for t in tools]
        assert "rag_retrieval" not in tool_names

    def test_coach_tools_has_no_write_output(self) -> None:
        tools = create_coach_tools()
        tool_names = [getattr(t, "name", None) for t in tools]
        assert "write_output" not in tool_names

    def test_coach_factory_signature_has_no_tools_param(self) -> None:
        """Coach factory signature does not accept a 'tools' parameter."""
        sig = inspect.signature(create_coach_tools)
        assert "tools" not in sig.parameters

    def test_coach_factory_signature_has_no_collection_param(self) -> None:
        """Coach factory has no collection_name parameter — cannot create rag_retrieval."""
        sig = inspect.signature(create_coach_tools)
        assert "collection_name" not in sig.parameters

    def test_coach_factory_signature_has_no_output_dir_param(self) -> None:
        """Coach factory has no output_dir parameter — cannot create write_output."""
        sig = inspect.signature(create_coach_tools)
        assert "output_dir" not in sig.parameters

    def test_coach_factory_signature_has_no_metadata_schema_param(self) -> None:
        """Coach factory has no metadata_schema parameter."""
        sig = inspect.signature(create_coach_tools)
        assert "metadata_schema" not in sig.parameters

    def test_coach_tools_cannot_be_mutated_to_add_tools(self) -> None:
        """Even if a caller mutates the returned list, the next call is clean."""
        tools = create_coach_tools()
        tools.append(MagicMock(name="rag_retrieval"))

        # Next call should return a fresh empty list
        assert create_coach_tools() == []

    def test_coach_module_does_not_import_rag_or_write(self) -> None:
        """The create_coach_tools function source does not reference tool factories."""
        source = inspect.getsource(create_coach_tools)
        assert "create_rag_retrieval_tool" not in source
        assert "create_write_output_tool" not in source


# ---------------------------------------------------------------------------
# AC-004: Tools are properly bound to their configuration
# ---------------------------------------------------------------------------


class TestAC004ToolsBoundToConfiguration:
    """AC-004: Tools are properly bound to their configuration."""

    @patch("tools.tool_factory.create_rag_retrieval_tool")
    def test_rag_tool_bound_to_collection_name(
        self,
        mock_rag_factory: MagicMock,
    ) -> None:
        mock_rag_factory.return_value = MagicMock()

        create_player_tools(
            collection_name="my-special-collection",
        )

        mock_rag_factory.assert_called_once_with("my-special-collection", "./chroma_data")

    @patch("tools.tool_factory.create_rag_retrieval_tool")
    def test_different_configs_produce_different_tools(
        self,
        mock_rag_factory: MagicMock,
    ) -> None:
        """Two calls with different collection names produce different rag tools."""
        rag_a = MagicMock(name="rag_a")
        rag_b = MagicMock(name="rag_b")
        mock_rag_factory.side_effect = [rag_a, rag_b]

        tools_a = create_player_tools(collection_name="collection-a")
        tools_b = create_player_tools(collection_name="collection-b")

        assert tools_a[0] is rag_a
        assert tools_b[0] is rag_b
        assert tools_a[0] is not tools_b[0]


# ---------------------------------------------------------------------------
# AC-005: Factory validates inputs
# ---------------------------------------------------------------------------


class TestAC005FactoryValidatesInputs:
    """AC-005: Factory validates inputs (non-empty collection name, valid output dir path)."""

    # -- Collection name validation --

    def test_empty_collection_name_raises_value_error(self) -> None:
        with pytest.raises(ValueError, match="non-empty"):
            create_player_tools(collection_name="")

    def test_whitespace_collection_name_raises_value_error(self) -> None:
        with pytest.raises(ValueError, match="non-empty"):
            create_player_tools(collection_name="   ")

    def test_none_collection_name_raises_value_error(self) -> None:
        with pytest.raises(ValueError, match="non-empty"):
            create_player_tools(collection_name=None)  # type: ignore[arg-type]

    # -- Validation happens before tool creation --

    @patch("tools.tool_factory.create_rag_retrieval_tool")
    def test_validation_failure_prevents_tool_creation(
        self,
        mock_rag_factory: MagicMock,
    ) -> None:
        """If collection_name is invalid, no tool factories are called."""
        with pytest.raises(ValueError):
            create_player_tools(collection_name="")

        mock_rag_factory.assert_not_called()


# ---------------------------------------------------------------------------
# AC-007: create_write_tool returns write_output for orchestrator (TASK-TRF-005)
# ---------------------------------------------------------------------------


class TestAC007CreateWriteTool:
    """AC-007: create_write_tool returns a write_output tool for orchestrator use."""

    @patch("tools.tool_factory.create_write_output_tool")
    def test_returns_write_output_tool(
        self,
        mock_write_factory: MagicMock,
        valid_output_dir: Path,
        valid_metadata_schema: list[MetadataField],
    ) -> None:
        write_sentinel = MagicMock(name="write_output")
        mock_write_factory.return_value = write_sentinel

        tool = create_write_tool(
            output_dir=valid_output_dir,
            metadata_schema=valid_metadata_schema,
        )

        assert tool is write_sentinel

    @patch("tools.tool_factory.create_write_output_tool")
    def test_write_factory_called_with_output_dir_and_schema(
        self,
        mock_write_factory: MagicMock,
        valid_output_dir: Path,
        valid_metadata_schema: list[MetadataField],
    ) -> None:
        mock_write_factory.return_value = MagicMock()

        create_write_tool(
            output_dir=valid_output_dir,
            metadata_schema=valid_metadata_schema,
        )

        mock_write_factory.assert_called_once_with(valid_output_dir, valid_metadata_schema)

    def test_non_path_output_dir_raises_value_error(
        self,
        valid_metadata_schema: list[MetadataField],
    ) -> None:
        with pytest.raises(ValueError, match="Path instance"):
            create_write_tool(
                output_dir="/some/string/path",  # type: ignore[arg-type]
                metadata_schema=valid_metadata_schema,
            )

    def test_empty_path_output_dir_raises_value_error(
        self,
        valid_metadata_schema: list[MetadataField],
    ) -> None:
        with pytest.raises(ValueError, match="must not be empty"):
            create_write_tool(
                output_dir=Path(""),
                metadata_schema=valid_metadata_schema,
            )

    def test_null_byte_output_dir_raises_value_error(
        self,
        valid_metadata_schema: list[MetadataField],
    ) -> None:
        with pytest.raises(ValueError, match="null bytes"):
            create_write_tool(
                output_dir=Path("/tmp/output\x00malicious"),
                metadata_schema=valid_metadata_schema,
            )

    def test_non_list_metadata_schema_raises_value_error(
        self,
        valid_output_dir: Path,
    ) -> None:
        with pytest.raises(ValueError, match="must be a list"):
            create_write_tool(
                output_dir=valid_output_dir,
                metadata_schema=None,  # type: ignore[arg-type]
            )

    @patch("tools.tool_factory.create_write_output_tool")
    def test_empty_metadata_schema_accepted(
        self,
        mock_write_factory: MagicMock,
        valid_output_dir: Path,
        empty_metadata_schema: list[MetadataField],
    ) -> None:
        """An empty list is a valid metadata_schema."""
        mock_write_factory.return_value = MagicMock()

        tool = create_write_tool(
            output_dir=valid_output_dir,
            metadata_schema=empty_metadata_schema,
        )

        assert tool is not None


# ---------------------------------------------------------------------------
# Validation helper unit tests
# ---------------------------------------------------------------------------


class TestValidateCollectionName:
    """Unit tests for _validate_collection_name helper."""

    def test_valid_name_passes(self) -> None:
        _validate_collection_name("gcse-english-tutor")  # should not raise

    def test_empty_string_raises(self) -> None:
        with pytest.raises(ValueError, match="non-empty"):
            _validate_collection_name("")

    def test_whitespace_only_raises(self) -> None:
        with pytest.raises(ValueError, match="non-empty"):
            _validate_collection_name("   ")

    def test_none_raises(self) -> None:
        with pytest.raises(ValueError, match="non-empty"):
            _validate_collection_name(None)  # type: ignore[arg-type]


class TestValidateOutputDir:
    """Unit tests for _validate_output_dir helper."""

    def test_valid_path_passes(self, tmp_path: Path) -> None:
        _validate_output_dir(tmp_path / "output")  # should not raise

    def test_non_path_raises(self) -> None:
        with pytest.raises(ValueError, match="Path instance"):
            _validate_output_dir("/some/string")  # type: ignore[arg-type]

    def test_empty_path_raises(self) -> None:
        with pytest.raises(ValueError, match="must not be empty"):
            _validate_output_dir(Path(""))

    def test_null_byte_raises(self) -> None:
        with pytest.raises(ValueError, match="null bytes"):
            _validate_output_dir(Path("/tmp/\x00bad"))


class TestValidateMetadataSchema:
    """Unit tests for _validate_metadata_schema helper."""

    def test_valid_list_passes(self) -> None:
        _validate_metadata_schema([])  # should not raise

    def test_none_raises(self) -> None:
        with pytest.raises(ValueError, match="must be a list"):
            _validate_metadata_schema(None)  # type: ignore[arg-type]

    def test_dict_raises(self) -> None:
        with pytest.raises(ValueError, match="must be a list"):
            _validate_metadata_schema({})  # type: ignore[arg-type]

    def test_string_raises(self) -> None:
        with pytest.raises(ValueError, match="must be a list"):
            _validate_metadata_schema("not a list")  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# AC-006: Lint/format compliance (tested externally via ruff)
# ---------------------------------------------------------------------------


class TestAC006ModuleStructure:
    """AC-006: Verify module has proper structure for lint compliance."""

    def test_module_has_docstring(self) -> None:
        import tools.tool_factory as mod

        assert mod.__doc__ is not None
        assert len(mod.__doc__) > 20

    def test_module_has_all_attribute(self) -> None:
        import tools.tool_factory as mod

        assert hasattr(mod, "__all__")
        assert "create_player_tools" in mod.__all__
        assert "create_coach_tools" in mod.__all__
        assert "create_write_tool" in mod.__all__

    def test_public_functions_have_docstrings(self) -> None:
        assert create_player_tools.__doc__ is not None
        assert create_coach_tools.__doc__ is not None
        assert create_write_tool.__doc__ is not None

    def test_public_functions_have_type_annotations(self) -> None:
        hints = inspect.get_annotations(create_player_tools)
        assert "return" in hints

        hints = inspect.get_annotations(create_coach_tools)
        assert "return" in hints

        hints = inspect.get_annotations(create_write_tool)
        assert "return" in hints
