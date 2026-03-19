# Feature Spec Summary: Ingestion Pipeline — Docling PDF Processing to ChromaDB

**Stack**: python (pyproject.toml)
**Generated**: 2026-03-19T00:00:00Z
**Scenarios**: 31 total (8 smoke, 0 regression)
**Assumptions**: 4 total (3 high / 0 medium / 1 low confidence)
**Review required**: Yes

## Scope

The ingestion pipeline is a one-time pre-processing step per domain that converts source PDF documents into queryable chunks in ChromaDB. It reads file patterns and Docling modes from the GOAL.md Source Documents section, processes each document via Docling (standard or VLM mode), splits extracted text into fixed-size overlapping chunks, and indexes them with provenance metadata into a named ChromaDB collection. The pipeline supports force re-ingestion, custom chunk sizing, and graceful handling of individual document failures.

## Scenario Counts by Category

| Category | Count |
|----------|-------|
| Key examples (@key-example) | 7 |
| Boundary conditions (@boundary) | 6 |
| Negative cases (@negative) | 9 |
| Edge cases (@edge-case) | 11 |

Note: Some scenarios carry multiple tags (e.g. @edge-case @negative). Total unique scenarios: 31.

## Deferred Items

None — all groups accepted.

## Open Assumptions (low confidence)

- **ASSUM-004**: Re-ingestion with force is not safe during concurrent reads. Operator must ensure no generation pipeline is running during re-ingestion. ChromaDB delete+create is not atomic and no locking mechanism is specified.

## Integration with /feature-plan

This summary can be passed to `/feature-plan` as a context file:

    /feature-plan "Ingestion Pipeline — Docling PDF Processing to ChromaDB" --context features/ingestion-pipeline/ingestion-pipeline_summary.md
