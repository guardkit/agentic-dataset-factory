# FPF1 Regression Fixes

## Problem

The test-FPF1-fixes run regressed acceptance from 90.9% to 68.8% (-22.1pp).
Root cause: prompt changes (BAD/GOOD examples, "do not think out loud") caused the
Player to produce worse output in every dimension — more non-JSON (44 → 68), a new
failure mode of JSON without metadata (0 → 22 write validation failures), and more
unclosed think blocks (4 → 14).

## Parent Review

- Review: TASK-REV-FPF1
- Report: `docs/reviews/TASK-REV-FPF1-review-report.md`
- Baseline: TASK-REV-TPF1 (90.9% acceptance)

## Solution Approach

1. Revert the harmful prompt changes (restore baseline behavior)
2. Harden the format gate to catch incomplete JSON early
3. Decouple format correction from the turn budget

## Subtasks

| Task | Wave | Description | Method |
|------|------|-------------|--------|
| TASK-FPF1-001 | 1 | Revert harmful prompt changes | task-work |
| TASK-FPF1-002 | 1 | Harden format gate with key validation | task-work |
| TASK-FPF1-003 | 2 | Decouple format retries from turn budget | task-work |

## Execution Strategy

Wave 1 (TASK-FPF1-001 + 002) can run in parallel — they touch different files.
Wave 2 (TASK-FPF1-003) depends on Wave 1 completion.
