# Review Report: TASK-REV-TRF12

## Executive Summary

Analysis of 11 runs and 31 fixes across the agentic-dataset-factory pipeline reveals that **~84% of fixes (26/31) could have been prevented by better template scaffolding**. The remaining 5 required runtime discovery (model-specific behaviour, SDK limitations, infrastructure decisions). The fixes cluster into 6 root cause categories, with **validation/schema gaps** (9 fixes) and **prompt engineering** (7 fixes) dominating. Five high-impact template improvements would prevent the majority of future iteration cycles.

**Review Details**
- **Mode**: Architectural + Decision (hybrid)
- **Depth**: Comprehensive
- **Scope**: 11 runs (TASK-REV-E2A7 through TASK-REV-TRF11), 31 fixes (TRF-001 through TRF-031)

---

## 1. Bug Taxonomy — Complete Classification

### 1.1 SDK/Framework Misunderstanding (6 fixes)

| Fix | Issue | Could Template Prevent? |
|-----|-------|------------------------|
| TRF-003 | `backend=None` doesn't disable FilesystemMiddleware — SDK defaults to StateBackend | Yes — document middleware injection |
| TRF-011 | langchain-skills lost during ~/.claude restructure | No — infrastructure issue |
| TRF-012 | `create_deep_agent()` unconditionally adds FilesystemMiddleware (Coach bypass) | No — SDK limitation, requires bypass |
| TRF-016 | Tool leakage: Player used leaked `write_file` instead of returning content | Yes — factory must allowlist tools |
| TRF-024 | vLLM `--reasoning-parser qwen3` strips think blocks from Player output | Partial — document parser side effects |
| FRF-001 | ChromaDB path mismatch (hardcoded `./chroma` vs `./chroma_data`) | Yes — parameterise persist_directory |

**Pattern**: The DeepAgents SDK's `create_deep_agent()` function has undocumented side effects (middleware injection, backend defaulting) that caused 3 separate fix cycles. This is the single most expensive root cause.

### 1.2 Prompt Engineering (7 fixes)

| Fix | Issue | Could Template Prevent? |
|-----|-------|------------------------|
| TRF-008 | Coach outputs preamble text before JSON verdict | Yes — robust extraction pattern |
| TRF-009 | Player doesn't call rag_retrieval autonomously | Yes — orchestrator-side pre-fetch |
| TRF-014 | Player makes 3+ rag_retrieval calls per target | Yes — explicit call limits in prompt |
| TRF-027 | Coach accepts examples missing required think blocks | Yes — explicit quality gates |
| TRF-029 | Player lacks concrete think block format example | Yes — show-don't-tell prompt pattern |
| TRF-031 | Output format instruction buried mid-prompt, too polite | Yes — CRITICAL section at prompt end |
| FRF-002* | Model misstructures write_output arguments | Yes — clearer tool schema |

**Pattern**: Prompts lacked (a) concrete format examples, (b) imperative language for critical constraints, and (c) recency-bias positioning (end of prompt). All 7 are template-preventable.

### 1.3 Validation/Schema Gaps (9 fixes)

| Fix | Issue | Could Template Prevent? |
|-----|-------|------------------------|
| TRF-004 | `grade_target` integer vs string type mismatch at validation boundary | Yes — auto-coerce at boundaries |
| TRF-019 | Think block closing tag malformed (`<think>` instead of `</think>`) | Yes — model output normalization |
| TRF-021 | Think block EOF pattern (no closing tag at all) | Yes — comprehensive edge cases |
| TRF-022 | No explicit `max_tokens` set on Player model | Yes — required config fields |
| TRF-025 | Naive brace counting breaks on `{` inside JSON string values | Yes — string-aware parsing |
| TRF-028 | Range notation `1+` treated as enum value | Yes — domain schema type system |
| TRF-030 | Literal newlines in JSON strings break `json.loads()` | Yes — JSON repair pre-processing |
| FRF-002 | Array metadata field uses scalar `in` operator | Yes — type-aware validation |
| TRF-015 | Player `.content` is block-list not string (provider-dependent) | Yes — format-agnostic extraction |

