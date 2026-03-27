---
id: TASK-REV-TRF4
title: Analyse fourth run findings (Qwen3.5-35B-A3B-FP8)
status: review_complete
created: 2026-03-26T00:00:00Z
updated: 2026-03-26T00:00:00Z
priority: critical
tags: [review, fourth-run, qwen35, post-fix-validation]
complexity: 5
task_type: review
decision_required: true
parent_review: TASK-REV-FRF3
depends_on: [TASK-TRF-001, TASK-TRF-002, TASK-TRF-003, TASK-TRF-004, TASK-TRF-005, TASK-TRF-006, TASK-TRF-007]
review_results:
  mode: decision
  depth: standard
  score: 25
  findings_count: 3
  recommendations_count: 3
  decision: pending
  report_path: .claude/reviews/TASK-REV-TRF4-review-report.md
  completed_at: 2026-03-26T15:00:00Z
test_results:
  status: pending
  coverage: null
  last_run: null
---

# Task: Analyse Fourth Run Findings (Qwen3.5-35B-A3B-FP8)

## Description

Analyse the fourth end-to-end run log at `docs/reviews/second-run/qwen35-run-1.md` captured after implementing all fixes from TASK-REV-FRF3:

- **TASK-TRF-001**: Updated vLLM launch script for Qwen3.5-35B-A3B-FP8 on GB10
- **TASK-TRF-002**: Updated agent-config.yaml (model + temperature)
- **TASK-TRF-003**: Removed FilesystemBackend from Player (fix tool leakage)
- **TASK-TRF-004**: Fixed grade_target type coercion (str() cast)
- **TASK-TRF-005**: Moved write_output to orchestrator (fix Coach bypass)
- **TASK-TRF-006**: Added write_output retry cap (3 per target)

This is the first run with the Qwen3.5-35B-A3B-FP8 model (262K context, BFCL-V4 67.3, native `<think>` blocks) and the architectural fix that moves write authority from the Player to the orchestrator.

## Source Document

`docs/reviews/second-run/qwen35-run-1.md`

## Key Questions to Analyse

### Fix Verification (from TASK-REV-FRF3)

1. **F3 (Coach bypass) — TASK-TRF-005**: Does the Coach now evaluate BEFORE any writes occur? Is the orchestrator-gated write pattern working?
2. **F4 (context exhaustion) — TASK-TRF-001/002**: Does the 262K context window provide sufficient headroom? How many tokens used at peak?
3. **F5 (tool leakage) — TASK-TRF-003**: Are only the expected tools visible in the request? (Player: `rag_retrieval` only; no `ls`, `read_file`, etc.)
4. **F7 (`<think>` blocks) — TASK-TRF-001**: Does Qwen3.5-35B produce valid `<think>...</think>` blocks for reasoning-type examples?
5. **F8 (grade_target coercion) — TASK-TRF-004**: Do integer metadata values pass validation correctly?
6. **F6 (retry cap) — TASK-TRF-006**: If any write failures occur, does the retry cap limit them to 3?

### Pipeline Performance

7. **How many targets were processed?** Total accepted vs rejected?
8. **What was the generation quality?** Are Coach verdicts reasonable? What scores were assigned?
9. **What was the throughput?** Tokens/second, time per target, overall pipeline duration?
10. **Are there any new issues?** Regressions or unexpected behaviours with the new model/architecture?

### Model Quality Assessment

11. **Tool calling reliability**: Does Qwen3.5-35B reliably call `rag_retrieval` with correct arguments?
12. **Example quality**: Are the generated training examples pedagogically sound and well-structured?
13. **Metadata correctness**: Are `ao`, `text`, `topic`, `grade_target`, `source`, `turns` values valid?
14. **`<think>` block quality**: Are reasoning traces meaningful, or just boilerplate?

## Acceptance Criteria

- [ ] Confirm each TASK-TRF fix is working as intended (6 fixes verified)
- [ ] Pipeline progress summary (targets processed, accepted, rejected)
- [ ] Coach verdict analysis (score distribution, common issues)
- [ ] Token budget assessment (peak usage vs 262K limit)
- [ ] Tool visibility audit (confirm no leaked backend tools)
- [ ] New issues identified (if any)
- [ ] Decision on whether pipeline is ready for overnight run (1,000 targets)
- [ ] Implementation tasks created for any new findings

## Decisions Required

1. **Production readiness** — Is the pipeline ready for a full 1,000-target overnight run?
2. **Model confirmation** — Does Qwen3.5-35B-A3B-FP8 meet quality requirements for this domain?
3. **Configuration tuning** — Any adjustments needed to temperature, max_turns, or timeouts?
4. **Outstanding issues** — Do any new findings block the overnight run?

## Context

This is the **fourth** iteration of the review cycle:

```
TASK-REV-E2A7 (Run 1) — ChromaDB path + array validation bugs
    → TASK-FRF-001 + TASK-FRF-002 (fixes)

TASK-REV-FRF2 (Run 2) — tool_calls.args deserialization + model arg structure
    → Model switch to Nemotron 3 Nano 4B + qwen3_coder parser

TASK-REV-FRF3 (Run 3) — Context window + tool leakage + Coach bypass + type coercion
    → TASK-TRF-001 through TASK-TRF-007 (6 code fixes + validation run)

TASK-REV-TRF4 (Run 4, THIS REVIEW) — Post-fix validation with Qwen3.5-35B-A3B-FP8
    → Goal: Confirm all fixes working, assess production readiness
```

Each iteration has progressively unblocked the pipeline. This is the first run with the production-candidate model and architecture. If successful, the pipeline moves to overnight production runs.

## Implementation Notes

This is a review/analysis task. Use `/task-review TASK-REV-TRF4` to execute the review, then create implementation tasks for any new findings.

## Test Execution Log

[Automatically populated by /task-work]
