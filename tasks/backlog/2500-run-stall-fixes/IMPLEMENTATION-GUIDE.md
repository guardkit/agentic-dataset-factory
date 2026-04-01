# Implementation Guide: 2500-Run Stall Fixes

## Wave 1: Pre-Resume Fixes (Parallel)

All Wave 1 tasks can be executed in parallel. They must be completed before Wave 2.

### TASK-D0A8-001: Wire per-call LLM timeout
- **Method**: task-work
- **Files**: `agents/model_factory.py`, `entrypoint/generation_loop.py`
- **Complexity**: 4
- **Key risk**: LangChain's `ChatOpenAI` passes `timeout=None` to OpenAI SDK, defeating the 600s default. The fix must ensure a numeric timeout reaches the httpx client.

### TASK-D0A8-002: Reduce Player temperature
- **Method**: direct (config change only)
- **Files**: `agent-config.yaml` or equivalent config
- **Complexity**: 1

### TASK-D0A8-003: GB10 setup and run script
- **Method**: task-work
- **Files**: `scripts/run-on-gb10.sh`, `docs/deployment/gb10-setup.md`
- **Complexity**: 3

### TASK-D0A8-005: Write learnings document
- **Method**: direct
- **Files**: `docs/learnings/2500-run-stall-analysis.md`
- **Complexity**: 2

## Wave 2: Resume Run (Sequential, after Wave 1)

### TASK-D0A8-004: Resume generation run
- **Method**: manual (operator executes on GB10)
- **Depends on**: TASK-D0A8-001, TASK-D0A8-002, TASK-D0A8-003
- **Complexity**: 2

## Execution Strategy

```
Wave 1 (parallel):
  TASK-D0A8-001 ──┐
  TASK-D0A8-002 ──┤
  TASK-D0A8-003 ──┼── All complete → Wave 2
  TASK-D0A8-005 ──┘

Wave 2 (manual):
  TASK-D0A8-004 (resume run on GB10)
```

## Verification

After Wave 1, before Wave 2:
- [ ] `pytest tests/ -v` passes (no regressions from timeout wiring)
- [ ] Config shows Player temperature = 0.4
- [ ] `scripts/run-on-gb10.sh` is executable and contains tmux setup
- [ ] Learnings document exists at `docs/learnings/2500-run-stall-analysis.md`
- [ ] GB10 can SSH and reach vLLM at localhost:8002
