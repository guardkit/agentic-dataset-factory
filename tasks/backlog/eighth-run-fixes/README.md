# Eighth Run Fixes (FEAT-TRF8)

## Problem

Run 8 (post-TRF-020–023) achieved 0/1 accepted targets. Two interrelated root causes:

1. **vLLM `--reasoning-parser qwen3` strips think blocks** — The model generates `<think>` blocks but vLLM intercepts them, stripping them from `content` and placing them in `reasoning_content`. Training examples lose their required think blocks.

2. **Naive brace matching in JSON extraction** — The `_extract_json_object` brace counter doesn't track JSON string boundaries, failing when string values contain unbalanced `{` or `}`.

## Source

- Review: TASK-REV-TRF8
- Report: `.claude/reviews/TASK-REV-TRF8-review-report.md`
- Run log: `docs/reviews/second-run/qwen35-run-5.md`

## Tasks

| Task | Title | Priority | Wave | Mode |
|------|-------|----------|------|------|
| TASK-TRF-024 | Remove `--reasoning-parser qwen3` from vLLM launch script | P0 | 1 | direct |
| TASK-TRF-025 | JSON-string-aware brace matching in `_extract_json_object` | P0 | 1 | task-work |
| TASK-TRF-026 | Add `reasoning_content` fallback to `_extract_player_content` | P1 | 2 | task-work |
| TASK-TRF-027 | Coach prompt — verify think block presence | P2 | 2 | direct |
