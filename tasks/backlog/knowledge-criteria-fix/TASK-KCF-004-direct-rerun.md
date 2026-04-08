---
id: TASK-KCF-004
title: Full direct-only re-run (625 targets)
status: backlog
created: 2026-04-05T19:30:00Z
updated: 2026-04-05T19:30:00Z
priority: high
tags: [pipeline-run, direct-targets, re-run]
task_type: implementation
complexity: 2
parent_review: TASK-REV-3A86
feature_id: FEAT-KCF
wave: 3
implementation_mode: manual
dependencies: [TASK-KCF-003]
test_results:
  status: pending
  coverage: null
  last_run: null
---

# Task: Full direct-only re-run (625 targets)

## Description

After smoke test passes (KCF-003), run the full 625 direct targets with layer-aware criteria.

### Pre-run Checklist

- [ ] KCF-003 smoke test passed with >80% acceptance
- [ ] Current output backed up: `cp -r output/ output_backup_run1/`
- [ ] `GOAL-direct-only.md` has layer-aware criteria from KCF-001
- [ ] vLLM server running and healthy
- [ ] Sufficient disk space for output

### Run Command

```bash
# Activate venv
source .venv/bin/activate

# Backup current output first
cp -r output/ output_backup_run1/

# Back up production GOAL.md
cp domains/gcse-english-tutor/GOAL.md domains/gcse-english-tutor/GOAL.md.bak

# Swap in direct-only variant (agent.py hardcodes GOAL.md path)
cp domains/gcse-english-tutor/GOAL-direct-only.md domains/gcse-english-tutor/GOAL.md

# Run via tmux (recommended for long runs)
./scripts/run-on-gb10.sh

# Or run directly
python agent.py

# Restore original GOAL.md when done
cp domains/gcse-english-tutor/GOAL.md.bak domains/gcse-english-tutor/GOAL.md
```

### Expected Results

| Metric | Expected |
|--------|----------|
| Total targets | 625 |
| Acceptance rate | >80% (~530 accepted) |
| Runtime | ~8 hours |
| knowledge.jsonl | ~450 examples |
| train.jsonl | ~80 examples (encouragement only) |
| rejected.jsonl | ~95 examples |

### Monitoring

```bash
# Tail progress
tail -f output/logs/run-*.log | grep -E "(progress|target_accepted|target_rejected)"
```

## Acceptance Criteria

- [ ] Run completes for all 625 targets
- [ ] Acceptance rate >80%
- [ ] Output files written to correct locations
- [ ] No pipeline crashes or lock issues
- [ ] Output backed up before run started
