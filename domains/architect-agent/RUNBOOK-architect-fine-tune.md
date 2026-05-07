# Runbook: Architect Agent — Fine-Tune (Gemma-4-26B-A4B MoE)

**Purpose:** Take the dataset produced by `RUNBOOK-architect-dataset-pipeline.md` and fine-tune Gemma-4-26B-A4B (MoE) on it via Unsloth + TRL inside the NVIDIA PyTorch container.
**Machine:** Dell DGX Spark GB10 (`promaxgb10-41b1`), 128 GB unified memory.
**Duration:** ~2-4 hours wall-clock for ~900 examples × 1 epoch with effective batch 4 (~225 steps).
**Prerequisite:** Stage 1 generation has finished cleanly (`STAGE: Generation COMPLETE`, exit 0). The dataset must pass every gate in Phase 0 before any backup/staging/launch work happens.
**Reproducibility:** This runbook is phrased for the architect-agent domain but Phase 0 (validation) and Phases 3-5 (launch / monitor / validate) are domain-agnostic. To re-use for a future domain, change the constants in the *Inputs* block below and copy the file.

---

## Inputs

```bash
DOMAIN="architect-agent"
SOURCE_OUTPUT="$HOME/Projects/appmilla_github/agentic-dataset-factory/output"
EXPECTED_TARGETS=2400          # value from generation-plan; informs accept-rate calc
MIN_ACCEPTED=1500              # below this we stop and re-run generation, do not fine-tune
MAX_REJECTION_RATE_PCT=20      # above this we investigate before launching
FT_HOME="$HOME/fine-tuning"
STAGED_TRAIN="$FT_HOME/data/train-${DOMAIN}.jsonl"
OUTPUT_TAG="${DOMAIN}-gemma4-26b-moe"
OUTPUT_DIR_HOST="$FT_HOME/output/${OUTPUT_TAG}"
OUTPUT_DIR_CTR="/workspace/output/${OUTPUT_TAG}"
DATA_PATH_CTR="/workspace/data/train-${DOMAIN}.jsonl"
```

---

## Phase 0: Validate the dataset (the GO/NO-GO gate)

This is the most important phase: do not run any of the destructive backup or rename operations in Phase 1 until everything below passes. If a gate fails, fix the dataset (or the generator) first.

The whole phase is read-only. Run it after every generation pass — including reruns.

### 0.1 Counts and acceptance rate

```bash
cd "$SOURCE_OUTPUT/.." || exit 1

BEHAVIOUR=$(wc -l < output/train.jsonl)
KNOWLEDGE=$(wc -l < output/rag_index/knowledge.jsonl)
REJECTED=$(wc -l < output/rejected.jsonl)
TOTAL_ACCEPTED=$((BEHAVIOUR + KNOWLEDGE))
TOTAL_ATTEMPTED=$((TOTAL_ACCEPTED + REJECTED))
ACCEPT_PCT=$(python3 -c "print(f'{$TOTAL_ACCEPTED / max($TOTAL_ATTEMPTED, 1) * 100:.1f}')")

echo "behaviour:    $BEHAVIOUR"
echo "knowledge:    $KNOWLEDGE"
echo "rejected:     $REJECTED"
echo "accepted:     $TOTAL_ACCEPTED / $TOTAL_ATTEMPTED  (${ACCEPT_PCT}%)"
```

| Gate | Expected | Action if violated |
|---|---|---|
| `BEHAVIOUR >= 500` | True | Below 500 the fine-tune won't have enough signal — rerun generation, don't proceed |
| `TOTAL_ACCEPTED >= MIN_ACCEPTED` | True (≥1,500) | Investigate why; consider raising `--ctx-size`, lowering `max_turns`, or expanding the generation plan |
| `100 - ACCEPT_PCT <= MAX_REJECTION_RATE_PCT` | True (≤20%) | Read the rejection analysis (0.4); if rejections are concentrated in one criterion the Coach rubric may be miscalibrated |

### 0.2 Template-token leak check

If the Player accidentally bled chat-template control tokens (`<|channel>`, `<|turn>`) into the content, fine-tuning will train the model to reproduce them — fatal. This must be zero.

```bash
LEAK_B=$(grep -c '<|channel>\|<channel|>\|<|turn>\|<turn|>' output/train.jsonl 2>/dev/null || echo 0)
LEAK_K=$(grep -c '<|channel>\|<channel|>\|<|turn>\|<turn|>' output/rag_index/knowledge.jsonl 2>/dev/null || echo 0)

echo "behaviour leaks:  $LEAK_B"
echo "knowledge leaks:  $LEAK_K"

if [ "$LEAK_B" -gt 0 ] || [ "$LEAK_K" -gt 0 ]; then
    echo "ABORT: template-token leaks detected. Inspect with:"
    echo "  grep -n '<|channel>\|<|turn>' output/train.jsonl | head"
    exit 1
fi
echo "PASS"
```

