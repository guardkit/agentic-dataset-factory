# Review Report: TASK-REV-R2A1 (Revised v2 — Source-Verified)

## Executive Summary

Factory-run-2 processed **3 of 20 targets** before crashing at index 3. Root cause analysis with full end-to-end message tracing confirms **two interacting bugs**:

1. **P0 — Dual system messages**: The retry path passes a `system` reinforcement message inside `retry_input`, but `create_agent()` unconditionally prepends the Coach's original system prompt via `MemoryMiddleware`. vLLM receives `[sys, sys, user]` and rejects with HTTP 400.
2. **P1 — Uncaught exception type**: `httpx.HTTPStatusError` is not caught by either `_invoke_with_retry()` or the per-target handler, so the 400 crashes the entire pipeline.

**Severity: BLOCKING** — the overnight run will crash on the first Coach JSON parse failure.

**Confidence: CONFIRMED FROM FRAMEWORK SOURCE** — root cause verified by reading the actual installed LangChain `create_agent()` source at `langchain/agents/factory.py:1270-1271`. The framework unconditionally prepends `system_message` with no guard against existing system messages in the input. Additionally confirmed by (a) end-to-end code trace through 4 system boundaries, (b) HTTP request payload from the run log, and (c) alignment check against all 6 architectural constraints from Runs 5-12.

TASK-OR-002 (grade distribution) is correctly implemented — target 0 shows grade 5 (not the old default 7), confirming round-robin is active.

## Review Details

- **Mode**: Architectural / Code Quality (hybrid, revised for depth)
- **Depth**: Comprehensive (revised from standard)
- **Parent Review**: TASK-REV-7617
- **Source**: `docs/reviews/longer-runs/factor-run2.md` (376-line pipeline log)
- **Historical Reviews Checked**: 16 reports (TASK-REV-7617, TRF4-12, FRF2-3, 1F3F, A1B4, E2A7, F5F5)
- **Graphiti Status**: Offline (FalkorDB connection error — NAS unreachable)

---

## C4 Sequence Trace: Normal vs Retry Message Flow

### Container Diagram — System Boundaries

```
┌─────────────────────────────────────────────────────────────────────┐
│ Python Process                                                       │
│                                                                      │
│  ┌──────────────┐    ┌──────────────────┐    ┌──────────────────┐   │
│  │ generation    │───>│ create_agent()   │───>│ MemoryMiddleware  │   │
│  │ _loop.py      │    │ (LangChain)      │    │ + PatchToolCalls  │   │
│  │              │    │                  │    │ + PromptCaching   │   │
│  │ Builds       │    │ Stores           │    │                  │   │
│  │ retry_input  │    │ system_prompt    │    │ Injects           │   │
│  │ dict         │    │ at creation      │    │ AGENTS.md into    │   │
│  │              │    │ time             │    │ system prompt     │   │
│  └──────────────┘    └──────────────────┘    └────────┬─────────┘   │
│                                                        │             │
│                                              ┌────────▼─────────┐   │
│                                              │ ChatOpenAI        │   │
│                                              │ (OpenAI compat    │   │
│                                              │  client)          │   │
│                                              └────────┬─────────┘   │
└───────────────────────────────────────────────────────┼─────────────┘
                                                        │ HTTP POST
                                              ┌────────▼─────────┐
                                              │ vLLM              │
                                              │ Qwen3.5-35B      │
                                              │ :8002/v1/chat/    │
                                              │ completions       │
                                              └──────────────────┘
```

### Sequence: Normal Coach Call (WORKING)

```
generation_loop.py          create_agent()           Middleware            vLLM
       │                         │                       │                  │
       │  coach_input =          │                       │                  │
       │  {messages:             │                       │                  │
       │    [{role:"user",       │                       │                  │
       │      content:player}]}  │                       │                  │
       │                         │                       │                  │
       │──ainvoke(coach_input)──>│                       │                  │
       │                         │──prepend sys_prompt──>│                  │
       │                         │                       │──inject AGENTS──>│
       │                         │                       │  md into prompt  │
       │                         │                       │                  │
       │                         │                       │  POST:           │
       │                         │                       │  [system(prompt  │
       │                         │                       │   +AGENTS.md),   │
       │                         │                       │   user(player)]  │
       │                         │                       │                  │
       │                         │                       │<────200 OK───────│
       │<───────────verdict──────│                       │                  │
```

**Key**: `create_agent()` stores `system_prompt` at construction time. On every `ainvoke()`, it prepends this as the first message. The input dict should contain only `user` messages.

