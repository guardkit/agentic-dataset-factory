---
id: TASK-TRF-002
title: Update agent-config.yaml for Qwen3.5-35B-A3B-FP8
status: completed
created: 2026-03-26T00:00:00Z
updated: 2026-03-26T00:00:00Z
completed: 2026-03-26T00:00:00Z
completed_location: tasks/completed/TASK-TRF-002/
priority: critical
tags: [config, model-switch]
complexity: 1
task_type: implementation
parent_review: TASK-REV-FRF3
feature_id: FEAT-TRF
wave: 1
implementation_mode: direct
depends_on: [TASK-TRF-001]
test_results:
  status: pending
  coverage: null
  last_run: null
---

# Task: Update agent-config.yaml for Qwen3.5-35B-A3B-FP8

## Description

Update `agent-config.yaml` to point both Player and Coach at the new Qwen3.5-35B-A3B-FP8 model. Use the Qwen3.5-recommended temperature (0.6) for the Player.

## Changes

```yaml
player:
  provider: local
  model: Qwen/Qwen3.5-35B-A3B-FP8
  endpoint: http://promaxgb10-41b1:8002/v1
  temperature: 0.6    # Qwen3.5 recommended for tool calling (was 0.7)

coach:
  provider: local
  model: Qwen/Qwen3.5-35B-A3B-FP8
  endpoint: http://promaxgb10-41b1:8002/v1
  temperature: 0.3    # unchanged
```

## Acceptance Criteria

- [x] Player model updated to `Qwen/Qwen3.5-35B-A3B-FP8`
- [x] Coach model updated to `Qwen/Qwen3.5-35B-A3B-FP8`
- [x] Player temperature changed to 0.6
- [x] Endpoint unchanged (`http://promaxgb10-41b1:8002/v1`)
- [x] All other config sections unchanged

## Test Execution Log

[Automatically populated by /task-work]
