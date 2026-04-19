# Gemma 4 MoE Deployment to MacBook

## Problem Statement

Training run 4 of the Gemma 4 26B A4B MoE fine-tune on the GCSE English tutor dataset completed successfully. The model needs to be deployed to MacBook Pro with a student-facing interface (Ollama + ChromaRAG + Open WebUI).

## Solution Approach

Deploy the Q4_K_M quantised GGUF model via:
1. rsync over Tailscale from DGX Spark to MacBook
2. Register in Ollama with the Unsloth-generated Modelfile
3. Smoke test the tutor persona before full setup
4. Wire up ChromaRAG for document-grounded responses
5. Set up Open WebUI as the chat interface

## Subtask Summary

| Task | Title | Wave | Status |
|------|-------|------|--------|
| [TASK-G4D-001](TASK-G4D-001-transfer-gguf-to-macbook.md) | Transfer GGUF to MacBook | 1 | Backlog |
| [TASK-G4D-002](TASK-G4D-002-register-ollama-and-smoke-test.md) | Register in Ollama + smoke tests | 2 | Backlog |
| [TASK-G4D-003](TASK-G4D-003-setup-chromarag-and-openwebui.md) | ChromaRAG + Open WebUI setup | 3 | Backlog |
| [TASK-G4D-004](TASK-G4D-004-fix-task-metadata-lr-schedule.md) | Fix LR schedule metadata | 1 | Backlog |

## Source Review

- [TASK-REV-G4R2 Review Report](../../../.claude/reviews/TASK-REV-G4R2-review-report.md) — Training Health Score: 82/100
