# Transfer: docling output → MacBook (over Tailscale)

## Context

GB10 holds two separate sets of dataset-factory output. The dir names don't
make the domain obvious — the system prompt inside `train.jsonl` is the
authoritative tell.

| GB10 dir | Domain (from train.jsonl system prompt) | Size |
|---|---|---|
| `output/` | architect-agent | 16M |
| `output_backup_post_architect-agent_20260502-072937/` | architect-agent | 16M |
| `output_backup_pre_architect_20260429-154246/` | architect-agent | 380K |
| `output-run1-backup/` | GCSE English tutor | 169M |
| `output_backup_run1/` | GCSE English tutor | 170M |
| `output_backup_pre_rerun/` | GCSE English tutor | 170M |
| `output_gcse_rerun/` | GCSE English tutor (latest, richest rag) | 222M |

## Round 1 — architect dirs (already on Mac)

```bash
mkdir -p ~/Projects/agentic-dataset-factory-runs && \
rsync -avh --progress \
  richardwoollcott@promaxgb10-41b1:/home/richardwoollcott/Projects/appmilla_github/agentic-dataset-factory/output \
  richardwoollcott@promaxgb10-41b1:/home/richardwoollcott/Projects/appmilla_github/agentic-dataset-factory/output_backup_post_architect-agent_20260502-072937 \
  richardwoollcott@promaxgb10-41b1:/home/richardwoollcott/Projects/appmilla_github/agentic-dataset-factory/output_backup_pre_architect_20260429-154246 \
  ~/Projects/agentic-dataset-factory-runs/
```

## Round 2 — study-tutor (GCSE) latest run

Run on the MacBook:

```bash
rsync -avh --progress \
  richardwoollcott@promaxgb10-41b1:/home/richardwoollcott/Projects/appmilla_github/agentic-dataset-factory/output_gcse_rerun \
  ~/Projects/agentic-dataset-factory-runs/
```

Lands as `~/Projects/agentic-dataset-factory-runs/output_gcse_rerun/`.

If MagicDNS isn't resolving, swap `promaxgb10-41b1` for `100.84.90.91`.

## Verification on the Mac

```bash
head -c 400 ~/Projects/agentic-dataset-factory-runs/output_gcse_rerun/train.jsonl
# expect: "...expert GCSE English tutor supporting a Year 10 student..."
wc -l ~/Projects/agentic-dataset-factory-runs/output_gcse_rerun/{train,rejected}.jsonl \
      ~/Projects/agentic-dataset-factory-runs/output_gcse_rerun/rag_index/knowledge.jsonl
# expect: train=1736  rejected=457  rag=368
```
