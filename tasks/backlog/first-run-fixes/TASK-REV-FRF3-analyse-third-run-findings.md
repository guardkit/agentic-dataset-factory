---
id: TASK-REV-FRF3
title: Analyse third run findings (Nemotron 3 Nano 4B)
status: review_complete
created: 2026-03-26T00:00:00Z
updated: 2026-03-26T00:00:00Z
priority: critical
tags: [review, first-run, nemotron, third-run, context-window]
complexity: 5
task_type: review
decision_required: true
parent_review: TASK-REV-FRF2
depends_on: [TASK-FRF-004]
review_results:
  mode: decision
  depth: standard
  score: 25
  findings_count: 9
  recommendations_count: 7
  decision: implement
  report_path: .claude/reviews/TASK-REV-FRF3-review-report.md
  completed_at: 2026-03-26T00:00:00Z
test_results:
  status: pending
  coverage: null
  last_run: null
---

# Task: Analyse Third Run Findings (Nemotron 3 Nano 4B)

## Description

Analyse the third end-to-end run log at `docs/reviews/first-run/vllm-nemotron3-nano-1.md` captured after switching from Qwen2.5-14B to Nemotron 3 Nano 4B with `--tool-call-parser qwen3_coder`.

The model switch was implemented to resolve three issues from TASK-REV-FRF2:
- **F3**: vLLM/LangChain `tool_calls.args` deserialization crash (Qwen2.5 + hermes parser)
- **F4**: Model misstructuring `write_output` arguments (split into separate fields)
- **F5**: Player bypassing Coach evaluation

## Source Document

`docs/reviews/first-run/vllm-nemotron3-nano-1.md`

## Preliminary Observations

### Fixed Issues (from TASK-REV-FRF2)

- **F3 FIXED**: No `tool_calls.args` dict_type crash — `qwen3_coder` parser returns args as dict correctly
- **F4 FIXED**: Model sends single `example_json` string with both messages and metadata (correct structure)

### New Issues Identified

1. **Context window exhaustion**: Pipeline crashed with `maximum context length is 16384 tokens, request has 16413 input tokens` after 10 API calls. The accumulated conversation history (system prompt + tool definitions + 9 round-trips) exceeded 16K.

2. **Nemotron 3 Nano 4B cannot produce `<think>` blocks**: The `write_output` validation requires `<think>...</think>` tags when `metadata.type == "reasoning"`. The 4B model doesn't understand this format — all 7 `write_output` calls rejected.

3. **`grade_target` type mismatch bug**: `_coerce_valid_values` in `domain_config/parser.py:86-94` returns all values as `list[str]` (e.g., `["4", "5", "6", "7"]`). Model sends integer `7` in JSON. Comparison `7 not in ["4", "5", ...]` always fails. This is a code bug, not model-specific.

4. **DeepAgents backend tools leak into Player**: Player has 10 tools (including `ls`, `read_file`, `write_file`, `edit_file`, `glob`, `grep`, `task`, `write_todos`) instead of just 2 (`rag_retrieval`, `write_output`). Wastes context tokens and model used `read_file` inappropriately.

5. **No retry limit on write_output failures**: Player retried `write_output` 7 times in a loop with no cap, burning context tokens.

6. **Player still bypasses Coach**: Player calls `write_output` directly — Coach was never reached (same architectural issue as Run 2).

7. **RAG chunk source metadata blank**: All chunks show `source: unknown, p.?` — ingestion metadata not populated.

## Key Questions to Analyse

1. **Is 4B too small?** — Should we switch to Nano 30B-A3B (MoE, 3.2B active, ~15GB) for `<think>` block capability?
2. **How to fix context exhaustion?** — Increase `max_model_len`? Truncate conversation history? Reduce tool definitions?
3. **What's the right fix for `grade_target` type coercion?** — Coerce in parser, in write_output validation, or both?
4. **How to limit DeepAgents backend tool leakage?** — Can `create_deep_agent` be configured to exclude backend tools?
5. **Should we add a write_output retry cap?** — What's the right limit before giving up on a target?

## Acceptance Criteria

- [ ] Confirm which TASK-REV-FRF2 issues are resolved by the model switch
- [ ] Root cause identified for context window exhaustion (budget breakdown)
- [ ] Decision on model size: stay with 4B or upgrade to 30B-A3B
- [ ] Decision on `grade_target` type coercion fix approach
- [ ] Decision on DeepAgents tool leakage mitigation
- [ ] Implementation tasks created for all accepted findings

## Decisions Required

1. **Model size** — Nano 4B (with workarounds) vs Nano 30B-A3B (larger, more capable)
2. **Context budget** — Increase `max_model_len` to 32K/64K, or implement conversation truncation
3. **`grade_target` fix** — Parser-side type coercion vs validation-side string casting
4. **Tool leakage** — Configure DeepAgents, filter tool list, or accept overhead
5. **Retry cap** — Maximum write_output retries per target before rejection

## Context

This is the third iteration of the review cycle: TASK-REV-E2A7 (first run) → TASK-REV-FRF2 (second run) → TASK-REV-FRF3 (this review). Each review has progressively unblocked the pipeline further:
- Run 1: ChromaDB path + array validation bugs
- Run 2: tool_calls.args deserialization + model arg structure
- Run 3: Context window + model capability + type coercion + tool leakage

## Implementation Tasks Created

Implementation tasks created at `tasks/backlog/third-run-fixes/`:

| ID | Task | Wave | Priority |
|----|------|------|----------|
| TASK-TRF-001 | Update vLLM script for Qwen3.5-35B-A3B-FP8 | 1 | P0 |
| TASK-TRF-002 | Update agent-config.yaml | 1 | P0 |
| TASK-TRF-003 | Remove FilesystemBackend from Player | 1 | P0 |
| TASK-TRF-004 | Fix grade_target type coercion | 1 | P0 |
| TASK-TRF-005 | Orchestrator-gated writes (Coach bypass fix) | 2 | P1 |
| TASK-TRF-006 | Add write_output retry cap | 2 | P1 |
| TASK-TRF-007 | Fourth end-to-end run (validation) | 3 | P1 |

See `tasks/backlog/third-run-fixes/IMPLEMENTATION-GUIDE.md` for execution strategy.

## Implementation Notes

This is a review/analysis task. Review completed, implementation tasks created above.

## Test Execution Log

[Automatically populated by /task-work]
