---
id: TASK-GG-005
title: "Write GOAL.md structural smoke tests for section presence, format, and split ratio"
task_type: testing
parent_review: TASK-REV-843F
feature_id: FEAT-GG
wave: 2
implementation_mode: task-work
complexity: 4
dependencies:
  - TASK-GG-002
  - TASK-GG-003
status: pending
estimated_minutes: 60
---

# Task: Write GOAL.md structural smoke tests

## Description

Create pytest tests that validate the structural integrity of the GCSE English GOAL.md file without depending on the parser module (FEAT-5606). These are lightweight smoke tests that verify the contract expectations from `docs/design/contracts/API-domain-config.md`.

Tests should cover:
1. All 9 required sections are present (## Goal, ## Source Documents, ## System Prompt, ## Generation Targets, ## Generation Guidelines, ## Evaluation Criteria, ## Output Schema, ## Metadata Schema, ## Layer Routing)
2. Source Documents table has correct columns and valid mode values
3. Generation Targets table sums to 1,000 total examples
4. Reasoning/direct split is 75/25 (>= 70% reasoning per validation rule)
5. System prompt is minimum 100 characters
6. Generation guidelines is minimum 100 characters
7. Output Schema contains valid JSON with `messages` and `metadata` keys
8. Evaluation criteria weights sum to 100% (within ±1% tolerance)
9. Layer Routing table contains `behaviour` and `knowledge` rows
10. No source document file pattern contains ".." (path traversal guard)

## Acceptance Criteria

- [ ] Test file created at `tests/test_goal_md_structure.py`
- [ ] Test verifies all 9 section headings are present
- [ ] Test verifies generation targets sum to exactly 1,000
- [ ] Test verifies reasoning percentage >= 70%
- [ ] Test verifies system prompt length >= 100 characters
- [ ] Test verifies generation guidelines length >= 100 characters
- [ ] Test verifies output schema is valid JSON with required keys
- [ ] Test verifies evaluation criteria weights sum to ~100% (±1%)
- [ ] Test verifies layer routing contains behaviour and knowledge entries
- [ ] Test verifies no path traversal in source document patterns
- [ ] All tests pass with `pytest tests/test_goal_md_structure.py -v`

## Implementation Notes

- Use simple string matching / regex to find `## Section Name` headings
- Parse tables by splitting on `|` and stripping whitespace
- Extract JSON from fenced code blocks with regex
- These tests are intentionally independent of the domain_config parser module
- They serve as a safety net that can run before the parser is implemented