### 0.3 `<think>` block coverage

The Gemma-4-thinking chat template trains the model to emit `<think>…</think>` followed by the visible answer. If a training example doesn't contain a `<think>` block the model learns to skip thinking on that prompt class.

For this domain, every accepted example should contain `<think>` (the generator targets `type=reasoning` for all of them).

```bash
TOT_B=$(wc -l < output/train.jsonl)
THINK_B=$(grep -c '<think>' output/train.jsonl)
TOT_K=$(wc -l < output/rag_index/knowledge.jsonl)
THINK_K=$(grep -c '<think>' output/rag_index/knowledge.jsonl)

echo "behaviour:  $THINK_B / $TOT_B with <think>"
echo "knowledge:  $THINK_K / $TOT_K with <think>"

if [ "$THINK_B" -ne "$TOT_B" ] || [ "$THINK_K" -ne "$TOT_K" ]; then
    echo "WARN: missing <think> blocks. Identify offenders with:"
    echo "  awk 'NR && !/<think>/ {print NR}' output/train.jsonl | head"
    echo "Acceptable only if your generation plan includes type=direct examples."
fi
```

### 0.4 Rejection analysis

A high rejection rate isn't necessarily bad — `max_turns_exhausted` from a strict Coach is fine. What matters is *what's missing*: if rejections are concentrated in one dimension you'll under-represent it in training.

```bash
python3 - <<'PY'
import json
from collections import Counter

reasons = Counter()
dims = Counter()
with open("output/rejected.jsonl") as f:
    for line in f:
        if not line.strip():
            continue
        rec = json.loads(line)
        reasons[rec.get("reason", "unknown")[:80]] += 1
        dims[rec.get("category", rec.get("dimension", "?"))] += 1

total = sum(reasons.values())
print(f"Total rejected: {total}\n")
print("By reason:")
for reason, n in reasons.most_common(5):
    print(f"  {n:>4}  {reason}")
print("\nBy dimension:")
for dim, n in dims.most_common():
    print(f"  {n:>4}  {dim}")
PY
```

| Pattern | Interpretation |
|---|---|
| All `max_turns_exhausted`, evenly spread across dimensions | Coach is strict but consistent — fine to proceed |
| One dimension dominates rejections | Coach rubric or RAG retrieval is weak for that dimension; consider rerunning that subset only |
| Many `llm_failure` / `timeout` | Backend instability — check llama-swap and the workhorse worker before re-running |
| Many `Failed to parse CoachVerdict` | Coach's structured-output mode is misconfigured; not a dataset problem but worth investigating |

### 0.5 Dimension distribution

Verify the accepted corpus covers every architect dimension with reasonable balance.

```bash
python3 - <<'PY'
import json
from collections import Counter

for layer, path in [("behaviour", "output/train.jsonl"),
                    ("knowledge", "output/rag_index/knowledge.jsonl")]:
    dims = Counter()
    with open(path) as f:
        for line in f:
            rec = json.loads(line)
            dims[rec.get("metadata", {}).get("dimension", "?")] += 1
    total = sum(dims.values())
    print(f"=== {layer} ({total} examples) ===")
    for d, n in sorted(dims.items()):
        print(f"  {d:<35}  {n:>4}  ({n/total*100:.1f}%)")
    print()
PY
```

Expected (architect domain): 10 dimensions present in `behaviour`, ~9 in `knowledge` (cross_cutting is behaviour-only by design). No single dimension above ~25% of its layer's total. If one dimension is missing, generation didn't complete that section — investigate before fine-tuning.

### 0.6 Spot-check format

Eyeball the first record of each layer to confirm structure matches what `train_gemma4_moe.py:load_sharegpt_jsonl` expects (a `messages` list with `role`/`content` pairs).

```bash
python3 - <<'PY'
import json
for label, path in [("behaviour", "output/train.jsonl"),
                    ("knowledge", "output/rag_index/knowledge.jsonl")]:
    with open(path) as f:
        ex = json.loads(f.readline())
    msgs = ex["messages"]
    meta = ex.get("metadata", {})
    print(f"=== {label} ===")
    print(f"  metadata keys: {sorted(meta.keys())}")
    print(f"  message roles: {[m['role'] for m in msgs]}")
    for m in msgs:
        print(f"  [{m['role']}] {len(m['content'])} chars: {m['content'][:160]!r}")
    print()
PY
```

Required: roles are `system`/`user`/`assistant` (or `human`/`gpt` — both are normalised by the loader); the assistant turn opens with `<think>`; `metadata.dimension`, `.layer`, `.type` are present.

### 0.7 Decision matrix

| All gates pass | → | Proceed to Phase 1 |
| Leak count > 0 | → | **STOP**. Patch the generator (the Player produced control tokens), regenerate the affected indices, re-validate |
| Acceptance rate < 80% **or** dimension missing | → | **STOP**. Diagnose and partial-rerun before fine-tuning — a fine-tune on a skewed corpus is harder to undo than a re-run |
| `<think>` coverage incomplete (and your plan said all-reasoning) | → | **STOP**. Patch and regenerate |
| Behaviour count < 500 | → | **STOP**. Not enough data; expand the generation plan |