### Sequence: Retry Coach Call (BROKEN)

```
generation_loop.py          create_agent()           Middleware            vLLM
       │                         │                       │                  │
       │  retry_input =          │                       │                  │
       │  {messages:             │                       │                  │
       │    [{role:"system",     │  ← BUG: system msg   │                  │
       │      content:reinf},    │    in input dict      │                  │
       │     {role:"user",       │                       │                  │
       │      content:player}]}  │                       │                  │
       │                         │                       │                  │
       │──ainvoke(retry_input)──>│                       │                  │
       │                         │──prepend sys_prompt──>│                  │
       │                         │  (unconditional!)     │──inject AGENTS──>│
       │                         │                       │  md into prompt  │
       │                         │                       │                  │
       │                         │                       │  POST:           │
       │                         │                       │  [system(prompt  │
       │                         │                       │   +AGENTS.md),   │
       │                         │                       │   system(reinf), │
       │                         │                       │   user(player)]  │
       │                         │                       │                  │
       │                         │                       │<──400 BAD REQ────│
       │                         │                       │  "System message │
       │                         │                       │   must be at the │
       │<───httpx.HTTPStatusError│                       │   beginning"     │
       │                         │                       │                  │
       │  Exception propagates   │                       │                  │
       │  through:               │                       │                  │
       │  _invoke_with_retry     │                       │                  │
       │  (misses HTTPStatusErr) │                       │                  │
       │  per-target handler     │                       │                  │
       │  (misses HTTPStatusErr) │                       │                  │
       │  ──> PIPELINE CRASH     │                       │                  │
```

### Evidence: Actual HTTP Payload from Run Log

The run log at `docs/reviews/longer-runs/factor-run2.md` contains the exact `json_data` sent during the retry. The request shows:

```json
{
  "messages": [
    {
      "role": "system",
      "content": [
        {"type": "text", "text": "You are a quality evaluator for training data generation..."},
        {"type": "text", "text": "\n\n<agent_memory>\n./AGENTS.md\n# Agent Boundaries..."}
      ]
    },
    {
      "role": "system",
      "content": "IMPORTANT: Your previous response was not valid JSON..."
    },
    {
      "role": "user",
      "content": "The user wants me to generate a training example for..."
    }
  ],
  "model": "Qwen/Qwen3.5-35B-A3B-FP8",
  "temperature": 0.3
}
```

vLLM response: `400 Bad Request: "System message must be at the beginning."`

### Coach Agent Creation (where system_prompt is stored)

File: `agents/coach.py`

```python
def create_coach(model_config, system_prompt, memory):
    model = create_model(model_config)
    backend = FilesystemBackend(root_dir=".")
    middleware = [
        MemoryMiddleware(backend=backend, sources=memory),  # injects AGENTS.md
        PatchToolCallsMiddleware(),
        AnthropicPromptCachingMiddleware(unsupported_model_behavior="ignore"),
    ]
    return create_agent(
        model=model,
        tools=[],                    # Coach has no tools (D5 invariant)
        system_prompt=system_prompt, # Stored, prepended on every ainvoke()
        middleware=middleware,
    )
```

### Framework Source Verification (langchain/agents/factory.py)

The LangChain `create_agent()` source code was read directly from the installed package. The critical path:

**Line 823-829** — system_prompt converted to SystemMessage at creation time:
```python
system_message: SystemMessage | None = None
if system_prompt is not None:
    system_message = SystemMessage(content=system_prompt)
```

**Line 1289-1294** — stored system_message passed into every ModelRequest:
```python
request = ModelRequest(
    model=model,
    system_message=system_message,   # original from create_agent()
    messages=state["messages"],       # our ainvoke() input
    ...
)
```

**Lines 1270-1271** — unconditional prepend before LLM invocation:
```python
messages = request.messages
if request.system_message:
    messages = [request.system_message, *messages]  # ALWAYS prepends
```

There is **no guard** against existing system messages in `request.messages`. The framework does not check `if messages[0].role == "system"`. It always prepends.

**MemoryMiddleware** (deepagents/middleware/memory.py:322-337) modifies `request.system_message` before this prepend, using `append_to_system_message()` (deepagents/middleware/_utils.py:6-23) to combine the original system prompt with AGENTS.md content into a single SystemMessage with multiple content blocks.

This means the correct contract for `ainvoke()` input is: **only pass `user` and `assistant` messages in the input dict — never `system` messages**. The framework owns system message injection.

---

## Finding 1: Dual System Messages in Coach Retry (CRITICAL)

