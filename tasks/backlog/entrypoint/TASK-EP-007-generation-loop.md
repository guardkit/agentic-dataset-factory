---
id: TASK-EP-007
title: "Generation loop \u2014 Player-Coach cycle with DeepAgents SDK"
task_type: feature
parent_review: TASK-REV-9EDC
feature_id: FEAT-2CF1
wave: 3
implementation_mode: task-work
complexity: 6
dependencies:
- TASK-EP-005
- TASK-EP-006
status: in_review
autobuild_state:
  current_turn: 1
  max_turns: 35
  worktree_path: /Users/richardwoollcott/Projects/appmilla_github/agentic-dataset-factory/.guardkit/worktrees/FEAT-6D0B
  base_branch: main
  started_at: '2026-03-21T00:01:38.272356'
  last_updated: '2026-03-21T00:14:00.591563'
  turns:
  - turn: 1
    decision: approve
    feedback: null
    timestamp: '2026-03-21T00:01:38.272356'
    player_summary: Implementation via task-work delegation
    player_success: true
    coach_success: true
---

# Task: Generation Loop — Player-Coach Cycle with DeepAgents SDK

## Description

Implement `run_generation_loop()` — the core sequential Player-Coach adversarial loop that processes generation targets. This is the heart of the pipeline.

The loop uses DeepAgent instances (created by `create_player()` and `create_coach()` factories from the agent-factories feature). The entrypoint orchestrates target iteration, turn management, and resilience mechanisms. DeepAgents SDK manages the agent's internal tool calling and conversation.

## Requirements

### Core Loop (ADR-ARCH-006 — sequential)
```
for each target in targets[start_index:]:
    for turn in range(max_turns):
        1. Player generates example (DeepAgent handles RAG retrieval internally)
        2. Coach evaluates example (DeepAgent returns structured JSON verdict)
        3. If accepted: Player writes output (via write_output tool), break
        4. If rejected and turns remain: Player revises with Coach feedback
        5. If rejected at max_turns: log to rejected.jsonl
    write_checkpoint(target_index)
```

### Resilience (ADR-ARCH-010)
- **LLM retry**: Configure via LangChain model's `max_retries` parameter (set from `config.generation.llm_retry_attempts`)
- **LLM timeout**: Configure via model's `timeout` parameter (set from `config.generation.llm_timeout`)
- **Per-target timeout**: Wrap target processing in `asyncio.wait_for(timeout=config.generation.target_timeout)`. On timeout: log to `rejected.jsonl` with `reason: "timeout"`, continue to next target
- **All retries exhausted**: Log to `rejected.jsonl` with failure reason, continue to next target

### Progress Logging (ADR-ARCH-007)
- Log `target_start` at beginning of each target
- Log `turn_complete` after each Player-Coach cycle
- Log `target_accepted` or `target_rejected` after target resolution
- Log `progress` periodically (e.g., every 50 targets)
- Log `complete` at end of generation

### Return Value
```python
@dataclass
class GenerationResult:
    total_targets: int
    accepted: int
    rejected: int
    total_turns: int
    elapsed_seconds: float
```

## Acceptance Criteria

- [ ] Sequential target processing (one at a time per ADR-ARCH-006)
- [ ] Player-Coach cycle with up to `max_turns` revisions (BDD: "Generation loop processes a target")
- [ ] `max_turns=1` gives exactly one attempt (BDD: "Generation with max_turns set to 1")
- [ ] Rejected targets logged to `rejected.jsonl` with rejection history (BDD: "Target rejected after exhausting all turns")
- [ ] Per-target timeout discards and continues (BDD: "Target exceeding the per-target timeout")
- [ ] Transient LLM failures retried with backoff (BDD: "Transient LLM failure is retried")
- [ ] All retries exhausted: target discarded, pipeline continues (BDD: "All LLM retries exhausted")
- [ ] Checkpoint written after each target
- [ ] Structured JSON progress logging at key milestones
- [ ] `GenerationResult` returned with statistics
- [ ] All modified files pass project-configured lint/format checks with zero errors

## Reference

- API contract: `docs/design/contracts/API-generation.md` (Player-Coach Protocol)
- API contract: `docs/design/contracts/API-entrypoint.md` (Generation Loop, Progress Logging)
- ADR-ARCH-006: Sequential generation
- ADR-ARCH-010: Overnight run resilience
- DDR-003: 3-turn limit
- Coach rejection schema: `docs/design/models/DM-coach-rejection.md`

## Implementation Notes

Place in `entrypoint/generation_loop.py`. This module receives pre-instantiated DeepAgent instances — it does NOT create them. The retry/timeout configuration is set on the LangChain model objects during agent factory creation, not in the loop itself. The loop handles per-target timeout via `asyncio.wait_for`.
