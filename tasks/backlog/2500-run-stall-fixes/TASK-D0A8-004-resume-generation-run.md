---
id: TASK-D0A8-004
title: Resume generation run from checkpoint 1404
status: backlog
created: 2026-04-01T20:00:00Z
updated: 2026-04-01T20:00:00Z
priority: high
tags: [generation-run, resume, checkpoint]
task_type: implementation
complexity: 2
parent_review: TASK-REV-D0A8
feature_id: FEAT-D0A8
wave: 2
implementation_mode: manual
dependencies: [TASK-D0A8-001, TASK-D0A8-002, TASK-D0A8-003]
test_results:
  status: pending
  coverage: null
  last_run: null
---

# Task: Resume generation run from checkpoint 1404

## Description

Resume the 2500-target generation run from checkpoint 1404 on GB10. All Wave 1 fixes must be applied first (per-call timeout, lower Player temperature, GB10 run script).

## Pre-Resume Checklist

- [ ] TASK-D0A8-001 complete: per-call LLM timeout wired (300s)
- [ ] TASK-D0A8-002 complete: Player temperature set to 0.4
- [ ] TASK-D0A8-003 complete: GB10 setup verified, run script ready
- [ ] vLLM container running on GB10 (`docker logs -f vllm-agentic-factory`)
- [ ] Checkpoint file shows 1404: `cat output/.checkpoint`
- [ ] Output files exist and contain prior data: `wc -l output/train.jsonl output/rejected.jsonl`
- [ ] Config endpoint points to localhost:8002 (not Tailscale address)

## Execution

```bash
ssh promaxgb10-41b1
cd /path/to/agentic-dataset-factory
./scripts/run-on-gb10.sh
```

## Expected Outcomes

| Metric | Expected |
|--------|----------|
| Remaining targets | 1,094 (indices 1405-2499) |
| Estimated duration | 18-22 hours |
| Format gate failure rate | ~25-30% (improved from 41% via lower temperature) |
| Stalls from Mac sleep | 0 (running on GB10) |
| Per-call timeout fires | Should not fire under normal conditions (300s >> typical ~50s calls) |

## Monitoring During Run

```bash
# Reattach to tmux
tmux attach -t factory

# Check progress (from another terminal)
grep -c target_accepted output/logs/run-*.log
grep -c target_rejected output/logs/run-*.log
grep -c "format gate" output/logs/run-*.log

# Check vLLM health
docker logs --tail 20 vllm-agentic-factory
```

## Acceptance Criteria

- [ ] Run resumes from index 1405 (not from 0)
- [ ] Run completes all 2,500 targets (or runs until manually stopped)
- [ ] No stalls from process suspension
- [ ] Output files contain the additional accepted examples
- [ ] Format gate failure rate is tracked for comparison with pre-fix baseline (41%)
