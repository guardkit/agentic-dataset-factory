---
id: TASK-REV-F479
title: "Plan: Ingestion Pipeline — Docling PDF Processing to ChromaDB"
status: review_complete
created: 2026-03-19T00:00:00Z
updated: 2026-03-19T00:00:00Z
priority: high
tags: [ingestion, docling, chromadb, pipeline, review]
task_type: review
complexity: 7
decision_required: true
clarification:
  context_a:
    timestamp: 2026-03-19T00:00:00Z
    decisions:
      focus: all
      depth: standard
      tradeoff: balanced
      extensibility: "yes"
review_results:
  mode: decision
  depth: standard
  findings_count: 6
  recommendations_count: 1
  decision: accepted
  recommended_approach: "Thin Orchestrator + Isolated Components"
  alternatives_considered:
    - "Single-File Pipeline"
    - "Pipeline Pattern (Step Chain)"
  implementation_tasks: 7
  implementation_waves: 4
test_results:
  status: pending
  coverage: null
  last_run: null
---

# Task: Plan: Ingestion Pipeline — Docling PDF Processing to ChromaDB

## Description

Review and plan the implementation of the ingestion pipeline (Stage 0) that converts source PDF documents into queryable chunks in ChromaDB. The pipeline reads file patterns and Docling modes from the GOAL.md Source Documents section, processes each document via Docling (standard or VLM mode), splits extracted text into fixed-size overlapping chunks, and indexes them with provenance metadata into a named ChromaDB collection.

## Context

- **Feature spec**: 31 BDD scenarios (8 smoke, 6 boundary, 9 negative, 11 edge case)
- **API contract**: `docs/design/contracts/API-ingestion.md`
- **Architecture**: Modular monolith, Stage 0 pipeline (ADR-ARCH-001, ADR-ARCH-002)
- **ChromaDB**: Embedded PersistentClient (ADR-ARCH-004)
- **Upstream dependency**: GOAL.md parser (TASK-REV-DC5D) for Source Documents section parsing
- **Assumptions**: 4 confirmed (3 high confidence, 1 low — concurrent access safety ASSUM-004)

## Key Technical Components

1. **GOAL.md Parser Integration** — Parse Source Documents table for file patterns and modes
2. **Docling Processing** — Standard and VLM mode document extraction
3. **Text Chunking** — Fixed-size (512 tokens) with overlap (64 tokens) via LangChain RecursiveCharacterTextSplitter
4. **ChromaDB Indexing** — PersistentClient, collection per domain, provenance metadata
5. **CLI Interface** — `python -m ingestion.ingest --domain <name> [--chunk-size] [--overlap] [--force]`
6. **Error Handling** — Per-document failure tolerance, structured error reporting

## Acceptance Criteria

- [ ] Technical options analysed with complexity and effort estimates
- [ ] Architecture implications reviewed against existing ADRs
- [ ] Risk analysis completed (Docling failures, ChromaDB availability, concurrent access)
- [ ] Implementation breakdown with task dependencies identified
- [ ] Recommended approach with justification provided

## Implementation Notes

This is a review/analysis task. Use `/task-review TASK-REV-F479` to execute the analysis.
