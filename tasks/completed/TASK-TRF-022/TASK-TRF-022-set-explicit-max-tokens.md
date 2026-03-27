---
id: TASK-TRF-022
title: Set explicit max_tokens on Player and Coach models
status: completed
created: 2026-03-27T12:00:00Z
updated: 2026-03-27T15:05:00Z
completed: 2026-03-27T15:05:00Z
priority: high
tags: [config, model-factory, seventh-run]
complexity: 2
parent_review: TASK-REV-TRF7
feature_id: FEAT-TRF7
depends_on: []
wave: 1
implementation_mode: task-work
test_results:
  status: passed
  coverage: null
  last_run: 2026-03-27T15:00:00Z
  total: 21
  passed: 21
  failed: 0
---

# Task: Set Explicit max_tokens on Player and Coach Models

## Problem

Neither the Player nor Coach model has an explicit `max_tokens` parameter set. The model factory (`agents/model_factory.py:75`) calls `init_chat_model()` with only `temperature` and optional `base_url`. The vLLM server's default `max_tokens` applies, which may silently truncate Player responses.

Run 7 shows Player completion_tokens of 940, 957, 899 per turn. A full training example JSON with system prompt, user question, and assistant response containing a `<think>` block may require more than ~1000 tokens. If vLLM defaults to 1024, responses would be truncated mid-JSON.

Token budget is only 8.6% utilised (28K / 262K), so there is ample room for larger completions.

## Fix

Add `max_tokens` to the model creation. This can be done via `model_kwargs` in `init_chat_model` or by passing it directly:

```python
# In model_factory.py or at the call site:
kwargs["max_tokens"] = config.max_tokens  # Add to ModelConfig, default 4096
```

Alternatively, pass it at the agent level if `init_chat_model` doesn't support it directly for OpenAI-compatible endpoints.

## Acceptance Criteria

- [x] `max_tokens` is explicitly set (default 4096) for both Player and Coach models
- [x] `ModelConfig` updated with optional `max_tokens` field (default 4096)
- [x] Existing tests still pass
- [x] New test: verify `max_tokens` is passed through to the model

## Files to Modify

- `config/models.py` (add `max_tokens` field to `ModelConfig`)
- `agents/model_factory.py` (pass `max_tokens` to `init_chat_model`)
- `tests/test_player_factory.py` (verify max_tokens propagation)
