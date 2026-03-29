# Review Report: TASK-REV-7617 (Revised v3 — History-Aware)

## Executive Summary

Two longer runs were analysed: a 20-target pipeline execution (factory-run-1) and Docker vLLM startup logs (docker-run-1). The pipeline achieved an **80% acceptance rate** (16/20), producing 13 behaviour examples and 3 knowledge examples. Infrastructure is healthy.

**Revision v3** adds a complete audit of all prior decisions across 12 runs to ensure no regressions. The key constraint discovered: **the Run 5 review explicitly rejected `enable_thinking: false` for Coach** because "the original architecture deliberately chose a reasoning model because the Coach needs to reason deeply about example quality. Disabling thinking entirely would degrade evaluation quality." This was classified as the **"last resort"** option.

This changes the recommendation significantly. The layered strategy must respect the established architectural decisions.

---

## Prior Decision Audit

### Complete Think-Block / Reasoning Timeline (Runs 1-12)

| Run | Event | Decision | Task | Status |
|-----|-------|----------|------|--------|
| 5 | vLLM `--reasoning-parser qwen3` strips Coach JSON into `reasoning_content` | Add `reasoning_content` fallback to `_extract_coach_content()` | TRF-013 | **DONE** |
| 5 | Considered `enable_thinking: false` for Coach | **REJECTED** — "last resort; sacrifices Coach reasoning quality; counter to architectural intent" | TASK-REV-TRF5 | **DECIDED: NO** |
| 5 | Considered separate vLLM endpoints for Coach | Deferred — doubles infrastructure | TASK-REV-TRF5 | **DEFERRED** |
| 7 | 94% of `<think>` blocks unclosed | Call `normalise_think_closing_tags()` before JSON extraction | TRF-020, TRF-021 | **DONE** |
| 8 | `--reasoning-parser qwen3` strips Layer 2 think blocks from training data | **REMOVE** `--reasoning-parser qwen3` from vLLM | TRF-024 | **DONE** |
| 8 | String-aware brace matching for JSON extraction | Fix `_extract_json_object()` | TRF-025 | **DONE** |
| 9 | Coach returns Player-like prose; `ValueError` not caught | Add `ValueError` to per-target exception handler | NRF-12C1 | **DONE** |
| 9 | Consider stripping Player's Layer 1 thinking before Coach | **WITHDRAWN** — "adds complexity for marginal gain; pipeline handles rejections gracefully" | TASK-REV-1F3F R2 | **DECIDED: NO** |
| 9 | Coach verdict retry logic | **DEFERRED** — "over-engineering for ~5% failure rate; revisit if >5% in production" | TASK-REV-1F3F R3 | **DEFERRED** |
| 9 | vLLM structured output for Coach | **KEPT as P2** — "only if rejection rate >5% in production" | TASK-REV-1F3F R4 | **PENDING** |
| 10 | Think block format instruction added to Player prompt | Explicit `<think>` format guidance | TRF-029 | **DONE** |
| 10 | Coach validates think block presence | Coach prompt checks `<think>` before accepting | TRF-027 | **DONE** |

### Current Production State (Post Run 12)

| Component | State | Evidence |
|-----------|-------|---------|
| vLLM `--reasoning-parser` | **DISABLED** (TRF-024) | Docker logs confirm not in launch args |
| `enable_thinking` for Coach | **NOT CHANGED** — reasoning enabled for both Player and Coach | agent-config.yaml has no `extra_model_kwargs` |
| `ValueError` exception handler | **FIXED** (NRF-12C1) | `generation_loop.py:1011` catches ValueError |
| Think block normalization | **ACTIVE** (TRF-020/021) | Called before JSON extraction |
| 4-source Coach content extraction | **ACTIVE** (TRF-013 + extensions) | Paths 1-4 in `_extract_coach_content()` |
| Structured output | **NOT IMPLEMENTED** | No `response_format` or `with_structured_output` anywhere |
| Coach retry on parse failure | **NOT IMPLEMENTED** | Deferred per TASK-REV-1F3F |

