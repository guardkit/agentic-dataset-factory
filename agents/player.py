"""Player agent factory for adversarial cooperation.

Provides ``create_player``, the factory function that assembles a fully
configured Player agent via ``create_deep_agent``.  The Player receives
tools and an injected system prompt.  No filesystem backend is used so
the DeepAgents SDK does not inject its 8 filesystem tools.

References:
    - ``docs/design/contracts/API-generation.md``
    - TASK-AF-003 acceptance criteria
    - TASK-TRF-003 (remove filesystem backend to fix tool leakage)
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from deepagents import create_deep_agent

from agents.model_factory import create_model
from config.models import ModelConfig

if TYPE_CHECKING:
    from langgraph.graph.state import CompiledStateGraph


def create_player(
    model_config: ModelConfig,
    tools: list,
    system_prompt: str,
    memory: list[str],
) -> CompiledStateGraph:
    """Create a configured Player agent instance via create_deep_agent.

    Translates ``model_config`` to a concrete model identifier, validates
    the system prompt, and delegates to ``create_deep_agent`` with the
    provided tools and memory.  No filesystem backend is used so the
    SDK does not inject its 8 filesystem tools (~3 000 tokens saved).

    Args:
        model_config: Provider, model ID, endpoint, temperature from
            agent-config.yaml.
        tools: Tool list for the Player (expected: [rag_retrieval, write_output]).
        system_prompt: Base player prompt combined with GOAL.md Generation
            Guidelines.  Must not be empty or whitespace-only.
        memory: Memory file paths (expected: ["./AGENTS.md"]).

    Returns:
        Configured DeepAgent (CompiledStateGraph) without filesystem backend.

    Raises:
        ValueError: If ``system_prompt`` is empty or whitespace-only.
    """
    if not system_prompt or not system_prompt.strip():
        msg = "system_prompt must not be empty or whitespace-only"
        raise ValueError(msg)

    model = create_model(model_config)

    return create_deep_agent(
        model=model,
        tools=tools,
        system_prompt=system_prompt,
        memory=memory,
        backend=None,
    )
