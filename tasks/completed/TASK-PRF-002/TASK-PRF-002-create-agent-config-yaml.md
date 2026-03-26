---
id: TASK-PRF-002
title: Create agent-config.yaml from Pydantic schema
status: completed
created: 2026-03-22T00:00:00Z
updated: 2026-03-22T12:00:00Z
completed: 2026-03-22T12:05:00Z
completed_location: tasks/completed/TASK-PRF-002/
priority: critical
tags: [config, setup, P0]
complexity: 2
parent_review: TASK-REV-A1B4
feature_id: FEAT-PRF
wave: 1
implementation_mode: direct
dependencies: []
test_results:
  status: pass
  coverage: null
  last_run: 2026-03-22T12:00:00Z
---

# Task: Create agent-config.yaml

## Description

Create the `agent-config.yaml` file at the repo root. The config loader (`config/loader.py`) expects this file and raises `FileNotFoundError` without it, blocking startup Step 1.

The schema is fully defined in `config/models.py` (`AgentConfig` Pydantic model).

## Files to Create

- `agent-config.yaml`

## Configuration

```yaml
domain: gcse-english-tutor

player:
  provider: local
  model: Qwen/Qwen3-Coder-Next-FP8
  endpoint: http://localhost:8002/v1
  temperature: 0.7

coach:
  provider: local
  model: Qwen/Qwen3-Coder-Next-FP8
  endpoint: http://localhost:8002/v1
  temperature: 0.3

generation:
  max_turns: 3
  llm_retry_attempts: 3
  llm_retry_backoff: 2.0
  llm_timeout: 300
  target_timeout: 600

chunking:
  chunk_size: 512
  overlap: 64

logging:
  level: INFO
  format: json
```

## Acceptance Criteria

- [x] File exists at repo root as `agent-config.yaml`
- [x] File validates via `load_config()` without errors
- [x] Domain is `gcse-english-tutor`
- [x] Both Player and Coach point to port 8002 endpoints
- [x] All defaults from `config/models.py` are respected

## Verification

```bash
python -c "from config.loader import load_config; c = load_config(); print(f'OK: {c.domain}')"
```

## Notes

- Endpoint URL assumes vLLM serving on GB10 port 8002
- If running from Mac, change endpoint to `http://promaxgb10-41b1:8002/v1`
- Both agents use same model initially; can differentiate later

## Test Execution Log

[Automatically populated by /task-work]
