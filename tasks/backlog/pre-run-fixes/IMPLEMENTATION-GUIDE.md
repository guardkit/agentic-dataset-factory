# Implementation Guide: Pre-Run Fixes (FEAT-PRF)

## Source Review

- Review task: TASK-REV-A1B4
- Review report: `.claude/reviews/TASK-REV-A1B4-review-report.md`
- Source verification: `docs/reviews/verification/TASK-REV-PRE-RUN-agentic-dataset-factory.md`

## Wave Breakdown

### Wave 1: Critical Blockers (3 tasks — parallel)

These three tasks are independent and can run in parallel. They address the P0 blockers that prevent any startup.

| Task | Title | Mode | Complexity |
|------|-------|------|------------|
| TASK-PRF-001 | Fix Player `create_model()` bug | task-work | 2 |
| TASK-PRF-002 | Create `agent-config.yaml` | direct | 2 |
| TASK-PRF-003 | Create `AGENTS.md` | direct | 2 |

**No file conflicts between tasks — safe for parallel execution.**

### Wave 2: Validation (2 tasks — parallel after Wave 1)

| Task | Title | Mode | Complexity | Depends On |
|------|-------|------|------------|------------|
| TASK-PRF-004 | Run test suite | task-work | 3 | TASK-PRF-001 |
| TASK-PRF-005 | Run ingestion pipeline | manual | 4 | TASK-PRF-002 |

**TASK-PRF-004 depends on TASK-PRF-001** (test baseline before/after fix).
**TASK-PRF-005 depends on TASK-PRF-002** (needs config for domain resolution).

### Wave 3: End-to-End (1 task — sequential)

| Task | Title | Mode | Complexity | Depends On |
|------|-------|------|------------|------------|
| TASK-PRF-006 | First end-to-end run | manual | 5 | All Wave 1 + TASK-PRF-005 |

## Execution Strategy

```
Wave 1 (parallel):  PRF-001 ─┐
                    PRF-002 ─┤
                    PRF-003 ─┘
                              │
Wave 2 (parallel):  PRF-004 ─┤ (after PRF-001)
                    PRF-005 ─┘ (after PRF-002, requires GB10)
                              │
Wave 3 (sequential): PRF-006 ─  (after all above, requires GB10)
```

## Implementation Modes

- **task-work**: PRF-001, PRF-004 — use `/task-work` for full quality gates
- **direct**: PRF-002, PRF-003 — simple file creation, no complex logic
- **manual**: PRF-005, PRF-006 — require GB10 hardware, human-operated
