# Review Report: TASK-REV-FRF2

## Executive Summary

The second end-to-end run confirmed that **TASK-FRF-001 (ChromaDB path fix) is working correctly** — RAG retrieval successfully returned 5 curriculum chunks. **TASK-FRF-002 (array validation fix) was never exercised** because the pipeline crashed before reaching valid `write_output` calls. Three new issues were identified: (1) a **critical vLLM/LangChain `tool_calls.args` deserialization failure** that crashes the pipeline, (2) the model **incorrectly structures `write_output` arguments** by splitting `example_json` and `metadata` into separate fields, and (3) the **Player calls `write_output` directly without Coach evaluation**, bypassing the adversarial cooperation loop.

- **Mode**: Architectural / Decision
- **Depth**: Standard
- **Source**: `docs/reviews/first-run/vllm-qwen-25-2.md`

## Findings

### Finding 1: TASK-FRF-001 (ChromaDB path fix) — CONFIRMED WORKING

**Severity**: Resolved
**Evidence**: The `rag_retrieval` tool successfully connected to ChromaDB and returned 5 relevant curriculum chunks for query "Macbeth Act 1 Scene 7 ambition soliloquy":

- Chunk 1: Act 1 Scene 7 soliloquy ("I have no spur to prick the sides of my intent but only vaulting ambition")
- Chunk 2: Act 3 Scene 1, Banquo's soliloquy
- Chunk 3: Macbeth title-level chunk
- Chunk 4: Act 2 Scene 4, chorus function
- Chunk 5: Act 1, dramatic irony in Duncan's arrival

The ONNX provider warning (`No ONNX providers provided, defaulting to...`) is cosmetic — ChromaDB falls back to available ONNX Runtime providers.

**Verdict**: No action needed. TASK-FRF-001 acceptance criterion met.

### Finding 2: TASK-FRF-002 (array validation fix) — NOT TESTED

**Severity**: Indeterminate
**Evidence**: The `write_output` tool was called once, but with malformed input — the model split `messages` and `metadata` into separate argument fields instead of combining them into a single `example_json` string. The tool returned "Error: Invalid JSON" before metadata validation was ever invoked. The TASK-FRF-002 fix (array membership test for `ao`, `text`, etc.) was never exercised.

**Verdict**: Cannot confirm fix. Requires a successful `write_output` call with correctly-structured arguments to validate.

### Finding 3 (NEW, P0): vLLM/LangChain `tool_calls.args` Deserialization Crash

**Severity**: Critical — pipeline-terminating
**Evidence**: The third vLLM API call returned HTTP 200 with a 5504-byte response. LangChain's `AIMessage` Pydantic model rejected it:

```
1 validation error for AIMessage
tool_calls.0.args
  Input should be a valid dictionary [type=dict_type,
  input_value='{"example_json": "{\\\"me...ic\\",\\\"turns\\\":1}}"}',
  input_type=str]
```

**Root cause**: vLLM's OpenAI-compatible endpoint returns `function.arguments` as a JSON string (per the OpenAI API spec). LangChain's OpenAI integration normally parses this string into a dict via `json.loads()`. When using vLLM via the `openai` provider with `base_url`, this parsing step is either skipped or the arguments are double-serialized by vLLM's tool-call parser, resulting in a string where a dict is expected.

**Impact**: This error is unrecoverable — it crashes the entire pipeline, not just the current target. The `_invoke_with_retry` helper only catches `RuntimeError`, `OSError`, and `TimeoutError`, so `ValidationError` propagates to the top-level exception handler.

**Code path**: `generation_loop.py:243` → `player_response["messages"][-1]` → Pydantic validates `AIMessage.tool_calls[0].args` → fails because args is `str` not `dict`.

### Finding 4 (NEW, P1): Model Misstructures `write_output` Arguments

**Severity**: High
**Evidence**: On the second API call, the model correctly identified the `write_output` tool but split the arguments incorrectly:

```json
{
  "example_json": "{\"messages\": [...]}",
  "metadata": {"layer": "behaviour", "type": "reasoning", "ao": ["AO1", "AO2"], ...}
}
```

