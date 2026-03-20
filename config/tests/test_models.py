"""Tests for config.models.ModelConfig Pydantic model.

Covers all acceptance criteria for TASK-AF-001 and BDD scenarios from
features/agent-factories/agent-factories.feature.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from config.models import ModelConfig


# ---------------------------------------------------------------------------
# AC-001: ModelConfig is a Pydantic BaseModel in config/models.py
# ---------------------------------------------------------------------------


class TestModelConfigIsBaseModel:
    """AC-001: ModelConfig is a Pydantic BaseModel."""

    def test_is_pydantic_base_model(self) -> None:
        from pydantic import BaseModel

        assert issubclass(ModelConfig, BaseModel)


# ---------------------------------------------------------------------------
# AC-002: provider uses Literal["local", "anthropic", "openai"]
# ---------------------------------------------------------------------------


class TestProviderValidation:
    """AC-002: provider field uses Literal enforcement."""

    @pytest.mark.parametrize("provider", ["local", "anthropic", "openai"])
    def test_valid_providers_accepted(self, provider: str) -> None:
        kwargs: dict = {"provider": provider, "model": "test-model"}
        if provider == "local":
            kwargs["endpoint"] = "http://localhost:8000/v1"
        cfg = ModelConfig(**kwargs)
        assert cfg.provider == provider

    @pytest.mark.parametrize("provider", ["azure", "huggingface", "google"])
    def test_invalid_providers_rejected(self, provider: str) -> None:
        with pytest.raises(ValidationError):
            ModelConfig(provider=provider, model="test-model")

    def test_missing_provider_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ModelConfig(model="test-model")  # type: ignore[call-arg]


# ---------------------------------------------------------------------------
# AC-003: model is a required non-empty str
# ---------------------------------------------------------------------------


class TestModelFieldValidation:
    """AC-003: model is required and non-empty."""

    def test_valid_model_accepted(self) -> None:
        cfg = ModelConfig(provider="anthropic", model="claude-3-opus")
        assert cfg.model == "claude-3-opus"

    def test_missing_model_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ModelConfig(provider="anthropic")  # type: ignore[call-arg]

    def test_empty_model_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ModelConfig(provider="anthropic", model="")


# ---------------------------------------------------------------------------
# AC-004: temperature uses Field(ge=0.0, le=2.0, default=0.7)
# ---------------------------------------------------------------------------


class TestTemperatureValidation:
    """AC-004: temperature range 0.0-2.0 inclusive, default 0.7."""

    def test_default_temperature(self) -> None:
        cfg = ModelConfig(provider="anthropic", model="test-model")
        assert cfg.temperature == 0.7

    def test_temperature_zero_accepted(self) -> None:
        cfg = ModelConfig(provider="anthropic", model="test-model", temperature=0.0)
        assert cfg.temperature == 0.0

    def test_temperature_two_accepted(self) -> None:
        cfg = ModelConfig(provider="anthropic", model="test-model", temperature=2.0)
        assert cfg.temperature == 2.0

    def test_temperature_above_two_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ModelConfig(provider="anthropic", model="test-model", temperature=2.1)

    def test_temperature_negative_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ModelConfig(provider="anthropic", model="test-model", temperature=-0.1)


# ---------------------------------------------------------------------------
# AC-005: model_validator ensures endpoint is non-empty and valid URL
#         when provider == "local"
# ---------------------------------------------------------------------------


class TestEndpointValidation:
    """AC-005: endpoint required and must be valid URL for local provider."""

    def test_local_with_valid_endpoint_accepted(self) -> None:
        cfg = ModelConfig(
            provider="local",
            model="nemotron-3-super-120b",
            endpoint="http://localhost:8000/v1",
        )
        assert cfg.endpoint == "http://localhost:8000/v1"

    def test_local_without_endpoint_rejected(self) -> None:
        with pytest.raises(ValidationError, match="endpoint"):
            ModelConfig(provider="local", model="test-model")

    def test_local_with_empty_endpoint_rejected(self) -> None:
        with pytest.raises(ValidationError, match="endpoint"):
            ModelConfig(provider="local", model="test-model", endpoint="")

    def test_local_with_malformed_endpoint_rejected(self) -> None:
        with pytest.raises(ValidationError, match="endpoint"):
            ModelConfig(
                provider="local", model="test-model", endpoint="not-a-url"
            )

    def test_local_with_https_endpoint_accepted(self) -> None:
        cfg = ModelConfig(
            provider="local",
            model="test-model",
            endpoint="https://api.example.com/v1",
        )
        assert cfg.endpoint == "https://api.example.com/v1"


# ---------------------------------------------------------------------------
# AC-006: Anthropic and OpenAI providers accept empty endpoint
# ---------------------------------------------------------------------------


class TestCloudProviderEndpoint:
    """AC-006: anthropic/openai accept empty endpoint (use defaults)."""

    def test_anthropic_without_endpoint_accepted(self) -> None:
        cfg = ModelConfig(provider="anthropic", model="claude-3-opus")
        assert cfg.endpoint == ""

    def test_openai_without_endpoint_accepted(self) -> None:
        cfg = ModelConfig(provider="openai", model="gpt-4")
        assert cfg.endpoint == ""

    def test_anthropic_with_endpoint_accepted(self) -> None:
        cfg = ModelConfig(
            provider="anthropic",
            model="claude-3-opus",
            endpoint="https://custom.anthropic.api/v1",
        )
        assert cfg.endpoint == "https://custom.anthropic.api/v1"


# ---------------------------------------------------------------------------
# AC-007: Validation errors raise ValidationError with clear messages
# ---------------------------------------------------------------------------


class TestValidationErrorMessages:
    """AC-007: ValidationError messages are clear and actionable."""

    def test_invalid_provider_message_is_clear(self) -> None:
        with pytest.raises(ValidationError) as exc_info:
            ModelConfig(provider="azure", model="test-model")
        error_text = str(exc_info.value)
        # Should mention provider context
        assert "provider" in error_text.lower() or "input" in error_text.lower()

    def test_local_missing_endpoint_message_mentions_endpoint(self) -> None:
        with pytest.raises(ValidationError) as exc_info:
            ModelConfig(provider="local", model="test-model")
        error_text = str(exc_info.value)
        assert "endpoint" in error_text.lower()

    def test_temperature_out_of_range_message_is_clear(self) -> None:
        with pytest.raises(ValidationError) as exc_info:
            ModelConfig(provider="anthropic", model="test-model", temperature=5.0)
        error_text = str(exc_info.value)
        assert "temperature" in error_text.lower() or "less than" in error_text.lower()
