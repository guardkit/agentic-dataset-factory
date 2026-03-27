"""Unit tests for Player factory — TASK-TRF-016.

Tests the ``create_player`` factory function using the exemplar testing
methodology: patch ``create_agent`` at the import site, inspect
``call_args`` kwargs to verify correct wiring.

Mirrors the Coach factory test pattern (TASK-TRF-012) with the key
difference that the Player receives tools (e.g. [rag_retrieval]).

Acceptance Criteria:
    AC-001: Tests mock ``create_agent`` at the import site
    AC-002: Tests verify ``call_args`` keyword arguments for tools,
            system_prompt, middleware
    AC-003: Tests verify middleware stack includes MemoryMiddleware
            but excludes FilesystemMiddleware
    AC-004: Tests verify tools list is forwarded as-is
    AC-005: Module-level import assertion for ``create_agent``
            (not ``create_deep_agent``)
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
    mock_ca: MagicMock,
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
        tools = [MagicMock(name="rag_retrieval")]
    if memory is None:
        memory = ["./AGENTS.md"]
    with patch("agents.player.create_model", return_value=MagicMock()):
        return create_player(
            model_config=model_config,
            tools=tools,
            system_prompt=system_prompt,
            memory=memory,
        )


# ---------------------------------------------------------------------------
# AC-001: Tests mock create_agent at the import site
# ---------------------------------------------------------------------------


class TestPatchAtImportSite:
    """AC-001: Tests mock create_agent at agents.player.create_agent."""

    def test_create_agent_patched_at_import_site(self) -> None:
        """Patching at import site intercepts the factory's delegation call."""
        with (
            patch("agents.player.create_agent") as mock_ca,
            patch("agents.player.FilesystemBackend"),
        ):
            _call_create_player(mock_ca)
        mock_ca.assert_called_once()

    def test_returns_result_of_create_agent(self) -> None:
        """create_player returns whatever create_agent returns."""
        fake_agent = MagicMock(name="fake_player_agent")
        with (
            patch("agents.player.create_agent", return_value=fake_agent) as mock_ca,
            patch("agents.player.FilesystemBackend"),
        ):
            result = _call_create_player(mock_ca)
        assert result is fake_agent


# ---------------------------------------------------------------------------
# AC-002: Tests verify call_args keyword arguments
# ---------------------------------------------------------------------------


class TestCallArgsKeywordArguments:
    """AC-002: Verify call_args kwargs for tools, system_prompt, middleware."""

    def test_system_prompt_forwarded(self) -> None:
        """create_player passes system_prompt through to create_agent."""
        prompt = "You are a Player agent for GCSE English tutor dataset generation."
        with (
            patch("agents.player.create_agent") as mock_ca,
            patch("agents.player.FilesystemBackend"),
        ):
            _call_create_player(mock_ca, system_prompt=prompt)
        _, kwargs = mock_ca.call_args
        assert kwargs["system_prompt"] == prompt

    def test_tools_forwarded(self) -> None:
        """create_player passes tools list through to create_agent."""
        tool_a = MagicMock(name="rag_retrieval")
        with (
            patch("agents.player.create_agent") as mock_ca,
            patch("agents.player.FilesystemBackend"),
        ):
            _call_create_player(mock_ca, tools=[tool_a])
        _, kwargs = mock_ca.call_args
        assert tool_a in kwargs["tools"]

    def test_middleware_forwarded(self) -> None:
        """create_player passes middleware list to create_agent."""
        with (
            patch("agents.player.create_agent") as mock_ca,
            patch("agents.player.FilesystemBackend"),
        ):
            _call_create_player(mock_ca)
        _, kwargs = mock_ca.call_args
        assert "middleware" in kwargs
        assert isinstance(kwargs["middleware"], list)
        assert len(kwargs["middleware"]) == 3

    def test_model_config_translated_and_forwarded(self) -> None:
        """create_player passes create_model result to create_agent as 'model'."""
        config = _make_model_config(provider="local", model="test-model")
        fake_model = MagicMock(name="fake_model")
        with (
            patch("agents.player.create_agent") as mock_ca,
            patch("agents.player.FilesystemBackend"),
            patch("agents.player.create_model", return_value=fake_model),
        ):
            from agents.player import create_player

            create_player(
                model_config=config,
                tools=[MagicMock(name="rag_retrieval")],
                system_prompt="You are a Player agent.",
                memory=["./AGENTS.md"],
            )
        _, kwargs = mock_ca.call_args
        assert "model" in kwargs
        assert kwargs["model"] is fake_model

    def test_max_tokens_passed_through_to_model(self) -> None:
        """max_tokens from ModelConfig is passed through to create_model."""
        config = _make_model_config(max_tokens=8192)
        with (
            patch("agents.player.create_agent") as mock_ca,
            patch("agents.player.FilesystemBackend"),
            patch("agents.player.create_model") as mock_cm,
        ):
            mock_cm.return_value = MagicMock()
            from agents.player import create_player

            create_player(
                model_config=config,
                tools=[MagicMock(name="rag_retrieval")],
                system_prompt="You are a Player agent.",
                memory=["./AGENTS.md"],
            )
        mock_cm.assert_called_once_with(config)
        assert config.max_tokens == 8192

    def test_max_tokens_default_is_4096(self) -> None:
        """ModelConfig defaults max_tokens to 4096."""
        config = _make_model_config()
        assert config.max_tokens == 4096