### Decisions That Must Be Respected

1. **DO NOT disable Coach reasoning** without strong evidence that evaluation quality is maintained. Run 5 review explicitly rejected this.
2. **DO NOT strip Player's Layer 1 thinking before Coach**. Run 9 review withdrew this recommendation.
3. **DO NOT re-enable `--reasoning-parser qwen3`**. Run 8 proved this breaks Layer 2 think blocks in training data.
4. Coach retry / structured output are **allowed but conditional** — Run 9 said "only if failure rate >5% in production".

---

## The Key Question: Is 15% Rejection Rate > 5% Threshold?

**Yes.** Run 12 (factory-run-1) shows **4/20 = 20% rejection rate**, with 3/20 (15%) due to Coach role confusion. This **exceeds the 5% threshold** set in TASK-REV-1F3F R3/R4 as the trigger for revisiting mitigation options.

The Run 9 review based its 5% estimate on 2/20 targets (Run 9 crashed after 2, one of which failed). Run 12's larger sample confirms the rate is higher than estimated.

**This means R3 (Coach retry) and R4 (structured output) are now activated as valid options to explore — but `enable_thinking: false` remains the "last resort" per Run 5.**

---

## Finding F1: Revised Recommendation (History-Aware)

### What We Know From 12 Runs

1. Coach role confusion is **stochastic** (~15% per-target probability on reasoning-type targets)
2. It correlates with Player Layer 1 `<think>` blocks that read like task instructions
3. Direct-type targets have **0% failure rate** (6/6 in Run 12) — no Layer 1 think blocks
4. The Coach successfully evaluates 85% of targets including those with Layer 1 think blocks
5. The pipeline handles failures gracefully post NRF-12C1

### Options (Ordered by Architectural Alignment)

#### Option A: Coach Verdict Retry with JSON Reinforcement (RECOMMENDED)

**Aligns with**: TASK-REV-1F3F R3 (previously deferred, now activated by >5% threshold)

When `_parse_coach_verdict()` raises `ValueError`, retry **once** with an explicit system message reinforcement:

```python
# In the generation loop, after Coach JSON parse failure:
if coach_parse_failed and retry_count == 0:
    # Re-invoke Coach with JSON-only reminder prepended
    reinforcement = (
        "IMPORTANT: Your previous response was not valid JSON. "
        "You MUST respond with ONLY a JSON object matching the "
        "CoachVerdict schema. No prose, no reasoning, no markdown. "
        "Start with { and end with }."
    )
    coach_input["messages"].insert(0, {"role": "system", "content": reinforcement})
    coach_response = await _invoke_with_retry(coach, coach_input, ...)
```

**Why this respects prior decisions**:
- Coach reasoning stays enabled (respects Run 5 decision)
- Player content stays intact (respects Run 9 R2 withdrawal)
- Adds one retry, not a full retry loop (minimal complexity)
- Only triggers on parse failure, not on every call

**Expected impact**: Should recover 2/3 of the current failures (the Coach "snaps out of it" with explicit reinforcement). Reduces rejection from ~15% to ~5%.

**Cost**: One extra Coach LLM call per failure (~15% of targets = ~3 tokens overhead per 20 targets).

**Effort**: 2-3 hours.

#### Option B: Structured Output via `with_structured_output()` (EXPERIMENTAL)

**Aligns with**: TASK-REV-1F3F R4 (kept as P2, now activated)

