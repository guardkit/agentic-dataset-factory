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
    echo "  Start it with: docker start vllm-agentic-factory"
    exit 1
fi
echo "  vLLM: OK"

# Check Python venv
if [ -z "${VIRTUAL_ENV:-}" ]; then
    if [ -f .venv/bin/activate ]; then
        echo "  Activating .venv..."
        # shellcheck disable=SC1091
        source .venv/bin/activate
    else
        echo "WARNING: No virtual environment active or found at .venv/"
    fi
fi
echo "  Python: $(python --version 2>&1)"

# Check checkpoint
if [ -f output/.checkpoint ]; then
    CHECKPOINT=$(cat output/.checkpoint)
    echo "  Checkpoint: ${CHECKPOINT} (will resume from next index)"
else
    echo "  Checkpoint: none (fresh start)"
fi

# Create log directory
mkdir -p "${LOG_DIR}"

# Check for existing tmux session
if tmux has-session -t "${SESSION_NAME}" 2>/dev/null; then
    echo ""
    echo "tmux session '${SESSION_NAME}' already exists."
    echo "  Attach: tmux attach -t ${SESSION_NAME}"
    echo "  Kill:   tmux kill-session -t ${SESSION_NAME}"
    exit 1
fi

# Run in tmux
echo ""
echo "=== Starting generation loop in tmux session '${SESSION_NAME}' ==="
echo "  Log: ${LOG_FILE}"
echo "  Detach: Ctrl-B D"
echo "  Reattach: tmux attach -t ${SESSION_NAME}"

SCRIPT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
tmux new-session -d -s "${SESSION_NAME}" \
    "cd ${SCRIPT_DIR}; source .venv/bin/activate 2>/dev/null; python agent.py --resume 2>&1 | tee ${LOG_FILE}; echo 'Run complete. Press Enter to close.'; read"

tmux attach -t "${SESSION_NAME}"