Architect-agent run on 2026-05-02: all gates passed (894/1102 split, 0 leaks, 100% think coverage, 83.2% accept). Proceeding.

---

## Phase 0.5: Stop llama-swap and confirm GPU is clear

**Critical** — both freezes seen during initial runs of this runbook were caused by running fine-tuning concurrently with llama-swap workers. The Gemma-4-26B fine-tune needs ~50-80 GB of GPU memory; llama-swap workers (workhorse, qwen-graphiti, gemma4-tutor, embedder) routinely consume 60-70 GB. The combination on a 121 GB unified-memory GB10 oversubscribes the system and freezes the kernel.

**Take llama-swap fully down before launching Docker.** Bring it back up only after the fine-tune (and GGUF export) has completed.

```bash
# On the GB10 (host, not container):
pkill -f "llama-swap|llama-server"
sleep 3
pgrep -fa "llama-swap|llama-server" | grep -v grep || echo "(clear — good)"
nvidia-smi --query-compute-apps=pid,process_name,used_memory --format=csv
```

Expected output:
- `(clear — good)`
- The `nvidia-smi` query returns just the header row (no compute apps)

If you see lingering processes, a follow-up `pkill -9 -f "llama-swap|llama-server"` is fine — they're long-running but stateless from llama-swap's perspective; they'll respawn on demand once you bring it back up later.

If `infra-up.sh` (or whatever brings llama-swap up) auto-runs on boot, disable it for the duration of the fine-tune. On 2026-05-02 the user confirmed it's a manual script, so no systemd disable was needed.

**Other GPU consumers to check:**
- vLLM containers (none on this box, but the docker images are present — verify with `docker ps`)
- Any in-flight Claude Code sessions doing `task-work`/`autobuild` against the local API (these route through llama-swap)
- Forge / Graphiti / Open WebUI containers (some use llama-swap)

The desktop's Xorg/gnome-shell consume ~1.5 GB of GPU memory; that's normal and not a problem.

---

## Phase 1: Backup existing artefacts

Only run after every Phase 0 gate passes.

### 1.1 Snapshot the dataset-factory output before any fine-tune-side moves

The point of this snapshot is provenance: if anything in `~/fine-tuning/` gets clobbered, we still have the original generation output preserved beside the runbook that produced it.

```bash
cd ~/Projects/appmilla_github/agentic-dataset-factory
TS=$(date +%Y%m%d-%H%M%S)
SNAPSHOT="output_backup_post_${DOMAIN}_${TS}"
cp -a output "$SNAPSHOT"
ls -la "$SNAPSHOT"/{train.jsonl,rag_index/knowledge.jsonl,rejected.jsonl}
```

### 1.2 Rename existing fine-tune outputs to disambiguate

The previous study-tutor fine-tune left ~272 GB of artefacts in `~/fine-tuning/output/` owned by `root` (the Docker container created them). We don't need to delete them — disk is fine — but renaming with a date suffix prevents the architect run from accidentally writing into them and makes the artefact zoo readable.

```bash
ls -la ~/fine-tuning/output/

# Only rename if they exist and haven't already been dated.
if [ -d ~/fine-tuning/output/gcse-tutor-gemma4-26b-moe ]; then
    sudo mv ~/fine-tuning/output/gcse-tutor-gemma4-26b-moe \
            ~/fine-tuning/output/gcse-tutor-gemma4-26b-moe-2026-04-18
fi
if [ -d ~/fine-tuning/output/gcse-tutor-gemma4-31b ]; then
    sudo mv ~/fine-tuning/output/gcse-tutor-gemma4-31b \
            ~/fine-tuning/output/gcse-tutor-gemma4-31b-2026-04-10
fi

ls -la ~/fine-tuning/output/
```

`sudo` is required because Docker created those directories as `root`. Do not `chown` — it'll break in-place resume of any future GCSE run.

### 1.3 Move the previous training data aside

`~/fine-tuning/data/train.jsonl` is the GCSE study-tutor data from the previous run. Don't overwrite it; rename so future GCSE work can find it again.

```bash
if [ -f ~/fine-tuning/data/train.jsonl ] && [ ! -f ~/fine-tuning/data/train-gcse.jsonl ]; then
    mv ~/fine-tuning/data/train.jsonl ~/fine-tuning/data/train-gcse.jsonl
fi
ls -la ~/fine-tuning/data/
```

---

## Phase 2: Stage the architect dataset

