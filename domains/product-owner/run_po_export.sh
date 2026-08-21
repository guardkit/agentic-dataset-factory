#!/bin/bash
# FRESH-PROCESS merged-gen gate + GGUF export for a completed PO tune (2026-08-21).
#
# WHY THIS EXISTS: train_po.py did the merge + GGUF export INSIDE the training process, which repeats
# the QAV v1 mistake the estate already paid for (merge_qav_v2.py: "the v1 in-process merge OOMed at
# ~119 GB — the receipted lesson: merge in a process with nothing else resident"). On 2026-08-21 the
# Gemma v3 full run trained cleanly (141 steps, loss 0.6296) and was then watchdog-killed at 08:05:49
# during the merge, with the training process still holding its GPU state. The merged-16bit shards
# survived intact, but the gate and the GGUF never ran.
#
# This script runs the two remaining steps in a FRESH container with nothing else resident:
#   1. the merged-generation gate (house law: generate from the merged model BEFORE any GGUF)
#   2. the GGUF export via llama.cpp's own converter + quantizer — which STREAMS the safetensors
#      instead of loading 52 GB into torch, so it is far lighter than save_pretrained_gguf.
# q8_0 only: never serve this model family's Q4_K_M mix on the GB10 (2026-08-19 receipt).
#
# KNOBS: STUDENT=gemma4|qwen38  OUTDIR=<dir under ~/fine-tuning/output>  WATCHDOG_GB=8  SKIP_GATE=0|1
set -eo pipefail
STUDENT="${STUDENT:-gemma4}"
OUTDIR="${OUTDIR:-$HOME/fine-tuning/output/po-${STUDENT}-v3}"
WATCHDOG_GB="${WATCHDOG_GB:-8}"     # lower than training's 12: this step has no GPU state to protect
LOG="$OUTDIR/export.log"
MERGED="$OUTDIR/merged-16bit"
GGUF_DIR="$OUTDIR/gguf"
LCPP="${LCPP:-$HOME/llama.cpp-new}"

[ -d "$MERGED" ] || { echo "ABORT: no $MERGED"; exit 2; }
mkdir -p "$GGUF_DIR"
echo "=== PO EXPORT start $(date -u +%FT%TZ) student=$STUDENT out=$OUTDIR ===" | tee -a "$LOG"

AVAIL=$(free -g | awk 'NR==2{print $7}')
echo "[pre-flight] MemAvailable ${AVAIL} GiB" | tee -a "$LOG"
if [ "$AVAIL" -lt 80 ]; then echo "ABORT: only ${AVAIL} GiB — the merge/export needs a quiet box (curl :9000/unload)"; exit 2; fi
if pgrep -a llama-server >/dev/null 2>&1; then echo "ABORT: llama-server resident — unload first"; exit 2; fi

# 1. merged-generation gate, fresh process
if [ "${SKIP_GATE:-0}" != "1" ]; then
  echo "--- [1/2] merged-generation gate (fresh process) ---" | tee -a "$LOG"
  bash "$HOME/fine-tuning/scripts/mem_watchdog.sh" "po-export-gate-$$" "$WATCHDOG_GB" >> "$LOG" 2>&1 &
  WD=$!
  docker run --gpus all --ulimit memlock=-1 --ulimit stack=67108864 --rm \
    --name "po-export-gate-$$" \
    -v "$HOME/fine-tuning/output:/workspace/output" -v "$HOME/fine-tuning/scripts:/workspace/scripts" \
    -v "$HOME/fine-tuning/data:/workspace/data" -v "$HOME/.cache/huggingface:/root/.cache/huggingface" \
    -e PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True \
    --entrypoint /usr/bin/bash nvcr.io/nvidia/pytorch:25.11-py3 -c '
      set -eo pipefail
      pip install -q transformers==5.5.4 peft hf_transfer "datasets==4.3.0" "trl==0.26.1" "accelerate==1.10.0"
      pip install -q --no-deps unsloth unsloth_zoo bitsandbytes
      cd /workspace/scripts && python train_po.py --student '"$STUDENT"' --gate-only \
        --output-dir /workspace/output/'"$(basename "$OUTDIR")"' ' 2>&1 | tee -a "$LOG"
  kill $WD 2>/dev/null || true
fi

# 2. GGUF via llama.cpp (streams safetensors — no 52 GB torch load)
echo "--- [2/2] GGUF export via llama.cpp converter (q8_0) ---" | tee -a "$LOG"
F16="$GGUF_DIR/po-${STUDENT}-v3-f16.gguf"
Q8="$GGUF_DIR/po-${STUDENT}-v3-q8_0.gguf"
if [ ! -s "$F16" ]; then
  "$HOME/Projects/appmilla_github/agentic-dataset-factory/.venv/bin/python" \
    "$LCPP/convert_hf_to_gguf.py" "$MERGED" --outfile "$F16" --outtype f16 2>&1 | tail -20 | tee -a "$LOG"
fi
"$LCPP/build/bin/llama-quantize" "$F16" "$Q8" q8_0 2>&1 | tail -8 | tee -a "$LOG"
ls -la "$GGUF_DIR" | tee -a "$LOG"
echo "=== PO EXPORT end $(date -u +%FT%TZ) rc=$? ===" | tee -a "$LOG"
echo "NEXT: serve $Q8 on a scratch port at --ctx-size 131072 and run the frozen exam." | tee -a "$LOG"
