"""Tests for agents.player.create_player factory function.

Covers all acceptance criteria for TASK-AF-003 and TASK-TRF-003.
Uses patch-at-import-site pattern and call_args keyword argument assertions.

Updated for TASK-TRF-016: create_player now delegates to create_agent
(not create_deep_agent) with an explicit middleware stack.
"""

from __future__ import annotations

import ast
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from config.models import ModelConfig


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


class TestCreatePlayerSignature:
    """AC-001: agents/player.py contains create_player() with the contract signature."""

    def test_create_player_is_importable(self) -> None:
        """create_player can be imported from agents.player."""
        from agents.player import create_player

        assert callable(create_player)

    def test_create_player_accepts_contract_parameters(self) -> None:
        """create_player accepts model_config, tools, system_prompt, memory."""
        import inspect

        from agents.player import create_player

        sig = inspect.signature(create_player)
        param_names = list(sig.parameters.keys())
        assert "model_config" in param_names
        assert "tools" in param_names
        assert "system_prompt" in param_names
        assert "memory" in param_names


class TestCreatePlayerDelegation:
    """AC-002: Factory delegates to create_agent with correct kwargs."""

    def test_returns_result_of_create_agent(self) -> None:
        """create_player returns whatever create_agent returns."""
        fake_agent = MagicMock(name="fake_player_agent")
        with (
            patch("agents.player.create_agent", return_value=fake_agent),
            patch("agents.player.create_model"),
            patch("agents.player.FilesystemBackend"),
        ):
            from agents.player import create_player

            result = create_player(
                model_config=_make_model_config(),
                tools=[MagicMock(), MagicMock()],
                system_prompt="test prompt",
                memory=["./AGENTS.md"],
            )
        assert result is fake_agent

    def test_delegates_to_create_agent(self) -> None:
        """create_player calls create_agent exactly once."""
        with (
            patch("agents.player.create_agent") as mock_ca,
            patch("agents.player.create_model"),
            patch("agents.player.FilesystemBackend"),
        ):
            from agents.player import create_player

            create_player(
                model_config=_make_model_config(),
                tools=[MagicMock(), MagicMock()],
                system_prompt="test prompt",
                memory=["./AGENTS.md"],
            )
        mock_ca.assert_called_once()


class TestCreatePlayerModel:
    """AC-002+: ModelConfig is translated via create_model and forwarded."""

    def test_passes_model_from_create_model_to_create_agent(self) -> None:
        """create_player translates ModelConfig via create_model and forwards result."""
        sentinel_model = MagicMock(name="translated_model")
        config = _make_model_config()
        with (
            patch("agents.player.create_agent") as mock_ca,
            patch("agents.player.create_model", return_value=sentinel_model),
            patch("agents.player.FilesystemBackend"),
        ):
            from agents.player import create_player

            create_player(
                model_config=config,
                tools=[MagicMock(), MagicMock()],
                system_prompt="test prompt",
                memory=["./AGENTS.md"],
            )
        _, kwargs = mock_ca.call_args
        assert kwargs["model"] is sentinel_model


class TestCreatePlayerBackend:
    """TASK-TRF-003: no backend kwarg passed to create_agent."""

    def test_no_backend_kwarg(self) -> None:
        """create_player does not pass backend kwarg to create_agent."""
        with (
            patch("agents.player.create_agent") as mock_ca,
            patch("agents.player.create_model"),
            patch("agents.player.FilesystemBackend"),
        ):
            from agents.player import create_player

            create_player(
                model_config=_make_model_config(),
                tools=[MagicMock(), MagicMock()],
                system_prompt="test prompt",
                memory=["./AGENTS.md"],
            )
        _, kwargs = mock_ca.call_args
        assert "backend" not in kwargs


class TestCreatePlayerTools:
    """AC-004: tools parameter is passed through."""

    def test_tools_passed_through_to_create_agent(self) -> None:
        """create_player forwards tools list to create_agent."""
        tool_a = MagicMock(name="rag_retrieval")
        tool_b = MagicMock(name="write_output")
        with (
            patch("agents.player.create_agent") as mock_ca,
            patch("agents.player.create_model"),
            patch("agents.player.FilesystemBackend"),
        ):
            from agents.player import create_player

            create_player(
                model_config=_make_model_config(),
                tools=[tool_a, tool_b],
                system_prompt="test prompt",
                memory=["./AGENTS.md"],
            )
        _, kwargs = mock_ca.call_args
        assert tool_a in kwargs["tools"]
        assert tool_b in kwargs["tools"]
        assert len(kwargs["tools"]) == 2


