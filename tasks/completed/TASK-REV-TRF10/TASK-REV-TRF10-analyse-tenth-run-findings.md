---
id: TASK-REV-TRF10
title: Analyse tenth run findings (Qwen3.5-35B-A3B-FP8, post-TRF-028-030)
status: completed
created: 2026-03-27T19:00:00Z
updated: 2026-03-27T19:00:00Z
priority: critical
tags: [review, tenth-run, qwen35, post-fix-validation, production-readiness]
complexity: 5
task_type: review
decision_required: true
parent_review: TASK-REV-TRF9
depends_on: [TASK-TRF-028, TASK-TRF-029, TASK-TRF-030]
review_results:
  mode: architectural
  depth: standard
  score: 95
  findings_count: 2
  recommendations_count: 3
  decision: conditional_go
  report_path: .claude/reviews/TASK-REV-TRF10-review-report.md
  completed_at: 2026-03-27T19:30:00Z
test_results:
  status: pending
  coverage: null
  last_run: null
---

# Task: Analyse Tenth Run Findings (Qwen3.5-35B-A3B-FP8, Post-TRF-028-030)

## Description

Analyse the tenth end-to-end run log at `docs/reviews/second-run/qwen35-run-7.md` captured after implementing all fixes from TASK-REV-TRF9:

- **TASK-TRF-028**: Added range notation detection to `_coerce_valid_values` (parser no longer treats `1+` as an enum)
- **TASK-TRF-029**: Added explicit `<think>` block instruction to Player prompt
- **TASK-TRF-030**: JSON string repair pre-processing for literal newlines

**Early indication: the pipeline appears to have produced accepted examples.** This review should confirm success, assess quality, and make a production readiness decision for the 1,000-target overnight run.

## Source Document

`docs/reviews/second-run/qwen35-run-7.md`

## Key Questions to Analyse

### Fix Verification (from TASK-REV-TRF9)

1. **Range notation parser fix (TASK-TRF-028)**: Does `metadata.turns` validation pass? No more "value '1' not in valid values" errors?
2. **Think block prompt instruction (TASK-TRF-029)**: Does the Player include `<think>` blocks in the assistant content field of generated training examples?
3. **JSON string repair (TASK-TRF-030)**: Do earlier turns now succeed with JSON extraction? Has the repair pre-processing improved extraction success rates?

### Pipeline Success Metrics

4. **Accepted examples**: How many targets were accepted? What is the acceptance rate?
5. **First-turn success**: Do any targets succeed on Turn 1 (no revision needed)?
6. **Examples written**: Were training examples actually written to `output/train.jsonl`?
7. **Write validation**: Do all accepted examples pass full `write_output` validation (schema, think blocks, metadata)?

### Carry-Forward Verification

8. **Player tools**: Still exactly 1 tool (`rag_retrieval`)?
9. **Coach tools**: Still 0 tools?
10. **Token logging**: Per-turn and aggregate stats present?
11. **Think block normalisation (TRF-020/021)**: Still working with unstripped think blocks?
12. **max_tokens (TRF-022)**: Completion tokens still under 4096?
13. **Extraction failure logging (TRF-023)**: Improved logging format still present?

### Quality Assessment

14. **Example quality**: Are generated training examples pedagogically sound for GCSE English tutoring?
15. **Think block quality**: Are `<think>` blocks meaningful, containing AO analysis, misconception awareness, and Socratic strategy?
16. **Coach evaluation quality**: Are Coach verdicts accurate — accepting good examples and rejecting bad ones?
17. **Metadata accuracy**: Are metadata fields (text, topic, ao, grade_target) correct for the generated content?

### Performance Metrics

18. **Throughput**: Time per target, tokens per turn, overall pipeline duration?
19. **Token efficiency**: Are turns productive (not wasted on extraction failures)?
20. **Revision patterns**: How many turns needed on average? Are revision cycles productive?

### Production Readiness

21. **Regressions**: Any new issues introduced by TRF-028-030?
22. **Scale concerns**: Anything that would fail at 1,000 targets that works at 1?
23. **Configuration**: Are temperature, max_turns, max_tokens optimal for overnight run?
24. **Error handling**: Are transient failures (timeouts, rate limits) handled gracefully?

## Acceptance Criteria

- [ ] Confirm TASK-TRF-028 fix is working (turns validation passes)
- [ ] Confirm TASK-TRF-029 fix is working (think blocks in assistant content)
- [ ] Confirm TASK-TRF-030 fix is working (JSON repair improves extraction)
- [ ] Verify all carry-forward fixes still working
- [ ] Pipeline produces accepted examples written to output/train.jsonl
- [ ] Example quality assessment (pedagogical soundness)
- [ ] Think block quality assessment
- [ ] Coach verdict analysis
- [ ] Token budget assessment
- [ ] Performance metrics for overnight run projection
- [ ] New issues identified (if any)
- [ ] **GO/NO-GO decision for 1,000-target overnight run**
- [ ] Implementation tasks created for any new findings

## Decisions Required

1. **GO/NO-GO for overnight run** — Is the pipeline ready for 1,000 targets?
2. **Model confirmation** — Does Qwen3.5-35B-A3B-FP8 meet quality requirements?
3. **Configuration for overnight** — Final settings for temperature, max_turns, max_tokens, timeouts?
4. **Monitoring plan** — What should be monitored during the overnight run?

## Context

This is the **tenth** iteration of the review cycle:

```
TASK-REV-E2A7 (Run 1) — ChromaDB path + array validation bugs
TASK-REV-FRF2 (Run 2) — tool_calls.args deserialization + model arg structure
TASK-REV-FRF3 (Run 3) — Context window + tool leakage + Coach bypass + type coercion
TASK-REV-TRF4 (Run 4) — Coach verdict parser preamble bug + no RAG tool use + no token logging
TASK-REV-TRF5 (Run 5) — Coach empty content (think-mode split) + tool leakage regression
TASK-REV-TRF6 (Run 6) — Player write_file misuse via leaked FilesystemMiddleware tools
TASK-REV-TRF7 (Run 7) — JSON extraction failure due to unclosed think blocks
TASK-REV-TRF8 (Run 8) — vLLM --reasoning-parser stripping think blocks + naive brace matching
TASK-REV-TRF9 (Run 9) — metadata.turns validation bug + no think blocks in examples
TASK-REV-TRF10 (Run 10, THIS REVIEW) — Post-fix validation: pipeline should produce accepted examples
    -> Goal: Confirm end-to-end success, GO/NO-GO for 1,000-target overnight run
```

After 9 iterations and 30 fixes (TRF-001 through TRF-030), the pipeline should now be fully functional. Run 10 is the validation run that determines whether we proceed to production.

## Implementation Notes

This is a review/analysis task. Use `/task-review TASK-REV-TRF10` to execute the review, then create implementation tasks for any new findings.

## Test Execution Log

[Automatically populated by /task-work]
