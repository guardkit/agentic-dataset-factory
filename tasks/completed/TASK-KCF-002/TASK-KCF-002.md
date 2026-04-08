---
id: TASK-KCF-002
title: Create GOAL-direct-only.md for targeted re-run
status: completed
created: 2026-04-05T19:30:00Z
updated: 2026-04-05T21:00:00Z
completed: 2026-04-05T21:00:00Z
priority: high
tags: [goal-md, direct-targets, re-run]
task_type: implementation
complexity: 2
parent_review: TASK-REV-3A86
feature_id: FEAT-KCF
wave: 1
implementation_mode: direct
dependencies: [TASK-KCF-001]
completed_location: tasks/completed/TASK-KCF-002/
test_results:
  status: passed
  coverage: null
  last_run: 2026-04-05T21:00:00Z
---

# Task: Create GOAL-direct-only.md for targeted re-run

## Description

Create a variant of GOAL.md that contains only the 6 direct-type categories from the
Generation Targets table. This enables a targeted re-run of only the knowledge/direct
targets (~625 examples, ~8 hours) instead of a full 2500-target re-run (~50 hours).

### Direct Categories to Include

| Category | Type | Layer | Count | Grade Targets |
|---|---|---|---|---|
| Terminology and literary devices | direct | knowledge | 125 | [null] |
| Character knowledge — set texts | direct | knowledge | 100 | [null] |
| Factual recall — AQA specification | direct | knowledge | 100 | [null] |
| Exam structure and mark allocation | direct | knowledge | 75 | [null] |
| Encouragement and study skills | direct | behaviour | 100 | [null] |
| Context — historical and social (set texts) | direct | knowledge | 125 | [null] |

**Total: 625 targets**

### Steps

1. Copy `domains/gcse-english-tutor/GOAL.md` to `domains/gcse-english-tutor/GOAL-direct-only.md`
2. Remove the 12 reasoning-type categories from the Generation Targets table
3. Keep ALL other sections unchanged (Goal, System Prompt, Evaluation Criteria with
   layer-aware fix from KCF-001, Output Schema, Metadata Schema, Layer Routing, etc.)
4. Update the Generation Guidelines section to emphasise knowledge/direct generation
   (remove or soften references to Socratic questioning for direct examples)

### Important

This file must include the layer-aware evaluation criteria from TASK-KCF-001. Do NOT
create this file until KCF-001 is complete.

## Acceptance Criteria

- [x] `GOAL-direct-only.md` exists in `domains/gcse-english-tutor/`
- [x] Contains only 6 direct-type categories (625 total targets)
- [x] Includes layer-aware evaluation criteria from KCF-001
- [x] All other GOAL.md sections (Goal, System Prompt, Output Schema, etc.) preserved
- [x] Parses successfully via `src.goal_parser.load_goal_md()` and `domain_config.parser.parse_goal_md()`
