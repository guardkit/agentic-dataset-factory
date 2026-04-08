# Implementation Guide: Coach Layer-Aware Criteria Routing

## Overview

Fix the Coach's 0% compliance with layer-specific criteria routing by filtering evaluation criteria at the code level before constructing the Coach prompt.

## Wave Breakdown

### Wave 1 (Parallel — 3 tasks)

These three tasks can be developed in parallel as they touch different files:

| Task | Files | Method |
|------|-------|--------|
| TASK-CR-001: Add layer to criterion model | models.py, parser.py, GOAL.md | task-work |
| TASK-CR-002: Layer-aware build_coach_prompt() | coach_prompts.py | task-work |
| TASK-CR-004: Update base prompt wording | coach_prompts.py (constant only) | direct |

**Note:** TASK-CR-002 and TASK-CR-004 both touch `coach_prompts.py` — CR-004 modifies the `COACH_BASE_PROMPT` constant while CR-002 modifies the `build_coach_prompt()` function. Merge carefully.

### Wave 2 (Sequential — 1 task)

| Task | Depends On | Files | Method |
|------|------------|-------|--------|
| TASK-CR-003: Wire layer through generation loop | CR-001, CR-002 | generation_loop.py | task-work |

### Separate Track

| Task | Notes |
|------|-------|
| TASK-CR-005: Coach refusal investigation | Different root cause; research task |

## Expected Impact

- Knowledge/direct rejection rate: ~63% -> ~20-25% (removing socratic_approach as blocking)
- Behaviour/reasoning rejection rate: unchanged (~12%)
- Overall rejection rate: ~36% -> ~15-18% (back to baseline)

## Verification

After implementation, a new pipeline run is required. Cannot be applied post-hoc.

Expected verification:
1. Unit tests: `build_coach_prompt(goal, "knowledge")` excludes socratic_approach
2. Unit tests: `build_coach_prompt(goal, "behaviour")` excludes completeness
3. Integration: Run 20-target test with mixed layers, verify Coach verdicts use correct criteria
4. Full run: Compare rejection rates against baseline
