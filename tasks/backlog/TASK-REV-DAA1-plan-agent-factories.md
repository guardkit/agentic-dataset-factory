---
id: TASK-REV-DAA1
title: "Plan: Agent Factories — Player and Coach"
status: completed
created: 2026-03-19T00:00:00Z
updated: 2026-03-19T00:00:00Z
priority: high
task_type: review
tags: [agent-factories, player, coach, create_deep_agent, adversarial-cooperation]
complexity: 6
decision_required: true
review_results:
  mode: decision
  depth: standard
  findings_count: 5
  recommendations_count: 3
  decision: implement
  approach: "Option C: Hybrid — Contract Signatures + Extracted Model Factory"
  feature_id: FEAT-5AC9
clarification:
  context_a:
    decisions:
      focus: all
      tradeoff: balanced
      concerns: [tool-access-asymmetry, goal-md-injection, modelconfig-validation]
  context_b:
    decisions:
      approach: option-c-hybrid
      execution: auto-detect
      testing: complexity-adaptive
test_results:
  status: pending
  coverage: null
  last_run: null
---

# Task: Plan: Agent Factories — Player and Coach

## Description

Analyse and plan the implementation of Player and Coach agent factory functions that delegate to `create_deep_agent`. This review covers role separation through tool access asymmetry (Player gets rag_retrieval and write_output; Coach gets none per D5), FilesystemBackend assignment (Player only), prompt injection from GOAL.md sections, memory injection via AGENTS.md, and ModelConfig validation including provider, model, endpoint, and temperature constraints.

## Context

- Feature spec: `features/agent-factories/agent-factories.feature` (35 BDD scenarios)
- Assumptions: `features/agent-factories/agent-factories_assumptions.yaml` (4 high-confidence)
- Summary: `features/agent-factories/agent-factories_summary.md`
- API contract: `docs/design/contracts/API-generation.md`
- Data model: `docs/design/models/DM-agent-config.md`

## Review Focus

- All aspects (comprehensive — architecture, technical, security, performance)
- Trade-off priority: Balanced
- Specific concerns:
  1. Tool access asymmetry enforcement (Player vs Coach tool lists)
  3. GOAL.md prompt injection wiring
  5. ModelConfig validation (provider, model, endpoint, temperature)

## Acceptance Criteria

- [x] Technical options analysed with pros/cons
- [x] Architecture implications assessed
- [x] Implementation breakdown with subtasks
- [x] Risk analysis completed
- [x] Dependencies identified

## Implementation Notes

This is a review task — use `/task-review TASK-REV-DAA1` for analysis.