```bash
# Copy the validated training data into the Docker-mounted area with a domain-tagged name
cp ~/Projects/appmilla_github/agentic-dataset-factory/output/train.jsonl "$STAGED_TRAIN"

# Sanity check the copy
diff -q ~/Projects/appmilla_github/agentic-dataset-factory/output/train.jsonl "$STAGED_TRAIN"
wc -l "$STAGED_TRAIN"

# Knowledge layer is for RAG, not fine-tuning. Stash a copy alongside for the
# eventual ChromaDB seeding step but do NOT pass it to the trainer.
cp ~/Projects/appmilla_github/agentic-dataset-factory/output/rag_index/knowledge.jsonl \
   "$FT_HOME/data/knowledge-${DOMAIN}.jsonl"
```

Why two files, not one: `train_gemma4_moe.py` reads exactly one path from `--data-path`. Mixing knowledge into `train.jsonl` would teach the model the answers to factual-recall questions verbatim, which is the opposite of what RAG-grounded behaviour fine-tuning wants ("teach the *behaviour* of looking things up; let RAG provide *what* to look up").

---

## Phase 3: Launch the training run (terminal-paste workflow)

**Important**: this phase is intentionally manual paste-from-MacBook to GB10, **not** driven from a Claude Code session running on the GB10 itself. The Claude Code → tmux → docker chain has too many moving parts and was implicated in two GB10 freezes on 2026-05-02. Run these commands directly from an SSH terminal — Claude Code can be useful for *interpreting* the output, but should not own the live launch.

### 3.1 Sync the script into the mounted scripts directory

From the GB10 host shell:

```bash
cp ~/Projects/appmilla_github/agentic-dataset-factory/docs/research/train_gemma4_moe.py \
   ~/fine-tuning/scripts/
diff ~/Projects/appmilla_github/agentic-dataset-factory/docs/research/train_gemma4_moe.py \
     ~/fine-tuning/scripts/train_gemma4_moe.py && echo "scripts match"
```

### 3.2 Start the Docker container in tmux

Open a fresh SSH from your MacBook to the GB10 (`ssh promaxgb10-41b1`), then paste this single command:

```bash
tmux new -s architect-ft "docker run --gpus all --ulimit memlock=-1 --ulimit stack=67108864 -it --rm -v \$HOME/fine-tuning/data:/workspace/data -v \$HOME/fine-tuning/output:/workspace/output -v \$HOME/fine-tuning/scripts:/workspace/scripts -v \$HOME/.cache/huggingface:/root/.cache/huggingface --entrypoint /usr/bin/bash --name architect-ft-\$(date +%Y%m%d-%H%M%S) nvcr.io/nvidia/pytorch:25.11-py3"
```

You'll land at `root@<container-id>:/workspace#` inside a tmux session named `architect-ft`.

- Detach: `Ctrl-B` then `D` — the container keeps running.
- Reattach: `tmux attach -t architect-ft`.
- The container has `--rm` set; outputs live on the bind-mounts so they persist after the container exits.

### 3.3 Install pinned dependencies (inside the container)

The base `nvcr.io/nvidia/pytorch:25.11-py3` does NOT include Unsloth, TRL, or PEFT. Each fresh `--rm` container needs them installed at the start. **The version pins below are deliberate and verified-working** — newer versions break the launch.

```bash
pip install transformers==5.5.4 peft hf_transfer "datasets==4.3.0" "trl==0.26.1" "accelerate==1.10.0"
pip install --no-deps unsloth unsloth_zoo bitsandbytes
```

Why the specific pins:

| Package | Pin | Reason |
|---|---|---|
| `transformers` | `==5.5.4` | 5.6+ added `model.vision_tower.std_bias` parameters that Unsloth's auto device-map can't resolve (`ValueError: device_map provided does not give any device for…`). 5.5.4 is the last known compatible version. |
| `accelerate` | `==1.10.0` | 1.12+ adds a strict check that rejects ANY `device_map='auto'` model in `accelerator.prepare()`, which Unsloth always uses for big MoE models on single GPUs (`ValueError: You can't train a model that has been loaded with device_map='auto' in any distributed mode`). 1.10.0 is verified working. |
| `trl` | `==0.26.1` | Matches the previous successful study-tutor run (recorded in its model card). |
| `datasets` | `==4.3.0` | Same. |
| `unsloth`, `unsloth_zoo`, `bitsandbytes` | latest (`--no-deps`) | The dep-resolver constraints from these warn about trl/transformers versions but do NOT block runtime. Ignore the pip warnings. |

You should see: `Successfully installed accelerate-1.10.0 ... transformers-5.5.4 trl-0.26.1` and `Successfully installed bitsandbytes-* unsloth-* unsloth_zoo-*`.

### 3.4 Smoke test (~14 min, recommended before full run)

Strongly recommended on any first run for a new dataset shape, model size, or seq-length. Catches OOM, bad masking, or version-pin issues at low cost.

```bash
cd /workspace/scripts
mkdir -p /workspace/output/architect-agent-gemma4-26b-moe-smoke

python train_gemma4_moe.py \
  --data-path /workspace/data/train-architect-agent.jsonl \
  --output-dir /workspace/output/architect-agent-gemma4-26b-moe-smoke \
  --chat-template gemma-4-thinking \
  --max-seq-length 2048 \
  --max-steps 60 \
  --skip-export 2>&1 | tee /workspace/output/architect-agent-gemma4-26b-moe-smoke/train.log
```