# ---------------------------------------------------------------------------
# AC-003: Tests verify middleware excludes FilesystemMiddleware
# ---------------------------------------------------------------------------


class TestMiddlewareStack:
    """AC-003: Middleware includes MemoryMiddleware, excludes FilesystemMiddleware."""

    def test_memory_middleware_in_stack(self) -> None:
        """MemoryMiddleware is present in the middleware stack."""
        from deepagents.middleware import MemoryMiddleware

        with (
            patch("agents.player.create_agent") as mock_ca,
            patch("agents.player.FilesystemBackend"),
        ):
            _call_create_player(mock_ca)
        _, kwargs = mock_ca.call_args
        middleware_types = [type(m).__name__ for m in kwargs["middleware"]]
        assert "MemoryMiddleware" in middleware_types

    def test_no_filesystem_middleware_in_stack(self) -> None:
        """FilesystemMiddleware is NOT in the middleware stack."""
        with (
            patch("agents.player.create_agent") as mock_ca,
            patch("agents.player.FilesystemBackend"),
        ):
            _call_create_player(mock_ca)
        _, kwargs = mock_ca.call_args
        middleware_types = [type(m).__name__ for m in kwargs["middleware"]]
        assert "FilesystemMiddleware" not in middleware_types

    def test_patch_tool_calls_middleware_in_stack(self) -> None:
        """PatchToolCallsMiddleware is present in the middleware stack."""
        from deepagents.middleware.patch_tool_calls import PatchToolCallsMiddleware

        with (
            patch("agents.player.create_agent") as mock_ca,
            patch("agents.player.FilesystemBackend"),
        ):
            _call_create_player(mock_ca)
        _, kwargs = mock_ca.call_args
        middleware_types = [type(m).__name__ for m in kwargs["middleware"]]
        assert "PatchToolCallsMiddleware" in middleware_types

    def test_memory_middleware_receives_memory_sources(self) -> None:
        """MemoryMiddleware is configured with the provided memory sources."""
        from deepagents.middleware import MemoryMiddleware

        memory = ["./AGENTS.md"]
        with (
            patch("agents.player.create_agent") as mock_ca,
            patch("agents.player.FilesystemBackend"),
        ):
            _call_create_player(mock_ca, memory=memory)
        _, kwargs = mock_ca.call_args
        mem_mw = [m for m in kwargs["middleware"] if isinstance(m, MemoryMiddleware)]
        assert len(mem_mw) == 1
        assert mem_mw[0].sources == memory

    def test_filesystem_backend_used_for_memory_only(self) -> None:
        """FilesystemBackend is constructed with root_dir='.' for MemoryMiddleware."""
        with (
            patch("agents.player.create_agent") as mock_ca,
            patch("agents.player.FilesystemBackend") as mock_backend_cls,
        ):
            _call_create_player(mock_ca)
        mock_backend_cls.assert_called_once_with(root_dir=".")


# ---------------------------------------------------------------------------
# AC-004: Tests verify tools list is forwarded as-is
# ---------------------------------------------------------------------------


