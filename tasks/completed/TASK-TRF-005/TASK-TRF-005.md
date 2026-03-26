---
id: TASK-TRF-005
title: Move write_output to orchestrator (fix Coach bypass)
status: completed
created: 2026-03-26T00:00:00Z
updated: 2026-03-26T12:00:00Z
completed: 2026-03-26T12:00:00Z
completed_location: tasks/completed/TASK-TRF-005/
priority: high
tags: [architecture, coach-bypass, adversarial-cooperation]
complexity: 5
task_type: implementation
parent_review: TASK-REV-FRF3
feature_id: FEAT-TRF
wave: 2
implementation_mode: task-work
depends_on: [TASK-TRF-003]
test_results:
  status: pass
  coverage: 204/204
  last_run: 2026-03-26T12:00:00Z
---

# Task: Move write_output to Orchestrator (Fix Coach Bypass)

## Description

The Player currently has `write_output` in its tool list and writes examples to disk autonomously during `ainvoke()`, before the Coach evaluates them. This violates the adversarial cooperation principle where the Coach should gate all writes.

**Architectural fix**: Remove `write_output` from the Player's tool list. The orchestrator (`generation_loop.py`) should extract the generated example from the Player's response, pass it to the Coach, and only call `write_output` programmatically after Coach acceptance.

This follows the proven GuardKit autobuild pattern where the orchestrator owns all state transitions.

## Changes Required

### 1. `src/tools/tool_factory.py`

```python
# Player gets only rag_retrieval (no write_output)
def create_player_tools(...) -> list[Callable]:
    _validate_collection_name(collection_name)
    rag_tool = create_rag_retrieval_tool(collection_name, persist_directory)
    return [rag_tool]

# New: expose write_output factory for orchestrator use
def create_write_tool(output_dir: Path, metadata_schema: list[MetadataField]) -> Callable:
    _validate_output_dir(output_dir)
    _validate_metadata_schema(metadata_schema)
    return create_write_output_tool(output_dir, metadata_schema)
```

### 2. `entrypoint/generation_loop.py`

The `_process_single_target` function needs restructuring:

```python
async def _process_single_target(
    player, coach, target, target_index, total_targets, config,
    output_manager, write_tool,  # NEW: write_tool passed in
):
    for turn in range(config.max_turns):
        # Player generates (no write_output available)
        player_input = {"messages": [{"role": "user", "content": _build_player_message(target, coach_feedback)}]}
        player_response = await _invoke_with_retry(player, player_input, ...)
        player_content = player_response["messages"][-1].content

        # Coach evaluates
        coach_input = {"messages": [{"role": "user", "content": player_content}]}
        coach_response = await _invoke_with_retry(coach, coach_input, ...)
        verdict = _parse_coach_verdict(coach_response["messages"][-1].content)

        if verdict.is_accepted:
            # ORCHESTRATOR writes — not the Player
            write_result = write_tool.invoke({"example_json": player_content})
            if write_result.startswith("Error:"):
                # Write validation failed — treat as rejection
                logger.warning("Write validation failed after Coach acceptance: %s", write_result)
                rejection_history.append({"write_error": write_result, **verdict.model_dump()})
                coach_feedback = f"Write validation failed: {write_result}. Revise the example."
                continue
            return True, turn + 1, rejection_history

        # Rejected — extract feedback for next turn
        rejection_history.append(verdict.model_dump())
        coach_feedback = verdict.quality_assessment
        ...
```

### 3. `agent.py`

Update the startup sequence to create the write tool separately and pass it to the generation loop:

```python
# Step 9: Create tools
player_tools = create_player_tools(collection_name=config.domain, ...)
write_tool = create_write_tool(output_dir=OUTPUT_DIR, metadata_schema=goal.metadata_schema)

# Step 12: Run generation loop
result = asyncio.run(run_generation_loop(
    player=player, coach=coach,
    targets=goal.generation_targets, config=config.generation,
    checkpoint=checkpoint_mgr, output_manager=output_mgr,
    write_tool=write_tool,  # NEW
    start_index=start_index,
))
```

### 4. Player prompt update

Update `prompts/player_prompts.py` to remove references to `write_output` tool. The Player should be instructed to **return the generated example as its response content**, not to call a write tool.

### 5. Extract example from Player response

The Player's final response content needs to be a valid JSON example that can be passed to `write_output`. Add parsing logic to extract the JSON from the Player's response (it may be wrapped in markdown code fences or have surrounding text).

## Acceptance Criteria

- [x] `write_output` removed from `create_player_tools()` return list
- [x] New `create_write_tool()` factory function in `tool_factory.py`
- [x] `generation_loop.py` calls `write_tool` only after `verdict.is_accepted`
- [x] `agent.py` creates write_tool separately and passes to generation loop
- [x] Player prompt updated to return example as content (not call write_output)
- [x] Example JSON extraction from Player response implemented
- [x] Write validation errors after Coach acceptance handled gracefully
- [x] All existing generation_loop tests updated
- [x] New test: Player response → Coach accepts → orchestrator writes
- [x] New test: Player response → Coach rejects → no write occurs
- [x] New test: Coach accepts but write_output validation fails → treated as rejection

## Architecture Reference

This follows the GuardKit autobuild pattern:
- Player generates content, reports back to orchestrator
- Coach independently evaluates
- Orchestrator writes only after Coach approval
- See `.guardkit/autobuild/*/turn_state_*.json` for the proven pattern

## Test Execution Log

**Run**: 2026-03-26T12:00:00Z
**Result**: 204 passed, 0 failed
**Files modified**: 10 (5 source, 5 test)

### Files Changed

| File | Change |
|------|--------|
| `src/tools/tool_factory.py` | Removed `write_output` from Player; added `create_write_tool()` |
| `entrypoint/generation_loop.py` | Added `write_tool` param, `_extract_example_json()`, orchestrator-gated writes |
| `agent.py` | Creates `write_tool` separately, passes to loop |
| `prompts/player_prompts.py` | Removed `write_output` references; Player returns JSON in response |
| `prompts/tests/test_prompt_builders.py` | Updated assertion for removed `write_output` |
| `src/tools/tests/test_tool_factory.py` | Updated for 1-tool Player; added 7 `create_write_tool` tests |
| `entrypoint/tests/test_generation_loop.py` | Added `write_tool`; added 9 new tests (orchestrator writes, JSON extraction) |
| `entrypoint/tests/test_agent_graph.py` | Added `create_write_tool` patch |
| `entrypoint/tests/test_startup_orchestration.py` | Updated for new architecture |
| `tests/test_integration_smoke.py` | Updated for `write_tool` parameter |
