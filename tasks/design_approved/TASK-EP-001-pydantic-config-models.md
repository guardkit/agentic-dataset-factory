---
complexity: 3
dependencies: []
feature_id: FEAT-2CF1
id: TASK-EP-001
implementation_mode: task-work
parent_review: TASK-REV-9EDC
status: design_approved
task_type: declarative
title: Pydantic config models for agent-config.yaml
wave: 1
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