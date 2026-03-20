"""Tests for config.models.ModelConfig Pydantic model.

Covers all acceptance criteria for TASK-AF-001 and BDD scenarios from
features/agent-factories/agent-factories.feature.

Extended by TASK-AF-007 with comprehensive BDD boundary, negative, and
edge-case scenarios.
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


# ===========================================================================
# TASK-AF-007: BDD Boundary Conditions
# From features/agent-factories/agent-factories.feature @boundary
# ===========================================================================


class TestBDDBoundaryTemperature:
    """BDD @boundary scenarios for temperature field validation."""

    def test_temperature_at_minimum_0_0_accepted(self) -> None:
        """Scenario: Creating an agent with temperature 0.0."""
        cfg = ModelConfig(provider="anthropic", model="test-model", temperature=0.0)
        assert cfg.temperature == 0.0

    def test_temperature_at_maximum_2_0_accepted(self) -> None:
        """Scenario: Creating an agent with temperature 2.0."""
        cfg = ModelConfig(provider="openai", model="gpt-4", temperature=2.0)
        assert cfg.temperature == 2.0

    def test_temperature_just_above_maximum_2_1_rejected(self) -> None:
        """Scenario: Creating an agent with temperature above 2.0."""
        with pytest.raises(ValidationError):
            ModelConfig(provider="anthropic", model="test-model", temperature=2.1)

    def test_temperature_just_below_minimum_negative_0_1_rejected(self) -> None:
        """Scenario: Creating an agent with negative temperature."""
        with pytest.raises(ValidationError):
            ModelConfig(provider="anthropic", model="test-model", temperature=-0.1)

    @pytest.mark.parametrize(
        "temp",
        [0.0, 0.1, 0.5, 0.7, 1.0, 1.5, 1.99, 2.0],
        ids=[
            "min-0.0",
            "near-min-0.1",
            "mid-0.5",
            "default-0.7",
            "mid-1.0",
            "mid-1.5",
            "near-max-1.99",
            "max-2.0",
        ],
    )
    def test_temperature_within_range_accepted(self, temp: float) -> None:
        """All values in [0.0, 2.0] are accepted."""
        cfg = ModelConfig(provider="anthropic", model="test-model", temperature=temp)
        assert cfg.temperature == temp

    @pytest.mark.parametrize(
        "temp",
        [-1.0, -0.1, -0.001, 2.001, 2.1, 3.0, 100.0],
        ids=[
            "far-below-neg1",
            "just-below-neg0.1",
            "tiny-below-neg0.001",
            "tiny-above-2.001",
            "just-above-2.1",
            "far-above-3.0",
            "extreme-100",
        ],
    )
    def test_temperature_outside_range_rejected(self, temp: float) -> None:
        """All values outside [0.0, 2.0] are rejected."""
        with pytest.raises(ValidationError):
            ModelConfig(provider="anthropic", model="test-model", temperature=temp)


# ===========================================================================
# TASK-AF-007: BDD Negative Cases
# From features/agent-factories/agent-factories.feature @negative
# ===========================================================================


class TestBDDNegativeProvider:
    """BDD @negative scenarios for provider validation."""

    def test_missing_provider_raises_validation_error(self) -> None:
        """Scenario: ModelConfig with missing provider."""
        with pytest.raises(ValidationError):
            ModelConfig(model="test-model")  # type: ignore[call-arg]

    @pytest.mark.parametrize(
        "provider",
        ["azure", "huggingface", "google"],
    )
    def test_invalid_provider_raises_validation_error(self, provider: str) -> None:
        """Scenario Outline: ModelConfig with invalid provider."""
        with pytest.raises(ValidationError):
            ModelConfig(provider=provider, model="test-model")

    def test_provider_none_raises_validation_error(self) -> None:
        """Provider set to None should be rejected."""
        with pytest.raises(ValidationError):
            ModelConfig(provider=None, model="test-model")  # type: ignore[arg-type]

    def test_provider_empty_string_raises_validation_error(self) -> None:
        """Provider set to empty string should be rejected."""
        with pytest.raises(ValidationError):
            ModelConfig(provider="", model="test-model")  # type: ignore[arg-type]

    def test_provider_integer_raises_validation_error(self) -> None:
        """Provider set to an integer should be rejected."""
        with pytest.raises(ValidationError):
            ModelConfig(provider=42, model="test-model")  # type: ignore[arg-type]


class TestBDDNegativeEndpoint:
    """BDD @negative scenarios for local provider endpoint validation."""

    def test_local_without_endpoint_raises_validation_error(self) -> None:
        """Scenario: Local provider without endpoint."""
        with pytest.raises(ValidationError, match="endpoint"):
            ModelConfig(provider="local", model="test-model")

    def test_local_with_empty_endpoint_raises_validation_error(self) -> None:
        """Local provider with empty endpoint string."""
        with pytest.raises(ValidationError, match="endpoint"):
            ModelConfig(provider="local", model="test-model", endpoint="")

    def test_local_with_malformed_url_raises_validation_error(self) -> None:
        """Scenario: Local provider with malformed endpoint URL."""
        with pytest.raises(ValidationError, match="endpoint"):
            ModelConfig(
                provider="local", model="test-model", endpoint="not-a-valid-url"
            )

    @pytest.mark.parametrize(
        "endpoint",
        [
            "ftp://localhost:8000/v1",
            "ws://localhost:8000",
            "just-some-text",
            "://missing-scheme",
            "http://",
        ],
        ids=[
            "ftp-scheme",
            "ws-scheme",
            "no-scheme",
            "missing-scheme",
            "http-no-host",
        ],
    )
    def test_local_with_non_http_or_malformed_endpoint_rejected(
        self, endpoint: str
    ) -> None:
        """Malformed and non-HTTP(S) endpoints are rejected for local provider."""
        with pytest.raises(ValidationError):
            ModelConfig(provider="local", model="test-model", endpoint=endpoint)


class TestBDDNegativeModel:
    """BDD @negative scenarios for model field validation."""

    def test_missing_model_raises_validation_error(self) -> None:
        """Scenario: ModelConfig with missing model identifier."""
        with pytest.raises(ValidationError):
            ModelConfig(provider="anthropic")  # type: ignore[call-arg]

    def test_empty_model_raises_validation_error(self) -> None:
        """Empty model string should be rejected (min_length=1)."""
        with pytest.raises(ValidationError):
            ModelConfig(provider="anthropic", model="")

    def test_model_none_raises_validation_error(self) -> None:
        """Model set to None should be rejected."""
        with pytest.raises(ValidationError):
            ModelConfig(provider="anthropic", model=None)  # type: ignore[arg-type]


# ===========================================================================
# TASK-AF-007: BDD Edge Cases
# From features/agent-factories/agent-factories.feature @edge-case
# ===========================================================================


class TestBDDEdgeCaseDefaults:
    """BDD @edge-case scenarios for default values."""

    def test_default_temperature_applied_when_not_specified(self) -> None:
        """Scenario: Default temperatures are applied when not specified."""
        cfg = ModelConfig(provider="anthropic", model="test-model")
        assert cfg.temperature == 0.7

    def test_default_endpoint_is_empty_string(self) -> None:
        """Default endpoint should be empty for cloud providers."""
        cfg = ModelConfig(provider="openai", model="gpt-4")
        assert cfg.endpoint == ""


class TestBDDEdgeCaseCloudProviders:
    """BDD @edge-case scenarios for cloud provider endpoint handling."""

    def test_anthropic_without_endpoint_accepted(self) -> None:
        """Scenario: Anthropic provider uses default endpoint."""
        cfg = ModelConfig(provider="anthropic", model="claude-3-opus")
        assert cfg.provider == "anthropic"
        assert cfg.endpoint == ""

    def test_openai_without_endpoint_accepted(self) -> None:
        """Scenario: OpenAI provider uses default endpoint."""
        cfg = ModelConfig(provider="openai", model="gpt-4")
        assert cfg.provider == "openai"
        assert cfg.endpoint == ""

    def test_anthropic_with_custom_endpoint_accepted(self) -> None:
        """Cloud providers can optionally supply a custom endpoint."""
        cfg = ModelConfig(
            provider="anthropic",
            model="claude-3-opus",
            endpoint="https://custom.anthropic.api/v1",
        )
        assert cfg.endpoint == "https://custom.anthropic.api/v1"

    def test_openai_with_custom_endpoint_accepted(self) -> None:
        """Cloud providers can optionally supply a custom endpoint."""
        cfg = ModelConfig(
            provider="openai",
            model="gpt-4",
            endpoint="https://custom.openai.api/v1",
        )
        assert cfg.endpoint == "https://custom.openai.api/v1"


class TestBDDEdgeCaseFullConfig:
    """BDD @key-example scenario: Full valid config with all fields."""

    def test_full_valid_config_accepted(self) -> None:
        """Scenario: Agent factory passes model configuration to create_deep_agent."""
        cfg = ModelConfig(
            provider="local",
            model="nemotron-3-super-120b",
            endpoint="http://localhost:8000/v1",
            temperature=0.7,
        )
        assert cfg.provider == "local"
        assert cfg.model == "nemotron-3-super-120b"
        assert cfg.endpoint == "http://localhost:8000/v1"
        assert cfg.temperature == 0.7

    def test_local_provider_with_https_endpoint_accepted(self) -> None:
        """Scenario: Provider 'local' with valid HTTPS endpoint."""
        cfg = ModelConfig(
            provider="local",
            model="test-model",
            endpoint="https://api.example.com/v1",
        )
        assert cfg.provider == "local"
        assert cfg.endpoint == "https://api.example.com/v1"


class TestBDDEdgeCaseHeterogeneousConfig:
    """BDD @edge-case: Player and Coach can use different providers/temperatures."""

    def test_different_providers_accepted(self) -> None:
        """Scenario: Player and Coach configured with different providers."""
        player_cfg = ModelConfig(
            provider="local",
            model="nemotron-3-super-120b",
            endpoint="http://localhost:8000/v1",
            temperature=0.7,
        )
        coach_cfg = ModelConfig(
            provider="anthropic",
            model="claude-3-opus",
            temperature=0.3,
        )
        assert player_cfg.provider == "local"
        assert coach_cfg.provider == "anthropic"

    def test_different_temperatures_accepted(self) -> None:
        """Scenario: Player and Coach with different temperatures."""
        player_cfg = ModelConfig(
            provider="anthropic", model="test-model", temperature=0.7
        )
        coach_cfg = ModelConfig(
            provider="anthropic", model="test-model", temperature=0.3
        )
        assert player_cfg.temperature == 0.7
        assert coach_cfg.temperature == 0.3
