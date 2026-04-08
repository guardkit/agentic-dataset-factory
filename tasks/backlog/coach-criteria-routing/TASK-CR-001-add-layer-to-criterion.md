---
id: TASK-CR-001
title: Add layer field to EvaluationCriterion and GOAL.md column mapping
status: backlog
created: 2026-04-07T12:00:00Z
updated: 2026-04-07T12:00:00Z
priority: high
complexity: 3
tags: [criteria-routing, model, parser]
parent_review: TASK-REV-CC01
feature_id: FEAT-CR
wave: 1
implementation_mode: task-work
dependencies: []
test_results:
  status: pending
  coverage: null
  last_run: null
---

# Task: Add layer field to EvaluationCriterion and GOAL.md column mapping

## Description

Add an optional `layer` field to the `EvaluationCriterion` model so each criterion can declare which layer(s) it applies to. Update the GOAL.md Evaluation Criteria table to include a "Layer" column, and update the parser column mapping to extract it.

## Implementation Details

### 1. Update `EvaluationCriterion` in `domain_config/models.py`

Add a `layer` field:
```python
layer: Literal["behaviour", "knowledge", "all"] = "all"
```

Default `"all"` means the criterion applies to both layers (backwards compatible).

### 2. Update GOAL.md Evaluation Criteria table

Add a "Layer" column to the table:

```
| Criterion | Description | Weight | Layer |
|---|---|---|---|
| socratic_approach | Guides via questions ... | 25% | behaviour |
| ao_accuracy | Correct application of AOs ... | 25% | behaviour |
| mark_scheme_aligned | Aligns with AQA marking ... | 20% | all |
| age_appropriate | Language suitable for Year 10 | 15% | all |
| factual_accuracy | No incorrect claims ... | 15% | all |
| completeness | Covers topic for RAG use | 25% | knowledge |
```

### 3. Update parser column mapping

In `domain_config/parser.py`, update `_EVALUATION_CRITERIA_COLUMN_MAP`:
```python
_EVALUATION_CRITERIA_COLUMN_MAP = {
    "Criterion": "name",
    "Description": "description",
    "Weight": "weight",
    "Layer": "layer",
}
```

### 4. Remove "(behaviour layer only)" / "(knowledge layer only)" hints from descriptions

These become redundant once the Layer column exists.

## Files to Modify

- `domain_config/models.py` — EvaluationCriterion model
- `domain_config/parser.py` — _EVALUATION_CRITERIA_COLUMN_MAP
- `domains/gcse-english-tutor/GOAL.md` — Evaluation Criteria table
- `domains/gcse-english-tutor/GOAL.prod.md` — if exists, same change
- `domains/gcse-english-tutor/GOAL.test.md` — if exists, same change

## Acceptance Criteria

- [ ] `EvaluationCriterion` has a `layer` field with Literal type and default "all"
- [ ] GOAL.md table has a Layer column with correct values per criterion
- [ ] Parser extracts the Layer column into the `layer` field
- [ ] Existing tests pass (no regression)
- [ ] New unit test: parsing a criterion row with Layer column produces correct `layer` value
