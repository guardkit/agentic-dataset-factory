---
id: TASK-KCF-003
title: Smoke test layer-aware criteria with 10 direct targets
status: backlog
created: 2026-04-05T19:30:00Z
updated: 2026-04-05T19:30:00Z
priority: high
tags: [testing, smoke-test, direct-targets, validation]
task_type: implementation
complexity: 2
parent_review: TASK-REV-3A86
feature_id: FEAT-KCF
wave: 2
implementation_mode: direct
dependencies: [TASK-KCF-001, TASK-KCF-002]
test_results:
  status: pending
  coverage: null
  last_run: null
---

# Task: Smoke test layer-aware criteria with 10 direct targets

## Description

Before committing to an 8-hour re-run, validate the fix with a minimal test run.

### Steps

1. Create `GOAL-test-direct.md` from `GOAL-direct-only.md` with reduced counts:
   - 2 categories (e.g., Terminology + Character knowledge)
   - 5 targets each = 10 total
   - Estimated runtime: ~15 minutes

2. Run the pipeline:
   ```bash
   # Activate venv
   source .venv/bin/activate

   # Back up production GOAL.md
   cp domains/gcse-english-tutor/GOAL.md domains/gcse-english-tutor/GOAL.md.bak

   # Swap in test variant (agent.py hardcodes GOAL.md path)
   cp domains/gcse-english-tutor/GOAL-test-direct.md domains/gcse-english-tutor/GOAL.md

   # Run (default is fresh start; use --resume to continue a previous run)
   python agent.py

   # Restore original GOAL.md when done
   cp domains/gcse-english-tutor/GOAL.md.bak domains/gcse-english-tutor/GOAL.md
   ```

3. Verify results:
   - Acceptance rate should be >80% (vs current 33% for direct)
   - Accepted examples should be factual, NOT forced-Socratic
   - Coach verdicts should evaluate `completeness` not `socratic_approach`
   - Knowledge examples should route to `output/rag_index/knowledge.jsonl`
   - No `socratic_approach` blocking issues in `rejected.jsonl`

4. Inspect Coach verdicts in logs:
   ```bash
   grep "criteria_met" output/logs/*.log | head -20
   ```
   - Should see `completeness`, `factual_accuracy`, `age_appropriate`, `mark_scheme_aligned`
   - Should NOT see `socratic_approach` for direct examples

### Pass/Fail Criteria

| Metric | Pass | Fail |
|--------|------|------|
| Acceptance rate | >80% | <60% |
| socratic_approach blocks | 0 | >0 |
| Knowledge routing | All direct/knowledge to knowledge.jsonl | Any misrouted |
| Coach criteria keys | Layer-appropriate | Old universal criteria |

### If Test Fails

- Check if GOAL.md parser handled the new criteria format correctly
- Inspect Coach prompt: is it seeing the layer-specific criteria?
- Check if Coach is ignoring the layer routing instruction
- Report findings before proceeding to KCF-004

## Acceptance Criteria

- [ ] Test run completes with 10 targets
- [ ] Acceptance rate >80%
- [ ] Zero socratic_approach blocking issues
- [ ] Coach uses layer-appropriate criteria
- [ ] Results documented (paste summary output)
