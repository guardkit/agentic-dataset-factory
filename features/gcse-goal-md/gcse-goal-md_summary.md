# Feature Spec Summary: GCSE English Tutor GOAL.md — First Domain Configuration

**Stack**: python (pyproject.toml)
**Generated**: 2026-03-19T00:00:00Z
**Scenarios**: 38 total (10 smoke, 0 regression)
**Assumptions**: 5 total (2 high / 3 medium / 0 low confidence)
**Review required**: No

## Scope

This specification covers the concrete GCSE English tutor GOAL.md — the first real domain configuration for the Agentic Dataset Factory. It validates all 9 GOAL.md sections against the GCSE English curriculum requirements (AQA specification, Socratic tutoring, ShareGPT format, Nemotron 3 Nano 75/25 reasoning split), ensures metadata fields use curriculum-appropriate valid values (set texts, assessment objectives, grade targets), and verifies layer routing, evaluation criteria, and generation target composition for a 1,000-example dataset.

## Scenario Counts by Category

| Category | Count |
|----------|-------|
| Key examples (@key-example) | 10 |
| Boundary conditions (@boundary) | 8 |
| Negative cases (@negative) | 8 |
| Edge cases (@edge-case) | 12 |

## Deferred Items

None — all groups accepted.

## Open Assumptions (low confidence)

None — all assumptions resolved at medium or high confidence.

## Integration with /feature-plan

This summary can be passed to `/feature-plan` as a context file:

    /feature-plan "GCSE English Tutor GOAL.md — First Domain Configuration" --context features/gcse-goal-md/gcse-goal-md_summary.md
