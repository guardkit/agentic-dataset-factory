---
id: TASK-AF-003
title: Implement Player factory
task_type: feature
parent_review: TASK-REV-DAA1
feature_id: FEAT-AF
wave: 2
implementation_mode: task-work
complexity: 3
dependencies:
- TASK-AF-001
status: in_review
tags:
- player
- factory
- create-deep-agent
- filesystem-backend
consumer_context:
- task: TASK-AF-001
  consumes: ModelConfig
  framework: DeepAgents create_deep_agent
  driver: deepagents
  format_note: ModelConfig must be translated to a concrete model object via create_model()
    before passing to create_deep_agent
autobuild_state:
  current_turn: 1
  max_turns: 35
  worktree_path: /Users/richardwoollcott/Projects/appmilla_github/agentic-dataset-factory/.guardkit/worktrees/FEAT-5AC9
  base_branch: main
  started_at: '2026-03-20T22:58:25.791396'
  last_updated: '2026-03-20T23:08:57.171953'
  turns:
  - turn: 1
    decision: approve
    feedback: null
    timestamp: '2026-03-20T22:58:25.791396'
    player_summary: Implementation via task-work delegation
    player_success: true
    coach_success: true
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
