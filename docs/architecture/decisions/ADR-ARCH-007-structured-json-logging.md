# ADR-ARCH-007: Structured JSON Logging

**Status:** Accepted
**Date:** 2026-03-16
**Deciders:** ML Engineer + /system-arch session

## Context

The pipeline needs logging for operational visibility during overnight runs. Coach rejections already use structured JSON format (`{decision, score, issues, criteria_met, quality_assessment}`). We need to decide whether pipeline-level logging should be plain text or structured JSON.

## Decision

Use structured JSON logging throughout the pipeline for consistency with Coach rejection format.

## Alternatives Considered

| Alternative | Why Rejected |
|-------------|-------------|
| Plain text logging | Inconsistent with structured Coach rejection output; less queryable for post-run analysis |

## Consequences

- (+) Consistent format across all pipeline output (logs, rejections, traces)
- (+) Queryable — can filter/aggregate logs programmatically
- (+) Complements LangSmith traces with pipeline-level context
- (+) Progress tracking via structured log entries (e.g. `{"event": "example_generated", "count": 42, "total": 1000}`)
- (-) Slightly less human-readable in raw terminal output (mitigated by log formatting tools)
