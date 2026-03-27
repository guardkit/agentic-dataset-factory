# Review Report: TASK-REV-TRF5

## Executive Summary

The fifth pipeline run with **Qwen3.5-35B-A3B-FP8** (262K context) processed **1 target** and **failed to complete**. Zero training examples were accepted or rejected. Two of three new fixes are verified working (TRF-009 RAG calls, TRF-010 token logging). The Coach verdict parser fix (TRF-008) is structurally correct but encountered a **new, distinct failure mode**: the Coach generated 578 completion tokens but the pipeline received an **empty string**.

**Root cause (F1)**: A three-layer toolchain gap. vLLM's `--reasoning-parser qwen3` splits the response into `reasoning_content` (think blocks) and `content` (visible text). When the Coach's entire output lands inside `<think>` tags, `content` is empty. LangChain's `ChatOpenAI` then discards `reasoning_content` because it's a non-standard field. The verdict JSON was generated correctly but lost in translation. **Disabling thinking is NOT recommended** — the Coach was deliberately given a reasoning model. Instead, we should extract from `reasoning_content` or fix the toolchain path.

**Root cause (F2)**: A critical **tool leakage regression** — all 8 DeepAgents platform tools are injected into both Player and Coach. The SDK's `create_deep_agent` unconditionally adds `FilesystemMiddleware` even when `backend=None` (it defaults to `StateBackend`). The Coach actively called `read_file` instead of evaluating, which may have contributed to F1 (the model entered a tool-use think loop rather than outputting JSON).

**Additional finding**: `langchain-skills` is installed but NOT used by this project at runtime — it is developer tooling only.

**Production readiness: NOT READY.** Two P0 blockers (F1 + F2) require fixes. Fixing F2 alone may resolve F1 indirectly.

---

## Review Details

- **Mode**: Decision Analysis
- **Depth**: Standard
- **Source**: `docs/reviews/second-run/qwen35-run-2.md`
- **Pipeline Duration**: ~71 seconds (15:11:04 – 15:12:15 UTC, 26 Mar 2026)
- **Model**: Qwen/Qwen3.5-35B-A3B-FP8, local vLLM on `promaxgb10-41b1:8002`

---

## Fix Verification (TASK-REV-TRF4)

| # | Fix | Task | Status | Evidence |
|---|-----|------|--------|----------|
| 1 | **F1 (Coach parser preamble) — robust 3-try extraction** | TASK-TRF-008 | PARTIALLY VERIFIED | Parser code is correct (3-try strategy works), but input was empty string — no JSON to extract. Error: `"no JSON object found in response. Raw content (first 200 chars): ''"`. Parser didn't crash — it correctly rejected empty input. |
| 2 | **F2 (missing rag_retrieval) — Player tool calls** | TASK-TRF-009 | VERIFIED | Player made **3 rag_retrieval calls** across 3 tool-use loop iterations before generating its example. First query: `"An Inspector Calls literary analysis character analysis AQA specification"` (n_results=10). Second query: `"AQA mark scheme grade descriptors character analysis AO1 AO2"` (n_results=8). RAG context was successfully incorporated. |
| 3 | **F3 (token usage logging) — vLLM response logging** | TASK-TRF-010 | VERIFIED | Token counts logged for both agents: Player (11,751 prompt / 782 completion = 12,533 total), Coach (8,610 prompt / 578 completion = 9,188 total). |

**Summary**: 2/3 new fixes verified working. TRF-008 parser is structurally correct but could not be fully tested because Coach content was empty (a different bug).

---

## Deferred Fix Verification (from TASK-REV-FRF3)

| # | Fix | Task | Status | Evidence |
|---|-----|------|--------|----------|
| 4 | **F7: `<think>` blocks** | TASK-TRF-001 | UNVERIFIED | Pipeline failed before any example was accepted/written. `<think>` references present in system prompts but no generated examples reached write stage. |
| 5 | **F8: grade_target coercion** | TASK-TRF-004 | VERIFIED | Player's generated example contains `"grade_target": 7` (integer). No coercion error encountered. |
| 6 | **F6: Retry cap** | TASK-TRF-006 | UNVERIFIED | No write attempts occurred. Config confirms `max_write_attempts: 3`. Code path not exercised. |

---

## New Findings

