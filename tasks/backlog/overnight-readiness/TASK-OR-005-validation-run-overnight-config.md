---
id: TASK-OR-005
title: Validation run and overnight config
status: backlog
created: 2026-03-29T00:00:00Z
updated: 2026-03-29T11:00:00Z
priority: critical
tags: [validation, overnight, config, overnight-readiness]
task_type: implementation
complexity: 2
parent_review: TASK-REV-7617
feature_id: FEAT-OR
depends_on: [TASK-OR-001, TASK-OR-002, TASK-OR-006, TASK-OR-007]
wave: 3
implementation_mode: direct
test_results:
  status: pending
  coverage: null
  last_run: null
---

# Task: Validation Run and Overnight Config

## Problem

Need to confirm TASK-OR-001 (retry) and TASK-OR-002 (grade distribution) fixes
work correctly before committing to a 10-hour overnight run.

**IMPORTANT**: TASK-OR-006 (retry message format fix) and TASK-OR-007 (exception
handler fix) must be completed first. TASK-REV-R2A1 found that TASK-OR-001's retry
crashes the pipeline due to dual system messages in `ainvoke()` input. These two
fixes are prerequisites for a successful validation run.

## Steps

### 1. Clear Previous Output

```bash
# Back up existing output
cp -r output/ output_run12_backup/

# Clear for clean validation run
rm output/train.jsonl output/rejected.jsonl output/rag_index/knowledge.jsonl
```

### 2. Run Validation (20 targets, count=1)

```bash
python -m entrypoint.agent
```

Expected duration: ~34 minutes.

### 3. Verify Results

Check against baseline (Run 12):

| Metric | Run 12 (baseline) | Target | Pass Criteria |
|--------|-------------------|--------|---------------|
| Accepted | 16/20 (80%) | >= 18/20 (90%) | Retry recovers at least 2 failures |
| Coach JSON failures | 3/20 (15%) | <= 1/20 (5%) | Retry fixes role confusion |
| Grade diversity | 92.3% Grade 7 | < 40% Grade 7 | Round-robin distributes grades |
| Multi-turn essay | 50% compliant | — | Not addressed until TASK-OR-003 |

### 4. Review Output Quality

```bash
# Check grade distribution
python -c "
import json
grades = []
with open('output/train.jsonl') as f:
    for line in f:
        ex = json.loads(line)
        grades.append(ex['metadata'].get('grade_target'))
from collections import Counter
print(Counter(grades))
"

# Check rejection reasons
cat output/rejected.jsonl | python -c "
import sys, json
for line in sys.stdin:
    r = json.loads(line)
    print(f'  index={r[\"target_index\"]}: {r[\"reason\"][:80]}')
"
```

### 5. Configure Overnight Run

If validation passes, update agent-config.yaml or use CLI override for overnight:

- **Option**: All 20 categories at count=17 each = 340 targets, ~10 hours
- **Alternative**: Prioritise under-represented texts (a_christmas_carol,
  power_conflict_poetry) with higher counts

### 6. Start Overnight Run

```bash
# Use nohup or tmux for unattended execution
nohup python -m entrypoint.agent > overnight_run.log 2>&1 &
```

## Acceptance Criteria

- [ ] Validation run completes successfully (no pipeline crashes)
- [ ] Rejection rate <= 5% (retry working)
- [ ] Grade distribution is diverse (not all Grade 7)
- [ ] Overnight config set to appropriate counts
- [ ] Overnight run started with output logging
