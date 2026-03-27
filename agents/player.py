"""Player agent factory for adversarial cooperation.

Provides ``create_player``, the factory function that assembles a fully
configured Player agent via ``create_deep_agent``.  The Player receives
tools, an injected system prompt, and a ``FilesystemBackend`` for file
access (the original exemplar design).

References:
    - ``docs/design/contracts/API-generation.md``
    - TASK-AF-003 acceptance criteria
    - TASK-TRF-012 (restore FilesystemBackend for Player)
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from deepagents import create_deep_agent
from deepagents.backends import FilesystemBackend

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
    provided tools, memory, and a ``FilesystemBackend``.

    The Player intentionally receives filesystem tools via the SDK's
    ``FilesystemMiddleware`` (injected when a backend is provided).
    These are acceptable for the Player role and restore the original
    exemplar design.

    Args:
        model_config: Provider, model ID, endpoint, temperature from
            agent-config.yaml.
        tools: Tool list for the Player (expected: [rag_retrieval]).
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

    return create_deep_agent(
        model=model,
        tools=tools,
        system_prompt=system_prompt,
        memory=memory,
        backend=FilesystemBackend(root_dir="."),
    )
