---
id: TASK-CR-005
title: Investigate Coach refusal issue (120 empty responses with refusal key)
status: completed
created: 2026-04-07T12:00:00Z
updated: 2026-04-07T18:00:00Z
priority: medium
complexity: 5
tags: [coach, refusal, vllm, investigation]
parent_review: TASK-REV-CC01
feature_id: FEAT-CR
wave: null
implementation_mode: manual
dependencies: []
test_results:
  status: n/a
  coverage: null
  last_run: null
---

# Task: Investigate Coach refusal issue (120 empty responses with refusal key)

## Description

120 Coach responses (51% of direct rejections, ~19% of all direct targets) returned empty content with a `refusal` key in `additional_kwargs`. This is a separate issue from the criteria routing non-compliance.

```
llm_failure: Coach response has no extractable content:
content='', additional_kwargs keys=['refusal']
```

96% of refusals (120/125) affect direct-type targets, suggesting the knowledge content triggers the Qwen 3.5-35B safety layer more frequently than reasoning/Socratic content.

## Investigation Areas

1. **vLLM safety settings** — check if content filtering is enabled and can be tuned
2. **Refusal content patterns** — which categories trigger refusals most (character knowledge? factual recall?)
3. **Prompt length** — do refusals correlate with longer examples?
4. **Model alternative** — would a different model handle knowledge evaluation without refusals?
5. **Retry strategy** — would retrying with a rephrased prompt succeed?

---

## Investigation Findings

### 1. Refusal Statistics (from `output_backup_pre_rerun/rejected.jsonl`)

**98 refusals total** in the analysed run:

| Type | Refusals | Non-refusal rejections | Refusal rate |
|------|----------|----------------------|--------------|
| **direct** (knowledge) | 93 | 397 | **19.0%** |
| **reasoning** (behaviour) | 5 | 117 | **4.1%** |

Direct/knowledge examples are **4.6x more likely** to trigger refusals than reasoning examples.

### 2. Refusal Distribution by Category

| Category | Refusals | Refusal % of category |
|----------|----------|-----------------------|
| Terminology and literary devices | 25 | Highest |
| Context — historical and social (set texts) | 18 | High |
| Factual recall — AQA specification | 17 | High |
| Character knowledge — set texts | 15 | Moderate |
| Exam structure and mark allocation | 11 | Moderate |
| Encouragement and study skills | 7 | Lower |
| Essay feedback — Language (multi-turn) | 3 | Low |
| Essay feedback — Literature (multi-turn) | 1 | Minimal |
| Exam technique — Language Paper 1 | 1 | Minimal |

**Pattern:** Content-heavy knowledge categories (literary terms, historical context, factual recall) trigger refusals most. The Coach is being asked to evaluate factual content — the model's safety layer appears to interpret this as reproducing copyrighted/exam material.

### 3. Root Cause: Qwen 3.5-35B Safety Layer + Structured Outputs

The refusal mechanism:

1. Player generates a knowledge example (e.g., character facts, exam specification details)
2. Coach receives the Player's content as a user message to evaluate
3. vLLM's structured outputs mode constrains output to `CoachVerdict` JSON schema
4. **Qwen 3.5-35B safety layer fires** — interprets the evaluation request as reproducing exam/educational content
5. Model returns `content=''` with `additional_kwargs={'refusal': '...'}`
6. `_extract_coach_content()` finds no content in any of its 4 fallback paths
7. `ValueError` propagates → target rejected as `llm_failure`

**Key evidence:**
- The `refusal` key is set by the OpenAI-compatible API when the model declines to respond
- It is NOT a vLLM configuration issue — it's the model's built-in safety filter
- Structured outputs mode may amplify the problem: the model must produce valid JSON or refuse entirely (no partial/hedged response possible)

### 4. Code Gap: No Refusal Detection or Handling

**`_extract_coach_content()`** (`entrypoint/generation_loop.py:496-568`):
- Checks 4 content sources but never inspects `additional_kwargs['refusal']`
- Does not log the refusal reason text
- Raises generic `ValueError` — indistinguishable from other empty-content failures

**`_invoke_with_retry()`** (`entrypoint/generation_loop.py:366-424`):
- Retries on `RuntimeError`, `OSError`, `TimeoutError`, `ValidationError`, `httpx.HTTPStatusError`
- Refusals don't raise any of these — the HTTP call succeeds (200 OK), content is just empty
- No retry path exists for refusals

**Outer exception handler** (`entrypoint/generation_loop.py:1187`):
- Catches the `ValueError` from `_extract_coach_content()` as `llm_failure`
- No differentiation between refusal vs other content extraction failures

### 5. vLLM Safety Settings

vLLM itself does not add content filtering — it passes through the model's native safety behaviour. There is no vLLM flag to disable Qwen's built-in refusal mechanism. The safety filter is embedded in the model weights.

### 6. Investigation Area Answers

| Area | Finding |
|------|---------|
| **vLLM safety settings** | vLLM has no content filter — refusals come from Qwen 3.5-35B model weights. Cannot be tuned via vLLM config. |
| **Refusal content patterns** | Literary terminology (25), historical context (18), and factual recall (17) are top triggers. Educational/exam content evaluation triggers the safety layer. |
| **Prompt length** | Not the primary factor — the *type* of content (knowledge vs reasoning) is the dominant variable (4.6x differential). |
| **Model alternative** | A model without aggressive educational-content safety (e.g., Llama 3.1, Mistral, or a newer Qwen variant) would likely reduce refusals. |
| **Retry strategy** | Current retry targets JSON parse failures, not refusals. Retrying the same content will likely hit the same safety filter. A rephrased "evaluation-only" framing might help. |

---

## Recommended Mitigations

### Option A: Refusal-Aware Retry with Reframed Prompt (Low risk, moderate impact)

Add refusal detection in `_extract_coach_content()` and retry with a prompt that frames the task as "quality assessment" rather than content evaluation:

```python
# Detect refusal
if 'refusal' in additional_kwargs:
    logger.warning("Coach refused to evaluate content: %s", additional_kwargs['refusal'])
    # Retry with reframed prompt emphasising assessment role
```

**Estimated impact:** May recover 30-50% of refusals if the safety trigger is prompt-sensitive.

### Option B: Structured Outputs Fallback (Medium risk, moderate impact)

When a refusal occurs, retry without structured outputs constraints. The model may be more willing to respond in free-form text, which can then be parsed:

```python
# Retry without structured_outputs constraint
extra_body_fallback = {}  # No JSON schema constraint
```

**Estimated impact:** May recover refusals where the JSON constraint + content combined triggers the filter.

### Option C: Model Switch for Coach (Low risk, high impact)

Use a different model for the Coach role that has a less aggressive safety layer for educational content evaluation. The Coach only needs to produce structured JSON verdicts — it doesn't need the same creative capability as the Player.

**Candidates:** Llama 3.1 70B, Mistral Large, Qwen2.5-72B (older Qwen may have different safety profile).

### Option D: Accept-by-Default on Refusal (High risk, quick fix)

If the Player's content passes format validation, treat a Coach refusal as an implicit acceptance rather than rejection. This avoids wasting valid content but bypasses quality gating.

**Not recommended** without additional validation gates.

---

## Implementation Tasks (if proceeding)

If mitigation is approved, these would be the implementation tasks:

1. **Add refusal detection** — detect `refusal` key in `_extract_coach_content()`, log the refusal reason
2. **Add refusal-specific retry** — retry with reframed prompt on first refusal
3. **Add structured-outputs fallback** — retry without JSON schema on second refusal
4. **Add metrics** — track refusal rate per category in generation summary
