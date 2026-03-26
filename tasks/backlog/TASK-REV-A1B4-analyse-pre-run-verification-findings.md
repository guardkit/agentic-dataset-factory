---
id: TASK-REV-A1B4
title: Analyse pre-run verification findings
status: review_complete
created: 2026-03-22T00:00:00Z
updated: 2026-03-22T00:00:00Z
priority: critical
tags: [review, verification, pre-run, phase-2]
complexity: 5
task_type: review
decision_required: true
review_results:
  mode: architectural
  depth: standard
  score: 95
  findings_count: 6
  recommendations_count: 6
  decision: implement
  report_path: .claude/reviews/TASK-REV-A1B4-review-report.md
  completed_at: 2026-03-22T00:00:00Z
test_results:
  status: pending
  coverage: null
  last_run: null
---

# Task: Analyse Pre-Run Verification Findings

## Description

Analyse the findings from the Claude Desktop pre-run verification review of the agentic-dataset-factory Phase 2 codebase. The review document is at `docs/reviews/verification/TASK-REV-PRE-RUN-agentic-dataset-factory.md` and was produced during a session examining runtime readiness of the 43 AutoBuild-generated tasks across 6 features.

## Source Document

`docs/reviews/verification/TASK-REV-PRE-RUN-agentic-dataset-factory.md`

## Key Findings to Analyse

### 1. CONFIRMED BUG — Player Model Creation (P0)
- **Location**: `agents/player.py` local `create_model()` returns `"local:model-name"` string
- **Problem**: `"local"` is not a valid `init_chat_model` provider — blocks Player instantiation
- **Coach works correctly** via shared `agents/model_factory.py` which maps `local` → `openai`
- **Root cause**: Integration gap between TASK-AF-003 (Player) and TASK-AF-004 (Coach)
- **Proposed fix**: Replace local `create_model()` with import from `agents.model_factory`
- **Decision needed**: Verify the bug against actual codebase and SDK, then create implementation task

### 2. Missing Files — Must Create Before Running (P0)
- `agent-config.yaml` — config loader fails without it (Step 1 of startup)
- `AGENTS.md` — referenced by both agent factories for memory injection
- ChromaDB collection — startup Step 5 verification fails without populated data
- `.env` — optional, for LangSmith tracing

### 3. Startup Dependency Chain (12 steps)
- Steps 1, 5, and 10 will fail without the prerequisites above
- Full dependency chain documented in review Section 3

### 4. Test Suite Assessment
- 40+ test files across all modules
- Recommended execution order: unit → smoke → seam → integration
- Decision needed: Run test suite to verify AutoBuild output before fixing anything

### 5. Architecture Observations
- AutoBuild quality assessed as excellent (clean separation, resilience patterns, validation)
- Player/Coach model factory inconsistency is the only confirmed code bug
- Ingestion pipeline is separate CLI by design (Stage 0 vs Stage 1)

### 6. Port Allocation (GB10)
- Port 8002 (vLLM serve) required for Player + Coach inference
- Other ports (8000, 8001, 8003) not required for first run

## Acceptance Criteria

- [ ] Review findings verified against actual codebase state
- [ ] Player model creation bug confirmed or refuted by inspecting `agents/player.py`
- [ ] Missing files inventory validated (agent-config.yaml, AGENTS.md, ChromaDB)
- [ ] Decision made on priority ordering of remediation tasks
- [ ] Implementation tasks created for each confirmed finding (if accepted)
- [ ] Risk matrix reviewed and any additional risks identified

## Decisions Required

1. **Accept findings?** — Are the review conclusions accurate against current codebase?
2. **Task ordering** — Which remediation tasks to create first (bug fix vs missing files vs tests)?
3. **Model strategy** — Should Player and Coach use same model or different models?
4. **Test-first approach** — Run existing tests before or after applying fixes?

## Suggested Follow-Up Tasks (if findings accepted)

| Priority | Task | Description |
|----------|------|-------------|
| P0 | TASK-FIX-MODEL | Fix Player `create_model()` to use shared `model_factory` |
| P0 | TASK-CREATE-CONFIG | Create `agent-config.yaml` from Pydantic schema |
| P0 | TASK-CREATE-AGENTS-MD | Create `AGENTS.md` with Player/Coach boundaries |
| P1 | TASK-VERIFY-TESTS | Run full test suite and document results |
| P1 | TASK-INGEST | Run ingestion pipeline to populate ChromaDB |
| P2 | TASK-FIRST-RUN | Execute first end-to-end generation cycle |

## Implementation Notes

This is a review/analysis task. Use `/task-review TASK-REV-A1B4` to execute the review, then create implementation tasks for accepted findings.

## Test Execution Log

[Automatically populated by /task-work]
