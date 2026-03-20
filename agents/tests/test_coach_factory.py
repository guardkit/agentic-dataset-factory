"""Tests for agents.coach — Coach agent factory.

Covers all acceptance criteria for TASK-AF-004 and the seam test
validating the ModelConfig integration contract from TASK-AF-001.

TDD approach: these tests are written FIRST (RED), then create_coach()
is implemented to make them pass (GREEN).
"""

from __future__ import annotations

import ast
import inspect
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from config.models import ModelConfig


# ---------------------------------------------------------------------------
# AC-001: agents/coach.py contains create_coach() with the contract signature
#         (no `tools` parameter)
# ---------------------------------------------------------------------------


class TestCreateCoachSignature:
    """AC-001: create_coach exists with correct signature."""

    def test_create_coach_is_callable(self) -> None:
        from agents.coach import create_coach

        assert callable(create_coach)

    def test_create_coach_has_no_tools_parameter(self) -> None:
        """Structural enforcement of D5: signature must NOT accept tools."""
        from agents.coach import create_coach

        sig = inspect.signature(create_coach)
        param_names = set(sig.parameters.keys())
        assert "tools" not in param_names, (
            "create_coach must NOT have a 'tools' parameter — "
            "D5 invariant enforced structurally"
        )

    def test_create_coach_accepts_model_config(self) -> None:
        from agents.coach import create_coach

        sig = inspect.signature(create_coach)
        assert "model_config" in sig.parameters

    def test_create_coach_accepts_system_prompt(self) -> None:
        from agents.coach import create_coach

        sig = inspect.signature(create_coach)
        assert "system_prompt" in sig.parameters

    def test_create_coach_accepts_memory(self) -> None:
        from agents.coach import create_coach

        sig = inspect.signature(create_coach)
        assert "memory" in sig.parameters


# ---------------------------------------------------------------------------
# AC-002: Factory delegates to create_deep_agent with tools=[]
# ---------------------------------------------------------------------------


class TestDelegationToCreateDeepAgent:
    """AC-002: create_coach delegates to create_deep_agent with tools=[]."""

    @patch("agents.coach.create_deep_agent")
    @patch("agents.coach.create_model")
    def test_delegates_to_create_deep_agent(
        self, mock_create_model: MagicMock, mock_create_deep: MagicMock
    ) -> None:
        from agents.coach import create_coach

        mock_model = MagicMock()
        mock_create_model.return_value = mock_model
        config = ModelConfig(provider="anthropic", model="claude-3-opus")

        create_coach(
            model_config=config,
            system_prompt="You are a coach.",
            memory=["./AGENTS.md"],
        )

        mock_create_deep.assert_called_once()

    @patch("agents.coach.create_deep_agent")
    @patch("agents.coach.create_model")
    def test_passes_empty_tools_list(
        self, mock_create_model: MagicMock, mock_create_deep: MagicMock
    ) -> None:
        from agents.coach import create_coach

        mock_create_model.return_value = MagicMock()
        config = ModelConfig(provider="anthropic", model="claude-3-opus")

        create_coach(
            model_config=config,
            system_prompt="You are a coach.",
            memory=["./AGENTS.md"],
        )

        call_kwargs = mock_create_deep.call_args
        assert call_kwargs.kwargs.get("tools") == [], (
            "Coach factory must always pass tools=[] to create_deep_agent"
        )


# ---------------------------------------------------------------------------
# AC-003: NO backend kwarg passed (or explicitly backend=None)
# ---------------------------------------------------------------------------


class TestNoBackend:
    """AC-003: Coach agent has no FilesystemBackend."""

    @patch("agents.coach.create_deep_agent")
    @patch("agents.coach.create_model")
    def test_no_backend_kwarg_or_none(
        self, mock_create_model: MagicMock, mock_create_deep: MagicMock
    ) -> None:
        from agents.coach import create_coach

        mock_create_model.return_value = MagicMock()
        config = ModelConfig(provider="openai", model="gpt-4")

        create_coach(
            model_config=config,
            system_prompt="Evaluate quality.",
            memory=["./AGENTS.md"],
        )

        call_kwargs = mock_create_deep.call_args
        # backend must either not be passed or be explicitly None
        backend_value = call_kwargs.kwargs.get("backend")
        assert backend_value is None, (
            f"Coach must not pass a backend to create_deep_agent, got {backend_value}"
        )


# ---------------------------------------------------------------------------
# AC-004: FilesystemBackend is NOT imported in agents/coach.py
# ---------------------------------------------------------------------------


class TestNoFilesystemBackendImport:
    """AC-004: FilesystemBackend not imported in coach module."""

    def test_filesystem_backend_not_in_source(self) -> None:
        """Parse coach.py AST to ensure FilesystemBackend is never imported."""
        coach_path = Path(__file__).resolve().parent.parent / "coach.py"
        source = coach_path.read_text()
        tree = ast.parse(source)

        imported_names: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                for alias in node.names:
                    imported_names.append(alias.name)
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    imported_names.append(alias.name)

        assert "FilesystemBackend" not in imported_names, (
            "FilesystemBackend must NOT be imported in agents/coach.py"
        )

    def test_filesystem_backend_not_in_source_text(self) -> None:
        """Belt-and-suspenders: grep for the string in source."""
        coach_path = Path(__file__).resolve().parent.parent / "coach.py"
        source = coach_path.read_text()
        assert "FilesystemBackend" not in source, (
            "The string 'FilesystemBackend' must not appear in agents/coach.py"
        )


