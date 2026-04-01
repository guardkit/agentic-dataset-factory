---
id: TASK-OR-003
title: Domain-level structural validation rules from GOAL.md
status: backlog
created: 2026-03-29T00:00:00Z
updated: 2026-03-29T00:00:00Z
priority: high
tags: [validation, goal-md, multi-turn, metadata, overnight-readiness]
task_type: implementation
complexity: 6
parent_review: TASK-REV-7617
feature_id: FEAT-OR
depends_on: []
wave: 2
implementation_mode: task-work
test_results:
  status: pending
  coverage: null
  last_run: null
---

# Task: Domain-Level Structural Validation Rules from GOAL.md

## Problem

Two structural issues slip past the Coach:

1. **F3**: Essay feedback examples should be multi-turn (turns >= 2) per GOAL.md, but
   1/2 essay feedback examples was single-turn and the Coach accepted it at score 4+.

2. **F5**: Player omits `metadata` key from JSON response, consuming all 3 max_turns
   with Coach revise loops before the structural problem is caught.

## Solution

Add a configurable validation layer parsed from a new GOAL.md section, enforced
**before** sending to the Coach. This catches structural failures early, saves
Coach LLM calls, and provides clear feedback for the Player to fix on retry.

## Implementation

### 1. Add Structural Validation Rules Section to GOAL.md

```markdown
## Structural Validation Rules

Rules applied by the orchestrator before Coach evaluation. Violations trigger
auto-revise feedback to the Player without consuming a Coach turn.

| Rule | Condition | Requirement | Error Message |
|------|-----------|-------------|---------------|
| multi_turn_essay | topic in [essay_feedback] | turns >= 2 | "Essay feedback must have at least 2 exchange rounds per Generation Guidelines" |
| think_block_reasoning | type == reasoning | assistant content starts with <think> | "Reasoning examples must include <think> block per Generation Guidelines" |
| no_think_block_direct | type == direct | assistant content does NOT contain <think> | "Direct examples must not include <think> block" |
| metadata_present | always | "metadata" key exists in top-level JSON | "Response must include metadata object per Output Schema" |
| messages_present | always | "messages" key exists with >= 2 entries | "Response must include messages array with system + user + assistant" |
```

### 2. Create ValidationRule Model

```python
class StructuralRule(BaseModel):
    name: str
    condition: str  # Evaluated against target metadata
    requirement: str  # Evaluated against the parsed example
    error_message: str
```

### 3. Parse Rules from GOAL.md

Read the Structural Validation Rules table from GOAL.md at pipeline startup.
Store as a list of `StructuralRule` objects.

### 4. Validate Before Coach

In the generation loop, after Player output is extracted and parsed as JSON,
but before invoking the Coach:

```python
violations = validate_structural_rules(parsed_example, target, rules)
if violations:
    # Build synthetic "revise" verdict with specific feedback
    # Does NOT count as a Coach turn (saves tokens)
    # Player gets another attempt with clear error message
```

### 5. Handle Validation Failures

When structural validation fails:
- Log the violation at INFO level
- Construct a feedback message listing all violations
- Feed back to Player as if Coach said "revise" with score=1
- This consumes a Player-Coach turn but does NOT invoke the Coach LLM

## Files to Modify

- `domains/gcse-english-tutor/GOAL.md` — Add Structural Validation Rules section
- New file: `domain_config/structural_rules.py` — StructuralRule model + parser
- New file: `entrypoint/structural_validator.py` — Validation logic
- `entrypoint/generation_loop.py` — Insert validation step before Coach invocation

## Acceptance Criteria

- [ ] GOAL.md has Structural Validation Rules section with 5 initial rules
- [ ] Rules parsed at pipeline startup and validated
- [ ] Structural validation runs before Coach invocation
- [ ] Violations produce clear error messages fed back to Player
- [ ] Failed structural validation does NOT consume a Coach LLM call
- [ ] multi_turn_essay rule catches single-turn essay feedback examples
- [ ] metadata_present rule catches missing metadata before Coach sees it
- [ ] think_block_reasoning rule catches missing <think> blocks
- [ ] Existing tests pass (no regressions)

## Test Requirements

- Unit test: parse rules from GOAL.md table format
- Unit test: multi_turn_essay rule triggers on turns=1, essay_feedback topic
- Unit test: multi_turn_essay rule passes on turns=2, essay_feedback topic
- Unit test: metadata_present catches missing metadata key
- Unit test: think_block_reasoning catches missing <think> in reasoning example
- Unit test: no_think_block_direct catches <think> in direct example
- Integration: validation runs before Coach and saves LLM call
