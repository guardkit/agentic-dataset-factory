"""Unit tests for Coach factory — TASK-TRF-012.

Tests the ``create_coach`` factory function to verify:
- Coach uses ``create_agent`` (not ``create_deep_agent``) to avoid
  FilesystemMiddleware tool leakage.
- Coach has exactly 0 tools.
- Coach does not import ``create_deep_agent``.
- MemoryMiddleware is wired with a FilesystemBackend for AGENTS.md injection.
- PatchToolCallsMiddleware and AnthropicPromptCachingMiddleware are included.
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


def _call_create_coach(
    mock_create_agent: MagicMock,
    *,
    model_config: ModelConfig | None = None,
    system_prompt: str = "You are a Coach agent.",
    memory: list[str] | None = None,
) -> object:
    """Invoke create_coach with sensible defaults and return its result."""
    from agents.coach import create_coach

    if model_config is None:
        model_config = _make_model_config()
    if memory is None:
        memory = ["./AGENTS.md"]
    return create_coach(
        model_config=model_config,
        system_prompt=system_prompt,
        memory=memory,
    )


# ---------------------------------------------------------------------------
# Coach uses create_agent (not create_deep_agent)
# ---------------------------------------------------------------------------


class TestCoachUsesCreateAgent:
    """Coach factory uses langchain create_agent, not deepagents create_deep_agent."""

    def test_create_agent_called(self) -> None:
        """create_coach delegates to langchain's create_agent."""
        with (
            patch("agents.coach.create_agent") as mock_ca,
            patch("agents.coach.create_model"),
            patch("agents.coach.FilesystemBackend"),
        ):
            _call_create_coach(mock_ca)
        mock_ca.assert_called_once()

    def test_returns_result_of_create_agent(self) -> None:
        """create_coach returns whatever create_agent returns."""
        fake_agent = MagicMock(name="fake_coach_agent")
        with (
            patch("agents.coach.create_agent", return_value=fake_agent) as mock_ca,
            patch("agents.coach.create_model"),
            patch("agents.coach.FilesystemBackend"),
        ):
            result = _call_create_coach(mock_ca)
        assert result is fake_agent


# ---------------------------------------------------------------------------
# Coach has zero tools
# ---------------------------------------------------------------------------


class TestCoachHasNoTools:
    """Coach must have exactly 0 tools — no filesystem tools leaked."""

    def test_tools_is_empty_list(self) -> None:
        """create_coach passes tools=[] to create_agent."""
        with (
            patch("agents.coach.create_agent") as mock_ca,
            patch("agents.coach.create_model"),
            patch("agents.coach.FilesystemBackend"),
        ):
            _call_create_coach(mock_ca)
        _, kwargs = mock_ca.call_args
        assert kwargs["tools"] == []

    def test_no_filesystem_middleware_in_stack(self) -> None:
        """FilesystemMiddleware must NOT be in the middleware stack."""
        from deepagents.middleware import FilesystemMiddleware

        with (
            patch("agents.coach.create_agent") as mock_ca,
            patch("agents.coach.create_model"),
            patch("agents.coach.FilesystemBackend"),
        ):
            _call_create_coach(mock_ca)
        _, kwargs = mock_ca.call_args
        middleware_types = [type(m) for m in kwargs["middleware"]]
        assert FilesystemMiddleware not in middleware_types


# ---------------------------------------------------------------------------
# Coach middleware stack is correct
# ---------------------------------------------------------------------------


