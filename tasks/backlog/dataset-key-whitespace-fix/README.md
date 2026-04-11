# Feature: dataset-key-whitespace-fix

**Parent review**: [TASK-REV-4AA0](../TASK-REV-4AA0-fix-dataset-key-whitespace-bug.md)
**Feature ID**: FEAT-DKW
**Status**: backlog
**Confidence**: HIGH (empirically validated — see review §Evidence)

## Problem Statement

During the first fine-tuning run of the GCSE English tutor (Gemma 4 31B, April 2026), 2 of 1,716 training examples in `output/train.jsonl` contained JSON with a leading-space `role` key (`{" role": "user", ...}`) instead of `{"role": "user", ...}`. The training script crashed with `KeyError: 'role'` and required a runtime `{k.strip(): v for k, v in msg.items()}` workaround to continue.

The defect occurs **only in multi-turn records** (0.84 % rate among 238 multi-turn records, 0 % among 1478 single-turn records) and consistently lands at `messages[3]` — the second user turn, immediately after the `}, {` JSON object separator. This is consistent with LLM tokenization drift at that specific position, not a Python code bug.

## Solution Approach

Add a deterministic structural gate in `src/tools/write_output.py` that validates every message dict has exactly `{"role", "content"}` keys and a valid `role` value. The gate lives between existing step 2 (messages is non-empty array) and step 3 (messages[0].role == "system"). Rejections flow back through the existing write-error → Coach-feedback → Player-revision loop, so throughput is unaffected (~0.06 % expected impact).

The fix was simulated against all 1,716 real backup records: **0 false positives**, rejects exactly the 2 known-bad records. See review §Regression Risk Analysis.

## Subtasks

| ID | Title | File | Status |
|---|---|---|---|
| [TASK-DKW-001](TASK-DKW-001-add-message-structure-gate.md) | Add message-structure validation gate to write_output tool | [src/tools/write_output.py](../../../src/tools/write_output.py) | backlog |
| [TASK-DKW-002](TASK-DKW-002-regression-tests.md) | Regression tests for write_output message-structure gate | [src/tools/tests/test_write_output.py](../../../src/tools/tests/test_write_output.py) | backlog |

See [IMPLEMENTATION-GUIDE.md](IMPLEMENTATION-GUIDE.md) for execution order and validation checklist.

## Non-goals

- Changes to Player or Coach prompts
- Replacing `write_output`'s ad-hoc validation with `TrainingExample.model_validate` (deferred as optional TASK-DKW-003)
- Rewriting historical `output/train.jsonl` (training-script workaround handles it)

## References

- Review report: [.claude/reviews/TASK-REV-4AA0-review-report.md](../../../.claude/reviews/TASK-REV-4AA0-review-report.md)
- Original bug report: [docs/reviews/training-1/TASK-REV-dataset-key-whitespace-bug.md](../../../docs/reviews/training-1/TASK-REV-dataset-key-whitespace-bug.md)
- Affected records (in backup): `output_backup_run1/train.jsonl` lines 1145 and 1330
