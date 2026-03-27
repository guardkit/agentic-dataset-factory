# Review Report: TASK-REV-TRF7

## Executive Summary

**Run 7 (qwen35-run-4)** represents a **major architectural breakthrough** with **critical serialisation bugs** blocking acceptance. The Player-Coach orchestration is now working correctly end-to-end for the first time: Player has exactly 1 tool, Coach has 0 tools, the pipeline completes all 3 turns, and Coach produces meaningful verdicts. However, **0 out of 1 targets were accepted** due to two blocking issues: (1) unclosed `<think>` tags breaking JSON extraction, and (2) `normalise_think_closing_tags` not being called in the generation loop before JSON extraction.

**Production readiness: NO** -- 2-3 code fixes required before overnight run.

## Review Details

- **Mode**: Architectural / Code-Quality Review
- **Depth**: Standard
- **Source Document**: `docs/reviews/second-run/qwen35-run-4.md`
- **Run Date**: 2026-03-27
- **Model**: Qwen3.5-35B-A3B-FP8 on vLLM (promaxgb10-41b1:8002)
- **Targets**: 1 configured, 1 attempted, 0 accepted, 1 rejected

---

## Fix Verification (TASK-REV-TRF6 Findings)

### F1: Player Tool Leakage (TASK-TRF-016) -- PASS

**Evidence**: `Creating Player agent (tools=['rag_retrieval'])`

Player has exactly 1 tool (`rag_retrieval`). The 8 leaked DeepAgents platform tools (`write_todos`, `ls`, `read_file`, `write_file`, `edit_file`, `glob`, `grep`, `task`) are gone. The `create_agent()` bypass of `create_deep_agent` is working as designed.

### F2: Player Content Return (TASK-TRF-016) -- PASS

Player returns training examples as response content (not via `write_file` to `/tmp/`). Coach receives the content and evaluates it. No `/tmp/` file writes observed in the log.

### F3: Player System Prompt Size (TASK-TRF-016) -- PASS

System prompt is dramatically smaller. Token usage shows Player turn 1 at 4,616 prompt_tokens (vs estimated ~43K+ previously with DeepAgents boilerplate + 8 tool schemas). This is an ~89% reduction.

### F4: Coach 0 Tools Runtime (TASK-TRF-012) -- PASS

**Evidence**: `Creating Coach agent (no tools)`

Coach HTTP requests contain no `tools` field at runtime. This was previously untested (Coach was never invoked in Run 6). Now confirmed working.

### F5: Coach Reasoning Extraction (TASK-TRF-013) -- PARTIAL PASS

Coach verdicts ARE parsed correctly -- `decision=accept, score=5` (turns 1-2) and `decision=revise, score=2` (turn 3). However, the **training example JSON** extracted from Player content fails to parse. The CoachVerdict itself parses fine; the issue is with `_extract_example_json`, not `_parse_coach_verdict`.

### F6: Player Tool-Use Cap (TASK-TRF-014) -- PASS

Player makes 0 `rag_retrieval` tool calls after prefetch. RAG context is pre-fetched (1 call, 1929 chars) and reused across turns.

### F7: Example Truncation (TASK-TRF-015) -- FAIL

