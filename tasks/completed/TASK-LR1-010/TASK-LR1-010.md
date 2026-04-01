---
id: TASK-LR1-010
title: Clean defective entries from Long Run 1 training data
status: completed
created: 2026-03-30T00:00:00Z
updated: 2026-03-30T12:00:00Z
completed: 2026-03-30T12:30:00Z
completed_location: tasks/completed/TASK-LR1-010/
priority: high
tags: [data-cleaning, training-data, quality]
complexity: 3
parent_review: TASK-REV-649A
feature_id: FEAT-LR1
wave: 1
implementation_mode: task-work
dependencies: []
---

# Task: Clean defective entries from Long Run 1 training data

## Description

Long Run 1's `output/train.jsonl` contains 33 defective entries that need removal or repair before the dataset is used for fine-tuning.

## Defects

| Type | Count | Lines | Action |
|------|-------|-------|--------|
| Degenerate placeholder (`"..."` content) | 3 | 163, 164, 541 | Remove |
| Empty assistant response (think-block only) | 23 | Various | Remove |
| Unclosed `<think>` blocks | 7 | 42, 396, 416, 486, 491, 556, 574 | Repair (close tags) |

## Scope

- [x] Write a Python script to process `output/train.jsonl`:
  1. Remove entries where any message content is `"..."`
  2. Remove entries where assistant content (after stripping `<think>...</think>`) is empty/whitespace
  3. Fix unclosed `<think>` blocks using the same logic as `normalise_think_closing_tags()`
- [x] Output cleaned dataset to `output/train_cleaned.jsonl`
- [x] Log all modifications (line number, defect type, action taken)
- [x] Report final counts: removed, repaired, unchanged

## Acceptance Criteria

- [x] 3 degenerate entries removed
- [x] 13 empty-response entries removed (task estimated 23; actual count is 13)
- [x] 6 unclosed think-blocks repaired (task estimated 7; actual count is 6)
- [x] Cleaned dataset has 745 entries (761 - 16 removed)
- [x] Cleaning log output for audit trail (`output/cleaning_log.json`)
- [x] Original `train.jsonl` preserved (not overwritten)

## Implementation Notes

Actual defect counts differ from the review estimates:
- Empty assistant responses: 13 (not 23)
- Unclosed think blocks: 6 (not 7)
- No overlap between empty and unclosed categories
- Total removals: 16 (3 degenerate + 13 empty)

Script: `scripts/clean_training_data.py`
Tests: `tests/test_clean_training_data.py` (27 tests)
