---
id: TASK-REV-TRF9
title: Analyse ninth run findings (Qwen3.5-35B-A3B-FP8, post-TRF-024-027)
status: review_complete
created: 2026-03-27T17:00:00Z
updated: 2026-03-27T17:30:00Z
review_results:
  mode: code-quality
  depth: standard
  score: 65
  findings_count: 5
  recommendations_count: 4
  decision: implement
  report_path: .claude/reviews/TASK-REV-TRF9-review-report.md
priority: critical
tags: [review, ninth-run, qwen35, post-fix-validation]
complexity: 5
task_type: review
decision_required: true
parent_review: TASK-REV-TRF8
depends_on: [TASK-TRF-024, TASK-TRF-025, TASK-TRF-026, TASK-TRF-027]
test_results:
  status: pending
  coverage: null
  last_run: null
---

# Task: Analyse Ninth Run Findings (Qwen3.5-35B-A3B-FP8, Post-TRF-024-027)

## Description

Analyse the ninth end-to-end run log at `docs/reviews/second-run/qwen35-run-6.md` captured after implementing all fixes from TASK-REV-TRF8:

- **TASK-TRF-024**: Removed `--reasoning-parser qwen3` from vLLM launch script (think blocks no longer stripped)
- **TASK-TRF-025**: JSON-string-aware brace matching in `_extract_json_object` (handles unbalanced braces in strings)
- **TASK-TRF-026**: Added `reasoning_content` fallback to `_extract_player_content` (defence-in-depth)
- **TASK-TRF-027**: Coach prompt — verify think block presence before accepting

This is the sixth run with Qwen3.5-35B-A3B-FP8 and the first run where:
- Think blocks should flow through naturally (no vLLM stripping)
- JSON extraction should handle braces in string values
- Coach should reject examples missing think blocks

## Source Document

`docs/reviews/second-run/qwen35-run-6.md`

## Key Questions to Analyse

### Fix Verification (from TASK-REV-TRF8)

1. **Think block restoration (TASK-TRF-024)**: Does the Player's `content` field now contain `<think>` blocks? Are think blocks visible in the raw Player output?
2. **JSON-string-aware brace matching (TASK-TRF-025)**: Does `_extract_json_object` succeed on Player content with braces in string values? Is the 3-try strategy now robust?
3. **Player reasoning_content fallback (TASK-TRF-026)**: If `reasoning_content` is present in `additional_kwargs`, does the Player extractor handle it? (May not be exercised if TRF-024 works correctly)
4. **Coach think block verification (TASK-TRF-027)**: Does the Coach reject reasoning-type examples that lack `<think>` blocks? Are Coach verdicts now checking for structural completeness?

### Carry-Forward Verification (from TASK-REV-TRF6, confirmed in TRF7 and TRF8)

5. **F1 (Player tool leakage)**: Player still has exactly 1 tool (`rag_retrieval`)?
6. **F4 (Coach 0 tools)**: Coach still has 0 tools at runtime?
7. **F6 (Player tool-use cap)**: Player still makes 0-1 `rag_retrieval` calls?
8. **Token logging**: Per-turn and aggregate token stats still present?

### Previously Fixed (from TRF-020-023, confirmed in TRF8)

9. **Think block normalisation (TASK-TRF-020)**: Is `normalise_think_closing_tags` still called before extraction? Does it handle any malformed tags from the now-unstripped model output?
10. **EOF pattern handling (TASK-TRF-021)**: Are `<think>...EOF` blocks (unclosed at end of content) handled? NOW EXERCISED since think blocks are present.
11. **max_tokens (TASK-TRF-022)**: Are completion_tokens still under 4096? Is the model generating longer responses now that think blocks are included?
12. **Extraction failure logging (TASK-TRF-023)**: If any extraction failures occur, do logs show content length + tail?

### JSON Extraction (Primary Focus)

