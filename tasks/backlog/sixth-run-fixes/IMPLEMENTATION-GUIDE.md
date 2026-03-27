# Implementation Guide — Sixth Run Fixes

## Wave 1: Player Tool Leakage Fix (Critical)

### TASK-TRF-016: Bypass create_deep_agent for Player

**What**: Replace `create_deep_agent()` → `create_agent()` in `agents/player.py`
**Why**: `create_deep_agent` injects `FilesystemMiddleware` which leaks 8 platform tools
**Reference**: `agents/coach.py` lines 83-101 (same fix applied by TASK-TRF-012)
**Complexity**: 3 — straightforward, proven pattern exists

```bash
/task-work TASK-TRF-016
```

### TASK-TRF-017: Update Player Factory Tests

**What**: Rewrite `tests/test_player_factory.py` to test `create_agent` pattern
**Why**: Tests currently assert `create_deep_agent` is called, which will no longer be true
**Reference**: `tests/test_coach_factory.py` (mirror this pattern)
**Complexity**: 2 — test structure already exists for Coach

```bash
/task-work TASK-TRF-017
```

## Wave 2: Improvements (Parallel)

### TASK-TRF-018: Token Usage Logging
### TASK-TRF-019: `<think>` Closing Tag

These can be done in parallel and are not blockers for Wave 3.

## Wave 3: Validation Run

### TASK-REV-TRF7: Seventh Run Validation

After Wave 1 is complete, run the pipeline and capture the log:

```bash
python agent.py 2>&1 | tee docs/reviews/second-run/qwen35-run04.md
```

Then review:

```bash
/task-review TASK-REV-TRF7
```

**Success criteria**: At least 1 target accepted end-to-end (Player generates → Coach evaluates → output written).
