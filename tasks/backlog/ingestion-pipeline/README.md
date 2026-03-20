# Ingestion Pipeline — Docling PDF Processing to ChromaDB

## Problem Statement

The dataset factory needs a one-time pre-processing step (Stage 0) that converts source PDF documents into queryable chunks in a vector store. Without this, the generation pipeline (Stage 1) has no curriculum content to retrieve during training example creation.

## Solution Approach

**Thin Orchestrator + Isolated Components** — each concern lives in its own module within `ingestion/`, with a central orchestrator calling them in sequence.

Architecture: `GOAL.md → File Resolution → Docling Extraction → Chunking → ChromaDB Indexing`

## Subtask Summary

| # | Task | Type | Complexity | Wave |
|---|------|------|-----------|------|
| 1 | [TASK-ING-001](TASK-ING-001-create-ingestion-package-and-models.md) — Package, models, errors | scaffolding | 3 | 1 |
| 2 | [TASK-ING-002](TASK-ING-002-implement-chunker.md) — Chunker (RecursiveCharacterTextSplitter) | feature | 4 | 1 |
| 3 | [TASK-ING-003](TASK-ING-003-implement-docling-processor.md) — Docling processor (standard + VLM) | feature | 5 | 2 |
| 4 | [TASK-ING-004](TASK-ING-004-implement-chromadb-indexer.md) — ChromaDB indexer (CRUD + batch) | feature | 5 | 2 |
| 5 | [TASK-ING-005](TASK-ING-005-implement-goal-reader.md) — GOAL.md Source Documents reader | feature | 3 | 2 |
| 6 | [TASK-ING-006](TASK-ING-006-implement-orchestrator-and-cli.md) — Orchestrator + CLI | feature | 5 | 3 |
| 7 | [TASK-ING-007](TASK-ING-007-integration-tests-bdd-smoke.md) — Integration tests (8 smoke scenarios) | testing | 5 | 4 |

**Total estimated effort:** 8-12 hours
**Review task:** [TASK-REV-F479](../../in_review/TASK-REV-F479-plan-ingestion-pipeline.md)

## Key References

- [API Contract](../../../docs/design/contracts/API-ingestion.md)
- [BDD Feature Spec](../../../features/ingestion-pipeline/ingestion-pipeline.feature) (31 scenarios)
- [Architecture](../../../docs/architecture/ARCHITECTURE.md)
- [ADR-ARCH-004: ChromaDB PersistentClient](../../../docs/architecture/decisions/ADR-ARCH-004-chromadb-embedded-persistent.md)
- [Upstream: GOAL.md Parser (FEAT-5606)](../goal-md-parser/)
