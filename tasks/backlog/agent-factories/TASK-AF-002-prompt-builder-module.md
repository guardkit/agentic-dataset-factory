---
id: TASK-AF-002
title: Create prompt builder module
task_type: feature
parent_review: TASK-REV-DAA1
feature_id: FEAT-AF
wave: 1
implementation_mode: task-work
complexity: 4
dependencies: []
status: in_review
tags:
- prompts
- goal-md
- injection
- player
- coach
autobuild_state:
  current_turn: 1
  max_turns: 35
  worktree_path: /Users/richardwoollcott/Projects/appmilla_github/agentic-dataset-factory/.guardkit/worktrees/FEAT-5AC9
  base_branch: main
  started_at: '2026-03-20T22:47:21.306581'
  last_updated: '2026-03-20T22:58:22.059681'
  turns:
  - turn: 1
    decision: approve
    feedback: null
    timestamp: '2026-03-20T22:47:21.306581'
    player_summary: Implementation via task-work delegation
    player_success: true
    coach_success: true
---

# Task: Create prompt builder module

## Description

Create `prompts/player_prompts.py` and `prompts/coach_prompts.py` with base prompt constants and builder functions that inject GOAL.md sections into agent system prompts.

## Requirements

Based on `docs/design/contracts/API-generation.md`:

### Player Prompt Structure
- Base player prompt (role, instructions, tool usage guidance, output format)
- Injected from GOAL.md: Goal, System Prompt, Generation Guidelines, Output Schema, Metadata Schema, Layer Routing

### Coach Prompt Structure
- Base coach prompt (role, evaluation instructions, response format, scoring guidance)
- Injected from GOAL.md: Goal, Evaluation Criteria, Output Schema, Metadata Schema, Layer Routing

## Acceptance Criteria

- [ ] `prompts/player_prompts.py` contains `PLAYER_BASE_PROMPT` constant and `build_player_prompt(goal: GoalConfig) -> str`
- [ ] `prompts/coach_prompts.py` contains `COACH_BASE_PROMPT` constant and `build_coach_prompt(goal: GoalConfig) -> str`
- [ ] Builder functions validate all required GOAL.md sections are non-empty before concatenation
- [ ] Missing or empty required section raises an error indicating the prompt is incomplete
- [ ] Base prompt appears FIRST, GOAL.md content appended as clearly delimited domain context
- [ ] Coach prompt includes all evaluation criteria names for `criteria_met` validation
- [ ] GOAL.md content is treated as domain context, not directives (no instruction override)
- [ ] `prompts/__init__.py` created
- [ ] All modified files pass project-configured lint/format checks with zero errors

## BDD Scenario Coverage

From `features/agent-factories/agent-factories.feature`:
- Player prompt includes all 6 injected GOAL.md sections
- Coach prompt includes all 5 injected GOAL.md sections
- GOAL.md with prompt-like instructions does not override base prompt
- Player factory rejects a prompt with missing GOAL.md sections
- Coach prompt includes all evaluation criteria names for criteria_met validation

## Implementation Notes

The `GoalConfig` type comes from the Domain Config module (Feature 2). For now, define a minimal protocol or type hint that the prompt builders depend on. The full GoalConfig implementation will come from the domain-config feature.
