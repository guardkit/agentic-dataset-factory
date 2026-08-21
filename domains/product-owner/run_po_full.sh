#!/usr/bin/env bash
# HOST launcher — PO bake-off FULL run for ONE student (train -> merge -> merged-gen gate -> GGUF q8_0).
# Run it only after run_po_smoke.sh came back all-green for the SAME student/SEQ/DATA:
#   [G1]/[G1b] trainable + per-layer attach, [G2] markers (and no double <think>), [G3] attn/fla,
#   [G4] masking sane, [G5] peak memory inside the envelope, [G6] zero truncation.
#
# KNOBS (env):  STUDENT=gemma4|qwen38   SEQ=6144   EPOCHS=3   DATA=<file in ~/fine-tuning/data>
#               GGUF=q8_0   FREE_MIN=95 (GiB)   WATCHDOG_GB=9   INSTALL_FLA=0|1 (qwen38)
#               ALLOW_TRUNCATION=0|1   RESUME=0|1
# SERVING LAW (2026-08-19): this estate serves q8_0. Do NOT export/seat this family's q4_k_m on
# the GB10 (architect re-export: q8_0 6/6 clean vs q4_k_m 5/6 CUT).
# NOTHING IS SEATED BY THIS SCRIPT. The exam against the untuned baseline comes after, and the
# llama-swap entry only moves on Rich's word.
set -eo pipefail

STUDENT="${STUDENT:-gemma4}"
SEQ="${SEQ:-6144}"
EPOCHS="${EPOCHS:-3}"
DATA="${DATA:-train-po-v3.fit-6144.jsonl}"   # 187 rows, zero truncation at 6144
GGUF="${GGUF:-q8_0}"
FREE_MIN="${FREE_MIN:-95}"
WATCHDOG_GB="${WATCHDOG_GB:-9}"
INSTALL_FLA="${INSTALL_FLA:-0}"
ALLOW_TRUNCATION="${ALLOW_TRUNCATION:-0}"
RESUME="${RESUME:-0}"

case "$STUDENT" in gemma4|qwen38) ;; *) echo "ABORT: STUDENT must be gemma4 or qwen38"; exit 2;; esac

NAME="po-ft-${STUDENT}-$(date +%Y%m%d-%H%M)"
OUT="$HOME/fine-tuning/output/po-${STUDENT}-v3"
# 2026-08-20 (verifier finding): a reused output dir lets a STALE merged-16bit / gguf / receipt
# from an aborted attempt be read as if this run produced it (--gate-only especially). Refuse by
# name unless the operator says which they mean: RESUME=1 continues the same dir, FRESH=1 moves
# the old one aside with a timestamp. Nothing is ever deleted.
if [ -d "$OUT" ] && [ "${RESUME:-0}" != "1" ]; then
  # `|| true` is load-bearing: grep exits 1 when it matches NOTHING, and under `set -e` + pipefail a
  # failing command substitution kills the script — i.e. the guard aborted every HEALTHY run (no stale
  # artifacts) while passing the unhealthy one. Found 2026-08-21 after three silent exits.
  STALE=$(ls -1 "$OUT" 2>/dev/null | grep -E '^(merged-16bit|gguf|train-receipt.json|merged-gen-gate.json)$' | tr '\n' ' ' || true)
  if [ -n "$STALE" ]; then
    if [ "${FRESH:-0}" = "1" ]; then
      MOVED="$OUT.superseded-$(date -u +%Y%m%dT%H%M%SZ)"; mv "$OUT" "$MOVED"
      echo "[pre-flight] prior artifacts moved aside -> $MOVED"
    else
      echo "ABORT: $OUT already holds artifacts from a previous attempt: $STALE"
      echo "  RESUME=1 ... to continue that run's dir, or FRESH=1 ... to move it aside (nothing is deleted)."
      exit 2
    fi
  fi
fi
mkdir -p "$OUT"
LOG="$OUT/host.log"

