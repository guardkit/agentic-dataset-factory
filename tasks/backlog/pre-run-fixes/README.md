# Pre-Run Fixes (FEAT-PRF)

## Problem

The Phase 2 codebase (43 AutoBuild tasks, 6 features) has one confirmed code bug and three missing prerequisite files that block the first end-to-end generation run.

## Solution

Six remediation tasks organized into three execution waves:

1. **Wave 1** (P0): Fix the Player model creation bug, create `agent-config.yaml`, create `AGENTS.md`
2. **Wave 2** (P1): Run test suite for baseline, populate ChromaDB via ingestion pipeline
3. **Wave 3** (P2): Execute first end-to-end generation cycle

## Tasks

| ID | Title | Priority | Wave | Status |
|----|-------|----------|------|--------|
| TASK-PRF-001 | Fix Player create_model bug | P0 | 1 | backlog |
| TASK-PRF-002 | Create agent-config.yaml | P0 | 1 | backlog |
| TASK-PRF-003 | Create AGENTS.md | P0 | 1 | backlog |
| TASK-PRF-004 | Run test suite | P1 | 2 | backlog |
| TASK-PRF-005 | Run ingestion pipeline | P1 | 2 | backlog |
| TASK-PRF-006 | First end-to-end run | P2 | 3 | backlog |

## Origin

Created from `/task-review TASK-REV-A1B4` — analysis of pre-run verification findings.