### F1 (CRITICAL): Coach response is empty string — reasoning/content split causes data loss

**Severity**: P0 — blocks all pipeline execution
**Component**: vLLM reasoning parser + LangChain ChatOpenAI + pipeline content extraction

**Problem**: The Coach LLM returned 578 completion tokens but the extracted message content is an empty string (`''`). The root cause is a **three-layer interaction** between vLLM, LangChain, and the pipeline:

1. **vLLM layer**: The `--reasoning-parser qwen3` flag splits the model's response into `reasoning_content` (the `<think>` block) and `content` (everything after `</think>`). When the Coach places its entire JSON verdict inside `<think>` tags (reasoning about the evaluation), `content` is empty and the verdict lands in `reasoning_content`.

2. **LangChain layer**: The pipeline uses `model_provider="openai"` (i.e., `ChatOpenAI`) for vLLM. Per the `langchain-openai` docs: *"Non-standard response fields added by third-party providers (e.g., `reasoning_content`) are NOT extracted or preserved."* So `reasoning_content` from vLLM is silently discarded — it never reaches the `AIMessage`.

3. **Pipeline layer**: `coach_response["messages"][-1].content` returns the empty `content` field. The 578 tokens of actual verdict JSON are lost.

**Evidence**:
- Coach: `prompt_tokens=8610, completion_tokens=578` — the model generated substantial output
- Parse error: `Raw content (first 200 chars): ''` — content string is empty
- vLLM script (`vllm-agentic-factory.sh:65`): `--reasoning-parser qwen3` is active
- Model factory (`agents/model_factory.py:29`): `"local": "openai"` — uses ChatOpenAI, not a vLLM-aware provider

**Why NOT just "disable thinking"**: The original architecture deliberately chose a reasoning model (Qwen3.5-35B-A3B) because the Coach needs to reason deeply about example quality. Disabling thinking entirely would degrade evaluation quality — the Coach would lose its chain-of-thought capability. This is counter to the architectural intent.

**Fix options** (revised, in order of preference):

1. **Extract reasoning_content in the pipeline** (recommended): After `coach_response["messages"][-1]`, check `message.additional_kwargs.get("reasoning_content")` or iterate `message.content` blocks for `type: "reasoning"`. If the text content is empty but reasoning content exists, parse the verdict from reasoning content. This preserves the Coach's thinking ability while correctly extracting the verdict.

2. **Use `.text` property + reasoning fallback**: LangChain-Core's `AIMessage.text` filters to `type: "text"` blocks only. But we need to ALSO check reasoning blocks as a fallback. Implement: try `.text` first, if empty try reasoning blocks.

3. **Switch to a vLLM-aware LangChain provider**: If one exists (e.g., a `ChatVLLM` class) that properly extracts `reasoning_content`, use it instead of `ChatOpenAI`. This would be the cleanest solution but may not exist.

4. **Separate vLLM endpoints** (architectural): Run a second vLLM instance for Coach WITHOUT `--reasoning-parser qwen3`. The Coach gets raw output including any `<think>` tags as inline text, which our existing `_extract_json_object()` 3-try parser can handle (it would find the `{...}` JSON inside or after the think block). Downside: doubles infrastructure.

5. **Per-request `enable_thinking: false`** (last resort): Pass `extra_body={"chat_template_kwargs": {"enable_thinking": false}}` for Coach calls only. This disables thinking at the model template level. Simple but sacrifices Coach reasoning quality.

### F2 (CRITICAL): Leaked platform tools — backend=None does NOT work

**Severity**: P0 — security/correctness violation, causes Coach to call `read_file` instead of evaluating
**Component**: `agents/player.py`, `agents/coach.py`, DeepAgents SDK `create_deep_agent`

**Problem**: Both Player and Coach have **all 8 DeepAgents platform tools** injected: `edit_file`, `glob`, `grep`, `ls`, `read_file`, `write_file`, `task`, `write_todos`.

**Root cause** (confirmed by SDK source inspection):

```python
# deepagents/graph.py line 186:
backend = backend if backend is not None else (StateBackend)
```

When we pass `backend=None`, the SDK checks `backend is not None` → `False` (because None IS None), and falls through to the default `StateBackend`. Then line 258 unconditionally adds `FilesystemMiddleware(backend=StateBackend)`, which injects all 8 filesystem tools.

