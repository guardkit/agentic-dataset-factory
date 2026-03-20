# Feature: GCSE English Tutor GOAL.md — First Domain Configuration

> Feature ID: FEAT-GG | Review: TASK-REV-843F
> Status: Planned | Tasks: 5 | Waves: 2

## Problem

The Agentic Dataset Factory has a fully designed GOAL.md schema (9 sections) and API contracts, but no concrete domain configuration exists yet. Without a real GOAL.md, no downstream module (prompts, ingestion, generation loop) can be developed or tested against real content.

## Solution

Author the complete GCSE English tutor GOAL.md with all 9 sections populated from the research specification and AQA curriculum requirements. Write validation tests to ensure metadata values stay consistent with the Pydantic models in `synthesis/validator.py`.

## Approach

**Authoring-Only** — create the GOAL.md content and validation tests independently of the parser (FEAT-5606). The GOAL.md is a pure markdown document; parser integration happens when FEAT-5606 completes.

## Tasks

| Task | Description | Complexity | Wave | Mode |
|------|-------------|-----------|------|------|
| TASK-GG-001 | Domain directory structure | 3 | 1 | direct |
| TASK-GG-002 | GOAL.md sections 1-5 (Goal, Sources, System Prompt, Targets, Guidelines) | 5 | 1 | task-work |
| TASK-GG-003 | GOAL.md sections 6-9 (Eval Criteria, Output Schema, Metadata, Routing) | 5 | 1 | task-work |
| TASK-GG-004 | Metadata consistency tests (GOAL.md ↔ validator.py) | 4 | 2 | task-work |
| TASK-GG-005 | Structural smoke tests (sections, totals, format) | 4 | 2 | task-work |

## Key References

- BDD specification: `features/gcse-goal-md/gcse-goal-md.feature` (38 scenarios)
- Research doc: `docs/research/gcse-tutor-training-data-format.md`
- API contract: `docs/design/contracts/API-domain-config.md`
- Data model: `docs/design/models/DM-goal-schema.md`
- Existing validator: `synthesis/validator.py`
