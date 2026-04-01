# Learnings: 2500-Run Stall at Index 1405

**Date**: 2026-04-01
**Review**: TASK-REV-D0A8
**Run**: 2500-target GCSE English tutor dataset generation (Qwen3.5-35B-A3B-FP8 on GB10)

---

## 1. Incident Summary

The 2500-target generation run started 2026-03-31 12:34 UTC and stalled at index 1405 on 2026-04-01 16:37 UTC (28 hours wall-clock). The run produced 1,342 accepted training examples (53.7%) before terminating. The application process was running on a Mac laptop calling vLLM on a remote GB10 server over Tailscale. The process was suspended by macOS power management and never resumed.

**Impact**: 1,094 targets remaining unprocessed. ~87 minutes of wall-clock time lost to two Mac sleep events. ~40% of compute wasted on format gate retries.

---

## 2. Root Causes

### 2.1 Mac Process Suspension (Direct Cause of Stall)

The generation loop ran as `python agent.py` on `Richards-MBP` (Mac), not on the GB10 server. macOS power management suspended the process twice:

| Gap | Period | Duration | Recovery |
|-----|--------|----------|----------|
| #1 | 03-31 14:01 - 15:06 UTC | 65.5 min | Automatic (Mac woke, process resumed) |
| #2 | 04-01 16:13 - 16:35 UTC | 22.0 min | Automatic (Mac woke, process resumed) |
| Terminal | 04-01 16:37+ UTC | Permanent | **Never recovered** |

**Evidence**: TCP client port changes across gaps (57805 -> 65455 -> 54839 -> 56416), vLLM prefix cache preserved across gaps (no container restart), zero vLLM errors.

**Lesson**: Long-running generation loops MUST run on the server hosting the LLM, not on a laptop. Use `tmux` or `nohup` for process persistence.

### 2.2 Infinite HTTP Timeout (Latent Vulnerability)

Individual LLM calls have **no HTTP timeout**. The timeout chain:

```
httpx default:          5s all        -> Overridden by OpenAI SDK
OpenAI SDK default:     600s read     -> Defeated by LangChain
LangChain ChatOpenAI:   timeout=None  -> Passed explicitly, means "no timeout"
App model_factory.py:   (not passed)  -> Inherits None
App config llm_timeout: 300s          -> DEAD CONFIG (never wired)
App target_timeout:     600s          -> Only active protection
```

**The critical bug**: LangChain's `ChatOpenAI` has `request_timeout = Field(default=None)`. It passes `None` to the OpenAI SDK. The SDK uses a `NotGiven` sentinel pattern where `None` means "disable timeout" and only `NOT_GIVEN` triggers the 600s default. LangChain's `None` defeats the safety net.

**Lesson**: Always verify timeout propagation across framework boundaries. Don't assume a library's defaults are active -- middleware layers can override them.

### 2.3 Format Gate Failure Rate (Throughput Bottleneck)

The Player model (Qwen3.5-35B-A3B-FP8) produced plain reasoning text instead of JSON in 41% of attempts, worsening over time:

| Quartile | Format Gate Failures | Rate |
|----------|---------------------|------|
| Q1 (0-351) | 280 | 24.1% |
| Q2 (352-702) | 273 | 23.5% |
| Q3 (703-1053) | 280 | 24.1% |
| Q4 (1054-1405) | 325 | 28.0% |

The model outputs "The user wants me to generate a training example for..." (chain-of-thought reasoning) before or instead of the required JSON. This is the model's natural reasoning behaviour leaking into the visible response.

---

## 3. Cross-Boundary Execution Flow

The validated invocation chain for each LLM call:

