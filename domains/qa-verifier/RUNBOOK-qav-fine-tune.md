# Runbook: QAV Judgment Seat — Fine-Tune (Gemma-4-26B-A4B MoE, 16-bit LoRA)

**Purpose:** Train the **QAV pilot PROBE** — a fine-tune of `unsloth/gemma-4-26B-A4B-it` that
reads a CoachEvidenceBundle and renders **approve / reject-with-findings** (the L5 judgment
layer the deterministic L1–L4 gates structurally cannot be). Rich ruled **Option A on plateau
card #2 (2026-07-22): the pilot tune fires on the 108-corpus.** This is a **probe, not an
adoption** — the deploy gate is FEAT-EVAL-QAV (the frozen qav-held exam), NOT this run.
**Machine:** Dell DGX Spark GB10, 121 GB unified memory.
**Base:** `unsloth/gemma-4-26B-A4B-it` (bf16 MoE) — the **coach-ft lineage**, same served base
as the coach/PO judgment fleet, satisfying the **D9 different-family rule** (the judged Player
is gpt-oss/frontier Claude; the judge is Gemma). Base **TRAINING weights are on disk** (see
"Base-weights finding" below) — no download needed.
**Corpus:** **108 verified rows** = 86 train + 22 held-out eval (`output/qa-verifier/`), the
split already applied by the factory. Honest floor note: 108 rows is a **deliberate pilot probe
floor**, far below any production adoption bar — recorded here and in the staging manifest, not
hidden. Balance is enforced **at generation** (SCOPE §3 delta 2), so staging **never
oversamples**: 41 approve / 45 reject train, ugly-green share 0.95 of approves.
**Companion of:** `../coach-agent/RUNBOOK-coach-fine-tune.md` (the proven Unsloth+TRL LoRA shape
on this exact base) and `../dcl-capability-language/RUNBOOK-dcl-fine-tune.md` (the three
serving-contract catches this runbook re-applies).

---

## The one-minute version (read this first)

The corpus is already banked and split on disk. The job is four moves:

1. **Stage** (`prepare_qav_sft.py`) — reads `output/qa-verifier/{train,eval_qav}.jsonl`, runs
   every Phase-0 gate, and writes **bare-verdict-JSON** targets to `~/fine-tuning/data/`. Green
   = go. (Verified end-to-end on the real 108-corpus: all hard gates PASS.)
2. **Train** (`train_qav.py`) a 16-bit LoRA inside the NVIDIA PyTorch container — a smoke first
   (guards green + loss falling), then the full run.
3. **Merge → (Phase-5.2 merged-gen sanity, MANDATORY) → GGUF q4_k_m.**
4. **A/B on the frozen exam** (qav-held-001/002) — must **catch 4/4 gold negatives** and hold
   the over-reject ceiling on the honest greens. Only then does any deploy decision happen.

**One mental model: this is the coach fine-tune with a different target format.** Where the
coach emits a fenced verdict directly, the QAV corpus rows carry a `<think>` block + a `` ```json ``
fence — and both are **stripped at staging** so the trained target byte-matches what the QAV
serving contract asks the model to emit: **only a bare JSON verdict object.** Same base, same
gemma-4 non-thinking template, same 16-bit-LoRA-because-MoE-QLoRA-is-blocked, same GB10 memory
discipline.

**Jargon, defined once:** *LoRA adapter* = the small trained delta on the frozen base.
*16-bit LoRA (not QLoRA)* = the 26B-A4B MoE's 3D fused expert tensors block 4-bit quantised
training, so the base loads in 16-bit (the coach finding). *GGUF* = the llama.cpp/Ollama
single-file serving format. *Frozen exam* = the two `qav-held-*` tasks (the 4 gold negatives +
the honest greens), never trained on, that grade the model. *Bundle* = a `CoachEvidenceBundle`,
the serialized evidence about one task turn — the QAV's input.

---

## Base-weights finding (the load-bearing check)

**PRESENT — no substitution needed.** The SCOPE names `gemma-4-26B-A4B` (coach-ft lineage). The
**training weights (HF safetensors, not GGUF)** are on disk in the HF cache:

```
~/.cache/huggingface/hub/models--unsloth--gemma-4-26b-a4b-it/snapshots/<sha>/
    model-00001-of-00002.safetensors   (47 GB)
    model-00002-of-00002.safetensors   (1.6 GB)
    config.json                        (architectures: Gemma4ForConditionalGeneration)
