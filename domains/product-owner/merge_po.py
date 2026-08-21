"""Fresh-process merge for a PO tune — with a MERGE-APPLIED assertion (2026-08-21).

WHY THIS EXISTS. On 2026-08-21 the Gemma v3 run trained cleanly, then its in-process merge was
watchdog-killed. The merged-16bit dir it left behind was STRUCTURALLY perfect — both shards matched the
byte length their own safetensors headers declared, 1,013 tensors, index-consistent — and I concluded
from that that the merge had finished. It had not: every sampled LoRA-target tensor was
BYTE-IDENTICAL TO THE BASE. The adapter was never applied. The merged-generation gate then scored the
"tune" 2/8, which was really the base model failing a contract it was never taught.

THE LESSON, now enforced below: structural completeness is not semantic correctness. A merged file that
parses is not a merged file that merged. The only honest check is to compare a LoRA-target tensor
against the base and require that it DIFFERS.

House pattern: merge_qav_v2.py (fresh process, nothing else resident).
Run inside nvcr.io/nvidia/pytorch:25.11-py3 with the pinned deps. Explicit exit.
"""
import glob
import json
import os
import sys
import time

ADAPTER = os.environ.get("ADAPTER", "/workspace/output/po-gemma4-v3/lora-adapter")
MERGED = os.environ.get("MERGED", "/workspace/output/po-gemma4-v3/merged-16bit")
MAX_SEQ = int(os.environ.get("MAX_SEQ", "6144"))


def say(m):
    print(f"{time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())} {m}", flush=True)


from unsloth import FastModel  # noqa: E402
import peft.import_utils  # noqa: E402
import peft.tuners.lora.torchao  # noqa: E402
peft.import_utils.is_torchao_available = lambda: False
peft.tuners.lora.torchao.is_torchao_available = lambda: False
import torch  # noqa: E402
import unsloth  # noqa: E402

say(f"[GATE] unsloth {unsloth.__version__} torch {torch.__version__}")
say(f"Loading base + adapter from {ADAPTER} (fresh process, nothing else resident) ...")
model, tokenizer = FastModel.from_pretrained(
    model_name=ADAPTER,
    max_seq_length=MAX_SEQ,
    dtype=None,
    load_in_4bit=False,
    load_in_16bit=True,
    full_finetuning=False,
    attn_implementation="sdpa",
)
say("Loaded. Merging -> merged_16bit ...")
model.save_pretrained_merged(MERGED, tokenizer, save_method="merged_16bit")
say("MERGE_WRITTEN")

# ---- [G7] MERGE-APPLIED assertion — the check whose absence cost 2026-08-21 -------------------
say("[G7] verifying the adapter was actually applied (target tensors must DIFFER from base) ...")
from safetensors import safe_open  # noqa: E402

with safe_open(os.path.join(ADAPTER, "adapter_model.safetensors"), "pt") as f:
    akeys = list(f.keys())
targets = {
    k.replace("base_model.model.", "").replace(".lora_A.weight", "").replace(".lora_B.weight", "") + ".weight"
    for k in akeys
}
base_dir = os.environ.get(
    "BASE_SNAPSHOT",
    glob.glob("/root/.cache/huggingface/hub/models--unsloth--gemma-4-26b-a4b-it/snapshots/*")[0],
)
checked = same = 0
for shard in sorted(glob.glob(os.path.join(MERGED, "model-*.safetensors"))):
    bshard = os.path.join(base_dir, os.path.basename(shard))
    if not os.path.exists(bshard):
        continue
    with safe_open(shard, "pt") as fm, safe_open(bshard, "pt") as fb:
        mk, bk = set(fm.keys()), set(fb.keys())
        for t in sorted(targets & mk & bk):
            a, b = fm.get_tensor(t), fb.get_tensor(t)
            if a.shape != b.shape:
                continue
            checked += 1
            if bool((a == b).all()):
                same += 1
            if checked >= 12:
                break
    if checked >= 12:
        break
say(f"[G7] sampled {checked} LoRA-target tensors: {same} identical to base, {checked - same} merged")
if checked == 0:
    say("[G7] ABORT: could not compare any target tensor against the base — cannot prove the merge applied")
    sys.exit(3)
if same == checked:
    say("[G7] ABORT: EVERY sampled target tensor is byte-identical to the base — the adapter was NOT "
        "applied. This is exactly the 2026-08-21 failure; the merged dir is unusable. Do not gate it.")
    sys.exit(4)
say("[G7] PASS — the merge really merged.")
json.dump({"checked": checked, "identical_to_base": same, "merged": checked - same},
          open(os.path.join(MERGED, "merge-applied-check.json"), "w"), indent=2)
say("MERGE_DONE")
os._exit(0)
