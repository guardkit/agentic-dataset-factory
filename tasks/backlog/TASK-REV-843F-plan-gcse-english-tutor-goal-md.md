---
id: TASK-REV-843F
title: "Plan: GCSE English Tutor GOAL.md — First Domain Configuration"
status: review_complete
created: 2026-03-19T00:00:00Z
updated: 2026-03-19T00:00:00Z
priority: high
task_type: review
tags: [domain-config, gcse-english, goal-md, planning]
complexity: 6
clarification:
  context_a:
    timestamp: 2026-03-19T00:00:00Z
    decisions:
      focus: all
      depth: standard
      tradeoff: balanced
      concerns: none
      extensibility: default
review_results:
  mode: decision
  depth: standard
  findings_count: 3
  recommendations_count: 1
  decision: implement
  recommended_approach: "Authoring-Only — Write GOAL.md + Validation Tests"
  alternatives_considered:
    - "GOAL.md + Parser Together"
    - "Template-Driven Generation"
  implementation_tasks: 5
  implementation_waves: 2
  feature_id: FEAT-GG
test_results:
  status: pending
  coverage: null
  last_run: null
---

# Task: Plan: GCSE English Tutor GOAL.md — First Domain Configuration

## Description

Plan the implementation of the concrete GCSE English tutor GOAL.md — the first real domain configuration for the Agentic Dataset Factory. This review analyses technical options for creating a GOAL.md that validates all 9 sections against the GCSE English curriculum requirements (AQA specification, Socratic tutoring, ShareGPT format, Nemotron 3 Nano 75/25 reasoning split), ensures metadata fields use curriculum-appropriate valid values (set texts, assessment objectives, grade targets), and verifies layer routing, evaluation criteria, and generation target composition for a 1,000-example dataset.

## Context

- Feature spec: features/gcse-goal-md/gcse-goal-md.feature (38 BDD scenarios)
- GoalConfig schema: docs/design/models/DM-goal-schema.md
- Domain Config contract: docs/design/contracts/API-domain-config.md
- Architecture: docs/architecture/ARCHITECTURE.md

## Acceptance Criteria

- [ ] Technical options analysis for GOAL.md creation approach
- [ ] Risk assessment for curriculum alignment
- [ ] Implementation breakdown with subtasks
- [ ] Validation strategy for all 9 GOAL.md sections

## Implementation Notes

[Space for review findings]
