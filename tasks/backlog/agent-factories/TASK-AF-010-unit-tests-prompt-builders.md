---
id: TASK-AF-010
title: Unit tests for prompt builders
task_type: testing
parent_review: TASK-REV-DAA1
feature_id: FEAT-AF
wave: 2
implementation_mode: task-work
complexity: 3
dependencies:
- TASK-AF-002
status: in_review
tags:
- testing
- prompts
- goal-md
- injection
- criteria-met
autobuild_state:
  current_turn: 1
  max_turns: 35
  worktree_path: /Users/richardwoollcott/Projects/appmilla_github/agentic-dataset-factory/.guardkit/worktrees/FEAT-5AC9
  base_branch: main
  started_at: '2026-03-20T22:58:25.795048'
  last_updated: '2026-03-20T23:05:26.037315'
  turns:
  - turn: 1
    decision: approve
    feedback: null
    timestamp: '2026-03-20T22:58:25.795048'
    player_summary: Implementation via task-work delegation
    player_success: true
    coach_success: true
---

# Task: Unit tests for prompt builders

## Description

Write unit tests for the prompt builder module verifying GOAL.md section injection, missing section error handling, and base prompt precedence.

## Test Cases

### Player Prompt
- Built prompt contains base player instructions
- Built prompt contains all 6 injected GOAL.md sections (Goal, System Prompt, Generation Guidelines, Output Schema, Metadata Schema, Layer Routing)
- Base prompt appears before GOAL.md content
- Missing Generation Guidelines section → error raised
- GOAL.md content with prompt-like instructions does not override base prompt

### Coach Prompt
- Built prompt contains base coach instructions
- Built prompt contains all 5 injected GOAL.md sections (Goal, Evaluation Criteria, Output Schema, Metadata Schema, Layer Routing)
- All 5 evaluation criteria names are present in the prompt
- Base prompt appears before GOAL.md content
- Missing Evaluation Criteria section → error raised

### Edge Cases
- Partial GOAL.md parse (missing section) → error, not silent degradation
- Memory content supplements but does not replace system prompt

## Acceptance Criteria

- [ ] Player prompt tests verify all 6 GOAL.md sections are present
- [ ] Coach prompt tests verify all 5 GOAL.md sections are present
- [ ] Tests verify base prompt appears before injected content
- [ ] Tests verify missing section raises error
- [ ] Tests verify evaluation criteria names are present for criteria_met alignment
- [ ] Tests are in `tests/test_prompt_builders.py`

## Implementation Notes

Use mock GoalConfig objects with known section content to verify injection.
