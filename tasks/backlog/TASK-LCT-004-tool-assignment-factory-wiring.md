---
id: TASK-LCT-004
title: "Implement tool assignment and create_tools factory wiring"
task_type: feature
parent_review: TASK-REV-723B
feature_id: FEAT-LCT
wave: 3
implementation_mode: direct
complexity: 3
dependencies:
  - TASK-LCT-002
  - TASK-LCT-003
status: pending
priority: high
tags: [langchain-tools, factory, tool-assignment]
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
