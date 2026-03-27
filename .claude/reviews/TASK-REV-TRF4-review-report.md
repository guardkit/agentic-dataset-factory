# Review Report: TASK-REV-TRF4

## Executive Summary

The fourth pipeline run with **Qwen3.5-35B-A3B-FP8** (262K context) processed **1 target** and **failed to complete**. Zero training examples were accepted or rejected. The root cause is a **Coach response format mismatch**: the Coach prefixes its JSON verdict with explanatory text before a markdown code fence, but the parser only strips fences when they appear at the start of the response.

**4 of 6 fixes from TASK-REV-FRF3 are verified working. 2 could not be verified** because the pipeline failed before reaching those code paths. **1 new critical bug** was discovered.

**Production readiness: NOT READY.** One fix required before overnight run.

---

## Review Details

- **Mode**: Decision Analysis
- **Depth**: Standard
- **Source**: `docs/reviews/second-run/qwen35-run-1.md`
- **Pipeline Duration**: 92 seconds (14:16:11 – 14:17:43 GMT, 26 Mar 2026)
- **Model**: Qwen/Qwen3.5-35B-A3B-FP8, local vLLM on `promaxgb10-41b1:8002`

---

## Fix Verification (TASK-REV-FRF3)

| # | Fix | Task | Status | Evidence |
|---|-----|------|--------|----------|
| 1 | **F3: Coach bypass → orchestrator-gated writes** | TASK-TRF-005 | VERIFIED | Player has 0 write tools. Orchestrator manages lock, opens files, controls write path. Player prompt: "Do not call any write tool — the orchestrator handles persistence after Coach acceptance." |
| 2 | **F4: Context exhaustion → 262K context window** | TASK-TRF-001/002 | VERIFIED | Model loaded as Qwen3.5-35B-A3B-FP8 with 262K max_model_len. 8 API calls completed with HTTP 200. No context overflow errors. |
| 3 | **F5: Tool leakage → backend=None** | TASK-TRF-003 | VERIFIED | Player system prompt shows exactly 1 tool: `rag_retrieval`. No `ls`, `read_file`, `write_file`, `edit_file`, `glob`, `grep`, `task`, `write_todos` leaked. |
| 4 | **F7: `<think>` blocks → qwen3 reasoning parser** | TASK-TRF-001 | UNVERIFIED | Pipeline failed before any example was accepted. Cannot assess `<think>` block quality from this run. vLLM configured with `--tool-parser-plugin qwen3_coder --reasoning-parser qwen3`. |
| 5 | **F8: grade_target coercion → str() cast** | TASK-TRF-004 | UNVERIFIED | No examples reached the write_output validation stage. Cannot verify integer metadata handling. |
| 6 | **F6: Retry cap → max_write_attempts=3** | TASK-TRF-006 | UNVERIFIED | No write attempts occurred. Config confirms `max_write_attempts: 3` in agent-config.yaml. Code path exists but was not exercised. |

**Summary**: 3/6 verified working, 3/6 unverified (pipeline failed too early to reach those code paths). No regressions detected in the verified fixes.

---

## New Findings

### F1 (CRITICAL): Coach verdict parsing fails on preamble text

**Severity**: P0 — blocks all pipeline execution
**Component**: `entrypoint/generation_loop.py:140-180` (`_parse_coach_verdict()`)

**Problem**: The Coach model (Qwen3.5-35B at temp=0.3) returns its verdict with explanatory preamble text before a markdown code fence:

```
I can see the training example in your message. Let me evaluate it against the criteria.

```json
{
  "decision": "revise",
  "score": 4,
  "layer_correct": true,
  "type_correct": false,
  ...
}
```​
```

The parser at line 159 checks `if content.startswith("```")` which is `False` because the response starts with "I can see...". The code fence stripping is skipped, and the entire raw text hits `model_validate_json()`, which fails:

```
Failed to parse CoachVerdict from response: 1 validation error for CoachVerdict
  Invalid JSON: expected ident at line 1 column 2
```

This error occurred **twice** (both Coach invocations failed identically), resulting in 100% pipeline failure.

**Fix options** (in order of preference):

1. **Robust JSON extraction** (recommended): Use regex to find the first `{...}` block in the response, similar to the existing `_extract_example_json()` function used for Player responses. This handles preamble text, code fences, and any other wrapper.

2. **Coach prompt hardening**: Add explicit instruction like "Return ONLY the JSON object. Do not include any explanatory text before or after the JSON." — but this is fragile with smaller models.

3. **Both**: Apply robust extraction AND prompt hardening for defense in depth.

### F2 (MEDIUM): Player did not call rag_retrieval

**Severity**: P1 — quality concern, not blocking
**Component**: Tool calling / Player agent behavior

**Problem**: Despite having `rag_retrieval` as its only tool, the Player agent did not make any tool calls during the run. All 8 HTTP requests were text-only completions — no `tool_use` blocks were found in responses.

**Impact**: Training examples are generated without RAG context, meaning they are not grounded in curriculum source material. The system prompt says "Always call rag_retrieval before generating an example" but the model didn't comply.

**Possible causes**:
- Qwen3.5-35B may need explicit `tool_choice: "required"` or `tool_choice: {"type": "function", "function": {"name": "rag_retrieval"}}` to force initial tool use
- The tool schema may not be passed correctly via vLLM's `qwen3_coder` parser
- Model may need few-shot examples in the system prompt

