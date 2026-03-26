# Implementation Guide: Third Run Fixes

## Execution Strategy

### Wave 1: P0 Fixes (parallel, no dependencies between them)

These 4 tasks can be executed in parallel as they modify different files:

| Task | Files Modified | Method |
|------|---------------|--------|
| TASK-TRF-001 | `guardkit/scripts/vllm-agentic-factory.sh` | task-work |
| TASK-TRF-002 | `agent-config.yaml` | direct edit |
| TASK-TRF-003 | `agents/player.py`, `agents/tests/test_player.py` | task-work |
| TASK-TRF-004 | `src/tools/write_output.py`, `src/tools/tests/test_write_output.py` | direct edit |

**Note**: TASK-TRF-002 depends on TASK-TRF-001 being deployed to GB10, but the code change itself is independent.

### Wave 2: Architectural Fix (sequential)

| Task | Files Modified | Depends On |
|------|---------------|------------|
| TASK-TRF-005 | `generation_loop.py`, `tool_factory.py`, `agent.py`, `prompts/player_prompts.py` | TASK-TRF-003 |
| TASK-TRF-006 | `generation_loop.py`, `config/models.py` | TASK-TRF-005 |

TASK-TRF-005 is the most complex change (complexity 5). It restructures the generation loop to follow the GuardKit orchestrator-gated write pattern.

### Wave 3: Validation

| Task | Method | Depends On |
|------|--------|------------|
| TASK-TRF-007 | Manual execution on GB10 | All Wave 1 + Wave 2 |

## Risk Assessment

| Risk | Mitigation |
|------|-----------|
| Qwen3.5-35B doesn't fit in GB10 memory alongside Graphiti | Set GPU util to 0.80; Graphiti uses 0.40 on port 8000. Total ~120GB of 128GB. May need to stop Graphiti during generation. |
| Player response format changes after removing write_output | TASK-TRF-005 must update Player prompt to return JSON directly. Test with mock LLM. |
| vLLM cu130-nightly image has breaking changes | Pin to specific nightly tag if instability found. Community Docker image `hellohal2064/vllm-qwen3.5-gb10:latest` is an alternative. |
| First startup takes ~15 min | Expected. Document in README. Don't treat as failure. |

## Testing Strategy

- **Wave 1**: Unit tests only (no LLM needed)
- **Wave 2**: Unit tests with mocked DeepAgent responses
- **Wave 3**: Full integration test on GB10 hardware
