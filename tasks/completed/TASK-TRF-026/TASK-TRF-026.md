---
id: TASK-TRF-026
title: Add reasoning_content fallback to _extract_player_content
status: completed
completed: 2026-03-27T17:05:00Z
created: 2026-03-27T16:00:00Z
updated: 2026-03-27T17:05:00Z
priority: medium
tags: [generation-loop, defence-in-depth, eighth-run]
complexity: 2
parent_review: TASK-REV-TRF8
feature_id: FEAT-TRF8
depends_on: [TASK-TRF-024]
wave: 2
implementation_mode: task-work
completed_location: tasks/completed/TASK-TRF-026/
test_results:
  status: passed
  coverage: null
  last_run: 2026-03-27T17:05:00Z
  tests_passed: 66
  tests_failed: 0
---

# Task: Add reasoning_content Fallback to _extract_player_content

## Problem

`_extract_coach_content` (generation_loop.py:394-466) has a 4-source fallback including Path 4: `additional_kwargs["reasoning_content"]` for vLLM think-mode. This was added after TASK-REV-TRF5 discovered Coach verdicts were lost inside think blocks.

`_extract_player_content` (generation_loop.py:169-217) lacks this fallback — it only checks:
1. `content` (string)
2. Content blocks list

If `--reasoning-parser` is ever re-enabled (or a different model server with similar behaviour is used), Player content would silently disappear.

## Fix

Add Path 3 (reasoning_content from additional_kwargs) and Path 4 (reasoning blocks from content list) to `_extract_player_content`, mirroring the Coach extractor. Additionally, when both `content` and `reasoning_content` are present, **concatenate them** (think block + generation output).

```python
# Path 3: Content blocks list — look for reasoning blocks
if isinstance(content, list):
    reasoning_parts = [
        block.get("text", "") or block.get("content", "")
        for block in content
        if isinstance(block, dict) and block.get("type") == "reasoning"
    ]
    combined_reasoning = "".join(reasoning_parts).strip()
    if combined_reasoning:
        logger.info("player_content_source: content list (reasoning blocks)")
        return combined_reasoning

# Path 4: additional_kwargs.reasoning_content (vLLM think-mode)
additional_kwargs = getattr(last_msg, "additional_kwargs", None) or {}
reasoning_content = additional_kwargs.get("reasoning_content", "")
if isinstance(reasoning_content, str) and reasoning_content.strip():
    # If content is also present, concatenate: think + content
    base_content = content if isinstance(content, str) and content.strip() else ""
    if base_content:
        combined = f"<think>{reasoning_content}</think>\n\n{base_content}"
        logger.info(
            "player_content_source: content + reasoning_content merged, len=%d",
            len(combined),
        )
        return combined
    logger.info(
        "player_content_source: additional_kwargs.reasoning_content "
        "(vLLM think-mode fallback), len=%d",
        len(reasoning_content),
    )
    return reasoning_content
```

## Files to Modify

- `entrypoint/generation_loop.py` (`_extract_player_content`, lines 169-217)
- `entrypoint/tests/test_generation_loop.py` (add new tests)

## Acceptance Criteria

- [ ] `_extract_player_content` checks `additional_kwargs["reasoning_content"]`
- [ ] When both `content` and `reasoning_content` present, merges them with `<think>` wrapper
- [ ] When only `reasoning_content` present, returns it directly
- [ ] Existing tests pass unchanged
- [ ] New test: empty content + reasoning_content returns reasoning_content
- [ ] New test: content + reasoning_content returns merged result
- [ ] New test: content only (no reasoning_content) returns content unchanged

## Note

This is a **defence-in-depth** fix. TASK-TRF-024 (removing `--reasoning-parser`) is the primary fix. This task ensures the Player extractor is robust against future configuration changes.
