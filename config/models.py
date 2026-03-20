"""Pydantic models for agent configuration.

Provides ``ModelConfig``, the foundational data model used by both Player and
Coach agent factories.  Validates provider enum, model identifier, endpoint
URL (required for local provider), and temperature range.

References:
    - ``docs/design/models/DM-agent-config.md``
    - ``docs/design/contracts/API-generation.md``
"""

from __future__ import annotations

from typing import Literal
from urllib.parse import urlparse

from pydantic import BaseModel, Field, model_validator


class ModelConfig(BaseModel):
    """Configuration for a single LLM agent (Player or Coach).

    Attributes:
        provider: LLM provider — ``"local"``, ``"anthropic"``, or ``"openai"``.
        model: Model identifier string (e.g. ``"nemotron-3-super-120b"``).
        endpoint: API endpoint URL.  Required and must be a valid URL when
            ``provider == "local"``.  Defaults to ``""`` (cloud providers
            use their default API endpoints).
        temperature: Sampling temperature, 0.0-2.0 inclusive.  Defaults to 0.7.
    """

    provider: Literal["local", "anthropic", "openai"]
    model: str = Field(min_length=1, description="Model identifier; must not be empty.")
    endpoint: str = Field(
        default="",
        description=(
            "API endpoint URL. Required when provider is 'local'; "
            "cloud providers use their default endpoint when empty."
        ),
    )
    temperature: float = Field(
        default=0.7,
        ge=0.0,
        le=2.0,
        description="Sampling temperature (0.0-2.0 inclusive).",
    )

    @model_validator(mode="after")
    def validate_local_endpoint(self) -> ModelConfig:
        """Ensure ``endpoint`` is present and a valid URL when provider is ``local``.

        Raises:
            ValueError: If provider is ``"local"`` and endpoint is empty or
                not a valid HTTP(S) URL.
        """
        if self.provider != "local":
            return self

        if not self.endpoint:
            raise ValueError(
                "endpoint is required when provider is 'local'; "
                "provide a valid HTTP(S) URL (e.g. 'http://localhost:8000/v1')"
            )

        parsed = urlparse(self.endpoint)
        if parsed.scheme not in ("http", "https") or not parsed.netloc:
            raise ValueError(
                f"endpoint must be a valid HTTP(S) URL when provider is 'local', "
                f"got '{self.endpoint}'"
            )

        return self


__all__ = ["ModelConfig"]
