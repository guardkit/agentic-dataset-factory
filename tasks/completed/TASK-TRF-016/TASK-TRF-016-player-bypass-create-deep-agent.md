---
id: TASK-TRF-016
title: Bypass create_deep_agent for Player — remove FilesystemMiddleware tool leakage
status: completed
created: 2026-03-27T00:00:00Z
updated: 2026-03-27T00:00:00Z
completed: 2026-03-27T00:00:00Z
priority: critical
tags: [fix, player, tool-leakage, sixth-run]
complexity: 3
parent_review: TASK-REV-TRF6
feature_id: FEAT-TRF6
wave: 1
implementation_mode: task-work
depends_on: []
test_results:
  status: pass
  coverage: null
  last_run: 2026-03-27T00:00:00Z
---

# Task: Bypass create_deep_agent for Player — Remove FilesystemMiddleware Tool Leakage

## Description

Apply the same fix pattern from TASK-TRF-012 (Coach) to the Player factory. Replace `create_deep_agent()` with the lower-level `create_agent()` API and curate the middleware stack to exclude `FilesystemMiddleware`.

### Root Cause

`agents/player.py` lines 65-71 call `create_deep_agent()` which unconditionally injects `FilesystemMiddleware` (via `deepagents/graph.py` line 258). This adds 8 platform tools (`write_todos`, `ls`, `read_file`, `write_file`, `edit_file`, `glob`, `grep`, `task`) alongside the intended `rag_retrieval`. In Run 6, Qwen3.5-35B used the leaked `write_file` to save output to `/tmp/` instead of returning content, crashing the pipeline.

### Changes Required

**File: `agents/player.py`**

1. Remove import of `create_deep_agent` and `FilesystemBackend` (if only used for the backend param)
2. Add imports mirroring the Coach pattern in `agents/coach.py` lines 83-101:
   - `create_agent` from `langchain.agents`
   - `MemoryMiddleware` from `deepagents.middleware`
   - `PatchToolCallsMiddleware` from `deepagents.middleware`
   - `AnthropicPromptCachingMiddleware` from `deepagents.middleware` (if applicable)
   - `FilesystemBackend` from `deepagents.backends` (only for `MemoryMiddleware`)
3. Replace lines 65-71 (`create_deep_agent()` call) with `create_agent()`:
   - `tools=[rag_retrieval]` — only the intended tool
   - `middleware=[MemoryMiddleware(backend=FilesystemBackend(root_dir="."), sources=memory), PatchToolCallsMiddleware()]`
   - NO `FilesystemMiddleware` in the middleware stack

**Reference**: Mirror exactly what `agents/coach.py` does at lines 83-101, except:
- Coach has `tools=[]` → Player has `tools=[rag_retrieval]`
- Both exclude `FilesystemMiddleware`

### Expected Outcome

Player HTTP requests should contain exactly 1 tool (`rag_retrieval`), not 9.

## Acceptance Criteria

- [x] Player factory uses `create_agent()` not `create_deep_agent()`
- [x] Player middleware stack excludes `FilesystemMiddleware`
- [x] Player tools at runtime: only `rag_retrieval`
- [x] `MemoryMiddleware` still loads `AGENTS.md` memory
- [x] All existing tests pass (after updating test_player_factory.py)
- [x] System prompt no longer contains DeepAgents boilerplate (~43K chars → much smaller)

## Context

Run 6 log: `docs/reviews/second-run/qwen35-run03.md`
Review report: `.claude/reviews/TASK-REV-TRF6-review-report.md`
Coach fix reference: `agents/coach.py` lines 83-101 (TASK-TRF-012)
