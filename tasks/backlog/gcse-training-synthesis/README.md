# Feature: GCSE English Training Example Synthesis (Phase 1)

**Feature ID:** FEAT-GTS
**Parent Review:** TASK-REV-6DBC
**Status:** Planned
**Testing:** Full TDD

## Problem Statement

The project needs a Phase 1 baseline dataset of ~200-300 GCSE English tutoring training examples for fine-tuning Nemotron 3 Nano via Unsloth QLoRA. This baseline is the reference checkpoint for an ablation study comparing manual synthesis (Phase 1) against the Player-Coach adversarial loop (Phase 2).

## Solution Approach

A self-contained Python script in `synthesis/` that:
1. Loads generation targets from `domains/gcse-english-tutor/generation-plan.yaml`
2. Calls Claude API (claude-sonnet-4-5) with parameterised prompt templates
3. Validates output against ShareGPT schema with metadata
4. Enforces 75/25 reasoning/direct split
5. Routes examples by layer (behaviour → train.jsonl, knowledge → rag_index/knowledge.jsonl)
6. Handles errors, rate limits, and supports resumption via checkpoint file

## Subtasks

| Task | Title | Complexity | Wave | Mode |
|------|-------|-----------|------|------|
| TASK-GTS-001 | Project scaffolding | 2 | 1 | direct |
| TASK-GTS-002 | Pydantic models | 3 | 2 | task-work |
| TASK-GTS-003 | Validation logic | 5 | 3 | task-work |
| TASK-GTS-004 | Prompt templates | 4 | 3 | task-work |
| TASK-GTS-005 | Synthesis orchestrator | 6 | 4 | task-work |

## Execution Order

- **Wave 1:** TASK-GTS-001 (scaffolding)
- **Wave 2:** TASK-GTS-002 (depends on scaffolding)
- **Wave 3:** TASK-GTS-003 + TASK-GTS-004 (parallel — independent modules, both depend on models)
- **Wave 4:** TASK-GTS-005 (depends on validation + templates)

## Feature Spec

28 Gherkin scenarios in `features/gcse-training-synthesis/gcse-training-synthesis.feature`

## Key Documents

- Pipeline plan: `docs/research/training-pipeline-plan.md`
- Data format spec: `docs/research/gcse-tutor-training-data-format.md`
- Assumptions: `features/gcse-training-synthesis/gcse-training-synthesis_assumptions.yaml`
