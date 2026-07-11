---
id: TASK-REV-TRF8
title: Analyse eighth run findings (Qwen3.5-35B-A3B-FP8, post-TRF-020-023)
status: review_complete
created: 2026-03-27T00:00:00Z
updated: 2026-03-27T16:00:00Z
review_results:
  mode: code-quality
  depth: standard
  score: 25
  findings_count: 5
  recommendations_count: 5
  decision: implement
  report_path: .claude/reviews/TASK-REV-TRF8-review-report.md
priority: critical
tags: [review, eighth-run, qwen35, post-fix-validation]
complexity: 5
task_type: review
decision_required: true
parent_review: TASK-REV-TRF7
depends_on: [TASK-TRF-020, TASK-TRF-021, TASK-TRF-022, TASK-TRF-023]
test_results:
  status: pending
  coverage: null
  last_run: null
---

# Task: Analyse Eighth Run Findings (Qwen3.5-35B-A3B-FP8, Post-TRF-020-023)

## Description

Analyse the eighth end-to-end run log at `docs/reviews/second-run/qwen35-run-5.md` captured after implementing all fixes from TASK-REV-TRF7:

- **TASK-TRF-020**: Called `normalise_think_closing_tags` before `_extract_example_json` in the generation loop
- **TASK-TRF-021**: Extended normaliser to handle missing close tags (`<think>...EOF` pattern)
- **TASK-TRF-022**: Set explicit `max_tokens` on Player and Coach models
- **TASK-TRF-023**: Improved JSON extraction failure logging (full content length + tail)

This is the fifth run with Qwen3.5-35B-A3B-FP8 and the first run where think block normalisation and JSON extraction should work end-to-end. Run 7 showed Coach accepting examples (score 5/5) but JSON extraction failing due to unclosed think blocks.

## Source Document

`docs/reviews/second-run/qwen35-run-5.md`

## Key Questions to Analyse

### Fix Verification (from TASK-REV-TRF7)

1. **Think block normalisation (TASK-TRF-020)**: Is `normalise_think_closing_tags` called before `_extract_example_json`? Do the logs show normalisation happening?
2. **EOF pattern handling (TASK-TRF-021)**: Are `<think>...EOF` blocks (no closing tag at all) now closed? What is the think block open/close ratio?
3. **max_tokens (TASK-TRF-022)**: Are Player completion_tokens higher than the previous ~940 cap? Is JSON no longer truncated mid-object?
4. **Extraction failure logging (TASK-TRF-023)**: If any extraction failures occur, do the logs now show full content length and last 200 chars?

### Carry-Forward Verification (from TASK-REV-TRF6, confirmed in TRF7)

5. **F1 (Player tool leakage)**: Player still has exactly 1 tool (`rag_retrieval`)?
6. **F4 (Coach 0 tools)**: Coach still has 0 tools at runtime?
7. **F6 (Player tool-use cap)**: Player still makes 0-1 `rag_retrieval` calls?
8. **Token logging**: Per-turn and aggregate token stats still present?

### JSON Extraction (Primary Focus)

9. **Extraction success**: Does `_extract_example_json` succeed now? Are training examples written to `train.jsonl`?
10. **Code fence handling**: Are `\`\`\`json` wrapped responses handled correctly?
11. **Brace matching**: Does the 3-try strategy (direct parse, fence extraction, brace matching) succeed?

### Pipeline Performance

12. **How many targets were processed?** Total accepted vs rejected?
13. **What was the generation quality?** Coach verdicts and scores?
14. **What was the throughput?** Tokens/second, time per target, overall pipeline duration?
15. **Write validation**: Do accepted examples pass `write_output` validation (schema, think blocks, metadata)?

### Model Quality Assessment

16. **Example quality**: Are generated training examples pedagogically sound?
17. **Coach evaluation quality**: Are Coach verdicts accurate and well-reasoned?
18. **Think block quality**: Are normalised think blocks meaningful and well-structured?

### New Issues

19. **Regressions**: Any new issues introduced by TRF-020-023?
20. **Remaining blockers**: Anything preventing the overnight run (1,000 targets)?

## Acceptance Criteria

- [ ] Confirm TASK-TRF-020 fix is working (normalisation before extraction)
- [ ] Confirm TASK-TRF-021 fix is working (EOF pattern think blocks closed)
- [ ] Confirm TASK-TRF-022 fix is working (explicit max_tokens, no truncation)
- [ ] Confirm TASK-TRF-023 fix is working (improved failure logging)
- [ ] Verify all carry-forward fixes still working (Player tools, Coach tools, token logging)
- [ ] Pipeline progress summary (targets processed, accepted, rejected)
- [ ] Coach verdict analysis (score distribution, quality of feedback)
- [ ] Token budget assessment with actual logged values
- [ ] Think block open/close ratio (target: >95% properly closed)
- [ ] New issues identified (if any)
- [ ] **Decision on whether pipeline is ready for overnight run (1,000 targets)**
- [ ] Implementation tasks created for any new findings

## Decisions Required

1. **Production readiness** -- Is the pipeline ready for a full 1,000-target overnight run?
2. **Model confirmation** -- Does Qwen3.5-35B-A3B-FP8 meet quality requirements?
3. **Configuration tuning** -- Any adjustments needed to temperature, max_turns, max_tokens, or timeouts?
4. **Outstanding issues** -- Do any new findings block the overnight run?

## Context

This is the **eighth** iteration of the review cycle:

```
TASK-REV-E2A7 (Run 1) -- ChromaDB path + array validation bugs
    -> TASK-FRF-001 + TASK-FRF-002 (fixes)

TASK-REV-FRF2 (Run 2) -- tool_calls.args deserialization + model arg structure
    -> Model switch to Nemotron 3 Nano 4B + qwen3_coder parser

TASK-REV-FRF3 (Run 3) -- Context window + tool leakage + Coach bypass + type coercion
    -> TASK-TRF-001 through TASK-TRF-007 (6 code fixes + validation run)

TASK-REV-TRF4 (Run 4) -- Coach verdict parser preamble bug + no RAG tool use + no token logging
    -> TASK-TRF-008 through TASK-TRF-010 (3 code fixes)

TASK-REV-TRF5 (Run 5) -- Coach empty content (think-mode split) + tool leakage regression + skills lost
    -> TASK-TRF-011 through TASK-TRF-015 (skills restore + 4 code fixes)

TASK-REV-TRF6 (Run 6) -- Player write_file misuse via leaked FilesystemMiddleware tools
    -> TASK-TRF-016 through TASK-TRF-019 (Player factory fix + tests + logging + think tags)

TASK-REV-TRF7 (Run 7) -- JSON extraction failure due to unclosed think blocks
    -> TASK-TRF-020 through TASK-TRF-023 (normaliser in gen loop + EOF pattern + max_tokens + logging)

TASK-REV-TRF8 (Run 8, THIS REVIEW) -- Post-fix validation with think block + extraction fixes
    -> Goal: Confirm ALL fixes working end-to-end, assess production readiness
```

Each iteration has progressively unblocked the pipeline. Run 7 achieved correct architecture but failed at serialisation. Run 8 is the first run where both architecture AND serialisation should work. If successful, the pipeline moves to overnight production runs.

## Implementation Notes

This is a review/analysis task. Use `/task-review TASK-REV-TRF8` to execute the review, then create implementation tasks for any new findings.

## Test Execution Log

[Automatically populated by /task-work]
