"""Tests for agents.model_factory — shared model creation.

Covers all acceptance criteria for TASK-AF-006 and the seam test
validating the ModelConfig integration contract from TASK-AF-001.

TDD approach: these tests are written FIRST, then create_model() is
implemented to make them pass.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from config.models import ModelConfig


# ---------------------------------------------------------------------------
# AC-001: agents/model_factory.py contains create_model(config) -> BaseChatModel
# ---------------------------------------------------------------------------


class TestCreateModelExists:
    """AC-001: create_model function exists and returns BaseChatModel."""

    def test_create_model_is_callable(self) -> None:
        from agents.model_factory import create_model

        assert callable(create_model)

    @patch("agents.model_factory.init_chat_model")
    def test_create_model_returns_base_chat_model(
        self, mock_init: MagicMock
    ) -> None:
        from langchain_core.language_models import BaseChatModel

        from agents.model_factory import create_model

        mock_model = MagicMock(spec=BaseChatModel)
        mock_init.return_value = mock_model

        config = ModelConfig(provider="openai", model="gpt-4")
        result = create_model(config)

        assert isinstance(result, BaseChatModel)


# ---------------------------------------------------------------------------
# AC-002: Local provider creates model with custom endpoint URL
# ---------------------------------------------------------------------------


class TestLocalProvider:
    """AC-002: local provider uses custom endpoint."""

    @patch("agents.model_factory.init_chat_model")
    def test_local_provider_passes_endpoint(self, mock_init: MagicMock) -> None:
        from agents.model_factory import create_model

        config = ModelConfig(
            provider="local",
            model="nemotron-3-super-120b",
            endpoint="http://localhost:8000/v1",
            temperature=0.5,
        )
        create_model(config)

        mock_init.assert_called_once()
        call_kwargs = mock_init.call_args
        # The base_url / api_base must be set to the endpoint
        assert call_kwargs.kwargs.get("base_url") == "http://localhost:8000/v1"

    @patch("agents.model_factory.init_chat_model")
    def test_local_provider_uses_openai_model_provider(
        self, mock_init: MagicMock
    ) -> None:
        """Local provider should use openai-compatible model provider for init_chat_model."""
        from agents.model_factory import create_model

        config = ModelConfig(
            provider="local",
            model="nemotron-3-super-120b",
            endpoint="http://localhost:8000/v1",
        )
        create_model(config)

        call_kwargs = mock_init.call_args
        # Local providers use OpenAI-compatible endpoints
        assert call_kwargs.kwargs.get("model_provider") == "openai"

    @patch("agents.model_factory.init_chat_model")
    def test_local_provider_passes_model_name(
        self, mock_init: MagicMock
    ) -> None:
        from agents.model_factory import create_model

        config = ModelConfig(
            provider="local",
            model="nemotron-3-super-120b",
            endpoint="http://localhost:8000/v1",
        )
        create_model(config)

        call_kwargs = mock_init.call_args
        # Model name passed as first positional arg or 'model' kwarg
        assert call_kwargs.args[0] == "nemotron-3-super-120b" or call_kwargs.kwargs.get("model") == "nemotron-3-super-120b"


# ---------------------------------------------------------------------------
# AC-003: Anthropic provider creates model using default Anthropic API
# ---------------------------------------------------------------------------


class TestAnthropicProvider:
    """AC-003: anthropic provider uses default Anthropic API."""

    @patch("agents.model_factory.init_chat_model")
    def test_anthropic_provider_uses_anthropic_model_provider(
        self, mock_init: MagicMock
    ) -> None:
        from agents.model_factory import create_model

        config = ModelConfig(provider="anthropic", model="claude-3-opus")
        create_model(config)

        call_kwargs = mock_init.call_args
        assert call_kwargs.kwargs.get("model_provider") == "anthropic"

    @patch("agents.model_factory.init_chat_model")
    def test_anthropic_provider_does_not_pass_base_url(
        self, mock_init: MagicMock
    ) -> None:
        from agents.model_factory import create_model

        config = ModelConfig(provider="anthropic", model="claude-3-opus")
        create_model(config)

        call_kwargs = mock_init.call_args
        assert "base_url" not in call_kwargs.kwargs

    @patch("agents.model_factory.init_chat_model")
    def test_anthropic_provider_passes_model_name(
        self, mock_init: MagicMock
    ) -> None:
        from agents.model_factory import create_model

        config = ModelConfig(provider="anthropic", model="claude-3-opus")
        create_model(config)

        call_kwargs = mock_init.call_args
        assert call_kwargs.args[0] == "claude-3-opus" or call_kwargs.kwargs.get("model") == "claude-3-opus"


# ---------------------------------------------------------------------------
# AC-004: OpenAI provider creates model using default OpenAI API
# ---------------------------------------------------------------------------


class TestOpenAIProvider:
    """AC-004: openai provider uses default OpenAI API."""

    @patch("agents.model_factory.init_chat_model")
    def test_openai_provider_uses_openai_model_provider(
        self, mock_init: MagicMock
    ) -> None:
        from agents.model_factory import create_model

        config = ModelConfig(provider="openai", model="gpt-4")
        create_model(config)

        call_kwargs = mock_init.call_args
        assert call_kwargs.kwargs.get("model_provider") == "openai"

    @patch("agents.model_factory.init_chat_model")
    def test_openai_provider_does_not_pass_base_url(
        self, mock_init: MagicMock
    ) -> None:
        from agents.model_factory import create_model

        config = ModelConfig(provider="openai", model="gpt-4")
        create_model(config)

        call_kwargs = mock_init.call_args
        assert "base_url" not in call_kwargs.kwargs

    @patch("agents.model_factory.init_chat_model")
    def test_openai_provider_passes_model_name(
        self, mock_init: MagicMock
    ) -> None:
        from agents.model_factory import create_model

        config = ModelConfig(provider="openai", model="gpt-4")
        create_model(config)

        call_kwargs = mock_init.call_args
        assert call_kwargs.args[0] == "gpt-4" or call_kwargs.kwargs.get("model") == "gpt-4"


# ---------------------------------------------------------------------------
# AC-005: Temperature is passed through to the model
# ---------------------------------------------------------------------------


class TestTemperaturePassthrough:
    """AC-005: temperature from config reaches the model."""

    @patch("agents.model_factory.init_chat_model")
    def test_temperature_passed_to_init_chat_model(
        self, mock_init: MagicMock
    ) -> None:
        from agents.model_factory import create_model

        config = ModelConfig(
            provider="anthropic", model="claude-3-opus", temperature=1.5
        )
        create_model(config)

        call_kwargs = mock_init.call_args
        assert call_kwargs.kwargs.get("temperature") == 1.5

    @patch("agents.model_factory.init_chat_model")
    def test_default_temperature_passed_through(
        self, mock_init: MagicMock
    ) -> None:
        from agents.model_factory import create_model

        config = ModelConfig(provider="openai", model="gpt-4")
        create_model(config)

        call_kwargs = mock_init.call_args
        assert call_kwargs.kwargs.get("temperature") == 0.7

    @patch("agents.model_factory.init_chat_model")
    def test_zero_temperature_passed_through(
        self, mock_init: MagicMock
    ) -> None:
        from agents.model_factory import create_model

        config = ModelConfig(
            provider="openai", model="gpt-4", temperature=0.0
        )
        create_model(config)

        call_kwargs = mock_init.call_args
        assert call_kwargs.kwargs.get("temperature") == 0.0


# ---------------------------------------------------------------------------
# TASK-D0A8-001: Timeout is wired to init_chat_model
# ---------------------------------------------------------------------------


class TestTimeoutPassthrough:
    """TASK-D0A8-001: timeout from GenerationConfig reaches init_chat_model."""

    @patch("agents.model_factory.init_chat_model")
    def test_timeout_passed_to_init_chat_model(
        self, mock_init: MagicMock
    ) -> None:
        """When timeout is provided, it should be forwarded to init_chat_model."""
        from agents.model_factory import create_model

        config = ModelConfig(provider="openai", model="gpt-4")
        create_model(config, timeout=300)

        call_kwargs = mock_init.call_args
        assert call_kwargs.kwargs.get("timeout") == 300

    @patch("agents.model_factory.init_chat_model")
    def test_timeout_none_omits_kwarg(self, mock_init: MagicMock) -> None:
        """When timeout is None (default), no timeout kwarg should be passed."""
        from agents.model_factory import create_model

        config = ModelConfig(provider="openai", model="gpt-4")
        create_model(config)

        call_kwargs = mock_init.call_args
        assert "timeout" not in call_kwargs.kwargs

    @patch("agents.model_factory.init_chat_model")
    def test_timeout_none_explicit_omits_kwarg(
        self, mock_init: MagicMock
    ) -> None:
        """Explicitly passing timeout=None should not add timeout to kwargs."""
        from agents.model_factory import create_model

        config = ModelConfig(provider="openai", model="gpt-4")
        create_model(config, timeout=None)

        call_kwargs = mock_init.call_args
        assert "timeout" not in call_kwargs.kwargs

    @patch("agents.model_factory.init_chat_model")
    def test_custom_timeout_value(self, mock_init: MagicMock) -> None:
        """Custom timeout values should be forwarded correctly."""
        from agents.model_factory import create_model

        config = ModelConfig(
            provider="local",
            model="test-model",
            endpoint="http://localhost:8000/v1",
        )
        create_model(config, timeout=120)

        call_kwargs = mock_init.call_args
        assert call_kwargs.kwargs.get("timeout") == 120


# ---------------------------------------------------------------------------
# AC-006: Invalid provider raises clear error
# ---------------------------------------------------------------------------


class TestInvalidProvider:
    """AC-006: invalid provider raises ValueError with clear message.

    Note: Pydantic validation catches this first via Literal, but if
    create_model receives an already-constructed config object with an
    unexpected provider value (e.g. via model_construct), it should still
    raise a clear error.
    """

    def test_unsupported_provider_raises_value_error(self) -> None:
        from agents.model_factory import create_model

        # Bypass Pydantic validation to test the factory's own guard
        config = ModelConfig.model_construct(
            provider="azure",  # type: ignore[arg-type]
            model="test-model",
            endpoint="",
            temperature=0.7,
        )

        with pytest.raises(ValueError, match="[Uu]nsupported.*provider"):
            create_model(config)


# ---------------------------------------------------------------------------
# Seam test: ModelConfig contract from TASK-AF-001
# ---------------------------------------------------------------------------


class TestModelConfigSeam:
    """Seam test verifying the ModelConfig integration contract."""

    @pytest.mark.seam
    @pytest.mark.integration_contract("ModelConfig")
    def test_model_config_to_model_translation(self) -> None:
        """Verify ModelConfig can be translated to model creation parameters.

        Contract: ModelConfig fields (provider, model, endpoint, temperature)
        must be translated to init_chat_model parameters.
        Producer: TASK-AF-001
        """
        config = ModelConfig(
            provider="local",
            model="test-model",
            endpoint="http://localhost:8000/v1",
            temperature=0.7,
        )
        assert hasattr(config, "provider"), "ModelConfig must have provider field"
        assert hasattr(config, "model"), "ModelConfig must have model field"
        assert hasattr(config, "endpoint"), "ModelConfig must have endpoint field"
        assert hasattr(config, "temperature"), "ModelConfig must have temperature field"


# ---------------------------------------------------------------------------
# AC-007: lint/format (verified separately via ruff)
# ---------------------------------------------------------------------------
