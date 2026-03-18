# ADR-ARCH-004: ChromaDB Embedded PersistentClient for Generation

**Status:** Accepted
**Date:** 2026-03-16
**Deciders:** ML Engineer + /system-arch session

## Context

The pipeline needs a vector store for RAG retrieval during training example generation. ChromaDB was selected (D9) for privacy and no cloud dependency. There are two distinct ChromaDB use cases:

1. **Generation pipeline (this repo):** Temporary per domain, rebuilt from Docling on each ingestion run. Single process access.
2. **Inference-time RAG (consuming project):** Long-lived, multi-consumer (Reachy robot, mobile app), must survive restarts.

## Decision

Use ChromaDB embedded `PersistentClient` for the generation pipeline. The inference-time ChromaDB is the consuming project's concern — this repo outputs `knowledge.jsonl` for downstream seeding.

## Alternatives Considered

| Alternative | Why Rejected |
|-------------|-------------|
| ChromaDB server (standalone HTTP) | Unnecessary — no concurrent access during generation; extra process to manage |
| ChromaDB in separate Docker container | Overkill — ingestion and generation don't run concurrently |
| Embedded non-persistent Client | Data would be lost on process restart; PersistentClient survives restarts at no extra cost |

## Consequences

- (+) Zero ops — no port conflicts, no extra processes
- (+) Fastest reads — in-process, no network overhead
- (+) Data persists to disk, survives process restarts
- (+) Clean separation — this repo generates knowledge.jsonl, consuming project handles inference-time RAG
- (-) No concurrent access from other tools (acceptable for batch pipeline)
- (-) Data directory must be managed (included in start-fresh restart strategy)
