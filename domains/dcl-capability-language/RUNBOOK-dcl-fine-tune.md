# Runbook: DCL Capability Language — Fine-Tune (Qwen3-4B-Instruct-2507, dense QLoRA)

**Purpose:** Train the **DCL pilot gift model** — a laptop-runnable fine-tune of
`Qwen/Qwen3-4B-Instruct-2507` that authors and repairs DCL capabilities. It is a **gift to
Russell East** (he published our first DCL case study; his link is a Bonsai-sized, laptop-run
model). Its one job: **make the model's FIRST authoring attempt compile clean.** The factory
chain already authors its own `.dcl` in production via a dirty-first-attempt → one bounded
repair → clean loop (6/6 derived assertions against the live service); this tune moves that
first attempt from dirty to clean.
**Machine:** Dell DGX Spark GB10 (`promaxgb10-41b1`), 121 GB unified memory.
**Base:** `Qwen/Qwen3-4B-Instruct-2507` (Apache-2.0, DENSE, non-thinking instruct). Chosen on
measured probe evidence (`fleet-evals/calibration/dcl-candidate-probes/COMPARISON-2026-07-19.md`,
pushed `9c37df5`): stock zero-shot authoring **0/9**, §10 protocol authoring **2/9**, repair
**3/3**. That profile — perfect repair (the format/vocabulary is reachable) with weak zero-shot
emission — is exactly the trainable shape the 507-row corpus fills. Gemma-4-E4B scored 0/9 and
carries a messier license for a public gift; Bonsai has no fine-tune path. Qwen's Apache-2.0
license is the tiebreak for a public gift.
**Corpus:** **507 verified rows** = 87 authors + 420 repairs, both contamination-pass. Honest
floor note: 507 rows is **BELOW** the architect runbook's `MIN_ACCEPTED = 1500` — this is a
**deliberate, Rich-approved pilot floor**, recorded here and in the staging manifest, not hidden.
**Duration (ESTIMATE — first pilot run, no actuals yet):** smoke (60 steps) ~5–10 min; full run
(~264 steps, 2 epochs) ~30–60 min incl. merge + GGUF export. A 4B is far smaller than the 26B
MoE these template runbooks were written for, so times fall accordingly.
**Companion of:** `../coach-agent/RUNBOOK-coach-fine-tune.md` (the proven Unsloth+TRL QLoRA
shape) and `../architect-agent/RUNBOOK-architect-fine-tune.md` (the domain-agnostic phase
skeleton: 0 gates → 0.5 GPU posture → 1 backup → 2 stage → 3 launch → 4 monitor → 5 validate).

> **Chat-template deviation (recorded, `OUTPUT-CONTRACT.md` left unedited):** the contract line
> names the train-time template `gemma-4`. The base moved to **Qwen3-4B-Instruct-2507** on
> 2026-07-19 probe evidence, so the train-time template is Qwen3's **native tokenizer template**
> (`<|im_start|>role\n…<|im_end|>`), NOT gemma-4. Everything downstream — the leak gates, the
> `train_on_responses_only` markers, the A/B serve — follows the Qwen3 template. The staging
> step is template-agnostic (writes ShareGPT `messages`); the trainer applies the template.

---

## The one-minute version (read this first)

You already have two banked, verified corpora on disk. The job is four moves:

1. **Stage** the corpus (`prepare_dcl_sft.py`) — it merges the two sets, drops the retired old
   author rows, oversamples the fresh authors, and runs every Phase-0 go/no-go gate. Green = go.
2. **Train** (`train_dcl_qwen3.py`) a QLoRA adapter inside the NVIDIA PyTorch container — a smoke
   first (60 steps, guards must be green + loss falling), then the full run.
3. **Merge → GGUF Q4_K_M** (done in the same script) — this is the laptop-runnable artefact.
4. **A/B on the frozen exam** — the tuned model must **demolish the stock 2/9 authoring** and
   **hold repair at 3/3**. Only then does the (Rich-gated) gift packaging happen.

One mental model: **this is the coach fine-tune with a smaller, denser base and a Qwen3
template.** Where the coach runbook says "gemma / 26B / MoE / turn markers", read "Qwen3 / 4B /
dense / im_start markers". The GPU posture is gentler (a 4B QLoRA co-exists with the live fleet;
the 26B did not) — but you still watch memory.

