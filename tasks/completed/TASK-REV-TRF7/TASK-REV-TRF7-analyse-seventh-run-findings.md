---
id: TASK-REV-TRF7
title: Analyse seventh run findings (Qwen3.5-35B-A3B-FP8, post-TRF-016-019)
status: review_complete
review_mode: architectural
review_depth: standard
review_results:
  score: 69
  findings_count: 13
  recommendations_count: 5
  passing: 9
  failing: 4
  decision: fix-and-rerun
  report_path: .claude/reviews/TASK-REV-TRF7-review-report.md
  completed_at: 2026-03-27T12:00:00Z
created: 2026-03-27T00:00:00Z
updated: 2026-03-27T00:00:00Z
priority: critical
tags: [review, seventh-run, qwen35, post-fix-validation]
complexity: 5
task_type: review
decision_required: true
parent_review: TASK-REV-TRF6
depends_on: [TASK-TRF-016, TASK-TRF-017, TASK-TRF-018, TASK-TRF-019]
test_results:
  status: pending
  coverage: null
  last_run: null
---

# Task: Analyse Seventh Run Findings (Qwen3.5-35B-A3B-FP8, Post-TRF-016-019)

## Description

Analyse the seventh end-to-end run log at `docs/reviews/second-run/qwen35-run-4.md` captured after implementing all fixes from TASK-REV-TRF6:

- **TASK-TRF-016**: Bypassed `create_deep_agent` for Player — switched to `create_agent()` with curated middleware excluding `FilesystemMiddleware`, removing 8 leaked platform tools
- **TASK-TRF-017**: Updated `tests/test_player_factory.py` to match new `create_agent` pattern
- **TASK-TRF-018**: Added token usage logging from vLLM responses
- **TASK-TRF-019**: Verified and fixed `<think>` closing tag handling

This is the fourth run with Qwen3.5-35B-A3B-FP8 and the first run where **both** Player and Coach should have correct tool sets (Player: `rag_retrieval` only; Coach: 0 tools) and no `FilesystemMiddleware` leakage.

## Source Document

`docs/reviews/second-run/qwen35-run-4.md`

## Key Questions to Analyse

### Fix Verification (from TASK-REV-TRF6)

1. **F1 (Player tool leakage) — TASK-TRF-016**: Does the Player now have exactly 1 tool (`rag_retrieval`)? Are the 8 leaked platform tools (`write_todos`, `ls`, `read_file`, `write_file`, `edit_file`, `glob`, `grep`, `task`) gone?
2. **F2 (Player content return) — TASK-TRF-016**: Does the Player return the training example as response content (not via `write_file` to `/tmp/`)?
3. **F3 (Player system prompt) — TASK-TRF-016**: Is the system prompt dramatically smaller without DeepAgents boilerplate (~43K chars → much smaller)?
4. **F4 (Coach 0 tools runtime) — TASK-TRF-012**: Does the Coach HTTP request contain an empty `tools` array at runtime? (Previously untested — Coach was never invoked in Run 6)
5. **F5 (Coach reasoning extraction) — TASK-TRF-013**: Does the Coach verdict parse correctly? Does the `<think>` tag fallback extract reasoning content? Are verdicts valid CoachVerdict JSON?
6. **F6 (Player tool-use cap) — TASK-TRF-014**: Does the Player make 0-1 `rag_retrieval` calls (not 3+)?
7. **F7 (Example truncation) — TASK-TRF-015**: Does the Coach receive the complete training example JSON (system + user + assistant messages + metadata)?

### Token/Logging Verification (TASK-TRF-018)

8. **Token usage logging**: Are `prompt_tokens`, `completion_tokens`, `total_tokens` logged for each LLM call?
9. **Token budget**: What are the peak prompt_tokens for Player and Coach vs the 262K limit?
10. **Prompt size reduction**: How much smaller is the Player system prompt now without the 8 tool schemas and DeepAgents boilerplate?

### Think Block Verification (TASK-TRF-019)

11. **`<think>` closing tag**: Are `<think>` blocks properly closed with `</think>` (not `<think>`)?
12. **`<think>` block quality**: Are reasoning traces meaningful and pedagogically sound?