class TestToolsListForwarding:
    """AC-004: tools list passed through contains only intended tools."""

    def test_single_tool_forwarded(self) -> None:
        """create_player forwards a single-tool list as-is."""
        tool_a = MagicMock(name="rag_retrieval")
        with (
            patch("agents.player.create_agent") as mock_ca,
            patch("agents.player.FilesystemBackend"),
        ):
            _call_create_player(mock_ca, tools=[tool_a])
        _, kwargs = mock_ca.call_args
        assert len(kwargs["tools"]) == 1
        assert kwargs["tools"][0] is tool_a

    def test_no_extra_tools_injected(self) -> None:
        """No filesystem tools are added beyond what was passed."""
        tool_a = MagicMock(name="rag_retrieval")
        with (
            patch("agents.player.create_agent") as mock_ca,
            patch("agents.player.FilesystemBackend"),
        ):
            _call_create_player(mock_ca, tools=[tool_a])
        _, kwargs = mock_ca.call_args
        tool_names = [getattr(t, "name", "") for t in kwargs["tools"]]
        filesystem_tools = {"write_todos", "ls", "read_file", "write_file",
                           "edit_file", "glob", "grep", "task"}
        assert not filesystem_tools.intersection(set(tool_names))

    def test_no_backend_kwarg_passed_to_create_agent(self) -> None:
        """create_agent is NOT called with a backend kwarg (no FilesystemMiddleware)."""
        with (
            patch("agents.player.create_agent") as mock_ca,
            patch("agents.player.FilesystemBackend"),
        ):
            _call_create_player(mock_ca)
        _, kwargs = mock_ca.call_args
        assert "backend" not in kwargs


# ---------------------------------------------------------------------------
# AC-005: Module-level import assertions
# ---------------------------------------------------------------------------


class TestModuleLevelImports:
    """AC-005: Module-level import assertions for agents.player."""

    def test_player_module_imports_create_agent(self) -> None:
        """agents.player imports create_agent (not create_deep_agent)."""
        sys.modules.pop("agents.player", None)
        import agents.player as player_module

        assert hasattr(player_module, "create_agent"), (
            "agents.player must import create_agent — "
            "the factory delegates to this function"
        )

    def test_player_module_does_not_import_create_deep_agent(self) -> None:
        """agents.player does NOT import create_deep_agent."""
        sys.modules.pop("agents.player", None)
        import agents.player as player_module

        assert not hasattr(player_module, "create_deep_agent"), (
            "agents.player must NOT import create_deep_agent — "
            "it leaks FilesystemMiddleware tools"
        )

    def test_player_module_imports_memory_middleware(self) -> None:
        """agents.player imports MemoryMiddleware for memory injection."""
        sys.modules.pop("agents.player", None)
        import agents.player as player_module

        assert hasattr(player_module, "MemoryMiddleware"), (
            "agents.player must import MemoryMiddleware — "
            "needed for AGENTS.md memory injection"
        )


# ---------------------------------------------------------------------------
# Negative Cases: Validation
# ---------------------------------------------------------------------------


class TestValidationErrors:
    """Negative: Empty system prompt raises validation error."""

    def test_empty_system_prompt_raises_value_error(self) -> None:
        """create_player raises ValueError when system_prompt is empty string."""
        with (
            patch("agents.player.create_agent"),
            patch("agents.player.FilesystemBackend"),
        ):
            from agents.player import create_player

            with pytest.raises(ValueError, match="system_prompt"):
                create_player(
                    model_config=_make_model_config(),
                    tools=[MagicMock()],
                    system_prompt="",
                    memory=["./AGENTS.md"],
                )

    def test_whitespace_only_system_prompt_raises_value_error(self) -> None:
        """create_player raises ValueError when system_prompt is whitespace-only."""
        with (
            patch("agents.player.create_agent"),
            patch("agents.player.FilesystemBackend"),
        ):
            from agents.player import create_player

            with pytest.raises(ValueError, match="system_prompt"):
                create_player(
                    model_config=_make_model_config(),
                    tools=[MagicMock()],
                    system_prompt="   \t\n  ",
                    memory=["./AGENTS.md"],
                )
