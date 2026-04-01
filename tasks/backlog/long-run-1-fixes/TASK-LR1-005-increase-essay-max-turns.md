---
id: TASK-LR1-005
title: Increase max_turns from 3 to 4 for essay feedback categories
status: backlog
created: 2026-03-30T00:00:00Z
updated: 2026-03-30T00:00:00Z
priority: medium
tags: [config-tuning, pipeline]
complexity: 2
parent_review: TASK-REV-649A
feature_id: FEAT-LR1
wave: 2
implementation_mode: direct
dependencies: [TASK-LR1-001]
---

# Task: Increase max_turns from 3 to 4 for essay feedback categories

## Description

Essay feedback categories (indices ~470-600) had the highest rejection rate (~21%) in Long Run 1, with `max_turns_exhausted` as the dominant rejection reason (70.5% of all rejections). Multi-turn JSON structures are harder for the model to produce correctly.

Allow one additional revision turn specifically for essay feedback targets. This should be implemented after TASK-LR1-001 (guided_json for Coach) since many of these failures may be resolved by fixing Coach parsing first.

## Scope

- [ ] Add category-specific max_turns configuration (default 3, essay_feedback 4)
- [ ] Identify where `max_turns` is configured/used in `entrypoint/generation_loop.py`
- [ ] Add the category override logic

## Acceptance Criteria

- [ ] Essay feedback targets use max_turns=4
- [ ] All other categories remain at max_turns=3
- [ ] Configuration is clear and documented in code comments
