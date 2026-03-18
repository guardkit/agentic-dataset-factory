---
id: TASK-GTS-002
title: "Define Pydantic models for ShareGPT schema, metadata, and generation plan"
task_type: declarative
parent_review: TASK-REV-6DBC
feature_id: FEAT-GTS
wave: 2
implementation_mode: task-work
complexity: 3
dependencies:
  - TASK-GTS-001
status: pending
priority: high
tags: [synthesis, phase1, models, pydantic]
---

# Task: Define Pydantic models for ShareGPT schema, metadata, and generation plan

## Description

Create Pydantic v2 models in `synthesis/validator.py` that define the data structures for:
1. The ShareGPT message format (system/user/assistant messages)
2. The metadata schema (layer, type, ao, text, topic, grade_target, source, turns)
3. A complete training example (messages + metadata)
4. The generation plan target format (what gets loaded from generation-plan.yaml)
5. The rejection record format (example + reason code)

These models are the foundation for all validation logic in subsequent tasks.

## Requirements

### Message model
- `role`: Literal["system", "user", "assistant"]
- `content`: str (non-empty)

### Metadata model
- `layer`: Literal["behaviour", "knowledge"]
- `type`: Literal["reasoning", "direct"]
- `ao`: list[str] — each element must match pattern `AO[1-6]`; can be empty list
- `text`: str — one of: macbeth, a_christmas_carol, an_inspector_calls, power_conflict_poetry, language_paper_1, language_paper_2, general, unseen_poetry
- `topic`: str — one of: character_analysis, language_analysis, structure_analysis, essay_feedback, exam_technique, comparative, factual_recall, character_knowledge, terminology, encouragement
- `grade_target`: int | None — if present, must be 4-9 inclusive
- `source`: Literal["synthetic", "aqa_derived", "exam_board_adapted"] — default "synthetic"
- `turns`: int — default 1, must be >= 1

### TrainingExample model
- `messages`: list[Message] — minimum 2 (system + at least one user/assistant pair)
- `metadata`: Metadata
- Validator: first message must have role "system"
- Validator: messages after system must alternate user/assistant

### GenerationTarget model
- `text`: str
- `topic`: str
- `grade_target`: int | None
- `layer`: Literal["behaviour", "knowledge"]
- `type`: Literal["reasoning", "direct"]
- Optional fields: `ao`: list[str], `turns`: int (default 1)

### GenerationPlan model
- `generation_targets`: list[GenerationTarget]

### RejectionRecord model
- `target`: GenerationTarget
- `reason`: str (reason code e.g. "malformed_content", "missing_think_block", "invalid_metadata", "duplicate", "api_error")
- `raw_response`: str | None (the raw API response if available)
- `timestamp`: str (ISO 8601)

## Acceptance Criteria

- [ ] All models defined with Pydantic v2 BaseModel
- [ ] Field validators enforce constraints (ao pattern, grade_target range, message ordering)
- [ ] Models are importable: `from synthesis.validator import TrainingExample, GenerationTarget, GenerationPlan`
- [ ] Unit tests cover: valid construction, each invalid field, edge cases (null grade_target, empty ao list)
- [ ] All modified files pass project-configured lint/format checks with zero errors

## Implementation Notes

Use `Literal` types for constrained string fields. Use `field_validator` for complex constraints (ao pattern matching, message ordering). Keep models at the top of `validator.py` — validation functions will be added in TASK-GTS-003.
