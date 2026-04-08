# Implementation Guide: Knowledge-Layer Criteria Fix

## Execution Strategy

### Wave 1: GOAL.md Changes (parallel)

| Task | Description | Method | Est. Time |
|------|-------------|--------|-----------|
| KCF-001 | Add layer-aware criteria to GOAL.md | task-work | 30 min |
| KCF-002 | Create GOAL-direct-only.md variant | direct | 15 min |

**KCF-001 and KCF-002** can start in parallel but KCF-002 must incorporate KCF-001's
criteria changes before completion.

### Wave 2: Validation

| Task | Description | Method | Est. Time |
|------|-------------|--------|-----------|
| KCF-003 | Smoke test (10 direct targets) | direct | 15 min |

**Gate**: KCF-003 must pass (>80% acceptance, 0 socratic blocks) before proceeding.

### Wave 3: Production Run + Merge (sequential)

| Task | Description | Method | Est. Time |
|------|-------------|--------|-----------|
| KCF-004 | Full direct-only re-run (625 targets) | manual | ~8 hours |
| KCF-005 | Merge outputs from both runs | direct | 30 min |
| KCF-006 | Investigate Coach refusals | task-work | 1 hour |

**KCF-004 → KCF-005** are strictly sequential.
**KCF-006** is independent and can run in parallel with KCF-004.

## Critical Path

```
KCF-001 → KCF-002 → KCF-003 → KCF-004 → KCF-005
                                    ↕
                                 KCF-006 (parallel)
```

**Total estimated wall time: ~9.5 hours** (dominated by KCF-004 pipeline run)

## Risk Mitigation

| Risk | Mitigation | Fallback |
|------|------------|----------|
| Parser can't handle two criteria tables | Use single table with text annotation | Quick N/A fix as stopgap |
| Smoke test fails (<60% acceptance) | Inspect Coach prompt, check criteria injection | Debug before proceeding |
| Full run crashes mid-way | Pipeline has checkpoint/resume support | `--resume` flag |
| Merge produces invalid output | Validation script in KCF-005 | Re-run merge steps |

## Pre-flight Checklist

Before starting any tasks:

- [ ] vLLM server running and healthy on `localhost:8002`
- [ ] ChromaDB available for RAG retrieval
- [ ] Sufficient disk space (~500MB for output)
- [ ] `output/` directory backed up: `cp -r output/ output_backup_run1/`
- [ ] Current branch clean: `git stash` any uncommitted changes
