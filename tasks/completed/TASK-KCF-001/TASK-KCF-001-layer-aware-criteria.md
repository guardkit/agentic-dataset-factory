---
id: TASK-KCF-001
title: Add layer-aware evaluation criteria to GOAL.md
status: completed
created: 2026-04-05T19:30:00Z
updated: 2026-04-05T21:05:00Z
completed: 2026-04-05T21:05:00Z
completed_location: tasks/completed/TASK-KCF-001/
priority: high
tags: [goal-md, evaluation-criteria, knowledge-layer, coach-prompt]
task_type: implementation
complexity: 4
parent_review: TASK-REV-3A86
feature_id: FEAT-KCF
wave: 1
implementation_mode: task-work
dependencies: []
test_results:
  status: passed
  coverage: null
  last_run: 2026-04-05T21:00:00Z
---

# Task: Add layer-aware evaluation criteria to GOAL.md

## Description

Modify the Evaluation Criteria section in `domains/gcse-english-tutor/GOAL.md` to define
separate criteria for behaviour-layer and knowledge-layer examples.

### Current State

A single set of 5 criteria applied uniformly to all examples:

| Criterion | Weight |
|-----------|--------|
| socratic_approach | 25% |
| ao_accuracy | 25% |
| mark_scheme_aligned | 20% |
| age_appropriate | 15% |
| factual_accuracy | 15% |

### Required Change

Add layer-specific criteria routing. The Coach prompt is built by `_format_evaluation_criteria()`
in `prompts/coach_prompts.py` which iterates `goal.evaluation_criteria` — a list of
`EvaluationCriterion(name, description, weight)`.

**Option A — Prompt-level routing (recommended):**
Add text to the Evaluation Criteria section instructing the Coach to apply different criteria
based on the example's `metadata.layer` value:

```markdown
## Evaluation Criteria

### Behaviour Layer (type: reasoning)
| Criterion | Description | Weight |
|---|---|---|
| socratic_approach | Guides via questions rather than giving answers | 25% |
| ao_accuracy | Correct application of assessment objectives | 25% |
| mark_scheme_aligned | Analysis aligns with AQA marking criteria | 20% |
| age_appropriate | Language suitable for Year 10 student | 15% |
| factual_accuracy | No incorrect claims about texts or context | 15% |

### Knowledge Layer (type: direct)
| Criterion | Description | Weight |
|---|---|---|
| factual_accuracy | No incorrect claims about texts, context, or terminology | 35% |
| completeness | Covers the topic adequately for RAG retrieval use | 25% |
| age_appropriate | Language suitable for Year 10 student | 20% |
| mark_scheme_aligned | References AQA criteria where applicable | 20% |
```

**Key design decisions:**
- `socratic_approach` removed entirely for knowledge layer (not just N/A)
- `completeness` added as new criterion for knowledge layer (valid Python identifier)
- `factual_accuracy` weight increased to 35% for knowledge (primary concern)
- `ao_accuracy` removed for knowledge (many knowledge examples don't reference specific AOs)
- Weights still sum to 100% per layer

**What to verify:**
- `EvaluationCriterion.name` must be a valid Python identifier — `completeness` passes
- `criteria_met` is `dict[str, bool]` — Coach can return different keys per layer
- The Coach prompt's Evaluation Protocol (step 4) says "Evaluate EACH criterion individually
  from the Evaluation Criteria section" — this naturally routes to the correct layer section

### Files to Modify

1. `domains/gcse-english-tutor/GOAL.md` — Evaluation Criteria section
2. `domains/gcse-english-tutor/GOAL.prod.md` — Same change (if exists and differs)
3. `domains/gcse-english-tutor/GOAL.test.md` — Same change (if exists and differs)

### Files NOT to Modify (verified safe)

- `config/coach_verdict.py` — `criteria_met: dict[str, bool]` accepts any keys
- `prompts/coach_prompts.py` — Formats criteria from GOAL.md, no hardcoded names
- `entrypoint/generation_loop.py` — Uses only `verdict.is_accepted`, never criteria names
- `src/tools/write_output.py` — Validates schema, not criteria
- `domain_config/models.py` — `EvaluationCriterion.name` is free-form `str`

### Parser Compatibility Check

`_format_evaluation_criteria()` in `coach_prompts.py` iterates the criteria list and outputs
a markdown table. If GOAL.md now has TWO tables under subsections, the parser needs to handle
this. Check `src/goal_parser.py` `parse_evaluation_criteria()` to confirm it can parse
subsectioned criteria or if the section format needs adjusting.

**If the parser only handles a single table**: Keep a single flat table but add a text note
above it instructing the Coach on layer-specific application. This avoids parser changes.

## Acceptance Criteria

- [x] GOAL.md has layer-specific evaluation criteria
- [x] `completeness` is a valid Python identifier (verified by EvaluationCriterion validator)
- [x] Coach prompt correctly includes layer-aware criteria when built
- [x] Existing tests pass (`pytest tests/ -v`) — 129 criteria-related tests pass
- [x] Parser handles the new format (single flat table with layer annotations in descriptions)

## Implementation Notes

- Check `src/goal_parser.py` `parse_evaluation_criteria()` first to understand format constraints
- If parser needs changes, keep them minimal — the parser is well-tested
- The CRITICAL PRE-CHECK for `<think>` blocks should remain unchanged (it's type-based, not layer-based)