**Our code** in `agents/player.py:60-66` and `agents/coach.py:74-80` both pass `backend=None`, believing this disables the filesystem. It does not.

**Impact observed in this run**:
- Player: Had 9 tools (8 platform + rag_retrieval) instead of 1 (rag_retrieval only)
- Coach: Had 8 tools (all platform) instead of 0
- Coach actively called `read_file('/evaluation_criteria.md')` on its first turn instead of evaluating the example — returned "File not found" error
- Coach then used its remaining budget to think (inside `<think>` tags) but never produced visible JSON output

**Fix options**:

1. **Use `middleware` parameter to override** (recommended): Build the middleware stack manually without `FilesystemMiddleware`. Pass `middleware=[...]` with only the middleware we want.

2. **Patch after creation**: Remove filesystem tools from the agent's tool list after `create_deep_agent` returns.

3. **Upstream fix**: Open an issue/PR on DeepAgents to support a sentinel value like `backend=False` to disable filesystem middleware entirely.

### F3 (MEDIUM): Player makes 3 rag_retrieval calls instead of 1

**Severity**: P1 — performance concern
**Component**: Player tool-use loop / orchestrator pre-fetch interaction

**Problem**: The Player made 3 rag_retrieval calls across 3 tool-use loop iterations (4 LLM round-trips total before generating its example). The orchestrator already pre-fetches RAG context (TASK-TRF-009 `rag_tool` reference), so the Player should need at most 0-1 additional calls.

**Impact**: Extra token usage and latency. 3 additional LLM round-trips × ~12K tokens each.

**Fix options**:
1. **Clarify in Player prompt** that curriculum context is pre-fetched and one additional retrieval is the maximum
2. **Set `tool_choice: "none"` after first Player turn** to prevent further tool calls
3. **Accept as-is** — the additional retrievals may improve example quality

### F4 (LOW): Player example may be truncated

**Severity**: P2 — quality concern
**Component**: Orchestrator example extraction

**Problem**: The Coach's input contained only the tail end of the Player's generated training example (~951 chars): the assistant response text and metadata, but missing the system message and user message from the JSON `messages` array.

**Possible causes**:
- Player generated incomplete JSON
- Orchestrator's extraction function truncated the JSON
- Context window message truncation

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
| Player LLM calls | 4 (3 tool-use loops + 1 generation) |
| Coach LLM calls | 2 (1 read_file tool call + 1 empty response) |
| Total HTTP requests | ~6 |
| Player prompt tokens | 11,751 |
| Player completion tokens | 782 |
| Coach prompt tokens | 8,610 |
| Coach completion tokens | 578 |
| **Total tokens** | **21,721** |
| Pipeline duration | ~71 seconds |
| Peak context utilisation | 11,751 / 262,144 = 4.5% |

---

## Coach Verdict Analysis

No verdicts were successfully parsed. The Coach:
1. First turn: Called leaked `read_file('/evaluation_criteria.md')` tool → file not found
2. Second turn: Generated 578 tokens but content was empty (think-mode stripping)

---

## Tool Visibility Audit

| Agent | Expected Tools | Actual Tools | Status |
|-------|---------------|--------------|--------|
| Player | `[rag_retrieval]` | `[rag_retrieval, edit_file, glob, grep, ls, read_file, write_file, task, write_todos]` | **FAIL** — 8 extra tools |
| Coach | `[]` (empty) | `[edit_file, glob, grep, ls, read_file, write_file, task, write_todos]` | **FAIL** — 8 leaked tools |
| Orchestrator | `write_output` | `write_output` | PASS |

**Root cause**: `backend=None` in `create_deep_agent` does NOT disable filesystem tools. SDK always injects them via `FilesystemMiddleware`.

---

## Model Quality Assessment (Preliminary)

| Criterion | Assessment |
|-----------|------------|
| Tool calling reliability | GOOD — Player reliably called rag_retrieval (3 times, correct args) |
| RAG retrieval quality | GOOD — Queries were topically relevant and well-formed |
| Example quality | PARTIAL — Socratic approach observed, AO alignment present, but example may be truncated |
| Metadata correctness | PARTIAL — `grade_target=7` (valid integer), `layer=behaviour`, `type=reasoning`, `text=an_inspector_calls` all valid |
| `<think>` block quality | NOT TESTED — no examples reached write stage |
| Coach evaluation quality | NOT TESTED — Coach called leaked tools and then produced empty content |
| Network reliability | EXCELLENT — all API calls returned 200 OK |
| Context window utilisation | 4.5% — well within limits |

