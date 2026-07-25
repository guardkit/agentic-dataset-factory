#!/usr/bin/env bash
# In-container training driver for the recruiter tune. Runs deps -> seq audit -> smoke -> full ->
# gate-generate (tuned + stock). Conditional: full only runs if the smoke reached "Training complete."
# with no ABORT/Traceback. Everything logged under /workspace/output.
set -uo pipefail
cd /workspace/scripts

OUT=/workspace/output
SMOKE=$OUT/recruiter-qwen3-8b-smoke
FULL=$OUT/recruiter-qwen3-8b
DATA=/workspace/data/train-recruiter.jsonl
EVAL=/workspace/data/val-recruiter.jsonl
TPL=/workspace/scripts/qwen3-2507-stock.jinja
mkdir -p "$SMOKE" "$FULL" "$FULL/gate"

echo "===== [1/6] deps ====="
pip install -q transformers==5.5.4 peft hf_transfer "datasets==4.3.0" "trl==0.26.1" "accelerate==1.10.0" 2>&1 | tail -1
pip install -q --no-deps unsloth unsloth_zoo bitsandbytes 2>&1 | tail -1
echo "deps done"

echo "===== [2/6] real-tokenizer seq audit ====="
python - <<'PY' 2>&1 | tee "$OUT/seq-audit.txt"
import json
from unsloth import FastLanguageModel
_, tok = FastLanguageModel.from_pretrained("Qwen/Qwen3-8B",
    max_seq_length=4096, load_in_4bit=True, full_finetuning=False)
tok.chat_template = open("/workspace/scripts/qwen3-2507-stock.jinja").read()
L=[len(tok.apply_chat_template(json.loads(l)["messages"], tokenize=True, add_generation_prompt=False))
   for l in open("/workspace/data/train-recruiter.jsonl") if l.strip()]
L.sort(); n=len(L)
for thr in (2048,3072,4096): print(thr, f"{sum(x>thr for x in L)}/{n} exceed")
print("p95", L[int(.95*n)], "p99", L[int(.99*n)], "max", L[-1])
PY

echo "===== [3/6] SMOKE (40 steps, skip-export) ====="
python train_recruiter_qwen3.py --base-model Qwen/Qwen3-8B \
  --data-path "$DATA" --eval-path "$EVAL" \
  --output-dir "$SMOKE" --max-steps 40 --skip-export \
  --chat-template-file "$TPL" 2>&1 | tee "$SMOKE/train.log"

if ! grep -q "Training complete." "$SMOKE/train.log" || grep -qE "ABORT \[G|Traceback" "$SMOKE/train.log"; then
  echo "!!!! SMOKE FAILED — stopping before full run. Inspect $SMOKE/train.log"
  exit 2
fi
echo "smoke OK"

echo "===== [4/6] FULL run (2 epochs, merge + gguf) ====="
python train_recruiter_qwen3.py --base-model Qwen/Qwen3-8B \
  --data-path "$DATA" --eval-path "$EVAL" \
  --output-dir "$FULL" \
  --chat-template-file "$TPL" 2>&1 | tee "$FULL/train.log"

if ! grep -q "Training complete." "$FULL/train.log" || grep -qE "ABORT \[G|Traceback" "$FULL/train.log"; then
  echo "!!!! FULL TRAIN FAILED. Inspect $FULL/train.log"
  exit 3
fi
if [ ! -d "$FULL/merged-16bit" ]; then
  echo "!!!! merged-16bit not written — gate cannot run. Inspect $FULL/train.log"
  exit 4
fi
echo "full train OK; merged-16bit present"

echo "===== [5/6] GATE generate: TUNED ====="
python /workspace/scripts/merged_gen_gate.py --mode generate \
  --model "$FULL/merged-16bit" \
  --prompts "$EVAL" \
  --chat-template-file "$TPL" \
  --out "$FULL/gate/tuned-outputs.jsonl" --label tuned 2>&1 | tee "$FULL/gate/gen-tuned.log"

echo "===== [6/6] GATE generate: STOCK ====="
python /workspace/scripts/merged_gen_gate.py --mode generate \
  --model Qwen/Qwen3-8B \
  --prompts "$EVAL" \
  --chat-template-file "$TPL" \
  --out "$FULL/gate/stock-outputs.jsonl" --label stock 2>&1 | tee "$FULL/gate/gen-stock.log"

echo "===== DRIVER DONE ====="
echo "ALL_STAGES_COMPLETE"
