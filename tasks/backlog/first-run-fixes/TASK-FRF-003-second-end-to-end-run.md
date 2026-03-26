---
id: TASK-FRF-003
title: Second end-to-end pipeline run with fixes applied
status: backlog
created: 2026-03-25T00:00:00Z
updated: 2026-03-25T00:00:00Z
priority: high
tags: [validation, e2e, pipeline, second-run]
complexity: 4
parent_review: TASK-REV-E2A7
feature_id: FEAT-FRF
wave: 2
implementation_mode: manual
dependencies: [TASK-FRF-001, TASK-FRF-002]
test_results:
  status: pending
  coverage: null
  last_run: null
---

# Task: Second End-to-End Pipeline Run

## Description

Re-run the agentic-dataset-factory pipeline with both P0 fixes applied (TASK-FRF-001: ChromaDB path, TASK-FRF-002: array validation). Validates that the pipeline can complete a full generation cycle: RAG retrieval, example generation, write_output acceptance, Coach evaluation.

## Prerequisites

- TASK-FRF-001 merged (rag_retrieval uses correct ChromaDB path)
- TASK-FRF-002 merged (write_output handles array metadata fields)
- GB10 vLLM instance running on port 8002 (Qwen2.5-14B with hermes tool parser)
- ChromaDB `chroma_data/` populated (3854 chunks from TASK-PRF-005)

## Execution Steps

1. Verify GB10 vLLM is accessible: `curl http://promaxgb10-41b1:8002/v1/models`
2. Run pipeline: `python agent.py`
3. Monitor logs for:
   - rag_retrieval returning chunks (not errors)
   - write_output accepting examples (not rejecting on metadata.ao)
   - Coach evaluating and returning verdicts
   - At least 1 accepted example written to `output/train.jsonl`
4. Capture full log output to `docs/reviews/first-run/vllm-qwen-25-2.md`

## Success Criteria

- [ ] rag_retrieval returns formatted curriculum chunks (no "Collection not found")
- [ ] write_output accepts at least 1 example (no metadata.ao validation errors)
- [ ] Coach evaluation is reached and returns structured verdict
- [ ] At least 1 accepted example in `output/train.jsonl`
- [ ] No 600s timeout on the first target
- [ ] Pipeline processes multiple targets without crashing

## Expected Architecture

Same as first run (MacBook + GB10 split):
- MacBook: pipeline code, ChromaDB, output files
- GB10: vLLM inference via Tailscale (port 8002)
