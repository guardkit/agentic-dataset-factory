# Review Report: TASK-REV-1F3F (Revised)

## Executive Summary

Run-9 crashed after completing only 2 of 20 targets. Two independent issues were identified, but only **one is actionable** — the other is an inherent property of the model that existing architecture already mitigates (when the pipeline doesn't crash).

1. **Pipeline bug (the crash)**: `_parse_coach_verdict()` raises `ValueError`, but the per-target error handler at [generation_loop.py:1011](entrypoint/generation_loop.py#L1011) only catches `RuntimeError | OSError | ValidationError`. The `ValueError` propagates through 4 levels of call stack and kills the entire pipeline.

2. **Model behaviour (the trigger)**: Qwen3.5-35B Coach intermittently returns Player-like reasoning text instead of a JSON verdict. This is stochastic and **cannot be eliminated** — but the pipeline is already designed to handle it (reject target, continue). The crash happens because the exception type isn't caught, not because the error is unrecoverable.

**The count change is the statistical trigger.** Run-8 processed 1 target; run-9 processes 20. With ~5% Coach role confusion probability per target, hitting it within 20 targets is expected (~64% cumulative probability).

---

## C4 Context: System Boundaries

```
┌──────────────────────────────────────────────────────────────┐
│                    Generation Pipeline                        │
│  ┌─────────┐    ┌────────────┐    ┌────────────┐            │
│  │ agent.py │───→│ generation │───→│ synthesis/ │            │
│  │ (entry)  │    │ _loop.py   │    │ validator  │            │
│  └─────────┘    └─────┬──────┘    └────────────┘            │
│                       │                                      │
│              ┌────────┴────────┐                             │
│              ▼                 ▼                              │
│  ┌──────────────────┐ ┌──────────────────┐                  │
│  │   Player Agent   │ │   Coach Agent    │                  │
│  │ (create_agent)   │ │ (create_agent)   │                  │
│  │ tools: [rag]     │ │ tools: []        │                  │
│  └────────┬─────────┘ └────────┬─────────┘                  │
│           │                    │                             │
└───────────┼────────────────────┼─────────────────────────────┘
            │                    │
            ▼                    ▼
┌──────────────────────────────────────────────────────────────┐
│               vLLM on promaxgb10-41b1:8002                   │
│               Qwen/Qwen3.5-35B-A3B-FP8                      │
│               --tool-call-parser qwen3_coder                 │
│               (NO --reasoning-parser — disabled TRF-024)     │
└──────────────────────────────────────────────────────────────┘
```

---

## Sequence Diagram: Normal Flow (Index 0 — Succeeded)

```
agent.py        generation_loop     Player (vLLM)      Coach (vLLM)
   │                  │                  │                  │
   │  run_pipeline()  │                  │                  │
   │─────────────────→│                  │                  │
   │                  │                  │                  │
   │                  │ rag_prefetch()   │                  │
   │                  │─ ─ ─ ─ ─ ─ ─ ─→│                  │
   │                  │ 1929 chars       │                  │
   │                  │← ─ ─ ─ ─ ─ ─ ─ ─│                  │
   │                  │                  │                  │
   │                  │ Player turn 1    │                  │
   │                  │ (target + RAG    │                  │
   │                  │  context)        │                  │
   │                  │─────────────────→│                  │
   │                  │                  │                  │
   │                  │ player_content   │                  │
   │                  │ (3871 chars)     │                  │
   │                  │ [<think>reasoning│                  │
   │                  │  </think>        │                  │
   │                  │  {JSON example}] │                  │
   │                  │←─────────────────│                  │
   │                  │                  │                  │
   │                  │ _extract_player_ │                  │
   │                  │ content()        │                  │
   │                  │ PATH 1: string   │                  │
   │                  │ (3871 chars)     │                  │
   │                  │                  │                  │
   │                  │ Coach evaluates  │                  │
   │                  │ (full player_    │                  │
   │                  │  content as      │                  │
   │                  │  user message)   │                  │
   │                  │──────────────────┼─────────────────→│
   │                  │                  │                  │
   │                  │                  │   JSON verdict   │
   │                  │                  │   {"decision":   │
   │                  │                  │    "accept",     │
   │                  │                  │    "score": 5}   │
   │                  │←─────────────────┼──────────────────│
   │                  │                  │                  │
   │                  │ _parse_coach_    │                  │
   │                  │ verdict() ✓      │                  │
   │                  │                  │                  │
   │                  │ normalise_think_ │                  │
   │                  │ closing_tags()   │                  │
   │                  │                  │                  │
   │                  │ _extract_example_│                  │
   │                  │ json() ✓         │                  │
   │                  │                  │                  │
   │                  │ write_tool ✓     │                  │
   │                  │                  │                  │
   │                  │ checkpoint.save()│                  │
   │                  │                  │                  │
```

---

## Sequence Diagram: Failure Flow (Index 2 — Crashed)

```
agent.py        generation_loop     Player (vLLM)      Coach (vLLM)
   │                  │                  │                  │
   │                  │ Player turn 1    │                  │
   │                  │─────────────────→│                  │
   │                  │                  │                  │
   │                  │ player_content   │                  │
   │                  │ (4042 chars)     │                  │
   │                  │ ["<think>        │                  │
   │                  │  The user wants  │                  │
   │                  │  me to generate  │                  │
   │                  │  a training      │                  │
   │                  │  example for:    │                  │
   │                  │  - Category:...  │                  │
   │                  │  </think>        │                  │
   │                  │                  │                  │
   │                  │  {JSON example}"]│                  │
   │                  │←─────────────────│                  │
   │                  │                  │                  │
   │                  │ Coach evaluates  │                  │
   │                  │ (full 4042 chars │                  │
   │                  │  incl. Player's  │                  │
   │                  │  <think> block)  │                  │
   │                  │──────────────────┼─────────────────→│
   │                  │                  │                  │
   │                  │                  │  ╔══════════════╗│
   │                  │                  │  ║ ROLE         ║│
   │                  │                  │  ║ CONFUSION    ║│
   │                  │                  │  ║              ║│
   │                  │                  │  ║ Coach mimics ║│
   │                  │                  │  ║ Player's CoT ║│
   │                  │                  │  ║ instead of   ║│
   │                  │                  │  ║ returning    ║│
   │                  │                  │  ║ JSON verdict ║│
   │                  │                  │  ╚══════════════╝│
   │                  │                  │                  │
   │                  │ "The user wants  │                  │
   │                  │  me to generate  │                  │
   │                  │  a training..."  │                  │
   │                  │←─────────────────┼──────────────────│
   │                  │                  │                  │
   │                  │ _extract_coach_  │                  │
   │                  │ content()        │                  │
   │                  │ PATH 1: string   │                  │
   │                  │ (non-empty)  ✓   │                  │
   │                  │                  │                  │
   │                  │ _parse_coach_    │                  │
   │                  │ verdict()        │                  │
   │                  │ _extract_json_   │                  │
   │                  │ object()         │                  │
   │                  │ Try 1: direct ✗  │                  │
   │                  │ Try 2: fence  ✗  │                  │
   │                  │ Try 3: brace  ✗  │                  │
   │                  │                  │                  │
   │                  │ ┌─────────────┐  │                  │
   │                  │ │ ValueError  │  │                  │
   │                  │ │ "no JSON    │  │                  │
   │                  │ │  object     │  │                  │
   │                  │ │  found"     │  │                  │
   │                  │ └──────┬──────┘  │                  │
   │                  │        │         │                  │
   │                  │        ▼         │                  │
   │                  │ NOT CAUGHT by    │                  │
   │                  │ per-target       │                  │
   │                  │ handler (only    │                  │
   │                  │ catches Runtime, │                  │
   │                  │ OS, Validation)  │                  │
   │                  │        │         │                  │
   │  ╔═══════════╗  │        │         │                  │
   │  ║ ValueError║←─┼────────┘         │                  │
   │  ║ propagates║  │                  │                  │
   │  ║ to top    ║  │                  │                  │
   │  ╚═════╤═════╝  │                  │                  │
   │        │        │                  │                  │
   │        ▼        │                  │                  │
   │  except Exception│                  │                  │
   │  (catch-all)    │                  │                  │
   │  "Pipeline      │                  │                  │
   │   failed: ..."  │                  │                  │
   │  exit(1)        │                  │                  │
```

---

## Exception Propagation Chain (Verified)

```
Level 1: _parse_coach_verdict()        [generation_loop.py:351]
         raises ValueError("Failed to parse CoachVerdict: no JSON...")
              │
              ▼ NOT wrapped in try/except
Level 2: _process_single_target()      [generation_loop.py:726]
         verdict = _parse_coach_verdict(coach_content)  ← bare call
              │
              ▼ propagates through asyncio.wait_for()
Level 3: run_generation_loop()         [generation_loop.py:951-1032]
         try:
             await asyncio.wait_for(_process_single_target(...), ...)
         except asyncio.TimeoutError:     ← doesn't match ValueError
             ...
         except (RuntimeError, OSError,   ← doesn't match ValueError
                 ValidationError):
             ...
              │
              ▼ NO handler at function level
Level 4: run_generation_loop()         [generation_loop.py:883]
         No outer try/except — ValueError escapes
              │
              ▼ through asyncio.run()
Level 5: run_pipeline()               [agent.py:228]
         except Exception as exc:      ← CATCHES HERE (catch-all)
             logger.error("Pipeline failed: %s", exc, exc_info=True)
             return PipelineState(error=str(exc))
```

**Confirmed**: `ValueError` is not caught at Level 3 (per-target handler). Pipeline crashes.

---

## Historical Context: The `</think>` Block Journey (Runs 1-10)

This section is critical. The `</think>` handling has been through 8 iterations across 10 runs. Any fix must respect these decisions.

### Timeline

| Run | Issue | Decision | Rationale | Task |
|-----|-------|----------|-----------|------|
| 5 | vLLM `--reasoning-parser qwen3` strips Coach verdict JSON into `reasoning_content` field | Add `reasoning_content` fallback to `_extract_coach_content()` | LangChain ignores non-standard field | TRF-013 |
| 6 | Player's `<think>` blocks appear malformed (missing `</think>`) | Observe but don't fix yet | Need to understand Layer 1 vs Layer 2 | — |
| 7 | 94% of `<think>` blocks unclosed; JSON extraction fails | Call `normalise_think_closing_tags()` BEFORE JSON extraction | Fix malformed: `<think>...<think>` and `<think>...EOF` | TRF-020, TRF-021 |
| 8 | **KEY**: `--reasoning-parser qwen3` strips `<think>` from INSIDE training example JSON strings (Layer 2) | **DISABLE** `--reasoning-parser qwen3` | Layer 2 think blocks are pedagogical content, not model reasoning; parser can't distinguish layers | TRF-024 |
| 8 | Brace-matching JSON extractor breaks on `{` inside strings | String-aware brace matching | Track `in_string` state during scan | TRF-025 |
| 9 | Without reasoning parser, model thinking appears as raw text in `.content` | Add `reasoning_content` fallback to `_extract_player_content()` | Defence-in-depth for vLLM interop | TRF-026 |
| 10 | Think blocks now flow through; Player prompt needs explicit format instruction | Add CRITICAL `<think>` format instruction to Player prompt | 35B models need explicit structural guidance | TRF-029 |
| 10 | Coach needs to validate think block presence | Coach prompt: check `<think>` before accepting | Quality gate for reasoning examples | TRF-027 |

### The Two-Layer Architecture (Established in Run 8)

```
┌────────────────────────────────────────────────────────┐
│ LAYER 1: Model's Own Chain-of-Thought                  │
│                                                        │
│ <think>                                                │
│ The user wants me to generate a training example for:  │
│ - Category: Character analysis                         │
│ - Type: reasoning                                      │
│ I need to include a <think> block in the assistant...  │
│ </think>                                               │
│                                                        │
│ ← Model reasoning about HOW to generate the example    │
│ ← NOT part of the training data                        │
│ ← Can be safely discarded                              │
└────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────┐
│ LAYER 2: Think Blocks INSIDE Training Example JSON     │
│                                                        │
│ {"messages": [...,                                     │
│   {"role": "assistant",                                │
│    "content": "<think>The student is asking about      │
│    Lady Macbeth's soliloquy. This relates to AO2...    │
│    </think>\n\nThat's a really interesting passage!"}  │
│ ], "metadata": {...}}                                  │
│                                                        │
│ ← Pedagogical content — the tutor's internal reasoning │
│ ← MUST be preserved in training data                   │
│ ← Protected by TRF-024 (disabled reasoning parser)     │
└────────────────────────────────────────────────────────┘
```

**The invariant**: Layer 2 think blocks MUST be preserved. Layer 1 is model scaffolding.

### What the current pipeline does with think blocks

1. **vLLM**: `--reasoning-parser` DISABLED (TRF-024). Both layers flow in `.content` as raw text
2. **`_extract_player_content()`**: Returns full content including Layer 1 + Layer 2 (PATH 1: string)
3. **Coach input**: Full `player_content` passed as `user` message — Layer 1 included
4. **On acceptance**: `normalise_think_closing_tags()` fixes malformed tags, then `_extract_example_json()` extracts the JSON (Layer 2 preserved within)
5. **`write_tool`**: Validates Layer 2 think block presence in reasoning examples

---

## Root Cause Analysis: What Actually Happened at Index 2

### The Player's output (4042 chars, `player_content_source: string`)

```
<think>                                          ← Layer 1 START
The user wants me to generate a training
example for:
- Category: Character analysis — An Inspector Calls
- Type: reasoning
- Count: 80

I need to create a ShareGPT conversation format
with:
1. System message (from the system prompt)
2. User message (student question)
3. Assistant message (with <think> block)
...
</think>                                         ← Layer 1 END

{                                                ← Layer 2 (JSON)
  "messages": [
    {"role": "system", "content": "You are..."},
    {"role": "user", "content": "I'm trying..."},
    {"role": "assistant", "content":
      "<think>The student is asking about the    ← Layer 2 think
       mysterious nature of Inspector Goole...
       </think>\n\nThat's a really interesting
       observation!..."}
  ],
  "metadata": {
    "layer": "behaviour",
    "type": "reasoning",
    ...
  }
}
```

### What the Coach received (as `user` message)

The ENTIRE 4042-char string above, including:
- Layer 1 model reasoning (starts with "The user wants me to generate...")
- The JSON training example (with Layer 2 think blocks inside strings)

### Why the Coach got confused

The Coach's `user` message starts with text that reads like a task instruction:
```
The user wants me to generate a training example for:
- Category: Character analysis — An Inspector Calls
- Type: reasoning
- Count: 80
```

Despite having a clear system prompt saying "you are an evaluator, return JSON", the Coach (Qwen3.5-35B at temp 0.3) **continued the pattern** from the input rather than following its system prompt. It generated its own version of Player reasoning.

### Why this is stochastic

- Index 0: Player content 3871 chars with Layer 1 thinking → Coach returned JSON verdict ✓
- Index 1: Player content with Layer 1 thinking → Coach returned JSON verdict (revise) ✓
- Index 2: Player content 4042 chars with Layer 1 thinking → Coach returned Player-like text ✗

The difference is stochastic model behaviour, not a deterministic bug.

---

## Revised Recommendations (History-Aware)

### R1: Add ValueError to per-target exception handler (P0 — MUST FIX)

**Impact**: Prevents pipeline crash; rejected targets are logged and skipped
**Risk**: None — purely additive exception handling
**Conflicts with previous work**: None

```python
# generation_loop.py line 1011
# BEFORE:
except (RuntimeError, OSError, ValidationError) as exc:

# AFTER:
except (RuntimeError, OSError, ValidationError, ValueError) as exc:
```

**This alone would have allowed run-9 to continue past index 2.** The remaining 17 targets would have been processed, and index 2 would have been recorded as rejected with reason `llm_failure: Failed to parse CoachVerdict...`.

### R2: WITHDRAWN — Do NOT strip Player's Layer 1 thinking before Coach

**Previous recommendation**: Extract just the JSON from `player_content` before passing to Coach.

**Why withdrawn**: After reviewing the history, this is a rabbit hole:
- TRF-024 disabled the reasoning parser specifically to let think blocks flow naturally
- Stripping Layer 1 requires reliably distinguishing it from Layer 2 (which is inside JSON strings)
- The `_extract_json_object()` function already handles this for acceptance — repurposing it for Coach input adds complexity
- If the Coach sometimes fails despite a clear system prompt, adding pre-processing won't eliminate the stochastic nature
- **With R1 applied, the pipeline already handles this correctly** — reject target, continue

### R3: DEFERRED — Coach verdict retry logic

**Previous recommendation**: Retry Coach with "you must return JSON" reminder.

**Why deferred**:
- With R1 applied, Coach parsing failures gracefully reject the target
- Retry logic adds complexity and doubles Coach token cost per failure
- At ~5% failure rate over 20 targets, we'd expect ~1 rejected target — acceptable
- If failure rate proves higher in production (1000 targets), revisit this

### R4: KEPT but P2 — Consider vLLM structured output for Coach

**If** the rejection rate from Coach role confusion exceeds 5% in production runs, investigate vLLM's `response_format={"type": "json_object"}` or guided decoding. But this requires testing with Qwen3.5-35B to ensure compatibility.

---

## Revised Decision

**One-line fix (R1) is sufficient for the overnight re-run.** The pipeline's existing architecture (per-target error handling, rejection logging, checkpoint/resume) already handles intermittent Coach failures — the bug was simply that `ValueError` wasn't in the exception list.

**Do NOT**:
- Strip think blocks from Player content before Coach (conflicts with TRF-024 philosophy; adds complexity for marginal gain)
- Add Coach retry logic (over-engineering for observed failure rate)
- Modify the Player or Coach prompts (they're working correctly)
- Change vLLM configuration (the reasoning parser is correctly disabled)

**DO**:
- Add `ValueError` to the except clause at [generation_loop.py:1011](entrypoint/generation_loop.py#L1011)
- Re-run overnight
- Monitor rejection rate in the output — if >5% targets are rejected due to Coach parsing, THEN consider R3/R4

---

## Appendix A: Pipeline Flow for Index 2 (Detailed)

```
22:10:10  target_start(index=2, "Character analysis — An Inspector Calls")
22:10:10  rag_prefetch: query="Character analysis — An Inspector Calls reasoning"
22:10:10  rag result: 2363 chars (5 chunks about Inspector Goole, drama conventions)
22:10:10  Loaded AGENTS.md memory
22:10:10  Player call → POST promaxgb10-41b1:8002/v1/chat/completions
22:13:38  Player response: 200 OK (4414 prompt + 896 completion = 5310 tokens)
22:13:38  player_content_source: string, len=4042
22:13:38  Coach call → POST promaxgb10-41b1:8002/v1/chat/completions
22:14:03  Coach response: 200 OK (3754 prompt + 896 completion = 4650 tokens)
22:14:03  coach_content_source: content (standard path)
22:14:03  _parse_coach_verdict() → ValueError (no JSON object found)
22:14:03  ValueError NOT caught by per-target handler
22:14:03  Lock released: output/.lock
22:14:03  Pipeline failed (logged twice — agent.py:229 with exc_info=True)
```

## Appendix B: Token Usage Summary

| Target | Agent | Prompt | Completion | Total | Result |
|--------|-------|--------|------------|-------|--------|
| 0 | Player | 4,342 | 933 | 5,275 | OK |
| 0 | Coach | 3,791 | 648 | 4,439 | Accept (5) |
| 1 | Player | 4,268 | 913 | 5,181 | OK |
| 1 | Coach | 3,834 | 648 | 4,482 | Revise |
| 1 | Player (t2) | — | — | — | OK |
| 1 | Coach (t2) | — | — | — | Accept (5) |
| 2 | Player | 4,414 | 896 | 5,310 | OK |
| 2 | Coach | 3,754 | 896 | 4,650 | **FAIL** (role confusion) |

## Appendix C: What the Coach's Response Actually Was

The Coach returned Player-like reasoning (first 200 chars from error log):
```
The user wants me to generate a training example for:
- Category: Character analysis — An Inspector Calls
- Type: reasoning
- Count: 80

I need to create a ShareGPT conversation format with:
1. System
```

This is the Coach **mimicking the Player's Layer 1 thinking pattern** that appeared at the start of the `user` message. The Coach generated 896 completion tokens of this content — a full Player-style response rather than a ~648 token JSON verdict.

## Appendix D: Files to Change

| File | Line | Change | Risk |
|------|------|--------|------|
| [generation_loop.py](entrypoint/generation_loop.py#L1011) | 1011 | Add `ValueError` to except tuple | None — additive |
