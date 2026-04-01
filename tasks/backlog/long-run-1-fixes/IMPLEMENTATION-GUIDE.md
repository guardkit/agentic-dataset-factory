# Implementation Guide: Long Run 1 Fixes (FEAT-LR1)

**Parent review**: TASK-REV-649A
**Feature**: Long Run 1 pipeline fixes, prompt tuning, coverage gaps, and data cleaning

## Wave Breakdown

### Wave 1: Critical fixes before next run (4 parallel + 1 direct)

These tasks have no dependencies on each other and can be executed in parallel.

| Task | Title | Mode | Complexity |
|------|-------|------|------------|
| TASK-LR1-001 | Enable vLLM guided_json for Coach | task-work | 5 |
| TASK-LR1-002 | Post-generation validation gate | task-work | 3 |
| TASK-LR1-003 | Strengthen Coach prompt (shallow accepts) | task-work | 3 |
| TASK-LR1-004 | Strengthen Player prompt (metadata) | direct | 2 |
| TASK-LR1-010 | Clean Long Run 1 training data | task-work | 3 |

**Expected outcome**: Coach parse failures eliminated, 33 defective training entries caught/cleaned, Coach evaluation quality improved, Player metadata compliance improved.

### Wave 2: Tuning and coverage (depends on Wave 1 results)

| Task | Title | Mode | Complexity | Dependencies |
|------|-------|------|------------|-------------|
| TASK-LR1-005 | Increase essay max_turns to 4 | direct | 2 | LR1-001 |
| TASK-LR1-006 | Boost Grade 4 weighting | direct | 2 | — |
| TASK-LR1-007 | Lower Coach temperature to 0.1 | direct | 1 | LR1-001 |
| TASK-LR1-008 | Generate RAG entries for missing texts | task-work | 4 | — |
| TASK-LR1-009 | Increase multi-turn weighting | task-work | 3 | LR1-001, LR1-005 |
| TASK-LR1-011 | Review RAG misclassification | task-work | 3 | LR1-008 |

**Expected outcome**: Improved grade balance, curriculum coverage, multi-turn representation, and evaluation determinism.

## Prior Fixes Already in Production

From the superseded overnight-readiness feature (FEAT-OR):
- **TASK-OR-006** (retry message format fix) — `tasks/completed/TASK-OR-006/`
- **TASK-OR-007** (httpx.HTTPStatusError handling) — `tasks/completed/TASK-OR-007/`

These are fallback defences; LR1-001 guided_json should prevent the failures they mitigate.

## Execution Strategy

1. **Start Wave 1** — all 5 tasks can run in parallel
2. **Test batch (50-100 targets)** after Wave 1 completion to verify:
   - Coach parse failure rate drops to ~0
   - Accept rate remains >75%
   - No defective entries pass validation gate
3. **Start Wave 2** — respecting dependency ordering
4. **Full run (1000+ targets)** after Wave 2 completion

## Success Metrics

| Metric | Run 1 Baseline | Target |
|--------|---------------|--------|
| Accept rate | 83.4% | >90% |
| Coach parse failures | 245 | <5 |
| Defective entries in train.jsonl | 33 | 0 |
| Grade 4 representation | 3.9% | 12-15% |
| Multi-turn examples | 8.7% | 25-30% |
| RAG coverage (missing texts) | 3 missing | 0 missing |
