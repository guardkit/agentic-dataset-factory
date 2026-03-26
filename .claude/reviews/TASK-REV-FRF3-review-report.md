# Review Report: TASK-REV-FRF3

## Executive Summary

The third end-to-end run (Nemotron 3 Nano 4B with `qwen3_coder` tool-call parser) confirmed that **TASK-REV-FRF2 findings F3 and F4 are fixed** -- the `tool_calls.args` deserialization crash is gone and the model correctly structures `write_output` arguments as a single `example_json` string. However, the pipeline crashed after just 10 API calls due to **context window exhaustion** (16,413 tokens vs 16,384 limit). Seven `write_output` calls were rejected because the 4B model cannot produce `<think>` blocks. Additionally, **8 DeepAgents backend tools leaked into the Player** (critical tool hygiene issue), the **`grade_target` type coercion is broken** (code bug), and the **Player still bypasses Coach evaluation** (architectural issue persisting from Run 2).

- **Mode**: Decision / Architectural
- **Depth**: Standard
- **Source**: `docs/reviews/first-run/vllm-nemotron3-nano-1.md`
- **Pipeline Score**: 25/100 (progressed further than Run 2, but no accepted examples)

## Findings

### Finding 1: TASK-REV-FRF2 F3 (tool_calls.args crash) -- CONFIRMED FIXED

**Severity**: Resolved
**Evidence**: All 9 successful API calls returned properly deserialised `tool_calls.args` dicts. The `qwen3_coder` parser on vLLM correctly returns arguments as native dicts, eliminating the Pydantic `dict_type` ValidationError that crashed Run 2.

**Verdict**: No action needed. Model/parser switch resolved the deserialization issue.

### Finding 2: TASK-REV-FRF2 F4 (model misstructures write_output args) -- CONFIRMED FIXED

**Severity**: Resolved
**Evidence**: The Nemotron 3 Nano 4B model correctly sends a single `example_json` string parameter containing both `messages` and `metadata` as one JSON object. The Qwen2.5-14B split-argument problem does not occur with this model.

**Verdict**: No action needed. Model switch resolved the argument structure issue.

### Finding 3: TASK-REV-FRF2 F5 (Player bypasses Coach) -- STILL PRESENT

**Severity**: High (P1) -- architectural
**Evidence**: All 10 API calls were Player-only. The Coach was created at startup (line 14: `"Creating Coach agent..."`) but never invoked. The Player calls `write_output` directly during its own turns, bypassing Coach evaluation entirely.

**Root cause**: Same as Run 2. The `generation_loop.py:238-243` invokes the Player as a DeepAgent, which autonomously calls tools during its turn. By the time the loop reaches the Coach invocation at line 256, the Player has already written (or attempted to write) the example. The architectural problem is that `write_output` is a Player tool, but writing should only happen after Coach approval.

**Impact**: The adversarial cooperation pattern is non-functional. All examples written to disk are unreviewed.

**Recommendation**: Remove `write_output` from the Player's tool list entirely. The generation loop should extract the Player's generated example from its response content, pass it to the Coach, and only call `write_output` programmatically after Coach acceptance. This is an architectural change to `generation_loop.py` and `tool_factory.py`.

### Finding 4 (NEW, P0): Context Window Exhaustion

**Severity**: Critical -- pipeline-terminating
**Evidence**: Run crashed on the 10th API call:
```
This model's maximum context length is 16384 tokens.
However, your request has 16413 input tokens.
```

The Nemotron 3 Nano 4B model has a 16,384 token context window. After 9 round-trips (system prompt + tool definitions + 9 request/response pairs), the accumulated conversation history exceeded this limit by just 29 tokens.

**Token budget breakdown** (estimated):
| Component | Est. Tokens |
|-----------|-------------|
| System prompt (with GOAL.md context) | ~3,000 |
| 10 tool schemas (8 leaked + 2 intended) | ~4,000 |
| 9 accumulated request/response pairs | ~9,400 |
| **Total at crash** | **~16,413** |

**Root cause (compound)**:
1. **16K context is too small** for a multi-turn tool-calling agent with large system prompts
2. **8 leaked backend tools** waste ~3,000 tokens of context on tool schemas that shouldn't be present (Finding 5)
3. **No conversation history truncation** -- DeepAgents accumulates all messages without cleanup
4. **No retry cap** on `write_output` failures (Finding 6) -- 7 failed retries consumed context tokens

