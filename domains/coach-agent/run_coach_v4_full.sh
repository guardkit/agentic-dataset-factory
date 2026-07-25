#!/usr/bin/env bash
# In-container FULL run for the v4 raw-JSON Coach LoRA — run via `docker run ... bash this`.
# Only after run_coach_v4_smoke.sh is all-green ([G2] framing verified, [G4] masking sane,
# peak memory inside the envelope). 3 epochs on the 174-row balanced corpus, merge + GGUF q8_0
# (the signed serving pick). The merged-gen gate and the UNFENCED-parse serve gate run AFTER
# this script, against merged-16bit/ and the exported GGUF — no reseat before both pass.
set -eo pipefail
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
DATA="${DATA:-train-coach-v4.jsonl}"
EPOCHS="${EPOCHS:-3}"
SEQ="${SEQ:-4096}"
echo "=== deps (pinned, verified) ==="
pip install transformers==5.5.4 peft hf_transfer "datasets==4.3.0" "trl==0.26.1" "accelerate==1.10.0"
pip install --no-deps unsloth unsloth_zoo bitsandbytes
python - <<'PYEOF'
from packaging.version import Version
import unsloth
v = unsloth.__version__
assert Version(v) >= Version("2026.4.4"), f"ABORT: unsloth {v} < 2026.4.4 (the signed recipe pin)"
print(f"[GATE] unsloth {v} >= 2026.4.4 OK")
PYEOF
echo "=== v4 FULL: $EPOCHS epochs, seq $SEQ, merge + GGUF q8_0 | data=$DATA ==="
cd /workspace/scripts
mkdir -p /workspace/output/coach-gemma4-26b-moe-v4
python train_coach_moe.py \
  --model-name unsloth/gemma-4-26b-a4b-it \
  --data-path "/workspace/data/$DATA" \
  --output-dir /workspace/output/coach-gemma4-26b-moe-v4 \
  --chat-template gemma-4-thinking \
  --gguf-quant q8_0 \
  --max-seq-length "$SEQ" --epochs "$EPOCHS"
echo "=== V4 FULL DONE (exit $?) — artifacts in /workspace/output/coach-gemma4-26b-moe-v4 ==="
echo "next: merged-gen gate -> GGUF serve gate (clean UNFENCED parse) -> v2 bar grade"
