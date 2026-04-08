---
id: TASK-CR-002
title: Add layer-aware filtering to build_coach_prompt()
status: completed
created: 2026-04-07T12:00:00Z
updated: 2026-04-07T18:00:00Z
completed: 2026-04-07T18:00:00Z
priority: high
complexity: 4
tags: [criteria-routing, coach, prompt]
parent_review: TASK-REV-CC01
feature_id: FEAT-CR
wave: 1
implementation_mode: task-work
dependencies: [TASK-CR-001]
completed_location: tasks/completed/TASK-CR-002/
test_results:
  status: passed
  coverage: null
  last_run: 2026-04-07T18:00:00Z
  tests_total: 420
  tests_passed: 420
  tests_failed: 0
  new_tests_added: 10
---

# Task: Add layer-aware filtering to build_coach_prompt()

## Description

Modify `build_coach_prompt()` to accept a `target_layer` parameter and filter `goal.evaluation_criteria` to only include criteria applicable to that layer. This ensures the Coach only sees (and is instructed to evaluate) the criteria relevant to the current example's layer.

## Implementation Details

### 1. Add `target_layer` parameter to `build_coach_prompt()`

```python
def build_coach_prompt(goal: GoalConfig, target_layer: str = "behaviour") -> str:
```

### 2. Add filtering helper

```python
def _filter_criteria_for_layer(
    criteria: list, target_layer: str
) -> list:
    """Return only criteria applicable to the given layer."""
    return [c for c in criteria if c.layer in (target_layer, "all")]
```

### 3. Use filtered criteria in prompt construction

Replace:
```python
{_format_evaluation_criteria(goal.evaluation_criteria)}
```
With:
```python
applicable_criteria = _filter_criteria_for_layer(goal.evaluation_criteria, target_layer)
...
{_format_evaluation_criteria(applicable_criteria)}
```

### 4. Update `_format_evaluation_criteria()` "MUST include" instruction

The existing instruction lists ALL criteria names. After filtering, it should only list the applicable ones. This already works correctly because `_format_evaluation_criteria()` builds the name list from its input parameter — no change needed to this function.

### 5. Prompt caching consideration

Since `target_layer` changes the prompt text, consider caching both variants at startup rather than rebuilding per-target. Two prompts: `coach_prompt_behaviour` and `coach_prompt_knowledge`.

## Files to Modify

- `prompts/coach_prompts.py` — build_coach_prompt(), add _filter_criteria_for_layer()

## Acceptance Criteria

- [x] `build_coach_prompt(goal, "behaviour")` includes socratic_approach, ao_accuracy but NOT completeness
- [x] `build_coach_prompt(goal, "knowledge")` includes factual_accuracy, completeness but NOT socratic_approach, ao_accuracy
- [x] `build_coach_prompt(goal, "behaviour")` "MUST include" instruction lists only behaviour criteria
- [x] `build_coach_prompt(goal, "knowledge")` "MUST include" instruction lists only knowledge criteria
- [x] Default behaviour (no target_layer) is backwards-compatible (behaviour layer)
- [x] Unit tests for both layer variants

## Completion Summary

### Implementation
- `prompts/coach_prompts.py` — `_filter_criteria_for_layer()` helper and `target_layer` parameter on `build_coach_prompt()` were implemented as part of TASK-CR-001.
- Prompt now includes a "Target Layer" header informing the Coach which layer is being evaluated.

### Tests Added (10 new tests in `TestCoachLayerAwareFiltering`)
- `test_behaviour_layer_includes_behaviour_criteria`
- `test_behaviour_layer_excludes_knowledge_only_criteria`
- `test_knowledge_layer_includes_knowledge_criteria`
- `test_knowledge_layer_excludes_behaviour_only_criteria`
- `test_behaviour_layer_includes_all_layer_criteria`
- `test_knowledge_layer_includes_all_layer_criteria`
- `test_behaviour_must_include_lists_only_behaviour_criteria`
- `test_knowledge_must_include_lists_only_knowledge_criteria`
- `test_default_target_layer_is_behaviour`
- `test_filter_criteria_for_layer_helper`

### Test fixture updated
- Added `layer` values to all criteria in `valid_goal_config`
- Added `completeness` criterion with `layer="knowledge"`
- Updated `test_all_criteria_names_present` → `test_all_applicable_criteria_names_present` for layer-awareness
