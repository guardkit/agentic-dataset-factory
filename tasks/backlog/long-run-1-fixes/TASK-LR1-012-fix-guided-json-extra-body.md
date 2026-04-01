---
id: TASK-LR1-012
title: Fix guided_json to use extra_body instead of model_kwargs
status: in_progress
created: 2026-03-31T00:00:00Z
updated: 2026-03-31T00:00:00Z
priority: critical
tags: [pipeline-fix, coach, guided-json, vllm, regression]
complexity: 2
parent_review: TASK-REV-TFR1
feature_id: FEAT-LR1
wave: 1
implementation_mode: task-work
dependencies: []
---

# Task: Fix guided_json to use extra_body instead of model_kwargs

## Description

TASK-LR1-001 introduced `guided_json` for the Coach agent to constrain vLLM output
to valid CoachVerdict JSON. However, it passes the schema via LangChain's `model_kwargs`,
which merges it as a top-level keyword argument to the OpenAI SDK's
`AsyncCompletions.create()`. The SDK rejects unknown top-level parameters, crashing
the pipeline after the first Player turn completes.

The fix: use `extra_body` instead, which LangChain and the OpenAI SDK both support
as the correct mechanism for vendor-specific parameters (vLLM, LM Studio, etc.).

## Root Cause (from TASK-REV-TFR1)

- `model_kwargs` items are **spread into the top-level** request payload
  (`langchain_openai/chat_models/base.py:1130`)
- `extra_body` is passed as a **named key** that the OpenAI SDK explicitly accepts
  (`completions.py:1207`) and merges into the HTTP body (`_base_client.py:506`)
- LangChain docs explicitly warn: "Always use `extra_body` for custom parameters,
  **not** `model_kwargs`" (base.py:3031-3080)

## Scope

- [x] Add `extra_body` parameter to `create_model()` in `agents/model_factory.py`
- [x] Change `coach.py` to pass `extra_body=` instead of `model_kwargs=`
- [x] Update `TestCoachGuidedJson` tests to assert `extra_body` kwarg
- [x] Run full test suite — zero regressions

## Acceptance Criteria

- [x] Coach LLM calls use `extra_body={"guided_json": schema}` (not `model_kwargs`)
- [x] Player LLM calls are unchanged
- [x] Anthropic provider path is unaffected (`extra_body` is `None` when not local)
- [x] All existing tests pass
- [ ] Pipeline completes at least 10 targets without `guided_json` crash *(requires live run)*

## Key Files

- `agents/model_factory.py` — add `extra_body` parameter
- `agents/coach.py` — use `extra_body` instead of `model_kwargs`
- `tests/test_coach_factory.py` — update `TestCoachGuidedJson` assertions
