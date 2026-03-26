---
id: TASK-EP-002
title: Config loader with yaml.safe_load and Pydantic parsing
task_type: feature
parent_review: TASK-REV-9EDC
feature_id: FEAT-2CF1
wave: 1
implementation_mode: task-work
complexity: 3
dependencies:
- TASK-EP-001
status: in_review
consumer_context:
- task: TASK-EP-001
  consumes: AgentConfig
  framework: Pydantic BaseModel
  driver: pydantic
  format_note: AgentConfig.model_validate() expects a dict from yaml.safe_load output
autobuild_state:
  current_turn: 1
  max_turns: 35
  worktree_path: /Users/richardwoollcott/Projects/appmilla_github/agentic-dataset-factory/.guardkit/worktrees/FEAT-6D0B
  base_branch: main
  started_at: '2026-03-20T23:36:11.514925'
  last_updated: '2026-03-20T23:43:53.027653'
  turns:
  - turn: 1
    decision: approve
    feedback: null
    timestamp: '2026-03-20T23:36:11.514925'
    player_summary: Implementation via task-work delegation
    player_success: true
    coach_success: true
---

# Task: Config Loader — yaml.safe_load + Pydantic Parsing

## Description

Implement `load_config(path: Path) -> AgentConfig` function that loads `agent-config.yaml` using `yaml.safe_load` (ASSUM-005 — rejects anchors/aliases/custom tags) and parses it into the Pydantic `AgentConfig` model.

## Requirements

- `load_config(path: Path = Path("agent-config.yaml")) -> AgentConfig`
- Use `yaml.safe_load()` exclusively (security — ASSUM-005)
- Raise `FileNotFoundError` with clear message if config file missing
- Raise `ConfigValidationError` (custom exception) wrapping Pydantic `ValidationError` with user-friendly message
- Log warning for unknown fields (via Pydantic's `extra="ignore"` + custom `model_validator`)
- Support all validation rules from DM-agent-config.md (delegated to Pydantic models)

## Acceptance Criteria

- [ ] `load_config()` returns validated `AgentConfig` from valid YAML
- [ ] `FileNotFoundError` raised when config file missing (BDD: "Startup with missing agent-config.yaml")
- [ ] `ConfigValidationError` raised for invalid config values with actionable error messages
- [ ] `yaml.safe_load` used (never `yaml.load` or `yaml.unsafe_load`)
- [ ] Warning logged for unrecognised fields (BDD: "Config file with extra unknown fields")
- [ ] YAML anchor/alias injection rejected (BDD: "Config file with YAML alias injection")
- [ ] All modified files pass project-configured lint/format checks with zero errors

## Seam Tests

The following seam test validates the integration contract with the producer task. Implement this test to verify the boundary before integration.

```python
"""Seam test: verify AgentConfig contract from TASK-EP-001."""
import pytest


@pytest.mark.seam
@pytest.mark.integration_contract("AgentConfig")
def test_agent_config_format():
    """Verify AgentConfig matches the expected format.

    Contract: AgentConfig.model_validate() expects a dict from yaml.safe_load output
    Producer: TASK-EP-001
    """
    from config.models import AgentConfig

    # Minimal valid config dict (as yaml.safe_load would produce)
    config_dict = {
        "domain": "test-domain",
        "player": {"provider": "local", "model": "test-model", "endpoint": "http://localhost:8000/v1"},
        "coach": {"provider": "local", "model": "test-model", "endpoint": "http://localhost:8000/v1"},
    }

    result = AgentConfig.model_validate(config_dict)
    assert result.domain == "test-domain"
    assert result.generation.max_turns == 3  # default
```

## Reference

- API contract: `docs/design/contracts/API-entrypoint.md` (Python Contract: Config Loading)
- BDD scenarios: `features/entrypoint/entrypoint.feature` (negative cases group)
- ASSUM-005: yaml.safe_load security

## Implementation Notes

Place in `config/loader.py`. Define `ConfigValidationError` in `config/exceptions.py`.
