"""Player agent factory for adversarial cooperation.

Provides ``create_player``, the factory function that assembles a fully
configured Player agent via ``create_deep_agent``.  The Player receives
tools, a FilesystemBackend for file I/O, and an injected system prompt.

References:
    - ``docs/design/contracts/API-generation.md``
    - TASK-AF-003 acceptance criteria
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from deepagents import create_deep_agent
from deepagents.backends import FilesystemBackend

from config.models import ModelConfig

if TYPE_CHECKING:
    from langgraph.graph.state import CompiledStateGraph


def create_model(model_config: ModelConfig) -> str:
    """Translate a ModelConfig into a model identifier for create_deep_agent.

    For cloud providers (anthropic, openai), returns ``"provider:model"`` format.
    For local providers, returns ``"provider:model"`` with the endpoint available
    on the original ModelConfig for downstream configuration.

    Args:
        model_config: Validated ModelConfig with provider, model, endpoint,
            and temperature fields.

    Returns:
        A model identifier string accepted by ``create_deep_agent``.

    Raises:
        ValueError: If model_config has an unsupported provider.
    """
    if model_config.provider not in ("local", "anthropic", "openai"):
        msg = (
            f"Unsupported provider '{model_config.provider}'; "
            f"expected one of: local, anthropic, openai"
        )
        raise ValueError(msg)

    return f"{model_config.provider}:{model_config.model}"


def create_player(
    model_config: ModelConfig,
    tools: list,
    system_prompt: str,
    memory: list[str],
) -> CompiledStateGraph:
    """Create a configured Player agent instance via create_deep_agent.

    Translates ``model_config`` to a concrete model identifier, validates
    the system prompt, and delegates to ``create_deep_agent`` with the
    provided tools, memory, and a ``FilesystemBackend``.

    Args:
        model_config: Provider, model ID, endpoint, temperature from
            agent-config.yaml.
        tools: Tool list for the Player (expected: [rag_retrieval, write_output]).
        system_prompt: Base player prompt combined with GOAL.md Generation
            Guidelines.  Must not be empty or whitespace-only.
        memory: Memory file paths (expected: ["./AGENTS.md"]).

    Returns:
        Configured DeepAgent (CompiledStateGraph) with FilesystemBackend.

    Raises:
        ValueError: If ``system_prompt`` is empty or whitespace-only.
    """
    if not system_prompt or not system_prompt.strip():
        msg = "system_prompt must not be empty or whitespace-only"
        raise ValueError(msg)

    model = create_model(model_config)
    backend = FilesystemBackend(root_dir=".")

    return create_deep_agent(
        model=model,
        tools=tools,
        system_prompt=system_prompt,
        memory=memory,
        backend=backend,
    )
