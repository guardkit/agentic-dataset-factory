# Implementation Guide: Gemma 4 MoE Deployment to MacBook

## Parent Review

- **Review**: TASK-REV-G4R2 — Analyse Gemma 4 MoE full training run and deploy to MacBook
- **Training Health Score**: 82/100
- **Decision**: Deploy as-is (training is healthy)
- **Report**: [.claude/reviews/TASK-REV-G4R2-review-report.md](../../../.claude/reviews/TASK-REV-G4R2-review-report.md)

## Execution Strategy

All deployment tasks are **manual** — they require physical access to the DGX Spark and MacBook Pro, and CLI interaction with Ollama, ChromaRAG, and Open WebUI.

### Wave 1: Transfer + Housekeeping (parallel)

| Task | Title | Mode | Est. Time |
|------|-------|------|-----------|
| TASK-G4D-001 | Transfer GGUF to MacBook via rsync/Tailscale | Manual | 30-60 min (network dependent) |
| TASK-G4D-004 | Fix LR schedule metadata | Direct | 5 min |

### Wave 2: Ollama Registration + Smoke Tests

| Task | Title | Mode | Est. Time |
|------|-------|------|-----------|
| TASK-G4D-002 | Register in Ollama and run smoke tests | Manual | 30 min |

**Decision gate**: If smoke tests reveal persona gaps, pause and consider retraining before proceeding.

### Wave 3: RAG + Web UI

| Task | Title | Mode | Est. Time |
|------|-------|------|-----------|
| TASK-G4D-003 | Set up ChromaRAG and Open WebUI | Manual | 1-2 hours |

## Key Decision Points

1. **After TASK-G4D-002 (smoke tests)**: Go/no-go for full RAG setup. If the model doesn't demonstrate Socratic questioning or AQA knowledge, consider a second training epoch at lr=2e-5 before continuing.

2. **During TASK-G4D-001 (transfer)**: Check whether the Ollama Modelfile references `BF16-mmproj.gguf` — if so, transfer that file too. For text-only use, it may not be needed.

## Prerequisites

- Both DGX Spark and MacBook Pro on Tailscale
- Docker container `6150ec61761e` accessible on DGX Spark (or files already copied to host)
- Ollama installed on MacBook Pro
- GCSE English reference documents available for ChromaRAG ingestion
