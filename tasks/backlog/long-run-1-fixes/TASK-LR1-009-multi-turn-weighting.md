---
id: TASK-LR1-009
title: Increase multi-turn example weighting in target generation
status: backlog
created: 2026-03-30T00:00:00Z
updated: 2026-03-30T00:00:00Z
priority: medium
tags: [config-tuning, multi-turn, curriculum-balance]
complexity: 3
parent_review: TASK-REV-649A
feature_id: FEAT-LR1
wave: 2
implementation_mode: task-work
dependencies: [TASK-LR1-001, TASK-LR1-005]
---

# Task: Increase multi-turn example weighting in target generation

## Description

Long Run 1 produced 91.3% single-turn examples. Multi-turn tutoring dynamics (follow-up questions, scaffolded learning, misconception correction) are important for fine-tuning a tutor model.

Increase multi-turn weighting to target ~25-30% multi-turn examples. Implement after TASK-LR1-001 (guided_json) and TASK-LR1-005 (increased max_turns for essay) since multi-turn generation was the hardest category in Run 1.

## Scope

- [ ] Identify where turn count is configured in target generation
- [ ] Increase multi-turn target weighting (2-turn: ~15%, 3-turn: ~8%, 4-turn: ~5%)
- [ ] Ensure multi-turn targets span all text types and topics

## Acceptance Criteria

- [ ] Multi-turn examples target ~25-30% of total generation
- [ ] Turn distribution is specified in configuration
- [ ] Multi-turn targets cover all text types
