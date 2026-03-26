---
id: TASK-AF-001
title: Create ModelConfig Pydantic model
task_type: declarative
parent_review: TASK-REV-DAA1
feature_id: FEAT-AF
wave: 1
implementation_mode: task-work
complexity: 3
dependencies: []
status: in_review
tags:
- pydantic
- config
- validation
- model-config
autobuild_state:
  current_turn: 1
  max_turns: 35
  worktree_path: /Users/richardwoollcott/Projects/appmilla_github/agentic-dataset-factory/.guardkit/worktrees/FEAT-5AC9
  base_branch: main
  started_at: '2026-03-20T22:47:21.312711'
  last_updated: '2026-03-20T22:52:19.329198'
  turns:
  - turn: 1
    decision: approve
    feedback: null
    timestamp: '2026-03-20T22:47:21.312711'
    player_summary: Implementation via task-work delegation
    player_success: true
    coach_success: true
---

# Task: Create ModelConfig Pydantic model

## Description

Create `config/models.py` containing a `ModelConfig` Pydantic BaseModel with field-level validators for the agent configuration. This is the foundational data model used by both Player and Coach factories.

## Requirements

Based on `docs/design/models/DM-agent-config.md` and `docs/design/contracts/API-generation.md`:

- `provider: Literal["local", "anthropic", "openai"]` — enum enforcement
- `model: str` — required, non-empty
- `endpoint: str = ""` — required when `provider == "local"`, must be a valid URL
- `temperature: float` — range 0.0-2.0 inclusive, default 0.7

## Acceptance Criteria

- [ ] `ModelConfig` is a Pydantic `BaseModel` (not a dataclass) in `config/models.py`
- [ ] `provider` uses `Literal["local", "anthropic", "openai"]` for compile-time enforcement
- [ ] `model` is a required non-empty `str`
- [ ] `temperature` uses `Field(ge=0.0, le=2.0, default=0.7)`
- [ ] A `model_validator` ensures `endpoint` is non-empty and a valid URL when `provider == "local"`
- [ ] Anthropic and OpenAI providers accept empty endpoint (use default API)
- [ ] Validation errors raise `ValidationError` with clear messages
- [ ] All modified files pass project-configured lint/format checks with zero errors

## BDD Scenario Coverage

From `features/agent-factories/agent-factories.feature`:
- Temperature boundaries: 0.0 (accept), 2.0 (accept), 2.1 (reject), -0.1 (reject)
- Missing provider (reject)
- Invalid provider: azure, huggingface, google (reject)
- Local provider without endpoint (reject)
- Missing model (reject)
- Malformed endpoint URL for local provider (reject)
- Anthropic/OpenAI without endpoint (accept, use defaults)

## Implementation Notes

Follow existing Pydantic patterns from `synthesis/validator.py`. Create `config/__init__.py` as well.
