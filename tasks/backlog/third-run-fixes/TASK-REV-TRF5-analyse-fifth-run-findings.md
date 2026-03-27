---
id: TASK-REV-TRF5
title: Analyse fifth run findings (Qwen3.5-35B-A3B-FP8, post-TRF-008-010)
status: completed
created: 2026-03-26T00:00:00Z
updated: 2026-03-26T00:00:00Z
priority: critical
tags: [review, fifth-run, qwen35, post-fix-validation]
complexity: 5
task_type: review
decision_required: true
parent_review: TASK-REV-TRF4
depends_on: [TASK-TRF-008, TASK-TRF-009, TASK-TRF-010]
review_results:
  mode: decision
  depth: standard
  findings_count: 4
  recommendations_count: 6
  decision: implement
  report_path: .claude/reviews/TASK-REV-TRF5-review-report.md
  implementation_tasks: [TASK-TRF-011, TASK-TRF-012, TASK-TRF-013, TASK-TRF-014, TASK-TRF-015]
  implementation_guide: tasks/backlog/fifth-run-fixes/IMPLEMENTATION-GUIDE-TRF5.md
  completed_at: 2026-03-26T16:00:00Z
test_results:
  status: pending
  coverage: null
  last_run: null
---

# Task: Analyse Fifth Run Findings (Qwen3.5-35B-A3B-FP8, Post-TRF-008-010)

## Description

Analyse the fifth end-to-end run log at `docs/reviews/second-run/qwen35-run-2.md` captured after implementing all fixes from TASK-REV-TRF4:

- **TASK-TRF-008**: Fixed Coach verdict parser to handle preamble text before JSON (robust 3-try extraction)
- **TASK-TRF-009**: Investigated and fixed missing rag_retrieval tool calls from Player
- **TASK-TRF-010**: Added token usage logging from vLLM API responses

This is the second run with Qwen3.5-35B-A3B-FP8 and the first run where the Coach verdict parser should correctly handle the model's natural output format.

## Source Document

`docs/reviews/second-run/qwen35-run-2.md`

## Key Questions to Analyse

### Fix Verification (from TASK-REV-TRF4)

1. **F1 (Coach parser preamble) — TASK-TRF-008**: Does the Coach verdict now parse correctly even when preceded by explanatory text? Are verdicts being extracted from markdown code fences?
2. **F2 (missing rag_retrieval) — TASK-TRF-009**: Does the Player now call rag_retrieval? Is RAG context present in the generation?
3. **F3 (token usage logging) — TASK-TRF-010**: Are token counts (prompt_tokens, completion_tokens, total_tokens) logged for each LLM call?

### Deferred Fix Verification (from TASK-REV-FRF3, unverified in Run 4)

4. **F7 (`<think>` blocks) — TASK-TRF-001**: Does Qwen3.5-35B produce valid `<think>...</think>` blocks for reasoning-type examples?
5. **F8 (grade_target coercion) — TASK-TRF-004**: Do integer metadata values pass validation correctly?
6. **F6 (retry cap) — TASK-TRF-006**: If any write failures occur, does the retry cap limit them to 3?

### Pipeline Performance

7. **How many targets were processed?** Total accepted vs rejected?
8. **What was the generation quality?** Are Coach verdicts reasonable? What scores were assigned?
9. **What was the throughput?** Tokens/second, time per target, overall pipeline duration?
10. **Are there any new issues?** Regressions or unexpected behaviours?

### Model Quality Assessment

11. **Tool calling reliability**: Does Qwen3.5-35B reliably call `rag_retrieval` with correct arguments?
12. **Example quality**: Are the generated training examples pedagogically sound and well-structured?
13. **Metadata correctness**: Are `ao`, `text`, `topic`, `grade_target`, `source`, `turns` values valid?
14. **`<think>` block quality**: Are reasoning traces meaningful, or just boilerplate?

## Acceptance Criteria

- [ ] Confirm each TASK-TRF-008-010 fix is working as intended (3 new fixes verified)
- [ ] Verify deferred fixes from Run 4 (F7, F8, F6) if code paths were exercised
- [ ] Pipeline progress summary (targets processed, accepted, rejected)
- [ ] Coach verdict analysis (score distribution, common issues)
- [ ] Token budget assessment (from new logging — peak usage vs 262K limit)
- [ ] Tool visibility audit (confirm no leaked backend tools, confirm rag_retrieval usage)
- [ ] New issues identified (if any)
- [ ] Decision on whether pipeline is ready for overnight run (1,000 targets)
- [ ] Implementation tasks created for any new findings

## Decisions Required

1. **Production readiness** — Is the pipeline ready for a full 1,000-target overnight run?
2. **Model confirmation** — Does Qwen3.5-35B-A3B-FP8 meet quality requirements for this domain?
3. **Configuration tuning** — Any adjustments needed to temperature, max_turns, or timeouts?
4. **Outstanding issues** — Do any new findings block the overnight run?

## Context

This is the **fifth** iteration of the review cycle:

```
TASK-REV-E2A7 (Run 1) — ChromaDB path + array validation bugs
    → TASK-FRF-001 + TASK-FRF-002 (fixes)

TASK-REV-FRF2 (Run 2) — tool_calls.args deserialization + model arg structure
    → Model switch to Nemotron 3 Nano 4B + qwen3_coder parser

TASK-REV-FRF3 (Run 3) — Context window + tool leakage + Coach bypass + type coercion
    → TASK-TRF-001 through TASK-TRF-007 (6 code fixes + validation run)

TASK-REV-TRF4 (Run 4) — Coach verdict parser preamble bug + no RAG tool use + no token logging
    → TASK-TRF-008 through TASK-TRF-010 (3 code fixes)

TASK-REV-TRF5 (Run 5, THIS REVIEW) — Post-fix validation with all parser/RAG/logging fixes
    → Goal: Confirm all fixes working, assess production readiness
```

Each iteration has progressively unblocked the pipeline. If successful, the pipeline moves to overnight production runs.

## Implementation Notes

This is a review/analysis task. Use `/task-review TASK-REV-TRF5` to execute the review, then create implementation tasks for any new findings.

## Test Execution Log

[Automatically populated by /task-work]
