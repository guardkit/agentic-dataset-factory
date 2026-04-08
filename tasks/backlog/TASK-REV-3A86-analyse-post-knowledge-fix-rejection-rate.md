---
id: TASK-REV-3A86
title: Analyse post-knowledge-fix rejection rate increase
status: review_complete
created: 2026-04-05T17:30:00Z
updated: 2026-04-05T18:45:00Z
review_results:
  mode: architectural
  depth: standard
  score: null
  findings_count: 4
  recommendations_count: 4
  decision: implement
  report_path: docs/reviews/longer-runs/TASK-REV-3A86-post-knowledge-fix-rejection-analysis.md
priority: high
tags: [review, quality, rejection-rate, knowledge-fix, pipeline-analysis]
task_type: review
complexity: 5
test_results:
  status: pending
  coverage: null
  last_run: null
---

# Task: Analyse post-knowledge-fix rejection rate increase

## Description

Analyse the pipeline output logs from the run after the knowledge layer fix to investigate
a significantly higher rejection rate than previously observed. The run completed with
**984 accepted and 562 rejected out of 1546 targets (36.4% rejection rate)**.

Key metrics from the run:
- **Accepted**: 984 (63.6%)
- **Rejected**: 562 (36.4%)
- **Total turns**: 3,844 (avg ~2.49 turns per target)
- **Elapsed time**: 181,466s (~50.4 hours)
- **Total tokens**: 33,551,901 (prompt: 27,360,997 + completion: 6,190,904)

## Source Log

[tail-output-after-knowledge-fix.md](docs/reviews/longer-runs/tail-output-after-kownledge-fix.md)

## Review Objectives

1. **Compare rejection rates** against previous runs to quantify the increase
2. **Identify rejection patterns** — are rejections concentrated in specific layers, types, or index ranges?
3. **Analyse Coach verdict reasons** — what criteria are failing most often?
4. **Determine root cause** — did the knowledge layer fix introduce stricter acceptance criteria, change prompt wording, or alter the CoachVerdict schema in a way that increases rejections?
5. **Assess output quality** — are the accepted examples higher quality despite more rejections (i.e., is the Coach correctly filtering)?
6. **Recommend fixes** — if the rejection rate is unjustified, propose targeted changes to reduce it

## Acceptance Criteria

- [ ] Rejection rate comparison table across recent runs
- [ ] Breakdown of rejections by layer and type
- [ ] Top 5 most common blocking issues from Coach verdicts
- [ ] Root cause determination with evidence
- [ ] Recommendation: accept current rate OR propose specific fixes
- [ ] Review document written to `docs/reviews/longer-runs/`

## Implementation Notes

Review the following sources:
- Pipeline output logs in `docs/reviews/longer-runs/`
- Coach verdict schema (CoachVerdict model with acceptance rule)
- GOAL.md knowledge layer changes from the fix
- Previous run review documents for baseline comparison
- Checkpoint data and accepted/rejected example files in `output/`
