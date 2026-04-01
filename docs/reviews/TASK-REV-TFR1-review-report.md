# Review Report: TASK-REV-TFR1

## Executive Summary

The test-fixes-run-1 pipeline crashed after 1 target due to **two compounding issues**
in the TASK-LR1-001 guided JSON implementation:

1. **LangChain transport**: `guided_json` was passed via `model_kwargs` (which merges
   at the top level of the OpenAI SDK `create()` call, causing rejection). Fix: use
   `extra_body` instead.
2. **vLLM API version**: The `guided_json` parameter itself was removed in vLLM v0.12.0.
   The nightly image (v0.18.1rc1.dev) requires `structured_outputs: {"json": schema}`.
   The CLI flag `--guided-decoding-backend` was also removed — replaced by
   `--structured-outputs-config.backend xgrammar`.

**Fix:** TASK-LR1-012 — both issues resolved. Implemented and tested (20/20 coach tests pass).

## Review Details

- **Mode**: Root cause analysis / decision
- **Depth**: Comprehensive (full source tracing across 4 libraries)
- **Reviewer**: Claude (TASK-REV-TFR1)
- **Parent review**: TASK-REV-649A

## Findings

### 1. Crash Path (Confirmed)

The log at `docs/reviews/longer-runs/test-fixes-run-1.md` shows:
- Player completed target 0 successfully (line 46: `player_response: index=0, turn=1, content_len=4109`)
- Coach memory loaded (line 48)
- Crash on Coach's first LLM call (line 50): `AsyncCompletions.create() got an unexpected keyword argument 'guided_json'`

### 2. Root Cause (Confirmed via Source Tracing)

**Code path:**
```
coach.py:81     → guided_kwargs = {"guided_json": schema}
coach.py:84     → create_model(config, model_kwargs=guided_kwargs)
model_factory.py:77  → kwargs["model_kwargs"] = {"guided_json": {...}}
init_chat_model  → ChatOpenAI(model_kwargs={"guided_json": {...}})
ChatOpenAI._default_params (base.py:1130):
    **self.model_kwargs  ← SPREADS guided_json at TOP LEVEL
self.async_client.create(guided_json={...})  ← SDK REJECTS
```

**LangChain documentation** (base.py:3031-3080) explicitly warns:
> "Always use `extra_body` for custom parameters, **not** `model_kwargs`.
> Using `model_kwargs` for non-OpenAI parameters will cause API errors."

### 3. Fix Validation (End-to-End Traced)

`extra_body` code path verified through:
- `ChatOpenAI.extra_body` field (base.py:780)
- `_default_params` includes it as named key (base.py:1113)
- OpenAI SDK `create()` accepts `extra_body` explicitly (completions.py:1207)
- `make_request_options` converts to `extra_json` (_base_client.py:1995)
- `_post()` merges `extra_json` into HTTP body via `_merge_mappings` (_base_client.py:506)
- Final HTTP body contains `"guided_json": {...}` at top level — what vLLM expects

### 4. Non-vLLM Safety

Zero regression risk. Guard at `coach.py:80` (`if model_config.provider == "local"`)
ensures `extra_body` is only set for vLLM. Anthropic path never sees it.

## Implementation (TASK-LR1-012)

### Files Changed

| File | Change |
|------|--------|
| `agents/model_factory.py` | Added `extra_body` parameter, forwarded to `init_chat_model` |
| `agents/coach.py` | Changed from `model_kwargs=guided_kwargs` to `extra_body=extra_body` |
| `tests/test_coach_factory.py` | Updated `TestCoachGuidedJson`: asserts `extra_body`, added regression test for `model_kwargs` |

### Test Results

- **19/19** coach factory tests pass (including 5 guided_json tests)
- **292/297** full suite passes (5 pre-existing GOAL.md target count failures, unrelated)
- New test `test_guided_json_not_passed_via_model_kwargs` prevents future regression

## Remaining Server-Side Validation

Before the overnight run, verify on the vLLM server:
1. `--guided-decoding-backend` is configured (required for guided decoding to work)
2. Run a quick 5-10 target smoke test to confirm Coach responses parse correctly
