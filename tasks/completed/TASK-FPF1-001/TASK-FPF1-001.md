---
id: TASK-FPF1-001
title: Revert harmful prompt changes from player_prompts.py
status: completed
created: 2026-03-31T00:00:00Z
updated: 2026-03-31T00:00:00Z
completed: 2026-03-31T00:00:00Z
priority: critical
tags: [prompt, player, regression-fix, format-compliance]
complexity: 2
task_type: implementation
parent_review: TASK-REV-FPF1
feature_id: FEAT-FPF1
wave: 1
implementation_mode: task-work
dependencies: []
test_results:
  status: passed
  tests_total: 60
  tests_passed: 60
  coverage: null
  last_run: 2026-03-31T00:00:00Z
---

# Task: Revert harmful prompt changes from player_prompts.py

## Description

The BAD/GOOD examples and "do not think out loud" instruction added to the Player
prompt caused a 22.1pp acceptance regression (90.9% → 68.8%). Evidence:

- Non-JSON output increased 54% (44 → 68 format gate blocks)
- NEW failure mode: JSON without metadata (0 → 22 write validation failures)
- Unclosed think blocks increased 250% (4 → 14 post-gen failures)

The BAD example likely primes Qwen3.5 to replicate the bad pattern (negative example
priming). The "do not think out loud" instruction causes the model to split its
output into separate JSON objects.

## Changes Required

### File: `prompts/player_prompts.py`

1. **REMOVE** the BAD/GOOD example block (approx lines 115-124):
   ```
   ### BAD (causes pipeline failure — do NOT do this):
   The user wants me to generate a literary analysis example...
   ...
   ### GOOD (correct — do this):
   {"messages": [...], "metadata": {...}}
   ```

2. **REMOVE** the "do not think out loud" bullet (approx line 109):
   ```
   - Do NOT "think out loud" or reason about what to generate — just output the JSON
   ```

3. **KEEP** the "CRITICAL — Mandatory Metadata" section (lines 79-84) — data shows
   this is net positive.

4. **KEEP** the "Metadata Checklist" section (lines 231-250) — this is net positive.

5. **KEEP** the "CRITICAL — Response Format" header and its other bullets — only
   remove the specific BAD/GOOD and "think out loud" items.

## Acceptance Criteria

- [x] BAD/GOOD example block removed from player_prompts.py
- [x] "think out loud" bullet removed from CRITICAL Response Format section
- [x] Mandatory Metadata section preserved
- [x] Metadata Checklist section preserved
- [x] All existing prompt builder tests pass: `pytest prompts/tests/test_prompt_builders.py -v`
- [x] Prompt still contains Output Schema before Generation Guidelines
- [x] No other prompt sections affected

## Key Files

- `prompts/player_prompts.py` (lines 79-124, 231-250)
- `prompts/tests/test_prompt_builders.py` (may need test updates if tests assert removed text)

## Verification

After implementing, the Player prompt should match the baseline prompt from the
test-run-after-params-fixes run, plus the Mandatory Metadata and Metadata Checklist
additions. Run `pytest prompts/tests/ -v` to verify.