```

This is the same base the coach-ft-v3 run trained on — the coach artifacts confirm both the
base and the recipe: `~/fine-tuning/output/coach-gemma4-26b-moe-v3/` (lora-adapter +
merged-16bit + gguf) and the served entry `/opt/llama-swap/models/coach-ft-v3`. `train_qav.py`
is a direct fork of `../coach-agent/train_coach_moe.py`, so the loader, template, and LoRA
config are already proven on these exact weights. **If this cache is ever evicted, the run
re-downloads `unsloth/gemma-4-26B-A4B-it` on first model load (~49 GB) into the mounted HF
cache — never silently swap to the E4B or 31B variant on disk (different family/size).**

---

## The serving contract + the target format (why bare JSON parses)

The QAV serving surface is `fleet-evals/harness/run_qav_heldout.py` against llama-swap `:9000`.
Per bundle it composes **one** chat completion:

- **system** = the pinned seat line, ending: *"output ONLY the verdict JSON object the contract
  specifies — no prose, no explanation, no markdown fences."*
- **user** = the task's `instruction.md` verbatim + that bundle's `bundle.json` inlined.
- **sampling** = temperature 0.1, top_p 0.9, **max_tokens 2048**, no grammar.

**Verdict extraction** (`extract_json`): a `` ```json `` fence **first**, else the **first
balanced `{…}` object**. The balanced-object scanner is the **robust** path: the fence regex
`` ```(?:json)?\s*(\{.*?\})\s*``` `` is non-greedy, so on a real verdict `{"verdict":…,
"findings":[{"class":…,"locus":…}]}` it captures only up to the first `}` (the inner finding),
which fails `json.loads` and falls through to the balanced scanner. `_first_balanced_object`
depth-counts braces (honoring string literals) and returns the whole object.

