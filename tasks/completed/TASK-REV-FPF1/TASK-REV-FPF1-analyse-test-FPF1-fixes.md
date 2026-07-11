---
id: TASK-REV-FPF1
title: Analyse test-FPF1-fixes output (post format-gate fixes)
status: review_complete
created: 2026-03-31T00:00:00Z
updated: 2026-03-31T00:00:00Z
priority: high
tags: [review, analysis, pipeline-run, format-gate, post-fix-validation]
complexity: 4
task_type: review
parent_review: TASK-REV-TPF1
review_results:
  mode: code-quality
  depth: comprehensive
  score: 58
  findings_count: 10
  recommendations_count: 5
  decision: implement
  report_path: docs/reviews/TASK-REV-FPF1-review-report.md
  completed_at: 2026-03-31T00:00:00Z
test_results:
  status: pending
  coverage: null
  last_run: null
---

# Task: Analyse test-FPF1-fixes output (post format-gate fixes)

## Description

Analyse the output of the pipeline run following the TASK-REV-TPF1 fixes:
- **Fix 1**: Pre-Coach JSON format gate (skip Coach when Player output is not parseable JSON)
- **Fix 2**: Stronger Player prompt (BAD/GOOD examples, "do not think out loud" instruction)
- **Fix 1b**: Format Error vs Coach Feedback labelling in Player messages

The run log is at `docs/reviews/longer-runs/test-FPF1-fixes.md`.

### Fixes Being Validated

| Fix | Task | Description |
|-----|------|-------------|
| Pre-Coach format gate | TASK-REV-TPF1 Fix 1 | Skip Coach invocation when Player output fails JSON extraction |
| Stronger Player prompt | TASK-REV-TPF1 Fix 2 | Added BAD/GOOD examples, "do not think out loud" instruction |
| Feedback labelling | TASK-REV-TPF1 Fix 1b | Distinguish "Format Error" from "Coach Feedback" in messages |

### Baseline (test-run-after-params-fixes)

| Metric | Value |
|--------|-------|
| Targets | 77 |
| Accepted | 70 (90.9%) |
| Rejected | 7 (9.1%) |
| Coach parse failures | 0 |
| Player JSON extraction failures | 44 (across 33 targets) |
| Wasted Coach calls on non-JSON | ~44 |
| Token total | 1,516,355 |

## Scope

### Format Gate Validation
- [ ] Confirm format gate is triggering (look for "Pre-Coach format gate" log messages)
- [ ] Count how many Coach calls were saved by the format gate
- [ ] Verify format gate does NOT block valid JSON Player output
- [ ] Check "FORMAT ERROR" feedback label appears in Player messages (not "Coach Feedback")

### Player JSON Compliance Improvement
- [ ] Count Player JSON extraction failures (compare to baseline: 44)
- [ ] Determine if the stronger prompt reduced prose-before-JSON occurrences
- [ ] Check if rejection count decreased (baseline: 7/77 = 9.1%)

### Acceptance/Rejection Analysis
- [ ] Analyse any rejected targets — root cause categorisation
- [ ] Check if "unseen poetry" and "AO-specific guidance" categories still fail (baseline: 100% rejection)
- [ ] Compare acceptance rate to baseline (90.9%)

### Quality Analysis
- [ ] Score distribution across accepted examples
- [ ] Turn distribution (first-turn accept vs revisions)
- [ ] Check for post-generation validation catches (unclosed think blocks etc.)

### Token Efficiency
- [ ] Compare total token usage to baseline (1,516,355)
- [ ] Calculate token savings from skipped Coach calls
- [ ] Average tokens per accepted example

### Performance
- [ ] Average time per target (baseline: 75.4s)
- [ ] Any unusually slow targets

## Acceptance Criteria

- [ ] Format gate effectiveness quantified (Coach calls saved, false positives checked)
- [ ] Player JSON compliance improvement measured (extraction failures vs baseline)
- [ ] Acceptance rate compared to baseline (90.9%)
- [ ] Token savings from format gate quantified
- [ ] Readiness assessment for 1,000-target production run updated
- [ ] Any new issues or regressions documented

## Key Files

- Run log: `docs/reviews/longer-runs/test-FPF1-fixes.md`
- Baseline run: `docs/reviews/longer-runs/test-run-after-params-fixes.md`
- Baseline review: `docs/reviews/TASK-REV-TPF1-review-report.md`
- Fix 1 code: `entrypoint/generation_loop.py` (pre-Coach format gate, lines 703-720)
- Fix 2 code: `prompts/player_prompts.py` (stronger JSON instructions, lines 101-121)

## Implementation Notes

This is a review/analysis task. Use `/task-review TASK-REV-FPF1` to execute the analysis.
