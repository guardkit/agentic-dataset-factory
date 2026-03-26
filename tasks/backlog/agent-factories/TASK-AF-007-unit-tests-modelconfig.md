---
id: TASK-AF-007
title: Unit tests for ModelConfig
task_type: testing
parent_review: TASK-REV-DAA1
feature_id: FEAT-AF
wave: 2
implementation_mode: task-work
complexity: 3
dependencies:
- TASK-AF-001
status: in_review
tags:
- testing
- pydantic
- validation
- model-config
- boundary
autobuild_state:
  current_turn: 1
  max_turns: 35
  worktree_path: /Users/richardwoollcott/Projects/appmilla_github/agentic-dataset-factory/.guardkit/worktrees/FEAT-5AC9
  base_branch: main
  started_at: '2026-03-20T22:58:25.791029'
  last_updated: '2026-03-20T23:04:23.294985'
  turns:
  - turn: 1
    decision: approve
    feedback: null
    timestamp: '2026-03-20T22:58:25.791029'
    player_summary: Implementation via task-work delegation
    player_success: true
    coach_success: true
---

# Task: Unit tests for ModelConfig

## Description

Write comprehensive unit tests for the `ModelConfig` Pydantic model covering all BDD boundary and negative scenarios from `features/agent-factories/agent-factories.feature`.

## Test Cases

### Boundary Conditions
- Temperature 0.0 → accepted
- Temperature 2.0 → accepted
- Temperature 2.1 → `ValidationError`
- Temperature -0.1 → `ValidationError`

### Negative Cases
- Missing provider → `ValidationError`
- Invalid provider (azure, huggingface, google) → `ValidationError`
- Local provider without endpoint → `ValidationError`
- Missing model → `ValidationError`
- Local provider with malformed endpoint URL → `ValidationError`

### Edge Cases
- Anthropic provider without endpoint → accepted (default API)
- OpenAI provider without endpoint → accepted (default API)
- Default temperature applied when not specified → 0.7

### Key Examples
- Full valid config with all fields → accepted
- Provider "local" with valid endpoint → accepted

## Acceptance Criteria

- [ ] All boundary temperature tests pass
- [ ] All negative validation tests pass
- [ ] All edge case tests pass
- [ ] Tests use `pytest.raises(ValidationError)` for negative cases
- [ ] Tests are in `tests/test_model_config.py` or `config/tests/test_models.py`

## Implementation Notes

Follow existing test patterns from `synthesis/tests/test_validator.py`.
