---
id: TASK-CR-003
title: Wire target layer through generation_loop.py to Coach prompt
status: backlog
created: 2026-04-07T12:00:00Z
updated: 2026-04-07T12:00:00Z
priority: high
complexity: 3
tags: [criteria-routing, orchestrator, generation-loop]
parent_review: TASK-REV-CC01
feature_id: FEAT-CR
wave: 2
implementation_mode: task-work
dependencies: [TASK-CR-001, TASK-CR-002]
test_results:
  status: pending
  coverage: null
  last_run: null
---

# Task: Wire target layer through generation_loop.py to Coach prompt

## Description

The generation loop currently constructs a single Coach agent with one prompt at startup. After TASK-CR-002, the Coach prompt varies by layer. This task wires the target's `layer` metadata through to the Coach so it evaluates with the correct criteria set.

## Implementation Options

### Option A: Two Coach Agents (preferred)

Pre-build two Coach agents at startup — one for behaviour, one for knowledge. Select the correct agent per-target based on `target.layer`.

```python
coach_behaviour = create_coach(build_coach_prompt(goal, "behaviour"), ...)
coach_knowledge = create_coach(build_coach_prompt(goal, "knowledge"), ...)

# In the per-target loop:
coach = coach_knowledge if target.layer == "knowledge" else coach_behaviour
```

**Pros:** Clean separation, no per-target prompt rebuilding, prompt caching works.
**Cons:** Two agent instances in memory.

### Option B: Per-Target Prompt Injection

Rebuild the Coach prompt per-target. Less efficient but simpler if agent construction is lightweight.

### Expected interface

The generation loop should select the Coach agent/prompt based on `target.layer` where `target` is a `GenerationTarget` instance. The `layer` field already exists on `GenerationTarget` (values: "behaviour" or "knowledge").

## Files to Modify

- `entrypoint/generation_loop.py` — Coach agent creation + per-target selection

## Acceptance Criteria

- [ ] Knowledge-layer targets are evaluated by a Coach with only knowledge-applicable criteria
- [ ] Behaviour-layer targets are evaluated by a Coach with only behaviour-applicable criteria
- [ ] No regression in behaviour-layer acceptance rates
- [ ] Logging indicates which Coach variant is used per target
