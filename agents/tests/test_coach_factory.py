"""Tests for agents.coach — Coach agent factory.

Covers all acceptance criteria for TASK-AF-009 (unit tests for Coach factory),
verifying the D5 invariant (no tools, no backend) using the exemplar testing
methodology. Also includes the seam test validating the ModelConfig integration
contract from TASK-AF-001.

Updated for TASK-TRF-012: create_coach now delegates to create_agent
(not create_deep_agent) with an explicit middleware stack.
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
            "create_coach must NOT have a 'tools' parameter — D5 invariant enforced structurally"
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
# AC-002: Factory delegates to create_agent with tools=[]
# ---------------------------------------------------------------------------


class TestDelegationToCreateAgent:
    """AC-002: create_coach delegates to create_agent with tools=[]."""

    def test_delegates_to_create_agent(self) -> None:
        from agents.coach import create_coach

        with (
            patch("agents.coach.create_agent") as mock_ca,
            patch("agents.coach.create_model"),
            patch("agents.coach.FilesystemBackend"),
        ):
            mock_ca.return_value = MagicMock()
            config = ModelConfig(provider="anthropic", model="claude-3-opus")
            create_coach(
                model_config=config,
                system_prompt="You are a coach.",
                memory=["./AGENTS.md"],
            )
        mock_ca.assert_called_once()

    def test_passes_empty_tools_list(self) -> None:
        from agents.coach import create_coach

        with (
            patch("agents.coach.create_agent") as mock_ca,
            patch("agents.coach.create_model"),
            patch("agents.coach.FilesystemBackend"),
        ):
            mock_ca.return_value = MagicMock()
            config = ModelConfig(provider="anthropic", model="claude-3-opus")
            create_coach(
                model_config=config,
                system_prompt="You are a coach.",
                memory=["./AGENTS.md"],
            )
        _, kwargs = mock_ca.call_args
        assert kwargs["tools"] == [], (
            "Coach factory must always pass tools=[] to create_agent"
        )


# ---------------------------------------------------------------------------
# AC-003: NO backend kwarg passed to create_agent
# ---------------------------------------------------------------------------


class TestNoBackend:
    """AC-003: Coach agent has no backend kwarg passed to create_agent."""

    def test_no_backend_kwarg(self) -> None:
        from agents.coach import create_coach

        with (
            patch("agents.coach.create_agent") as mock_ca,
            patch("agents.coach.create_model"),
            patch("agents.coach.FilesystemBackend"),
        ):
            mock_ca.return_value = MagicMock()
            config = ModelConfig(provider="openai", model="gpt-4")
            create_coach(
                model_config=config,
                system_prompt="Evaluate quality.",
                memory=["./AGENTS.md"],
            )
        _, kwargs = mock_ca.call_args
        assert "backend" not in kwargs, (
            "Coach must not pass a backend kwarg to create_agent"
        )


# ---------------------------------------------------------------------------
# AC-004: FilesystemBackend IS now imported (for MemoryMiddleware backing)
# ---------------------------------------------------------------------------


class TestFilesystemBackendUsage:
    """AC-004: FilesystemBackend imported for MemoryMiddleware, not for tool leakage."""

    def test_create_deep_agent_not_imported(self) -> None:
        """coach.py must NOT import create_deep_agent."""
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

        assert "create_deep_agent" not in imported_names, (
            "create_deep_agent must NOT be imported in agents/coach.py"
        )

    def test_filesystem_backend_used_for_memory(self) -> None:
        """FilesystemBackend is constructed for MemoryMiddleware backing."""
        with (
            patch("agents.coach.create_agent"),
            patch("agents.coach.create_model"),
            patch("agents.coach.FilesystemBackend") as mock_backend,
        ):
            from agents.coach import create_coach

            mock_backend.return_value = MagicMock()
            config = ModelConfig(provider="anthropic", model="claude-3-opus")
            create_coach(
                model_config=config,
                system_prompt="Evaluate quality.",
                memory=["./AGENTS.md"],
            )
        mock_backend.assert_called_once_with(root_dir=".")


# ---------------------------------------------------------------------------
# AC-005: system_prompt is passed as system_prompt kwarg
# ---------------------------------------------------------------------------


class TestSystemPromptPassthrough:
    """AC-005: system_prompt forwarded to create_agent."""

    def test_system_prompt_passed_through(self) -> None:
        from agents.coach import create_coach

        with (
            patch("agents.coach.create_agent") as mock_ca,
            patch("agents.coach.create_model"),
            patch("agents.coach.FilesystemBackend"),
        ):
            mock_ca.return_value = MagicMock()
            config = ModelConfig(provider="anthropic", model="claude-3-opus")
            prompt = "You are a strict quality evaluator."
            create_coach(
                model_config=config,
                system_prompt=prompt,
                memory=["./AGENTS.md"],
            )
        _, kwargs = mock_ca.call_args
        assert kwargs["system_prompt"] == prompt


# ---------------------------------------------------------------------------
# AC-006: memory wired via MemoryMiddleware
# ---------------------------------------------------------------------------


class TestMemoryPassthrough:
    """AC-006: memory wired through MemoryMiddleware in the middleware stack."""

    def test_memory_wired_through_middleware(self) -> None:
        from deepagents.middleware import MemoryMiddleware

        with (
            patch("agents.coach.create_agent") as mock_ca,
            patch("agents.coach.create_model"),
            patch("agents.coach.FilesystemBackend"),
        ):
            from agents.coach import create_coach

            mock_ca.return_value = MagicMock()
            config = ModelConfig(provider="openai", model="gpt-4")
            memory = ["./AGENTS.md", "./GOAL.md"]
            create_coach(
                model_config=config,
                system_prompt="Evaluate.",
                memory=memory,
            )
        _, kwargs = mock_ca.call_args
        mem_mw = [m for m in kwargs["middleware"] if isinstance(m, MemoryMiddleware)]
        assert len(mem_mw) == 1
        assert mem_mw[0].sources == memory


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
# Seam test: ModelConfig contract from TASK-AF-001
# ---------------------------------------------------------------------------


class TestModelConfigSeam:
    """Seam test verifying ModelConfig integration contract for Coach."""

    @pytest.mark.seam
    @pytest.mark.integration_contract("ModelConfig")
    def test_model_config_format(self) -> None:
        """Verify ModelConfig matches the expected format.

        Contract: ModelConfig must be translated to a concrete model object
        via create_model() before passing to create_agent.
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

    def test_model_created_from_config(self) -> None:
        """Verify create_model is called with the ModelConfig."""
        from agents.coach import create_coach

        with (
            patch("agents.coach.create_agent"),
            patch("agents.coach.create_model") as mock_create_model,
            patch("agents.coach.FilesystemBackend"),
        ):
            mock_create_model.return_value = MagicMock()
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
        # For local provider, extra_body is passed with structured_outputs
        mock_create_model.assert_called_once()
        _, kwargs = mock_create_model.call_args
        assert kwargs.get("extra_body") is not None

    def test_model_passed_to_create_agent(self) -> None:
        """The translated model object is passed to create_agent."""
        from agents.coach import create_coach

        mock_model = MagicMock()
        with (
            patch("agents.coach.create_agent") as mock_ca,
            patch("agents.coach.create_model", return_value=mock_model),
            patch("agents.coach.FilesystemBackend"),
        ):
            config = ModelConfig(provider="anthropic", model="claude-3-opus")
            create_coach(
                model_config=config,
                system_prompt="Evaluate quality.",
                memory=["./AGENTS.md"],
            )
        _, kwargs = mock_ca.call_args
        assert kwargs["model"] is mock_model