JSON extraction fails on the Player's training example JSON. Error messages show:
- Turn 1: Raw content starts `'\n\n{\n  "messages": [...]'` -- valid JSON start
- Turn 2: Raw content starts `'\n\n```json\n{\n  "messages": [...]'` -- code-fenced JSON

Both fail `_extract_json_object()` despite the 3-try strategy. Root cause analysis below.

---

## Token/Logging Verification (TASK-TRF-018)

### Token Usage Logging -- PASS

Per-turn and aggregate token stats are now logged:

| Agent | Turn | Prompt Tokens | Completion Tokens | Total |
|-------|------|---------------|-------------------|-------|
| Player | 1 | 4,616 | 940 | 5,556 |
| Coach | 1 | 3,473 | 809 | 4,282 |
| Player | 2 | 4,012 | 957 | 4,969 |
| Coach | 2 | 3,549 | 948 | 4,497 |
| Player | 3 | 4,012 | 899 | 4,911 |
| Coach | 3 | 3,002 | 903 | 3,905 |
| **Total** | | **22,664** | **5,456** | **28,120** |

### Token Budget -- PASS

Peak prompt_tokens (single call): **4,616** (Player turn 1)
Budget utilisation: 22,664 / 262,000 = **8.6%** -- excellent headroom.

### Prompt Size Reduction -- PASS

Player prompt reduced from estimated ~43K+ tokens (with DeepAgents boilerplate + 8 tool schemas) to ~4.6K tokens. This is consistent with a clean system prompt containing only the domain instructions and single tool schema.

---

## Think Block Verification (TASK-TRF-019)

### Think Block Closure -- FAIL (CRITICAL)

Pattern analysis of the full run log:

| Pattern | Count |
|---------|-------|
| `<think>` opens | 33 |
| `</think>` proper closes | 2 |
| `<think>...<think>` malformed closes | 16 |
| `<think>...` with NO closing tag | 15 |

**Status**: 94% of think blocks are unclosed. Two distinct failure modes:
1. **Malformed close** (16 cases): Model uses `<think>` as both open and close tag. The existing `normalise_think_closing_tags()` regex handles this pattern.
2. **Missing close** (15 cases): Model opens `<think>` and never closes it. The normaliser does NOT handle this pattern -- it only matches `<think>...<think>`.

### Think Block Content Quality -- PASS

The reasoning content is pedagogically sound (AO analysis, student knowledge assessment, Socratic question planning). The content quality is high; only the XML structure is broken.

---

## Root Cause Analysis: JSON Extraction Failure

This is the **primary blocking issue**. Three contributing factors:

### Cause 1: `normalise_think_closing_tags` Not Called in Generation Loop

**Location**: [generation_loop.py:644-645](entrypoint/generation_loop.py#L644-L645)

The generation loop calls `_extract_example_json(player_content)` directly after Coach acceptance, but **never calls `normalise_think_closing_tags()`** on the player content first. The normaliser is only called in [write_output.py:140](src/tools/write_output.py#L140), which runs AFTER JSON extraction succeeds -- a chicken-and-egg problem.

The Player's training example JSON contains assistant messages with `<think>` blocks. When those blocks have malformed/missing close tags, the JSON content string contains unbalanced characters that may confuse the brace-matching parser.

### Cause 2: Normaliser Doesn't Handle Missing Close Tags

**Location**: [validator.py:192-210](synthesis/validator.py#L192-L210)

`normalise_think_closing_tags()` handles `<think>...<think>` (malformed close) but NOT `<think>...EOF` (missing close entirely). With 15 instances of the latter pattern, the normaliser alone won't fix all cases. A new pattern is needed: if `<think>` appears with no closing tag of any kind, append `</think>` at the end of the content.

### Cause 3: Possible Completion Truncation

Player completion_tokens are 940, 957, 899 per turn. A full training example JSON with system prompt, user question, and assistant response containing a `<think>` block may exceed ~900 tokens. No explicit `max_tokens` is set on the Player model ([model_factory.py:75](agents/model_factory.py#L75)), so vLLM uses its server-side default. If that default is ~1024, responses may be truncated mid-JSON.

**Evidence**: HTTP response content-lengths are small (1670-4311 bytes) and JSON extraction error messages only show the first 200 chars, making it impossible to determine if full content was received.

---

## Pipeline Performance

| Metric | Value |
|--------|-------|
| Targets configured | 1 |
| Targets attempted | 1 |
| Accepted | **0** |
| Rejected | **1** |
| Total turns | 3 (max_turns=3) |
| Wall time | 171.5 seconds |
| Tokens consumed | 28,120 |

### Turn Sequence

| Turn | Coach Decision | Score | Outcome |
|------|---------------|-------|---------|
| 1 | accept | 5 | JSON extraction failed |
| 2 | accept | 5 | JSON extraction failed |
| 3 | revise | 2 | Pipeline terminates (max_turns) |

Coach accepted the example twice (score 5/5) but JSON extraction failure on both turns prevented the write step. On turn 3, the Coach requested revision (possibly because the re-prompt feedback about JSON format confused the Player), and the pipeline terminated at max_turns.

---

## Model Quality Assessment

### Tool Calling Reliability -- EXCELLENT

Player makes 0 erroneous tool calls. No leaked tools used. RAG prefetch cap (0-1 calls) respected.

### Example Quality -- HIGH

Coach evaluates favourably (score 5 on turns 1-2). System prompt correctly focuses on GCSE English tutoring (An Inspector Calls, AO2 analysis, Year 10, Grade 7 target). Socratic method is followed.

### Coach Evaluation Quality -- GOOD

Coach produces structured verdicts with clear accept/revise decisions and numerical scores. Verdicts are extracted correctly. Full feedback content is lost due to the JSON extraction issue affecting the example, not the verdict.

---

## Comparison: Run 6 vs Run 7

| Aspect | Run 6 (TASK-REV-TRF6) | Run 7 (This Review) |
|--------|----------------------|---------------------|
| Player tools | 9 (8 leaked + 1 correct) | 1 (correct) |
| Coach tools | 8 (leaked) | 0 (correct) |
| Pipeline completion | CRASH (empty content) | Success (3 turns) |
| Coach invoked | Never | Every turn |
| Coach verdicts | None | 3 verdicts (2 accept, 1 revise) |
| Examples accepted | 0 | 0 |
| Root cause | Tool leakage (architectural) | JSON serialisation (code-level) |
| Token budget | Unknown | 8.6% used |

**Key insight**: Run 6 failed at the architectural level (wrong tools). Run 7 has correct architecture but fails at the serialisation level. This is a qualitatively different (and much more fixable) class of issue.

---

## Findings Summary

| # | Finding | Severity | Status |
|---|---------|----------|--------|
| F1 | Player tool leakage fixed | -- | PASS |
| F2 | Player content return fixed | -- | PASS |
| F3 | System prompt reduced ~89% | -- | PASS |
| F4 | Coach 0 tools confirmed | -- | PASS |
| F5 | Coach verdict parsing works | -- | PASS |
| F6 | Player tool-use cap works | -- | PASS |
| F7 | JSON extraction fails | CRITICAL | FAIL |
| F8 | Token logging comprehensive | -- | PASS |
| F9 | Token budget excellent (8.6%) | -- | PASS |
| F10 | Think blocks 94% unclosed | CRITICAL | FAIL |
| F11 | Normaliser not called in gen loop | HIGH | FAIL |
| F12 | Normaliser misses EOF pattern | HIGH | FAIL |
| F13 | No max_tokens on Player model | MEDIUM | INVESTIGATE |

**Score: 9/13 checks passing (69%)**
**Blocking issues: 4 (F7, F10, F11, F12)**

---

## Recommendations

### R1: Call `normalise_think_closing_tags` Before JSON Extraction (CRITICAL)

**Location**: `entrypoint/generation_loop.py` around line 644

Add normalisation of player content before attempting JSON extraction. The think block normaliser must run on the raw Player content so that the JSON inside (which contains assistant messages with think blocks) has properly closed tags.

**Implementation sketch**:
```python
from synthesis.validator import normalise_think_closing_tags

# Before extraction:
player_content = normalise_think_closing_tags(player_content)
example_json = _extract_example_json(player_content)
```

**Note**: This needs careful handling -- `player_content` is the entire Player response containing a JSON object. The think blocks are INSIDE JSON string values. The normaliser should be applied to the raw content string, and the brace-matching parser should then handle the rest.

### R2: Handle Missing Close Tags in Normaliser (CRITICAL)

**Location**: `synthesis/validator.py` around line 192

Extend `normalise_think_closing_tags()` to handle the case where `<think>` appears with no closing tag at all (not even a malformed `<think>` as close):

```python
def normalise_think_closing_tags(content: str) -> str:
    if "</think>" in content.lower():
        return content
    # Existing: fix <think>...<think> pairs
    result = _MALFORMED_CLOSE_RE.sub(r"\1</think>", content)
    # NEW: if still no </think>, append one after the last <think> block
    if "<think>" in result.lower() and "</think>" not in result.lower():
        # Find last <think> and close it at end of content
        result = re.sub(r'(<think>)((?:(?!<think>).)*?)$', r'\1\2</think>', result, flags=re.DOTALL | re.IGNORECASE)
    return result
```

### R3: Set Explicit `max_tokens` on Player Model (MEDIUM)

**Location**: `agents/model_factory.py` or `entrypoint/generation_loop.py`

Set `max_tokens=4096` (or higher) explicitly on the Player model to prevent silent truncation by the vLLM server default. With the 262K context window and only 8.6% utilisation, there's ample budget.

### R4: Add Full Response Logging for Extraction Failures (MEDIUM)

**Location**: `entrypoint/generation_loop.py` around line 655

Log more than 200 chars when JSON extraction fails:

```python
logger.warning(
    "JSON extraction failed after Coach acceptance: %s\n"
    "Full content length: %d chars\nLast 200 chars: %s",
    exc, len(player_content), player_content[-200:]
)
```

### R5: Verify HTTP Response Completeness (LOW)

Add Content-Length validation or `finish_reason` logging for vLLM responses to confirm no silent truncation at the HTTP level.

---

## Decisions Required

| # | Decision | Recommendation |
|---|----------|---------------|
| 1 | **Production readiness** | **NO** -- Fix R1+R2 first (estimated 1-2 hours), then re-run |
| 2 | **Model confirmation** | **YES** -- Qwen3.5-35B demonstrates excellent tool calling, example quality, and Coach evaluation |
| 3 | **Architecture confirmation** | **YES** -- Player-Coach orchestration is working correctly end-to-end |
| 4 | **Config tuning** | Set explicit `max_tokens=4096` on Player; consider `max_turns=5` |
| 5 | **Blocking issues** | R1 and R2 block overnight run; R3-R5 are recommended but not blocking |

---

## Implementation Priority

| Priority | Task | Effort | Impact |
|----------|------|--------|--------|
| 1 (BLOCKING) | R1: Call normaliser in gen loop | 15 min | Fixes 16/33 malformed think blocks |
| 2 (BLOCKING) | R2: Handle EOF pattern in normaliser | 30 min | Fixes remaining 15/33 unclosed blocks |
| 3 (HIGH) | R3: Set explicit max_tokens | 10 min | Prevents potential truncation |
| 4 (MEDIUM) | R4: Improve failure logging | 15 min | Enables faster diagnosis |
| 5 (LOW) | R5: HTTP completeness check | 30 min | Defence in depth |

**Estimated total to unblock**: ~1 hour for R1+R2+R3
