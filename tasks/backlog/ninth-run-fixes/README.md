# Ninth Run Fixes (FEAT-TRF9)

## Problem

Run 9 achieved the pipeline's first successful JSON extraction (Turn 3: 3069 chars from 4514). But `write_output` validation rejected it with `metadata.turns value '1' not in valid values` — a parser bug where range notation (`1+`) is treated as an enumeration.

Secondary issues: no `<think>` blocks in generated examples, and JSON with literal newlines in strings failing extraction on earlier turns.

## Source

- Review: TASK-REV-TRF9
- Report: `.claude/reviews/TASK-REV-TRF9-review-report.md`
- Run log: `docs/reviews/second-run/qwen35-run-6.md`

## Tasks

| Task | Title | Priority | Wave | Mode |
|------|-------|----------|------|------|
| TASK-TRF-028 | Add range notation detection to `_coerce_valid_values` | P0 | 1 | task-work |
| TASK-TRF-029 | Add explicit `<think>` block instruction to Player prompt | P0 | 1 | direct |
| TASK-TRF-030 | JSON string repair for literal newlines | P1 | 2 | task-work |
