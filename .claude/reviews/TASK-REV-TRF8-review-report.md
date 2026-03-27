# Review Report: TASK-REV-TRF8

## Executive Summary

**Run 8 FAILS. 0/1 targets accepted. Pipeline NOT ready for overnight run.**

All four TRF-020–023 fixes are deployed and operational, but two interrelated root-cause issues block the pipeline:

1. **vLLM's `--reasoning-parser qwen3` strips `<think>` blocks** from the Player's output before the application sees them. The model IS generating think blocks, but vLLM intercepts and redirects them to `reasoning_content` (a separate field). The Player content extractor doesn't read this field, so think blocks are silently lost. This also likely corrupts the JSON structure, causing extraction failures.

2. **JSON extraction brace-matching is naive** — the `_extract_json_object` brace counter doesn't track JSON string boundaries, so `{`/`}` characters inside string values throw off depth tracking.

The Coach accepted the Player's output twice (score 5/5), but JSON extraction failed both times. No training examples were written. The root cause was identified by cross-referencing the vLLM launch script (`guardkit/scripts/vllm-agentic-factory.sh`) which configures `--reasoning-parser qwen3` — this flag is the primary blocker.

## Review Details

- **Mode**: Code Quality / Post-Fix Validation
- **Depth**: Standard
- **Source**: `docs/reviews/second-run/qwen35-run-5.md`
- **Run Date**: 2026-03-27 13:18–13:21 UTC
- **Model**: Qwen/Qwen3.5-35B-A3B-FP8
- **Reviewer**: Opus 4.6

---

## Fix Verification (TASK-TRF-020 through TASK-TRF-023)

### F1: TASK-TRF-020 — normalise_think_closing_tags before extraction

**Status: DEPLOYED** — Line 645 of `generation_loop.py` calls `normalise_think_closing_tags(player_content)` before `_extract_example_json`.

**Effectiveness: NOT EXERCISED** — Player generated no `<think>` blocks at all, so normalisation was a no-op. The fix is structurally correct but untested in this run.

### F2: TASK-TRF-021 — EOF pattern handling (unclosed think blocks)

**Status: DEPLOYED** — `normalise_think_closing_tags()` includes EOF pattern logic (appends `</think>` when `<think>` is opened but never closed).

**Effectiveness: NOT EXERCISED** — No think blocks in Player output. Same as F1.

### F3: TASK-TRF-022 — Explicit max_tokens

**Status: DEPLOYED** — Request options show `'max_completion_tokens': 4096`. ModelConfig has `max_tokens: int = Field(default=4096)`.

**Effectiveness: CONFIRMED WORKING** — The model is not being truncated. Player completion_tokens: 940, 957, 899 (all well under 4096). The model self-limits its output length rather than hitting the cap.

### F4: TASK-TRF-023 — Improved extraction failure logging

**Status: DEPLOYED AND WORKING** — Log lines 79 and 118 show the improved format:
```
JSON extraction failed after Coach acceptance: Failed to extract JSON object from content.
Raw content (first 200 chars): '...'
Content length: 3195 chars | Last 200 chars: ...
```

This is exactly the TASK-TRF-023 format with both content length and tail. The logging improvement is confirmed working.

---

## Carry-Forward Verification

| Check | Status | Evidence |
|-------|--------|----------|
| F1: Player tools = `['rag_retrieval']` | PASS | Line 13: `tools=['rag_retrieval']` |
| F4: Coach 0 tools | PASS | Line 15: `Creating Coach agent (no tools)` |
| F6: Player 0-1 RAG calls | PASS | 1 rag_retrieval call per target (tool_call on turn 1 only) |
| Token logging (per-turn) | PASS | Lines 59, 77, 98, 116, 137, 155 |
| Token logging (aggregate) | PASS | Lines 157, 161 |

All carry-forward invariants confirmed.

---

## JSON Extraction Analysis (CRITICAL)

### Turn 1: Coach accepts (score 5), extraction FAILS

- **Content format**: Bare JSON (no code fence, no think block)
- **Content starts with**: `\n\n{\n  "messages": [...]`
- **Content length**: 3195 chars
- **Content ends with**: Conversational text outside the JSON object
- **3-try result**: All 3 strategies fail

