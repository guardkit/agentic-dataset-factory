"""Shared model factory for Player and Coach agents.

Translates a ``ModelConfig`` into a concrete LangChain ``BaseChatModel``
using ``init_chat_model``.  This module is the single source of model
creation logic, preventing duplication between Player and Coach factories
(DRY principle).

References:
    - ``docs/design/contracts/API-generation.md``
    - TASK-AF-006 acceptance criteria
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from langchain.chat_models import init_chat_model

if TYPE_CHECKING:
    from langchain_core.language_models import BaseChatModel

    from config.models import ModelConfig

logger = logging.getLogger(__name__)

# Mapping from ModelConfig.provider to the init_chat_model model_provider string.
_PROVIDER_MAP: dict[str, str] = {
    "local": "openai",       # Local endpoints use OpenAI-compatible API
    "anthropic": "anthropic",
    "openai": "openai",
}


def create_model(config: ModelConfig) -> BaseChatModel:
    """Create a LangChain chat model from a validated ``ModelConfig``.

    Translates provider, model name, endpoint, and temperature into the
    appropriate ``init_chat_model`` call.

    Args:
        config: A validated ``ModelConfig`` instance specifying provider,
            model identifier, optional endpoint URL, and temperature.

    Returns:
        A ``BaseChatModel`` ready for use with ``create_deep_agent``.

    Raises:
        ValueError: If ``config.provider`` is not one of the supported
            providers (``"local"``, ``"anthropic"``, ``"openai"``).
    """
    model_provider = _PROVIDER_MAP.get(config.provider)
    if model_provider is None:
        raise ValueError(
            f"Unsupported provider '{config.provider}'. "
            f"Supported providers: {sorted(_PROVIDER_MAP)}"
        )

    kwargs: dict[str, object] = {
        "model_provider": model_provider,
        "temperature": config.temperature,
        "max_tokens": config.max_tokens,
    }

    # Local providers require a custom base_url for the OpenAI-compatible endpoint.
    if config.provider == "local":
        kwargs["base_url"] = config.endpoint

    logger.debug(
        "Creating model: provider=%s, model=%s, temperature=%s",
        config.provider,
        config.model,
        config.temperature,
    )

    return init_chat_model(config.model, **kwargs)  # type: ignore[return-value]


__all__ = ["create_model"]