**Severity**: P0 — Pipeline crash, overnight blocker
**Component**: `entrypoint/generation_loop.py:742-765`
**Confidence**: Confirmed — traced through all 4 system boundaries with HTTP payload evidence

### Root Cause (Detailed)

The retry at line 742 constructs `retry_input` with a `system` reinforcement message:

```python
retry_input = {
    "messages": [
        {"role": "system", "content": "IMPORTANT: Your previous response was not valid JSON..."},
        {"role": "user", "content": player_content},
    ]
}
```

This input is passed to `coach.ainvoke(retry_input)`. The `create_agent()` framework:
1. Takes the input messages array
2. **Unconditionally** prepends the system_prompt (stored at Coach creation time)
3. `MemoryMiddleware` injects `AGENTS.md` content into the system prompt
4. Sends the combined array to `ChatOpenAI` → httpx → vLLM

Result: `[system(prompt+AGENTS.md), system(reinforcement), user(player)]` — **two system messages**.

vLLM's OpenAI-compatible endpoint enforces: exactly one system message, at position 0. Two system messages trigger HTTP 400.

### Why Tests Missed This

The 35 tests in `test_coach_retry_json_reinforcement.py` mock `agent.ainvoke()` at the boundary. They validate the `retry_input` dict structure (correct) but never exercise the framework's system prompt prepending. This is the classic **mock-vs-integration gap** — the contract between `generation_loop.py` and `create_agent()` was not tested.

### Broken Assumption

The retry code assumes that passing a `system` message inside `retry_input` will replace or augment the framework-level system prompt. In reality, `create_agent()` has no such mechanism — it always prepends its own system prompt regardless of what's in the input.

The normal Coach call works because it only passes `[user]` messages, producing the correct `[system, user]` after framework prepending.

### Fix Recommendation

**Option B (preferred)**: Merge reinforcement into the user message content. This respects the framework's contract — input should contain only `user` messages:

```python
retry_input = {
    "messages": [
        {
            "role": "user",
            "content": (
                "IMPORTANT: Your previous response was not valid JSON. "
                "You MUST respond with ONLY a JSON object matching the "
                "CoachVerdict schema. No prose, no reasoning text, no "
                "markdown. Start your response with { and end with }.\n\n"
                + player_content
            ),
        },
    ]
}
```

**Why Option B over Option A** (two separate user messages):
- Single message avoids any framework edge cases with consecutive same-role messages
- Matches the normal call pattern (one user message in, framework prepends system)
- Simpler to reason about

---

## Finding 2: Missing Exception Type in Per-Target Handler (HIGH)

**Severity**: P1 — Causes Finding 1 to crash the pipeline instead of rejecting the target
**Component**: `entrypoint/generation_loop.py:1076` and `:396`
**Confidence**: Confirmed — exception type chain traced

### Root Cause

The exception propagation path:

```
vLLM returns HTTP 400
  → httpx raises httpx.HTTPStatusError
    → _invoke_with_retry catches (RuntimeError, OSError, TimeoutError, ValidationError)
      → HTTPStatusError NOT IN LIST → propagates
        → per-target handler catches (RuntimeError, OSError, ValidationError, ValueError)
          → HTTPStatusError NOT IN LIST → propagates
            → PIPELINE CRASH (unhandled exception)
```

### Architectural Context

This gap was introduced incrementally:
- **Run 9 (TASK-REV-1F3F R1)**: Added `ValueError` to per-target handler for Coach parse failures
- **Run 10**: Added `ValidationError` for vLLM tool_calls parsing edge case
- **Neither added** `httpx.HTTPStatusError` because prior to TASK-OR-001, no code path produced an HTTP error that wasn't wrapped in `RuntimeError` by the OpenAI client

The retry path is different — it can trigger a raw HTTP 400 from vLLM that the OpenAI client surfaces as `httpx.HTTPStatusError` (or `openai.BadRequestError`, which inherits from it).

### Fix Recommendation

