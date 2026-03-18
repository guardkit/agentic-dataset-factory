# ADR-ARCH-003: Docker Containerisation from Day One

**Status:** Accepted
**Date:** 2026-03-16
**Deciders:** ML Engineer + /system-arch session

## Context

The pipeline runs on a Dell Pro Max GB10 (DGX Spark) which already uses Docker for vLLM model serving (see `vllm-serve.sh` and `vllm-embed.sh` scripts). We need to decide between running the agent loop as direct Python or in a Docker container.

## Decision

Use Docker containerisation from day one with `docker compose` orchestrating all services on GB10.

Target docker compose topology:
```
services:
  vllm-coach     — Local LLM serving (Nemotron 3 Super or other)
  agent-loop     — Player-Coach generation pipeline
```

## Alternatives Considered

| Alternative | Why Rejected |
|-------------|-------------|
| Direct Python via `uv` | Simpler initially, but risks dependency conflicts with vLLM's torch/CUDA stack; inconsistent with existing Docker workflow on GB10 |
| Hybrid (vLLM in Docker, agent loop direct) | Inconsistent operational model; if vLLM is already containerised, adding agent-loop is low incremental cost |

## Consequences

- (+) Consistent with existing vLLM Docker workflow on GB10
- (+) Clean dependency isolation — agent loop won't conflict with vLLM's torch/CUDA
- (+) `docker compose up` / `docker compose down` for the whole stack
- (+) Reproducible setup for open-source contributors
- (+) Start/stop without orphaned processes
- (-) Slightly more setup overhead than direct Python
- (-) Requires NVIDIA Container Toolkit for GPU access (already installed on GB10)
