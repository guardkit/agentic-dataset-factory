---
id: TASK-G4D-004
title: Fix LR schedule metadata in task and training script
status: backlog
created: 2026-04-19T00:00:00Z
priority: low
tags: [housekeeping, documentation]
complexity: 1
task_type: implementation
implementation_mode: direct
parent_review: TASK-REV-G4R2
feature_id: FEAT-G4D
wave: 1
dependencies: []
---

# Task: Fix LR schedule metadata in task and training script

## Description

TASK-REV-G4R2 Finding 10 identified that the TASK-REV-G4R2 task file line 42 says "cosine decay" for the learning rate schedule, but the training script (`train_gemma4_moe.py` line 318) specifies `lr_scheduler_type="linear"`. The actual training used linear decay as confirmed by the LR values in the run-4 log.

## Changes Required

1. Update TASK-REV-G4R2 task file line 42: change "cosine decay" to "linear decay"
2. Optionally: add a comment in `train_gemma4_moe.py` noting that linear was used intentionally (or switch to cosine if cosine was the intent)

## Acceptance Criteria

- [ ] Task metadata matches actual training configuration
