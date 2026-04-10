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
from config.coach_verdict import CoachVerdict

if TYPE_CHECKING:
    from langgraph.graph.state import CompiledStateGraph

    from config.models import ModelConfig

logger = logging.getLogger(__name__)


def create_coach(
    model_config: ModelConfig,
    system_prompt: str,
    memory: list[str],
    timeout: int | None = None,
    structured_outputs: bool = True,
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
        timeout: Optional per-call LLM timeout in seconds, forwarded
            to ``create_model()`` (TASK-D0A8-001).
        structured_outputs: Whether to enable vLLM structured outputs
            (JSON schema constraint).  Defaults to ``True``.  Set to
            ``False`` to create a fallback Coach that returns free-form
            text, used when structured outputs trigger model refusals
            (TASK-CR-007).

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

    # Constrain Coach output to valid CoachVerdict JSON via vLLM structured
    # outputs (TASK-LR1-001, fix TASK-LR1-012).  Only applies to local
    # (vLLM) provider.  Uses extra_body with "structured_outputs" key —
    # the vLLM v0.12+ API (the old "guided_json" key was removed in v0.12).
    # extra_body is required (not model_kwargs) because vendor-specific
    # params must go through the OpenAI SDK's extra_body mechanism.
    extra_body = None
    if model_config.provider == "local" and structured_outputs:
        extra_body = {
            "structured_outputs": {"json": CoachVerdict.model_json_schema()},
        }
        logger.debug("Coach structured_outputs schema enabled for local provider")
    elif model_config.provider == "local" and not structured_outputs:
        logger.debug(
            "Coach structured_outputs DISABLED for local provider "
            "(fallback mode, TASK-CR-007)"
        )

    model = create_model(model_config, extra_body=extra_body, timeout=timeout)

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