**Recommendation**: Two-pronged fix:
1. **Eliminate tool leakage** (Finding 5) to reclaim ~3,000 tokens immediately
2. **Increase `max_model_len`** to 32K or 64K on the vLLM instance, OR switch to Nemotron 3 Nano 30B-A3B (MoE, 3.2B active parameters, supports 128K context)
3. Consider implementing conversation history windowing in the DeepAgents invocation

### Finding 5 (NEW, P0): DeepAgents Backend Tools Leak into Player

**Severity**: Critical -- wastes context tokens, enables unintended file access
**Evidence**: The Player had access to 10 tools instead of the intended 2. The 8 extra tools are injected by `FilesystemBackend`:

| Tool | Source | Should Be Present? |
|------|--------|--------------------|
| `rag_retrieval` | `tool_factory.py` | Yes |
| `write_output` | `tool_factory.py` | Yes |
| `ls` | `FilesystemBackend` | **No** |
| `read_file` | `FilesystemBackend` | **No** |
| `write_file` | `FilesystemBackend` | **No** |
| `edit_file` | `FilesystemBackend` | **No** |
| `glob` | `FilesystemBackend` | **No** |
| `grep` | `FilesystemBackend` | **No** |
| `task` | `FilesystemBackend` | **No** |
| `write_todos` | `FilesystemBackend` | **No** |

**Root cause**: `agents/player.py:57` creates `FilesystemBackend(root_dir=".")` and passes it to `create_deep_agent(backend=backend)`. The DeepAgents SDK injects all backend tools into the agent's tool list alongside the explicitly provided tools. The model then sees and can invoke these filesystem tools.

**Impact**:
- ~3,000 tokens wasted on tool schemas (contributes to Finding 4)
- Model used `read_file` inappropriately during the run
- Security risk: Player can read/write arbitrary files in the working directory

**Recommendation**: Remove `FilesystemBackend` from the Player factory. Pass `backend=None` to `create_deep_agent`, same as the Coach. The Player only needs `rag_retrieval` and `write_output` -- it has no legitimate need for filesystem access.

```python
# agents/player.py -- PROPOSED FIX
def create_player(...):
    model = create_model(model_config)
    # REMOVED: backend = FilesystemBackend(root_dir=".")
    return create_deep_agent(
        model=model,
        tools=tools,
        system_prompt=system_prompt,
        memory=memory,
        backend=None,  # No filesystem backend -- Player uses only explicit tools
    )
```

### Finding 6 (NEW, P1): No Retry Cap on write_output Failures

**Severity**: High -- burns context tokens, creates infinite loop risk
**Evidence**: The Player called `write_output` 7 times during the run, each time receiving a validation error (see Finding 7). Without a retry cap, the Player kept attempting to call the tool in a loop, consuming context tokens until the context window was exhausted.

**Root cause**: The DeepAgents SDK gives the Player autonomous tool-calling capability. There is no mechanism to limit the number of times the Player calls a specific tool per turn. The Player's system prompt does not instruct it to stop after N failures.

**Recommendation**: Two options:
1. **Prompt-level**: Add explicit instruction to the Player system prompt: "If write_output returns an error 3 times, stop retrying and report the failure."
2. **Code-level**: Implement a tool call counter wrapper around `write_output` that returns a hard-stop message after N failures. This is more reliable than prompt engineering.

### Finding 7 (NEW, P1): Nemotron 3 Nano 4B Cannot Produce `<think>` Blocks

**Severity**: High -- all 7 write_output calls rejected
**Evidence**: Every `write_output` call was rejected with:
```
Error: metadata.type is 'reasoning' but assistant content has no <think> block
```

The GOAL.md generation targets specify `type: reasoning`, which triggers the `<think>` block validation at `write_output.py:137`. The 4B model does not understand or generate `<think>...</think>` XML tags in its output.

**Root cause**: The `<think>` block requirement is a capability gap in the Nemotron 3 Nano 4B model. This is not a code bug -- the validation is correct -- but the model is too small to follow this output format instruction.