**Pattern**: The validation pipeline was built incrementally, discovering edge cases one at a time. A defensive-by-default extraction and validation template would have caught all 9.

### 1.4 Orchestration Logic (4 fixes)

| Fix | Issue | Could Template Prevent? |
|-----|-------|------------------------|
| TRF-005 | Player writes output before Coach evaluation (bypasses adversarial gate) | Yes — orchestrator-gated writes |
| TRF-006 | Uncontrolled retry loop burns context tokens | Yes — retry cap with defaults |
| TRF-013 | Coach reasoning_content discarded by LangChain ChatOpenAI | Yes — fallback extraction chain |
| TRF-020 | Think block normalization called after extraction (wrong order) | Yes — canonical pipeline order |

**Pattern**: The orchestration pipeline lacked a canonical processing order (normalize -> extract -> validate -> write) and standard resilience patterns (retry caps, fallback chains).

### 1.5 Model-Specific Quirks (3 fixes)

| Fix | Issue | Could Template Prevent? |
|-----|-------|------------------------|
| TRF-001 | Nemotron 3 Nano 4B too small for reasoning tasks | Partial — model selection guide |
| TRF-002 | Qwen3.5 config values (temperature, endpoint) | Yes — config validation |
| TRF-026 | Player reasoning_content fallback (defense-in-depth) | Yes — symmetric extraction |

**Pattern**: Model selection required empirical testing. Template can document known-good combinations but cannot fully prevent model-specific issues.

### 1.6 Test Coverage / Observability Gaps (2 fixes)

| Fix | Issue | Could Template Prevent? |
|-----|-------|------------------------|
| TRF-010 | No token usage logging | Yes — observability template |
| TRF-023 | Error logging shows only first 200 chars, no tail | Yes — structured logging |
| TRF-017 | Tests invalid after factory pattern change | Yes — contract-based tests |
| TRF-018 | Token logging not in generation loop | Yes — logging scaffold |

**Pattern**: Observability was added reactively. A "what to log" checklist would have caught all of these.

---

## 2. Root Cause Distribution

```
Validation/Schema Gaps    ████████████████████  9 fixes (29%)
Prompt Engineering         ██████████████       7 fixes (23%)
SDK/Framework              ████████████         6 fixes (19%)
Orchestration Logic        ████████             4 fixes (13%)
Model-Specific Quirks      ██████               3 fixes (10%)
Test/Observability         ██████               2 fixes  (6%)
                                               ──────────────
                                               31 fixes (100%)
```

---

## 3. Template Improvements — Concrete Recommendations

### 3.1 Robust JSON Extraction Pipeline (prevents 9 fixes)

**What to build**: A `JsonExtractor` class shipped with the template that implements:
1. Direct `json.loads()` attempt
2. Code-fence stripping + retry
3. String-aware brace-matching extraction
4. JSON string repair (literal newlines, unescaped chars)
5. `reasoning_content` fallback for vLLM providers

**Prevents**: TRF-008, TRF-015, TRF-019, TRF-020, TRF-021, TRF-025, TRF-030, TRF-013, TRF-026

**Effort**: 2-3 days (extraction code already exists in this project, needs packaging)

### 3.2 Orchestrator-Gated Writes Pattern (prevents 4 fixes)

**What to build**: Template enforces that:
- Player NEVER has write tools in its tool list
- Coach NEVER has filesystem tools
- Orchestrator calls write programmatically after Coach acceptance
- Retry cap (default 3) on all I/O operations

**Prevents**: TRF-005, TRF-006, TRF-003, TRF-016

**Effort**: 1-2 days (pattern already implemented, needs codification)

### 3.3 Prompt Engineering Template (prevents 7 fixes)

