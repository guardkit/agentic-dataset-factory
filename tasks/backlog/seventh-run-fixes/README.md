# Seventh Run Fixes (FEAT-TRF7)

## Summary

Fixes identified in TASK-REV-TRF7 review of Run 7 (`docs/reviews/second-run/qwen35-run-4.md`).

Run 7 was the first run with correct Player-Coach architecture (Player: 1 tool, Coach: 0 tools). The pipeline completed all 3 turns and Coach produced meaningful verdicts (score 5/5 on turns 1-2). However, 0/1 targets were accepted due to JSON extraction failures caused by unclosed `<think>` tags.

## Tasks

| ID | Title | Priority | Wave | Status |
|----|-------|----------|------|--------|
| TASK-TRF-020 | Call normaliser before JSON extraction | Critical | 1 | Backlog |
| TASK-TRF-021 | Handle missing think close tags (EOF) | Critical | 1 | Backlog |
| TASK-TRF-022 | Set explicit max_tokens on models | High | 1 | Backlog |
| TASK-TRF-023 | Improve extraction failure logging | Medium | 2 | Backlog |

## Goal

Unblock the overnight production run (1,000 targets) by fixing the serialisation bugs that prevent accepted examples from being written to `train.jsonl`.