13. **Extraction success**: Does `_extract_example_json` succeed now? Are training examples written to `train.jsonl`?
14. **Think block + JSON format**: How does the Player structure its output? Is it `<think>...</think>\n\n{json}` or `{json with think in content}`?
15. **Code fence handling**: Are ` ```json ` wrapped responses handled correctly with the new brace matcher?

### Pipeline Performance

16. **How many targets were processed?** Total accepted vs rejected?
17. **What was the generation quality?** Coach verdicts and scores?
18. **What was the throughput?** Tokens/second, time per target, overall pipeline duration?
19. **Write validation**: Do accepted examples pass `write_output` validation (schema, think blocks, metadata)?

### Model Quality Assessment

20. **Example quality**: Are generated training examples pedagogically sound?
21. **Think block quality**: Are think blocks meaningful, well-structured, and pedagogically appropriate?
22. **Coach evaluation quality**: Are Coach verdicts accurate — accepting good examples and rejecting bad ones?

### New Issues

23. **Regressions**: Any new issues introduced by TRF-024-027?
24. **Think block in JSON strings**: Does the model include think blocks inside the JSON content field (desired) vs outside it (needs extraction)?
25. **Remaining blockers**: Anything preventing the overnight run (1,000 targets)?

## Acceptance Criteria

- [ ] Confirm TASK-TRF-024 fix is working (think blocks in Player content, not stripped by vLLM)
- [ ] Confirm TASK-TRF-025 fix is working (JSON extraction succeeds with braces in strings)
- [ ] Confirm TASK-TRF-026 fix is deployed (reasoning_content fallback present)
- [ ] Confirm TASK-TRF-027 fix is working (Coach checks think block presence)
- [ ] Verify all carry-forward fixes still working (Player tools, Coach tools, token logging)
- [ ] Verify TRF-020-023 fixes still working with unstripped think blocks
- [ ] Pipeline progress summary (targets processed, accepted, rejected)
- [ ] Coach verdict analysis (score distribution, quality of feedback)
- [ ] Token budget assessment with actual logged values
- [ ] Think block open/close ratio (target: >95% properly closed)
- [ ] Training example quality assessment
- [ ] New issues identified (if any)
- [ ] **Decision on whether pipeline is ready for overnight run (1,000 targets)**
- [ ] Implementation tasks created for any new findings

## Decisions Required

1. **Production readiness** — Is the pipeline ready for a full 1,000-target overnight run?
2. **Model confirmation** — Does Qwen3.5-35B-A3B-FP8 meet quality requirements with think blocks restored?
3. **Configuration tuning** — Any adjustments needed to temperature, max_turns, max_tokens, or timeouts?
4. **Outstanding issues** — Do any new findings block the overnight run?

## Context

This is the **ninth** iteration of the review cycle:

```
TASK-REV-E2A7 (Run 1) — ChromaDB path + array validation bugs
    -> TASK-FRF-001 + TASK-FRF-002 (fixes)

TASK-REV-FRF2 (Run 2) — tool_calls.args deserialization + model arg structure
    -> Model switch to Nemotron 3 Nano 4B + qwen3_coder parser

TASK-REV-FRF3 (Run 3) — Context window + tool leakage + Coach bypass + type coercion
    -> TASK-TRF-001 through TASK-TRF-007 (6 code fixes + validation run)

TASK-REV-TRF4 (Run 4) — Coach verdict parser preamble bug + no RAG tool use + no token logging
    -> TASK-TRF-008 through TASK-TRF-010 (3 code fixes)

TASK-REV-TRF5 (Run 5) — Coach empty content (think-mode split) + tool leakage regression + skills lost
    -> TASK-TRF-011 through TASK-TRF-015 (skills restore + 4 code fixes)

TASK-REV-TRF6 (Run 6) — Player write_file misuse via leaked FilesystemMiddleware tools
    -> TASK-TRF-016 through TASK-TRF-019 (Player factory fix + tests + logging + think tags)

TASK-REV-TRF7 (Run 7) — JSON extraction failure due to unclosed think blocks
    -> TASK-TRF-020 through TASK-TRF-023 (normaliser in gen loop + EOF pattern + max_tokens + logging)

TASK-REV-TRF8 (Run 8) — vLLM --reasoning-parser stripping think blocks + naive brace matching
    -> TASK-TRF-024 through TASK-TRF-027 (remove reasoning-parser + brace fix + fallback + Coach prompt)

TASK-REV-TRF9 (Run 9, THIS REVIEW) — Post-fix validation with think blocks restored + robust extraction
    -> Goal: Confirm ALL fixes working end-to-end, assess production readiness
```

Each iteration has progressively unblocked the pipeline. Run 8 identified the vLLM reasoning-parser as the root cause of missing think blocks and discovered the naive brace-matching bug. Run 9 is the first run where think blocks, JSON extraction, and Coach evaluation should all work correctly. If successful, the pipeline moves to overnight production runs.

## Implementation Notes

This is a review/analysis task. Use `/task-review TASK-REV-TRF9` to execute the review, then create implementation tasks for any new findings.

## Test Execution Log

[Automatically populated by /task-work]
