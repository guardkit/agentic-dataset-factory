# Review Report: TASK-REV-TRF6

## Executive Summary

**Run 6 (qwen35-run03) is a complete pipeline failure.** The Player wrote its training example to `/tmp/training_example.json` via the leaked `write_file` tool instead of returning content in its response. The pipeline crashed with empty content, producing 0 accepted and 0 rejected examples. The Coach was never invoked.

**Root cause**: `agents/player.py` calls `create_deep_agent()` which unconditionally injects `FilesystemMiddleware`, adding 8 DeepAgents platform tools. TASK-TRF-012 fixed the Coach by switching to the lower-level `create_agent()` API, but the Player was deliberately left on `create_deep_agent` under the assumption that filesystem tools were "unused but harmless." That assumption was wrong — Qwen3.5-35B used the leaked `write_file` tool. Note: the `langchain-skills` package (Claude Code skills) has been reinstalled but does not affect the Python runtime pipeline — this is a code-level issue in the Player factory.

**Decision: NOT ready for overnight run.** Critical tool leakage must be resolved first.

## Review Details

- **Mode**: Architectural / Decision Review
- **Depth**: Standard
- **Source**: `docs/reviews/second-run/qwen35-run03.md` (56 lines, ~26K tokens)
- **Model**: Qwen3.5-35B-A3B-FP8 (local vLLM)
- **Run date**: Based on HTTP timestamps ~09:30-09:31 GMT

---

## Fix Verification (TASK-TRF-011 through TASK-TRF-015)

### F1: Coach Tool Leakage (TASK-TRF-012) — PARTIALLY VERIFIED

**Evidence**: Log line 13:
```
"Creating Coach agent (no tools): provider=local, model=Qwen/Qwen3.5-35B-A3B-FP8, memory=['./AGENTS.md']"
```

The Coach creation message says "no tools", which is correct. **However, the Coach was never invoked** (pipeline crashed before reaching Coach evaluation), so we cannot confirm the HTTP request would have had an empty `tools` array at runtime.

**Verdict**: Creation-time fix appears correct. Runtime verification still pending.

### F2: Coach Reasoning Content Extraction (TASK-TRF-013) — NOT TESTABLE

The Coach was never called. No verdict was produced. Cannot verify `<think>` tag fallback extraction or CoachVerdict JSON parsing.

**Verdict**: Untested.

### F3: Player FilesystemBackend Revert (TASK-TRF-012) — FAILED

**Evidence**: The Player's HTTP request contains a `tools` array with **9 tools**:

1. `write_todos` — DeepAgents platform tool (LEAKED)
2. `ls` — DeepAgents platform tool (LEAKED)
3. `read_file` — DeepAgents platform tool (LEAKED)
4. `write_file` — DeepAgents platform tool (LEAKED)
5. `edit_file` — DeepAgents platform tool (LEAKED)
6. `glob` — DeepAgents platform tool (LEAKED)
7. `grep` — DeepAgents platform tool (LEAKED)
8. `task` — DeepAgents platform tool (LEAKED)
9. `rag_retrieval` — Intended tool (CORRECT)

The Player is **NOT** using `FilesystemBackend`. The DeepAgents middleware is injecting its full platform tool set. The `write_output` tool (which FilesystemBackend would provide) is absent.

**Verdict**: FAILED. This is the root cause of the pipeline crash.

### F4: Player Tool-Use Cap (TASK-TRF-014) — NOT TESTABLE

The Player made **0 `rag_retrieval` calls**. Instead, it called `write_file` on its first turn, writing the training example to `/tmp/training_example.json`. On its second turn, it returned empty string content, crashing the pipeline.

**Verdict**: Moot — the model misuses leaked tools before `rag_retrieval` cap is relevant.

### F5: Example Truncation Before Coach (TASK-TRF-015) — NOT TESTABLE

Coach was never invoked. Cannot verify completeness of training example JSON passed to Coach.

**Verdict**: Untested.

---

## Deferred Fix Verification