**Jargon, defined once:** *QLoRA* = train a small low-rank adapter on top of a 4-bit-quantised
frozen base (cheap, laptop-sized output). *LoRA adapter* = the ~tens-of-MB trained delta.
*GGUF* = the llama.cpp/Ollama single-file model format. *§10 protocol* = the machine-authoring
protocol of record: hand the model the compiler-verified vocabulary reference, and allow it one
bounded compile→repair pass. *Frozen exam* = the four `dcl-held-*` tasks, never trained on,
that grade the model. *Wedge* = a known llama.cpp hang where the server pegs the GPU mid-prompt.

---

## Inputs

```bash
DOMAIN="dcl"
REPO="$HOME/Projects/appmilla_github/agentic-dataset-factory"
SCRIPTS="$REPO/domains/dcl-capability-language"     # prepare_dcl_sft.py, train_dcl_qwen3.py

# The two banked, verified corpora (READ-ONLY; NEVER modified, NEVER committed — DF-008 private).
AUTHORS_DIR="$REPO/output_backup_dcl-authors87_20260719-040358"   # 77 train + 10 eval, all dcl_author
REPAIRS_DIR="$REPO/output_backup_dcl-corpus468_20260718-031402"   # keep dcl_repair only (48 authors RETIRED)

# Staged data + all fine-tune artefacts live OUTSIDE the repo and are NEVER committed.
FT_HOME="$HOME/fine-tuning"
STAGED_TRAIN="$FT_HOME/data/train-dcl.jsonl"        # written by prepare_dcl_sft.py
STAGED_EVAL="$FT_HOME/data/eval-dcl.jsonl"          # written by prepare_dcl_sft.py (loss-only)
STAGING_MANIFEST="$FT_HOME/data/dcl-staging-manifest.json"
OUTPUT_TAG="dcl-qwen3-4b"
OUTPUT_DIR_HOST="$FT_HOME/output/${OUTPUT_TAG}"
SMOKE_DIR_HOST="$FT_HOME/output/${OUTPUT_TAG}-smoke"

# In-container mounts (Phase 3).
DATA_PATH_CTR="/workspace/data/train-dcl.jsonl"
EVAL_PATH_CTR="/workspace/data/eval-dcl.jsonl"
OUTPUT_DIR_CTR="/workspace/output/${OUTPUT_TAG}"

# Container + pinned deps (identical to the coach runbook §3.3; pins inherited-proven from the
# 26B runs — do NOT bump).
IMAGE="nvcr.io/nvidia/pytorch:25.11-py3"
# pip install transformers==5.5.4 peft hf_transfer "datasets==4.3.0" "trl==0.26.1" "accelerate==1.10.0"
# pip install --no-deps unsloth unsloth_zoo bitsandbytes
```

The `transformers==5.5.4` / `accelerate==1.10.0` pins are **inherited-proven from the 26B runs**
(transformers 5.6+ adds `vision_tower.std_bias` params Unsloth's device-map can't resolve;
accelerate 1.12+ rejects `device_map='auto'` in `prepare()`). They hold for the 4B too.

---

## Phase 0: Stage the corpus + run the go/no-go gates

Read-only on all sources; writes ONLY to `~/fine-tuning/data/` (outside the repo). One command
runs the whole gate battery and, only if every hard gate is green, writes the staged files +
manifest:

```bash
python3 "$SCRIPTS/prepare_dcl_sft.py"        # defaults: authors87 + corpus468 -> ~/fine-tuning/data/
```

`--help` and `python3 -m py_compile` work on the bare host (no GPU deps). Useful flags:
`--author-reps K` (default 2; K=1 disables oversampling), `--seed` (default 3407, the staged
train-order shuffle), `--date YYYY-MM-DD` (pin the manifest date), `--est-chars-per-token`
(default 3.5, the seq-audit estimate). It exits **0** on all-gates-green, **1** on any hard-gate
red (and writes nothing on red).

### What the gate table means

The script prints a `PHASE-0 STAGING GATES` block. Read every line:

