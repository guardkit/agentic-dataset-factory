# GB10 Server Setup — Agentic Dataset Factory

Run the generation loop on `promaxgb10-41b1` to avoid laptop power
management suspensions that stalled the 2500-run.

## Prerequisites

- SSH access to `promaxgb10-41b1` (via Tailscale or direct LAN)
- Python 3.14 available on GB10
- vLLM Docker container `vllm-agentic-factory` running with
  `Qwen/Qwen3.5-35B-A3B-FP8` on port 8002
- ChromaDB data synced from Mac (see below)

## 1. Sync Project to GB10

```bash
# From Mac — rsync the project (excluding large/generated files)
rsync -avz --exclude '.venv' --exclude '__pycache__' \
    --exclude 'chroma_data' --exclude 'output' \
    ~/Projects/appmilla_github/agentic-dataset-factory/ \
    promaxgb10-41b1:~/agentic-dataset-factory/
```

## 2. Sync ChromaDB Data

```bash
# From Mac — sync the ChromaDB collection
rsync -avz ~/Projects/appmilla_github/agentic-dataset-factory/chroma_data/ \
    promaxgb10-41b1:~/agentic-dataset-factory/chroma_data/
```

## 3. Python Environment on GB10

```bash
ssh promaxgb10-41b1
cd ~/agentic-dataset-factory

# Create virtual environment (first time only)
python3.14 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

## 4. Verify vLLM

```bash
# Check vLLM is responding
curl -sf http://localhost:8002/v1/models | python -m json.tool

# Expected: JSON listing the loaded model
```

If vLLM is not running, start the Docker container:

```bash
docker start vllm-agentic-factory

# Wait for model to load (check logs)
docker logs -f vllm-agentic-factory
# Look for: "INFO: Application startup complete"
```

## 5. Config Changes for GB10

Edit `agent-config.yaml` to use localhost (avoids Tailscale latency and
stale TCP connections):

```yaml
player:
  endpoint: http://localhost:8002/v1    # was: http://promaxgb10-41b1:8002/v1

coach:
  endpoint: http://localhost:8002/v1    # was: http://promaxgb10-41b1:8002/v1
```

## 6. Running with tmux

```bash
# Create a persistent tmux session
tmux new -s factory

# Inside tmux — activate venv and run
source .venv/bin/activate
python agent.py --resume 2>&1 | tee output/logs/run-$(date +%Y%m%d-%H%M%S).log

# Detach (process continues running): Ctrl-B D
# Reattach later:
tmux attach -t factory
```

Or use the provided script:

```bash
./scripts/run-on-gb10.sh
```

## 7. Checkpoint Resume

The generation loop writes a `.checkpoint` file to `output/` after each
accepted target. On restart with `--resume`:

1. Reads the checkpoint value (last completed target index)
2. Skips to `checkpoint + 1`
3. Opens output files in append mode (no data loss)

```bash
# Check current checkpoint
cat output/.checkpoint

# Resume from where it left off
python agent.py --resume
```

## 8. Monitoring

```bash
# In a separate SSH session or tmux pane:

# Watch application logs
tail -f output/logs/run-*.log

# Check vLLM container health
docker logs -f vllm-agentic-factory

# Count accepted targets
grep -c target_accepted output/logs/run-*.log

# Count rejected targets
grep -c target_rejected output/logs/run-*.log
```

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| `Connection refused` on port 8002 | vLLM container stopped | `docker start vllm-agentic-factory` |
| `TimeoutError` on LLM calls | Model overloaded or OOM | Check `docker logs`, may need to restart |
| Checkpoint not advancing | All targets being rejected | Check Coach verdict logs for rejection reasons |
| `FileNotFoundError: chroma_data` | ChromaDB not synced | Re-run rsync step 2 |
