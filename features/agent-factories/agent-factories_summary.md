# Feature Spec Summary: Agent Factories — Player and Coach via create_deep_agent

**Stack**: python (pyproject.toml)
**Generated**: 2026-03-19T00:00:00Z
**Scenarios**: 35 total (11 smoke, 0 regression)
**Assumptions**: 4 total (4 high / 0 medium / 0 low confidence)
**Review required**: No

## Scope

This specification covers the Player and Coach agent factory functions that delegate to `create_deep_agent`. It verifies role separation through tool access asymmetry (Player gets rag_retrieval and write_output; Coach gets none per D5), FilesystemBackend assignment (Player only), prompt injection from GOAL.md sections, memory injection via AGENTS.md, and ModelConfig validation including provider, model, endpoint, and temperature constraints.

## Scenario Counts by Category

| Category | Count |
|----------|-------|
| Key examples (@key-example) | 9 |
| Boundary conditions (@boundary) | 6 |
| Negative cases (@negative) | 10 |
| Edge cases (@edge-case) | 12 |

## Deferred Items

None — all groups accepted.

## Open Assumptions (low confidence)

None — all assumptions are high confidence, derived from explicit API contracts.

## Integration with /feature-plan

This summary can be passed to `/feature-plan` as a context file:

    /feature-plan "Agent Factories — Player and Coach" --context features/agent-factories/agent-factories_summary.md