---

## Recommendations

| # | Priority | Action | Effort | Task |
|---|----------|--------|--------|------|
| 1 | P0 | **Fix Coach reasoning content extraction** — extract verdict from `reasoning_content`/`additional_kwargs` when `.content` is empty, preserving Coach's thinking capability | Small (2-3h) | NEW |
| 2 | P0 | **Fix tool leakage** — bypass `create_deep_agent` for Coach (use `langchain.agents.create_agent` directly without `FilesystemMiddleware`), or build custom middleware stack | Medium (2-4h) | NEW |
| 3 | P1 | **Cap Player tool-use loops** — limit to 1-2 rag_retrieval calls per turn | Small (1h) | NEW |
| 4 | P2 | **Investigate example truncation** — verify orchestrator passes complete JSON to Coach | Small (1h) | NEW |
| 5 | P0 | **Restore langchain-skills** — were active during exemplar build but lost on 2026-03-17. Restore from `~/.claude.backup.20260317_101318/skills/` before next implementation cycle (see Appendix E) | Trivial (5m) | NEW |
| 6 | P1 | **Reconsider TASK-TRF-003** — the Player's original `FilesystemBackend` was intentional (exemplar design). Reverting Player to `FilesystemBackend` and focusing Coach fix on bypassing `create_deep_agent` may be the correct approach | Medium (2-3h) | NEW |

---

## Decision Matrix

| Option | Risk | Effort | Recommendation |
|--------|------|--------|----------------|
| Fix F1 (reasoning extraction) + F2 (tool leakage), re-run | Low | 4-7h | **Recommended** — addresses both P0 blockers while preserving Coach reasoning |
| Fix F2 (tool leakage) only, re-run | Low | 2-4h | Good first step — tool leakage may be causing the Coach to think/call tools instead of outputting JSON directly. Fixing tools alone might resolve F1 indirectly |
| Fix F1 via `enable_thinking: false`, re-run | Medium | 1h | Quick unblock but degrades Coach evaluation quality — counter to architectural intent |
| Separate vLLM endpoints (Coach without reasoning parser) | Low | 2h | Clean separation but doubles infrastructure. Our 3-try JSON parser would handle inline `<think>` tags |
| Switch Coach to Anthropic API | Low | 1h | Bypasses all local model issues but adds cost and doesn't validate local pipeline |

---

## Decisions Required

1. **Production readiness** — **NOT READY**. Two P0 blockers must be resolved.
2. **Model confirmation** — Qwen3.5-35B-A3B-FP8 shows promise (reliable tool calling, good RAG queries, reasonable example structure). The empty-content issue is NOT a model deficiency — it's a toolchain integration gap between vLLM's reasoning parser, LangChain's ChatOpenAI, and DeepAgents' middleware.
3. **F1 fix strategy** — Do we (a) extract reasoning_content in the pipeline (preserves thinking), (b) disable thinking for Coach only (`enable_thinking: false`), or (c) separate vLLM endpoints? Note: fixing F2 (tool leakage) alone may resolve F1 indirectly — if the Coach has no leaked tools, it may not enter a tool-calling think loop and instead output JSON directly.
4. **F2 fix strategy** — Do we (a) bypass `create_deep_agent` for Coach and use `langchain.agents.create_agent` directly with a custom middleware stack, or (b) accept the leaked tools and strip them post-creation?
5. **langchain-skills** — Were installed for the exemplar build but lost on 2026-03-17 when `~/.claude/` was restructured. Restore from backup (`~/.claude.backup.20260317_101318/skills/`) or re-install. The AutoBuild that created this repo ran without skills loaded.
6. **Reconsider TASK-TRF-003** — The "fix" that changed Player from `FilesystemBackend` to `backend=None` may have been wrong. The original exemplar design intentionally gave the Player filesystem access. The real problem is the Coach getting tools — focus the fix there.

---

## Appendix

### A. Token Usage Summary

| Agent | Prompt Tokens | Completion Tokens | Total |
|-------|--------------|-------------------|-------|
| Player | 11,751 | 782 | 12,533 |
| Coach | 8,610 | 578 | 9,188 |
| **Total** | **20,361** | **1,360** | **21,721** |