The `write_output` tool expects a **single** `example_json` string parameter containing BOTH the messages array AND the metadata object as one complete JSON object. The model put metadata outside the `example_json` string, causing "Error: Invalid JSON" on the tool side.

**Root cause**: The Qwen2.5-14B model does not fully comprehend the tool's single-string-parameter schema. This is a prompt engineering / tool schema clarity issue.

### Finding 5 (NEW, P1): Player Bypasses Coach Evaluation

**Severity**: High
**Evidence**: The log shows the Player agent calling `write_output` directly on turns 2 and 3 — writing the training example to disk without first submitting it to the Coach for quality evaluation. This contradicts the intended adversarial cooperation workflow (Player generates → Coach evaluates → write only if Coach accepts).

**Root cause**: DeepAgents SDK gives the Player agent tool-calling autonomy. The Player's system prompt does not explicitly prevent it from calling `write_output` before Coach review. The generation loop in `generation_loop.py:226-296` sends the Player's **content** to the Coach, but if the Player already wrote the file via a tool call, the Coach evaluation is post-hoc.

**Architectural concern**: The current design gives the Player both `rag_retrieval` and `write_output` tools. The Player can (and does) call `write_output` autonomously during its turn, before the Coach ever sees the output.

### Finding 6 (LOW): Python 3.14 / Pydantic V1 Compatibility Warning

**Severity**: Low
**Evidence**: `UserWarning: Core Pydantic V1 functionality isn't compatible with Python 3.14 or greater.` from `langchain_core`. Running on Python 3.14 with LangChain libraries that still import Pydantic V1 may cause subtle issues.

**Verdict**: Monitor but not actionable now. LangChain dependency update will resolve this.

### Finding 7 (LOW): Duplicate Error Logging

**Severity**: Low
**Evidence**: The pipeline error is logged twice — once by `generation_loop.py` (or the exception propagation path) and once by `agent.py:215` (`run_pipeline` catch block). The `main()` function at `agent.py:254` also logs `Pipeline failed`, making it three potential log lines for a single error.

## Pipeline Progress Summary

| # | API Call | Response Size | Tool Called | Result |
|---|---------|--------------|-------------|--------|
| 1 | 18:41:17 | 819 bytes | `rag_retrieval` | **Success** — 5 chunks returned |
| 2 | 18:41:25 | 2,829 bytes | `write_output` | **Tool error** — "Error: Invalid JSON" (malformed args) |
| 3 | 18:42:12 | 5,504 bytes | `write_output` | **Crash** — Pydantic `dict_type` ValidationError |

- Targets processed: 1 of 1
- Training examples written: 0
- Coach evaluations: 0 (Player bypassed Coach)

## Recommendations

### R1 (P0): Add `tool_calls.args` String-to-Dict Parsing Guard

Add a defensive parsing layer that catches the case where `tool_calls[0].args` arrives as a JSON string instead of a dict, and calls `json.loads()` on it before Pydantic validation. This should be implemented either:

- **Option A**: In the generation loop, wrapping the `ainvoke` response to normalize tool_calls args
- **Option B**: Via a custom LangChain callback/middleware that intercepts `AIMessage` construction
- **Option C**: Via vLLM `--tool-call-parser` configuration (e.g., `hermes` or `mistral` parser)

**Recommended**: Option A — most controlled, no dependency on vLLM config changes.

### R2 (P1): Restructure Tool Access to Enforce Coach-First Workflow

Remove `write_output` from the Player's tool set. Instead, have the generation loop handle writing after Coach acceptance:

1. Player gets only `rag_retrieval` tool
2. Player generates the training example as its **response content** (not a tool call)
3. Coach evaluates the Player's content
4. If Coach accepts → generation loop calls `write_output` programmatically

This eliminates the Player's ability to bypass Coach evaluation entirely.

### R3 (P1): Improve `write_output` Tool Schema / Player Prompt

If R2 is not adopted (tool stays with Player), improve the tool schema to make the expected format unambiguous:

- Add explicit examples in the tool's docstring showing the complete `example_json` structure
- Consider splitting into two parameters (`messages_json` and `metadata_json`) rather than a single string
- Strengthen the Player prompt to show the exact expected format