**Therefore the trained target is a BARE verdict JSON object** —
`{"verdict":…, "findings":[{"class","locus"}], "ground_truth_source":…}` — with **no `<think>`
block and no `` ```json `` fence.** That is exactly what the system prompt asks the model to
emit, and it parses cleanly under `_first_balanced_object`. (The graded contract in
`instruction.md` is the two keys `verdict`+`findings`; `ground_truth_source` is a tolerated
extra kept from the banked label.) The corpus rows on disk carry think + fence (OUTPUT-CONTRACT
§1); staging strips both. **Verified:** every one of the 86 staged train targets round-trips
through a replica of the exam extractor.

---

## The three DCL-tune catches, as binding law for QAV

These are the serving-contract laws the DCL pilot paid for in burned probe cycles. Each is
enforced in code here.

**LAW 1 — force the serving template; ban the silent hybrid swap.** The template is `gemma-4`
(**NON-thinking**), applied via `get_chat_template` — the coach-proven serving template,
embedded into the GGUF at export and verified by the export→serve round-trip. `train_qav.py`'s
`[GT]` guard **refuses `--chat-template gemma-4-thinking`** (the tutor template-leak lesson)
**and asserts the applied template carries no thinking-only constructs** (`reasoning_content` /
reverse-slice — the exact swap the DCL live-catch banned). `--chat-template-file` forces a stock
gemma jinja verbatim if the embedded one ever misbehaves (the coach SERVING fallback); a
thinking-template file is refused. *(For the DCL/Qwen base the swap was a file; for gemma the
named non-thinking template + the swap-ban guard + the round-trip are the enforcement — the
estate has no bespoke gemma jinja on disk, and the coach RESULTS confirmed the exported
non-thinking template serves with no `<|channel>thought`/`<|turn>` leakage.)*

**LAW 2 — never train targets on near-untrained added tokens.** The QAV corpus rows carry a
`<think>` block; `prepare_qav_sft.py` **strips it from staged targets by default**
(`--keep-think` restores). The trainer's `[G6]` aborts if any rendered target still contains
`<think>`. *(In gemma-4 the literal `<think>` is ordinary text, not a special token, so the
DCL collapse-onto-`<tool_call>` mechanism does not apply here — but the serving contract still
bans reasoning prose, and a long think block would risk truncating the END-positioned verdict
under max_tokens=2048. Strip is the byte-match cure either way.)*

**LAW 3 — staged targets must byte-match the serving contract.** The serving prompt demands
bare JSON with no markdown fences; `prepare_qav_sft.py` **unwraps the `` ```json `` fence to a
bare object by default** (`--keep-fence` restores), locating the verdict fence under the
**post-think law** (a fence inside `<think>` quotes evidence, never the verdict). The trainer's
`[G6]` aborts on any `` ``` `` in a rendered target span.

---

## Phase 0: Stage the corpus + run the go/no-go gates

Read-only on all sources; writes ONLY to `~/fine-tuning/data/` (outside the repo). One command
runs the whole gate battery and, only if every hard gate is green, writes the staged files +
manifest:

```bash
python3 domains/qa-verifier/prepare_qav_sft.py        # defaults -> ~/fine-tuning/data/
```

`--help` and `python3 -m py_compile` work on the bare host (stdlib only). Flags: `--keep-think`
/ `--keep-fence` (ablation — restore the banked shape; **if you keep either, the serving
contract or max_tokens must change to match, which re-freezes the exam — do not do this lightly**),
`--seed` (default 3407), `--date`, `--est-chars-per-token` (default 3.5). Exit **0** on
all-green, **1** on any red (writes nothing on red).

### The gate table (verified on the real 108-corpus, 2026-07-23)

| Gate | Expected / observed | If red |
|---|---|---|
| `row verification` | **PASS 108/108** — roles `[system,user,assistant]`, a `<think>` block, a post-think `` ```json `` fence, verdict∈{approve,reject}, approve⇒`findings:[]`, reject⇒≥1 finding with an admissible DC class (DC-03/05/08/12/14) + a non-empty locus, `ground_truth_source` in the enum | a bad row is banked; STOP and inspect the printed failures |
| `template-token leak gate` | **PASS** — 0 hits across 8 screened markers (gemma `<\|turn>`/`<\|channel>`/`<start_of_turn>`/`<end_of_turn>` + qwen) | any hit = chat-template framing bled into content; fatal, STOP |
| `contamination (train/eval)` | **PASS** — train∩eval `row_id` = 0 | overlap; STOP (never train on the eval) |
| `frozen-exam cross-check` | **PASS** — 0 hits; normalized 8-gram shingle overlap of the 2 `qav-held-*` exams' bundle bodies (GN-1..GN-4 + the honest greens) vs every train row's user content | a train row reproduces an exam bundle; STOP — the A/B would be contaminated |
| `class-balance tripwire` | **PASS** — staged train `by_verdict` {approve:41, reject:45} and `by_dc_class` {DC-03:27, DC-05:3, DC-08:8, DC-14:7} **byte-match** `output/qa-verifier/manifest.json` counts | mismatch = the corpus changed under the manifest (the coach-v2 81/19→87.5% false-approval saga is why this is a hard gate) |
| `target transform` | **RECORD** — `strip_think=True strip_fence=True` (default ⇒ bare verdict JSON) | — |
| `seq-length audit (est)` | **RECORD + LOUD** — see the seq-length blocker below | this is the critical gate; the real-tokenizer audit is ground truth |

### The seq-length blocker (SURFACE THIS TO RICH — the run's real risk)