```
Generation Loop (entrypoint/generation_loop.py)
  |
  | asyncio.wait_for(timeout=600s)        <- per-target timeout
  |
  +-> _invoke_with_retry(retries=3, backoff=2.0)
        |
        +-> agent.ainvoke(input)           <- no per-call timeout
              |
              +-> CompiledStateGraph.ainvoke()     [LangGraph]
                    |
                    +-> MemoryMiddleware            (reads ./AGENTS.md)
                    +-> PatchToolCallsMiddleware
                    |
                    +-> ChatOpenAI._agenerate()    [langchain-openai 1.1.12]
                          |
                          +-> openai.AsyncOpenAI    [openai 2.29.0]
                                .chat.completions
                                .create()
                                |
                                +-> httpx.AsyncClient  [httpx 0.28.1]
                                      .post()
                                      timeout=None (infinite!)
                                      |
                                      +-> TCP to GB10:8002
                                            via Tailscale
```

**Key boundaries**:
- Python asyncio -> LangGraph compiled graph (middleware stack)
- LangGraph -> LangChain ChatOpenAI (model invocation)
- LangChain -> OpenAI SDK (HTTP client creation, timeout defeated here)
- OpenAI SDK -> httpx (TCP connection, timeout=None inherited)
- httpx -> TCP/Tailscale -> vLLM on GB10

The project uses `langchain.agents.create_agent()` directly (not `create_deep_agent()`) to avoid DeepAgents' unconditional `FilesystemMiddleware` injection.

---

## 4. The LangChain Timeout Sentinel Bug

**Versions**: langchain-openai 1.1.12, openai 2.29.0, httpx 0.28.1

The OpenAI Python SDK uses a `NotGiven` sentinel to distinguish "user didn't pass this parameter" from "user explicitly set it to None":

```python
# openai/_client.py
class AsyncOpenAI:
    def __init__(self, timeout: float | Timeout | None | NotGiven = NOT_GIVEN):
        if is_given(timeout):       # True for None (it's not NOT_GIVEN)
            self.timeout = timeout   # None = no timeout
        else:
            self.timeout = DEFAULT_TIMEOUT  # 600s (never reached)
```

LangChain's `ChatOpenAI` has `request_timeout: float | None = Field(default=None)`. When it creates the OpenAI client, it passes `timeout=self.request_timeout` which is `None`. The SDK sees `None` as an explicit value (not `NOT_GIVEN`) and disables the timeout.

**Fix**: Pass a numeric timeout value through `init_chat_model()` or wrap `ainvoke()` with `asyncio.wait_for(timeout=llm_timeout)`.

---

## 5. Format Gate History

The format gate evolved through 6 stages across 12+ tasks:

| Stage | Task | Change | Outcome |
|-------|------|--------|---------|
| 1 | TRF (initial) | `_extract_json_object()` with 3-try strategy | Baseline extraction |
| 2 | TRF-025 | String-aware brace matching | Fixed Run 8 (100% extraction fail) |
| 3 | TRF-030 | `_repair_json_strings()` for literal newlines | Fixed Run 9 |
| 4 | TRF-031 | "CRITICAL -- Response Format" prompt section | Marginal improvement |
| 5 | FPF1 (test) | BAD/GOOD examples + "do not think out loud" | **22.1pp REGRESSION** |
| 6 | FPF1-001/002/003 | Revert bad prompt, harden gate, decouple retries | Current state |

**Key lesson from Stage 5**: Adding examples of bad output to the prompt **primes the model to replicate the bad pattern**. The regression was 100% attributable to prompt text changes (confirmed by framework validation: no LangChain/vLLM config changes).

The current format gate (Stage 6) successfully recovers ~60% of failures on first retry. The 41% failure rate causes throughput waste but does not affect output quality.

---

## 6. Why Structured Output Cannot Be Used for Player

The Coach uses vLLM xgrammar structured output (`extra_body: {"structured_outputs": {"json": CoachVerdict.model_json_schema()}}`), achieving zero format failures. This was explicitly NOT applied to the Player for four compounding reasons:

### 6.1 Tool Calling Conflict (Blocking)

The Player uses `rag_retrieval` in an agentic loop. vLLM structured output applies server-side to **every** completion request, including intermediate tool-call turns. A tool-call response is not JSON matching the training example schema -- xgrammar would reject it.