### Previously Deferred Fixes

13. **F6 (retry cap) — TASK-TRF-006**: If any write failures occur, does the retry cap limit them to 3?
14. **F7 (`<think>` blocks) — TASK-TRF-001**: Does Qwen3.5-35B produce valid `<think>...</think>` blocks for reasoning-type examples?

### Pipeline Performance

15. **How many targets were processed?** Total accepted vs rejected?
16. **What was the generation quality?** Are Coach verdicts reasonable? What scores were assigned?
17. **What was the throughput?** Tokens/second, time per target, overall pipeline duration?
18. **Are there any new issues?** Regressions or unexpected behaviours?

### Model Quality Assessment

19. **Tool calling reliability**: Does Qwen3.5-35B reliably call `rag_retrieval` with correct arguments (now that `write_file` is gone)?
20. **Example quality**: Are the generated training examples pedagogically sound and well-structured?
21. **Metadata correctness**: Are `ao`, `text`, `topic`, `grade_target`, `source`, `turns` values valid?
22. **Coach evaluation quality**: Are Coach verdicts accurate and well-reasoned?

## Acceptance Criteria

- [ ] Confirm TASK-TRF-016 fix is working (Player has only `rag_retrieval`, returns content in response)
- [ ] Confirm TASK-TRF-017 tests pass
- [ ] Confirm TASK-TRF-018 token logging is present and useful
- [ ] Confirm TASK-TRF-019 `<think>` tag handling is correct
- [ ] Verify all previously untested fixes from TASK-REV-TRF6 (Coach tools, reasoning extraction, tool-use cap, truncation)
- [ ] Pipeline progress summary (targets processed, accepted, rejected)
- [ ] Coach verdict analysis (score distribution, common issues, quality of feedback)
- [ ] Token budget assessment with actual logged values
- [ ] System prompt size comparison (before/after TRF-016)
- [ ] New issues identified (if any)
- [ ] **Decision on whether pipeline is ready for overnight run (1,000 targets)**
- [ ] Implementation tasks created for any new findings

## Decisions Required

1. **Production readiness** — Is the pipeline ready for a full 1,000-target overnight run?
2. **Model confirmation** — Does Qwen3.5-35B-A3B-FP8 meet quality requirements for this domain?
3. **Configuration tuning** — Any adjustments needed to temperature, max_turns, or timeouts?
4. **Outstanding issues** — Do any new findings block the overnight run?

## Context

This is the **seventh** iteration of the review cycle:

```
TASK-REV-E2A7 (Run 1) — ChromaDB path + array validation bugs
    → TASK-FRF-001 + TASK-FRF-002 (fixes)

TASK-REV-FRF2 (Run 2) — tool_calls.args deserialization + model arg structure
    → Model switch to Nemotron 3 Nano 4B + qwen3_coder parser

TASK-REV-FRF3 (Run 3) — Context window + tool leakage + Coach bypass + type coercion
    → TASK-TRF-001 through TASK-TRF-007 (6 code fixes + validation run)

TASK-REV-TRF4 (Run 4) — Coach verdict parser preamble bug + no RAG tool use + no token logging
    → TASK-TRF-008 through TASK-TRF-010 (3 code fixes)

TASK-REV-TRF5 (Run 5) — Coach empty content (think-mode split) + tool leakage regression + skills lost
    → TASK-TRF-011 through TASK-TRF-015 (skills restore + 4 code fixes)

TASK-REV-TRF6 (Run 6) — Player write_file misuse via leaked FilesystemMiddleware tools
    → TASK-TRF-016 through TASK-TRF-019 (Player factory fix + tests + logging + think tags)

TASK-REV-TRF7 (Run 7, THIS REVIEW) — Post-fix validation with Player tool leakage resolved
    → Goal: Confirm ALL fixes working end-to-end, assess production readiness
```

Each iteration has progressively unblocked the pipeline. Run 7 is the first run where both Player and Coach should have correct tool sets. If successful, the pipeline moves to overnight production runs.

## Implementation Notes

This is a review/analysis task. Use `/task-review TASK-REV-TRF7` to execute the review, then create implementation tasks for any new findings.

## Test Execution Log

[Automatically populated by /task-work]
