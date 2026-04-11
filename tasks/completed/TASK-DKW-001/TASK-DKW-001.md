---
id: TASK-DKW-001
title: Add message-structure validation gate to write_output tool
status: completed
created: 2026-04-11T00:00:00Z
updated: 2026-04-11T00:00:00Z
completed: 2026-04-11T00:00:00Z
completed_location: tasks/completed/TASK-DKW-001/
priority: high
tags: [dataset-factory, write-output, bug-fix, validation]
task_type: implementation
complexity: 2
parent_review: TASK-REV-4AA0
feature_id: FEAT-DKW
wave: 1
implementation_mode: task-work
dependencies: []
test_results:
  status: passed
  coverage: null
  last_run: 2026-04-11T00:00:00Z
  tests_passed: 66
  tests_failed: 0
---

# Task: Add message-structure validation gate to write_output tool

## Parent Review

[TASK-REV-4AA0](../TASK-REV-4AA0-fix-dataset-key-whitespace-bug.md) — see full analysis in [.claude/reviews/TASK-REV-4AA0-review-report.md](../../../.claude/reviews/TASK-REV-4AA0-review-report.md).

## Problem

Two records in `output_backup_run1/train.jsonl` (lines 1145 and 1330) contain a message dict with the key `" role"` (leading space) instead of `"role"`. Root cause: the Player LLM occasionally hallucinates a leading space inside the `role` key string when emitting multi-turn JSON after the `}, {` separator. The pipeline currently has **no deterministic validator for the key set of each message dict**, so the defect travels from Player response through to disk via `json.loads` → dict → `json.dumps`, which faithfully preserve it.

Defect rate in the backup: **2/238 multi-turn records (0.84 %)**, 0/1478 single-turn records.

## Scope

Add a structural-validation gate **inside the `write_output` tool only**. Do NOT modify prompts, the Coach, `validate_post_generation`, or `_repair_json_strings`. Do NOT alter the existing steps 3-10 behavior (apart from one error-message simplification — see below).

## Implementation

### File: [src/tools/write_output.py](../../../src/tools/write_output.py)

1. **Add module-level constants** near the top of the file (after `_LAYER_PATHS`):

   ```python
   _ALLOWED_MESSAGE_KEYS: frozenset[str] = frozenset({"role", "content"})
   _VALID_ROLES: frozenset[str] = frozenset({"system", "user", "assistant"})
   ```

2. **Insert a new validation block** in the `write_output` inner function **immediately after step 2** (the `messages` non-empty array check at line 104) and **before step 3** (the `first_msg.get("role") != "system"` check at line 108-110):

   ```python
   # -- Step 2b: Validate every message dict has exactly {"role", "content"}
   #    with a valid role value (TASK-DKW-001, bug TASK-REV-4AA0).
   #    Catches LLM-produced malformed keys like " role" (leading space)
   #    that json.loads accepts but downstream consumers reject.
   for i, msg in enumerate(messages):
       if not isinstance(msg, dict):
           return f"Error: messages[{i}] is not an object"
       keys = set(msg.keys())
       unexpected = keys - _ALLOWED_MESSAGE_KEYS
       missing = _ALLOWED_MESSAGE_KEYS - keys
       if unexpected or missing:
           return (
               f"Error: messages[{i}] has invalid keys "
               f"(unexpected={sorted(unexpected)}, missing={sorted(missing)})"
           )
       if msg["role"] not in _VALID_ROLES:
           return (
               f"Error: messages[{i}].role invalid value "
               f"{msg['role']!r} (expected: system, user, assistant)"
           )
   ```

3. **Simplify step 3 error message** now that the new gate guarantees `messages[0]["role"]` exists. Change line 108-110 from:

   ```python
   first_msg = messages[0]
   if not isinstance(first_msg, dict) or first_msg.get("role") != "system":
       return "Error: messages[0].role must be 'system'"
   ```

   to:

   ```python
   if messages[0]["role"] != "system":
       return "Error: messages[0].role must be 'system'"
   ```

   The `isinstance(first_msg, dict)` check is redundant (gate already enforced it at step 2b). The `.get()` is redundant (gate already enforced the key exists).

4. **Do not touch**:
   - Step 6b (think-tag normalisation with `.get("role") == "assistant"`) — left as-is; the gate makes it strictly correct but no change required.
   - Steps 4, 5, 6, 7, 8, 9, 10 — unchanged.
   - The error-return contract (no raises, everything is a descriptive string).

## Acceptance Criteria

- [ ] `_ALLOWED_MESSAGE_KEYS` and `_VALID_ROLES` constants defined at module scope
- [ ] Step 2b validation loop inserted between steps 2 and 3
- [ ] Step 3 error-check simplified to use `messages[0]["role"]` (the `isinstance`/`get` redundancy removed)
- [ ] All existing tests in `src/tools/tests/test_write_output.py` still pass (no regressions)
- [ ] Tool still returns error strings, never raises (D7 contract preserved)
- [ ] `pytest src/tools/tests/test_write_output.py -v` passes
- [ ] `ruff` / `black` clean

## Out of Scope

- Regression tests for the new behavior — handled by TASK-DKW-002 in the same wave
- Replacing validation steps 2-6 with `TrainingExample.model_validate` — filed as optional follow-up TASK-DKW-003
- Modifications to Player or Coach prompts
- Rewriting the historical `output/train.jsonl` file (training script workaround handles existing records)

## Validation

Simulated against 1,716 real backup records: **0 false positives**, rejects exactly the 2 known-bad records. Expected in-run throughput impact: +2 Player revisions across ~3,432 Player-Coach turns (~0.06 %).

Report: [.claude/reviews/TASK-REV-4AA0-review-report.md](../../../.claude/reviews/TASK-REV-4AA0-review-report.md) §F1, §R1, §Regression Risk Analysis.