### F7: `<think>` Blocks (TASK-TRF-001) — PARTIALLY VERIFIED

**Evidence**: The training example written via `write_file` contains a `<think>` block:

```
<think>
This is a literary analysis question about dramatic technique...
Key considerations:
- This is AO2 (analysis of writer's methods) and AO4 (connections across the text)
- For a Grade 7 response, they need developed analysis with some context
- The Socratic approach means I shouldn't just tell them what the Inspector represents
- I need to guide them to notice specific techniques Priestley uses
- Common misconceptions: students often just say "the Inspector represents socialism" without evidence
```

The reasoning content is **meaningful and pedagogically sound**. However, the closing tag appears malformed (`<think>` instead of `</think>`).

**Verdict**: Model can produce `<think>` blocks with genuine reasoning. Malformed closing tag may be a parsing/logging artefact — needs verification.

### F6: Retry Cap (TASK-TRF-006) — NOT TESTABLE

No write failures occurred. The pipeline failed on content extraction, not file writing. Retry cap was never triggered.

**Verdict**: Untested.

---

## Pipeline Performance

| Metric | Value |
|--------|-------|
| Targets configured | 1 |
| Targets attempted | 1 |
| Accepted | 0 |
| Rejected | 0 |
| Pipeline result | **CRASH** |
| Wall time | ~51 seconds (09:30:35 → 09:31:26 GMT) |
| Tokens/second | Not logged |
| Token usage | Not logged |

### Failure Sequence

1. **Target 0 starts**: `"target_start: index=0, total=1, category=Literary analysis (single-turn), type=reasoning"`
2. **RAG prefetch succeeds**: `"rag_prefetch: index=0, query='Literary analysis (single-turn) reasoning', result_len=1929"`
3. **Player turn 1**: Model calls `write_file` tool (not `rag_retrieval`), writing training example JSON to `/tmp/training_example.json`
4. **Player turn 2**: Model returns empty content (`repr(content)=''`)
5. **Pipeline crash**: `"Pipeline failed: Player response has no extractable content: content type=<class 'str'>, repr(content)=''"`

### Token Budget Assessment

No `prompt_tokens` or `completion_tokens` usage stats are logged. The Player's system prompt is **massively inflated** (~43K characters) due to DeepAgents boilerplate including `write_todos` instructions, filesystem tool descriptions, task tool descriptions, and memory guidelines. Estimated prompt: 15,000-18,000 tokens — well under 262K limit but far larger than necessary.

Coach prompt tokens cannot be assessed (Coach never invoked).

---

## Model Quality Assessment

### Tool Calling Reliability

Qwen3.5-35B **reliably called a tool** but **called the wrong tool**. It used `write_file` with correct JSON arguments instead of returning content in its response or calling `rag_retrieval`. This is a tooling design problem (leaked tools make `write_file` look like a reasonable choice), not a model capability issue.

### Example Quality (from `write_file` arguments)

The training example produced is **high quality**:
- Correct ShareGPT format (system/user/assistant messages)
- Appropriate *An Inspector Calls* content for GCSE
- Socratic questioning approach demonstrated
- Student question is natural and age-appropriate
- Tutor response guides rather than giving direct answers
- `<think>` block contains genuine pedagogical reasoning

### Metadata Correctness

| Field | Value | Valid? |
|-------|-------|--------|
| `ao` | `["AO2", "AO4"]` | Yes — appropriate for dramatic device analysis |
| `text` | `"an_inspector_calls"` | Yes |
| `topic` | `"character_analysis"` | Marginal — "structure_analysis" may be more precise for dramatic device |
| `grade_target` | `7` | Yes |
| `source` | `"synthetic"` | Yes |
| `turns` | `1` | Yes |
| `layer` | `"behaviour"` | Yes |
| `type` | `"reasoning"` | Yes |

### Coach Evaluation Quality

Not testable — Coach was never invoked.

---

## New Issues Identified

### CRITICAL: Player Tool Leakage Persists (Blocks Everything)