class TestCoachMiddlewareStack:
    """Coach middleware includes Memory, PatchToolCalls, AnthropicCaching."""

    def test_memory_middleware_present(self) -> None:
        """MemoryMiddleware is in the Coach's middleware stack."""
        from deepagents.middleware import MemoryMiddleware

        with (
            patch("agents.coach.create_agent") as mock_ca,
            patch("agents.coach.create_model"),
            patch("agents.coach.FilesystemBackend"),
        ):
            _call_create_coach(mock_ca)
        _, kwargs = mock_ca.call_args
        middleware_types = [type(m) for m in kwargs["middleware"]]
        assert MemoryMiddleware in middleware_types

    def test_patch_tool_calls_middleware_present(self) -> None:
        """PatchToolCallsMiddleware is in the Coach's middleware stack."""
        from deepagents.middleware.patch_tool_calls import PatchToolCallsMiddleware

        with (
            patch("agents.coach.create_agent") as mock_ca,
            patch("agents.coach.create_model"),
            patch("agents.coach.FilesystemBackend"),
        ):
            _call_create_coach(mock_ca)
        _, kwargs = mock_ca.call_args
        middleware_types = [type(m) for m in kwargs["middleware"]]
        assert PatchToolCallsMiddleware in middleware_types

    def test_anthropic_caching_middleware_present(self) -> None:
        """AnthropicPromptCachingMiddleware is in the Coach's middleware stack."""
        from langchain_anthropic.middleware import AnthropicPromptCachingMiddleware

        with (
            patch("agents.coach.create_agent") as mock_ca,
            patch("agents.coach.create_model"),
            patch("agents.coach.FilesystemBackend"),
        ):
            _call_create_coach(mock_ca)
        _, kwargs = mock_ca.call_args
        middleware_types = [type(m) for m in kwargs["middleware"]]
        assert AnthropicPromptCachingMiddleware in middleware_types

    def test_exactly_three_middleware(self) -> None:
        """Coach has exactly 3 middleware (Memory, PatchToolCalls, AnthropicCaching)."""
        with (
            patch("agents.coach.create_agent") as mock_ca,
            patch("agents.coach.create_model"),
            patch("agents.coach.FilesystemBackend"),
        ):
            _call_create_coach(mock_ca)
        _, kwargs = mock_ca.call_args
        assert len(kwargs["middleware"]) == 3


# ---------------------------------------------------------------------------
# Coach call_args keyword verification
# ---------------------------------------------------------------------------


class TestCoachCallArgs:
    """Verify keyword arguments passed to create_agent."""

    def test_system_prompt_forwarded(self) -> None:
        """create_coach passes system_prompt through to create_agent."""
        prompt = "Evaluate the training example."
        with (
            patch("agents.coach.create_agent") as mock_ca,
            patch("agents.coach.create_model"),
            patch("agents.coach.FilesystemBackend"),
        ):
            _call_create_coach(mock_ca, system_prompt=prompt)
        _, kwargs = mock_ca.call_args
        assert kwargs["system_prompt"] == prompt

    def test_model_forwarded(self) -> None:
        """create_coach translates ModelConfig and passes model to create_agent."""
        fake_model = MagicMock(name="fake_model")
        config = _make_model_config(provider="local", model="test-model")
        with (
            patch("agents.coach.create_agent") as mock_ca,
            patch("agents.coach.create_model", return_value=fake_model),
            patch("agents.coach.FilesystemBackend"),
        ):
            _call_create_coach(mock_ca, model_config=config)
        _, kwargs = mock_ca.call_args
        assert "model" in kwargs
        assert kwargs["model"] is fake_model


# ---------------------------------------------------------------------------
# Module-level import assertions
# ---------------------------------------------------------------------------


class TestCoachModuleLevelImports:
    """Coach module must NOT import create_deep_agent."""

    def test_coach_does_not_import_create_deep_agent(self) -> None:
        """agents.coach must not have create_deep_agent in its namespace."""
        sys.modules.pop("agents.coach", None)
        import agents.coach as coach_module

        assert not hasattr(coach_module, "create_deep_agent"), (
            "agents.coach must NOT import create_deep_agent — "
            "the Coach bypasses it to avoid FilesystemMiddleware"
        )

    def test_coach_imports_create_agent(self) -> None:
        """agents.coach imports create_agent from langchain.agents."""
        sys.modules.pop("agents.coach", None)
        import agents.coach as coach_module

        assert hasattr(coach_module, "create_agent"), (
            "agents.coach must import create_agent — "
            "the Coach uses the lower-level API"
        )


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


class TestCoachValidation:
    """Empty system prompt raises ValueError."""

    def test_empty_system_prompt_raises(self) -> None:
        """create_coach raises ValueError when system_prompt is empty."""
        with pytest.raises(ValueError, match="system_prompt"):
            from agents.coach import create_coach

            create_coach(
                model_config=_make_model_config(),
                system_prompt="",
                memory=["./AGENTS.md"],
            )

    def test_whitespace_only_system_prompt_raises(self) -> None:
        """create_coach raises ValueError when system_prompt is whitespace-only."""
        with pytest.raises(ValueError, match="system_prompt"):
            from agents.coach import create_coach

            create_coach(
                model_config=_make_model_config(),
                system_prompt="   \t\n  ",
                memory=["./AGENTS.md"],
            )


# ---------------------------------------------------------------------------
# Structured outputs (TASK-LR1-001, TASK-LR1-012)
# ---------------------------------------------------------------------------