### R4 (P1): Add ValidationError to Retry-Eligible Exceptions

The `_invoke_with_retry` helper in `generation_loop.py:115-165` only catches `RuntimeError`, `OSError`, and `TimeoutError`. A `pydantic.ValidationError` from malformed LLM output kills the entire pipeline instead of retrying. Add `ValidationError` to the caught exception types, or wrap the agent invoke in a broader try/except that normalizes the response.

### R5 (LOW): Deduplicate Error Logging

Consolidate error logging so a single pipeline failure produces one error log line, not two or three.

## Decision Matrix

| Option | Effort | Risk | Impact | Recommendation |
|--------|--------|------|--------|----------------|
| R1: args parsing guard | Small (1-2 hrs) | Low | Unblocks pipeline | **Do first** |
| R2: Restructure tool access | Medium (3-4 hrs) | Medium | Fixes Coach bypass | **Do second** |
| R3: Improve tool schema | Small (1-2 hrs) | Low | Reduces model errors | Do if R2 rejected |
| R4: Add ValidationError retry | Small (30 min) | Low | Resilience | **Do with R1** |
| R5: Dedup error logging | Trivial | None | Cleanliness | Low priority |

## Remaining Items from TASK-REV-E2A7

| Original Finding | Status | Notes |
|-----------------|--------|-------|
| ChromaDB path mismatch (P0) | **Resolved** | TASK-FRF-001 confirmed working |
| Array validation (P0) | **Unverified** | TASK-FRF-002 not exercised — needs successful run |
| Loop bounds (P1) | Deferred | Still relevant but blocked by P0 issues above |
| GB10 deployment strategy (P1) | Deferred | vLLM port 8002 is operational; config is correct |

## Revision: Model Attribution Analysis (2026-03-25)

After deeper analysis, **3 of 5 new issues (F3, F4, F5) are primarily attributable to the Qwen2.5-14B model** and its interaction with the `hermes` tool-call parser. The Qwen2.5 + hermes combination has known double-serialization bugs (vLLM issue #17481).

### Decision: Switch to Nemotron 3 Nano 4B

Rather than building code workarounds for model-specific bugs, switching to the intended model (Nemotron 3 Nano 4B with `qwen3_coder` parser) is the most efficient fix.

### Actions Taken

| Action | Status | Files Changed |
|--------|--------|---------------|
| Update `vllm-agentic-factory.sh` — default to Nano 4B, `qwen3_coder` parser, remove Qwen presets | **Done** | `guardkit/scripts/vllm-agentic-factory.sh` |
| Update `agent-config.yaml` — model to `nvidia/NVIDIA-Nemotron-3-Nano-4B-FP8` | **Done** | `agent-config.yaml` |
| Add `ValidationError` to retry-eligible exceptions | **Done** | `entrypoint/generation_loop.py` |
| Create TASK-FRF-004: third end-to-end run | **Done** | `tasks/backlog/first-run-fixes/TASK-FRF-004-third-end-to-end-run.md` |

### Deferred

- **R2 (Restructure tool access)**: Remove `write_output` from Player — defer to after successful Nemotron run
- **R1 (args parsing guard)**: May be unnecessary if Nemotron + `qwen3_coder` serializes correctly

## Appendix

### Environment (Second Run — Qwen2.5)

- Python: 3.14
- vLLM endpoint: `promaxgb10-41b1:8002`
- Model: `neuralmagic/Qwen2.5-14B-Instruct-FP8-dynamic`
- Tool-call parser: `hermes`
- Player temperature: 0.7, Coach temperature: 0.3
- Max turns: 3, Target timeout: 600s

### Environment (Third Run — Nemotron, pending)

- Python: 3.14
- vLLM endpoint: `promaxgb10-41b1:8002`
- Model: `nvidia/NVIDIA-Nemotron-3-Nano-4B-FP8`
- Tool-call parser: `qwen3_coder`
- Player temperature: 0.7, Coach temperature: 0.3
- Max turns: 3, Target timeout: 600s
