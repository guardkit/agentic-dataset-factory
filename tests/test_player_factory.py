"""Unit tests for Player factory — TASK-AF-008.

Tests the ``create_player`` factory function using the exemplar testing
methodology: patch ``create_deep_agent`` at the import site, inspect
``call_args`` kwargs to verify correct wiring.

Acceptance Criteria:
    AC-001: Tests mock ``create_deep_agent`` at the import site
    AC-002: Tests verify ``call_args`` keyword arguments for tools, backend,
            system_prompt, memory
    AC-003: Tests verify ``FilesystemBackend`` is in the ``backend`` kwarg
    AC-004: Tests verify tools list contains exactly 2 tools
    AC-005: Module-level import assertion for ``FilesystemBackend``
    AC-006: Tests are in ``tests/test_player_factory.py``
"""

from __future__ import annotations

import sys
from unittest.mock import MagicMock, patch

import pytest

from config.models import ModelConfig


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_model_config(**overrides: object) -> ModelConfig:
    """Create a valid ModelConfig with sensible defaults for testing."""
    defaults: dict = {
        "provider": "local",
        "model": "test-model",
        "endpoint": "http://localhost:8000/v1",
        "temperature": 0.7,
    }
    defaults.update(overrides)
    return ModelConfig(**defaults)


def _call_create_player(
    mock_cda: MagicMock,
    *,
    model_config: ModelConfig | None = None,
    tools: list | None = None,
    system_prompt: str = "You are a Player agent.",
    memory: list[str] | None = None,
) -> object:
    """Invoke create_player with sensible defaults and return its result."""
    from agents.player import create_player

    if model_config is None:
        model_config = _make_model_config()
    if tools is None:
        tools = [MagicMock(name="rag_retrieval"), MagicMock(name="write_output")]
    if memory is None:
        memory = ["./AGENTS.md"]
    return create_player(
        model_config=model_config,
        tools=tools,
        system_prompt=system_prompt,
        memory=memory,
    )


# ---------------------------------------------------------------------------
# AC-001: Tests mock create_deep_agent at the import site
# ---------------------------------------------------------------------------


class TestPatchAtImportSite:
    """AC-001: Tests mock create_deep_agent at agents.player.create_deep_agent."""

    def test_create_deep_agent_patched_at_import_site(self) -> None:
        """Patching at import site intercepts the factory's delegation call."""
        with (
            patch("agents.player.create_deep_agent") as mock_cda,
            patch("agents.player.FilesystemBackend"),
        ):
            _call_create_player(mock_cda)
        mock_cda.assert_called_once()

    def test_returns_result_of_create_deep_agent(self) -> None:
        """create_player returns whatever create_deep_agent returns."""
        fake_agent = MagicMock(name="fake_player_agent")
        with (
            patch("agents.player.create_deep_agent", return_value=fake_agent) as mock_cda,
            patch("agents.player.FilesystemBackend"),
        ):
            result = _call_create_player(mock_cda)
        assert result is fake_agent


# ---------------------------------------------------------------------------
# AC-002: Tests verify call_args keyword arguments
# ---------------------------------------------------------------------------


class TestCallArgsKeywordArguments:
    """AC-002: Verify call_args kwargs for tools, backend, system_prompt, memory."""

    def test_system_prompt_forwarded(self) -> None:
        """create_player passes system_prompt through to create_deep_agent."""
        prompt = "You are a Player agent for GCSE English tutor dataset generation."
        with (
            patch("agents.player.create_deep_agent") as mock_cda,
            patch("agents.player.FilesystemBackend"),
        ):
            _call_create_player(mock_cda, system_prompt=prompt)
        _, kwargs = mock_cda.call_args
        assert kwargs["system_prompt"] == prompt

    def test_memory_forwarded(self) -> None:
        """create_player passes memory list through to create_deep_agent."""
        memory = ["./AGENTS.md"]
        with (
            patch("agents.player.create_deep_agent") as mock_cda,
            patch("agents.player.FilesystemBackend"),
        ):
            _call_create_player(mock_cda, memory=memory)
        _, kwargs = mock_cda.call_args
        assert kwargs["memory"] == memory

    def test_tools_forwarded(self) -> None:
        """create_player passes tools list through to create_deep_agent."""
        tool_a = MagicMock(name="rag_retrieval")
        tool_b = MagicMock(name="write_output")
        with (
            patch("agents.player.create_deep_agent") as mock_cda,
            patch("agents.player.FilesystemBackend"),
        ):
            _call_create_player(mock_cda, tools=[tool_a, tool_b])
        _, kwargs = mock_cda.call_args
        assert tool_a in kwargs["tools"]
        assert tool_b in kwargs["tools"]

    def test_backend_forwarded(self) -> None:
        """create_player passes FilesystemBackend instance as backend kwarg."""
        with (
            patch("agents.player.create_deep_agent") as mock_cda,
            patch("agents.player.FilesystemBackend") as mock_backend_cls,
        ):
            fake_backend = MagicMock(name="fs_backend")
            mock_backend_cls.return_value = fake_backend
            _call_create_player(mock_cda)
        _, kwargs = mock_cda.call_args
        assert "backend" in kwargs
        assert kwargs["backend"] is fake_backend

    def test_model_config_translated_and_forwarded(self) -> None:
        """create_player translates ModelConfig and passes model to create_deep_agent."""
        from langchain_core.language_models import BaseChatModel

        config = _make_model_config(provider="local", model="test-model")
        with (
            patch("agents.player.create_deep_agent") as mock_cda,
            patch("agents.player.FilesystemBackend"),
        ):
            _call_create_player(mock_cda, model_config=config)
        _, kwargs = mock_cda.call_args
        assert "model" in kwargs
        assert isinstance(kwargs["model"], BaseChatModel)


