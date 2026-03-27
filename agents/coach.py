"""Coach agent factory -- evaluation-only agent with no tools or file access.

Creates a Coach agent that evaluates Player-generated training examples
against quality criteria.  The Coach returns structured JSON verdicts but
**never writes files** and **never calls tools** (D5 invariant).

Role separation is enforced structurally:

- ``create_coach`` has **no** ``tools`` parameter in its signature.
- ``tools=[]`` is always passed to ``create_agent``.
- No ``FilesystemMiddleware`` is included in the middleware stack.
- Uses ``create_agent`` (not ``create_deep_agent``) to bypass the
  unconditional ``FilesystemMiddleware`` injection in the SDK.

References:
    - ``docs/design/contracts/API-generation.md`` (Coach Factory contract)
    - TASK-AF-004 acceptance criteria
    - TASK-TRF-012 (bypass create_deep_agent to fix tool leakage)
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


def create_coach(
    model_config: ModelConfig,
    system_prompt: str,
    memory: list[str],
) -> CompiledStateGraph:
    """Create a Coach agent via ``create_agent()`` with a curated middleware stack.

    Uses ``create_agent`` (the lower-level LangChain API) instead of
    ``create_deep_agent`` to avoid the unconditional ``FilesystemMiddleware``
    injection that leaks 8 filesystem tools into the agent.

    The Coach evaluates Player-generated content and returns structured JSON
    feedback.  It has **no tools** and **no filesystem backend**, enforcing
    the D5 role-separation invariant at the factory level.

    Args:
        model_config: Provider, model ID, endpoint, and temperature
            sourced from ``agent-config.yaml``.
        system_prompt: Base coach prompt combined with GOAL.md Evaluation
            Criteria.  Must be non-empty.
        memory: List of memory file paths (e.g. ``["./AGENTS.md"]``).

    Returns:
        A compiled agent graph configured for evaluation only.

    Raises:
        ValueError: If ``system_prompt`` is empty or whitespace-only.
    """
    if not system_prompt or not system_prompt.strip():
        raise ValueError(
            "system_prompt must not be empty — the Coach requires evaluation "
            "criteria and role instructions to function correctly"
        )

    model = create_model(model_config)

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
        "Creating Coach agent (no tools): provider=%s, model=%s, memory=%s",
        model_config.provider,
        model_config.model,
        memory,
    )

    return create_agent(
        model=model,
        tools=[],
        system_prompt=system_prompt,
        middleware=middleware,
    )


__all__ = ["create_coach"]