**NVIDIA GB10 forum status**: Structured output on Qwen3.5 + GB10 is **unconfirmed in the community**. One thread says vLLM logs strict mode as "ignored". Multiple open vLLM bugs affect Qwen3.5 (#35700, #27447, #23404). Zero GB10 operators have reported `json_schema` mode working.

**LangChain approach**: `model.with_structured_output(CoachVerdict, method="json_schema", include_raw=True)` — triggers vLLM's xgrammar guided decoding for token-level schema enforcement.

**Critical question for this option**: Can we use structured output **while keeping reasoning enabled**?

The vLLM config shows `enable_in_reasoning=False` (default). To use structured output with a reasoning model requires:
1. Adding `--structured-outputs-config enable_in_reasoning=true` to vLLM launch
2. This tells xgrammar to only apply constraints AFTER `</think>` tag

**Known risk**: The `<think>` tag leakage bug (HF discussion #18) means reasoning content may leak into the structured output field, prepending `<think>...</think>` before the JSON. Our existing `_parse_coach_verdict()` 3-tier extraction would need to remain as fallback.

**Implementation (opt-in toggle)**:

Add to `ModelConfig`:
```python
structured_output_schema: str | None = Field(
    default=None,
    description="Pydantic model name for structured output (e.g. 'CoachVerdict')"
)
```

In `create_coach()`, conditionally bind:
```python
model = create_model(model_config)
if model_config.structured_output_schema:
    from config.coach_verdict import CoachVerdict
    model = model.with_structured_output(
        CoachVerdict, method="json_schema", include_raw=True
    )
```

**Config**:
```yaml
coach:
  provider: local
  model: Qwen/Qwen3.5-35B-A3B-FP8
  endpoint: http://promaxgb10-41b1:8002/v1
  temperature: 0.3
  # structured_output_schema: CoachVerdict  # UNCOMMENT after validation
```

**Validation protocol before enabling**:
1. Add `enable_in_reasoning=true` to vLLM config
2. Restart vLLM container
3. Run 20 targets at count=1 with structured output enabled
4. Compare rejection rate to baseline (current 20%)
5. If improved → enable for overnight
6. If degraded or unstable → disable, rely on Option A

**Effort**: 3-4 hours implementation + 34 min validation run.

#### Option C: Disable Coach Reasoning (LAST RESORT — NOT RECOMMENDED)

**Contradicts**: Run 5 review's explicit rejection of this approach.

**The Run 5 argument**: "The original architecture deliberately chose a reasoning model because the Coach needs to reason deeply about example quality. Disabling thinking entirely would degrade evaluation quality."

**Counter-argument from Run 12 data**: Looking at the actual Coach verdicts in this run, the accepted examples received scores of 4-5 with detailed quality assessments. The Coach IS using its reasoning to produce nuanced evaluations. Disabling this would reduce verdict quality to pattern-matching against criteria.

**However**: The GB10 forum confirms `enable_thinking: false` works for tool calling, and it IS the cleanest fix for role confusion. The question is whether Coach evaluation quality degrades.

**If pursued despite the prior decision**, this should be validated by comparing verdict quality:
1. Run 20 targets with reasoning enabled (current) — measure scores, verdict detail
2. Run 20 targets with reasoning disabled — compare scores, verdict detail
3. If verdict quality is comparable → reconsider the Run 5 decision
4. If verdict quality degrades → confirm Run 5 was right

**This is NOT recommended for the overnight run.** Use Option A instead.

---

## Finding F2: Grade Target Monoculture (Unchanged)

12/13 train.jsonl examples target Grade 7 (92.3%). Add `grade_targets` column to GOAL.md Generation Targets table. Orchestrator distributes examples across grades.

**Effort**: 3-4 hours. **No prior decision conflicts.**

---

## Finding F3 + F5: Structural Validation Rules (Unchanged)

Domain-level validation rules parsed from GOAL.md, enforced pre-Coach. Handles essay feedback multi-turn compliance and metadata-missing errors.

**Effort**: 4-5 hours. **No prior decision conflicts.**

---

## Revised Implementation Plan (History-Respecting)

### Priority Order

| Step | Task | Effort | Risk | Prior Decision Alignment |
|------|------|--------|------|-------------------------|
| 1 | **Option A**: Coach retry with JSON reinforcement | 2-3h | Low | Activates TASK-REV-1F3F R3 (threshold exceeded) |
| 2 | **R2**: Grade distribution in GOAL.md | 3-4h | Low | No conflicts |
| 3 | **R3**: Structural validation rules | 4-5h | Low | No conflicts |
| 4 | **Option B**: Structured output opt-in toggle | 3-4h | Medium | Activates TASK-REV-1F3F R4 (threshold exceeded) |
| 5 | **Validation run** | 34min | None | — |
| 6 | **Overnight config**: count=17 per category | Config | None | — |

**Total**: ~13-16h implementation + 34min validation

### Minimum Viable for Overnight (~6h)

1. **Option A** (Coach retry) — 2-3h, biggest impact on rejection rate
2. **R2** (grade distribution) — 3-4h, fixes training data quality
3. **Validation run** — 34min
4. **Overnight config** — 5min

**Expected rejection rate**: ~15% → ~5% (with retry recovering most failures)

### Post-Overnight Enhancements

5. **R3** (structural validation) — 4-5h
6. **Option B** (structured output) — 3-4h, requires separate validation
7. Post-run coverage monitoring

---

## What NOT to Do (Explicitly)

Based on the full history audit, these actions would risk regressions:

| Action | Why Not | Prior Decision |
|--------|---------|----------------|
| Disable Coach reasoning (`enable_thinking: false`) | Degrades evaluation quality; explicitly rejected in Run 5 as "counter to architectural intent" | TASK-REV-TRF5 |
| Strip Player Layer 1 thinking before Coach | Too fragile; adds complexity for marginal gain | TASK-REV-1F3F R2 (withdrawn) |
| Re-enable `--reasoning-parser qwen3` | Breaks Layer 2 think blocks in training data | TRF-024 |
| Change Player or Coach prompts | They're working correctly for 85% of targets | TASK-REV-1F3F |
| Add complex retry loops | Over-engineering; single retry with reinforcement is sufficient | TASK-REV-1F3F R3 |

---

## Appendix A: The Two-Layer Think Block Architecture (Established Run 8)

```
┌────────────────────────────────────────────────────────┐
│ LAYER 1: Model's Own Chain-of-Thought                  │
│                                                        │
│ <think>                                                │
│ The user wants me to generate a training example...    │
│ </think>                                               │
│                                                        │
│ ← Model reasoning about HOW to generate the example    │
│ �� NOT part of the training data                        │
│ ← Coach sees this (can trigger role confusion ~15%)    │
└────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────┐
│ LAYER 2: Think Blocks INSIDE Training Example JSON     │
│                                                        │
│ {"messages": [...,                                     │
│   {"role": "assistant",                                │
│    "content": "<think>The student is asking about      │
│    Lady Macbeth's soliloquy...</think>\n\nThat's a     │
│    really interesting passage!"}                        │
│ ], "metadata": {...}}                                  │
│                                                        │
│ ← Pedagogical content — MUST be preserved              │
│ ← Protected by TRF-024 (disabled reasoning parser)     │
└────────────────────────────────────────────────────────┘
```

## Appendix B: vLLM Structured Output on GB10 — Community Status

| Capability | Status | Source |
|------------|--------|--------|
| Basic inference | Working (30-70 tok/s) | Multiple forum threads |
| Tool calling | Working | Qwen3.5-122B thread |
| `enable_thinking: false` | Working for tool calling | Qwen3.5-122B thread |
| `response_format: json_schema` | **Likely broken** | GPT-OSS thread: "ignored" |
| Structured output + reasoning | **Multiple open bugs** | vLLM #35700, #18819, #27447 |

## Appendix C: Token Usage & Projections

| Metric | Value |
|--------|-------|
| Run 12 tokens | 334,370 (20 targets, 34 min) |
| Average per target | 16,718 tokens |
| Overnight (340 targets) | ~5.7M tokens, ~10 hours |
| Full GOAL.md (1,020 targets) | ~17M tokens, ~29 hours |
| Cost | $0 (self-hosted vLLM) |
