---
id: TASK-TRF-001
title: Update vLLM launch script for Qwen3.5-35B-A3B-FP8
status: completed
created: 2026-03-26T00:00:00Z
updated: 2026-03-26T00:00:00Z
completed: 2026-03-26T00:00:00Z
completed_location: tasks/completed/TASK-TRF-001/
priority: critical
tags: [vllm, model-switch, gb10, infrastructure]
complexity: 2
task_type: implementation
parent_review: TASK-REV-FRF3
feature_id: FEAT-TRF
wave: 1
implementation_mode: task-work
depends_on: []
test_results:
  status: passed
  coverage: n/a
  last_run: 2026-03-26T00:00:00Z
  notes: "bash -n syntax check passed"
---

# Task: Update vLLM Launch Script for Qwen3.5-35B-A3B-FP8

## Description

Update the vLLM launch script at `/Users/richardwoollcott/Projects/appmilla_github/guardkit/scripts/vllm-agentic-factory.sh` to add a `qwen35` preset for Qwen3.5-35B-A3B-FP8 and make it the new default. This model was selected based on GB10 forum research (TASK-REV-FRF3) as the best-performing model for agentic tool-calling on DGX Spark.

## Changes Required

### 1. Add `qwen35` preset (new default)

Add a new case block for the Qwen3.5-35B-A3B-FP8 model:

```bash
qwen35|default|"")
  MODEL="Qwen/Qwen3.5-35B-A3B-FP8"
  GPU_UTIL="${VLLM_FACTORY_GPU_UTIL:-0.80}"
  MAX_LEN="${VLLM_FACTORY_MAX_LEN:-262144}"
  TOOL_PARSER="qwen3_coder"
  IMAGE="${VLLM_IMAGE:-vllm/vllm-openai:cu130-nightly}"
  EXTRA_ARGS="--trust-remote-code \
    --reasoning-parser qwen3 \
    --enable-auto-tool-choice \
    --tool-call-parser qwen3_coder \
    --enable-prefix-caching"
  echo "═══ Qwen3.5-35B-A3B FP8 (3B active, ~70GB) — Tool-calling + Reasoning ═══"
  echo "    BFCL-V4: 67.3 | TAU2: 81.2 | 50 tok/s sustained"
  echo "    Tool parser: qwen3_coder | Reasoning: qwen3 | Context: ${MAX_LEN}"
  ;;
```

### 2. Demote `nano-4b` from default

Change `nano-4b|default|""` to just `nano-4b` so it's still available but not the default.

### 3. Update header comments

- Update the `Usage:` section to show qwen35 as default
- Update memory budget section for Qwen3.5 (~70GB model weights, 0.80 GPU util)
- Update the help text in the `*)` case

### 4. Critical: Docker image change

The Qwen3.5-35B requires `vllm/vllm-openai:cu130-nightly` (the NVIDIA container ships vLLM 0.13.0 which doesn't support Qwen3.5). The `IMAGE` variable should be overridden per-preset.

### 5. Add `--reasoning-parser qwen3`

This enables native `<think>` block parsing, solving TASK-REV-FRF3 Finding F7.

## Acceptance Criteria

- [x] `qwen35` preset added with correct model ID, GPU util (0.80), max_len (262144)
- [x] `qwen35` is the new default (matches `default|""`)
- [x] Docker image set to `vllm/vllm-openai:cu130-nightly` for qwen35 preset
- [x] `--reasoning-parser qwen3` included in EXTRA_ARGS
- [x] `--enable-prefix-caching` included for KV cache efficiency
- [x] `nano-4b` preset still available but no longer default
- [x] Header comments updated with new model and memory budget
- [x] Help text updated in `*)` case
- [x] Script passes `bash -n` syntax check

## Context

- Forum research: [Custom built vLLM + Qwen3.5-35B — 50 tok/s](https://forums.developer.nvidia.com/t/custom-built-vllm-qwen3-5-35b-on-nvidia-dgx-spark-gb10-sustained-50-tok-s-1m-context/362590)
- Setup guide: [github.com/adadrag/qwen3.5-dgx-spark](https://github.com/adadrag/qwen3.5-dgx-spark)
- First startup takes ~15 min for CUDA graph capture; first inference ~57s for torch.compile warmup

## Test Execution Log

[Automatically populated by /task-work]
