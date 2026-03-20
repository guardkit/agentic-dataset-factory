---
complexity: 3
consumer_context:
- consumes: ModelConfig
  driver: deepagents
  format_note: ModelConfig must be translated to a concrete model object via create_model()
    before passing to create_deep_agent
  framework: DeepAgents create_deep_agent
  task: TASK-AF-001
dependencies:
- TASK-AF-001
feature_id: FEAT-AF
id: TASK-AF-003
implementation_mode: task-work
parent_review: TASK-REV-DAA1
status: design_approved
tags:
- player
- factory
- create-deep-agent
- filesystem-backend
task_type: feature
title: Implement Player factory
wave: 2
---

# Task: Implement Player factory

## Description

Create `agents/player.py` with the `create_player` factory function that delegates to `create_deep_agent`. The Player agent receives tools (rag_retrieval + write_output), a FilesystemBackend, and an injected system prompt.

## Requirements

Based on `docs/design/contracts/API-generation.md`:

```python
def create_player(
    model_config: ModelConfig,
    tools: list,
    system_prompt: str,
    memory: list[str],
) -> DeepAgent:
```

- Translates `ModelConfig` to a concrete model via shared `create_model()`
- Passes `tools` list (expected: [rag_retrieval, write_output])
- Assigns `FilesystemBackend` to the agent
- Passes `system_prompt` and `memory` through to `create_deep_agent`

## Acceptance Criteria

- [ ] `agents/player.py` contains `create_player()` with the contract signature
- [ ] Factory delegates to `create_deep_agent` with correct kwargs
- [ ] `FilesystemBackend` is instantiated and passed as `backend` kwarg
- [ ] `tools` parameter is passed through (expected: 2 tools)
- [ ] `system_prompt` is passed as `system_prompt` kwarg
- [ ] `memory` list is passed as `memory` kwarg
- [ ] Empty system prompt raises a validation error
- [ ] `agents/__init__.py` created
- [ ] All modified files pass project-configured lint/format checks with zero errors

## BDD Scenario Coverage

- Creating a Player agent with full configuration
- Player agent is created with a FilesystemBackend
- Player factory receives exactly the expected tool list
- Both factories delegate to create_deep_agent
- Factory called with an empty system prompt (reject)
- Agent factory passes model configuration to create_deep_agent

## Seam Tests

The following seam test validates the integration contract with the producer task. Implement this test to verify the boundary before integration.

```python
"""Seam test: verify ModelConfig contract from TASK-AF-001."""
import pytest


@pytest.mark.seam
@pytest.mark.integration_contract("ModelConfig")
def test_model_config_format():
    """Verify ModelConfig matches the expected format.

    Contract: ModelConfig must be translated to a concrete model object via create_model() before passing to create_deep_agent
    Producer: TASK-AF-001
    """
    from config.models import ModelConfig

    config = ModelConfig(provider="local", model="test-model", endpoint="http://localhost:8000/v1")
    assert config.provider in ("local", "anthropic", "openai"), f"Invalid provider: {config.provider}"
    assert config.model, "model must not be empty"
    assert config.endpoint, "endpoint required for local provider"
```

## Implementation Notes

Use the shared `create_model()` function from `agents/model_factory.py` (or `config/model_factory.py`) to translate ModelConfig into a concrete model object. This avoids duplicating model creation logic with the Coach factory.