**Fix options**:
1. Verify tool schemas are being sent in the API request (check HTTP request bodies in debug log)
2. Try `tool_choice: "required"` for the first Player turn
3. Add a few-shot example showing rag_retrieval usage in the Player prompt

### F3 (LOW): No token usage logging

**Severity**: P2 — observability gap
**Component**: Logging / vLLM response handling

**Problem**: Token counts (prompt_tokens, completion_tokens, total_tokens) are not logged despite being returned by vLLM's OpenAI-compatible API. This makes it impossible to assess context window utilisation or track costs.

**Fix**: Log `response.usage` from each API call.

---

## Pipeline Performance

| Metric | Value |
|--------|-------|
| Targets queued | 1 |
| Targets started | 1 |
| Targets completed | 0 |
| Examples accepted | 0 |
| Examples rejected | 0 |
| Pipeline outcome | FAILED |
| HTTP requests | 8 (all 200 OK) |
| Duration | 92 seconds |
| Output files | 0 bytes (train.jsonl, rejected.jsonl both empty) |

**Throughput**: Not measurable — no targets completed.

---

## Coach Verdict Analysis

Both Coach invocations returned identical verdicts (visible in parse error output):

| Field | Value |
|-------|-------|
| decision | revise |
| score | 4/5 |
| layer_correct | true |
| type_correct | false |

The Coach was working correctly — it identified a `type_correct: false` issue and requested revision. The verdict content is valid; only the parsing failed.

---

## Model Quality Assessment (Preliminary)

| Criterion | Assessment |
|-----------|------------|
| Tool calling | NOT TESTED — Player didn't call rag_retrieval |
| Example quality | NOT TESTED — no examples reached acceptance |
| Metadata correctness | NOT TESTED — no examples written |
| `<think>` block quality | NOT TESTED — no examples reached write stage |
| Coach evaluation quality | GOOD — Coach correctly identified type mismatch (score 4, type_correct=false) |
| Network reliability | EXCELLENT — 8/8 API calls returned 200 OK |
| Context window | SUFFICIENT — no overflow errors with 262K limit |

---

## Recommendations

| # | Priority | Action | Effort |
|---|----------|--------|--------|
| 1 | P0 | Fix Coach verdict parser to extract JSON from preamble text (use regex `{...}` extraction) | Small (1-2h) |
| 2 | P1 | Investigate why Player doesn't call rag_retrieval (check tool schema in requests, consider tool_choice) | Medium (2-4h) |
| 3 | P2 | Add token usage logging for observability | Small (30m) |

---

## Decision Matrix

| Option | Risk | Effort | Recommendation |
|--------|------|--------|----------------|
| Fix F1 only, re-run | Low | 1-2h | **Recommended** — unblocks pipeline, then verify remaining fixes |
| Fix F1 + F2, re-run | Medium | 3-6h | Better quality but delays next run |
| Fix all (F1-F3), re-run | Low | 4-7h | Ideal but may over-engineer before confirming pipeline works |
| Re-run with Anthropic API | N/A | 0h | Bypasses local model issues but doesn't fix root cause |

---

## Appendix

### A. HTTP Request Timeline

| # | Time | Response Size | Purpose (inferred) |
|---|------|---------------|-------------------|
| 1 | 14:16:11 | 954 bytes | Player turn 1 (initial generation) |
| 2 | 14:16:38 | 822 bytes | Player continuation |
| 3 | 14:16:40 | 3,126 bytes | Player example generation |
| 4 | 14:17:05 | 3,181 bytes | Player example generation |
| 5 | 14:17:31 | 1,775 bytes | Player refinement |
| 6 | 14:17:38 | 830 bytes | Coach evaluation attempt 1 |
| 7 | 14:17:40 | 960 bytes | Coach evaluation attempt 2 |
| 8 | 14:17:43 | 4,144 bytes | Final response |

### B. Verified Code Configuration

```yaml
# agent-config.yaml
player:
  provider: local
  model: Qwen/Qwen3.5-35B-A3B-FP8
  temperature: 0.6

coach:
  provider: local
  model: Qwen/Qwen3.5-35B-A3B-FP8
  temperature: 0.3

generation:
  max_turns: 3
  max_write_attempts: 3
  llm_retry_attempts: 3
```

### C. Tool Assignment Audit

| Agent | Expected Tools | Actual Tools | Status |
|-------|---------------|--------------|--------|
| Player | `[rag_retrieval]` | `[rag_retrieval]` | PASS |
| Coach | `[]` (empty) | `[]` (empty) | PASS |
| Orchestrator | `write_output` | `write_output` | PASS |

### D. Previous Review Chain

| Review | Run | Key Findings | Fixes |
|--------|-----|-------------|-------|
| TASK-REV-E2A7 | Run 1 | ChromaDB path + array validation | TASK-FRF-001, TASK-FRF-002 |
| TASK-REV-FRF2 | Run 2 | tool_calls.args deserialization + model args | Model switch to Nemotron → qwen3_coder |
| TASK-REV-FRF3 | Run 3 | Context window + tool leakage + Coach bypass + type coercion | TASK-TRF-001 through TASK-TRF-007 |
| **TASK-REV-TRF4** | **Run 4** | **Coach verdict parser preamble bug + no RAG tool use** | **TBD** |