### B. Tool Leakage Root Cause — SDK Source

```python
# deepagents/graph.py:186
backend = backend if backend is not None else (StateBackend)

# deepagents/graph.py:258 — ALWAYS adds FilesystemMiddleware
deepagent_middleware.extend([
    FilesystemMiddleware(backend=backend),   # <-- injected regardless of backend=None
    SubAgentMiddleware(backend=backend, subagents=all_subagents),
    ...
])
```

Passing `backend=None` triggers `backend is not None` → `False` → default `StateBackend` is used. The `FilesystemMiddleware` is unconditionally added at line 258 for the main agent and line 191 for subagents.

### C. Previous Review Chain

| Review | Run | Key Findings | Fixes | Status |
|--------|-----|-------------|-------|--------|
| TASK-REV-E2A7 | Run 1 | ChromaDB path + array validation | TASK-FRF-001, TASK-FRF-002 | Fixed |
| TASK-REV-FRF2 | Run 2 | tool_calls.args deserialization + model args | Model switch + qwen3_coder parser | Fixed |
| TASK-REV-FRF3 | Run 3 | Context window + tool leakage + Coach bypass + type coercion | TASK-TRF-001 through TASK-TRF-007 | Fixed |
| TASK-REV-TRF4 | Run 4 | Coach verdict parser preamble + no RAG + no logging | TASK-TRF-008 through TASK-TRF-010 | Fixed |
| **TASK-REV-TRF5** | **Run 5** | **Empty Coach content (think-mode) + tool leakage regression + excessive tool calls** | **TBD** |

### D. Verified Fix Status (Cumulative)

| Fix | Task | First Seen | Status After Run 5 |
|-----|------|-----------|-------------------|
| ChromaDB path | TASK-FRF-001 | Run 1 | Verified (Run 2+) |
| Array validation | TASK-FRF-002 | Run 1 | Verified (Run 2+) |
| Context window 262K | TASK-TRF-001 | Run 3 | Verified (Run 4+) |
| Tool leakage backend=None | TASK-TRF-003 | Run 3 | **REGRESSION** — backend=None doesn't work |
| grade_target str() coercion | TASK-TRF-004 | Run 3 | Verified (Run 5) |
| Coach bypass → orchestrator writes | TASK-TRF-005 | Run 3 | Verified (Run 4+) |
| Retry cap max_write_attempts=3 | TASK-TRF-006 | Run 3 | Unverified (code path not exercised) |
| `<think>` block handling | TASK-TRF-001 | Run 3 | Unverified (no examples written) |
| Coach verdict parser preamble | TASK-TRF-008 | Run 4 | Partially verified (parser correct, input empty) |
| Player rag_retrieval calls | TASK-TRF-009 | Run 4 | **Verified** |
| Token usage logging | TASK-TRF-010 | Run 4 | **Verified** |

### E. langchain-skills Assessment — Installed Once, Then Lost

**Corrected finding**: langchain-skills **were** successfully installed before the project was created. The user ran `npx skills add langchain-ai/langchain-skills --skill '*' --yes --global` and the skills were active during the exemplar build phase. However, they were **lost on 2026-03-17** when `~/.claude/` was restructured — a backup at `~/.claude.backup.20260317_101318/skills/` contains all 11 skills.

**Timeline**:
1. **2026-03-16**: Skills installed. Exemplar repo (`deepagents-player-coach-exemplar`) built using skills + DeepAgents examples from `langchain-ai/deepagents/examples/` (deep_research + content-builder-agent). GuardKit `/template-create` generated the `langchain-deepagents` template with 7 specialist agent docs.
2. **2026-03-17**: `~/.claude/` directory was restructured/rebuilt. Skills lost. Backup created at `~/.claude.backup.20260317_101318/skills/`.
3. **2026-03-20**: `agentic-dataset-factory` created from template. AutoBuild ran dozens of tasks (TASK-AF-*, TASK-EP-*, etc.) — **without skills loaded**. Skills were no longer in `~/.claude/skills/`.
4. **2026-03-20+**: Five pipeline runs with progressively discovered bugs.

**What the original build got right (with skills active)**:

