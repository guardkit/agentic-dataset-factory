---
id: TASK-OR-004
title: Structured output opt-in toggle for Coach (experimental)
status: backlog
created: 2026-03-29T00:00:00Z
updated: 2026-03-29T11:00:00Z
priority: medium
tags: [structured-output, coach, vllm, experimental, overnight-readiness]
task_type: implementation
complexity: 6
parent_review: TASK-REV-7617
feature_id: FEAT-OR
depends_on: [TASK-OR-001, TASK-OR-006]
wave: 2
implementation_mode: task-work
test_results:
  status: pending
  coverage: null
  last_run: null
---

# Task: Structured Output Opt-In Toggle for Coach (Experimental)

## Problem

Coach role confusion causes 15% rejection rate. TASK-OR-001 (retry with JSON
reinforcement) addresses this with a single retry, but structured output could
eliminate the class of failures entirely by constraining Coach output at the
token level via vLLM's xgrammar guided decoding.

## Risk Assessment

**This is experimental.** The NVIDIA GB10 forum has zero confirmed reports of
json_schema mode working on GB10. Known vLLM bugs affecting Qwen3.5:
- #35700: Structured output fails with MTP enabled
- #27447: enable_thinking=False breaks guided decoding for some variants
- #23404: Field descriptions ignored in schema

**Critical constraint**: Coach reasoning must stay ENABLED (Run 5 decision).
This means structured output must work alongside reasoning mode, requiring
`--structured-outputs-config enable_in_reasoning=true` on the vLLM server.

**Note (TASK-REV-R2A1)**: TASK-OR-001 has a message format bug (dual system
messages in `ainvoke()` input) fixed by TASK-OR-006. Even if structured output
eliminates Coach parse failures entirely, the retry path must still be fixed as
a fallback. Structured output is NOT a shortcut to avoid TASK-OR-006.

## Solution

Add an opt-in `structured_output_schema` field to `ModelConfig`. When set for
Coach, use LangChain's `model.with_structured_output()` with `include_raw=True`
for graceful fallback to the existing 3-tier extraction.

## Implementation

### 1. Extend ModelConfig

In `config/models.py`:

```python
class ModelConfig(BaseModel):
    # ... existing fields ...
    structured_output_schema: str | None = Field(
        default=None,
        description=(
            "Optional Pydantic model name for structured output "
            "(e.g. 'CoachVerdict'). When set, model.with_structured_output() "
            "is applied with method='json_schema' and include_raw=True."
        )
    )
```

### 2. Create Structured Model Factory

In `agents/model_factory.py`:

```python
_SCHEMA_REGISTRY: dict[str, type[BaseModel]] = {}

def register_schema(name: str, schema: type[BaseModel]) -> None:
    _SCHEMA_REGISTRY[name] = schema

def create_model(config: ModelConfig) -> BaseChatModel:
    # ... existing logic ...
    model = init_chat_model(config.model, **kwargs)

    if config.structured_output_schema:
        schema = _SCHEMA_REGISTRY.get(config.structured_output_schema)
        if schema is None:
            raise ValueError(
                f"Unknown structured output schema: {config.structured_output_schema}. "
                f"Available: {sorted(_SCHEMA_REGISTRY)}"
            )
        model = model.with_structured_output(
            schema, method="json_schema", include_raw=True
        )
        logger.info(
            "Structured output enabled: schema=%s, method=json_schema",
            config.structured_output_schema,
        )

    return model
```

Register CoachVerdict at module level:
```python
from config.coach_verdict import CoachVerdict
register_schema("CoachVerdict", CoachVerdict)
```

### 3. Update Generation Loop

When structured output is enabled, the Coach response is a dict with
`{"parsed": CoachVerdict | None, "raw": AIMessage, "parsing_error": Exception | None}`.

Handle both paths:
```python
if structured_output_enabled:
    if response["parsing_error"]:
        # Fall back to existing 3-tier extraction
        coach_content = response["raw"].content
        verdict = _parse_coach_verdict(coach_content)
    else:
        verdict = response["parsed"]
else:
    # Existing path unchanged
    coach_content = _extract_coach_content(coach_response)
    verdict = _parse_coach_verdict(coach_content)
```

### 4. Update vLLM Launch Config

Add to Docker/launch script:
```bash
--structured-outputs-config enable_in_reasoning=true
```

### 5. Config (disabled by default)

```yaml
coach:
  provider: local
  model: Qwen/Qwen3.5-35B-A3B-FP8
  endpoint: http://promaxgb10-41b1:8002/v1
  temperature: 0.3
  # structured_output_schema: CoachVerdict  # UNCOMMENT after validation
```

## Validation Protocol (MUST complete before enabling)

1. Add `enable_in_reasoning=true` to vLLM config
2. Restart vLLM container
3. Enable `structured_output_schema: CoachVerdict` in agent-config.yaml
4. Run 20 targets at count=1
5. Compare results to baseline Run 12:
   - Rejection rate (baseline: 20%)
   - Verdict quality (score distribution, quality_assessment detail)
   - Coach response times (any slowdown from guided decoding?)
6. If improved or equal → approved for overnight
7. If degraded or unstable → disable, rely on TASK-OR-001 retry

## CoachVerdict Schema Compatibility Note

The `criteria_met: dict[str, bool]` field uses dynamic keys. xgrammar may not
handle this natively and could fall back to the outlines backend. If this causes
issues, consider changing `criteria_met` to `list[CriterionResult]` with named
fields — but this is a schema change that affects Coach prompt and parsing.
Defer unless needed.

## Files to Modify

- `config/models.py` — Add `structured_output_schema` to ModelConfig
- `agents/model_factory.py` — Schema registry + conditional `with_structured_output`
- `entrypoint/generation_loop.py` — Handle structured output response format
- vLLM launch script — Add `enable_in_reasoning=true`
- `agent-config.yaml` — Add commented-out `structured_output_schema`

## Acceptance Criteria

- [ ] `structured_output_schema` field added to ModelConfig (optional, default None)
- [ ] Schema registry maps string names to Pydantic models
- [ ] Coach uses `with_structured_output()` when schema configured
- [ ] `include_raw=True` enables fallback to 3-tier extraction
- [ ] Disabled by default (commented out in config)
- [ ] Coach reasoning stays enabled (no `enable_thinking` changes)
- [ ] Existing tests pass with structured output disabled
- [ ] Validation run protocol documented and executable
- [ ] vLLM config change documented

## Test Requirements

- Unit test: ModelConfig accepts structured_output_schema field
- Unit test: create_model returns structured model when schema set
- Unit test: create_model returns normal model when schema is None
- Unit test: schema registry lookup raises ValueError for unknown schema
- Unit test: generation loop handles structured response dict format
- Unit test: generation loop falls back to 3-tier on parsing_error
