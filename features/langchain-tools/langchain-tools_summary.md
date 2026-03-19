# Feature Spec Summary: LangChain Tools — RAG Retrieval and Write Output with Layer Routing

**Stack**: python (pyproject.toml)
**Generated**: 2026-03-19T00:00:00Z
**Scenarios**: 41 total (10 smoke, 0 regression)
**Assumptions**: 3 total (2 high / 0 medium / 1 low confidence)
**Review required**: Yes

## Scope

This specification covers the two LangChain `@tool` decorated functions used exclusively by the Player agent: `rag_retrieval` (retrieves curriculum chunks from ChromaDB) and `write_output` (validates and persists training examples with layer-based routing to behaviour or knowledge output files). It also covers the factory pattern for tool creation, the tool assignment invariant (Player gets both tools, Coach gets none), and the error-string-only contract (D7).

## Scenario Counts by Category

| Category | Count |
|----------|-------|
| Key examples (@key-example) | 8 |
| Boundary conditions (@boundary) | 8 |
| Negative cases (@negative) | 14 |
| Edge cases (@edge-case) | 13 |

## Deferred Items

None — all groups accepted.

## Open Assumptions (low confidence)

- **ASSUM-003**: Large content threshold is 100KB — no explicit limit in API contract; used as edge case threshold for testing very large assistant content.

## Integration with /feature-plan

This summary can be passed to `/feature-plan` as a context file:

    /feature-plan "LangChain Tools — RAG Retrieval and Write Output" --context features/langchain-tools/langchain-tools_summary.md
