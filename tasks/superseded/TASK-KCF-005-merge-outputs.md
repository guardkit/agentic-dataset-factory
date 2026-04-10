---
id: TASK-KCF-005
title: Merge outputs from reasoning run and direct re-run
status: backlog
created: 2026-04-05T19:30:00Z
updated: 2026-04-05T19:30:00Z
priority: high
tags: [output-merge, data-combination, pipeline-output]
task_type: implementation
complexity: 3
parent_review: TASK-REV-3A86
feature_id: FEAT-KCF
wave: 3
implementation_mode: direct
dependencies: [TASK-KCF-004]
test_results:
  status: pending
  coverage: null
  last_run: null
---

# Task: Merge outputs from reasoning run and direct re-run

## Description

Combine the high-quality reasoning output from the original run with the new direct
output from the fix re-run into a single coherent dataset.

### Source Files

**From original run** (`output_backup_run1/`):
- `train.jsonl` — 1,716 reasoning examples (KEEP)
- `rejected.jsonl` — 220 reasoning rejections (KEEP reasoning only)
- `rag_index/knowledge.jsonl` — 172 examples (DISCARD — mixed quality)

**From fix re-run** (`output/`):
- `train.jsonl` — ~80 encouragement examples (KEEP — append to original)
- `rag_index/knowledge.jsonl` — ~450 knowledge examples (KEEP — new primary)
- `rejected.jsonl` — ~95 direct rejections (KEEP)

### Merge Steps

```bash
# Step 1: Start with original reasoning output
cp output_backup_run1/train.jsonl output_combined/train.jsonl

# Step 2: Append new encouragement examples (direct/behaviour from fix run)
# These go to train.jsonl, not knowledge.jsonl
cat output/train.jsonl >> output_combined/train.jsonl

# Step 3: Use new knowledge output (replaces old mixed-quality)
cp output/rag_index/knowledge.jsonl output_combined/rag_index/knowledge.jsonl

# Step 4: Merge rejected files
# Keep reasoning rejections from original run
python3 -c "
import json
# Extract reasoning rejections from original run
with open('output_backup_run1/rejected.jsonl') as f:
    original = [json.loads(l) for l in f]
reasoning_rejects = [r for r in original if r['type'] == 'reasoning']
# Read new direct rejections
with open('output/rejected.jsonl') as f:
    new_rejects = [json.loads(l) for l in f]
# Combine
with open('output_combined/rejected.jsonl', 'w') as f:
    for r in reasoning_rejects + new_rejects:
        f.write(json.dumps(r) + '\n')
print(f'Combined: {len(reasoning_rejects)} reasoning + {len(new_rejects)} direct = {len(reasoning_rejects) + len(new_rejects)} total')
"
```

### Validation Steps

```bash
# Count lines
echo "=== Line counts ==="
wc -l output_combined/train.jsonl
wc -l output_combined/rag_index/knowledge.jsonl
wc -l output_combined/rejected.jsonl

# Validate JSON
echo "=== JSON validation ==="
python3 -c "
import json
for f in ['output_combined/train.jsonl', 'output_combined/rag_index/knowledge.jsonl', 'output_combined/rejected.jsonl']:
    with open(f) as fh:
        lines = fh.readlines()
    for i, line in enumerate(lines):
        json.loads(line)  # Will raise on invalid JSON
    print(f'{f}: {len(lines)} valid JSON lines')
"

# Verify layer routing
echo "=== Layer routing check ==="
python3 -c "
import json
with open('output_combined/train.jsonl') as f:
    train = [json.loads(l) for l in f]
with open('output_combined/rag_index/knowledge.jsonl') as f:
    knowledge = [json.loads(l) for l in f]

train_layers = {e['metadata']['layer'] for e in train}
knowledge_layers = {e['metadata']['layer'] for e in knowledge}
print(f'train.jsonl layers: {train_layers}')
print(f'knowledge.jsonl layers: {knowledge_layers}')

# train should be behaviour only, knowledge should be knowledge only
assert train_layers == {'behaviour'}, f'Unexpected layers in train: {train_layers}'
assert knowledge_layers == {'knowledge'}, f'Unexpected layers in knowledge: {knowledge_layers}'
print('Layer routing: CORRECT')
"

# Final stats
echo "=== Final dataset stats ==="
python3 -c "
import json
with open('output_combined/train.jsonl') as f:
    train = [json.loads(l) for l in f]
with open('output_combined/rag_index/knowledge.jsonl') as f:
    knowledge = [json.loads(l) for l in f]
with open('output_combined/rejected.jsonl') as f:
    rejected = [json.loads(l) for l in f]
total_accepted = len(train) + len(knowledge)
total = total_accepted + len(rejected)
print(f'Accepted: {total_accepted} (train={len(train)}, knowledge={len(knowledge)})')
print(f'Rejected: {len(rejected)}')
print(f'Total: {total}')
print(f'Rejection rate: {len(rejected)/total*100:.1f}%')
"
```

### Expected Combined Output

| File | Count | Content |
|------|-------|---------|
| train.jsonl | ~1,800 | 1,716 reasoning + ~80 encouragement |
| knowledge.jsonl | ~450 | New knowledge examples (properly evaluated) |
| rejected.jsonl | ~315 | 220 reasoning + ~95 direct |
| **Total accepted** | **~2,250** | |
| **Rejection rate** | **~12%** | |

### Final Step: Replace output/

```bash
# Once validated, replace the output directory
rm -rf output_final_backup/
mv output/ output_final_backup/
mv output_combined/ output/
```

## Acceptance Criteria

- [ ] Combined train.jsonl has ~1,800 examples (reasoning + encouragement)
- [ ] Combined knowledge.jsonl has ~450 examples (new, properly evaluated)
- [ ] Combined rejected.jsonl has ~315 examples (reasoning + new direct)
- [ ] All JSON validates successfully
- [ ] Layer routing correct (behaviour→train, knowledge→knowledge)
- [ ] Combined rejection rate ~10-15%
- [ ] Original output backed up
