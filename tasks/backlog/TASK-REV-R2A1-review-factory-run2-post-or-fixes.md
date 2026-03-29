---
id: TASK-REV-R2A1
title: Review factory-run2 output post TASK-OR-001 and TASK-OR-002 fixes
status: review_complete
review_mode: architectural
review_depth: comprehensive
review_results:
  score: 35
  findings_count: 6
  recommendations_count: 5
  decision: implement
  report_path: .claude/reviews/TASK-REV-R2A1-review-report.md
  completed_at: 2026-03-29T11:00:00Z
  implementation_tasks: [TASK-OR-006, TASK-OR-007]
  tasks_updated: [TASK-OR-004, TASK-OR-005, TASK-TI-004]
created: 2026-03-29T09:00:00Z
updated: 2026-03-29T09:00:00Z
priority: critical
tags: [pipeline, review, overnight-readiness, coach-retry, grade-distribution]
task_type: review
complexity: 5
parent_review: TASK-REV-7617
depends_on: [TASK-OR-001, TASK-OR-002]
test_results:
  status: pending
  coverage: null
  last_run: null
---

# Task: Review factory-run2 Output Post TASK-OR-001 and TASK-OR-002 Fixes

## Description

Analyse the pipeline output from `docs/reviews/longer-runs/factor-run2.md` — the first
run after implementing TASK-OR-001 (Coach retry with JSON reinforcement) and TASK-OR-002
(grade distribution in GOAL.md and orchestrator). Determine whether the fixes are working
correctly, identify any new issues, and recommend next steps for overnight readiness.

## Source Files

- `docs/reviews/longer-runs/factor-run2.md` (pipeline run log, 376 lines)
- `output/train.jsonl` (accepted examples from this run)
- `output/rejected.jsonl` (rejected examples from this run)

## Context from Parent Review

TASK-REV-7617 identified 6 findings from factory-run-1 and spawned 5 implementation tasks.
The two critical Wave 1 tasks were:

1. **TASK-OR-001** — Coach retry with JSON reinforcement on parse failure (completed, 35/35 tests passed)
2. **TASK-OR-002** — Grade distribution in GOAL.md and orchestrator (completed, 521/521 tests passed)

## Preliminary Observations from Run Log

### Pipeline Summary
- **Targets attempted**: 4 of 20 (pipeline crashed at index 3)
- **Accepted**: 3 (index 0, 1, 2 — all score 5)
- **Pipeline crash**: index 3 — Coach retry triggered but caused 400 Bad Request

### TASK-OR-001 Assessment (Coach Retry)
- **Detection working**: Coach JSON parse failure detected at index 3, turn 1
- **Retry triggered**: JSON reinforcement message correctly prepended
- **BUG — System message ordering**: The retry sends the reinforcement as a `system`
  message in the second position, but vLLM requires all system messages at the beginning.
  The retry message format is `[system (original), system (reinforcement), user]` but vLLM
  is rejecting with: `"System message must be at the beginning."` — this suggests the
  actual message ordering sent is `[system, user, system]` or similar
- **Error**: `400 Bad Request: System message must be at the beginning.`
- **Impact**: Pipeline crashes on first Coach retry — retry is non-functional

### TASK-OR-002 Assessment (Grade Distribution)
- Grade target parameter visible in player prompts (need to verify values)
- Only 3 accepted examples — insufficient sample to assess distribution
- Pipeline crashed before meaningful grade diversity could be evaluated

### Critical Issue
The pipeline crashed at index 3 (4th target) due to the Coach retry system message
ordering bug. This means:
1. The overnight run would crash on first Coach parse failure
2. The retry fix from TASK-OR-001 is worse than the original (which at least rejected
   and continued) — now it crashes the pipeline entirely

## Questions to Investigate

1. **Retry message ordering**: Is the reinforcement system message being placed after the
   user message? Trace the exact message array sent in the retry request.
2. **Grade targets**: Are the 3 accepted examples showing diverse grade targets from
   TASK-OR-002, or are they still all Grade 7?
3. **Token usage**: How do token counts compare to factory-run-1 for the same categories?
4. **Turn counts**: Are turn counts (2, 3, 2) reasonable for reasoning targets?
5. **Score distribution**: All 3 accepted examples scored 5 — is the Coach calibrated correctly?
6. **Error propagation**: The pipeline crash is unhandled — does the error handling from
   TASK-NRF-12C1 need extending to cover HTTP errors during retry?

## Acceptance Criteria

- [ ] TASK-OR-001 coach retry behaviour fully analysed with root cause of 400 error
- [ ] TASK-OR-002 grade distribution assessed (even with limited 3-example sample)
- [ ] Comparison to factory-run-1 metrics (acceptance rate, tokens, turns)
- [ ] Pipeline crash root cause documented with fix recommendation
- [ ] Severity assessment: can overnight run proceed, or is a fix required first?
- [ ] Clear next-steps: implementation tasks for any bugs found
- [ ] Regression check: are the 3 accepted examples quality comparable to run-1?

## Expected Outcomes

This review should produce:
1. A severity-rated finding for the retry message ordering bug
2. An assessment of whether TASK-OR-002 grade distribution is working
3. A recommendation on whether to fix the retry bug before overnight run
4. Any new implementation tasks needed (likely a fix for the message ordering)

## Test Requirements

- [ ] N/A — review task (no code changes)

## Implementation Notes

[Space for review findings and recommendations]

## Test Execution Log

[Automatically populated by /task-work]
