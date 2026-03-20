"""Tests for agents.player.create_player factory function.

Covers all acceptance criteria for TASK-AF-003.
Uses patch-at-import-site pattern and call_args keyword argument assertions.
"""

from __future__ import annotations

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
    """AC-002: Factory delegates to create_deep_agent with correct kwargs."""

    def test_returns_result_of_create_deep_agent(self) -> None:
        """create_player returns whatever create_deep_agent returns."""
        fake_agent = MagicMock(name="fake_player_agent")
        with (
            patch("agents.player.create_deep_agent", return_value=fake_agent),
            patch("agents.player.FilesystemBackend"),
            patch("agents.player.create_model"),
        ):
            from agents.player import create_player

            result = create_player(
                model_config=_make_model_config(),
                tools=[MagicMock(), MagicMock()],
                system_prompt="test prompt",
                memory=["./AGENTS.md"],
            )
        assert result is fake_agent

    def test_delegates_to_create_deep_agent(self) -> None:
        """create_player calls create_deep_agent exactly once."""
        with (
            patch("agents.player.create_deep_agent") as mock_cda,
            patch("agents.player.FilesystemBackend"),
            patch("agents.player.create_model"),
        ):
            from agents.player import create_player

            create_player(
                model_config=_make_model_config(),
                tools=[MagicMock(), MagicMock()],
                system_prompt="test prompt",
                memory=["./AGENTS.md"],
            )
        mock_cda.assert_called_once()


class TestCreatePlayerModel:
    """AC-002+: ModelConfig is translated via create_model and forwarded."""

    def test_passes_model_from_create_model_to_create_deep_agent(self) -> None:
        """create_player translates ModelConfig via create_model and forwards result."""
        sentinel_model = MagicMock(name="translated_model")
        config = _make_model_config()
        with (
            patch("agents.player.create_deep_agent") as mock_cda,
            patch("agents.player.FilesystemBackend"),
            patch("agents.player.create_model", return_value=sentinel_model) as mock_cm,
        ):
            from agents.player import create_player

            create_player(
                model_config=config,
                tools=[MagicMock(), MagicMock()],
                system_prompt="test prompt",
                memory=["./AGENTS.md"],
            )
        mock_cm.assert_called_once_with(config)
        _, kwargs = mock_cda.call_args
        assert kwargs["model"] is sentinel_model


class TestCreatePlayerBackend:
    """AC-003: FilesystemBackend is instantiated and passed as backend kwarg."""

    def test_backend_is_filesystem_backend_with_root_dot(self) -> None:
        """create_player uses FilesystemBackend(root_dir='.') as backend."""
        with (
            patch("agents.player.create_deep_agent") as mock_cda,
            patch("agents.player.FilesystemBackend") as mock_backend_cls,
            patch("agents.player.create_model"),
        ):
            fake_backend = MagicMock(name="fs_backend")
            mock_backend_cls.return_value = fake_backend

            from agents.player import create_player

            create_player(
                model_config=_make_model_config(),
                tools=[MagicMock(), MagicMock()],
                system_prompt="test prompt",
                memory=["./AGENTS.md"],
            )
        mock_backend_cls.assert_called_once_with(root_dir=".")
        _, kwargs = mock_cda.call_args
        assert kwargs["backend"] is fake_backend


class TestCreatePlayerTools:
    """AC-004: tools parameter is passed through (expected: 2 tools)."""

    def test_tools_passed_through_to_create_deep_agent(self) -> None:
        """create_player forwards tools list to create_deep_agent."""
        tool_a = MagicMock(name="rag_retrieval")
        tool_b = MagicMock(name="write_output")
        with (
            patch("agents.player.create_deep_agent") as mock_cda,
            patch("agents.player.FilesystemBackend"),
            patch("agents.player.create_model"),
        ):
            from agents.player import create_player

            create_player(
                model_config=_make_model_config(),
                tools=[tool_a, tool_b],
                system_prompt="test prompt",
                memory=["./AGENTS.md"],
            )
        _, kwargs = mock_cda.call_args
        assert tool_a in kwargs["tools"]
        assert tool_b in kwargs["tools"]
        assert len(kwargs["tools"]) == 2


class TestCreatePlayerSystemPrompt:
    """AC-005: system_prompt is passed as system_prompt kwarg."""

    def test_system_prompt_forwarded_to_create_deep_agent(self) -> None:
        """create_player passes system_prompt to create_deep_agent."""
        prompt = "You are a player agent for training data generation."
        with (
            patch("agents.player.create_deep_agent") as mock_cda,
            patch("agents.player.FilesystemBackend"),
            patch("agents.player.create_model"),
        ):
            from agents.player import create_player

            create_player(
                model_config=_make_model_config(),
                tools=[MagicMock(), MagicMock()],
                system_prompt=prompt,
                memory=["./AGENTS.md"],
            )
        _, kwargs = mock_cda.call_args
        assert kwargs["system_prompt"] == prompt


class TestCreatePlayerMemory:
    """AC-006: memory list is passed as memory kwarg."""

    def test_memory_forwarded_to_create_deep_agent(self) -> None:
        """create_player passes memory list to create_deep_agent."""
        memory = ["./AGENTS.md"]
        with (
            patch("agents.player.create_deep_agent") as mock_cda,
            patch("agents.player.FilesystemBackend"),
            patch("agents.player.create_model"),
        ):
            from agents.player import create_player

            create_player(
                model_config=_make_model_config(),
                tools=[MagicMock(), MagicMock()],
                system_prompt="test prompt",
                memory=memory,
            )
        _, kwargs = mock_cda.call_args
        assert kwargs["memory"] == ["./AGENTS.md"]


class TestCreatePlayerValidation:
    """AC-007: Empty system prompt raises a validation error."""

    def test_empty_system_prompt_raises_value_error(self) -> None:
        """create_player raises ValueError when system_prompt is empty."""
        with (
            patch("agents.player.create_deep_agent"),
            patch("agents.player.FilesystemBackend"),
            patch("agents.player.create_model"),
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
            patch("agents.player.create_deep_agent"),
            patch("agents.player.FilesystemBackend"),
            patch("agents.player.create_model"),
        ):
            from agents.player import create_player

            with pytest.raises(ValueError, match="system_prompt"):
                create_player(
                    model_config=_make_model_config(),
                    tools=[MagicMock(), MagicMock()],
                    system_prompt="   ",
                    memory=["./AGENTS.md"],
                )


class TestCreatePlayerSeam:
    """Seam test: verify ModelConfig contract from TASK-AF-001."""

    @pytest.mark.seam
    @pytest.mark.integration_contract("ModelConfig")
    def test_model_config_format(self) -> None:
        """Verify ModelConfig matches the expected format.

        Contract: ModelConfig must be translated to a concrete model object
        via create_model() before passing to create_deep_agent.
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
