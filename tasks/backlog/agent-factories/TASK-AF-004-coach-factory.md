---
id: TASK-AF-004
title: Implement Coach factory
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
- coach
- factory
- create-deep-agent
- no-tools
- role-separation
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
  started_at: '2026-03-20T22:58:25.787432'
  last_updated: '2026-03-20T23:08:29.485478'
  turns:
  - turn: 1
    decision: approve
    feedback: null
    timestamp: '2026-03-20T22:58:25.787432'
    player_summary: Implementation via task-work delegation
    player_success: true
    coach_success: true
---

# Task: Implement Coach factory

## Description

Create `agents/coach.py` with the `create_coach` factory function that delegates to `create_deep_agent`. The Coach agent has NO tools (D5 invariant) and NO FilesystemBackend — it is an evaluation-only agent.

## Requirements

Based on `docs/design/contracts/API-generation.md`:

```python
def create_coach(
    model_config: ModelConfig,
    system_prompt: str,
    memory: list[str],
) -> DeepAgent:
```

- Signature has NO `tools` parameter (structural enforcement of D5)
- Always passes `tools=[]` to `create_deep_agent`
- NO `FilesystemBackend` — Coach has no file access
- `FilesystemBackend` must NOT be imported in `agents/coach.py`

## Acceptance Criteria

- [ ] `agents/coach.py` contains `create_coach()` with the contract signature (no `tools` parameter)
- [ ] Factory delegates to `create_deep_agent` with `tools=[]`
- [ ] NO `backend` kwarg passed to `create_deep_agent` (or explicitly `backend=None`)
- [ ] `FilesystemBackend` is NOT imported anywhere in `agents/coach.py`
- [ ] `system_prompt` is passed as `system_prompt` kwarg
- [ ] `memory` list is passed as `memory` kwarg
- [ ] Empty system prompt raises a validation error
- [ ] All modified files pass project-configured lint/format checks with zero errors

## BDD Scenario Coverage

- Creating a Coach agent with no tools
- Coach agent is created without a FilesystemBackend
- Coach factory always passes an empty tools list
- Attempting to create a Coach with tools should be prevented (no tools param)
- Both factories delegate to create_deep_agent
- Factory called with an empty system prompt (reject)

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

    config = ModelConfig(provider="anthropic", model="claude-sonnet-4-20250514")
    assert config.provider in ("local", "anthropic", "openai"), f"Invalid provider: {config.provider}"
    assert config.model, "model must not be empty"
```

## Implementation Notes

The structural absence of a `tools` parameter is the primary enforcement mechanism for role separation. The module-level import check for `FilesystemBackend` (test in TASK-AF-008) provides a second layer of defence.
