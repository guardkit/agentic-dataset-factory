---
id: TASK-LR1-002
title: Add post-generation validation gate before writing to train.jsonl
status: completed
created: 2026-03-30T00:00:00Z
updated: 2026-03-30T00:00:00Z
completed: 2026-03-30T00:00:00Z
completed_location: tasks/completed/TASK-LR1-002/
priority: high
tags: [pipeline-fix, validation, data-quality]
complexity: 3
parent_review: TASK-REV-649A
feature_id: FEAT-LR1
wave: 1
implementation_mode: task-work
dependencies: []
---

# Task: Add post-generation validation gate before writing to train.jsonl

## Description

Add a validation gate after Coach acceptance and before `write_output` that catches defective training examples. Long Run 1 produced 33 defective entries that passed Coach review but should have been rejected.

## Defects to catch

| Defect | Count in Run 1 | Detection method |
|--------|----------------|-----------------|
| Empty assistant responses (think-block only, no visible reply) | 23 | Strip `<think>...</think>`, check remaining content length > 0 |
| Degenerate placeholder entries (`"..."` content) | 3 | Check system/user/assistant content != `"..."` |
| Unclosed `<think>` blocks | 7 | Count `<think>` opens vs `</think>` closes |

## Scope

- [x] Add validation function in `synthesis/validator.py` (or appropriate location)
- [x] Integrate validation call in `entrypoint/generation_loop.py` after Coach accept, before `write_output`
- [x] On validation failure: log a WARNING with the defect type and reject the example (write to rejected.jsonl with reason `validation_failed: {defect_type}`)
- [x] Add unit tests for each defect detection case
- [x] Ensure the validator is idempotent and side-effect-free

## Acceptance Criteria

- [x] All 3 defect types detected in unit tests
- [x] Validation gate integrated into pipeline
- [x] Defective examples written to rejected.jsonl with descriptive reason
- [x] No false positives on valid examples (test with representative sample)
- [x] Existing tests pass

## Risk Assessment

**Risk: Very low** — read-only validation gate. Worst case: false positive rejects a valid example, which is recoverable.
