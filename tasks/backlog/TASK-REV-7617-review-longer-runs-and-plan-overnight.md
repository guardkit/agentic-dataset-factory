---
id: TASK-REV-7617
title: Review longer runs and plan overnight batch
status: review_complete
review_results:
  mode: architectural
  depth: standard
  score: 62
  findings_count: 6
  recommendations_count: 5
  decision: implement
  report_path: .claude/reviews/TASK-REV-7617-review-report.md
  completed_at: 2026-03-28T09:30:00Z
created: 2026-03-28T09:00:00Z
updated: 2026-03-28T09:00:00Z
priority: high
tags: [pipeline, longer-runs, training-data, overnight-planning, review]
task_type: review
complexity: 5
test_results:
  status: pending
  coverage: null
  last_run: null
---

# Task: Review longer runs and plan overnight batch

## Description

Analyse the outputs from two longer runs:
- `docs/reviews/longer-runs/factory-run-1.md` — Full pipeline execution (20 targets)
- `docs/reviews/longer-runs/docker-run-1.md` — Docker vLLM container startup logs

Identify remaining issues, evaluate training data quality, and recommend next steps for a longer overnight production run.

## Source Files

- `docs/reviews/longer-runs/factory-run-1.md` (pipeline run log, 1405 lines)
- `docs/reviews/longer-runs/docker-run-1.md` (Docker/vLLM startup log, 400 lines)
- `output/train.jsonl` (13 accepted examples)
- `output/rejected.jsonl` (4 rejected examples)
- `output/rag_index/knowledge.jsonl` (3 knowledge entries)

## Initial Findings

### factory-run-1 Summary
- **Model**: Qwen/Qwen3.5-35B-A3B-FP8 on promaxgb10-41b1:8002
- **Results**: 16/20 accepted (80%), 4 rejected (20%)
- **Elapsed**: 2066s (34 min) for 20 targets
- **Tokens**: 334,370 total (~16.7K per target)
- **Turns**: 29 total across 20 targets (avg 1.45/target)
- **TASK-NRF-12C1 fix confirmed working**: 3 Coach JSON parsing failures were caught as rejections (not pipeline crashes)

### Rejection Breakdown
| Index | Category | Reason | Detail |
|-------|----------|--------|--------|
| 2 | Character analysis — An Inspector Calls | llm_failure | Coach returned prose instead of JSON |
| 3 | Character analysis — A Christmas Carol | max_turns | 3 turns, final score=1, metadata validation failures |
| 4 | Language analysis — poetry (Power & Conflict) | llm_failure | Coach returned prose instead of JSON |
| 11 | Comparative analysis — poetry | llm_failure | Coach returned prose instead of JSON |

**All 4 rejections were reasoning-type targets.** Direct type: 6/6 (100%).

### docker-run-1 Summary
- **Not a pipeline run** — Docker vLLM container startup logs only
- Confirms Qwen3.5-35B-A3B-FP8 model loads and serves correctly
- Generation throughput: ~35 tokens/s sustained
- Prefix cache hit rate: 0% → 65.3%
- Warnings: CUDA capability mismatch (informational), MoE config defaults, Mamba experimental support
- **No errors** — infrastructure is healthy

### Training Data Quality (output/train.jsonl)
- **13 accepted examples** across 8 topics
- **Type split**: 10 reasoning (76.9%), 3 direct (23.1%) — matches target 75/25
- **Think blocks**: 10/10 reasoning examples have `<think>` blocks (100%)
- **Grade target**: 12/13 are Grade 7 (92.3%) — needs more diversity
- **Turns**: 12 single-turn, 1 multi-turn — essay feedback should be multi-turn per GOAL.md

### Text Coverage Gaps
| Text | Examples | Target Count | Status |
|------|----------|-------------|--------|
| macbeth | 4 | 80 | Covered |
| general | 3 | — | Covered |
| language_paper_1 | 2 | — | Covered |
| language_paper_2 | 2 | — | Covered |
| an_inspector_calls | 1 | 80 | Partially covered (1 rejected) |
| unseen_poetry | 1 | 50 | Covered |
| a_christmas_carol | 0 | 60 | MISSING (1 rejected) |
| power_conflict_poetry | 0 | 60 | MISSING (1 rejected) |

### Knowledge Layer
- 3 entries in `output/rag_index/knowledge.jsonl` (terminology, exam technique, historical context)
- Sparse but correct structure

## Questions to Investigate

1. Is the 15% Coach JSON parsing failure rate acceptable for overnight runs, or does it need mitigation?
2. Why does Grade 7 dominate (92.3%)? Is the target distribution in GOAL.md specifying grade diversity?
3. Essay feedback examples should be multi-turn per GOAL.md but most are single-turn — is the Player ignoring this?
4. The 3 Coach role-confusion failures are all on reasoning targets — is the Player's Layer 1 `<think>` block length correlated?
5. At 34 min for 20 targets (each count=1), what's the projected runtime for 1000 targets at production counts?
6. Is the Docker environment (docker-run-1) the planned deployment for overnight runs, or direct execution?

## Acceptance Criteria

- [ ] All issues from both runs catalogued with severity
- [ ] Training data quality assessed against GOAL.md criteria
- [ ] Coach rejection rate evaluated (acceptable vs needs mitigation)
- [ ] Grade target diversity gap analysed
- [ ] Multi-turn essay feedback gap analysed
- [ ] Projected overnight runtime estimated
- [ ] Clear next-steps recommendation for overnight run configuration

## Test Requirements

- [ ] N/A — review task (no code changes)

## Implementation Notes

[Space for review findings and recommendations]

## Test Execution Log

[Automatically populated by /task-work]
