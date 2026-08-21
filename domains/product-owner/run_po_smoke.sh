#!/usr/bin/env bash
# HOST launcher — PO bake-off SMOKE (one student, a few steps, gates only).
# Shape copied from run_coach_v4_smoke.sh + run_architect_reexport.sh (host pre-flight,
# house container, pinned deps, unsloth gate, mem watchdog armed).
#
# ITS ONLY JOB: fire [G1] [G1b] [G2] [G3] [G4] [G5] [G6] and print peak memory. It trains
# MAXSTEPS steps and does NOT merge or export (--skip-export). If a gate is going to abort the
# window, it aborts here in minutes instead of an hour in.
#
# KNOBS (env):  STUDENT=gemma4|qwen38   SEQ=6144   MAXSTEPS=40   DATA=<file in ~/fine-tuning/data>
#               FREE_MIN=95 (GiB)   WATCHDOG_GB=9   INSTALL_FLA=0|1 (qwen38 only)
#               ALLOW_TRUNCATION=0|1
# PRE-CONDITIONS this script CHECKS and refuses to fix itself (box-hang law, no-side-servers law):
#   * host MemAvailable >= FREE_MIN GiB
#   * no llama-server process resident  -> if there is one, YOU unload it:
#         curl -sS http://localhost:9000/unload    (and stop the keepalive timer for the window)
#   * no other fine-tune container running
set -eo pipefail

STUDENT="${STUDENT:-gemma4}"
SEQ="${SEQ:-6144}"
MAXSTEPS="${MAXSTEPS:-40}"
DATA="${DATA:-train-po-v3.fit-6144.jsonl}"   # the NO-TRUNCATION file at seq 6144 (187 rows)
FREE_MIN="${FREE_MIN:-95}"
WATCHDOG_GB="${WATCHDOG_GB:-9}"
INSTALL_FLA="${INSTALL_FLA:-0}"
ALLOW_TRUNCATION="${ALLOW_TRUNCATION:-0}"

case "$STUDENT" in gemma4|qwen38) ;; *) echo "ABORT: STUDENT must be gemma4 or qwen38"; exit 2;; esac

STAMP=$(date +%Y%m%d-%H%M)
NAME="po-ft-smoke-${STUDENT}-${STAMP}"
OUT="$HOME/fine-tuning/output/po-${STUDENT}-smoke-${STAMP}"
mkdir -p "$OUT"
LOG="$OUT/host.log"

echo "=== PO SMOKE host start $(date -u +%FT%TZ) student=$STUDENT seq=$SEQ steps=$MAXSTEPS data=$DATA" | tee -a "$LOG"

# --- pre-flight: the box must be QUIET ---------------------------------------------------
AVAIL=$(free -g | awk 'NR==2{print $7}')
echo "[pre-flight] MemAvailable ${AVAIL} GiB (floor ${FREE_MIN})" | tee -a "$LOG"
if [ "$AVAIL" -lt "$FREE_MIN" ]; then
  echo "ABORT: only ${AVAIL} GiB available (< ${FREE_MIN}). Unload the seats first:
    curl -sS http://localhost:9000/unload      # and stop the keepalive timer for the window
  Every past tune on this box ran with llama-swap fully unloaded." | tee -a "$LOG"; exit 2
fi
# 2026-08-21: refuse only on LARGE seats. The estate's `embed` seat (Qwen3-Embedding-0.6B, ~9 GB)
# loads on demand whenever fleet-memory/office/crows-nest issue /v1/embeddings and reloads the moment
# it is unloaded — refusing on ANY llama-server made this script unrunnable. The memory floor above is
# the real guard. (Same fix already applied to run_po_export.sh.)
BIG=$(pgrep -a llama-server | grep -oE -- "--alias [a-z0-9._-]+" | awk '{print $2}' | grep -vE "^(embed|qwen3-embedding)$" || true)
if [ -n "$BIG" ]; then
  echo "ABORT: large seat(s) resident: $BIG — unload them yourself (curl -sS http://localhost:9000/unload);" | tee -a "$LOG"
  echo "  this script will not touch the serving estate." | tee -a "$LOG"; exit 2
fi
pgrep -a llama-server >/dev/null 2>&1 && echo "[pre-flight] only the small embed seat is resident — proceeding" | tee -a "$LOG"
# 2026-08-20: match TRAINING/EXPORT containers only. The estate's always-on seats
# (specialist-agent-*-agent-1, forge-prod, office-manager-*) are not GPU trainers and must
# not abort a window — the first draft's 'architect' substring matched
# specialist-agent-architect-agent-1 and would have refused every run.
if docker ps --format '{{.Names}}' | grep -Eq '(^|-)(po|coach|qav|architect|dcl)-(ft|train|reexport)|-ft-[0-9]|finetune|training'; then
  echo "ABORT: another training container is running:" | tee -a "$LOG"
  docker ps --format '  {{.Names}} {{.Status}}' | tee -a "$LOG"; exit 2
