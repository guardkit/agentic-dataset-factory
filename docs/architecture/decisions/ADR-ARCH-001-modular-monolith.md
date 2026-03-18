# ADR-ARCH-001: Use Modular Monolith Structural Pattern

**Status:** Accepted
**Date:** 2026-03-16
**Deciders:** ML Engineer + /system-arch session

## Context

The system is a domain-agnostic training dataset generation pipeline using Player-Coach adversarial agents. It runs as a batch pipeline on a single Dell Pro Max GB10 (DGX Spark, 128GB unified memory). We need a structural pattern that supports config-driven domain abstraction, factory-pattern agents, and single-machine deployment.

## Decision

Use the Modular Monolith structural pattern.

## Alternatives Considered

| Pattern | Why Rejected |
|---------|-------------|
| Domain-Driven Design | Higher complexity for what is fundamentally a pipeline; bounded contexts add overhead without proportional benefit |
| Event-Driven Architecture | Overkill for a single-machine batch pipeline; eventual consistency adds unnecessary complexity |
| Clean / Hexagonal | More abstractions than needed for this scope; the pipeline's ports are simple (LLM providers, ChromaDB, file output) |
| Layered Architecture | Rigid hierarchy doesn't map well to a pipeline with parallel concerns (ingestion vs generation) |

## Consequences

- (+) Simple deployment — single process on GB10
- (+) Shared ChromaDB instance with no network overhead
- (+) Easy to debug the Player-Coach loop end-to-end
- (+) Aligns with existing repo structure from the exemplar template
- (-) Scaling limited to single machine (acceptable — GB10 is the target)
- (-) Must manage module boundaries through discipline rather than enforcement
