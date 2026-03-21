---
complexity: 5
dependencies:
- TASK-GG-001
estimated_minutes: 90
feature_id: FEAT-GG
id: TASK-GG-003
implementation_mode: task-work
parent_review: TASK-REV-843F
status: design_approved
task_type: feature
title: 'Author GOAL.md sections 6-9: Evaluation Criteria, Output Schema, Metadata
  Schema, Layer Routing'
wave: 1
---

# Task: Author GOAL.md sections 6-9

## Description

Populate sections 6 through 9 of `domains/gcse-english-tutor/GOAL.md` with the evaluation rubric, output format, metadata constraints, and layer routing rules.

### Section 6: Evaluation Criteria
Create the 5-criterion Coach rubric table with valid Python identifier names and weights summing to 100%:
- `socratic_approach` (25%) — guides via questions rather than giving answers
- `ao_accuracy` (25%) — correct application of assessment objectives
- `mark_scheme_aligned` (20%) — analysis aligns with AQA marking criteria
- `age_appropriate` (15%) — language suitable for Year 10 student
- `factual_accuracy` (15%) — no incorrect claims about texts or context

### Section 7: Output Schema
Define the ShareGPT JSON structure with `messages` array and `metadata` object, matching the schema in `docs/design/models/DM-training-example.md`.

### Section 8: Metadata Schema
Create the metadata field table with valid values drawn from the GCSE English curriculum:
- `layer`: behaviour, knowledge
- `type`: reasoning, direct
- `ao`: AO1-AO6
- `text`: macbeth, a_christmas_carol, an_inspector_calls, power_conflict_poetry, language_paper_1, language_paper_2, general, unseen_poetry
- `topic`: character_analysis, language_analysis, structure_analysis, essay_feedback, exam_technique, comparative, factual_recall, character_knowledge, terminology, encouragement
- `grade_target`: 4-9 or null
- `source`: synthetic, aqa_derived, exam_board_adapted
- `turns`: 1+

### Section 9: Layer Routing
Define the behaviour→train.jsonl and knowledge→rag_index/knowledge.jsonl routing table with classification rules.

## Acceptance Criteria

- [ ] Section 6: 5 evaluation criteria; all names are valid Python identifiers (no hyphens); weights sum to 100%
- [ ] Section 6: Each criterion has a description and a weight column
- [ ] Section 7: Contains valid JSON code block with `messages` and `metadata` top-level keys
- [ ] Section 8: Markdown table with Field, Type, Required, Valid Values columns
- [ ] Section 8: All fields have Required = yes
- [ ] Section 8: `text` valid values include all AQA set text identifiers
- [ ] Section 8: `ao` valid values are AO1 through AO6 only (not AO7+)
- [ ] Section 8: `grade_target` valid values are 4-9 and null
- [ ] Section 9: Contains `behaviour` and `knowledge` rows with destinations
- [ ] All modified files pass project-configured lint/format checks with zero errors

## Source References

- `docs/design/contracts/API-domain-config.md` — section format specifications
- `docs/design/models/DM-goal-schema.md` — GoalConfig sub-entity schemas
- `docs/research/gcse-tutor-training-data-format.md` — metadata schema values
- `synthesis/validator.py` — existing Pydantic models for cross-reference
- `features/gcse-goal-md/gcse-goal-md.feature` — BDD scenarios