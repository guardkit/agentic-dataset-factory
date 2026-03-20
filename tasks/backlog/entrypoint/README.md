# Feature: Entrypoint — Config Loading, Validation, and Generation Loop Orchestration

## Problem

The agentic-dataset-factory pipeline needs a single entrypoint (`agent.py`) that loads configuration, validates all prerequisites, instantiates Player and Coach agents via DeepAgents SDK, and orchestrates the sequential generation loop with overnight-run resilience (retry, checkpoint/resume, per-target timeout).

## Solution

Pydantic-based config loading with DeepAgents SDK orchestration. The entrypoint runs a 12-step startup sequence (config → logging → domain → GOAL.md → ChromaDB → agents → loop) and exports a LangGraph `graph` for runtime compatibility.

## Tasks

| Task | Name | Complexity | Wave |
|------|------|-----------|------|
| TASK-EP-001 | Pydantic config models | 3 | 1 |
| TASK-EP-002 | Config loader | 3 | 1 |
| TASK-EP-003 | Structured JSON logging | 2 | 1 |
| TASK-EP-004 | Domain resolution + ChromaDB | 3 | 2 |
| TASK-EP-005 | Checkpoint/resume + lock file | 4 | 2 |
| TASK-EP-006 | Output directory management | 2 | 2 |
| TASK-EP-007 | Generation loop (Player-Coach) | 6 | 3 |
| TASK-EP-008 | LangGraph thin wrapper | 3 | 3 |
| TASK-EP-009 | Startup orchestration | 4 | 4 |
| TASK-EP-010 | Integration tests | 4 | 4 |

## Dependencies

- **Agent Factories** (TASK-AF-001..011): ModelConfig, create_player, create_coach
- **LangChain Tools** (TASK-LCT-001..005): rag_retrieval, write_output
- **GOAL.md Parser** (TASK-DC-001..005): parse_goal_md, GoalConfig

## Key ADRs

- ADR-ARCH-006: Sequential generation
- ADR-ARCH-007: Structured JSON logging
- ADR-ARCH-008: Start fresh on re-run
- ADR-ARCH-010: Overnight run resilience

## BDD Coverage

44 scenarios in `features/entrypoint/entrypoint.feature` (8 smoke, 10 boundary, 10 negative, 16 edge cases).

## Review Origin

Planned via TASK-REV-9EDC. Feature ID: FEAT-2CF1.