# ---------------------------------------------------------------------------
# AC-003: Tests verify FilesystemBackend is in the backend kwarg
# ---------------------------------------------------------------------------


class TestFilesystemBackendWiring:
    """AC-003: FilesystemBackend is instantiated and passed as backend kwarg."""

    def test_filesystem_backend_constructor_called_with_root_dot(self) -> None:
        """FilesystemBackend is constructed with root_dir='.'."""
        with (
            patch("agents.player.create_deep_agent") as mock_cda,
            patch("agents.player.FilesystemBackend") as mock_backend_cls,
        ):
            _call_create_player(mock_cda)
        mock_backend_cls.assert_called_once_with(root_dir=".")

    def test_filesystem_backend_instance_forwarded_to_create_deep_agent(self) -> None:
        """The FilesystemBackend instance is the backend kwarg to create_deep_agent."""
        with (
            patch("agents.player.create_deep_agent") as mock_cda,
            patch("agents.player.FilesystemBackend") as mock_backend_cls,
        ):
            fake_backend = MagicMock(name="fs_backend")
            mock_backend_cls.return_value = fake_backend
            _call_create_player(mock_cda)
        _, kwargs = mock_cda.call_args
        assert kwargs["backend"] is fake_backend


# ---------------------------------------------------------------------------
# AC-004: Tests verify tools list contains exactly 2 tools
# ---------------------------------------------------------------------------


class TestToolsListSize:
    """AC-004: tools list passed through contains exactly 2 tools."""

    def test_tools_list_has_exactly_two_elements(self) -> None:
        """create_player forwards a tools list with exactly 2 tools."""
        tool_a = MagicMock(name="rag_retrieval")
        tool_b = MagicMock(name="write_output")
        with (
            patch("agents.player.create_deep_agent") as mock_cda,
            patch("agents.player.FilesystemBackend"),
        ):
            _call_create_player(mock_cda, tools=[tool_a, tool_b])
        _, kwargs = mock_cda.call_args
        assert len(kwargs["tools"]) == 2

    def test_each_tool_present_in_forwarded_list(self) -> None:
        """Both tools are present in the forwarded tools list."""
        tool_a = MagicMock(name="rag_retrieval")
        tool_b = MagicMock(name="write_output")
        with (
            patch("agents.player.create_deep_agent") as mock_cda,
            patch("agents.player.FilesystemBackend"),
        ):
            _call_create_player(mock_cda, tools=[tool_a, tool_b])
        _, kwargs = mock_cda.call_args
        assert tool_a in kwargs["tools"]
        assert tool_b in kwargs["tools"]


# ---------------------------------------------------------------------------
# AC-005: Module-level import assertion for FilesystemBackend
# ---------------------------------------------------------------------------


class TestModuleLevelImports:
    """AC-005: Module-level import assertions for agents.player."""

    def test_player_module_imports_filesystem_backend(self) -> None:
        """agents.player imports FilesystemBackend (contrast with Coach)."""
        # Clear cached module to force fresh import inspection
        sys.modules.pop("agents.player", None)
        import agents.player as player_module

        assert hasattr(player_module, "FilesystemBackend"), (
            "agents.player must import FilesystemBackend — "
            "the Player agent requires filesystem access"
        )

    def test_player_module_imports_create_deep_agent(self) -> None:
        """agents.player imports create_deep_agent."""
        sys.modules.pop("agents.player", None)
        import agents.player as player_module

        assert hasattr(player_module, "create_deep_agent"), (
            "agents.player must import create_deep_agent — "
            "the factory delegates to this function"
        )


# ---------------------------------------------------------------------------
# Negative Cases: Validation
# ---------------------------------------------------------------------------


class TestValidationErrors:
    """Negative: Empty system prompt raises validation error."""

    def test_empty_system_prompt_raises_value_error(self) -> None:
        """create_player raises ValueError when system_prompt is empty string."""
        with (
            patch("agents.player.create_deep_agent"),
            patch("agents.player.FilesystemBackend"),
        ):
            from agents.player import create_player

            with pytest.raises(ValueError, match="system_prompt"):
                create_player(
                    model_config=_make_model_config(),
                    tools=[MagicMock(), MagicMock()],
                    system_prompt="",
                    memory=["./AGENTS.md"],
                )

    def test_whitespace_only_system_prompt_raises_value_error(self) -> None:
        """create_player raises ValueError when system_prompt is whitespace-only."""
        with (
            patch("agents.player.create_deep_agent"),
            patch("agents.player.FilesystemBackend"),
        ):
            from agents.player import create_player

            with pytest.raises(ValueError, match="system_prompt"):
                create_player(
                    model_config=_make_model_config(),
                    tools=[MagicMock(), MagicMock()],
                    system_prompt="   \t\n  ",
                    memory=["./AGENTS.md"],
                )