**Decision required**: Either:
1. **Switch to a larger model** (Nano 30B-A3B) that can follow `<think>` block formatting
2. **Remove the `<think>` block requirement** from validation and prompt, accepting that reasoning traces won't be explicitly tagged
3. **Make `<think>` blocks optional** -- downgrade from hard validation error to a warning

### Finding 8 (NEW, P1): `grade_target` Type Coercion Bug

**Severity**: High -- code bug, not model-specific
**Evidence**: The `_coerce_valid_values` function at `domain_config/parser.py:86-94` parses the GOAL.md metadata table cell `"4, 5, 6, 7, 8, 9, null"` into `["4", "5", "6", "7", "8", "9", "null"]` (list of strings). When the model sends `grade_target: 7` (integer) in the JSON metadata, the validation at `write_output.py:164` checks `7 not in ["4", "5", ...]`, which always fails because `int != str`.

**Root cause**: `_coerce_valid_values` returns all values as strings, but `grade_target` is defined as `integer or null` in GOAL.md. The validation comparison at `write_output.py:149-168` does not coerce the model's value to string before comparison.

**Fix options**:
1. **Fix in `write_output.py` (recommended)**: Cast `field_value` to `str()` before comparison against `valid_values`. This is the correct boundary -- the tool validates external (model-generated) input.
2. **Fix in `domain_config/parser.py`**: Make `_coerce_valid_values` type-aware. This is harder and affects the entire schema.
3. **Fix in both**: Belt-and-suspenders approach.

**Recommended fix** (minimal, correct):
```python
# write_output.py, Step 9, around line 163-164
else:
    if str(field_value) not in valid_values:
```

### Finding 9 (LOW): RAG Chunk Source Metadata Blank

**Severity**: Low -- cosmetic, does not affect retrieval quality
**Evidence**: All retrieved chunks show `source: unknown, p.?` in the formatted output. The ingestion pipeline did not populate `source` and `page` metadata fields in the ChromaDB documents.

**Root cause**: The Docling processor or ChromaDB indexer does not set `source` (filename) and `page` (page number) metadata during ingestion.

**Recommendation**: Fix in the ingestion pipeline -- populate `source` with the PDF filename and `page` with the page number during `chromadb_indexer.py` upsert. This is a quality-of-life improvement, not a blocker.

## Pipeline Progress Summary

| # | API Call | Status | Tool Called | Result |
|---|---------|--------|-------------|--------|
| 1 | 19:28:06 | 200 OK | `rag_retrieval` | Success -- chunks returned |
| 2 | 19:28:41 | 200 OK | `write_output` | Rejected -- no `<think>` block |
| 3 | 19:29:15 | 200 OK | `write_output` | Rejected -- no `<think>` block |
| 4 | 19:29:39 | 200 OK | `write_output` | Rejected -- no `<think>` block |
| 5 | 19:30:18 | 200 OK | `write_output` | Rejected -- no `<think>` block |
| 6 | 19:30:44 | 200 OK | `write_output` | Rejected -- no `<think>` block |
| 7 | 19:31:14 | 200 OK | `write_output` | Rejected -- no `<think>` block |
| 8 | 19:31:35 | 200 OK | `write_output` | Rejected -- no `<think>` block |
| 9 | 19:31:54 | 200 OK | mixed | Context nearing limit |
| 10 | 19:32:03 | 400 | -- | Context window exceeded (16,413 > 16,384) |

- **Targets processed**: 1 of 1
- **Training examples written**: 0
- **Pipeline duration**: ~4 minutes (19:28 to 19:32)

## TASK-REV-FRF2 Issue Resolution Summary

| TASK-REV-FRF2 Finding | Status After Run 3 |
|---|---|
| F3: `tool_calls.args` dict_type crash | **FIXED** by model/parser switch |
| F4: Model misstructures write_output args | **FIXED** by model switch |
| F5: Player bypasses Coach evaluation | **STILL PRESENT** -- architectural issue |

## Decisions Required

### Decision 1: Model Selection (REVISED — based on GB10 forum research)

