#!/usr/bin/env bash
# In-container SMOKE for the v4 raw-JSON Coach LoRA (60 steps) — run via `docker run ... bash this`.
# v4 deltas vs v3 (all Rich-signed, base-pick card 2026-07-25): updated base already in HF cache
# (refs/main 60941ad6 == the "Gemma 4 Fixes" release), template gemma-4-thinking pinned
# train==serve, GGUF q8_0, targets = raw unfenced {verdict, findings:[{locus}]}.
# Seq default 4096 (proven memory-safe); the in-container REAL-tokenizer audit below is the
# 4096-vs-6144 decision gate (runbook Phase 0.2) — 6144 only with the watchdog running.
set -eo pipefail
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
DATA="${DATA:-train-coach-v4.jsonl}"
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
echo "=== REAL-tokenizer seq audit (Phase 0.2 ground truth) ==="
python - <<PYEOF
import json
from transformers import AutoTokenizer
from unsloth.chat_templates import get_chat_template
tok = AutoTokenizer.from_pretrained("unsloth/gemma-4-26b-a4b-it")
tok = get_chat_template(tok, chat_template="gemma-4-thinking")
L = []
for line in open("/workspace/data/$DATA"):
    if not line.strip():
        continue
    convo = json.loads(line)["messages"]
    L.append(len(tok.apply_chat_template(convo, tokenize=True, add_generation_prompt=False)))
L.sort(); n = len(L)
print("p50", L[n // 2], "p95", L[int(.95 * n)], "p99", L[int(.99 * n)], "max", L[-1])
for thr in (4096, 6144):
    over = sum(x > thr for x in L)
    print(f"seq {thr}: {over}/{n} exceed")
import os
seq = int("$SEQ")
over = sum(x > seq for x in L)
assert over == 0, f"ABORT: {over} examples exceed SEQ={seq} — verdict tails would truncate; re-run with SEQ=6144 (watchdog mandatory)"
print(f"[GATE] all {n} examples fit SEQ={seq} — zero truncation")
PYEOF
echo "=== v4 SMOKE: 60 steps, seq $SEQ | data=$DATA ==="
cd /workspace/scripts
mkdir -p /workspace/output/coach-gemma4-26b-moe-v4-smoke
python train_coach_moe.py \
  --model-name unsloth/gemma-4-26b-a4b-it \
  --data-path "/workspace/data/$DATA" \
  --output-dir /workspace/output/coach-gemma4-26b-moe-v4-smoke \
  --chat-template gemma-4-thinking \
  --gguf-quant q8_0 \
  --max-seq-length "$SEQ" --max-steps 60 --skip-export
echo "=== V4 SMOKE DONE (exit $?) — check [G2] render (thought-block framing = THE CATCH), [G4] masking, [G5] peak memory ==="
