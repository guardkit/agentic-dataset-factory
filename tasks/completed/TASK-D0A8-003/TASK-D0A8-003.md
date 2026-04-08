---
id: TASK-D0A8-003
title: GB10 setup instructions and run script
status: completed
created: 2026-04-01T20:00:00Z
updated: 2026-04-02T08:00:00Z
completed: 2026-04-02T08:00:00Z
completed_location: tasks/completed/TASK-D0A8-003/
priority: critical
tags: [deployment, gb10, tmux, resilience]
task_type: implementation
complexity: 3
parent_review: TASK-REV-D0A8
feature_id: FEAT-D0A8
wave: 1
implementation_mode: task-work
dependencies: []
test_results:
  status: passed
  coverage: null
  last_run: 2026-04-01T21:25:00Z
  notes: script syntax validated, files created and executable
---

# Task: GB10 setup instructions and run script

## Description

The 2500-run stalled because it ran on a Mac laptop (`Richards-MBP`) which suspended twice during the 28-hour run. The generation loop must run on the GB10 server directly, where:
- No power management suspension
- vLLM accessible at localhost:8002 (no Tailscale latency, no stale TCP connections)
- Process persists via tmux even if SSH disconnects

This task creates:
1. Detailed setup instructions for running on GB10
2. A `scripts/run-on-gb10.sh` script for tmux-managed execution

## Setup Instructions

Create `docs/deployment/gb10-setup.md` covering:

### Prerequisites
- SSH access to `promaxgb10-41b1` (via Tailscale or direct)
- Python 3.14 environment on GB10 (or matching version)
- Project cloned/synced to GB10
- vLLM Docker container `vllm-agentic-factory` running with Qwen3.5-35B-A3B-FP8
- ChromaDB data available (either local or synced from Mac)

### Environment Setup
- How to set up the Python environment on GB10
- How to install dependencies (`pip install -r requirements.txt`)
- How to sync/clone the project from Mac to GB10
- How to verify vLLM is running (`curl localhost:8002/v1/models`)
- How to verify ChromaDB data is accessible

### Config Changes for GB10
- vLLM endpoint: change from `http://promaxgb10-41b1:8002/v1` to `http://localhost:8002/v1`
- Any environment variables needed
- Output directory permissions

### Running with tmux
- `tmux new -s factory` to create a persistent session
- Running the generation loop within tmux
- `Ctrl-B D` to detach (process continues)
- `tmux attach -t factory` to reattach
- Monitoring logs while detached

### Checkpoint Resume
- How `--resume` works (reads `.checkpoint` file, skips processed targets)
- Output files opened in append mode (no data loss)
- Verifying the checkpoint value before resuming

### Monitoring
- Tail the application log: `tail -f output/run.log` (or equivalent)
- Check vLLM status: `docker logs -f vllm-agentic-factory`
- Check progress: `grep -c target_accepted output/run.log`

## Run Script

Create `scripts/run-on-gb10.sh`:

```bash
#!/usr/bin/env bash
set -euo pipefail

# Configuration
SESSION_NAME="factory"
LOG_DIR="output/logs"
TIMESTAMP=$(date +%Y%m%d-%H%M%S)
LOG_FILE="${LOG_DIR}/run-${TIMESTAMP}.log"

# Pre-flight checks
echo "=== Pre-flight checks ==="

# Check vLLM is running
if ! curl -sf http://localhost:8002/v1/models > /dev/null 2>&1; then
    echo "ERROR: vLLM not responding at localhost:8002"
    exit 1
fi
echo "  vLLM: OK"

# Check checkpoint
if [ -f output/.checkpoint ]; then
    CHECKPOINT=$(cat output/.checkpoint)
    echo "  Checkpoint: ${CHECKPOINT} (will resume from next index)"
else
    echo "  Checkpoint: none (fresh start)"
fi

# Create log directory
mkdir -p "${LOG_DIR}"

# Run in tmux
echo "=== Starting generation loop in tmux session '${SESSION_NAME}' ==="
echo "  Log: ${LOG_FILE}"
echo "  Detach: Ctrl-B D"
echo "  Reattach: tmux attach -t ${SESSION_NAME}"

tmux new-session -d -s "${SESSION_NAME}" \
    "python agent.py --resume 2>&1 | tee ${LOG_FILE}; echo 'Run complete. Press Enter to close.'; read"

tmux attach -t "${SESSION_NAME}"
```

## Acceptance Criteria

- [x] `docs/deployment/gb10-setup.md` exists with complete setup instructions
- [x] `scripts/run-on-gb10.sh` is executable and handles pre-flight checks
- [x] Script verifies vLLM is accessible before starting
- [x] Script displays checkpoint status
- [x] Script uses tmux for process persistence
- [x] Script captures stdout/stderr to timestamped log file

## Files to Create

- `docs/deployment/gb10-setup.md`
- `scripts/run-on-gb10.sh`
