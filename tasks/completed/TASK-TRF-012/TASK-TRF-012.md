---
id: TASK-TRF-012
title: Fix Coach tool leakage — bypass create_deep_agent FilesystemMiddleware
status: completed
created: 2026-03-26T00:00:00Z
updated: 2026-03-27T00:00:00Z
completed: 2026-03-27T00:00:00Z
completed_location: tasks/completed/TASK-TRF-012/
priority: critical
tags: [bug-fix, coach, tool-leakage, P0, middleware]
complexity: 6
task_type: implementation
parent_review: TASK-REV-TRF5
feature_id: FEAT-TRF5
wave: 1
implementation_mode: task-work
depends_on: [TASK-TRF-011]
test_results:
  status: passed
  coverage: null
  last_run: 2026-03-27T00:00:00Z
  tests_passed: 56
  tests_failed: 0
---

# Task: Fix Coach Tool Leakage — Bypass create_deep_agent FilesystemMiddleware

## Description

Both Player and Coach agents have 8 leaked DeepAgents platform tools (`edit_file`, `glob`, `grep`, `ls`, `read_file`, `write_file`, `task`, `write_todos`) injected by `FilesystemMiddleware`. The Coach actively called `read_file('/evaluation_criteria.md')` instead of evaluating the training example.

### Root Cause (Confirmed in SDK Source)

`create_deep_agent` at `deepagents/graph.py:186` replaces `backend=None` with `StateBackend`, then unconditionally adds `FilesystemMiddleware` at line 258. There is no supported way to suppress filesystem tools via `create_deep_agent`.

```python
# deepagents/graph.py:186
backend = backend if backend is not None else (StateBackend)

# deepagents/graph.py:258 — ALWAYS adds FilesystemMiddleware
deepagent_middleware.extend([
    FilesystemMiddleware(backend=backend),
    ...
])
```

The langchain-skills confirm: *"Agents cannot remove core middleware or rename built-in tools"* (`deep-agents-core`).

### Fix Strategy

For the **Coach**: Bypass `create_deep_agent` and use `langchain.agents.create_agent` directly with a custom middleware stack that excludes `FilesystemMiddleware`. The Coach only needs:
- `TodoListMiddleware` (required by SDK)
- `PatchToolCallsMiddleware` (required for tool call normalization)
- `AnthropicPromptCachingMiddleware` (for Anthropic models, harmless for others)
- `MemoryMiddleware` (for AGENTS.md injection)

It does NOT need:
- `FilesystemMiddleware` (no file ops)
- `SubAgentMiddleware` (no subagents)
- `SummarizationMiddleware` (short conversations)

For the **Player**: Revert TASK-TRF-003 and restore `backend=FilesystemBackend(root_dir=".")`. The original exemplar design intentionally gave the Player filesystem access. The Player needs `rag_retrieval` as its only custom tool, but having filesystem tools available is acceptable (they're unused but not harmful for the Player role).

### Key Files

- `agents/coach.py` — Coach factory (main change)
- `agents/player.py` — Revert to FilesystemBackend
- `agents/model_factory.py` — No changes expected
- `tests/test_agents.py` — Update tests for new Coach factory

### Interface Contract

After fix:
- Player tools: `[rag_retrieval]` + 8 filesystem tools (via FilesystemBackend) = acceptable
- Coach tools: `[]` (zero tools) = required
- Coach must still accept `model_config`, `system_prompt`, `memory` parameters

## Acceptance Criteria

- [x] Coach agent has exactly 0 tools (no filesystem tools leaked)
- [x] Player agent has `rag_retrieval` + filesystem tools (original exemplar design)
- [x] Coach factory does not import or use `create_deep_agent` (uses `create_agent` directly)
- [x] Player factory uses `backend=FilesystemBackend(root_dir=".")`
- [x] All existing tests pass
- [x] New test: verify Coach has no tools after creation
- [x] New test: verify Player has `rag_retrieval` tool after creation

## Context

This is one of two P0 blockers from TASK-REV-TRF5. The Coach's leaked `read_file` tool caused it to enter a tool-calling workflow instead of outputting a JSON verdict, which may have contributed to the empty-content issue (F1). Fixing tool leakage alone may resolve F1 indirectly.