| Gate line | Expected | If violated |
|---|---|---|
| `count assertions` | **PASS** — `77/10 authors, 374/46 repairs` | The banked corpora changed. The script aborts loudly (hard-coded `EXPECTED`). Do not proceed. |
| `row verification` | **PASS** — every kept row has `compile_verified:true`, `[system,user,assistant]` roles, a `` ```dcl `` fence **after** `</think>` for repairs, unique `row_id` | Any fail = a bad row leaked into a banked set; STOP and inspect the printed failures. |
| `template-token leak gate` | **PASS** — 0 hits across 8 screened markers | Any hit means chat-template framing (`<\|im_start\|>`, gemma turn/channel markers) bled into content — fatal; the model would learn to emit template tokens. STOP. |
| `contamination (train/eval)` | **PASS** — `row_id ∩ = 0`, denylist violations 0 | Train/eval overlap or a frozen-exam denylist hit; STOP (never train on the eval). |
| `frozen-exam cross-check` | **PASS** — 0 hits; normalized 8-gram shingle overlap of the four `dcl-held-*` briefs vs every train row's user content | A train row reproduces exam text; STOP — the A/B would be contaminated. |
| `think coverage by mode` | **RECORD** — authors ~0% with `<think>`, repairs ~100% | Not a hard gate; confirms author rows are direct and repair rows carry the reasoning prefix (the post-think law). |
| `seq-length audit (est)` | **RECORD** — p50/p95/p99/max tok @ 3.5 ch/tok + a `RECOMMEND --max-seq-length N` line | This is an ESTIMATE. The in-container real-tokenizer audit (Phase 3.3a) is ground truth. |
| `author oversampling` | **RECORD** — `K=2 -> 154 author copies : 374 repairs = 1:2.43` | Confirms the ratio approximation (see below). |

### The two numbers that matter

- **Unique rows:** `train=451 + eval=56 = 507`. This is the honest pilot floor (below architect
  `MIN_ACCEPTED=1500`, Rich-approved). The `[RECORD]` line states it plainly.
- **Staged train rows at `--author-reps 2`:** `77 authors × 2 = 154` copies **+** `374` repairs
  **= 528 staged train rows** (eval is NEVER oversampled → 56). **Why oversample:** the ratified
  corpus target ratio was ≈1:2 (author:repair), but authors under-delivered — only 87 of 200
  briefs landed (113 hard-brief rejections = the measured zero-shot ceiling on rich constructs).
  K=2 lifts the staged mix to 154:374 ≈ **1:2.43**, approximating the ratified intent. K is
  configurable and K=1 must work (an ablation lever); the manifest records K and the rationale.

### The seq-length choice

The char-based audit recommends the smallest bucket (4096 / 6144 / 8192 / 12288) with <0.5%
truncation. DCL user turns **embed the ~12.5 KB vocabulary reference verbatim**, so rows are
prompt-heavy — the trainer defaults to **`--max-seq-length 8192`**, which a 4B at QLoRA affords
comfortably (unlike the 26B, where 8192 froze the box). Take the estimate as a floor; confirm
against the real Qwen3 tokenizer in Phase 3.3a before committing to anything below 8192.

---

## Phase 0.5: GPU posture (gentler than the 26B — but still watched)

**This is the key difference from the coach/architect runbooks.** Those fine-tuned a 26B MoE
that needed ~80–100 GB and **froze the GB10 twice** when run alongside llama-swap — so they
demand llama-swap fully down. **A 4B QLoRA is a different regime:** expected peak **~15–25 GB**,
and on 2026-07-19 the box had **~79 GB free** with the resident fleet up. So:

- **llama-swap MAY STAY UP.** The 4B QLoRA co-exists with the resident fleet on the 121 GB pool.
- **Watch rule (mandatory):** in a second shell, keep memory in view for the whole run —
  ```bash
  watch -n 5 'nvidia-smi --query-gpu=memory.used,memory.free --format=csv; free -g | head -2'
  ```
  **Abort (`Ctrl-C` in the training pane) if total used climbs past ~100 GB.** The allocator
  high-water keeps climbing over the first ~40 steps as the longest (8192-tok) rows appear
  (the 26B lesson: judge by the step-40 plateau, not step 1) — so keep watching past step 40.
- **Fallback:** if free memory is tight, or the watch shows pressure, stop llama-swap first
  (user service, no sudo) and bring it back after export:
  ```bash
  systemctl --user stop llama-swap      # free the fleet's ~40 GB
  # … run the tune …
  systemctl --user start llama-swap
  ```
- **Honest freeze history:** the 26B runs froze this box under memory pressure (a freeze needs a
  power-cycle). The 4B is a different, far lighter regime — but the watchdog discipline is kept
  because a misjudged seq-length or a stuck allocator can still climb. Watch, don't assume.

---

## Phase 1: Backup any prior artefacts

Only after Phase 0 is green. Docker writes outputs as `root`, so use `sudo mv` (never `chown` —
it breaks in-place resume):

```bash
ls -la "$FT_HOME/output/" 2>/dev/null
TS=$(date +%Y%m%d-%H%M%S)
for d in "$OUTPUT_TAG" "${OUTPUT_TAG}-smoke"; do
    src="$FT_HOME/output/$d"
    [ -d "$src" ] && sudo mv "$src" "${src}-${TS}"     # only if a prior run exists
