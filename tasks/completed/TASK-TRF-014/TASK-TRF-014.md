---
id: TASK-TRF-014
title: Cap Player rag_retrieval calls to prevent excessive tool-use loops
status: completed
completed: 2026-03-27T00:00:00Z
created: 2026-03-26T00:00:00Z
updated: 2026-03-27T00:00:00Z
priority: high
tags: [enhancement, player, performance, P1]
complexity: 3
task_type: implementation
parent_review: TASK-REV-TRF5
feature_id: FEAT-TRF5
wave: 2
implementation_mode: task-work
depends_on: [TASK-TRF-012]
test_results:
  status: passed
  coverage: null
  last_run: 2026-03-27T00:00:00Z
---

# Task: Cap Player rag_retrieval Calls

## Description

In Run 5, the Player made 3 rag_retrieval calls across 3 tool-use loop iterations (4 LLM round-trips total) before generating its example. The orchestrator already pre-fetches RAG context (TASK-TRF-009), so the Player should need at most 1 additional call.

**Impact**: Extra token usage (~12K tokens per round-trip) and latency (~25s per call).

### Fix Options

1. **Clarify in Player prompt** that curriculum context is pre-fetched and one additional retrieval is sufficient
2. **Add `max_tool_iterations` config** to limit the DeepAgent's internal tool-use loop (if supported by SDK)
3. **Count tool calls in orchestrator** and inject a "stop using tools" message after N calls

### Recommended Approach

Update the Player system prompt to clarify:
- Curriculum context is already provided in the user message (via orchestrator pre-fetch)
- One additional rag_retrieval call is acceptable for targeted lookups
- Do not make multiple retrieval calls — generate the example after at most 1 tool call

## Acceptance Criteria

- [x] Player makes 0-1 rag_retrieval calls per target (not 3+)
- [x] Pre-fetched RAG context is explicitly referenced in Player prompt
- [x] Generation quality is not degraded (example still grounded in curriculum)
- [x] Existing tests pass

## Context

This is a P1 performance improvement from TASK-REV-TRF5. Not blocking, but reduces token waste and latency for overnight runs.
