---
id: TASK-REV-D0A8
title: Analyse 2500-run-1 stall and advise course of action
status: review_complete
created: 2026-04-01T17:00:00Z
updated: 2026-04-01T17:00:00Z
priority: high
tags: [review, generation-run, stall-analysis, format-gate, qwen35]
task_type: review
decision_required: true
complexity: 5
review_results:
  mode: decision
  depth: standard
  score: N/A
  findings_count: 5
  recommendations_count: 4
  decision: implement
  report_path: docs/reviews/TASK-REV-D0A8-review-report.md
  completed_at: 2026-04-01T20:00:00Z
test_results:
  status: pending
  coverage: null
  last_run: null
---

# Task: Analyse 2500-run-1 stall and advise course of action

## Description

The 2500-target generation run (Qwen3.5-35B-A3B-FP8 on GB10) appears to have stalled at index 1405 of 2500. The run has been producing training examples but stopped making progress. This review task analyses both the application log (`2500-run-1.md`) and the vLLM Docker log (`2500-docker-run-1.md`) to determine root cause and recommend the best course of action.

## Source Files

- **Application log**: `docs/reviews/longer-runs/2500-run-1.md` (93,687 lines)
- **Docker/vLLM log**: `docs/reviews/longer-runs/2500-docker-run-1.md` (14,410 lines)

## Preliminary Findings (from task creation)

### Progress Summary
| Metric | Value |
|--------|-------|
| Target total | 2,500 |
| Targets started | 1,406 (index 0-1405) |
| Targets accepted | 1,342 (53.7% of 2,500) |
| Last checkpoint saved | index 1404 |
| Last target accepted | index 1403 |
| Coach decisions: accept | 1,409 |
| Coach decisions: revise | 107 |
| Pre-Coach format gate failures | 1,158 |

### Key Observations

1. **Format gate failures are very high (1,158)**: The Player model is frequently producing non-JSON output that fails the pre-Coach format gate. These failures trigger retry turns, significantly slowing throughput.

2. **Stall at index 1405**: The last log entry shows index 1405 receiving a format gate failure ("Player output is not valid JSON... Skipping Coach"), followed by a retry request being sent to vLLM, but the response was never logged — the application log ends mid-HTTP-request.

3. **vLLM engine went idle**: The Docker log shows the engine dropping to 0 running requests and 0 throughput at 16:37:20, suggesting either the client disconnected or the request completed but the application didn't process the response.

4. **Accept rate is high when format gate passes**: 1,409 accepts vs 107 revises from the Coach, suggesting content quality is good — the bottleneck is JSON formatting compliance.

5. **Model**: Qwen3.5-35B-A3B-FP8, 262K context, ~40 tok/s generation, prefix cache hit rate ~82.7%.

## Review Scope

1. **Root cause analysis**: Why did the run stall at index 1405? Was it an application crash, network issue, vLLM timeout, or something else?

2. **Format gate failure analysis**: Why are 1,158 out of ~2,800+ Player invocations failing JSON format validation? Is this a prompt issue, a model limitation (Qwen3.5 structured output compliance), or a parsing bug?

3. **Throughput assessment**: At the current rate (~40 tok/s, with high format-gate retry rate), estimate time to complete remaining 1,096 targets.

4. **Course of action recommendation**:
   - Can the run be resumed from checkpoint 1404?
   - Should the Player prompt be modified to reduce format gate failures before resuming?
   - Should structured output mode (xgrammar) be enforced on the vLLM side?
   - Is it worth switching to a different model or configuration?

## Acceptance Criteria

- [ ] Root cause of stall identified with evidence
- [ ] Format gate failure pattern characterised (is it specific categories/types that fail more?)
- [ ] Throughput and ETA estimated for remaining targets
- [ ] Clear recommendation: resume as-is, fix-then-resume, or restart with changes
- [ ] Any code changes needed are identified as follow-up implementation tasks

## Test Requirements

- N/A (review task)

## Implementation Notes

[Space for review findings]

## Test Execution Log

[Automatically populated by /task-work]
