---
id: TASK-PRF-003
title: Create AGENTS.md with Player/Coach boundaries
status: completed
created: 2026-03-22T00:00:00Z
updated: 2026-03-22T12:00:00Z
completed: 2026-03-22T12:05:00Z
completed_location: tasks/completed/TASK-PRF-003/
priority: critical
tags: [config, agents, memory, P0]
complexity: 2
parent_review: TASK-REV-A1B4
feature_id: FEAT-PRF
wave: 1
implementation_mode: direct
dependencies: []
test_results:
  status: pass
  coverage: N/A
  last_run: 2026-03-22T12:00:00Z
---

# Task: Create AGENTS.md

## Description

Create the `AGENTS.md` file at the repo root with ALWAYS/NEVER/ASK boundaries for Player and Coach agents, following the DeepAgents exemplar pattern. Both `create_player()` and `create_coach()` pass `memory=["./AGENTS.md"]` to `create_deep_agent()`. Missing file may cause runtime error at startup Step 10.

## Files to Create

- `AGENTS.md`

## Content

The file must define:
- **Player Agent** boundaries: tool usage rules (`rag_retrieval`, `write_output`), content generation rules, metadata requirements
- **Coach Agent** boundaries: D5 evaluation-only invariant (no tools, no files), JSON verdict rules, evaluation criteria

Template provided in the verification review document at `docs/reviews/verification/TASK-REV-PRE-RUN-agentic-dataset-factory.md` Section 2.2.

## Acceptance Criteria

- [x] File exists at `./AGENTS.md` (repo root)
- [x] Contains ALWAYS/NEVER/ASK sections for Player agent
- [x] Contains ALWAYS/NEVER/ASK sections for Coach agent
- [x] Player boundaries reference tool usage (`rag_retrieval`, `write_output`)
- [x] Coach boundaries enforce D5 evaluation-only invariant (no tools, no files)

## Test Execution Log

- 2026-03-22: File `AGENTS.md` created at repo root from verification review template (Section 2.2)
- Verification: file exists, 6 ALWAYS/NEVER/ASK sections present, tool references confirmed, D5 invariant enforced
