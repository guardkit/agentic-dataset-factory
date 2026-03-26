---
id: TASK-FRF-004
title: Third end-to-end run with Nemotron 3 Nano 4B
status: backlog
created: 2026-03-25T00:00:00Z
updated: 2026-03-25T00:00:00Z
priority: critical
tags: [end-to-end, nemotron, third-run, validation]
complexity: 2
task_type: implementation
parent_review: TASK-REV-FRF2
depends_on: []
test_results:
  status: pending
  coverage: null
  last_run: null
---

# Task: Third End-to-End Run with Nemotron 3 Nano 4B

## Description

Run the agentic-dataset-factory pipeline end-to-end with the new Nemotron 3 Nano 4B model to validate that the model switch resolves the three issues identified in TASK-REV-FRF2:

- **F3**: vLLM/LangChain `tool_calls.args` deserialization crash (fixed by `qwen3_coder` parser)
- **F4**: Model misstructuring `write_output` arguments (fixed by Nemotron's native tool-calling)
- **F5**: Player bypassing Coach evaluation (improved instruction-following)

Also validates TASK-FRF-002 (array metadata validation) which was never tested in the second run.

## Changes Applied Before This Run

1. **vLLM script**: `vllm-agentic-factory.sh` updated — defaults to Nemotron 3 Nano 4B with `--tool-call-parser qwen3_coder`
2. **agent-config.yaml**: Model changed to `nvidia/NVIDIA-Nemotron-3-Nano-4B-FP8`
3. **generation_loop.py**: `ValidationError` added to retry-eligible exceptions (defensive)

## Prerequisites

1. Restart vLLM on GB10:
   ```bash
   ./scripts/vllm-agentic-factory.sh  # defaults to nano-4b
   ```
2. Wait for model to load, verify health:
   ```bash
   curl http://promaxgb10-41b1:8002/health
   curl http://promaxgb10-41b1:8002/v1/models
   ```

## Execution Steps

1. SSH to GB10, stop existing vLLM factory container, start with new script
2. Wait for model to load, verify health
3. Run: `python agent.py`
4. Capture full terminal output to `docs/reviews/first-run/vllm-nemotron3-nano-1.md`
5. Analyse results — create TASK-REV-FRF3 if new issues found

## Acceptance Criteria

- [ ] vLLM serving Nemotron 3 Nano 4B on port 8002 with `qwen3_coder` parser
- [ ] Pipeline runs without `tool_calls.args` dict_type crash
- [ ] `write_output` receives correctly-structured single `example_json` argument
- [ ] At least one training example written to `output/train.jsonl`
- [ ] Coach evaluation occurs before `write_output`
- [ ] Terminal output captured for review
