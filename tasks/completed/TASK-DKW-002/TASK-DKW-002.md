---
id: TASK-DKW-002
title: Regression tests for write_output message-structure gate
status: completed
created: 2026-04-11T00:00:00Z
updated: 2026-04-11T00:00:00Z
completed: 2026-04-11T00:00:00Z
completed_location: tasks/completed/TASK-DKW-002/
priority: high
tags: [dataset-factory, write-output, testing, bug-fix]
task_type: implementation
complexity: 2
parent_review: TASK-REV-4AA0
feature_id: FEAT-DKW
wave: 1
implementation_mode: direct
dependencies: [TASK-DKW-001]
test_results:
  status: passing
  coverage: "97% (src/tools/write_output.py)"
  last_run: 2026-04-11
  total: 75
  passed: 75
  failed: 0
---

# Task: Regression tests for write_output message-structure gate

## Parent Review

[TASK-REV-4AA0](../TASK-REV-4AA0-fix-dataset-key-whitespace-bug.md) — see full analysis in [.claude/reviews/TASK-REV-4AA0-review-report.md](../../../.claude/reviews/TASK-REV-4AA0-review-report.md).

## Purpose

Lock in the behaviour introduced by TASK-DKW-001 with regression tests covering the exact production defect plus closely related key-shape failure modes. One of the tests uses the verbatim corrupted-record shape observed in `output_backup_run1/train.jsonl` lines 1145 and 1330.

## Scope

Add tests to [src/tools/tests/test_write_output.py](../../../src/tools/tests/test_write_output.py) inside the existing `TestValidationChain` class (following the `test_step3_first_message_not_system_rejected` style). Do NOT modify existing tests.

## Test Cases to Add

All tests should use the existing `write_tool` fixture and `output_dir` fixture where a successful write is expected.

1. **`test_step2b_leading_space_in_role_key_rejected`** — The primary regression test. Uses the exact shape observed in production: a 5-message conversation where `messages[3]` has key `" role"` (leading space). Assert error contains `messages[3]`, `invalid keys`, and `' role'`.

2. **`test_step2b_trailing_space_in_role_key_rejected`** — `{"role ": "user", "content": "x"}`. Assert rejection.

3. **`test_step2b_uppercase_role_key_rejected`** — `{"Role": "user", "content": "x"}`. Assert rejection (unexpected+missing).

4. **`test_step2b_unexpected_extra_key_rejected`** — `{"role": "user", "content": "x", "speaker": "alice"}`. Assert rejection names `speaker` as unexpected.

5. **`test_step2b_missing_content_key_rejected`** — `{"role": "user"}`. Assert rejection names `content` as missing.

6. **`test_step2b_missing_role_key_rejected`** — `{"content": "x"}`. Assert rejection names `role` as missing.

7. **`test_step2b_non_dict_message_rejected`** — `messages[1] = "not a dict"`. Assert error: `messages[1] is not an object`.

8. **`test_step2b_invalid_role_value_rejected`** — `{"role": "tool", "content": "x"}`. Assert error names `tool` as invalid role value and expected values listed.

9. **`test_step2b_valid_5_message_conversation_accepted`** — Happy-path guard. A proper 5-message reasoning example (system, user, assistant with `<think>`, user, assistant with `<think>`) must pass through the new gate and be written successfully. Read back the file and assert all 5 message dicts have exactly `{"role","content"}` keys.

## Structure Reference

The test for (1) should look approximately like:

```python
def test_step2b_leading_space_in_role_key_rejected(self, write_tool):
    """Regression for TASK-REV-4AA0: ' role' key (leading space) is rejected.

    Reproduces the defect observed in output_backup_run1/train.jsonl
    lines 1145 and 1330, where the Player LLM hallucinated a leading
    space inside the role key of messages[3].
    """
    example = {
        "messages": [
            {"role": "system", "content": "sys"},
            {"role": "user", "content": "first turn question"},
            {"role": "assistant", "content": "first turn answer"},
            {" role": "user", "content": "follow-up question"},  # ← bug
            {"role": "assistant", "content": "follow-up answer"},
        ],
        "metadata": {
            "layer": "behaviour",
            "type": "direct",
            "text": "macbeth",
        },
    }
    result = write_tool.invoke(json.dumps(example))
    assert "messages[3]" in result
    assert "invalid keys" in result
    assert " role" in result
```

## Acceptance Criteria

- [ ] All 9 test cases listed above implemented in `TestValidationChain`
- [ ] All tests follow project style: AAA pattern, `test_<method>_<scenario>_<result>` naming
- [ ] Happy-path test reads back from disk and asserts structural correctness
- [ ] `pytest src/tools/tests/test_write_output.py -v` passes (old + new tests)
- [ ] Coverage delta shows the new step 2b branches exercised (unexpected, missing, non-dict, invalid-role-value)
- [ ] `ruff` / `black` clean

## Dependencies

Depends on **TASK-DKW-001** landing first (the gate must exist for the tests to pass).

## Out of Scope

- Testing step 3-10 changes — no functional changes to those steps
- Performance benchmarks
- Integration tests against the real Player (covered by existing smoke tests)

## References

- [src/tools/tests/test_write_output.py:266](../../../src/tools/tests/test_write_output.py#L266) — `TestValidationChain` location
- [.claude/rules/testing.md](../../../.claude/rules/testing.md) — project testing conventions (pytest, AAA, naming)
- [.claude/reviews/TASK-REV-4AA0-review-report.md](../../../.claude/reviews/TASK-REV-4AA0-review-report.md) §R2