class TestCoachStructuredOutputs:
    """Coach passes structured_outputs schema via extra_body for local (vLLM) provider.

    vLLM v0.12+ uses ``structured_outputs: {"json": schema}`` (the old
    ``guided_json`` key was removed in v0.12.0).  The schema must go through
    ``extra_body`` (not ``model_kwargs``) so the OpenAI SDK forwards it
    in the HTTP request body.
    """

    def test_structured_outputs_passed_via_extra_body_for_local_provider(self) -> None:
        """create_coach passes structured_outputs via extra_body for local provider."""
        with (
            patch("agents.coach.create_model") as mock_cm,
            patch("agents.coach.create_agent") as mock_ca,
            patch("agents.coach.FilesystemBackend"),
        ):
            mock_cm.return_value = MagicMock()
            config = _make_model_config(provider="local")
            _call_create_coach(mock_ca, model_config=config)

        _, cm_kwargs = mock_cm.call_args
        extra_body = cm_kwargs.get("extra_body")
        assert extra_body is not None, "extra_body should be passed for local provider"
        assert "structured_outputs" in extra_body
        assert "json" in extra_body["structured_outputs"]

    def test_no_deprecated_guided_json_key(self) -> None:
        """extra_body must NOT contain the deprecated guided_json key (removed in vLLM v0.12)."""
        with (
            patch("agents.coach.create_model") as mock_cm,
            patch("agents.coach.create_agent") as mock_ca,
            patch("agents.coach.FilesystemBackend"),
        ):
            mock_cm.return_value = MagicMock()
            config = _make_model_config(provider="local")
            _call_create_coach(mock_ca, model_config=config)

        _, cm_kwargs = mock_cm.call_args
        extra_body = cm_kwargs.get("extra_body", {})
        assert "guided_json" not in extra_body, (
            "guided_json was removed in vLLM v0.12.0 — "
            "use structured_outputs.json instead (TASK-LR1-012)"
        )

    def test_not_passed_via_model_kwargs(self) -> None:
        """create_coach must NOT pass schema via model_kwargs (causes SDK crash)."""
        with (
            patch("agents.coach.create_model") as mock_cm,
            patch("agents.coach.create_agent") as mock_ca,
            patch("agents.coach.FilesystemBackend"),
        ):
            mock_cm.return_value = MagicMock()
            config = _make_model_config(provider="local")
            _call_create_coach(mock_ca, model_config=config)

        _, cm_kwargs = mock_cm.call_args
        model_kwargs = cm_kwargs.get("model_kwargs")
        assert model_kwargs is None, (
            "structured_outputs must use extra_body, not model_kwargs — "
            "model_kwargs merges at top level of OpenAI SDK create() "
            "which rejects non-standard params (TASK-LR1-012)"
        )

    def test_schema_matches_coach_verdict(self) -> None:
        """structured_outputs JSON schema matches CoachVerdict.model_json_schema()."""
        from config.coach_verdict import CoachVerdict

        with (
            patch("agents.coach.create_model") as mock_cm,
            patch("agents.coach.create_agent") as mock_ca,
            patch("agents.coach.FilesystemBackend"),
        ):
            mock_cm.return_value = MagicMock()
            config = _make_model_config(provider="local")
            _call_create_coach(mock_ca, model_config=config)

        _, cm_kwargs = mock_cm.call_args
        actual_schema = cm_kwargs["extra_body"]["structured_outputs"]["json"]
        expected_schema = CoachVerdict.model_json_schema()
        assert actual_schema == expected_schema

    def test_extra_body_not_passed_for_anthropic_provider(self) -> None:
        """create_coach does not pass extra_body for non-local providers."""
        with (
            patch("agents.coach.create_model") as mock_cm,
            patch("agents.coach.create_agent") as mock_ca,
            patch("agents.coach.FilesystemBackend"),
        ):
            mock_cm.return_value = MagicMock()
            config = _make_model_config(
                provider="anthropic",
                model="claude-sonnet-4-20250514",
                endpoint="",
            )
            _call_create_coach(mock_ca, model_config=config)

        _, cm_kwargs = mock_cm.call_args
        extra_body = cm_kwargs.get("extra_body")
        assert extra_body is None, "extra_body should be None for non-local provider"

    def test_guided_json_schema_has_required_fields(self) -> None:
        """guided_json schema contains all CoachVerdict fields."""
        from config.coach_verdict import CoachVerdict

        schema = CoachVerdict.model_json_schema()
        expected_fields = {
            "decision", "score", "layer_correct", "type_correct",
            "criteria_met", "issues", "quality_assessment",
        }
        assert expected_fields == set(schema["properties"].keys())
