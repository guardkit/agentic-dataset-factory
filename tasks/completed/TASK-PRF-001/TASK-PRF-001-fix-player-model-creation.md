---
id: TASK-PRF-001
title: Fix Player create_model to use shared model_factory
status: completed
created: 2026-03-22T00:00:00Z
updated: 2026-03-22T00:00:00Z
completed: 2026-03-22T00:00:00Z
completed_location: tasks/completed/TASK-PRF-001/
priority: critical
tags: [bug-fix, player, model-factory, P0]
complexity: 2
parent_review: TASK-REV-A1B4
feature_id: FEAT-PRF
wave: 1
implementation_mode: task-work
dependencies: []
test_results:
  status: passed
  coverage: null
  last_run: 2026-03-22T00:00:00Z
---

# Task: Fix Player create_model to Use Shared model_factory

## Description

The Player agent's local `create_model()` function in `agents/player.py` returns a raw string `"provider:model"` (e.g. `"local:Qwen/Qwen3-Coder-Next-FP8"`). The `"local"` prefix is NOT a valid `init_chat_model` provider — it only accepts `"openai"`, `"anthropic"`, etc. This blocks Player instantiation with `provider: local`.

The Coach already correctly uses `from agents.model_factory import create_model` which maps `local` → `openai` with `base_url`.

## Files to Modify

- `agents/player.py`

## Changes

1. Remove the local `create_model()` function (lines 25-39)
2. Add `from agents.model_factory import create_model` (same as `coach.py` line 25)
3. No changes needed to `create_player()` body — it already passes `model` to `create_deep_agent()`

## Acceptance Criteria

- [x] `create_player()` uses `model_factory.create_model()` which returns `BaseChatModel`
- [x] Both Player and Coach pass `BaseChatModel` to `create_deep_agent(model=...)`
- [x] Player with `provider: local` and `endpoint: http://localhost:8002/v1` creates a valid model
- [x] Existing tests in `agents/tests/test_player.py` updated and pass (mock return type changes from `str` to `BaseChatModel`)

## Notes

- The return type changes from `str` to `BaseChatModel` — tests mocking `create_model` will need updating
- This is a confirmed bug verified against DeepAgents SDK docs

## Test Execution Log

[Automatically populated by /task-work]
