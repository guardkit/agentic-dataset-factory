---
id: TASK-REV-TFR1
title: Analyse test-fixes-run-1 output and guided_json crash
status: review_complete
created: 2026-03-31T00:00:00Z
updated: 2026-03-31T00:00:00Z
priority: critical
tags: [review, analysis, guided-json, vllm, pipeline-crash]
complexity: 4
task_type: review
parent_review: TASK-REV-649A
test_results:
  status: pending
  coverage: null
  last_run: null
review_results:
  mode: decision
  depth: comprehensive
  findings_count: 1
  recommendations_count: 3
  decision: implement
  report_path: docs/reviews/TASK-REV-TFR1-review-report.md
  implementation_task: TASK-LR1-012
---

# Task: Analyse test-fixes-run-1 output and guided_json crash

## Description

The first test batch run after implementing Wave 1 fixes from `tasks/backlog/long-run-1-fixes/` crashed after 1 target with:

```
Pipeline failed: AsyncCompletions.create() got an unexpected keyword argument 'guided_json'
```

Review the full log at `docs/reviews/longer-runs/test-fixes-run-1.md`, investigate the root cause thoroughly, and determine the correct fix for passing guided JSON constraints to vLLM via the OpenAI SDK.

## Scope

### Crash Analysis
- [ ] Review full log output (50 lines) to confirm the single failure point
- [ ] Confirm the Player's first target completed successfully before the Coach call failed
- [ ] Trace the code path from TASK-LR1-001 implementation to the failing SDK call

### Root Cause Investigation
- [ ] Identify exactly where `guided_json` is passed to the OpenAI SDK
- [ ] Research the correct vLLM API for structured output (extra_body? response_format? guided_decoding?)
- [ ] Check vLLM version on promaxgb10-41b1:8002 for supported structured output parameters
- [ ] Check OpenAI SDK version for supported parameters (response_format, etc.)
- [ ] Review vLLM documentation for guided decoding backend requirements
- [ ] Determine if `--guided-decoding-backend` needs to be set on the vLLM server

### Fix Validation
- [ ] Verify the proposed fix won't break non-vLLM providers (Anthropic API)
- [ ] Verify the CoachVerdict JSON schema is compatible with vLLM's guided decoding
- [ ] Consider whether `response_format` (OpenAI-native) vs `guided_json` (vLLM extension) is the right approach
- [ ] Check if other Wave 1 fixes (LR1-002 validation gate, LR1-003/004 prompt changes) are working correctly in the log

## Acceptance Criteria

- [ ] Root cause fully understood with evidence from code and documentation
- [ ] Recommended fix validated against vLLM and OpenAI SDK documentation
- [ ] Impact assessment on non-vLLM providers documented
- [ ] Clear implementation task created from findings

## Key Files

- Run log: `docs/reviews/longer-runs/test-fixes-run-1.md`
- Wave 1 task list: `tasks/backlog/long-run-1-fixes/`
- TASK-LR1-001 (guided_json implementation): `tasks/backlog/long-run-1-fixes/TASK-LR1-001-guided-json-coach.md`

## Implementation Notes

This is a review/analysis task. Use `/task-review TASK-REV-TFR1` to execute the analysis.
