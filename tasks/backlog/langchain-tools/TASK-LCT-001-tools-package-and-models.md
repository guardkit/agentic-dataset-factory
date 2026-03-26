---
id: TASK-LCT-001
title: Create tools package and Pydantic validation models
task_type: scaffolding
parent_review: TASK-REV-723B
feature_id: FEAT-LCT
wave: 1
implementation_mode: direct
complexity: 3
dependencies: []
status: in_review
priority: high
tags:
- langchain-tools
- scaffolding
- pydantic
autobuild_state:
  current_turn: 1
  max_turns: 35
  worktree_path: /Users/richardwoollcott/Projects/appmilla_github/agentic-dataset-factory/.guardkit/worktrees/FEAT-945D
  base_branch: main
  started_at: '2026-03-20T20:38:33.369711'
  last_updated: '2026-03-20T20:44:57.896465'
  turns:
  - turn: 1
    decision: approve
    feedback: null
    timestamp: '2026-03-20T20:38:33.369711'
    player_summary: "Created the src/tools/ package with Pydantic validation models\
      \ following existing codebase patterns (synthesis/validator.py). Models: Message\
      \ (ShareGPT format), ExampleMetadata (layer/type enum validation with custom\
      \ validators for clear error messages), TrainingExample (system-first + alternating\
      \ role ordering via model_validator), RagRetrievalParams (n_results 1-20 bounds\
      \ with ge/le constraints plus custom validator for actionable error messages).\
      \ No runtime chromadb dependency \u2014 verified via "
    player_success: true
    coach_success: true
---

# Task: Create tools package and Pydantic validation models

## Description

Create the `src/tools/` package structure with Pydantic models for input validation used by both `rag_retrieval` and `write_output` tools.

## Deliverables

1. `src/tools/__init__.py` — Package init, public exports
2. `src/tools/models.py` — Pydantic models for:
   - `RagRetrievalParams` — validates `query` (str, non-empty) and `n_results` (int, 1-20, default 5)
   - `TrainingExample` — validates the full training example JSON structure per DM-training-example.md
   - `ExampleMetadata` — validates metadata fields against injected `MetadataField` schema
   - `Message` — validates individual message objects (role, content)
3. `src/tools/exceptions.py` — Custom error types (used internally, never raised to agents per D7)

## Acceptance Criteria

- [ ] `src/tools/` package importable with `from tools.models import TrainingExample, RagRetrievalParams`
- [ ] `RagRetrievalParams` rejects n_results < 1 or > 20
- [ ] `TrainingExample` validates messages[0].role == "system"
- [ ] `ExampleMetadata` validates layer ∈ {"behaviour", "knowledge"} and type ∈ {"reasoning", "direct"}
- [ ] All models have clear validation error messages suitable for D7 error strings
- [ ] Package has no runtime dependency on ChromaDB (lazy import pattern)

## Reference

- Data model: `docs/design/models/DM-training-example.md`
- API contract: `docs/design/contracts/API-tools.md`
- Goal schema: `docs/design/models/DM-goal-schema.md` (MetadataField type)

## Implementation Notes

- Use Pydantic v2 (`BaseModel`, `Field`, `field_validator`)
- Validation errors will be caught by tool functions and converted to error strings (D7)
- `MetadataField` from FEAT-5606 (Goal MD Parser) will be consumed here — for now define a compatible type locally, to be replaced when FEAT-5606 lands