QAV rows are **by far** the longest in the fleet: the user turn is a full serialized bundle and
**the verdict sits at the END**, so any truncation eats the label (SCOPE §3 delta 3, the coach
lesson squared). The char-estimate audit over the 108-corpus (3.5 ch/tok) reports:

```
p50 ≈ 4.7k tok   p95 ≈ 15.8k tok   p99 ≈ 52k tok   max ≈ 61k tok
exceed 4096 = 57% · 6144 = 39% · 8192 = 25% · 12288 = 10%
```

(Max row ≈ 214 KB of characters.) **This means `--max-seq-length 8192` would truncate ~25% of
rows — silently eating the verdict on a quarter of the corpus.** Even 12288 truncates ~10%, and
12288 is **GB10-memory-risky** on this 26B (the coach found seq≥6144 OOM-climbs over an epoch).
Two things follow, both BEFORE the full run:

1. **Run the real-tokenizer audit (Phase 3.3a) — it is ground truth, not the char estimate.**
   The 3.5 ch/tok ratio may over- or under-count JSON-heavy bundles.
2. **Decide a truncation/exclusion strategy with a dated note — NEVER silent tail loss**
   (SCOPE §3.3): e.g. a documented max-seq at the memory ceiling **plus** excluding or
   bundle-trimming the handful of giant rows (record which `row_id`s and why), or a
   left-truncation-that-preserves-the-tail approach. This is a Rich/operator decision the
   probe is gated on. `train_qav.py` defaults to `--max-seq-length 8192` as a *starting point
   only* — the real audit + this decision govern.

---

## Phase 0.5 → Phase 3: GPU posture, backup, launch

Follow `../coach-agent/RUNBOOK-coach-fine-tune.md` §0.5–§3 verbatim — same base, same box, same
container. Key carries:

- **26B posture is heavier than the DCL 4B.** llama-swap freed the fleet's memory for the coach
  26B runs; keep the mandatory second-shell watch
  (`watch -n5 'nvidia-smi --query-gpu=memory.used,memory.free --format=csv; free -g|head -2'`)
  and **abort past ~100 GB.** Manual SSH-paste launch, never Claude→tmux→docker from the GB10
  (two documented freezes).
- **Deps (pins inherited-proven):** `transformers==5.5.4 peft hf_transfer "datasets==4.3.0"
  "trl==0.26.1" "accelerate==1.10.0"` then `--no-deps unsloth unsloth_zoo bitsandbytes`.
- **Container bind-mounts:** `~/fine-tuning/{data,output,scripts}` + `~/.cache/huggingface`.
  Copy `train_qav.py` into `~/fine-tuning/scripts/` before launch.

### 3.3a Real-tokenizer seq audit (ground-truth the max-seq-length — MANDATORY)

In-container, after deps, on the real gemma-4 tokenizer:

```python
import json
from unsloth import FastModel
_, tok = FastModel.from_pretrained("unsloth/gemma-4-26B-A4B-it",
    max_seq_length=12288, load_in_4bit=False, load_in_16bit=True, full_finetuning=False)
from unsloth.chat_templates import get_chat_template
tok = get_chat_template(tok, chat_template="gemma-4")
L=[]
for line in open("/workspace/data/train-qav.jsonl"):
    if not line.strip(): continue
    convo=json.loads(line)["messages"]
    L.append(len(tok.apply_chat_template(convo, tokenize=True, add_generation_prompt=False)))
L.sort(); n=len(L)
for thr in (4096,6144,8192,12288):
    print(thr, f"{sum(x>thr for x in L)}/{n} ({100*sum(x>thr for x in L)/n:.1f}%) exceed")
print("p95",L[int(.95*n)],"p99",L[int(.99*n)],"max",L[-1])
```

Feed the result into the truncation/exclusion decision above **before** committing a
`--max-seq-length`.

### 3.4 Smoke run (~guards do the validating)

