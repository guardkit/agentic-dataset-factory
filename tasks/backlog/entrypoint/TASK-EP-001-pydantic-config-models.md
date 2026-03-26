---
id: TASK-EP-001
title: Pydantic config models for agent-config.yaml
task_type: declarative
parent_review: TASK-REV-9EDC
feature_id: FEAT-2CF1
wave: 1
implementation_mode: task-work
complexity: 3
dependencies: []
status: in_review
autobuild_state:
  current_turn: 1
  max_turns: 35
  worktree_path: /Users/richardwoollcott/Projects/appmilla_github/agentic-dataset-factory/.guardkit/worktrees/FEAT-6D0B
  base_branch: main
  started_at: '2026-03-20T23:28:43.395316'
  last_updated: '2026-03-20T23:36:11.481778'
  turns:
  - turn: 1
    decision: approve
    feedback: null
    timestamp: '2026-03-20T23:28:43.395316'
    player_summary: Implementation via task-work delegation
    player_success: true
    coach_success: true
---

# Task: Pydantic Config Models for agent-config.yaml

## Description

Create Pydantic BaseModel classes for the `agent-config.yaml` configuration file. This covers `AgentConfig`, `GenerationConfig`, `ChunkingConfig`, and `LoggingConfig`. The `ModelConfig` model is already planned in TASK-AF-001 (agent-factories feature) and should be imported, not duplicated.

## Requirements

- `AgentConfig` top-level model with fields: `domain` (str, required), `player` (ModelConfig), `coach` (ModelConfig), `generation` (GenerationConfig), `chunking` (ChunkingConfig), `logging` (LoggingConfig)
- `GenerationConfig` with defaults: `max_turns=3`, `llm_retry_attempts=3`, `llm_retry_backoff=2.0`, `llm_timeout=300`, `target_timeout=600`
- `ChunkingConfig` with defaults: `chunk_size=512`, `overlap=64`
- `LoggingConfig` with defaults: `level="INFO"`, `format="json"`
- Pydantic validators:
  - `max_turns >= 1`
  - `chunk_size > 0`
  - `overlap >= 0 and overlap < chunk_size`
  - `level` must be one of: DEBUG, INFO, WARNING, ERROR
  - `format` must be "json" (ADR-ARCH-007)
- Use `model_config = ConfigDict(extra="ignore")` for forward compatibility (ASSUM-003) — log warning on unknown fields

## Acceptance Criteria

- [ ] All config models defined as Pydantic BaseModel subclasses
- [ ] All validation rules from DM-agent-config.md enforced via Pydantic validators
- [ ] Default values match the API contract (API-entrypoint.md)
- [ ] `ConfigDict(extra="ignore")` set for unknown field tolerance
- [ ] Unit tests cover all boundary and negative validation scenarios
- [ ] All modified files pass project-configured lint/format checks with zero errors

## Reference

- Data model: `docs/design/models/DM-agent-config.md`
- API contract: `docs/design/contracts/API-entrypoint.md`
- BDD scenarios: `features/entrypoint/entrypoint.feature` (boundary group)
- Related: TASK-AF-001 (ModelConfig — import, do not duplicate)

## Implementation Notes

Place models in `config/models.py`. Import `ModelConfig` from `config.models` (shared with agent-factories).
