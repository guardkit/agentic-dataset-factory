# Implementation Guide: Seventh Run Fixes (FEAT-TRF7)

## Origin

Review: TASK-REV-TRF7 (Analyse seventh run findings)
Report: `.claude/reviews/TASK-REV-TRF7-review-report.md`

## Problem Statement

Run 7 achieved correct Player-Coach architecture (Player: 1 tool, Coach: 0 tools) but 0/1 targets accepted due to:
1. Think blocks 94% unclosed (33 opens, 2 closes)
2. `normalise_think_closing_tags` not called before JSON extraction in the generation loop
3. No explicit `max_tokens` set, risking silent truncation

## Execution Strategy

### Wave 1: Blocking Fixes (Parallel)

All three tasks can be executed in parallel -- they modify different files with no conflicts.

| Task | Description | Files | Effort |
|------|-------------|-------|--------|
| TASK-TRF-020 | Call normaliser before JSON extraction | `entrypoint/generation_loop.py` | 15 min |
| TASK-TRF-021 | Handle missing close tags (EOF pattern) | `synthesis/validator.py` | 30 min |
| TASK-TRF-022 | Set explicit max_tokens on models | `agents/model_factory.py`, `config/models.py` | 10 min |

**Workspace names** (for Conductor parallel execution):
- `seventh-run-fixes-wave1-1` (TRF-020)
- `seventh-run-fixes-wave1-2` (TRF-021)
- `seventh-run-fixes-wave1-3` (TRF-022)

### Wave 2: Observability (Sequential)

| Task | Description | Files | Effort |
|------|-------------|-------|--------|
| TASK-TRF-023 | Improve extraction failure logging | `entrypoint/generation_loop.py` | 15 min |

**Note**: TRF-023 modifies the same file as TRF-020, so it must run after Wave 1 completes.

## File Conflict Matrix

| File | TRF-020 | TRF-021 | TRF-022 | TRF-023 |
|------|---------|---------|---------|---------|
| `entrypoint/generation_loop.py` | MODIFY | - | - | MODIFY |
| `synthesis/validator.py` | - | MODIFY | - | - |
| `agents/model_factory.py` | - | - | MODIFY | - |
| `config/models.py` | - | - | MODIFY | - |

## Verification Plan

After all fixes:
1. Run `pytest tests/ -v` -- all existing tests must pass
2. Run `pytest entrypoint/tests/ -v` -- generation loop tests must pass
3. Run `pytest synthesis/tests/ -v` -- validator tests must pass
4. Re-run pipeline with 1 target: expect 1/1 accepted
5. If successful: overnight run with 1,000 targets