```bash
cd /workspace/scripts && mkdir -p /workspace/output/qav-gemma4-26b-moe-smoke
python train_qav.py \
  --data-path /workspace/data/train-qav.jsonl \
  --eval-path /workspace/data/eval-qav.jsonl \
  --output-dir /workspace/output/qav-gemma4-26b-moe-smoke \
  --max-steps 40 --skip-export 2>&1 | tee .../train.log
```

> **Do NOT judge pass/fail from the `tee`'d tail** (a BINDING lesson — `tee` masks the exit
> code). Check for the final `Training complete.` line AND the absence of any `ABORT [Gn]` /
> `Traceback`.

The smoke PASSES only if all guards are green **and** loss falls:

| Guard | Pass condition |
|---|---|
| **[G1]** trainable % | `~1.88%` (MoE experts attached, PR #4913). Aborts `< --min-trainable-pct` (1.0). |
| **[GT]** template | `gemma-4` (non-thinking) applied; thinking-template constructs → hard abort (LAW 1). |
| **[G2]** render | first example has `<\|turn>user` + `<\|turn>model`. Aborts otherwise. |
| **[G3]** attention | `sdpa` (FA2 crashes on gemma head_dim 512). |
| **[G6]** target-format | `think=0/N fenced=0/N` rendered targets (LAWS 2+3). Aborts otherwise unless `--allow-think-targets`. |
| **[G4]** masking | **HIGH masked% (~85–99%)** EXPECTED — the bundle prompt is huge, the bare verdict tiny (the OPPOSITE of the coach's ~29%). Aborts at ~0% (markers wrong) **or a full ~100% (the target was truncated/masked away — the seq-length label-loss you must not ship)**. |
| **[G5]** peak memory | reported; keep watching `nvidia-smi` past step 40. |
| loss | `{'loss': …}` decreasing. |

### 3.5 Full run — only after an all-green smoke

```bash
mkdir -p /workspace/output/qav-gemma4-26b-moe
python train_qav.py \
  --data-path /workspace/data/train-qav.jsonl \
  --eval-path /workspace/data/eval-qav.jsonl \
  --output-dir /workspace/output/qav-gemma4-26b-moe \
  --max-seq-length <decided in 3.3a> 2>&1 | tee .../train.log
```

Defaults: base `unsloth/gemma-4-26B-A4B-it`, 16-bit LoRA `r=16 / alpha=16 / dropout=0` on
attention+MLP, `--lr 2e-4` cosine, `--warmup-ratio 0.03`, eff-batch 4, **`--epochs 3`**,
`adamw_8bit`, `--seed 3407`. **Why 3 epochs:** 86 staged train rows at eff-batch 4 ≈ 22
steps/epoch — 1 epoch badly under-fits; 3 lets the judgment shape land without a large corpus (a
probe knob; the smoke's falling loss confirms it's learning). **GGUF is NOT exported by the full
run** — that is deliberate (see Phase 5).

---

## Phase 5: Post-training validation

The full run writes `lora-adapter/` and `merged-16bit/` (NOT `gguf/`).

### 5.1 Inventory

```bash
ls -la ~/fine-tuning/output/qav-gemma4-26b-moe/
test -d .../lora-adapter && test -d .../merged-16bit || echo "MISSING artefact"
```

### 5.2 Merged-16bit generation sanity — **MANDATORY GATE before any GGUF/serve**

This is the DCL process rule baked into `train_qav.py` (which refuses to export GGUF without
`--export-gguf`): the DCL first run skipped this check and **burned a probe cycle on a
serve-broken model.** Load `merged-16bit/` under plain transformers, feed one real bundle with
the GOAL.md system prompt, and confirm the model emits **exactly one bare verdict JSON object**
(`{"verdict":…,"findings":[…]}`) — **no `<think>`, no `` ```json `` fence, no template tokens.**
If it re-fences or emits think prose, STOP: re-stage/re-train, do not export.

### 5.3 Export GGUF (only after 5.2 passes)

```bash
python train_qav.py --output-dir ~/fine-tuning/output/qav-gemma4-26b-moe --export-gguf \
  --resume   # merges + exports q4_k_m from the trained adapter
# or export manually from merged-16bit/ with llama.cpp.
```

**Quant law:** `q4_k_m` is the pragmatic stand-in for **UD-Q4_K_XL**; **NEVER `q4_0`** (collapses
26B-A4B to 70.2% top-1 — the QAT research). Build true UD-Q4_K_XL with llama.cpp + imatrix if
serving quality needs it.

---

## Phase 6: A/B on the frozen exam (the verdict phase)

Serve the tuned GGUF beside the stock/coach fleet on llama-swap `:9000` (staged-deploy: a new
`qav-ft-v1` entry, on-demand, previous entries untouched, rollback = config revert + reload —
WS4 §6.2; keepalive/probe-list edits are a named phase with a Pass: check, never a side effect).
Then grade with the QAV seat's own harness — **never `run_po_eval.py`**:

```bash
# per rep, per task (run from the fleet-evals repo root):
python3 harness/run_qav_heldout.py \
  --task-dir tasks/qav-held-001-gold-negatives \
  --out <rep-dir> --rep <n> --model qav-ft-v1 \
  --endpoint http://127.0.0.1:9000/v1/chat/completions \
  --freeze-commit <frozen qav-heldout-suite-scope.md sha>
# grade that rep (the runner NEVER grades):
PO_EVAL_OUTPUT_DIR=<rep-dir> python3 -m pytest tasks/qav-held-001-gold-negatives/test -q
```

Repeat for `qav-held-002-honest-green` × K reps. Capture each pytest `$?` **separately** — never
infer pass/fail from a `tee`/`tail` (the BINDING lesson). The runner enforces the single-slot law
(a fresh `/running` probe before every bundle).

**The bar (FEAT-EVAL-QAV must-catch):**

- **qav-held-001: 4/4 reject** on the gold negatives (GN-1..GN-4), each with the owning DC class
  and a locus naming the in-bundle signal. **3 of 4 is a FAIL** (`instruction.md`).
- **qav-held-002: hold the over-reject ceiling** on the honest greens (clean AND ugly) — a judge
  that rejects every blemish is a rubber stamp in reverse (the two-sided discipline).

Record a graded RESULTS doc (per-rep grades + summary) under
`fleet-evals/calibration/qav-candidate-probes/qav-ft-v1/` with the content-addressed chain
(dataset sha → base+adapter → GGUF digest → llama-swap entry). **No deploy without a graded
PASS** — a checkpoint that fails stays a directory, not a seat.

---

## Artefacts (this domain)

| File | Purpose |
|---|---|
| `prepare_qav_sft.py` | stage `output/qa-verifier/{train,eval_qav}.jsonl` → bare-verdict-JSON ShareGPT train/eval + all Phase-0 gates → `~/fine-tuning/data/` + manifest (host-runnable, stdlib only) |
| `train_qav.py` | the fine-tune (gemma-4-26B-A4B 16-bit-LoRA defaults + baked-in `[G1]`–`[G6]`/`[GT]` guards; gemma-4 non-thinking template forced; merge, then GGUF only on `--export-gguf`) |
| `RUNBOOK-qav-fine-tune.md` | this runbook (stage → train → merge/sanity/GGUF → A/B) |
| `OUTPUT-CONTRACT.md` | the row envelope + label contract (§1 shows think+fence on disk; staging strips both to byte-match the serving contract) |
| `SCOPE-qav-finetune-training-serving.md` | the WS4 training/serving scope (base, seq-audit criticality, no-oversampling, class-imbalance tripwire) |
| `GOAL.md` | the judgment criteria + the served system prompt |

*Document version: 1.0 | 2026-07-23 | companion notes: `../coach-agent/RUNBOOK-coach-fine-tune.md`
(the LoRA shape on this base) and `../dcl-capability-language/RUNBOOK-dcl-fine-tune.md` (the three
serving-contract catches).*