**What to build**: Standard prompt sections generated by template:
- `## CRITICAL — Response Format` (end of prompt, imperative language, negative examples)
- `## Tool Usage` (explicit call limits, pre-fetch documentation)
- `## Quality Gates` (concrete accept/reject criteria with examples)
- `## Output Structure` (show-don't-tell with full JSON example)

**Prevents**: TRF-008, TRF-009, TRF-014, TRF-027, TRF-029, TRF-031, FRF-002

**Effort**: 1 day (prompt patterns already proven, needs templatisation)

### 3.4 Type-Aware Domain Validator (prevents 4 fixes)

**What to build**: Validation framework that:
- Inspects metadata field types (array vs scalar, int vs string)
- Auto-coerces at model-output boundaries
- Supports range notation (`1+`, `0-10`) alongside enumerations
- Validates against domain schema, not string matching

**Prevents**: TRF-004, TRF-028, FRF-002 (array), TRF-022

**Effort**: 2 days (validator exists, needs type system)

### 3.5 Agent Factory with Tool Allowlisting (prevents 4 fixes)

**What to build**: Factory functions that:
- Explicitly declare which tools each agent receives (allowlist, not blocklist)
- Bypass `create_deep_agent()` for agents that must not have filesystem access
- Document middleware injection behaviour per API variant
- Include assertion: `assert set(agent.tools) == expected_tools`

**Prevents**: TRF-003, TRF-012, TRF-016, TRF-017

**Effort**: 1 day (bypass pattern already implemented)

### 3.6 Observability Scaffold (prevents 4 fixes)

**What to build**: Standard logging template including:
- Token usage per API call and cumulative per target
- Content length at each pipeline stage (extraction, validation, write)
- Error context: first + last 200 chars + total length
- Pipeline stage timing

**Prevents**: TRF-010, TRF-018, TRF-023, TRF-015 (partial)

**Effort**: 0.5 days (logging code exists, needs template extraction)

### 3.7 Model Compatibility Matrix (prevents 3 fixes)

**What to build**: Documentation template including:
- Tested model/parser combinations with known issues
- BFCL and reasoning benchmark requirements
- vLLM configuration flags and their side effects
- Known parser quirks (hermes double-serialization, qwen3 think-stripping)

**Prevents**: TRF-001, TRF-002, TRF-024

**Effort**: 0.5 days (knowledge exists, needs documentation)

---

## 4. Top 5 Highest-Impact Improvements

Ranked by (fixes prevented x frequency of occurrence in future projects):

| Rank | Improvement | Fixes Prevented | Effort | ROI |
|------|-------------|----------------|--------|-----|
| **1** | Robust JSON Extraction Pipeline | 9 | 2-3 days | Very High |
| **2** | Prompt Engineering Template | 7 | 1 day | Very High |
| **3** | Orchestrator-Gated Writes Pattern | 4 | 1-2 days | High |
| **4** | Agent Factory with Tool Allowlisting | 4 | 1 day | High |
| **5** | Type-Aware Domain Validator | 4 | 2 days | Medium-High |

**Combined**: These 5 improvements would prevent **26 of 31 fixes (84%)**.

The remaining 5 fixes (TRF-001, TRF-002, TRF-011, TRF-012, TRF-024) required:
- Empirical model selection (no template can substitute for testing)
- SDK limitation workarounds (requires upstream fix or documented bypass)
- Infrastructure recovery (one-off incident)

---

## 5. First-Run Success Checklist

A pre-launch checklist that catches the top issues before running:

### Agent Wiring
- [ ] Player tool list contains ONLY intended tools (no leaked filesystem tools)
- [ ] Coach has NO filesystem/write tools
- [ ] Player does NOT have write_output in its tool list
- [ ] Orchestrator owns the write_output call (post-Coach-acceptance)
- [ ] Factory uses `create_agent()` not `create_deep_agent()` for tool-restricted agents
- [ ] `assert set(agent.tools) == expected_tools` passes for both agents

### Prompt Quality
- [ ] Player prompt ends with `## CRITICAL — Response Format` section
- [ ] Response format uses imperative language ("MUST", "NEVER")
- [ ] At least one concrete JSON output example in Player prompt
- [ ] Tool usage limits are explicit ("call rag_retrieval at most once")
- [ ] Coach prompt includes explicit accept/reject criteria with examples
- [ ] Coach prompt includes quality gates for domain-specific requirements

### JSON Extraction
- [ ] Extraction pipeline order: normalize -> extract -> validate -> write
- [ ] Extractor handles: direct parse, code-fence, brace-matching (3-try)
- [ ] Brace matcher is string-aware (tracks quoted context)
- [ ] JSON repair handles literal newlines in string values
- [ ] Both Player and Coach have symmetric content extraction (string + block-list + reasoning_content)

### Validation
- [ ] Metadata validation coerces types at model-output boundary
- [ ] Array fields validated with `set(field) <= set(valid)`, not `field in valid`
- [ ] Range notation (`1+`, `0-10`) recognised, not treated as enum
- [ ] `max_tokens` explicitly set for all model configs

### Observability
- [ ] Token usage logged per API call (prompt, completion, total)
- [ ] Error logging includes first + last 200 chars + total length
- [ ] Pipeline stage timing logged
- [ ] Retry counter visible in logs

### Model Configuration
- [ ] Model/parser combination tested with tool-calling benchmark
- [ ] vLLM flags reviewed for side effects (especially `--reasoning-parser`)
- [ ] Temperature, max_tokens, context window documented in config
- [ ] Known model quirks documented (think block format, JSON escaping)

---

## 6. Iteration Timeline

| Run | Fixes Applied | Category | Cumulative |
|-----|--------------|----------|------------|
| 1 | FRF-001, FRF-002 | SDK, Validation | 2 |
| 2 | (model switch) | Model quirk | 2 |
| 3 | TRF-001 to TRF-006 | Mixed (6 fixes) | 8 |
| 4 | TRF-007* to TRF-010 | Prompt, Observability | 12 |
| 5 | TRF-011 to TRF-015 | SDK, Orchestration | 17 |
| 6 | (blocking: tool leakage) | SDK | 17 |
| 7 | TRF-016 to TRF-019 | SDK, Validation | 21 |
| 8 | TRF-020 to TRF-023 | Orchestration, Validation | 25 |
| 9 | TRF-024 to TRF-027 | SDK, Prompt | 29 |
| 10 | TRF-028 to TRF-030 | Validation, Prompt | 31 |
| 11 | TRF-031 | Prompt (final) | 31 |

**Key Observation**: Validation and prompt fixes dominated runs 7-11, while SDK/framework issues dominated runs 1-6. This suggests the "hard" problems (SDK behaviour) were found first, while "soft" problems (prompt engineering, validation edge cases) required iterative refinement.

---

## 7. Decisions Required

### Decision 1: Template Scope

**Options**:
- **A**: Improve the general DeepAgents template (benefits all agent projects)
- **B**: Create a separate "adversarial-cooperation" template (focused, opinionated)
- **C**: Both — core improvements in DeepAgents template, adversarial-specific patterns in specialised template

**Recommendation**: **C** — The JSON extraction pipeline, observability scaffold, and factory patterns benefit all agents. The orchestrator-gated writes pattern and Coach prompt template are adversarial-cooperation-specific.

### Decision 2: Priority

**Options**:
- **A**: Implement all 5 top improvements before next agent project
- **B**: Implement top 3 (extraction + prompts + gated writes), defer rest
- **C**: Implement top 2 (extraction + prompts), defer rest

**Recommendation**: **B** — Top 3 cover 20/31 fixes (65%) in 4-5 days. Factory allowlisting and validators can follow.

### Decision 3: Automation

**Options**:
- **A**: Template includes automated pre-flight validation (runs checklist programmatically)
- **B**: Template includes manual checklist only
- **C**: Template includes both, with pre-flight as optional `--validate` flag

**Recommendation**: **C** — Automated checks for wiring (tool lists, factory patterns), manual review for prompts and model config.

### Decision 4: Documentation

**Options**:
- **A**: Embed known issues in template comments/docstrings
- **B**: Separate "Known Issues & Quirks" guide per model family
- **C**: Both — critical warnings in code, comprehensive guide as reference

**Recommendation**: **C** — Critical SDK pitfalls (create_deep_agent middleware injection) must be inline where developers encounter them.

---

## 8. Template Change Recommendations with Effort Estimates

| # | Change | Effort | Priority | Prevents |
|---|--------|--------|----------|----------|
| 1 | Package `JsonExtractor` class from generation_loop.py | 2-3 days | P0 | 9 fixes |
| 2 | Prompt template with CRITICAL section pattern | 1 day | P0 | 7 fixes |
| 3 | Orchestrator-gated writes scaffold | 1-2 days | P0 | 4 fixes |
| 4 | Factory tool allowlisting pattern | 1 day | P1 | 4 fixes |
| 5 | Type-aware domain validator | 2 days | P1 | 4 fixes |
| 6 | Observability logging scaffold | 0.5 days | P1 | 4 fixes |
| 7 | Model compatibility matrix doc | 0.5 days | P2 | 3 fixes |
| 8 | Pre-flight validation script | 1 day | P2 | N/A (catch-all) |
| **Total** | | **~10 days** | | **31/31** |

**Minimum viable improvement** (P0 only): ~5 days, prevents 20/31 fixes (65%)
**Full improvement** (P0 + P1): ~7.5 days, prevents 28/31 fixes (90%)

---

## Appendix A: Fix-to-Category Mapping (Complete)

| Fix ID | Title | Category | Template Preventable |
|--------|-------|----------|---------------------|
| FRF-001 | ChromaDB path mismatch | SDK/Framework | Yes |
| FRF-002 | Array metadata validation | Validation/Schema | Yes |
| TRF-001 | vLLM launch script for Qwen3.5 | Model-Specific | Partial |
| TRF-002 | Agent config for Qwen3.5 | Model-Specific | Yes |
| TRF-003 | Remove FilesystemBackend (backend=None) | SDK/Framework | Yes |
| TRF-004 | grade_target type coercion | Validation/Schema | Yes |
| TRF-005 | Move write_output to orchestrator | Orchestration | Yes |
| TRF-006 | Write retry cap | Orchestration | Yes |
| TRF-008 | Coach parser preamble handling | Prompt Engineering | Yes |
| TRF-009 | Orchestrator-side RAG pre-fetch | Prompt Engineering | Yes |
| TRF-010 | Token usage logging | Observability | Yes |
| TRF-011 | Restore langchain-skills | SDK/Framework | No |
| TRF-012 | Coach bypass create_deep_agent | SDK/Framework | No |
| TRF-013 | Coach reasoning_content extraction | Orchestration | Yes |
| TRF-014 | Cap rag_retrieval calls | Prompt Engineering | Yes |
| TRF-015 | Player content block-list handling | Validation/Schema | Yes |
| TRF-016 | Player tool leakage (create_agent bypass) | SDK/Framework | Yes |
| TRF-017 | Update player factory tests | Observability | Yes |
| TRF-018 | Token logging in generation loop | Observability | Yes |
| TRF-019 | Think block closing tag normalization | Validation/Schema | Yes |
| TRF-020 | Normalize before extraction (pipeline order) | Orchestration | Yes |
| TRF-021 | EOF think block pattern | Validation/Schema | Yes |
| TRF-022 | Explicit max_tokens | Validation/Schema | Yes |
| TRF-023 | Improved extraction failure logging | Observability | Yes |
| TRF-024 | Remove reasoning parser from vLLM | SDK/Framework | Partial |
| TRF-025 | JSON-string-aware brace matching | Validation/Schema | Yes |
| TRF-026 | Player reasoning_content fallback | Validation/Schema | Yes |
| TRF-027 | Coach think block verification prompt | Prompt Engineering | Yes |
| TRF-028 | Range notation parser | Validation/Schema | Yes |
| TRF-029 | Player think block format example | Prompt Engineering | Yes |
| TRF-030 | JSON string repair pre-processing | Validation/Schema | Yes |
| TRF-031 | CRITICAL response format instruction | Prompt Engineering | Yes |

**Summary**: 26 Yes, 2 Partial, 3 No = **~84% template-preventable**