### 6.2 Variable-Length Messages Array (Blocking)

Single-turn examples have 3 messages; multi-turn essay feedback has 5-7+. The strict role-alternation pattern (system, user, assistant, user, assistant...) cannot be expressed in JSON Schema. xgrammar would allow invalid orderings.

### 6.3 Prose Quality Degradation (High Risk)

The Player's core value is in `content` string fields containing paragraphs of Socratic dialogue and `<think>` reasoning blocks. xgrammar modifies token sampling distribution to enforce valid JSON. For long prose passages, this risks quality degradation.

### 6.4 `<think>` Blocks Unenforceable by Schema

JSON Schema cannot express "this string must start with `<think>` and contain `</think>`". xgrammar adds cost without benefit for this requirement.

### Comparison: Why Coach Structured Output Works

| Dimension | Coach (CoachVerdict) | Player (Training Example) |
|-----------|---------------------|--------------------------|
| Schema complexity | Fixed keys, enums, booleans | Variable-length arrays, free-form text |
| Tool calls | None (D5 invariant) | `rag_retrieval` in agentic loop |
| Content fields | Short assessment text | Multi-paragraph Socratic dialogue |
| `<think>` blocks | Not required | Required for 75% of examples |
| xgrammar compatibility | Excellent | Incompatible |

---

## 7. Binding Architectural Decisions

These decisions from prior reviews are binding and must not be violated:

| Decision | Source | Rationale |
|----------|--------|-----------|
| Do NOT apply structured output to Player | TASK-LR1-001, TASK-REV-649A | Tool calls, variable messages, prose quality (see Section 6) |
| Do NOT add BAD/GOOD examples to Player prompt | TASK-FPF1-001 | Caused 22.1pp acceptance regression (see Section 5, Stage 5) |
| Do NOT add "do not think out loud" instruction | TASK-FPF1-001 | Part of the regression-causing prompt changes |
| Coach reasoning must stay ENABLED | Run 5 decision (TASK-REV-7617) | Disabling reasoning degrades Coach evaluation quality |
| Format retries decoupled from Coach turns | TASK-FPF1-003 | Format retries have separate counter from Coach revision turns |
| Checkpoint resume via append mode | ADR-ARCH-010 | Output files must be opened in append mode for resumability |

---

## 8. Operational Checklist for Future Long Runs

### Before Starting

- [ ] **Run on the LLM server, not a laptop** -- use `tmux` or `nohup` for persistence
- [ ] **Verify per-call timeout is wired** -- not just per-target timeout
- [ ] **Verify vLLM is healthy**: `curl localhost:8002/v1/models`
- [ ] **Check disk space** for output files and logs
- [ ] **Set up log capture**: redirect stdout/stderr to timestamped file
- [ ] **Verify checkpoint state**: `cat output/.checkpoint` (or confirm fresh start)
- [ ] **Test with 10 targets first** to validate config changes

### During Run

- [ ] **Monitor format gate rate** periodically: `grep -c "format gate" log`
- [ ] **Monitor acceptance rate**: `grep -c "target_accepted" log`
- [ ] **Check vLLM GPU utilisation**: `docker logs --tail 5 vllm-agentic-factory`
- [ ] **Watch for timeout warnings**: `grep "timeout" log`

### After Run

- [ ] **Verify output counts** match expectations: `wc -l output/train.jsonl`
- [ ] **Check rejection reasons** for new failure patterns: `grep "target_rejected" log | sort | uniq -c`
- [ ] **Save logs** for post-run review
- [ ] **Update checkpoint** if run completed successfully

### If Run Stalls

- [ ] Check if the process is still running: `tmux ls`
- [ ] Check vLLM health: `docker logs --tail 20 vllm-agentic-factory`
- [ ] Check for OOM or GPU errors
- [ ] If process died: resume from checkpoint (`python agent.py --resume`)
- [ ] If vLLM died: restart container, then resume from checkpoint
