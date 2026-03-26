---
id: TASK-EP-008
title: "LangGraph thin wrapper \u2014 graph export for langgraph.json"
task_type: feature
parent_review: TASK-REV-9EDC
feature_id: FEAT-2CF1
wave: 3
implementation_mode: task-work
complexity: 3
dependencies:
- TASK-EP-007
status: in_review
autobuild_state:
  current_turn: 1
  max_turns: 35
  worktree_path: /Users/richardwoollcott/Projects/appmilla_github/agentic-dataset-factory/.guardkit/worktrees/FEAT-6D0B
  base_branch: main
  started_at: '2026-03-21T00:14:00.623995'
  last_updated: '2026-03-21T00:21:34.327307'
  turns:
  - turn: 1
    decision: approve
    feedback: null
    timestamp: '2026-03-21T00:14:00.623995'
    player_summary: Implementation via task-work delegation
    player_success: true
    coach_success: true
---

# Task: LangGraph Thin Wrapper — Graph Export

## Description

Create the LangGraph `graph` object exported from `agent.py` as required by `langgraph.json`. This is a thin wrapper that exposes the generation pipeline as a LangGraph-compatible graph for `langgraph dev` and Docker Compose execution.

The graph does NOT implement the generation loop as LangGraph nodes/edges — the loop is plain Python (TASK-EP-007). The LangGraph graph wraps the startup + loop as a single invocable unit.

## Requirements

- Export `graph` from `agent.py` as a LangGraph `StateGraph` or `CompiledGraph`
- Compatible with `langgraph.json`: `{"graphs": {"agent": "agent.py:graph"}}`
- Graph invocation triggers: config load → startup → generation loop
- Support `langgraph dev` for development
- Support `docker compose up agent-loop` for production

## Acceptance Criteria

- [ ] `agent.py` exports a `graph` object
- [ ] `langgraph.json` references `"agent.py:graph"` correctly
- [ ] `langgraph dev` can start the pipeline
- [ ] Graph invocation runs the complete startup + generation sequence
- [ ] All modified files pass project-configured lint/format checks with zero errors

## Reference

- API contract: `docs/design/contracts/API-entrypoint.md` (LangGraph Wiring section)
- Architecture: `docs/architecture/ARCHITECTURE.md`

## Implementation Notes

Keep the LangGraph wrapper minimal. The graph has a single node that calls the startup + generation pipeline. LangSmith tracing is automatic through LangGraph runtime. If LangGraph requires a state schema, define a minimal `PipelineState` with input/output fields.
