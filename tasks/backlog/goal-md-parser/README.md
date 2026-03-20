# Feature: GOAL.md Parser and Strict Validation

> **Feature ID**: FEAT-5606
> **Review**: TASK-REV-DC5D
> **Status**: Planned
> **Complexity**: 5/10 (Medium)

## Problem Statement

The pipeline needs to parse GOAL.md files — the central configuration artefact for each domain — into a validated `GoalConfig` structure. All 9 required sections must be present and well-formed. Invalid configurations must be rejected at startup with descriptive errors identifying every failing section.

## Solution Approach

**Pydantic v2 Models + Regex Section Splitter**: Use Pydantic `BaseModel` for all data structures (consistent with existing `synthesis/validator.py`). Split GOAL.md into sections using a whitelist regex on the 9 known `## ` headings. Aggregate all validation errors into a single descriptive exception.

## Subtask Summary

| # | Task | Type | Complexity | Wave |
|---|------|------|-----------|------|
| 1 | [TASK-DC-001](TASK-DC-001-pydantic-models.md) — Pydantic models | declarative | 3 | 1 |
| 2 | [TASK-DC-002](TASK-DC-002-section-splitter.md) — Section splitter | feature | 4 | 2 |
| 3 | [TASK-DC-003](TASK-DC-003-table-json-parsers.md) — Table + JSON parsers | feature | 5 | 2 |
| 4 | [TASK-DC-004](TASK-DC-004-cross-section-validation.md) — Validation + error aggregation | feature | 5 | 3 |
| 5 | [TASK-DC-005](TASK-DC-005-public-api-integration-tests.md) — Public API + integration tests | testing | 4 | 3 |

## Execution Order

- **Wave 1**: TASK-DC-001 (foundation)
- **Wave 2**: TASK-DC-002 + TASK-DC-003 (parallel — independent concerns)
- **Wave 3**: TASK-DC-004 → TASK-DC-005 (sequential — validation then API)

## Context

- **Feature spec**: `features/domain-config/domain-config.feature` (36 BDD scenarios)
- **API contract**: `docs/design/contracts/API-domain-config.md`
- **Data model**: `docs/design/models/DM-goal-schema.md`
- **Assumptions**: `features/domain-config/domain-config_assumptions.yaml` (4 confirmed)
- **Implementation guide**: [IMPLEMENTATION-GUIDE.md](IMPLEMENTATION-GUIDE.md)