echo "=== PO FULL host start $(date -u +%FT%TZ) student=$STUDENT seq=$SEQ epochs=$EPOCHS data=$DATA gguf=$GGUF resume=$RESUME" | tee -a "$LOG"

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
[ "$GGUF" = "q4_k_m" ] && echo "WARNING: GGUF=q4_k_m contradicts the 2026-08-19 serving law (q8_0 only on this box)." | tee -a "$LOG"

# --- watchdog armed ----------------------------------------------------------------------
bash "$HOME/fine-tuning/scripts/mem_watchdog.sh" "$NAME" "$WATCHDOG_GB" >>"$LOG" 2>&1 &
WD=$!
trap 'kill $WD 2>/dev/null || true' EXIT
echo "[pre-flight] watchdog pid $WD guarding $NAME at ${WATCHDOG_GB}GB" | tee -a "$LOG"

EXTRA=""
[ "$ALLOW_TRUNCATION" = "1" ] && EXTRA="$EXTRA --allow-truncation"
[ "$RESUME" = "1" ] && EXTRA="$EXTRA --resume"

docker run --gpus all --ulimit memlock=-1 --ulimit stack=67108864 --rm \
  --name "$NAME" \
  -v "$HOME/fine-tuning/data:/workspace/data" \
  -v "$HOME/fine-tuning/output:/workspace/output" \
  -v "$HOME/fine-tuning/scripts:/workspace/scripts" \
  -v "$HOME/.cache/huggingface:/root/.cache/huggingface" \
  -e PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True \
  -e STUDENT="$STUDENT" -e SEQ="$SEQ" -e EPOCHS="$EPOCHS" -e DATA="$DATA" -e GGUF="$GGUF" \
  -e OUTDIR="/workspace/output/po-${STUDENT}-v3" -e EXTRA="$EXTRA" -e INSTALL_FLA="$INSTALL_FLA" \
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
    echo "=== INSTALL_FLA=1: installing flash-linear-attention ==="
    pip install -q flash-linear-attention || echo "WARNING: fla install FAILED — [G3] will say so; slow pure-PyTorch DeltaNet path"
  else
    echo "=== INSTALL_FLA=0: no flash-linear-attention. [G3] prints importability; 48 of 64 layers then use the slow pure-PyTorch path. Nothing assumes it silently. ==="
  fi
fi
cd /workspace/scripts
python train_po.py \
  --student "$STUDENT" \
  --data-path "/workspace/data/$DATA" \
  --seq-audit /workspace/data/train-po-v3.seq-audit.json \
  --output-dir "$OUTDIR" \
  --max-seq-length "$SEQ" \
  --epochs "$EPOCHS" \
  --gguf-quant "$GGUF" $EXTRA
' 2>&1 | tee -a "$LOG"
RC=${PIPESTATUS[0]}

echo "=== PO FULL host end $(date -u +%FT%TZ) rc=$RC ===" | tee -a "$LOG"
echo "ARTIFACTS   : $OUT/{lora-adapter,merged-16bit,gguf,train-receipt.json,merged-gen-gate.json}" | tee -a "$LOG"
echo "READ RECEIPT: grep -E '\[G1\]|\[G1b\]|\[G2\]|\[G3\]|\[G4\]|\[G5\]|\[G6\]|MERGED-GEN GATE' $LOG" | tee -a "$LOG"
echo "RESUME      : RESUME=1 STUDENT=$STUDENT SEQ=$SEQ EPOCHS=$EPOCHS DATA=$DATA bash \$HOME/fine-tuning/scripts/run_po_full.sh   (picks up the last checkpoint in $OUT)" | tee -a "$LOG"
echo "GATE ONLY   : docker run ... (same image) python train_po.py --student $STUDENT --gate-only --output-dir /workspace/output/po-${STUDENT}-v3 --data-path /workspace/data/$DATA" | tee -a "$LOG"
echo "ROLLBACK    : rm -rf $OUT   (nothing was seated: llama-swap untouched, the entry moves only on Rich's word)" | tee -a "$LOG"
exit $RC