The `--max-seq-length 2048` (vs the script default 4096) halves activation memory. On the architect run this kept peak GPU memory at ~77 GB — comfortable on the 121 GB GB10. With seq-length 4096 we expect ~95-100 GB, which is too close to the freeze threshold.

Open a **second** SSH from your MacBook (separate window) to monitor:

```bash
watch -n 5 nvidia-smi
```

Healthy progression on the 26B model:
- Model load: GPU memory rises to ~50-55 GB
- During training: stable around **55-77 GB** (on architect run, peaked at ~77 GB)
- **Warning line: 100 GB** — if you see it climbing past this, hit `Ctrl-C` in the tmux pane immediately. That's the freeze precursor. Investigate before retrying.

Smoke is "passing" when:
- Tokenization completes without errors
- `Verifying response-only masking...` line prints (any percentage — see the masking note below)
- `Starting training...` followed by `{'loss': N.NNNN, ...}` lines that **decrease** over 60 steps
- Final summary `train_runtime: ..., train_loss: ...` prints with no Traceback
- Architect run actuals: 60 steps in 850s (~14 min), final loss 1.5075

**Note on masking ratio**: a low number (e.g. 27.7%) is **not** a problem for this dataset. "Masked" = system + user (ignored in loss); "unmasked" = assistant response (trained). Our dataset has very long `<think>`-heavy assistant responses (~5 KB) versus short prompts (~1.9 KB), so 27% prompt / 73% response is exactly right — the model is learning to *generate* architect reasoning, not parrot prompts. For datasets with longer prompts (multi-turn essay feedback, etc.) you'd see a higher masked ratio, also fine.

### 3.5 Full run (~70-90 min, only after smoke succeeds)

If smoke completes with declining loss, no errors, and GPU memory stayed under the warning line, kill the smoke process (which will already have exited cleanly back to the `root@…:/workspace/scripts#` prompt) and launch the full run:

```bash
mkdir -p /workspace/output/architect-agent-gemma4-26b-moe

python train_gemma4_moe.py \
  --data-path /workspace/data/train-architect-agent.jsonl \
  --output-dir /workspace/output/architect-agent-gemma4-26b-moe \
  --chat-template gemma-4-thinking \
  --max-seq-length 2048 \
  2>&1 | tee /workspace/output/architect-agent-gemma4-26b-moe/train.log
```

Same as smoke, minus `--max-steps` and `--skip-export`, with a different output dir (no `-smoke` suffix).

Architect run actuals (894 examples, 1 epoch, batch 4):

| Stage | Time |
|---|---|
| Training (224 steps) | 49 min 15s |
| LoRA adapter save | 10s |
| Merged-16bit save | ~6 min |
| GGUF export (q4_k_m) | ~16 min |
| **Total** | **~71 min** |

Loss trajectory: 2.775 (step 1) → 0.997 (step 224), train_loss mean 1.14. Smooth monotonic descent.

You can detach the tmux now and let it cook: `Ctrl-B` then `D`.

---

## Phase 4: Monitor the run

### What to watch

| Signal | Where | Healthy (architect run, 26B MoE, seq=2048) |
|---|---|---|
| Training loss | second-SSH `tail -f train.log`, lines `{'loss': …}` | Monotone-ish decrease. Architect actuals: 2.775 → 0.997. If it's flat or rising past step 5 there's a problem. |
| GPU memory | second-SSH `watch -n 5 nvidia-smi` | 50-77 GB. **Warning line: 100 GB** — see freeze recovery below. |
| GPU utilisation | nvidia-smi | 80-100% during forward/backward; brief drops between steps are normal |
| Step rate | log lines | ~13s/step on architect run (batch=1, grad_accum=4, seq=2048) |
| Disk free | `df -h ~/fine-tuning` | Stays positive; checkpoints write ~2 GB each every 100 steps. Full run produces ~123 GB total. |

### Failure modes

| Symptom | Likely cause | Fix |
|---|---|---|
| OOM at step 0 | seq length too high or other GPU consumers active | Drop `--max-seq-length` to 1024, AND verify Phase 0.5 was actually done |
| OOM mid-run on a specific example | one outlier example > seq length | Identify with `awk -F'[:,]' '/loss/ {print NR}' train.log` against `output/train.jsonl`; truncate or drop it |
| Loss flat at ~initial value | `train_on_responses_only` masking misconfigured (instruction/response markers wrong for the chat template) | Check the masking sanity print in the script output. For our long-response dataset 27% masked is fine; for shorter-response datasets expect 50-80% |
| `device_map='auto'` ValueError at start | accelerate >=1.12 strict check | Confirm `accelerate==1.10.0` is actually installed (`pip show accelerate`); newer versions get pulled in by transitive deps |
| `vision_tower.std_bias` ValueError at model load | transformers >=5.6 | Confirm `transformers==5.5.4` is installed |
| `ModuleNotFoundError: No module named 'unsloth'` | Container is fresh; deps not yet installed | Re-run the install paste from Phase 3.3 |

