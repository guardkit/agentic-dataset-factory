# Feature: Coach Layer-Aware Criteria Routing

## Problem

The Coach evaluates all 6 criteria uniformly for every example, ignoring the layer-specific routing instruction in GOAL.md. This causes 63% rejection of knowledge/direct examples — primarily because `socratic_approach` (25% weight) is applied to factual content that by design does not use Socratic questioning.

## Root Cause

The routing prose in GOAL.md is discarded during `parse_table()` (which only extracts table rows). The constructed Coach prompt then contains three explicit "include ALL criteria" instructions and zero routing instructions. 0% compliance is the expected outcome.

## Solution: Code-Level Criteria Filtering (Approach A)

Filter `goal.evaluation_criteria` by target layer **before** building the Coach prompt, so the Coach only ever sees criteria applicable to the current example's layer.

## Parent Review

TASK-REV-CC01 — [Review Report](../../../docs/reviews/TASK-REV-CC01-coach-criteria-compliance-review.md)

## Subtasks

| Task | Title | Wave | Method | Est. |
|------|-------|------|--------|------|
| TASK-CR-001 | Add layer field to EvaluationCriterion + GOAL.md column mapping | 1 | task-work | 1h |
| TASK-CR-002 | Add layer-aware filtering to build_coach_prompt() | 1 | task-work | 2h |
| TASK-CR-003 | Wire target layer through generation_loop.py to Coach prompt | 2 | task-work | 1h |
| TASK-CR-004 | Update COACH_BASE_PROMPT wording to remove "ALL criteria" | 1 | direct | 30m |
| TASK-CR-005 | Track Coach refusal issue separately | — | manual | — |

## Execution Strategy

**Wave 1** (parallel): TASK-CR-001, TASK-CR-002, TASK-CR-004
**Wave 2** (depends on Wave 1): TASK-CR-003
**Separate**: TASK-CR-005 (different root cause)