# ---------------------------------------------------------------------------
# AC-005: system_prompt is passed as system_prompt kwarg
# ---------------------------------------------------------------------------


class TestSystemPromptPassthrough:
    """AC-005: system_prompt forwarded to create_deep_agent."""

    @patch("agents.coach.create_deep_agent")
    @patch("agents.coach.create_model")
    def test_system_prompt_passed_through(
        self, mock_create_model: MagicMock, mock_create_deep: MagicMock
    ) -> None:
        from agents.coach import create_coach

        mock_create_model.return_value = MagicMock()
        config = ModelConfig(provider="anthropic", model="claude-3-opus")
        prompt = "You are a strict quality evaluator."

        create_coach(
            model_config=config,
            system_prompt=prompt,
            memory=["./AGENTS.md"],
        )

        call_kwargs = mock_create_deep.call_args
        assert call_kwargs.kwargs.get("system_prompt") == prompt


# ---------------------------------------------------------------------------
# AC-006: memory list is passed as memory kwarg
# ---------------------------------------------------------------------------


class TestMemoryPassthrough:
    """AC-006: memory list forwarded to create_deep_agent."""

    @patch("agents.coach.create_deep_agent")
    @patch("agents.coach.create_model")
    def test_memory_passed_through(
        self, mock_create_model: MagicMock, mock_create_deep: MagicMock
    ) -> None:
        from agents.coach import create_coach

        mock_create_model.return_value = MagicMock()
        config = ModelConfig(provider="openai", model="gpt-4")
        memory = ["./AGENTS.md", "./GOAL.md"]

        create_coach(
            model_config=config,
            system_prompt="Evaluate.",
            memory=memory,
        )

        call_kwargs = mock_create_deep.call_args
        assert call_kwargs.kwargs.get("memory") == memory


# ---------------------------------------------------------------------------
# AC-007: Empty system prompt raises a validation error
# ---------------------------------------------------------------------------


class TestEmptySystemPromptRejected:
    """AC-007: empty system_prompt raises ValueError."""

    def test_empty_string_system_prompt_raises(self) -> None:
        from agents.coach import create_coach

        config = ModelConfig(provider="anthropic", model="claude-3-opus")

        with pytest.raises(ValueError, match="[Ss]ystem.prompt"):
            create_coach(
                model_config=config,
                system_prompt="",
                memory=["./AGENTS.md"],
            )

    def test_whitespace_only_system_prompt_raises(self) -> None:
        from agents.coach import create_coach

        config = ModelConfig(provider="anthropic", model="claude-3-opus")

        with pytest.raises(ValueError, match="[Ss]ystem.prompt"):
            create_coach(
                model_config=config,
                system_prompt="   \n\t  ",
                memory=["./AGENTS.md"],
            )


# ---------------------------------------------------------------------------
# AC-008: lint/format (verified separately via ruff)
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Seam test: ModelConfig contract from TASK-AF-001
# ---------------------------------------------------------------------------


class TestModelConfigSeam:
    """Seam test verifying ModelConfig integration contract for Coach."""

    @pytest.mark.seam
    @pytest.mark.integration_contract("ModelConfig")
    def test_model_config_format(self) -> None:
        """Verify ModelConfig matches the expected format.

        Contract: ModelConfig must be translated to a concrete model object
        via create_model() before passing to create_deep_agent.
        Producer: TASK-AF-001
        """
        config = ModelConfig(provider="anthropic", model="claude-sonnet-4-20250514")
        assert config.provider in ("local", "anthropic", "openai"), (
            f"Invalid provider: {config.provider}"
        )
        assert config.model, "model must not be empty"


# ---------------------------------------------------------------------------
# BDD: Coach factory always passes an empty tools list (extra scenario)
# ---------------------------------------------------------------------------


class TestCoachToolsInvariant:
    """BDD extra: Coach always gets tools=[], regardless of input."""

    @patch("agents.coach.create_deep_agent")
    @patch("agents.coach.create_model")
    def test_model_created_from_config(
        self, mock_create_model: MagicMock, mock_create_deep: MagicMock
    ) -> None:
        """Verify create_model is called with the ModelConfig."""
        from agents.coach import create_coach

        mock_model = MagicMock()
        mock_create_model.return_value = mock_model
        config = ModelConfig(
            provider="local",
            model="nemotron",
            endpoint="http://localhost:8000/v1",
        )

        create_coach(
            model_config=config,
            system_prompt="Evaluate quality.",
            memory=["./AGENTS.md"],
        )

        mock_create_model.assert_called_once_with(config)

    @patch("agents.coach.create_deep_agent")
    @patch("agents.coach.create_model")
    def test_model_passed_to_create_deep_agent(
        self, mock_create_model: MagicMock, mock_create_deep: MagicMock
    ) -> None:
        """The translated model object is passed to create_deep_agent."""
        from agents.coach import create_coach

        mock_model = MagicMock()
        mock_create_model.return_value = mock_model
        config = ModelConfig(provider="anthropic", model="claude-3-opus")

        create_coach(
            model_config=config,
            system_prompt="Evaluate quality.",
            memory=["./AGENTS.md"],
        )

        call_kwargs = mock_create_deep.call_args
        assert call_kwargs.kwargs.get("model") == mock_model
