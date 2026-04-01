---
id: TASK-FPF1-002
title: Harden format gate with required-key validation
status: completed
created: 2026-03-31T00:00:00Z
updated: 2026-03-31T00:00:00Z
completed: 2026-03-31T00:00:00Z
priority: high
tags: [format-gate, validation, generation-loop, regression-fix]
complexity: 3
task_type: implementation
parent_review: TASK-REV-FPF1
feature_id: FEAT-FPF1
wave: 1
implementation_mode: task-work
dependencies: []
test_results:
  status: passed
  coverage: null
  last_run: 2026-03-31T00:00:00Z
  tests_passed: 7
  tests_failed: 0
---

# Task: Harden format gate with required-key validation

## Description

The format gate at `generation_loop.py:705-726` currently only checks whether
`_extract_json_object()` can find ANY valid JSON dict in the Player's output. This
is insufficient because:

1. The brace-matching extractor (Try 3) returns the FIRST valid JSON object
2. If the Player outputs `{"messages": [...]}` as a standalone object with metadata
   in a separate block, the extractor returns only the messages portion
3. This passes the format gate, Coach accepts the quality, but write validation
   catches "Missing required field 'metadata'" — wasting a turn

Evidence from TASK-REV-FPF1: 12 cases where extraction succeeded but JSON lacked
metadata (avg JSON ratio 60.5%, one extreme case: 33 chars extracted from 8421).

## Changes Required

### File: `entrypoint/generation_loop.py`

**Current code** (lines 705-726):
```python
try:
    _extract_json_object(player_content)
except ValueError:
    logger.warning(
        "Pre-Coach format gate: Player output is not valid JSON ..."
    )
    # ... format error feedback ...
    continue
```

**Proposed change:**
```python
try:
    extracted = _extract_json_object(player_content)
    data = json.loads(extracted)
    if "messages" not in data or "metadata" not in data:
        raise ValueError(
            f"JSON missing required top-level keys "
            f"(has: {sorted(data.keys())})"
        )
except ValueError as exc:
    logger.warning(
        "Pre-Coach format gate: Player output is not valid JSON "
        "(index=%d, turn=%d, content_len=%d, reason=%s). Skipping Coach.",
        target_index,
        turn + 1,
        len(player_content),
        exc,
    )
    rejection_history.append(
        {"format_gate": "player_output_not_json", "turn": turn + 1,
         "reason": str(exc)}
    )
    coach_feedback = (
        "FORMAT ERROR: Your previous response could not be parsed "
        "as a valid JSON object with both 'messages' and 'metadata' "
        "top-level keys. You MUST respond with ONLY a raw JSON object "
        "containing both 'messages' (array) and 'metadata' (object). "
        "Start your response with { and end with }. "
        "Do NOT include any text before or after the JSON. "
        "Do NOT output messages and metadata as separate JSON objects."
    )
    continue
```

Key changes:
1. Parse the extracted JSON and check for `messages` AND `metadata` keys
2. Include the missing-key info in the warning log for diagnostics
3. Update the FORMAT ERROR feedback to explicitly mention both required keys
4. Tell the Player not to split them into separate JSON objects

## Acceptance Criteria

- [ ] Format gate checks for both `messages` and `metadata` keys in extracted JSON
- [ ] Log message includes reason for rejection (missing keys listed)
- [ ] FORMAT ERROR feedback mentions both required top-level keys
- [ ] rejection_history includes reason field
- [ ] Existing tests pass (format gate tests may need updates)
- [ ] New test: verify format gate rejects `{"messages": [...]}` without metadata
- [ ] New test: verify format gate rejects `{"metadata": {...}}` without messages
- [ ] New test: verify format gate accepts `{"messages": [...], "metadata": {...}}`
- [ ] New test: verify format gate still rejects non-JSON (prose-only) content

## Key Files

- `entrypoint/generation_loop.py` (lines 705-726)
- Test file for generation loop (create if not exists, or add to existing)

## Notes

This fix is independent of TASK-FPF1-001 (prompt revert) and can be implemented
in parallel. Even after the prompt revert, this hardening prevents future regressions
where the Player might produce incomplete JSON.
