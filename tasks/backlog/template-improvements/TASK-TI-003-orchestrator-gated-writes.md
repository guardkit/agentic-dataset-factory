---
id: TASK-TI-003
title: Orchestrator-gated writes scaffold pattern
status: backlog
created: 2026-03-27T22:00:00Z
updated: 2026-03-27T22:00:00Z
priority: p0
tags: [template, orchestration, adversarial, base-template]
complexity: 5
parent_review: TASK-REV-TRF12
feature_id: FEAT-TI
wave: 1
implementation_mode: task-work
depends_on: []
test_results:
  status: pending
  coverage: null
  last_run: null
---

# Task: Orchestrator-Gated Writes Scaffold

## Description

Create a scaffold pattern for the `langchain-deepagents` base template that enforces the orchestrator-gated writes pattern. This prevents the Player from writing output before Coach evaluation, the single most architecturally significant bug pattern (TRF-005, TRF-006).

## What to Build

### 1. Tool Separation Contract
- Player tool list: domain-specific tools ONLY (e.g., rag_retrieval). NO write, NO filesystem.
- Coach/Evaluator tool list: EMPTY. Evaluation only, no side effects.
- Orchestrator: owns `write_output` call, invoked programmatically after acceptance.

### 2. Write Gate
- Orchestrator calls `write_output` ONLY after Coach returns acceptance verdict
- Retry cap: configurable, default 3 per target (TRF-006 lesson)
- On retry exhaustion: reject target with structured error, do NOT loop indefinitely

### 3. Scaffold Code
- `OrchestratorWriteGate` class with:
  - `attempt_write(example, max_retries=3)` — calls write with retry logic
  - `on_acceptance(coach_verdict, player_output)` — triggered by Coach acceptance
  - `on_rejection(coach_verdict, player_output)` — triggered by Coach rejection
  - `on_exhaustion(target, attempts)` — triggered when retries exceeded

### 4. Player Prompt Enforcement
- System prompt includes: "You MUST NOT call write_output. Return the example as response content."
- Assertion at factory: `"write_output" not in [t.name for t in player.tools]`

## Fixes Prevented

TRF-003, TRF-005, TRF-006, TRF-016

## Target Location

`scaffold/orchestrator_pattern.py` (in the template output)

## Acceptance Criteria

- [ ] Tool separation contract documented and enforced
- [ ] Write gate with configurable retry cap
- [ ] Player cannot call write_output (assertion at factory)
- [ ] Orchestrator-only write invocation after Coach acceptance
- [ ] Retry exhaustion handled gracefully (no infinite loops)
- [ ] Unit tests for all gate states (accept, reject, exhaust)
- [ ] Integration test showing full Player -> Coach -> Write flow

## Effort Estimate

1-2 days