The exemplar and template were well-designed. The 7 specialist agent docs in `.claude/agents/` (not `.claude/rules/guidance/` — those are stubs pointing to the full docs) contain detailed, correct guidance:
- `deepagents-factory-specialist.md` (517 lines): Correctly specifies `backend=FilesystemBackend(root_dir=".")` for Player, "omit `backend=` entirely" for Coach, `tools=[]` for Coach
- `adversarial-cooperation-architect.md`: Correctly specifies role separation, tool access asymmetry, orchestrator-gated writes

**What went wrong during AutoBuild (without skills)**:

The initial AutoBuild (commit `2ba8674`) correctly implemented the Player with `FilesystemBackend(root_dir=".")` and the Coach with `backend=None` — closely following the guidance. However:

1. The Coach's `backend=None` was already a bug (guidance said "omit `backend=`", meaning don't pass the parameter at all — but even omitting it wouldn't help because the SDK defaults to StateBackend regardless). **Neither the skills nor the guidance document this SDK trap.**

2. When TASK-TRF-003 (Run 3 fix) changed the Player from `FilesystemBackend` to `backend=None` to "remove filesystem tools", it made the problem worse — now both agents had leaked tools. **This fix was designed without skills loaded**, relying on the incorrect assumption that `backend=None` disables FilesystemMiddleware.

**The real gap**: Neither the langchain-skills NOR the project's own specialist agent docs document:
- That `backend=None` defaults to `StateBackend` (SDK bug/undocumented behavior)
- That `FilesystemMiddleware` is unconditionally added regardless of backend value
- How to create an agent with zero filesystem tools

The skills say *"Agents cannot remove core middleware or rename built-in tools"* (`deep-agents-core`) and *"FilesystemMiddleware automatically included in `create_deep_agent()`"* (`deep-agents-orchestration`) — which are accurate but don't suggest a workaround. The original architecture (Player with `FilesystemBackend`, Coach without) was the correct pattern given the SDK's constraints, but the Coach still got tools injected.

**Recommendation**:
1. **Restore skills immediately**: `cp -r ~/.claude.backup.20260317_101318/skills ~/.claude/skills` (or re-run install with `PATH="/opt/homebrew/bin:$PATH" npx skills add langchain-ai/langchain-skills --skill '*' --yes --global`)
2. **Accept that skills alone don't solve the tool leakage**: The `create_deep_agent` API has no supported way to suppress FilesystemMiddleware. The fix requires either bypassing `create_deep_agent` for the Coach, or using `langchain.agents.create_agent` directly with a custom middleware stack.
3. **Consider whether the original Player design was actually correct**: The exemplar intentionally gave the Player `FilesystemBackend` + filesystem tools. The TASK-TRF-003 "fix" that removed it may have been wrong — the original design expected the Player to have filesystem access (for RAG file operations), and the Coach's leaked tools were the real problem.

### F. Reasoning Content Flow — Why Coach Content Is Empty

```
Qwen3.5-35B (vLLM)
  └─ Model generates: <think>JSON verdict here</think>
  └─ --reasoning-parser qwen3 splits response:
       reasoning_content: "JSON verdict here"   ← 578 tokens
       content: ""                               ← empty
  └─ Returns OpenAI-compatible response with both fields

LangChain ChatOpenAI
  └─ Reads response.choices[0].message.content → ""
  └─ IGNORES response.choices[0].message.reasoning_content
     (documented limitation: "Non-standard response fields are NOT extracted")
  └─ Creates AIMessage(content="")

Pipeline (generation_loop.py:479)
  └─ coach_content = coach_response["messages"][-1].content → ""
  └─ _parse_coach_verdict("") → ValueError: "no JSON object found"
```

**Key insight**: The model DID generate a valid verdict (578 tokens). It was lost in the ChatOpenAI → AIMessage translation because `reasoning_content` is a vLLM-specific extension not part of the OpenAI spec.

### G. vLLM Script Configuration

From `guardkit/scripts/vllm-agentic-factory.sh`:
- Model: `Qwen/Qwen3.5-35B-A3B-FP8`
- Port: 8002
- Context: 262,144 tokens
- Flags: `--reasoning-parser qwen3 --enable-auto-tool-choice --tool-call-parser qwen3_coder --enable-prefix-caching`
- The `--reasoning-parser qwen3` flag is the trigger for the content/reasoning split