### GB10 freeze recovery

The GB10's unified-memory architecture means GPU memory pressure can lock the kernel — the screen freezes, SSH stops responding, and only a power-cycle recovers. **Two freezes were observed on 2026-05-02** before this runbook was hardened.

**Prevention** (this is the real fix):
1. Always do Phase 0.5 (stop llama-swap) before launching Docker
2. Use `--max-seq-length 2048`, not 4096, on the 26B MoE
3. Watch `nvidia-smi` in a second SSH and abort with `Ctrl-C` if memory exceeds 100 GB

**If a freeze happens**:
1. Power-cycle the GB10
2. Do **not** auto-run `infra-up.sh` on boot if it's wired that way; bring up only what's needed
3. After reboot, before retrying:
   - Verify GPU is empty: `nvidia-smi --query-compute-apps=pid,process_name,used_memory --format=csv` returns just the header
   - Verify staged data survived: `ls -la ~/fine-tuning/data/train-architect-agent.jsonl` exists
   - Verify backups survived: `ls -d ~/Projects/appmilla_github/agentic-dataset-factory/output_backup_post_*/`
   - Clean up any partial output: `sudo rm -rf ~/fine-tuning/output/architect-agent-gemma4-26b-moe-smoke` (if it has a stale `train.log` or partial checkpoint)
4. Restart the full procedure from Phase 3.2 (the container went away with `--rm`; deps must be reinstalled)

The state outside the container — staged data, snapshot, GCSE backup renames, training script — all survive a freeze unchanged.
| Loss explodes (NaN) | lr too high for this corpus | Drop to `--lr 5e-5`, restart with `--resume` |
| GGUF export fails at end | Common; not fatal | Use `--skip-export` next time, export manually from `merged-16bit/` |

### Estimated wall-clock

- Architect run: ~894 examples × 1 epoch / batch 4 ≈ 224 steps. At 60s/step ≈ **3.7h**.
- Smoke test (60 steps): ~1h.
- GGUF export (post-training): ~30-45 min.

---

## Phase 5: Post-training validation

When training exits cleanly, the script writes three artefact roots under `--output-dir`:

```
$OUTPUT_DIR_HOST/
├── checkpoint-N/         (intermediate every save_steps)
├── lora-adapter/         (~2 GB; small; what you'd push to HuggingFace)
├── merged-16bit/         (~50 GB; full base model + LoRA merged; vLLM-ready)
└── gguf/                 (~50 GB total; q4_k_m by default; llama.cpp / Ollama)
```

### 5.1 Inventory check

```bash
ls -la "$OUTPUT_DIR_HOST"/
du -sh "$OUTPUT_DIR_HOST"/*

# All three artefact dirs should be present and non-empty.
test -d "$OUTPUT_DIR_HOST/lora-adapter"  || echo "MISSING: lora-adapter"
test -d "$OUTPUT_DIR_HOST/merged-16bit" || echo "MISSING: merged-16bit"
test -d "$OUTPUT_DIR_HOST/gguf"         || echo "MISSING: gguf (re-export manually if needed)"
```

### 5.2 Smoke-test merged-16bit via vLLM

The fastest sanity check is a one-shot generation against a held-out architect prompt.

```bash
# In a fresh shell, outside the training container
cd ~/fine-tuning/output/architect-agent-gemma4-26b-moe/merged-16bit

# Quick HF transformers test (no vLLM needed for one-shot):
python3 - <<'PY'
from transformers import AutoTokenizer, AutoModelForCausalLM
import torch
m = AutoModelForCausalLM.from_pretrained(".", torch_dtype=torch.bfloat16, device_map="cuda")
t = AutoTokenizer.from_pretrained(".")
prompt = [{"role": "user",
           "content": "I'm building a new payments service that needs to integrate with five legacy systems. Which DDD strategic patterns should I apply first and why?"}]
inputs = t.apply_chat_template(prompt, return_tensors="pt", add_generation_prompt=True).to("cuda")
out = m.generate(inputs, max_new_tokens=600, do_sample=False)
print(t.decode(out[0][inputs.shape[1]:], skip_special_tokens=False))
PY
```

What "good" looks like:
- Output starts with `<think>…</think>` (template was preserved)
- Answer references DDD strategic patterns (bounded contexts, context maps) — confirming the dataset taught architect content
- No template-token artefacts (`<|channel>`, `<|turn>`) in the output text

### 5.3 Add the new model to llama-swap (production serve)