class TestCreatePlayerSystemPrompt:
    """AC-005: system_prompt is passed as system_prompt kwarg."""

    def test_system_prompt_forwarded_to_create_agent(self) -> None:
        """create_player passes system_prompt to create_agent."""
        prompt = "You are a player agent for training data generation."
        with (
            patch("agents.player.create_agent") as mock_ca,
            patch("agents.player.create_model"),
            patch("agents.player.FilesystemBackend"),
        ):
            from agents.player import create_player

            create_player(
                model_config=_make_model_config(),
                tools=[MagicMock(), MagicMock()],
                system_prompt=prompt,
                memory=["./AGENTS.md"],
            )
        _, kwargs = mock_ca.call_args
        assert kwargs["system_prompt"] == prompt


class TestCreatePlayerMemory:
    """AC-006: memory is wired via MemoryMiddleware in the middleware stack."""

    def test_memory_wired_through_middleware(self) -> None:
        """create_player wires memory via MemoryMiddleware, not as a direct kwarg."""
        from deepagents.middleware import MemoryMiddleware

        memory = ["./AGENTS.md"]
        with (
            patch("agents.player.create_agent") as mock_ca,
            patch("agents.player.create_model"),
            patch("agents.player.FilesystemBackend"),
        ):
            from agents.player import create_player

            create_player(
                model_config=_make_model_config(),
                tools=[MagicMock(), MagicMock()],
                system_prompt="test prompt",
                memory=memory,
            )
        _, kwargs = mock_ca.call_args
        mem_mw = [m for m in kwargs["middleware"] if isinstance(m, MemoryMiddleware)]
        assert len(mem_mw) == 1
        assert mem_mw[0].sources == memory


class TestCreatePlayerValidation:
    """AC-007: Empty system prompt raises a validation error."""

    def test_empty_system_prompt_raises_value_error(self) -> None:
        """create_player raises ValueError when system_prompt is empty."""
        with (
            patch("agents.player.create_agent"),
            patch("agents.player.create_model"),
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
        """create_player raises ValueError when system_prompt is whitespace."""
        with (
            patch("agents.player.create_agent"),
            patch("agents.player.create_model"),
            patch("agents.player.FilesystemBackend"),
        ):
            from agents.player import create_player

            with pytest.raises(ValueError, match="system_prompt"):
                create_player(
                    model_config=_make_model_config(),
                    tools=[MagicMock(), MagicMock()],
                    system_prompt="   ",
                    memory=["./AGENTS.md"],
                )


class TestNoFilesystemBackendImport:
    """TASK-TRF-016: FilesystemBackend IS now imported (used for MemoryMiddleware)."""

    def test_filesystem_backend_in_source(self) -> None:
        """agents/player.py imports FilesystemBackend for MemoryMiddleware backing."""
        player_path = Path(__file__).resolve().parent.parent / "player.py"
        source = player_path.read_text()
        tree = ast.parse(source)

        imported_names: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                for alias in node.names:
                    imported_names.append(alias.name)

        assert "FilesystemBackend" in imported_names, (
            "FilesystemBackend should be imported for MemoryMiddleware backing"
        )

    def test_create_deep_agent_not_imported(self) -> None:
        """agents/player.py must NOT import create_deep_agent."""
        player_path = Path(__file__).resolve().parent.parent / "player.py"
        source = player_path.read_text()
        tree = ast.parse(source)

        imported_names: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                for alias in node.names:
                    imported_names.append(alias.name)
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    imported_names.append(alias.name)

        assert "create_deep_agent" not in imported_names, (
            "create_deep_agent must NOT be imported in agents/player.py"
        )


class TestCreatePlayerSeam:
    """Seam test: verify ModelConfig contract from TASK-AF-001."""

    @pytest.mark.seam
    @pytest.mark.integration_contract("ModelConfig")
    def test_model_config_format(self) -> None:
        """Verify ModelConfig matches the expected format.

        Contract: ModelConfig must be translated to a concrete model object
        via create_model() before passing to create_agent.
        Producer: TASK-AF-001.
        """
        config = ModelConfig(
            provider="local",
            model="test-model",
            endpoint="http://localhost:8000/v1",
        )
        assert config.provider in ("local", "anthropic", "openai")
        assert config.model
        assert config.endpoint
