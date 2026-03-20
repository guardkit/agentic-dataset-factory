"""Coach agent factory -- evaluation-only agent with no tools or file access.

Creates a Coach ``DeepAgent`` that evaluates Player-generated training examples
against quality criteria.  The Coach returns structured JSON verdicts but
**never writes files** and **never calls tools** (D5 invariant).

Role separation is enforced structurally:

- ``create_coach`` has **no** ``tools`` parameter in its signature.
- ``tools=[]`` is always passed to ``create_deep_agent``.
- No filesystem backend is imported or used in this module.

References:
    - ``docs/design/contracts/API-generation.md`` (Coach Factory contract)
    - TASK-AF-004 acceptance criteria
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from deepagents import create_deep_agent

from agents.model_factory import create_model

if TYPE_CHECKING:
    from deepagents.graph import CompiledStateGraph

    from config.models import ModelConfig

logger = logging.getLogger(__name__)


def create_coach(
    model_config: ModelConfig,
    system_prompt: str,
    memory: list[str],
) -> CompiledStateGraph:
    """Create a Coach agent via ``create_deep_agent()``.

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
        A compiled ``DeepAgent`` graph configured for evaluation only.

    Raises:
        ValueError: If ``system_prompt`` is empty or whitespace-only.
    """
    if not system_prompt or not system_prompt.strip():
        raise ValueError(
            "system_prompt must not be empty — the Coach requires evaluation "
            "criteria and role instructions to function correctly"
        )

    model = create_model(model_config)

    logger.debug(
        "Creating Coach agent: provider=%s, model=%s, memory=%s",
        model_config.provider,
        model_config.model,
        memory,
    )

    return create_deep_agent(
        model=model,
        tools=[],
        system_prompt=system_prompt,
        memory=memory,
        backend=None,
    )


__all__ = ["create_coach"]