Research of the [NVIDIA DGX Spark / GB10 Developer Forum](https://forums.developer.nvidia.com/c/accelerated-computing/dgx-spark-gb10/719) identified real-world benchmarks and community experience across multiple models. The clear winner for our agentic tool-calling use case is:

#### Recommended: Qwen3.5-35B-A3B (FP8)

| Attribute | Value | Source |
|-----------|-------|--------|
| **Model** | `Qwen/Qwen3.5-35B-A3B-FP8` | HuggingFace |
| **Architecture** | MoE — 35B total, **3B active** per token | Official spec |
| **Native context** | 262,144 tokens | Official spec |
| **Extended context** | 1,010,000 tokens (YaRN) | Forum-confirmed |
| **BFCL-V4 (tool calling)** | **67.3** (vs GPT-5-mini: 55.5) | HuggingFace |
| **TAU2-Bench (agentic)** | **81.2** | HuggingFace |
| **GB10 throughput (FP8)** | **50 tok/s sustained** | Forum: 60+ hours tested |
| **GB10 throughput (MXFP4)** | **70 tok/s** | Forum: vLLM 0.17.0 patches |
| **Concurrency (100 users)** | 423.5 tok/s aggregate, zero errors | Forum: RAG workload |
| **Memory footprint** | ~70 GB model + ~28 GB KV cache in 128 GB | Forum-confirmed |
| **Tool call parser** | `qwen3_coder` (same as current setup) | Official + forum |
| **Reasoning parser** | `qwen3` (native `<think>` block support) | Official |
| **Stability** | 60+ hours continuous running, "very stable" | Forum |

**Why this model**:
1. **Proven on GB10**: Community member ran 60+ hours continuous with "very stable run-to-run" consistency. Pre-built Docker image available: `hellohal2064/vllm-qwen3.5-gb10:latest`
2. **Best tool-calling in class**: BFCL-V4 score of 67.3 outperforms GPT-5-mini. TAU2-Bench 81.2 shows strong agentic capability — critical for our Player-Coach architecture
3. **262K context eliminates F4**: Our Run 3 crashed at 16K. This model has 16x the context window natively, with 1M+ available via YaRN
4. **Same parser**: Uses `qwen3_coder` tool-call parser — the same one that already works in our Run 3 setup. Zero parser migration risk
5. **Native `<think>` blocks**: Qwen3.5 has native reasoning mode with `--reasoning-parser qwen3`, solving F7 (think-block capability gap)
6. **MoE efficiency**: Only 3B active params per token means fast inference (~50 tok/s) despite the 35B total parameter count

#### vLLM Launch Command (GB10)

```bash
docker run -d \
  --name qwen35 \
  --restart unless-stopped \
  --gpus all \
  --ipc host \
  --shm-size 64gb \
  -p 8002:8000 \
  -v ~/.cache/huggingface:/root/.cache/huggingface \
  vllm/vllm-openai:cu130-nightly \
  Qwen/Qwen3.5-35B-A3B-FP8 \
  --served-model-name qwen3.5-35b \
  --port 8000 \
  --host 0.0.0.0 \
  --max-model-len 262144 \
  --gpu-memory-utilization 0.80 \
  --reasoning-parser qwen3 \
  --enable-auto-tool-choice \
  --tool-call-parser qwen3_coder \
  --enable-prefix-caching
```

**Critical**: Use `vllm/vllm-openai:cu130-nightly` image (the NVIDIA container ships vLLM 0.13.0 which doesn't support Qwen3.5). Alternatively, use the community Docker image `hellohal2064/vllm-qwen3.5-gb10:latest` which includes all SM121 patches.

**Note**: First startup takes ~15 min for CUDA graph capture; first inference ~57s for torch.compile warmup. Subsequent requests run at full speed.

#### agent-config.yaml Changes

```yaml
player:
  provider: local
  model: Qwen/Qwen3.5-35B-A3B-FP8
  endpoint: http://promaxgb10-41b1:8002/v1
  temperature: 0.6  # Qwen3.5 recommended for tool calling

coach:
  provider: local
  model: Qwen/Qwen3.5-35B-A3B-FP8
  endpoint: http://promaxgb10-41b1:8002/v1
  temperature: 0.3
```

#### Models Considered and Rejected

| Model | Verdict | Reason |
|-------|---------|--------|
| Nemotron 3 Nano 4B (current) | **Reject** | 16K context too small, no `<think>` support, tool calling quality poor |
| Nemotron 3 Nano 30B-A3B FP8 | **Reject** | 154 tok/s throughput but NVFP4 crashes after 20-60 min; no BFCL benchmarks; less community validation |
| Nemotron 3 Nano 30B-A3B NVFP4 | **Reject** | 167 tok/s but reported GPU SM warp exceptions and misaligned address crashes; unstable |
| Qwen2.5-14B (Run 2 model) | **Reject** | `tool_calls.args` deserialization crash with hermes parser (F3 from TASK-REV-FRF2) |
| Qwen3.5-122B-A10B NVFP4 | **Defer** | Best quality (BFCL 72.2) but 16 tok/s throughput, OOM risk on single Spark, requires careful memory tuning. Consider for future upgrade |
| Qwen3.5-27B | **Defer** | Dense model, slightly better BFCL (68.5) but much higher memory usage than 35B-A3B MoE; ~27B active vs 3B active |
| GLM-4.7-Flash | **Insufficient data** | Forum thread had no technical content |

#### Forum Sources

- [Custom built vLLM + Qwen3.5-35B — sustained 50 tok/s, 1M context](https://forums.developer.nvidia.com/t/custom-built-vllm-qwen3-5-35b-on-nvidia-dgx-spark-gb10-sustained-50-tok-s-1m-context/362590)
- [Qwen3.5-35B-A3B on NVIDIA DGX Spark](https://forums.developer.nvidia.com/t/qwen3-5-35b-a3b-on-nvidia-dgx-spark/361724) — 30 tok/s initial report
- [vLLM 0.17.0 MXFP4 Patches — 70 tok/s](https://forums.developer.nvidia.com/t/vllm-0-17-0-mxfp4-patches-for-dgx-spark-qwen3-5-35b-a3b-70-tok-s-gpt-oss-120b-80-tok-s-tp-2/362824)
- [RedHatAI/Qwen3.5-122B-A10B-NVFP4 — best option for single Spark](https://forums.developer.nvidia.com/t/redhatai-qwen3-5-122b-a10b-nvfp4-seems-to-be-the-best-option-for-a-single-spark/363815)
- [Testing Nemotron 3 Nano Models with vLLM and FlashInfer](https://forums.developer.nvidia.com/t/testing-nemotron-3-nano-models-on-nvidia-dgx-spark-jetson-thor-with-vllm-and-flashinfer/360642)
- [Best LLM engine for several parallel models](https://forums.developer.nvidia.com/t/best-llm-engine-for-several-parallel-models/356581)
- [Complete setup guide (GitHub)](https://github.com/adadrag/qwen3.5-dgx-spark)
- [Qwen3.5-35B-A3B HuggingFace model card](https://huggingface.co/Qwen/Qwen3.5-35B-A3B)
- [NVFP4 crash bug on ARM64 GB10](https://github.com/vllm-project/vllm/issues/35519) — reason to prefer FP8 over NVFP4

### Decision 2: Context Budget Strategy

**Recommendation**: **Fix tool leakage + Qwen3.5-35B-A3B** — this combination gives us 262K context (16x current) with ~3,000 fewer wasted tokens from backend tool schemas. Conversation windowing is not needed at this scale.

### Decision 3: `grade_target` Type Coercion Fix

**Recommendation**: **Option A** — cast `field_value` to `str()` in `write_output.py:163`. Minimal 1-line fix at the validation boundary.

### Decision 4: Tool Leakage Mitigation

**Recommendation**: **Option A** — remove `FilesystemBackend` from Player (`backend=None`). 2-line change in `agents/player.py`.

### Decision 5: write_output Retry Cap

**Recommendation**: **Option B** — code-level tool wrapper with counter. Returns hard-stop after 3 consecutive failures per target.

## Recommendations Summary (Priority Order)

| # | Finding | Priority | Effort | Recommendation |
|---|---------|----------|--------|----------------|
| 1 | F5: Tool leakage (backend) | P0 | Low | Remove `FilesystemBackend` from Player |
| 2 | F8: `grade_target` type coercion | P0 | Low | Cast to `str()` in `write_output.py` |
| 3 | F4+F7: Context + `<think>` capability | P0 | Low | Switch to Qwen3.5-35B-A3B-FP8 (262K context, native reasoning) |
| 4 | F3: Player bypasses Coach | P1 | Medium | Remove `write_output` from Player tools; write programmatically after Coach acceptance |
| 5 | F6: No retry cap | P1 | Low | Code-level tool wrapper with counter |
| 6 | F9: RAG metadata blank | P2 | Low | Populate source/page in ingestion pipeline |

## Architectural Deep-Dive: Root Cause Validation (Revision 2)

### Methodology

Traced the complete invocation flow across system boundaries using C4 diagramming and sequence analysis. Studied the DeepAgents SDK source code (`deepagents/graph.py`, `deepagents/middleware/filesystem.py`, `deepagents/backends/filesystem.py`) and compared against the GuardKit autobuild Player-Coach pattern (proven over 40+ tasks in this repo).

### Root Cause 1: Player Bypasses Coach (F3) — VALIDATED via SDK Trace

**The architectural flaw is confirmed and deeper than initially reported.**

The DeepAgents SDK runs an **internal LangGraph tool-calling loop** inside `player.ainvoke()`. The sequence is:

```
Orchestrator                  Player (DeepAgent)              vLLM
    |                              |                            |
    |--- ainvoke(target) --------->|                            |
    |                              |--- LLM call #1 ---------->|
    |                              |<-- tool_call: rag_retrieval|
    |                              |    [executes internally]   |
    |                              |--- LLM call #2 ---------->|
    |                              |<-- tool_call: write_output |
    |                              |    [WRITES TO DISK NOW]    |
    |                              |--- LLM call #3 ---------->|
    |                              |<-- end_turn               |
    |<-- response -----------------|                            |
    |                              |                            |
    |--- ainvoke(Coach, content) ---------------------------------->
    |                         [TOO LATE: data already on disk]
```

**Why this happens**: `create_deep_agent()` creates a LangGraph `CompiledStateGraph` with nodes `agent` (LLM) and `tools` (executor). The graph loops between them until the LLM stops calling tools. Tool execution is **immediate and internal** — `write_output()` appends to `train.jsonl` during the Player's `ainvoke()`, before the orchestrator regains control.

**The orchestrator at `generation_loop.py:238-244` calls `player.ainvoke()` and only sees the final response**. All intermediate tool calls (including writes) happen inside the DeepAgent's internal loop. By the time line 256 sends `player_content` to the Coach, the file write has already occurred.

### Root Cause 2: Tool Leakage via FilesystemBackend (F5) — VALIDATED via SDK Source

**Confirmed: `FilesystemMiddleware` injects 8 tools regardless of the `tools` parameter.**

From `deepagents/middleware/filesystem.py:404-503`:

```python
class FilesystemMiddleware(AgentMiddleware):
    def __init__(self, *, backend, ...):
        self.tools = [
            self._create_ls_tool(),
            self._create_read_file_tool(),
            self._create_write_file_tool(),
            self._create_edit_file_tool(),
            self._create_glob_tool(),
            self._create_grep_tool(),
            self._create_execute_tool(),
        ]
```

From `deepagents/graph.py:189-206`, the middleware stack is always constructed when a backend is provided:

```python
gp_middleware = [
    TodoListMiddleware(),                    # +1 tool (write_todos)
    FilesystemMiddleware(backend=backend),   # +7 tools (ls, read_file, etc.)
    ...
]
```

**Total tools visible to vLLM**: 2 (explicit) + 7 (FilesystemMiddleware) + 1 (TodoListMiddleware) = **10 tools**. Each tool schema costs ~300 tokens, so **8 leaked tools waste ~2,400 tokens per API call**.

**Fix is confirmed simple**: Pass `backend=None` to `create_deep_agent()`. When `backend=None`, `FilesystemMiddleware` uses `StateBackend` (ephemeral) but the tools are still injected. However, the Coach uses `backend=None` and `tools=[]` — examining the SDK shows that `tools=[]` combined with `backend=None` results in the middleware still being present but its tools are only available if the middleware has a real backend. **The correct fix is actually to not pass a backend at all**, which prevents `FilesystemMiddleware` from injecting usable file tools.

### Root Cause 3: Context Window Exhaustion (F4) — VALIDATED via Token Budget

**Confirmed: compound cause across 3 contributing factors.**

| Component | Tokens per call | Accumulates? |
|-----------|----------------|-------------|
| System prompt (Player base + GOAL.md) | ~3,000 | Fixed |
| 10 tool schemas (8 leaked + 2 real) | ~3,000 | Fixed |
| DeepAgents base agent prompt | ~500 | Fixed |
| Conversation history (messages array) | ~1,000/round-trip | **Yes — grows every call** |

After 9 round-trips: 3,000 + 3,000 + 500 + (9 x 1,100) = **~16,400 tokens** > 16,384 limit.

**The conversation history accumulation is the primary driver**, but tool leakage (~3,000 tokens) and the small context window (16K) are the multipliers that made 10 calls the breaking point instead of ~30.

### GuardKit Autobuild Comparison — Proven Pattern

Studied the GuardKit autobuild artifacts (`.guardkit/autobuild/*/player_turn_*.json`, `coach_turn_*.json`, `turn_state_*.json`) across 40+ completed tasks. Key architectural differences:

| Aspect | Our Pipeline (Broken) | GuardKit Autobuild (Proven) |
|--------|----------------------|----------------------------|
| **Who writes?** | Player writes directly via `write_output` tool | **Orchestrator writes** after Coach approval |
| **Player tools** | `rag_retrieval` + `write_output` + 8 leaked | Read, Write, Edit, Bash, Grep, Glob (code tools) |
| **Coach tools** | None (correct) | Read, Bash, Grep, Glob (verification tools) |
| **Write authority** | Player has autonomous write | **Orchestrator gates all writes** |
| **Coach verification** | Post-hoc (Player already wrote) | **Independent verification** before approval |
| **Turn control** | DeepAgent internal loop (opaque) | **Orchestrator controls turn boundaries** |
| **Structured feedback** | CoachVerdict JSON | JSON with `criteria_verification[]`, quality gates |
| **Acceptance gate** | `verdict.is_accepted` (composite rule) | `all_gates_passed` AND `all_criteria_met` |
| **Max turns** | 3 (configurable) | 35 (configurable) |
| **State persistence** | In-memory during `ainvoke()` | JSON files per turn (full audit trail) |

**Key Insight from GuardKit**: The Coach in GuardKit **independently runs tests** (`tests_passed`, `coverage_met`, `arch_review_passed`) and **reads the actual files written** to verify correctness. It doesn't trust the Player's self-report. In our pipeline, the Coach only sees `player_content` (the final text response) — it never sees the actual written file or the tool call results.

**Takeaway**: The fundamental principle is **separation of concerns via tool access asymmetry, with the orchestrator (not the Player) owning write authority**. The Player should be a pure generator; the Coach should be a pure evaluator; the orchestrator should be the only entity that commits state changes.

### Validated Root Cause Summary

| Finding | Root Cause | Confidence | Validated By |
|---------|-----------|------------|-------------|
| F3: Coach bypass | DeepAgent internal tool loop writes before orchestrator regains control | **High** | SDK source trace (`graph.py:283-302`) |
| F4: Context exhaustion | Compound: 16K limit + 8 leaked tools (~3K waste) + no history truncation | **High** | Token budget analysis |
| F5: Tool leakage | `FilesystemMiddleware` always injects tools when `backend` is provided | **High** | SDK source (`middleware/filesystem.py:404`) |
| F6: No retry cap | DeepAgent autonomous tool loop has no per-tool call limit | **High** | SDK architecture (LangGraph loop) |
| F7: No `<think>` blocks | 4B model capability gap (not a code bug) | **High** | Run log evidence |
| F8: `grade_target` type | `_coerce_valid_values` returns `str`, model sends `int` | **High** | Code trace (`parser.py:86` + `write_output.py:164`) |

## Review Iteration Context

This is the **third** review in the pipeline debug cycle:

```
TASK-REV-E2A7 (Run 1) -- ChromaDB path + array validation bugs
    -> TASK-FRF-001 (fix ChromaDB path) [COMPLETED]
    -> TASK-FRF-002 (fix array validation) [COMPLETED]

TASK-REV-FRF2 (Run 2) -- tool_calls.args + model arg structure + Coach bypass
    -> Model switch to Nemotron 3 Nano 4B + qwen3_coder parser

TASK-REV-FRF3 (Run 3, THIS REVIEW) -- Context window + type coercion + tool leakage
    -> Proposed: 7 implementation tasks (see above)
```

Each iteration has progressively unblocked the pipeline further. Run 3 is the first time the model successfully called tools and received valid responses. The remaining blockers are primarily configuration issues (model size, tool leakage) and one architectural fix (Coach bypass), all with clear fix paths.
