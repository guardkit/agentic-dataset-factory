# Feature: DeepAgents Template Improvements

## Problem Statement

After 11 runs and 31 fixes across the agentic-dataset-factory pipeline, analysis shows that 84% of fixes (26/31) could have been prevented by better template scaffolding. The fixes cluster into 6 root cause categories: validation/schema gaps (29%), prompt engineering (23%), SDK/framework misunderstanding (19%), orchestration logic (13%), model-specific quirks (10%), and test/observability gaps (6%).

## Solution Approach

Two-template strategy:

1. **`langchain-deepagents`** (base template) — Enhanced with JsonExtractor, observability scaffold, factory tool allowlisting, model compatibility docs, and pre-flight validation
2. **`langchain-deepagents-adversarial`** (extends base) — Adds three-role scaffold (Orchestrator + Player + Coach), orchestrator-gated writes, Coach prompt template, canonical pipeline, domain configuration schema, configurable adversarial intensity, HITL hooks, and sprint contract negotiation

## Priority

- **P0 (Wave 1)**: Top 3 improvements — JsonExtractor + Prompt template + Gated writes (65% of fixes, 4-5 days)
- **P1 (Wave 2)**: Factory allowlisting + Validators + Observability + Model docs
- **P2 (Wave 3)**: Pre-flight validation script (`guardkit validate`)
- **P3 (Wave 4)**: Adversarial template scaffold and components

## Subtask Summary

| ID | Title | Wave | Method | Priority |
|----|-------|------|--------|----------|
| TASK-TI-001 | JsonExtractor class | 1 | task-work | P0 |
| TASK-TI-002 | Prompt engineering template | 1 | task-work | P0 |
| TASK-TI-003 | Orchestrator-gated writes scaffold | 1 | task-work | P0 |
| TASK-TI-004 | Factory tool allowlisting | 2 | task-work | P1 |
| TASK-TI-005 | Type-aware domain validator | 2 | task-work | P1 |
| TASK-TI-006 | Observability logging scaffold | 2 | direct | P1 |
| TASK-TI-007 | Model compatibility matrix | 2 | direct | P1 |
| TASK-TI-008 | Pre-flight validation script | 3 | task-work | P2 |
| TASK-TI-009 | Adversarial template scaffold | 4 | task-work | P3 |
| TASK-TI-010 | Three-role orchestrator scaffold | 4 | task-work | P3 |
| TASK-TI-011 | Canonical pipeline module | 4 | task-work | P3 |
| TASK-TI-012 | Domain configuration schema | 4 | task-work | P3 |
| TASK-TI-013 | Coach/Evaluator prompt template | 4 | task-work | P3 |
| TASK-TI-014 | Configurable adversarial intensity | 4 | task-work | P3 |
| TASK-TI-015 | HITL checkpoint hooks | 4 | task-work | P3 |
| TASK-TI-016 | Sprint contract negotiation | 4 | task-work | P3 |

## Provenance

- **Parent Review**: TASK-REV-TRF12
- **Feature ID**: FEAT-TI
- **Review Report**: `.claude/reviews/TASK-REV-TRF12-review-report.md`