**Severity**: Critical (pipeline non-functional)
**Impact**: Player writes output via leaked `write_file` instead of returning content
**Root cause**: `agents/player.py` lines 65-71 call `create_deep_agent()` which unconditionally injects `FilesystemMiddleware` (via `deepagents/graph.py` line 258). This adds 8 platform tools to the Player regardless of what tools are passed. TASK-TRF-012 fixed the Coach by switching to `create_agent()` but deliberately left the Player on `create_deep_agent` — that was a design error.

**Note**: The `langchain-skills` reinstallation (Claude Code skills) does not affect this. The tool leakage is a Python runtime issue in the agent factory code.

**Fix**: Apply the same pattern to the Player that TASK-TRF-012 applied to the Coach:
1. Replace `create_deep_agent` → `create_agent` in `agents/player.py`
2. Curate middleware: `MemoryMiddleware` + `PatchToolCallsMiddleware` (NO `FilesystemMiddleware`)
3. Pass `tools=[rag_retrieval]` explicitly
4. Update `tests/test_player_factory.py` to match new pattern

### MINOR: Duplicate Error Logging

The pipeline failure message appears twice in the log (lines 55-56). Minor — likely a duplicate handler issue.

### MINOR: `<think>` Closing Tag

The `<think>` block closing tag may be malformed. Needs verification whether this is a logging artefact or actual model output.

---

## Fix Verification Summary

| Fix | Task | Status | Evidence |
|-----|------|--------|----------|
| F1: Coach 0 tools | TASK-TRF-012 | Partial | Creation log correct; runtime untested |
| F2: Coach reasoning extraction | TASK-TRF-013 | Untested | Coach never invoked |
| F3: Player FilesystemBackend | TASK-TRF-012 | **FAILED** | 8 leaked platform tools present |
| F4: Player tool-use cap | TASK-TRF-014 | Untested | Model used write_file, not rag_retrieval |
| F5: Example truncation | TASK-TRF-015 | Untested | Coach never invoked |
| F6: Retry cap | TASK-TRF-006 | Untested | No write failures occurred |
| F7: `<think>` blocks | TASK-TRF-001 | Partial | Quality good; closing tag may be malformed |

---

## Recommendations

### R1: Fix Player Tool Leakage (CRITICAL — Blocks Pipeline)

The Player must have only `rag_retrieval` — not the 8 DeepAgents platform tools. Apply the same pattern TASK-TRF-012 applied to the Coach:

| Step | File | Change |
|------|------|--------|
| 1. Switch API | `agents/player.py` L65-71 | `create_deep_agent()` → `create_agent()` |
| 2. Curate middleware | `agents/player.py` | Add `MemoryMiddleware` + `PatchToolCallsMiddleware`, exclude `FilesystemMiddleware` |
| 3. Explicit tools | `agents/player.py` | Pass `tools=[rag_retrieval]` only |
| 4. Update tests | `tests/test_player_factory.py` | Mirror `tests/test_coach_factory.py` pattern |

This is a proven pattern (Coach has been running correctly with it since TASK-TRF-012).

### R2: Add Token Usage Logging

No `prompt_tokens` / `completion_tokens` data is logged. This makes it impossible to assess token budget utilisation. Add usage stats extraction from vLLM responses.

### R3: Verify `<think>` Closing Tag

Confirm whether the malformed closing tag is a logging artefact or actual model output. If model output, add a post-processing step to fix `<think>` → `</think>` for closing tags.

### R4: Fix Duplicate Error Logging

Minor — deduplicate the pipeline failure log message.

---

## Decisions Required

| # | Decision | Recommendation |
|---|----------|----------------|
| 1 | Production readiness | **NO** — pipeline non-functional due to Player tool leakage |
| 2 | Model confirmation | Qwen3.5-35B shows strong capability (good examples, good metadata, meaningful reasoning) but cannot be fully assessed until pipeline works |
| 3 | Configuration tuning | Cannot assess until pipeline completes at least one target end-to-end |
| 4 | Outstanding blockers | R1 (Player tool leakage) is the sole blocker. R2-R4 are improvements |
