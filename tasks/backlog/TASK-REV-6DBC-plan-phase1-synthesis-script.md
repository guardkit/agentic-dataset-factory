---
id: TASK-REV-6DBC
title: "Plan: Phase 1 synthesis script — generate GCSE training examples"
status: completed
created: 2026-03-17T00:00:00Z
updated: 2026-03-17T00:00:00Z
priority: high
tags: [synthesis, phase1, gcse, planning]
task_type: review
complexity: 6
review_results:
  mode: decision
  depth: standard
  decision: implement
  feature_id: FEAT-6A8C
  subtasks_created: 5
test_results:
  status: pending
  coverage: null
  last_run: null
---

# Task: Plan: Phase 1 synthesis script — generate GCSE training examples

## Description

Review and analyse the technical options for implementing the Phase 1 synthesis script that generates GCSE English tutoring training examples by calling the Claude API. The script must:

- Load generation targets from `domains/gcse-english-tutor/generation-plan.yaml`
- Call Claude API (claude-sonnet-4-5) with appropriate prompt templates (reasoning vs direct, single-turn vs multi-turn)
- Validate output against ShareGPT schema with metadata
- Enforce 75/25 reasoning/direct split
- Route examples by layer (behaviour → train.jsonl, knowledge → rag_index/knowledge.jsonl)
- Handle errors, rate limits, and resumption
- Log progress as structured JSON

## Context

- Feature spec: `features/gcse-training-synthesis/gcse-training-synthesis.feature` (28 scenarios)
- Pipeline plan: `docs/research/training-pipeline-plan.md`
- Target structure: `synthesis/` directory (synthesise.py, templates.py, validator.py)
- Assumptions: 5 confirmed (see `features/gcse-training-synthesis/gcse-training-synthesis_assumptions.yaml`)

## Acceptance Criteria

- [ ] Technical options analysed for module decomposition
- [ ] Architecture alignment with Phase 1/Phase 2 isolation verified
- [ ] Error handling and resumption strategy defined
- [ ] Implementation subtasks identified with complexity estimates

## Implementation Notes

This is a review/planning task. Use `/task-review` for analysis.
