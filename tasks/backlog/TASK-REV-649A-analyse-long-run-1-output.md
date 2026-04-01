---
id: TASK-REV-649A
title: Analyse long run 1 output and training dataset
status: review_complete
created: 2026-03-30T00:00:00Z
updated: 2026-03-30T00:00:00Z
priority: high
tags: [review, analysis, training-data, quality]
complexity: 0
task_type: review
test_results:
  status: pending
  coverage: null
  last_run: null
review_results:
  mode: comprehensive
  depth: standard
  score: 72
  findings_count: 16
  recommendations_count: 15
  decision: implement
  report_path: docs/reviews/TASK-REV-649A-long-run-1-review-report.md
  completed_at: 2026-03-30T00:00:00Z
  implementation_feature: FEAT-LR1
  implementation_path: tasks/backlog/long-run-1-fixes/
---

# Task: Analyse long run 1 output and training dataset

## Description

Review and analyse the first longer run output captured in `docs/reviews/longer-runs/long_run_1.md` (~78k lines of logs) and the generated training dataset in `output/` (761 train examples, 166 rejected examples, plus RAG index).

## Scope

### Log Analysis (`docs/reviews/longer-runs/long_run_1.md`)
- [ ] Identify error patterns and failure modes across the run
- [ ] Quantify success/failure/revision rates per category and type
- [ ] Identify Coach rejection reasons and frequency
- [ ] Check for pipeline stalls, timeouts, or repeated failures
- [ ] Assess model (Qwen3.5-35B-A3B-FP8) behaviour patterns
- [ ] Identify any think-block compliance issues
- [ ] Review JSON parsing error frequency and causes

### Training Dataset Analysis (`output/train.jsonl`)
- [ ] Verify ShareGPT format compliance across all 761 examples
- [ ] Check metadata field validity (layer, type, ao, text, topic, grade_target, source, turns)
- [ ] Assess category/type distribution balance
- [ ] Check grade target distribution
- [ ] Verify think-block presence in all reasoning-type examples
- [ ] Sample quality review of generated content (accuracy, Socratic method, age-appropriateness)
- [ ] Check for duplicate or near-duplicate examples

### Rejected Dataset Analysis (`output/rejected.jsonl`)
- [ ] Categorise rejection reasons
- [ ] Identify systematic generation failures
- [ ] Assess whether rejected examples indicate fixable pipeline issues

### RAG Index Analysis (`output/rag_index/knowledge.jsonl`)
- [ ] Review knowledge-layer examples for accuracy
- [ ] Check coverage of curriculum topics

## Acceptance Criteria

- [ ] Quantitative summary of run metrics (success rate, revision rate, rejection rate)
- [ ] Category distribution analysis with identified gaps
- [ ] List of actionable pipeline improvements
- [ ] Quality assessment of a representative sample (min 20 examples)
- [ ] Recommendations for next run configuration changes

## Implementation Notes

This is a review/analysis task. Use `/task-review TASK-REV-649A` to execute the analysis.
