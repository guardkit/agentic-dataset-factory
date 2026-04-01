---
id: TASK-REV-FRF1
title: Analyse test-fpf1-regression-fixes output (post FPF1 regression fixes)
status: review_complete
created: 2026-03-31T00:00:00Z
updated: 2026-03-31T00:00:00Z
priority: high
tags: [review, analysis, pipeline-run, regression-fix, post-fix-validation]
complexity: 4
task_type: review
parent_review: TASK-REV-FPF1
feature_id: FEAT-FPF1
test_results:
  status: pending
  coverage: null
  last_run: null
review_results:
  mode: code-quality
  depth: standard
  score: 93
  findings_count: 10
  recommendations_count: 4
  decision: accept
  report_path: docs/reviews/TASK-REV-FRF1-review-report.md
  completed_at: 2026-03-31
---

# Task: Analyse test-fpf1-regression-fixes output (post FPF1 regression fixes)

## Description

Analyse the output of the pipeline run following the TASK-REV-FPF1 regression fixes:
- **Fix 1 (TASK-FPF1-001)**: Revert harmful prompt changes (BAD/GOOD examples, "do not think out loud")
- **Fix 2 (TASK-FPF1-002)**: Harden format gate with required-key validation (messages + metadata)
- **Fix 3 (TASK-FPF1-003)**: Decouple format correction retries from turn budget

The run log is at `docs/reviews/longer-runs/test-fpf1-regression-fixes.md`.

### Fixes Being Validated

| Fix | Task | Description |
|-----|------|-------------|
| Revert harmful prompt changes | TASK-FPF1-001 | Removed BAD/GOOD examples and "think out loud" from Player prompt |
| Harden format gate | TASK-FPF1-002 | Format gate now checks for messages + metadata keys, not just valid JSON |
| Decouple format retries | TASK-FPF1-003 | Format gate failures no longer consume Coach turn budget |

### Baselines

| Run | Acceptance | Review |
|-----|-----------|--------|
| test-run-after-params-fixes (ORIGINAL BASELINE) | 70/77 (90.9%) | TASK-REV-TPF1 |
| test-FPF1-fixes (REGRESSION) | 53/77 (68.8%) | TASK-REV-FPF1 |
| test-fpf1-regression-fixes (THIS RUN) | TBD | THIS TASK |

### Expected Outcomes (from IMPLEMENTATION-GUIDE.md)

| Metric | Regression Run | Expected After Fixes |
|--------|---------------|---------------------|
| Acceptance rate | 68.8% | >= 91% (baseline restore) |
| Format gate blocks | 68 | ~44 (baseline level) |
| Write validation fails | 22 | ~0 |
| Post-gen validation fails | 14 | ~4 (baseline level) |

## Scope

### Fix Validation — Prompt Revert (TASK-FPF1-001)
- [ ] Confirm BAD/GOOD examples are absent from Player prompt (check log for prompt text)
- [ ] Confirm "do not think out loud" instruction removed
- [ ] Count Player JSON extraction / format gate failures (compare to baseline: 44, regression: 68)
- [ ] Verify write validation failures reduced (compare to baseline: 0, regression: 22)
- [ ] Verify post-gen validation failures reduced (compare to baseline: 4, regression: 14)

### Fix Validation — Format Gate Hardening (TASK-FPF1-002)
- [ ] Confirm format gate checks for messages + metadata keys (look for new log messages)
- [ ] Count format gate rejections due to missing keys vs non-JSON
- [ ] Verify zero false positives (valid JSON with both keys never blocked)
- [ ] Check FORMAT ERROR feedback mentions both required top-level keys

### Fix Validation — Turn Budget Decoupling (TASK-FPF1-003)
- [ ] Confirm format retries don't count as Coach turns (check turn_complete events)
- [ ] Count targets where format retry + Coach accept = accepted (was rejected before)
- [ ] Verify total Coach turns per target <= max_turns (3)
- [ ] Check that format_retries are bounded (max_format_retries)

### Acceptance/Rejection Analysis
- [ ] Compare acceptance rate to both baselines (90.9% original, 68.8% regression)
- [ ] Analyse any rejected targets — root cause categorisation
- [ ] Check previously problematic categories:
  - Literary analysis (was 57.1% rejection in regression run)
  - Essay feedback — Literature (was 80.0% rejection)
  - Character analysis — An Inspector Calls (was 33.3%)
  - Character analysis — A Christmas Carol (was 40.0%)
- [ ] Check originally weak categories that improved in regression:
  - Language analysis — unseen poetry (was 25% in regression, 100% in baseline)
  - AO-specific guidance (was 50% in regression, 100% in baseline)

### Quality Analysis
- [ ] Score distribution across accepted examples
- [ ] Turn distribution (first-turn accept vs revisions)
- [ ] Check for post-generation validation catches (unclosed think blocks etc.)

### Token Efficiency
- [ ] Compare total token usage to baselines (original: 1,516,355, regression: 1,477,301)
- [ ] Calculate token savings from decoupled format retries
- [ ] Average tokens per accepted example (original: 21,662, regression: 27,874)

### Performance
- [ ] Average time per target (original baseline: 75.4s, regression: 76.6s)
- [ ] Any unusually slow targets

## Acceptance Criteria

- [ ] All three fixes validated with quantitative evidence
- [ ] Acceptance rate compared to BOTH baselines (90.9% and 68.8%)
- [ ] Regression fully reversed (acceptance >= 90%)
- [ ] Format gate hardening effectiveness quantified
- [ ] Turn budget decoupling effectiveness quantified
- [ ] Token efficiency compared to baselines
- [ ] Readiness assessment for 1,000-target production run updated
- [ ] Any new issues or regressions from the fixes documented

## Key Files

- Run log: `docs/reviews/longer-runs/test-fpf1-regression-fixes.md`
- Original baseline run: `docs/reviews/longer-runs/test-run-after-params-fixes.md`
- Regression run: `docs/reviews/longer-runs/test-FPF1-fixes.md`
- Original baseline review: `docs/reviews/TASK-REV-TPF1-review-report.md`
- Regression review: `docs/reviews/TASK-REV-FPF1-review-report.md`
- Fix 1 code: `prompts/player_prompts.py`
- Fix 2 code: `entrypoint/generation_loop.py` (format gate, ~lines 705-726)
- Fix 3 code: `entrypoint/generation_loop.py` (turn loop, ~lines 657-957)
- Fix specs: `tasks/backlog/fpf1-regression-fixes/`

## Implementation Notes

This is a review/analysis task. Use `/task-review TASK-REV-FRF1` to execute the analysis.
