---
complexity: 4
dependencies:
- TASK-EP-004
- TASK-EP-007
- TASK-EP-008
feature_id: FEAT-2CF1
id: TASK-EP-009
implementation_mode: task-work
parent_review: TASK-REV-9EDC
status: design_approved
task_type: feature
title: agent.py startup orchestration (steps 1-12)
wave: 4
---

# Task: agent.py Startup Orchestration

## Description

Wire the complete `agent.py` entrypoint that executes the 12-step startup sequence from the API contract, composing all modules built in previous tasks. This is the integration task that brings everything together.

## Requirements

Implement the startup sequence exactly as specified in API-entrypoint.md:

1. Load config via `load_config()` (TASK-EP-002)
2. Configure structured JSON logging (TASK-EP-003)
3. Set `LANGSMITH_PROJECT` env var (TASK-EP-004)
4. Resolve domain path (TASK-EP-004)
5. Parse and validate GOAL.md (external: goal-md-parser feature)
6. Check ChromaDB collection (TASK-EP-004)
7. Handle clean/resume output directory (TASK-EP-005, TASK-EP-006)
8. Build prompts — base + GOAL.md injection (external: agent-factories prompts/)
9. Create tools — `rag_retrieval` + `write_output` (external: langchain-tools feature)
10. Instantiate Player and Coach via factories (external: agent-factories feature)
11. Build generation targets from GOAL.md
12. Run generation loop (TASK-EP-007)

Export `graph` for LangGraph (TASK-EP-008).

### CLI Arguments
- `--resume`: Resume from checkpoint (default: fresh start)
- Parse via `argparse` or LangGraph input schema

## Acceptance Criteria

- [ ] All 12 startup steps executed in order (BDD: "Full startup sequence completes")
- [ ] Fail-fast on any validation error during steps 1-6
- [ ] Player and Coach agents instantiated via factories with correct tool assignments
- [ ] Tools list contains `rag_retrieval` and `write_output`
- [ ] Generation loop invoked with agents, targets, and generation config
- [ ] `--resume` flag supported
- [ ] `graph` exported for `langgraph.json`
- [ ] All modified files pass project-configured lint/format checks with zero errors

## Reference

- API contract: `docs/design/contracts/API-entrypoint.md` (complete Startup Sequence)
- BDD: "Full startup sequence completes and generation loop is invoked"

## Implementation Notes

This task wires modules — it creates minimal new logic. The main `agent.py` file should be ~100-150 lines of orchestration code calling functions from `config/`, `entrypoint/`, `agents/`, `tools/`, and `prompts/` modules.

External dependencies (goal-md-parser, agent-factories, langchain-tools) may be stubbed with interfaces if not yet implemented. Use Protocol or ABC to define expected interfaces.