done
ls -la "$FT_HOME/output/"
```

The banked source corpora need no backup — they are read-only and never touched by this run.

---

## Phase 2: Stage (already done in Phase 0) + sync scripts

Phase 0's `prepare_dcl_sft.py` already wrote `$STAGED_TRAIN`, `$STAGED_EVAL`, and
`$STAGING_MANIFEST`. Confirm and copy the trainer into the mounted scripts dir:

```bash
wc -l "$STAGED_TRAIN" "$STAGED_EVAL"                  # expect 528 and 56 at --author-reps 2
python3 -c "import json,sys; json.load(open('$STAGING_MANIFEST')); print('manifest OK')"

mkdir -p "$FT_HOME/scripts"
cp "$SCRIPTS/train_dcl_qwen3.py" "$FT_HOME/scripts/"
diff -q "$SCRIPTS/train_dcl_qwen3.py" "$FT_HOME/scripts/train_dcl_qwen3.py" && echo "script synced"
```

Nothing under `~/fine-tuning` is ever committed.

---

## Phase 3: Launch (SSH-paste workflow)

Per the sibling runbooks, run the live launch directly from an SSH terminal (Claude interprets
output, does not own the launch). With llama-swap staying up you do **not** need the manual
freeze-prevention paste — but keep the Phase-0.5 watch shell open.

### 3.1–3.2 Container

Start the NVIDIA PyTorch container in tmux with the standard bind-mounts (data, output, scripts,
the HF cache). Single line — paste as-is:

```bash
tmux new -s dcl-ft "docker run --gpus all --ulimit memlock=-1 --ulimit stack=67108864 -it --rm \
  -v \$HOME/fine-tuning/data:/workspace/data \
  -v \$HOME/fine-tuning/output:/workspace/output \
  -v \$HOME/fine-tuning/scripts:/workspace/scripts \
  -v \$HOME/.cache/huggingface:/root/.cache/huggingface \
  --entrypoint /usr/bin/bash --name dcl-ft-\$(date +%Y%m%d-%H%M%S) nvcr.io/nvidia/pytorch:25.11-py3"
```

Detach `Ctrl-B D`, reattach `tmux attach -t dcl-ft`. Outputs persist on the bind-mounts after the
`--rm` container exits.

### 3.3 Deps (inside the container — pins matter)

```bash
pip install transformers==5.5.4 peft hf_transfer "datasets==4.3.0" "trl==0.26.1" "accelerate==1.10.0"
pip install --no-deps unsloth unsloth_zoo bitsandbytes
```

The base download of `Qwen/Qwen3-4B-Instruct-2507` (~8 GB safetensors) happens on first model
load, into the mounted HF cache. `[G1]` (below) catches a mis-attached LoRA if the Unsloth build
is wrong.

### 3.3a Real-tokenizer seq audit (ground-truth the max-seq-length)

The Phase-0 audit is a char estimate. Confirm with the actual Qwen3 tokenizer once, in the
container (adapted from the coach runbook 0.2 pattern to the Qwen3 native template — **no
`get_chat_template` call**; the Qwen3-Instruct-2507 tokenizer ships its own `<|im_start|>` template):

```python
# in-container REPL, after deps are installed
import json
from unsloth import FastLanguageModel
_, tok = FastLanguageModel.from_pretrained(
    "Qwen/Qwen3-4B-Instruct-2507", max_seq_length=8192,
    load_in_4bit=True, full_finetuning=False)
