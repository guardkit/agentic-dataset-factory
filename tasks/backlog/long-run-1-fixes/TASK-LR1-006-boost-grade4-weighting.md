---
id: TASK-LR1-006
title: Boost Grade 4 weighting in target generation
status: backlog
created: 2026-03-30T00:00:00Z
updated: 2026-03-30T00:00:00Z
priority: medium
tags: [config-tuning, curriculum-balance]
complexity: 2
parent_review: TASK-REV-649A
feature_id: FEAT-LR1
wave: 2
implementation_mode: direct
dependencies: []
---

# Task: Boost Grade 4 weighting in target generation

## Description

Grade 4 is severely underrepresented in Long Run 1: only 30 examples (3.9%), covering just 3 texts and 2 topics. The distribution skews mid-to-high, underserving lower-attaining students.

Increase Grade 4 weighting in the target generation configuration to achieve ~12-15% representation.

## Scope

- [ ] Identify where grade weighting is configured (likely in target generation config/curriculum definition)
- [ ] Increase Grade 4 weight to target ~12-15% of generated examples
- [ ] Ensure Grade 4 targets span all texts and topics (not just macbeth/an_inspector_calls + character_analysis/exam_technique)
- [ ] Consider also slightly boosting Grade 5 (14.7% → ~16%)

## Acceptance Criteria

- [ ] Grade 4 weighting increased in configuration
- [ ] Grade 4 targets cover broader text and topic range
- [ ] Grade distribution documented in config comments
