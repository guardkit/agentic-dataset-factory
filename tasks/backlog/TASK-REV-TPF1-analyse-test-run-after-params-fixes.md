---
id: TASK-REV-TPF1
title: Analyse test-run-after-params-fixes output
status: review_complete
created: 2026-03-31T00:00:00Z
updated: 2026-03-31T00:00:00Z
priority: high
tags: [review, analysis, pipeline-run, structured-outputs, post-fix-validation]
complexity: 4
task_type: review
parent_review: TASK-REV-TFR1
test_results:
  status: pending
  coverage: null
  last_run: null
review_results:
  mode: code-quality
  depth: comprehensive
  score: 85
  findings_count: 6
  recommendations_count: 3
  decision: pending
  report_path: docs/reviews/TASK-REV-TPF1-review-report.md
  completed_at: 2026-03-31T00:00:00Z
---

# Task: Analyse test-run-after-params-fixes output

## Description

Analyse the output of the first successful pipeline run after the TASK-LR1-012 fixes
(structured_outputs via extra_body, xgrammar backend). This run completed all 77 targets
with zero errors and zero Coach parse failures — a major improvement over Long Run 1
(245 parse failures) and test-fixes-run-1 (immediate crash).

The run log is at `docs/reviews/longer-runs/test-run-after-params-fixes.md` (6326 lines).

### Run Summary (from log)

| Metric | Value |
|--------|-------|
| Targets | 77 |
| Accepted | 70 (90.9%) |
| Rejected | 7 (9.1%) |
| Total turns | 145 |
| Elapsed | 5802s (~97 min) |
| Coach parse failures | **0** (was 245 in Long Run 1) |
| Pipeline errors | **0** (was crash in test-fixes-run-1) |
| Prompt tokens | 1,309,353 |
| Completion tokens | 207,002 |
| Total tokens | 1,516,355 |

### Fixes Validated

- TASK-LR1-012: `structured_outputs` via `extra_body` (replaced deprecated `guided_json` / `model_kwargs`)
- vLLM `--structured-outputs-config.backend xgrammar` (replaced deprecated `--guided-decoding-backend`)
- Log line 13 confirms: "Coach structured_outputs schema enabled for local provider"
- Log line 6300 confirms: Coach request includes `extra_json: {structured_outputs: {json: ...}}`

## Scope

### Fix Validation
- [x] Confirm structured_outputs fix eliminated Coach parse failures (0 vs 245)
- [x] Confirm pipeline completed without errors
- [ ] Verify Coach structured output responses are valid CoachVerdict JSON
- [ ] Check whether xgrammar constrained output correctly (no prose preamble)

### Acceptance/Rejection Analysis
- [ ] Analyse the 7 rejected targets (indices 29, 30, 31, 54, 55, 59, 70) — all exhausted 3 turns
- [ ] Determine rejection reasons (Coach revise verdicts vs structural issues)
- [ ] Check if rejections cluster by category/type/text
- [ ] Compare 90.9% acceptance rate against Long Run 1 baseline

### Quality Analysis
- [ ] Review score distribution across accepted examples (are they mostly 4-5 or 3?)
- [ ] Check turn distribution (how many needed revision vs first-turn accept?)
- [ ] Review the 2 post-generation validation warnings (unclosed think blocks at indices 41, 42)
- [ ] Verify think-block normalisation (TASK-LR1-003/004) caught the unclosed blocks

### Other Wave 1 Fix Validation
- [ ] TASK-LR1-002 (validation gate): Check if post-generation validation caught any defects
- [ ] TASK-LR1-003/004 (prompt changes): Check if think-block compliance improved
- [ ] TASK-LR1-010: Check any other Wave 1 fix impact visible in logs

### Performance Analysis
- [ ] Calculate average time per target (~75s)
- [ ] Check for any unusually slow targets (timeout near 600s limit)
- [ ] Token efficiency: avg tokens per accepted example

## Acceptance Criteria

- [ ] All 7 rejections analysed with root cause categorisation
- [ ] Score distribution documented
- [ ] Wave 1 fix effectiveness summarised
- [ ] Readiness assessment for overnight production run (77 → 1000 targets)
- [ ] Any new issues or fix recommendations documented

## Key Files

- Run log: `docs/reviews/longer-runs/test-run-after-params-fixes.md`
- Previous run (crash): `docs/reviews/longer-runs/test-fixes-run-1.md`
- Long Run 1 review: `docs/reviews/TASK-REV-649A-long-run-1-review-report.md`
- Fix task: `tasks/backlog/long-run-1-fixes/TASK-LR1-012-fix-guided-json-extra-body.md`

## Implementation Notes

This is a review/analysis task. Use `/task-review TASK-REV-TPF1` to execute the analysis.