fi
for f in "$HOME/fine-tuning/data/$DATA" "$HOME/fine-tuning/data/train-po-v3.seq-audit.json" \
         "$HOME/fine-tuning/scripts/train_po.py"; do
  [ -f "$f" ] || { echo "ABORT: missing $f" | tee -a "$LOG"; exit 2; }
done

# --- watchdog armed (kills the container instead of freezing the box) --------------------
bash "$HOME/fine-tuning/scripts/mem_watchdog.sh" "$NAME" "$WATCHDOG_GB" >>"$LOG" 2>&1 &
WD=$!
trap 'kill $WD 2>/dev/null || true' EXIT
echo "[pre-flight] watchdog pid $WD guarding $NAME at ${WATCHDOG_GB}GB" | tee -a "$LOG"

EXTRA=""
[ "$ALLOW_TRUNCATION" = "1" ] && EXTRA="--allow-truncation"

docker run --gpus all --ulimit memlock=-1 --ulimit stack=67108864 --rm \
  --name "$NAME" \
  -v "$HOME/fine-tuning/data:/workspace/data" \
  -v "$HOME/fine-tuning/output:/workspace/output" \
  -v "$HOME/fine-tuning/scripts:/workspace/scripts" \
  -v "$HOME/.cache/huggingface:/root/.cache/huggingface" \
  -e PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True \
  -e STUDENT="$STUDENT" -e SEQ="$SEQ" -e MAXSTEPS="$MAXSTEPS" -e DATA="$DATA" \
  -e OUTDIR="/workspace/output/$(basename "$OUT")" -e EXTRA="$EXTRA" -e INSTALL_FLA="$INSTALL_FLA" \
  --entrypoint /usr/bin/bash nvcr.io/nvidia/pytorch:25.11-py3 -c '
set -eo pipefail
echo "=== deps (the house pinned set) ==="
pip install -q transformers==5.5.4 peft hf_transfer "datasets==4.3.0" "trl==0.26.1" "accelerate==1.10.0"
pip install -q --no-deps unsloth unsloth_zoo bitsandbytes
python - <<PYEOF
from packaging.version import Version
import unsloth; v = unsloth.__version__
assert Version(v) >= Version("2026.4.4"), f"ABORT: unsloth {v} < 2026.4.4 (the signed recipe pin)"
print(f"[GATE] unsloth {v} >= 2026.4.4 OK")
PYEOF
if [ "$STUDENT" = "qwen38" ]; then
  if [ "$INSTALL_FLA" = "1" ]; then
    echo "=== INSTALL_FLA=1: installing flash-linear-attention (48 of 64 layers are Gated-DeltaNet) ==="
    pip install -q flash-linear-attention || echo "WARNING: fla install FAILED — [G3] will say so; the slow pure-PyTorch path will be used"
  else
    echo "=== INSTALL_FLA=0: NOT installing flash-linear-attention. [G3] prints whether it is importable; the DeltaNet layers fall back to the slow pure-PyTorch path (a GB10 report measured 451 -> 3,461 tok/s WITH it). Nothing here assumes it silently. ==="
  fi
fi
cd /workspace/scripts
python train_po.py \
  --student "$STUDENT" \
  --data-path "/workspace/data/$DATA" \
  --seq-audit /workspace/data/train-po-v3.seq-audit.json \
  --output-dir "$OUTDIR" \
  --max-seq-length "$SEQ" \
  --max-steps "$MAXSTEPS" \
  --skip-export $EXTRA
' 2>&1 | tee -a "$LOG"
RC=${PIPESTATUS[0]}

echo "=== PO SMOKE host end $(date -u +%FT%TZ) rc=$RC ===" | tee -a "$LOG"
echo "READ THE RECEIPT: grep -E '\[G1\]|\[G1b\]|\[G2\]|\[G3\]|\[G4\]|\[G5\]|\[G6\]' $LOG" | tee -a "$LOG"
echo "RESUME/NEXT : STUDENT=$STUDENT SEQ=$SEQ DATA=$DATA bash $HOME/fine-tuning/scripts/run_po_full.sh" | tee -a "$LOG"
echo "ROLLBACK    : rm -rf $OUT   (smoke output only; nothing was merged, exported or seated)" | tee -a "$LOG"
exit $RC
