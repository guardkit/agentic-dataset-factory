"""Player agent factory -- content-generation agent with curated tools.

Creates a Player agent that generates training examples using RAG retrieval.
The Player receives **only** the tools explicitly passed (e.g. ``rag_retrieval``)
and **no** filesystem tools.

Role separation is enforced structurally:

- ``create_player`` uses ``create_agent`` (not ``create_deep_agent``) to bypass
  the unconditional ``FilesystemMiddleware`` injection in the SDK.
- ``tools`` parameter accepts only the curated tool list.
- No ``FilesystemMiddleware`` is included in the middleware stack.
- ``MemoryMiddleware`` still loads AGENTS.md via ``FilesystemBackend``.

References:
    - ``docs/design/contracts/API-generation.md``
    - TASK-AF-003 acceptance criteria
    - TASK-TRF-016 (bypass create_deep_agent to fix tool leakage)
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from deepagents.backends import FilesystemBackend
from deepagents.middleware import MemoryMiddleware
from deepagents.middleware.patch_tool_calls import PatchToolCallsMiddleware
from langchain.agents import create_agent
from langchain_anthropic.middleware import AnthropicPromptCachingMiddleware

from agents.model_factory import create_model

if TYPE_CHECKING:
    from langgraph.graph.state import CompiledStateGraph

    from config.models import ModelConfig

logger = logging.getLogger(__name__)


def create_player(
    model_config: ModelConfig,
    tools: list,
    system_prompt: str,
    memory: list[str],
    timeout: int | None = None,
) -> CompiledStateGraph:
    """Create a Player agent via ``create_agent()`` with a curated middleware stack.

    Uses ``create_agent`` (the lower-level LangChain API) instead of
    ``create_deep_agent`` to avoid the unconditional ``FilesystemMiddleware``
    injection that leaks 8 filesystem tools into the agent.

    The Player generates content using only the explicitly provided tools
    (expected: ``[rag_retrieval]``).  Memory injection (AGENTS.md) is handled
    by ``MemoryMiddleware`` backed by ``FilesystemBackend``, which provides
    file access for memory loading without adding tools to the agent.

    Args:
        model_config: Provider, model ID, endpoint, temperature from
            agent-config.yaml.
        tools: Tool list for the Player (expected: [rag_retrieval]).
        system_prompt: Base player prompt combined with GOAL.md Generation
            Guidelines.  Must not be empty or whitespace-only.
        memory: Memory file paths (expected: ["./AGENTS.md"]).
        timeout: Optional per-call LLM timeout in seconds, forwarded
            to ``create_model()`` (TASK-D0A8-001).

    Returns:
        Configured agent (CompiledStateGraph) with curated tools only.

    Raises:
        ValueError: If ``system_prompt`` is empty or whitespace-only.
    """
    if not system_prompt or not system_prompt.strip():
        msg = "system_prompt must not be empty or whitespace-only"
        raise ValueError(msg)

    model = create_model(model_config, timeout=timeout)

    # MemoryMiddleware needs a backend to read memory files (e.g. AGENTS.md).
    # FilesystemBackend provides real file access for memory injection without
    # adding any tools to the agent.
    backend = FilesystemBackend(root_dir=".")

    middleware = [
        MemoryMiddleware(backend=backend, sources=memory),
        PatchToolCallsMiddleware(),
        AnthropicPromptCachingMiddleware(unsupported_model_behavior="ignore"),
    ]

    logger.debug(
        "Creating Player agent (tools=%s): provider=%s, model=%s, memory=%s",
        [getattr(t, "name", str(t)) for t in tools],
        model_config.provider,
        model_config.model,
        memory,
    )

    return create_agent(
        model=model,
        tools=tools,
        system_prompt=system_prompt,
        middleware=middleware,
    )


__all__ = ["create_player"]