**Root cause analysis**:
- Try 1 (direct parse): Fails — trailing conversational text after the JSON
- Try 2 (fence regex): Fails — no code fences present
- Try 3 (brace matching): Fails — **most likely due to unbalanced curly braces inside JSON string values** (e.g., the tutor's response contains `{` without matching `}`, or vice versa, in the text content). The naive brace counter doesn't track JSON string boundaries, so a stray `{` or `}` inside a string throws off the depth counter.

### Turn 2: Coach accepts (score 5), extraction FAILS

- **Content format**: Code-fenced JSON (`\`\`\`json\n{...}\n\`\`\``)
- **Content length**: 3251 chars
- **Content ends with**: `"turns": 1\n  }\n}\n\`\`\`` (proper code fence closure)
- **3-try result**: All 3 strategies fail

**Root cause analysis**:
- Try 1 (direct parse): Fails — content has leading newlines + code fence markers
- Try 2 (fence regex): Regex `r"```(?:json)?\s*\n(.*?)```"` SHOULD match, but `json.loads` fails on the extracted content. **Probable cause**: the JSON contains literal (unescaped) control characters in string values, or the model outputs literal newlines within JSON strings instead of `\n` escape sequences.
- Try 3 (brace matching): Same brace-counting issue as Turn 1 — unbalanced braces in string content

### Turn 3: Coach rejects (score 2)

- **Content length**: 852 chars (much shorter — Player generated a degraded response after two extraction failures)
- Extraction not attempted because Coach rejected

### Summary

The 3-try JSON extraction strategy has a fundamental weakness: **it cannot handle JSON where string values contain unbalanced curly braces**. The brace-matching (Try 3) treats all `{` and `}` as structural, but in JSON, braces inside strings are just text. A proper fix needs a JSON-string-aware parser or a different extraction approach.

---

## Missing Think Blocks — ROOT CAUSE IDENTIFIED (REVISED)

**Severity: CRITICAL — affects two distinct layers**

The generation target is `type=reasoning`, which requires `<think>` blocks per the prompt and `write_output` validation. But the Player's extracted content contains **no `<think>` blocks at all** across all 3 turns.

Even if JSON extraction had succeeded, `write_output` validation would reject the example with: `"reasoning example missing <think>...</think> block"`.

### Root Cause: vLLM `--reasoning-parser qwen3` strips think blocks

The vLLM launch script ([vllm-agentic-factory.sh](../../guardkit/scripts/vllm-agentic-factory.sh) line 65) configures:

```bash
--reasoning-parser qwen3
```

This tells vLLM to **intercept and strip `<think>` blocks** from the model's output. The Qwen3 reasoning parser:

1. Detects `<think>...</think>` blocks in the model's raw output
2. **Removes them from the `content` field** of the OpenAI-compatible API response
3. Places the thinking content in a separate `reasoning_content` field (via `additional_kwargs`)

So the model IS generating `<think>` blocks — **vLLM is stripping them before they reach the application**.

### Evidence

- The `_extract_coach_content` function (generation_loop.py:394-466) already knows about this! It has a **4-source fallback** including Path 4: `additional_kwargs["reasoning_content"]` (vLLM think-mode fallback). This was added specifically for the Coach after TASK-REV-TRF5 discovered the Coach's verdict was being lost inside think blocks.
- The `_extract_player_content` function (generation_loop.py:169-217) does **NOT** have this fallback — it only checks `content` (string) and content blocks (list). It never looks at `additional_kwargs["reasoning_content"]`.

### The Two-Layer Problem

This creates a **two-layer failure**:

**Layer 1 — Model's own reasoning is stripped**: The model thinks in `<think>` blocks before generating the JSON. vLLM strips these, leaving only the JSON in `content`. This is actually fine for extraction purposes — the JSON is what we want.

**Layer 2 — Training example's assistant content lacks think blocks**: The training example generated by the Player should contain `<think>` blocks *inside the JSON's `messages[].content` field* (the tutor's response). But the Player model generates the entire response — including the training example's embedded think blocks — and vLLM's reasoning parser may strip think blocks from ALL levels, not just the outer reasoning. If the model outputs:

```
<think>I should create an example about Macbeth...</think>

{"messages": [{"role": "assistant", "content": "<think>The student is asking about...</think>\n\nGreat question! Let's explore..."}]}
```

vLLM's parser strips the outer `<think>` (Layer 1 — fine) but may also strip or corrupt `<think>` tags embedded within the JSON string values (Layer 2 — problem).

Alternatively, **the model may not be generating think blocks inside the JSON content at all** because the `--reasoning-parser` intercepts the model's native think-mode, redirecting ALL thinking to the separate reasoning channel. The model's native thinking infrastructure conflicts with the prompt's instruction to embed `<think>` blocks within generated example content.

### Impact

- Blocks ALL reasoning-type examples (75% of the target dataset)
- Even with JSON extraction fixed, every example would fail `write_output` validation
- This is a fundamental architecture conflict between vLLM's reasoning parser and the application's requirement for think blocks inside generated content

### Possible Solutions

**Option A: Disable `--reasoning-parser qwen3`** — Remove the flag from the vLLM launch script. The model will include `<think>` blocks in its raw `content` output. The existing `normalise_think_closing_tags` pipeline handles malformed think blocks. Downside: the model's own reasoning and the training example's think blocks will be mixed together; extraction must handle this.

**Option B: Use reasoning_content for the model's thinking, inject think blocks via prompt engineering** — Keep the reasoning parser but rewrite the Player prompt to explicitly instruct the model to include `<think>` blocks as literal text within the JSON content field (not as native model thinking). This may conflict with the model's native think-mode behaviour.

**Option C: Post-process — reconstruct think blocks from reasoning_content** — Access `additional_kwargs["reasoning_content"]` in `_extract_player_content` (like the Coach extractor does) and inject it as a `<think>` block prefix into the training example's assistant content after JSON extraction. This is the most surgical fix.

**Recommended: Option A** — Disable `--reasoning-parser qwen3`. It's the simplest fix and lets the model output think blocks naturally. The normalisation pipeline (TASK-TRF-020/021) already handles malformed think tags. The JSON extraction just needs to handle content that starts with `<think>...</think>` before the JSON, which is a simpler problem.

---

## Pipeline Performance

| Metric | Value |
|--------|-------|
| Targets | 1 |
| Accepted | 0 |
| Rejected | 1 |
| Total turns | 3 (max_turns reached) |
| Elapsed | 165.1s |
| Prompt tokens | 22,664 |
| Completion tokens | 5,456 |
| Total tokens | 28,120 |
| Avg tokens/turn | ~4,687 |
| Time per turn | ~55s |

**Coach verdict distribution**:

| Turn | Decision | Score |
|------|----------|-------|
| 1 | accept | 5/5 |
| 2 | accept | 5/5 |
| 3 | revise | 2/5 |

The Coach accepted twice but extraction failed both times. The loop sent the Player a "return valid JSON" revision prompt, and the Player produced a short (852 char) degraded response on turn 3, which the Coach then rejected.

---

## Findings Summary

| # | Finding | Severity | Category |
|---|---------|----------|----------|
| F1 | vLLM `--reasoning-parser qwen3` strips `<think>` blocks from Player output — training examples lack required think blocks | CRITICAL | vLLM config / architecture conflict |
| F2 | `_extract_json_object` brace matcher fails on unbalanced braces in JSON strings | CRITICAL | JSON extraction |
| F3 | `_extract_json_object` fence regex extraction succeeds but `json.loads` fails (probable malformed JSON from think-block stripping) | HIGH | JSON extraction |
| F4 | `_extract_player_content` lacks `reasoning_content` fallback (unlike Coach extractor) | MEDIUM | Code asymmetry |
| F5 | Coach evaluating positively (5/5) despite missing required think blocks | MEDIUM | Coach quality |
| F6 | Player degrades to short/poor response after extraction-failure feedback | LOW | Loop behaviour |

---

## Recommendations

### R1: Disable `--reasoning-parser qwen3` in vLLM launch script (CRITICAL — P0)

The `--reasoning-parser qwen3` flag in `vllm-agentic-factory.sh` strips `<think>` blocks from ALL model output, creating a fundamental conflict: the pipeline needs think blocks embedded in the training example's assistant content, but vLLM removes them before the application sees them.

**Fix**: Remove `--reasoning-parser qwen3` from the Qwen3.5 case in the launch script. Keep `--enable-auto-tool-choice` and `--tool-call-parser qwen3_coder` (these are needed for tool calling and are unrelated to think-block parsing).

**Risk**: Without the reasoning parser, the model's `<think>` blocks will appear in the raw `content` field. The existing `normalise_think_closing_tags` pipeline (TRF-020/021) handles malformed think tags. The JSON extraction will need to handle content structured as `<think>...</think>\n\n{json}`.

**Impact**: This single change likely resolves BOTH the missing think blocks AND the JSON extraction failures (the think-block stripping may be corrupting the JSON structure).

### R2: Fix brace-matching to be JSON-string-aware (CRITICAL — P0)

Replace the naive brace counter in `_extract_json_object` Try 3 with a JSON-string-aware scanner that tracks whether the current position is inside a quoted string. This prevents `{`/`}` in string values from corrupting depth tracking.

```python
# Proposed approach: track "in_string" state
in_string = False
escape_next = False
for i, ch in enumerate(content):
    if escape_next:
        escape_next = False
        continue
    if ch == '\\' and in_string:
        escape_next = True
        continue
    if ch == '"' and not escape_next:
        in_string = not in_string
        continue
    if in_string:
        continue
    # Only count braces outside strings
    if ch == '{': ...
    elif ch == '}': ...
```

This fix is needed regardless of R1, because training example content will contain text with stray braces.

### R3: Add `reasoning_content` fallback to `_extract_player_content` (MEDIUM)

`_extract_coach_content` has a 4-source fallback including `additional_kwargs["reasoning_content"]`. `_extract_player_content` lacks this — it should be added for parity, even if R1 is applied. This provides defence-in-depth if the reasoning parser is ever re-enabled.

### R4: Improve Coach evaluation to check think block presence (MEDIUM)

The Coach should not score 5/5 for a reasoning-type example that lacks a `<think>` block. Add explicit instructions to the Coach prompt to verify think block presence before acceptance.

### R5: Handle JSON with literal unescaped newlines in strings (LOW)

Add a pre-processing step before `json.loads` that repairs common JSON issues:
- Replace literal newlines inside strings with `\n`
- Fix common escape sequence issues

---

## Decisions Required

### 1. Production readiness

**DECISION: NOT READY.** Two blocking issues must be fixed before the overnight run:
1. JSON extraction fails on all accepted outputs (0% extraction success rate)
2. Missing think blocks would cause write validation to reject even extracted JSON

### 2. Model confirmation

**DECISION: UNCERTAIN.** Qwen3.5-35B-A3B-FP8 shows good generation quality (Coach scores 5/5) but fails to follow the `<think>` block instruction. Need to verify whether the model supports think blocks at all, or if the prompt needs significant restructuring.

### 3. Configuration tuning

- `max_tokens: 4096` — confirmed working, no change needed
- `temperature: 0.6` (Player), `0.3` (Coach) — reasonable, no change needed
- `max_turns: 3` — may need increase once extraction works (to give more revision chances)

### 4. Outstanding blockers for overnight run

| Blocker | Priority | Estimated Fix |
|---------|----------|---------------|
| vLLM `--reasoning-parser qwen3` stripping think blocks from Player output | P0 | TASK-TRF-024: Remove `--reasoning-parser qwen3` from launch script |
| JSON extraction brace-matching fails on unbalanced braces in strings | P0 | TASK-TRF-025: JSON-string-aware brace matcher |
| `_extract_player_content` lacks `reasoning_content` fallback | P1 | TASK-TRF-026: Add fallback for defence-in-depth |
| Coach not checking think block presence | P2 | TASK-TRF-027: Coach prompt enhancement |

---

## Appendix: Log Timeline

```
13:18:43  Player turn 1 completes (940 tokens)
13:19:08  RAG retrieval (for Coach context)
13:19:32  Coach turn 1: accept, score=5
13:19:32  JSON extraction FAILS (content 3195 chars)
13:19:54  Player turn 2 (revision) completes (957 tokens)
13:20:18  Coach turn 2: accept, score=5
13:20:18  JSON extraction FAILS (content 3251 chars)
13:20:42  Player turn 3 (revision) completes (899 tokens, 852 char content)
13:21:04  Coach turn 3: revise, score=2
13:21:04  Target rejected after 3 turns
```

Total pipeline: 165.1 seconds, 28,120 tokens consumed, 0 examples produced.
