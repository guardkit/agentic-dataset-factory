---
id: TASK-D0A8-002
title: Reduce Player temperature from 0.6 to 0.4
status: completed
created: 2026-04-01T20:00:00Z
updated: 2026-04-01T21:20:00Z
completed: 2026-04-01T21:20:00Z
completed_location: tasks/completed/TASK-D0A8-002/
priority: high
tags: [config, player, format-gate, temperature]
task_type: implementation
complexity: 1
parent_review: TASK-REV-D0A8
feature_id: FEAT-D0A8
wave: 1
implementation_mode: direct
dependencies: []
test_results:
  status: passed
  coverage: null
  last_run: 2026-04-01T21:15:00Z
  tests_passed: 205
  tests_failed: 0
---

# Task: Reduce Player temperature from 0.6 to 0.4

## Description

The 2500-run showed a 41% format gate failure rate where the Player outputs reasoning text ("The user wants me to generate...") instead of JSON. Lowering the Player temperature from 0.6 to 0.4 reduces the model's tendency to "think aloud" before producing JSON output.

This is the **safest lever** for reducing format gate failures:
- Config-only change, easily reversible
- No architectural conflict
- Does not repeat previous mistakes (prompt engineering backfired in TASK-FPF1-001)
- Does not use structured output (incompatible with Player per TASK-LR1-001)

## Scope

Change the Player model temperature in the config from 0.6 to 0.4.

## Constraints

- MUST NOT change Coach temperature (currently 0.3)
- MUST NOT modify Player prompt text
- MUST NOT add structured output to Player (TASK-LR1-001 architectural decision)
- MUST NOT add BAD/GOOD examples (caused 22.1pp regression in TASK-FPF1)

## Acceptance Criteria

- [x] Player temperature is 0.4 in config
- [x] Coach temperature remains 0.3
- [x] No other config changes

## Files to Modify

- Agent config file (agent-config.yaml or equivalent)

## Rollback

Revert temperature to 0.6 if acceptance rate or example quality degrades in the resumed run.