L = []
for line in open("/workspace/data/train-dcl.jsonl"):
    if not line.strip():
        continue
    convo = json.loads(line)["messages"]
    t = tok.apply_chat_template(convo, tokenize=True, add_generation_prompt=False)
    L.append(len(t))
L.sort(); n = len(L)
for thr in (4096, 6144, 8192):
    print(thr, f"{sum(x>thr for x in L)}/{n} ({100*sum(x>thr for x in L)/n:.1f}%) exceed")
print("p95", L[int(.95*n)], "p99", L[int(.99*n)], "max", L[-1])
```

**Decision rule:** if real p99 ≤ 8192 (expected — the vocab reference dominates length), keep the
`--max-seq-length 8192` default. Only drop it if you need to shave memory AND p99 fits the smaller
bucket; only raise it (to 12288) if p99 exceeds 8192, watching memory closely.

### 3.4 Smoke run (~5–10 min) — the baked-in guards do the validating

```bash
cd /workspace/scripts
mkdir -p /workspace/output/dcl-qwen3-4b-smoke
python train_dcl_qwen3.py \
  --data-path /workspace/data/train-dcl.jsonl \
  --eval-path /workspace/data/eval-dcl.jsonl \
  --output-dir /workspace/output/dcl-qwen3-4b-smoke \
  --max-steps 60 --skip-export 2>&1 | tee /workspace/output/dcl-qwen3-4b-smoke/train.log
```

> **Do NOT judge pass/fail from the `tee`'d log's tail.** `tee` masks the real exit code (a
> BINDING §0 lesson — a red push happened that way). If you script the smoke, capture the
> trainer's own `$?` separately: `python train_dcl_qwen3.py …; rc=$?; … | tee …` won't do it —
> run the python **without** the pipe when you need the exit code, or check the log for the final
> `Training complete.` line AND the absence of any `ABORT [Gn]` / `Traceback`.

`train_dcl_qwen3.py` prints five guards. The smoke PASSES only if all are green **and** loss falls:

| Guard | Pass condition |
|---|---|
| **[G1]** trainable % | `Trainable params: … (~1–3%)`. A dense 4B LoRA (q/k/v/o + gate/up/down) sits ~1–3%. Aborts if `< --min-trainable-pct` (default 0.1) — that means the adapter did not attach. |
| **[G2]** template render | first rendered example contains `<\|im_start\|>user` AND `<\|im_start\|>assistant` AND **no** gemma tokens (`<start_of_turn>`, `<end_of_turn>`, `<\|turn>`, `<\|channel>`). Aborts otherwise — train==serve alignment would break. |
| **[G3]** attention impl | prints the attention implementation (informational). |
| **[G4]** masking | `train_on_responses_only` masked %. DCL user turns embed the vocab reference (long prompts) vs shorter `` ```dcl `` answers, so a **HIGH** masked % (~70–95%) is EXPECTED and correct. Aborts only at ~0% or ~100% (markers wrong). |
| **[G5]** peak memory | reported `peak GPU memory` — a dense 4B QLoRA should sit well under ~40 GB. Keep watching `nvidia-smi` past step 40 (the high-water climbs as the longest rows appear). |
| loss | `{'loss': …}` lines **decreasing** over 60 steps. |
| `[think]` | informational: `N/528 staged train rows contain <think>` — expect = the repair rows only (author rows are direct). |

### 3.5 Full run (~30–60 min incl. export) — only after the smoke is all-green

```bash
mkdir -p /workspace/output/dcl-qwen3-4b
python train_dcl_qwen3.py \
  --data-path /workspace/data/train-dcl.jsonl \
  --eval-path /workspace/data/eval-dcl.jsonl \
  --output-dir /workspace/output/dcl-qwen3-4b \
  2>&1 | tee /workspace/output/dcl-qwen3-4b/train.log
```

