---
id: TASK-LCT-004
title: Implement tool assignment and create_tools factory wiring
task_type: feature
parent_review: TASK-REV-723B
feature_id: FEAT-LCT
wave: 3
implementation_mode: direct
complexity: 3
dependencies:
- TASK-LCT-002
- TASK-LCT-003
status: in_review
priority: high
tags:
- langchain-tools
- factory
- tool-assignment
autobuild_state:
  current_turn: 1
  max_turns: 35
  worktree_path: /Users/richardwoollcott/Projects/appmilla_github/agentic-dataset-factory/.guardkit/worktrees/FEAT-945D
  base_branch: main
  started_at: '2026-03-20T20:56:00.071902'
  last_updated: '2026-03-20T21:05:42.164163'
  turns:
  - turn: 1
    decision: approve
    feedback: null
    timestamp: '2026-03-20T20:56:00.071902'
    player_summary: 'Implemented tool_factory.py with two public factory functions:
      create_player_tools() returns [rag_retrieval, write_output] bound to provided
      config (collection_name, output_dir, metadata_schema); create_coach_tools()
      returns [] with no parameters (enforcing D5 tool access asymmetry). Input validation
      is fail-fast: collection_name, output_dir, and metadata_schema are all validated
      before any tool is created. Coach factory signature has zero parameters, making
      it structurally impossible to inject '
    player_success: true
    coach_success: true
---

# Task: Implement tool assignment and create_tools factory wiring

## Description

Implement the top-level `create_tools()` factory function that creates both tools with the correct configuration and enforces the tool assignment invariant: Player gets `[rag_retrieval, write_output]`, Coach gets `[]` (empty — D5).

## Deliverables

1. `src/tools/factory.py` — Top-level factory
   - `create_player_tools(collection_name: str, output_dir: Path, metadata_schema: list[MetadataField]) -> list[Callable]`
   - `create_coach_tools() -> list[Callable]` (always returns `[]`)
2. Update `src/tools/__init__.py` — Export factory functions

## Acceptance Criteria

- [ ] `create_player_tools()` returns `[rag_retrieval, write_output]` — exactly 2 tools
- [ ] `create_coach_tools()` returns `[]` — always empty list
- [ ] Coach cannot access rag_retrieval or write_output through any code path
- [ ] Tools are properly bound to their configuration (collection name, output dir, schema)
- [ ] Factory validates inputs (non-empty collection name, valid output dir path)
- [ ] All modified files pass project-configured lint/format checks with zero errors

## Reference

- API contract: `docs/design/contracts/API-tools.md` (Tool Assignment table)
- Generation contract: `docs/design/contracts/API-generation.md` (Player/Coach factories)
- BDD scenario: "Coach agent is created with an empty tools list" (@negative @smoke)

## Implementation Notes

- This is the glue layer — delegates to `create_rag_retrieval_tool` and `create_write_output_tool`
- Keep it thin — validation of tool-specific params happens in individual factories
- The Coach tools function exists to make the D5 invariant explicit and testable