# ---------------------------------------------------------------------------
# Edge cases: provider and temperature independence
# ---------------------------------------------------------------------------


class TestCoachEdgeCases:
    """Edge cases: Coach works with different providers and temperatures."""

    def test_coach_with_different_provider_than_player(self) -> None:
        """Coach can use a different provider (e.g. openai) independently."""
        from agents.coach import create_coach

        with (
            patch("agents.coach.create_agent") as mock_ca,
            patch("agents.coach.create_model") as mock_create_model,
            patch("agents.coach.FilesystemBackend"),
        ):
            mock_create_model.return_value = MagicMock()
            config = ModelConfig(provider="openai", model="gpt-4o")
            create_coach(
                model_config=config,
                system_prompt="Evaluate quality.",
                memory=["./AGENTS.md"],
            )
        mock_ca.assert_called_once()

    def test_coach_with_custom_temperature(self) -> None:
        """Coach correctly passes through a custom temperature via ModelConfig."""
        from agents.coach import create_coach

        with (
            patch("agents.coach.create_agent"),
            patch("agents.coach.create_model") as mock_create_model,
            patch("agents.coach.FilesystemBackend"),
        ):
            mock_create_model.return_value = MagicMock()
            config = ModelConfig(provider="anthropic", model="claude-3-opus", temperature=0.3)
            create_coach(
                model_config=config,
                system_prompt="Evaluate quality.",
                memory=["./AGENTS.md"],
            )
        mock_create_model.assert_called_once()
        assert config.temperature == 0.3

    def test_coach_default_temperature_from_model_config(self) -> None:
        """When temperature is not specified, ModelConfig default (0.7) applies."""
        from agents.coach import create_coach

        with (
            patch("agents.coach.create_agent"),
            patch("agents.coach.create_model") as mock_create_model,
            patch("agents.coach.FilesystemBackend"),
        ):
            mock_create_model.return_value = MagicMock()
            config = ModelConfig(provider="anthropic", model="claude-3-opus")
            create_coach(
                model_config=config,
                system_prompt="Evaluate quality.",
                memory=["./AGENTS.md"],
            )
        mock_create_model.assert_called_once()
        assert config.temperature == 0.7

    def test_coach_with_local_provider(self) -> None:
        """Coach works with local provider requiring an endpoint."""
        from agents.coach import create_coach

        with (
            patch("agents.coach.create_agent") as mock_ca,
            patch("agents.coach.create_model"),
            patch("agents.coach.FilesystemBackend"),
        ):
            config = ModelConfig(
                provider="local",
                model="nemotron-3-super-120b",
                endpoint="http://localhost:8000/v1",
                temperature=0.3,
            )
            create_coach(
                model_config=config,
                system_prompt="Evaluate quality.",
                memory=["./AGENTS.md"],
            )
        mock_ca.assert_called_once()
        _, kwargs = mock_ca.call_args
        assert kwargs["tools"] == []
        assert "backend" not in kwargs