Defaults (from `train_dcl_qwen3.py`): base `Qwen/Qwen3-4B-Instruct-2507`, `--max-seq-length 8192`,
LoRA `r=16 / alpha=32 / dropout=0`, `--lr 2e-4` cosine, `--warmup-ratio 0.03`, `--batch-size 1
--grad-accum 4` (effective batch 4), `--epochs 2`, `optim adamw_8bit`, `--seed 3407`, GGUF
`q4_k_m`. **Step estimate:** 528 staged train rows / eff-batch 4 × 2 epochs ≈ **264 steps**
(ESTIMATE). **Why 2 epochs:** a single epoch under-fits a 507-row corpus; 2 lifts first-attempt
quality without memorising (the pilot-floor trade, recorded not hidden). Detach tmux and let it
cook; keep the watch shell open.

---

## Phase 4: Monitor

| Signal | Where | Healthy (4B QLoRA, seq 8192 — ESTIMATE, no actuals yet) |
|---|---|---|
| Training loss | `tail -f train.log`, `{'loss': …}` lines | Monotone-ish decrease. Flat/rising past ~step 5 = a problem (suspect masking). |
| GPU / system memory | second-SSH watch (Phase 0.5) | Expect ~15–25 GB for the tune; with the fleet up, total well under 100 GB. **Abort at ~100 GB.** |
| Step rate | log lines | A 4B is fast; a stall to zero throughput mid-step = suspect the llama.cpp wedge on a co-resident worker (see below). |
| Disk free | `df -h ~/fine-tuning` | Stays positive; the merged-16bit + GGUF export writes several GB at the end. |

### Failure modes