The full llama-swap integration recipe lives in **guardkit's** [`RUNBOOK-INFRA-ORCHESTRATION.md`](../../../guardkit/docs/runbooks/RUNBOOK-INFRA-ORCHESTRATION.md) §8 ("Adding a fine-tuned model to llama-swap"). guardkit owns the llama-swap config and supervisor; this runbook owns the dataset and fine-tune. Cross-reference rather than duplicate.

Quick summary of the steps (all done for `architect-agent` on 2026-05-03 — the worked example in guardkit's §8):

1. **Stage GGUF + Modelfile** under `/opt/llama-swap/models/<domain>/` (e.g. `architect-agent.Q4_K_M.gguf` from `~/fine-tuning/output/<domain>/gguf_gguf/`).
2. **Reuse the generic chat template** `/opt/llama-swap/config/gemma4-thinking.jinja` (created on 2026-05-03 from the gemma4-tutor file; same template suits any Gemma-4-thinking fine-tune).
3. **Add a model block** to `/opt/llama-swap/config/config.yaml`. Pattern: copy gemma4-tutor's block, swap paths and aliases, set `--temp 0.4` for architect-style determinism. Add the new model to the `matrix.vars` / `matrix.sets[all]` and `hooks.on_startup.preload` lists.
4. **Restart the daemon via the user-mode systemd unit**:
    ```bash
    systemctl --user restart llama-swap.service
    ```
    Don't `pkill` then `nohup` — that detaches the daemon from systemd and you lose `Restart=on-failure`.
5. **Update the keepalive's hardcoded model list** (`~/Projects/appmilla_github/guardkit/scripts/llama-swap-keepalive.sh`, the `MODEL_PROBE_KIND` array) so a crashed worker gets revived. **Currently a known gap** — see guardkit followups.
6. **Smoke-test** with a chat-completions request and verify `model in response: <domain>` and worker process exists for the new GGUF.

### 5.4 Verify response shape

After llama-swap is serving the new model, confirm:

| Check | What "good" looks like |
|---|---|
| Persona transfer | Domain-specific vocabulary (e.g. for architect-agent: references to Evans, "architectural tension," DDD patterns by name) — **not** generic textbook prose that any base Gemma 4 would produce |
| `<think>` tag emission | **May or may not appear depending on chat template + system prompt.** For the architect run on 2026-05-03, no literal `<think>` tags appeared in default output — the Gemma-4-thinking chat template's native `<\|channel>thought<channel\|>` framing absorbed the training's `<think>` markers. See [`FOLLOWUP-chat-template-thinking-tags.md`](FOLLOWUP-chat-template-thinking-tags.md) for the open investigation. Workaround: explicit system-prompt instruction "Begin every response with `<think>...</think>`" reliably reproduces the tag emission. |
| No template-token leaks | `<\|turn>`, `<\|channel>`, `<channel\|>` should NOT appear in user-visible content |
| Routing correctness | The `model` field in the OpenAI-compat response equals the requested model name, not a fallback (e.g. it should say `architect-agent`, not `gemma4-tutor`) |

---

## Phase 6: What's next

A working fine-tune is only step one of the architect agent's lifecycle. Open items to plan for, in roughly the order they're needed:

1. **Build a golden set** — hand-curated ~75 architect-domain examples with `expected_behaviours` and `red_flags` per the schema in `docs/research/training-pipeline-plan.md` § Evaluation strategy. Until this exists, "is the model good?" is a vibes question.
2. **Run the eval harness** against the new checkpoint. The plan describes a Claude-as-judge pipeline; reuse that.
3. **Seed the RAG index** with `~/fine-tuning/data/knowledge-architect-agent.jsonl` into a ChromaDB collection so the deployed agent has retrieval to ground its answers.
4. **Iterate**: if eval is weak, the knobs (in order of impact) are: more behaviour data → tighter Coach rubric → longer training (`--epochs 2`) → larger LoRA rank (`--lora-r 32`).

---

## Followups (open investigations / specialist briefs)

| Followup | Brief | Owned by |
|---|---|---|
| **Chat-template / `<think>` tag interaction** | The fine-tune learned the architect persona but does not emit literal `<think>...</think>` tags by default. Hypothesis: the Gemma-4-thinking chat template's native `<\|channel>thought<channel\|>` framing absorbed the training markers. See [`FOLLOWUP-chat-template-thinking-tags.md`](FOLLOWUP-chat-template-thinking-tags.md) for the full brief, observations, and three candidate paths forward. **Point a specialist agent at this file when ready to investigate.** | This repo (`agentic-dataset-factory`) |
| **Persistent llama-swap supervisor** | The user-mode systemd unit at `~/.config/systemd/user/llama-swap.service` exists and supervises the daemon, but `infra-down.sh --stop-llama-swap` only stops the *keepalive timer*, not the daemon — and `kill` + `nohup` workflows accidentally detach the daemon from systemd. Documented in detail in guardkit's [`RUNBOOK-INFRA-ORCHESTRATION.md`](../../../guardkit/docs/runbooks/RUNBOOK-INFRA-ORCHESTRATION.md) "Followups" section. | `guardkit` |

---

## Quick-reference launch (all-in-one)

Once Phase 0 is green, the verified happy path. Do these in order, **on the GB10**, mostly via SSH-paste from your MacBook:

```bash
# === On the GB10 host shell ===

# 1. Stop llama-swap (Phase 0.5)
pkill -f "llama-swap|llama-server"
sleep 3
nvidia-smi --query-compute-apps=pid,process_name,used_memory --format=csv  # expect empty

# 2. Snapshot generation output (Phase 1.1)
cd ~/Projects/appmilla_github/agentic-dataset-factory
cp -a output "output_backup_post_architect-agent_$(date +%Y%m%d-%H%M%S)"

# 3. Backup older fine-tune outputs (Phase 1.2; only if undated)
for d in gcse-tutor-gemma4-26b-moe gcse-tutor-gemma4-31b; do
    src="$HOME/fine-tuning/output/$d"
    [ -d "$src" ] && sudo mv "$src" "${src}-$(date +%Y%m%d)"
done

# 4. Move previous training data aside (Phase 1.3)
[ -f ~/fine-tuning/data/train.jsonl ] && \
    [ ! -f ~/fine-tuning/data/train-gcse.jsonl ] && \
    mv ~/fine-tuning/data/train.jsonl ~/fine-tuning/data/train-gcse.jsonl

# 5. Stage architect data and script (Phase 2 + 3.1)
cp output/train.jsonl                 ~/fine-tuning/data/train-architect-agent.jsonl
cp output/rag_index/knowledge.jsonl   ~/fine-tuning/data/knowledge-architect-agent.jsonl
cp docs/research/train_gemma4_moe.py  ~/fine-tuning/scripts/

# 6. Start container in tmux (Phase 3.2). Single line — paste as-is.
tmux new -s architect-ft "docker run --gpus all --ulimit memlock=-1 --ulimit stack=67108864 -it --rm -v \$HOME/fine-tuning/data:/workspace/data -v \$HOME/fine-tuning/output:/workspace/output -v \$HOME/fine-tuning/scripts:/workspace/scripts -v \$HOME/.cache/huggingface:/root/.cache/huggingface --entrypoint /usr/bin/bash --name architect-ft-\$(date +%Y%m%d-%H%M%S) nvcr.io/nvidia/pytorch:25.11-py3"

# === Now inside the container at root@<id>:/workspace# ===

# 7. Install pinned deps (Phase 3.3)
pip install transformers==5.5.4 peft hf_transfer "datasets==4.3.0" "trl==0.26.1" "accelerate==1.10.0"
pip install --no-deps unsloth unsloth_zoo bitsandbytes

# 8. Smoke test (Phase 3.4) — ~14 min
cd /workspace/scripts
mkdir -p /workspace/output/architect-agent-gemma4-26b-moe-smoke
python train_gemma4_moe.py \
  --data-path /workspace/data/train-architect-agent.jsonl \
  --output-dir /workspace/output/architect-agent-gemma4-26b-moe-smoke \
  --chat-template gemma-4-thinking \
  --max-seq-length 2048 \
  --max-steps 60 \
  --skip-export 2>&1 | tee /workspace/output/architect-agent-gemma4-26b-moe-smoke/train.log

# 9. Full run (Phase 3.5) — ~71 min
mkdir -p /workspace/output/architect-agent-gemma4-26b-moe
python train_gemma4_moe.py \
  --data-path /workspace/data/train-architect-agent.jsonl \
  --output-dir /workspace/output/architect-agent-gemma4-26b-moe \
  --chat-template gemma-4-thinking \
  --max-seq-length 2048 \
  2>&1 | tee /workspace/output/architect-agent-gemma4-26b-moe/train.log

# === On the GB10 host shell, after training completes ===

# 10. Bring llama-swap back up
~/path/to/infra-up.sh   # or whatever brings it up
```

In a **second** SSH from your MacBook (during steps 8-9), keep `watch -n 5 nvidia-smi` running. Abort with `Ctrl-C` in the tmux pane if memory exceeds 100 GB.

---

*Document version: 1.2 | 2026-05-03*
*Companion to `RUNBOOK-architect-dataset-pipeline.md`; assumes its Phase 6 (Stage 1 generation complete) has finished cleanly.*
*v1.1 changes (2026-05-02): added Phase 0.5 (stop llama-swap, freeze prevention); rewrote Phase 3 as terminal-paste workflow with verified version pins (`accelerate==1.10.0`, `transformers==5.5.4`); added Phase 4 freeze-recovery section; replaced estimated timings with actuals (loss 2.775→0.997, ~71 min total).*
*v1.2 changes (2026-05-03): expanded Phase 5.3 with the verified llama-swap integration recipe, cross-referencing guardkit; added Phase 5.4 response-shape verification; added Followups section pointing at the chat-template investigation and the guardkit-side supervisor gap.*
