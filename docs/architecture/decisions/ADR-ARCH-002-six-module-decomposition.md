# ADR-ARCH-002: Six-Module Decomposition

**Status:** Accepted
**Date:** 2026-03-16
**Deciders:** ML Engineer + /system-arch session

## Context

The system is a modular monolith needing clear responsibility boundaries between ingestion, generation, output, and configuration concerns. We need a module structure that separates concerns cleanly while keeping the simplicity of a single-process pipeline.

## Decision

Decompose into six modules with clear responsibility boundaries:

| Module | Directory | Responsibility | Data Owned |
|--------|-----------|----------------|------------|
| Domain Config | `domains/` | GOAL.md parsing, validation, source document inventory | GOAL.md files, source documents |
| Ingestion | `ingestion/` | Docling PDF processing, chunking, ChromaDB indexing (Stage 0) | ChromaDB collections |
| Agents | `agents/` | Player and Coach factory functions via `create_deep_agent()` | Agent instances (transient) |
| Tools | `tools/` | `rag_retrieval` (ChromaDB query) + `write_output` (layer-aware JSONL routing) | Output files |
| Prompts | `prompts/` | Base prompt templates + runtime GOAL.md section injection | Prompt templates (static) |
| Entrypoint | `agent.py` | LangGraph wiring, config loading, domain selection, loop orchestration | agent-config.yaml, AGENTS.md |

## Alternatives Considered

| Alternative | Why Rejected |
|-------------|-------------|
| Fewer modules (merge Prompts into Agents, Tools into Agents) | Conflates generation logic with orchestration, violates single responsibility |
| More modules (separate Output module, separate Validation module) | Premature — write_output handles routing, Coach handles validation |

## Consequences

- (+) Each module is independently testable
- (+) Adding a new domain requires zero code changes (Domain Config only)
- (+) Player and Coach can evolve independently
- (+) Ingestion is decoupled from generation — can re-ingest without affecting agent code
- (-) Cross-module dependencies must be managed carefully (Entrypoint depends on all others)
