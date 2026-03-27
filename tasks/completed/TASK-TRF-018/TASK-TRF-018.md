---
id: TASK-TRF-018
title: Add token usage logging from vLLM responses
status: completed
created: 2026-03-27T00:00:00Z
updated: 2026-03-27T00:00:00Z
completed: 2026-03-27T00:00:00Z
completed_location: tasks/completed/TASK-TRF-018/
priority: medium
tags: [improvement, logging, observability, sixth-run]
complexity: 2
parent_review: TASK-REV-TRF6
feature_id: FEAT-TRF6
wave: 2
implementation_mode: task-work
depends_on: []
test_results:
  status: passed
  coverage: null
  last_run: 2026-03-27
organized_files:
  - TASK-TRF-018.md
---

# Task: Add Token Usage Logging from vLLM Responses

## Description

Run 6 logged no `prompt_tokens` or `completion_tokens` data, making it impossible to assess token budget utilisation against the 262K context limit. Add usage stats extraction from vLLM/OpenAI-compatible API responses.

### Changes Required

After each LLM API call (Player and Coach), extract and log:
- `prompt_tokens`
- `completion_tokens`
- `total_tokens`

Log at INFO level in the structured JSON format used throughout the pipeline.

### Expected Log Output

```json
{"level": "INFO", "message": "llm_usage: role=player, turn=1, prompt_tokens=15234, completion_tokens=1823, total_tokens=17057"}
{"level": "INFO", "message": "llm_usage: role=coach, turn=1, prompt_tokens=8432, completion_tokens=512, total_tokens=8944"}
```

## Acceptance Criteria

- [x] Token usage logged for every Player LLM call
- [x] Token usage logged for every Coach LLM call
- [x] Log format matches existing structured JSON pattern
- [x] Peak prompt_tokens visible for token budget assessment

## Implementation Notes

**Already implemented** — this functionality was delivered as part of prior work (referenced as TASK-TRF-010 in test docstrings).

### Implementation Location

- **Extraction**: `entrypoint/generation_loop.py:_extract_token_usage()` (lines 351-390)
  - Supports `response_metadata.token_usage` (OpenAI/vLLM path)
  - Supports `usage_metadata` (LangChain native path)
  - Graceful fallback to `(0, 0)` when no usage data available
- **Accumulation**: `entrypoint/generation_loop.py:TokenUsage` dataclass (lines 55-72)
- **Per-call logging**: Player (lines 580-594), Coach (lines 615-629)
- **Per-target summaries**: `target_tokens:` log entries (lines 689-697, 711-719, 734-742)
- **Pipeline summary**: `pipeline_tokens:` log entry (lines 961-968)
- **Result propagation**: `GenerationResult.token_usage` field

### Test Coverage

5 tests in `entrypoint/tests/test_generation_loop.py::TestTokenUsageLogging`:
- `test_token_usage_logged_per_call` — verifies Player and Coach per-call logging
- `test_per_target_cumulative_tokens_logged` — verifies per-target cumulative totals
- `test_pipeline_summary_includes_total_tokens` — verifies pipeline-level summary
- `test_generation_result_includes_token_usage` — verifies GenerationResult contains cumulative stats
- `test_no_usage_data_gracefully_handled` — verifies graceful handling when no usage metadata

All 5 tests pass (0.08s).

## Context

Review report: `.claude/reviews/TASK-REV-TRF6-review-report.md` (R2)
