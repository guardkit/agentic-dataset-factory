---
id: TASK-TRF-007
title: Fourth end-to-end run (Qwen3.5-35B-A3B-FP8)
status: backlog
created: 2026-03-26T00:00:00Z
updated: 2026-03-26T00:00:00Z
priority: high
tags: [end-to-end, validation, qwen35]
complexity: 3
task_type: implementation
parent_review: TASK-REV-FRF3
feature_id: FEAT-TRF
wave: 3
implementation_mode: direct
depends_on: [TASK-TRF-001, TASK-TRF-002, TASK-TRF-003, TASK-TRF-004, TASK-TRF-005, TASK-TRF-006]
test_results:
  status: pending
  coverage: null
  last_run: null
---

# Task: Fourth End-to-End Run (Qwen3.5-35B-A3B-FP8)

## Description

Execute the fourth end-to-end run after all TASK-TRF fixes are applied. This validates:

1. Qwen3.5-35B-A3B-FP8 serves correctly on GB10 port 8002
2. Tool calling works with `qwen3_coder` parser (same as Run 3, proven)
3. `<think>` blocks are generated (native reasoning with `--reasoning-parser qwen3`)
4. No context window exhaustion (262K vs 16K)
5. No tool leakage (backend=None, only rag_retrieval visible to Player)
6. `grade_target` integer values pass validation
7. Coach evaluates before any writes occur (orchestrator-gated)
8. Write retry cap prevents unbounded loops

## Steps

1. Start vLLM: `./scripts/vllm-agentic-factory.sh qwen35`
2. Wait for model load (~15 min CUDA graph capture, ~57s first inference warmup)
3. Run pipeline: `python agent.py`
4. Capture full terminal output to `docs/reviews/first-run/vllm-qwen35-1.md`
5. Verify at least 1 target accepted and written to `output/train.jsonl`

## Acceptance Criteria

- [ ] vLLM serves Qwen3.5-35B-A3B-FP8 on port 8002 without errors
- [ ] Pipeline completes at least 1 target without crashing
- [ ] At least 1 accepted example written to `output/train.jsonl`
- [ ] No context window exhaustion errors in log
- [ ] No tool leakage (only rag_retrieval visible in request tool schemas)
- [ ] Coach verdict appears in log before any write occurs
- [ ] Log captured to `docs/reviews/first-run/vllm-qwen35-1.md`

## Context

This is the fourth iteration: Run 1 (ChromaDB bugs) → Run 2 (deserialization) → Run 3 (context + tool leakage) → Run 4 (this run, all fixes applied).

## Test Execution Log

[Automatically populated by /task-work]
