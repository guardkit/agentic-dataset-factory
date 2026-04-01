---
id: TASK-LR1-007
title: Lower Coach temperature from 0.3 to 0.1
status: backlog
created: 2026-03-30T00:00:00Z
updated: 2026-03-30T00:00:00Z
priority: low
tags: [config-tuning, coach]
complexity: 1
parent_review: TASK-REV-649A
feature_id: FEAT-LR1
wave: 2
implementation_mode: direct
dependencies: [TASK-LR1-001]
---

# Task: Lower Coach temperature from 0.3 to 0.1

## Description

Lower Coach temperature to reduce reasoning verbosity. With `guided_json` (TASK-LR1-001), this is less critical but still beneficial for more deterministic evaluation. Apply after verifying guided_json effectiveness.

## Scope

- [ ] Change Coach temperature from 0.3 to 0.1 in configuration
- [ ] Document rationale in config comment

## Acceptance Criteria

- [ ] Coach temperature set to 0.1
- [ ] Player temperature unchanged
