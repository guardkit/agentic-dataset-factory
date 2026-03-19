# Feature Spec Summary: GOAL.md Parser and Strict Validation

**Stack**: python (pyproject.toml)
**Generated**: 2026-03-19T00:00:00Z
**Scenarios**: 36 total (10 smoke, 0 regression)
**Assumptions**: 4 total (1 high / 3 medium / 0 low confidence)
**Review required**: No

## Scope

The Domain Config module parses GOAL.md files — the central configuration artefact for each domain — into a validated GoalConfig dataclass. It enforces that all 9 required sections are present and well-formed, validates minimum lengths, table structures, JSON schemas, Python identifier constraints, and the 70% minimum reasoning split. Invalid configurations are rejected at startup with descriptive errors identifying every failing section.

## Scenario Counts by Category

| Category | Count |
|----------|-------|
| Key examples (@key-example) | 8 |
| Boundary conditions (@boundary) | 8 |
| Negative cases (@negative) | 12 |
| Edge cases (@edge-case) | 11 |

Note: The "Missing a required section" Scenario Outline expands to 9 individual scenarios (one per section). Total unique test paths: 36.

## Deferred Items

None — all groups accepted.

## Open Assumptions (low confidence)

None — all assumptions are high or medium confidence and have been confirmed.

## Integration with /feature-plan

This summary can be passed to `/feature-plan` as a context file:

    /feature-plan "GOAL.md Parser and Strict Validation" --context features/domain-config/domain-config_summary.md