**Layer 1 — `_invoke_with_retry` (line 396)**:
- Add `httpx.HTTPStatusError` but only retry on 429 (rate limit) and 5xx (server error)
- Do NOT retry 400 (client error — retrying won't help)

**Layer 2 — Per-target handler (line 1076)**:
- Add `httpx.HTTPStatusError` (catch-all for any HTTP error that escapes layer 1)
- Target gets rejected with `llm_failure` reason, pipeline continues

**Consider also**: Catching `openai.APIStatusError` (the OpenAI SDK's base class) which may wrap httpx errors differently depending on the client version.

---

## Finding 3: Grade Distribution — Working but Unverifiable (INFO)

**Severity**: Informational
**Confidence**: High (code verified, insufficient runtime data)

### Code Verification

TASK-OR-002 implementation verified across 5 files:
- `GOAL.md`: Grade Targets column added for all 20 categories
- `models.py`: `grade_targets` field with `[4-9, null]` validation
- `parser.py`: `_coerce_grade_targets()` parses bracket notation
- `generation_loop.py:645-646`: Round-robin via `target.grade_targets[target_index % len(target.grade_targets)]`
- `generation_loop.py:926-931`: Grade target injected into player prompt

### Run-2 Evidence

| Target | Category | Grade Target | Source |
|--------|----------|-------------|--------|
| 0 | Literary analysis (single-turn) | 5 | Player prompt in run log |
| 1 | Character analysis — Macbeth | visible | Player prompt |
| 2 | Character analysis — An Inspector Calls | visible | Player prompt |
| 3 | Character analysis — A Christmas Carol | 7 | Retry prompt before crash |

Target 0 shows grade 5, confirming the round-robin is selecting from `[5, 6, 7, 7, 8, 9]` (first element). This is a clear improvement over Run 1 where 92.3% of examples were Grade 7.

**Verdict**: Code working. Need a successful 20-target run to validate full distribution spread.

---

## Finding 4: All Accepted Examples Score 5/5 (LOW)

**Severity**: Low
**Component**: Coach evaluation calibration

| Target | Turn 1 | Turn 2 | Turn 3 | Final |
|--------|--------|--------|--------|-------|
| 0 | score 5 accept | score 5 accept | — | 5 |
| 1 | score 3 revise | score 5 accept | score 5 accept | 5 |
| 2 | score 5 accept | score 5 accept | — | 5 |

The revision loop works (target 1: 3→revise→5→accept), but final scores are uniformly 5. Monitor in next run; no action needed with 3-example sample.

---

## Finding 5: Token Usage (INFO)

| Metric | Run-2 (3 targets) | Per-Target Average |
|--------|-------------------|-------------------|
| Total tokens | ~68,311 | ~22,770 |
| Prompt tokens | ~56,821 | ~18,940 |
| Completion tokens | ~11,490 | ~3,830 |
| Turns per target | 2, 3, 2 | 2.3 avg |

Consistent with Run-1. The 3-turn target (revision) costs ~50% more tokens. Budget remains excellent (~8% of 262K context).

---

## Finding 6: TASK-OR-001 Detection Logic Working (POSITIVE)

Coach retry detection, logging, and single-retry guard all work correctly. The issue is exclusively the message format passed to `ainvoke()`, not the triggering logic.

---

## Architectural Alignment Check

The proposed fixes were validated against **all 6 architectural constraints** established across Runs 5-12:

| Constraint | Source | Fix Alignment | Status |
|------------|--------|--------------|--------|
| Coach reasoning stays enabled | Run 5 (TASK-REV-TRF5) | Fix does not change Coach reasoning config | PRESERVED |
| Layer 1 thinking flows intact to Coach | Run 9 R2 (TASK-REV-1F3F) | `player_content` passed unchanged in merged user message | PRESERVED |
| Two-layer think block architecture protected | Run 8 (TRF-024) | No changes to reasoning parser config | PRESERVED |
| Single retry only (no loop) | Run 9 R3 (TASK-REV-1F3F) | `coach_retried` flag unchanged | PRESERVED |
| Structured output remains P2 experimental | Run 12 (TASK-REV-7617) | Fix uses message format, not structured output | PRESERVED |
| ValueError caught at per-target level | Run 9 R1 (TASK-REV-1F3F) | Finding 2 extends catch list (additive, not breaking) | PRESERVED |

**No architectural constraints are violated by either fix.**

### Regression Risk Assessment

| Fix | Regression Risk | Mitigation |
|-----|----------------|------------|
| Finding 1: Change `system` to merged `user` | LOW — only affects retry path; normal path unchanged | Existing 35 tests + update assertions for new message format |
| Finding 2: Add `httpx.HTTPStatusError` to handlers | LOW — additive change to exception tuple | New test: mock 400/429/500 responses, verify pipeline continues |

### What NOT to Do (reaffirmed from prior reviews)

- Do NOT disable Coach reasoning (`enable_thinking: false`) — Run 5 FIRM decision
- Do NOT strip Layer 1 thinking before Coach input — Run 9 R2 withdrawn
- Do NOT add complex retry loops — single retry is architecturally approved
- Do NOT change Player/Coach prompts — they work for 85%+ of targets
- Do NOT re-enable `--reasoning-parser qwen3` — breaks Layer 2 think blocks

---

## Recommendations (Updated)

| # | Action | Priority | Blocks Overnight? | Arch. Aligned? |
|---|--------|----------|-------------------|----------------|
| 1 | Fix retry message: merge reinforcement into single `user` message (Option B) | P0 | YES | YES — all 6 constraints preserved |
| 2 | Add `httpx.HTTPStatusError` to per-target handler and `_invoke_with_retry` | P1 | YES (defense in depth) | YES — additive to Run 9 R1 |
| 3 | Add integration test for retry (real `create_agent` path, not mocked) | P2 | No | YES — closes mock-vs-integration gap |
| 4 | Run 20-target validation after fixes | P2 | Recommended | N/A |
| 5 | Monitor Coach score calibration in longer runs | P3 | No | N/A |

### Overnight Readiness Assessment

**NOT READY** — Fixes 1 and 2 required. Estimated effort: ~30 minutes code + ~30 minutes validation run.

---

## Metrics Comparison: Run-1 vs Run-2

| Metric | Run-1 (20 targets) | Run-2 (3 of 20) |
|--------|--------------------|--------------------|
| Completed | 20 | 3 (crash at index 3) |
| Accepted | 17 | 3 |
| Rejected | 3 | 0 + 1 crash |
| Acceptance rate | 85% | 75% (too small to compare) |
| Coach parse failures | ~3 (15%) | 1 (25%, crashed) |
| Grade diversity | 92.3% Grade 7 | Multiple grades (improved) |
| Pipeline status | Completed | Crashed |
| Tokens per target | ~25K | ~22.7K |

---

## Appendix A: Message Flow Summary

```
Normal Coach call:
  gen_loop builds:  {messages: [user(player)]}
  create_agent:     prepends system(prompt+AGENTS.md)
  vLLM receives:    [system, user]               → 200 OK ✓

Retry Coach call (CURRENT — broken):
  gen_loop builds:  {messages: [system(reinf), user(player)]}
  create_agent:     prepends system(prompt+AGENTS.md)
  vLLM receives:    [system, system, user]        → 400 BAD REQUEST ✗

Retry Coach call (FIXED — Option B):
  gen_loop builds:  {messages: [user(reinf + player)]}
  create_agent:     prepends system(prompt+AGENTS.md)
  vLLM receives:    [system, user]               → 200 OK ✓
```

## Appendix B: Historical Review Cross-References

| Review | Relevant Finding | Impact on This Fix |
|--------|-----------------|-------------------|
| TASK-REV-TRF5 (Run 5) | Coach reasoning must stay enabled | Fix preserves this |
| TASK-REV-1F3F (Run 9) | R1: ValueError handler; R2: withdrawn (no stripping); R3: retry deferred | Fix extends R1, respects R2, implements R3 |
| TASK-REV-7617 (Run 12) | F1: Coach retry with JSON reinforcement approved; Option A spec provided | Fix corrects the Option A message format only |
| TASK-REV-FRF2 (Run 2) | ValidationError for tool_calls.args edge case | Finding 2 extends same handler |
| TASK-REV-FRF3 (Run 3) | Message format stability confirmed | Fix maintains format stability |

## Appendix C: DeepAgents `ainvoke()` Message Contract (Source-Verified)

**Source**: `langchain/agents/factory.py` (installed package, lines 1270-1271, 1289-1294)

The `create_agent()` framework enforces this contract:

| What you pass to `ainvoke()` | What the framework does | What vLLM receives |
|------------------------------|------------------------|--------------------|
| `{messages: [user]}` | Prepends system_message | `[system, user]` — CORRECT |
| `{messages: [system, user]}` | Prepends system_message | `[system, system, user]` — BROKEN |
| `{messages: [user, assistant, user]}` | Prepends system_message | `[system, user, assistant, user]` — CORRECT |

**Rule**: Never include `system` role messages in the `ainvoke()` input dict. The framework owns system message injection via `system_prompt` parameter at agent creation time + middleware augmentation.

**Implication for retry**: Any additional instructions must be injected as `user` role messages, not `system` role messages.

## Appendix D: Excalidraw Diagrams

Three interactive diagrams were created during this review:
1. **Normal vs Retry Message Flow** — Sequence diagram showing the dual system message bug
2. **Exception Propagation Chain** — How `httpx.HTTPStatusError` escapes both catch layers
3. **Proposed Fix with Architectural Alignment** — Option B fix + 6-constraint validation grid