| Symptom | Likely cause | Fix |
|---|---|---|
| `ABORT [G1]` trainable ~0% | Unsloth build didn't attach the LoRA to the dense modules | Upgrade Unsloth; re-check `target_modules`. |
| `ABORT [G2]` gemma tokens present / im_start absent | wrong template applied | Confirm no `get_chat_template` gemma call slipped in; the Qwen3 tokenizer template must render. |
| `ABORT [G4]` masked ~0% or ~100% | `train_on_responses_only` markers wrong | The markers are `<\|im_start\|>user\n` / `<\|im_start\|>assistant\n` — a gemma template would break them. |
| `vision_tower.std_bias` / `device_map='auto'` ValueError | transformers 5.6+ / accelerate 1.12+ pulled in | Confirm `transformers==5.5.4` and `accelerate==1.10.0` are the installed versions. |
| GPU pegged, step rate → 0, a co-resident llama-server hangs | **the llama.cpp WEDGE** (§0 lesson) | SIGKILL the wedged `llama-server` child **BY PORT** (read the port from llama-swap `/running`'s proxy field) — **never `pkill -f` a pattern** (it self-matches your own command and has killed tasks twice). Respawn cures it. |
| GGUF export fails at the end | common, non-fatal | The script prints a non-fatal note; export manually from `merged-16bit/`. |

---

## Phase 5: Post-training validation

The full run writes three artefact roots under `--output-dir`:

```
~/fine-tuning/output/dcl-qwen3-4b/
├── lora-adapter/     (small; the pushable adapter)
├── merged-16bit/     (full base + LoRA merged; HF-ready)
└── gguf/             (q4_k_m; the laptop-runnable gift artefact)
```

### 5.1 Inventory

```bash
ls -la "$OUTPUT_DIR_HOST"/ ; du -sh "$OUTPUT_DIR_HOST"/*
test -d "$OUTPUT_DIR_HOST/lora-adapter"  || echo "MISSING: lora-adapter"
test -d "$OUTPUT_DIR_HOST/merged-16bit"  || echo "MISSING: merged-16bit"
test -d "$OUTPUT_DIR_HOST/gguf"          || echo "MISSING: gguf (re-export manually if needed)"
```

### 5.2 Quick generation sanity (merged-16bit)

A one-shot check that the tune learned to author DCL, before the full A/B. In a fresh shell,
inside a container with the deps (or via HF transformers):

```python
from transformers import AutoTokenizer, AutoModelForCausalLM
import torch
m = AutoModelForCausalLM.from_pretrained(".", torch_dtype=torch.bfloat16, device_map="cuda")
t = AutoTokenizer.from_pretrained(".")
prompt = [{"role": "user", "content": "<a DCL feature brief + the vocab reference, per OUTPUT-CONTRACT §2>"}]
inputs = t.apply_chat_template(prompt, return_tensors="pt", add_generation_prompt=True).to("cuda")
out = m.generate(inputs, max_new_tokens=600, do_sample=False)
print(t.decode(out[0][inputs.shape[1]:], skip_special_tokens=False))
```

**What good looks like:** exactly one fenced `` ```dcl `` block, using ONLY the closed vocabulary
(no invented literals), no `<|im_start|>` / gemma template tokens leaked into the visible text.
This is a vibe check, not the verdict — the frozen exam (Phase 6) is the verdict.

---

## Phase 6: A/B on the frozen exam (the verdict phase)

The tuned model must beat its own stock base on the SAME frozen exam that produced the
COMPARISON numbers. **This is the gate that decides whether the pilot shipped.**

### 6.1 Stage the tuned GGUF + add a llama-swap entry

Copy the tuned GGUF beside the stock probe model, then add a serving entry **beside** the
existing `dcl-probe-qwen3-4b` (same shape; co-resident probe-set pattern). The stock entry lives
in `/opt/llama-swap/config/config.yaml` and points at
`~/dcl-probe-models/qwen3-4b/Qwen3-4B-Instruct-2507-Q4_K_M.gguf`; a config backup already exists
at `/opt/llama-swap/config/config.yaml.bak-20260718-pre-dclprobes`.

```bash
mkdir -p ~/dcl-probe-models/qwen3-4b-tuned
cp ~/fine-tuning/output/dcl-qwen3-4b/gguf/*.gguf ~/dcl-probe-models/qwen3-4b-tuned/
# Back up the config, then add a `dcl-tuned-qwen3-4b` model block cloned from `dcl-probe-qwen3-4b`:
#   same llama-server cmd, --alias dcl-tuned-qwen3-4b, --model <the tuned gguf>, ttl 1800,
#   checkEndpoint /health. Mirror it into a probe set the same way pq/probe_q were added.
# Then reload the user service (no sudo):
systemctl --user restart llama-swap
```

> Editing `/opt/llama-swap/config/config.yaml` and touching `~/dcl-probe-models/` are **operator
> actions outside this repo** — this runbook documents them; it does not perform them. Keep the
> `.bak-20260718-pre-dclprobes` backup discipline (make a fresh dated backup before editing).

### 6.2 Run the frozen exam — the exact protocol

Harness: `fleet-evals/harness/run_dcl_heldout.py` against llama-swap `:9000`. Tasks:
`dcl-held-001-author-stats`, `dcl-held-002-author-version`, `dcl-held-003-author-uptime`
(author) + `dcl-held-004-repair-diagnostics` (repair). Two conditions × K=3 reps:

- **zero-shot** — the bare task (no extra flags).
- **§10 protocol** — `--vocab-ref harness/dcl/vocab-reference.md --repair-loop` (append the
  compiler-verified vocabulary reference; allow one bounded compile→repair pass; the graded
  candidate is the FINAL response).

Per rep (run from the `fleet-evals` repo root; the runner NEVER grades — the task's pytest
battery does, shelling the vendored DCL compiler over `response.dcl`):

```bash
# one rep of one task, one condition:
python3 harness/run_dcl_heldout.py \
  --task-dir tasks/dcl-held-001-author-stats \
  --out <rep-output-dir> --rep <n> \
  --model dcl-tuned-qwen3-4b \
  --endpoint http://127.0.0.1:9000/v1/chat/completions \
  --freeze-commit <frozen dcl-heldout-suite-scope.md sha> \
  --refreeze-commit 8a3b9d1 \
  [--vocab-ref harness/dcl/vocab-reference.md --repair-loop]   # §10 condition only

# grade that rep (the task's gate battery):
PO_EVAL_OUTPUT_DIR=<rep-output-dir> python3 -m pytest tasks/dcl-held-001-author-stats/test -q
```

Repeat for all four tasks × both conditions × K=3. The runner enforces the single-slot law (GET
`<base>/running` must show `dcl-tuned-qwen3-4b` `ready` before generating). Capture each pytest
`$?` **separately** — never infer pass/fail from a `tee`/`tail` of the output (§0 lesson).

**Wedge cure (build-lane hazard):** if the runner reports **2 consecutive failures**, the
llama.cpp server has likely wedged — **SIGKILL the `llama-server` child BY PORT** (read the port
from `/running`'s proxy field), **never by pattern** (`pkill -f` self-matches). Respawn and
resume; a bad `.dcl` is a RESULT, not a wedge — do not confuse the two.

### 6.3 The bar (verbatim)

The tuned model must **demolish the stock protocol authoring score of 2/9 decisively AND hold
repair at 3/3.** Stock reference numbers (Qwen3-4B, `COMPARISON-2026-07-19.md`): zero-shot
authoring 0/9, zero-shot repair 3/3, §10-protocol authoring 2/9. A pass is a large authoring gain
(the whole point of the tune — first attempts landing clean) with repair still perfect.

### 6.4 Record the verdict

Write a graded RESULTS doc to
`fleet-evals/calibration/dcl-candidate-probes/dcl-tuned-qwen3-4b/` (per-rep grades + a summary
table) plus a comparison against `COMPARISON-2026-07-19.md` (tuned vs stock, both conditions,
same exam). Numbers, then a one-line bar verdict. This doc is the evidence Rich sees before the
gift ships.

---

## Phase 7: Gift packaging — RICH-GATED (do NOT run unprompted)

**Only after** the Phase-6 A/B verdict passes **and** Rich makes two explicit calls:
1. **Publication surface** — where the gift is published.
2. **Whether the corpus ships** — DF-008 default is **corpus PRIVATE**; the synthetic-only
   training slice already holds (harvested W2b briefs would need redaction review before any
   public training use). Do not publish the corpus without his word.

When he says go, the gift bundle is:

- **HuggingFace:** the `merged-16bit/`, the `gguf/` (q4_k_m — the laptop-runnable target), and
  the `lora-adapter/`.
- **Model card** citing the case studies (all in `ai-transition/docs/research/`):
  `dcl-case-study-2026-07.md`, `dcl-adoption-case-study-2026-07.md`,
  `dcl-gift-model-case-study-2026-07.md` (and `dcl-machine-authoring-case-study-2026-07.md` if
  useful) — with **Apache-2.0 NOTICE retention** for the Qwen3 base.
- **Ollama Modelfile** pointing at the GGUF (the laptop one-liner — the gift's whole point).

The gift is for **Russell East** (he published our first case study; laptop-runnable is the
promise). Package for that: a small model a non-specialist can `ollama run` and use to author DCL.

---

## Artefacts (this domain)

| File | Purpose |
|---|---|
| `prepare_dcl_sft.py` | stage authors87 + corpus468 → ShareGPT train/eval + oversample + all Phase-0 gates → `~/fine-tuning/data/` + manifest (host-runnable, no ML deps) |
| `train_dcl_qwen3.py` | the fine-tune (Qwen3-4B dense QLoRA defaults + baked-in `[G1]`–`[G5]` guards; native Qwen3 template; merge + GGUF export) |
| `RUNBOOK-dcl-fine-tune.md` | this runbook (stage → train → merge/GGUF → A/B → gift) |
| `OUTPUT-CONTRACT.md` | the row envelope + metadata contract (note: names `gemma-4`; superseded to Qwen3 native template on 2026-07-19 probe evidence — see the deviation note above) |
| `COMPARISON-2026-07-19.md` (`fleet-evals/calibration/dcl-candidate-probes/`) | the probe evidence the base choice rests on (stock 0/9 · 2/9 · 3/3) |

*Document version: 1.0 | 2026-07-19 | Companion to `../coach-agent/RUNBOOK-coach-fine-tune.md`
(the QLoRA shape) and `../architect-agent/RUNBOOK-architect-fine-tune.md` (the phase skeleton).*
