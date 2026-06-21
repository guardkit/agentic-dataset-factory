# Runbook: Coach Agent — Fine-Tune (Gemma-4-26B-A4B MoE)

**Purpose:** Fine-tune a judgment-quality Coach LoRA (structured-JSON verdicts for the
adversarial Player-Coach autobuild loop) on Gemma-4-26B-A4B (MoE) via Unsloth + TRL inside
the NVIDIA PyTorch container, from the curated `~/coach-dataset/` corpus.
**Machine:** Dell DGX Spark GB10 (`promaxgb10-41b1`), 121 GB unified memory.
**Duration:** smoke ~14 min (60 steps); full run ~71 min (incl. merge + GGUF export).
**Companion of:** the architect runbook (`../architect-agent/RUNBOOK-architect-fine-tune.md`)
— domain-agnostic phases (0.5 freeze-prevention, 3 launch, 4 monitor) are inherited; this
runbook documents only the Coach-specific deltas.

> ⚠️ **Phase 3 launch is a manual SSH-paste workflow from your MacBook, NOT driven from a
> Claude Code session running on the GB10.** The Claude→tmux→docker chain caused two GB10
> freezes (see architect runbook Phase 4). Claude prepares and interprets; you launch.

---

## The QAT decision (resolved 2026-06-19 — do NOT swap the base)

Google's Gemma 4 QAT release prompted "should we fine-tune the QAT checkpoint?". An
adversarially-verified research pass (`RESEARCH-gemma4-qat-decision.md`) answered **no**:

- **REFUTED:** `unsloth/gemma-4-26B-A4B-it-qat-q4_0-unquantized` as a fine-tune base. Its own
  HF card scopes it to "custom downstream compilation and research"; Unsloth's official FT
  guide points LoRA at the plain `unsloth/gemma-4-26B-A4B-it`.
- **REFUTED:** "QAT base + Q4_0 export wins." Q4_0-from-QAT collapses 26B-A4B to **70.2%
  top-1** (misaligned with the BF16 QAT lattice); only Unsloth's dynamic **UD-Q4_K_XL**
  recovers it to **85.6%**. Serve at UD-Q4_K_XL (or `q4_k_m`), **never q4_0**.
- The only real QAT lever is `qat_scheme="int4"` on `get_peft_model` (fake-quant *during*
  LoRA, torchao export) — **untested on this 128-expert MoE**, exports to w4a16 (vLLM), not
  GGUF. Treat as a research arm, not the production recipe.

**Net recipe delta vs the architect/GCSE recipe:** template `gemma-4-thinking → gemma-4`
(non-thinking), longer `--max-seq-length`, GGUF `q4_k_m` (never q4_0). Base unchanged.

---

## Inputs

```bash
DOMAIN="coach"
COACH_DS="$HOME/coach-dataset"                       # curated corpus (outside the repo)
SCRIPTS="$HOME/Projects/appmilla_github/agentic-dataset-factory/domains/coach-agent"
FT_HOME="$HOME/fine-tuning"
STAGED_TRAIN="$FT_HOME/data/train-coach.jsonl"       # ShareGPT, produced in Phase 2
OUTPUT_TAG="coach-gemma4-26b-moe"
OUTPUT_DIR_HOST="$FT_HOME/output/${OUTPUT_TAG}"
DATA_PATH_CTR="/workspace/data/train-coach.jsonl"
OUTPUT_DIR_CTR="/workspace/output/${OUTPUT_TAG}"
```

---

## Phase 0: Validate the corpus (GO/NO-GO gate)

Read-only. The Coach corpus is already curated (`~/coach-dataset/curated/train_final.jsonl`,
447 rows); the gates below confirm it converts cleanly and choose `--max-seq-length`.

### 0.1 Convert + audit (this IS the gate — it runs the leak/balance/seqlen checks)

```bash
python3 "$SCRIPTS/prepare_coach_sft.py" --out "$STAGED_TRAIN"
```

This emits, and you must eyeball:

| Output line | Expected | If violated |
|---|---|---|
| `Leakage guard: 0 / 447 ... overlap holdout` | 0 overlap | **STOP** — re-run curation; never train on eval |
| (no `ABORT: template-token leaks`) | clean | **STOP** — Player bled `<\|turn>`/`<\|channel>` into content; fix corpus |
| `output rows : 713` | 713 (after weight-oversampling) | mismatch ⇒ check `--weight-mode` |
| `decision (out) : approve=543 (76%), feedback=170 (24%)` | feedback ~24% | the anti-rubber-stamp lever; ~19% means weighting didn't apply |
| `sequence-length audit` | see 0.2 | drives the seq-length choice |

### 0.2 Choose `--max-seq-length` (Coach-specific — the verdict is at the END)

Unlike the architect/GCSE data (short completions), Coach verdicts are long
(`criteria_verification` JSON). **Measured with the real gemma4 serving tokenizer (2026-06-19,
`llama-tokenize` on the UD-Q4_K_XL GGUF): 3.50 chars/token; seq p50=3281, p95=5718, p99=6447,
max=7215 tokens.** Truncation rates (verdict tail is lost, it sits at the END):

```
max_seq_length= 4096:  26.9% truncate   <-- too lossy for a JSON Coach
max_seq_length= 6144:   2.0% truncate   <-- RECOMMENDED (covers 98% intact)
max_seq_length= 8192:    0% truncate    <-- memory-risky on GB10 (2x the 4096 activations)
```

**Recommendation: `--max-seq-length 4096`** (the script default). Although the data wants 6144
to avoid truncation, **seq ≥6144 does NOT complete on this 121 GB GB10** (see the empirical box
below). At 4096, pair with `prepare_coach_sft.py --max-completion-tokens 2800` to cut the
prompt+verdict length; ~18.7% of verdicts still truncate their rationale *tail* (decision +
criteria + issues are at the front and preserved; the serve-time GBNF grammar forces complete
JSON anyway). To cut that further you must trim prompts (long ACs / player reports), not just
completions — the residual truncation at 4096 is prompt-driven.

> **Empirical memory (2026-06-19 GB10 run — important):** the smoke at seq 4096 peaked [G5]
> 61.2 GB. The full run at **seq 8192 climbed to ~114 GB** system used and was watchdog-killed
> at step 45 — **8192 is NOT viable on the 121 GB box.** The trap: the *early-step* memory
> reading badly understates the peak — the allocator high-water mark grows over the first ~45
> steps as the longest 6–7k-token examples are encountered (peak is set by the longest example
> at the chosen `max_seq_length`, which appears partway through the shuffled epoch). So judge
> seq viability by the **step ~40 plateau AND the step-80 trajectory**, not step 1 — the
> high-water keeps *climbing* over the epoch (~6 GB / 40 steps at 6144). **seq 6144 ALSO fails:**
> 106 GB@40 → 112 GB@80, watchdog-killed. **`PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True`
> only shifts the curve down ~5 GB (101→107 GB) — not enough.** **seq 4096 is the practical
> ceiling** (~75–85 GB, completes in ~1.5 h). The training script defaults to 4096 and sets
> expandable_segments. ALWAYS run behind the memory watchdog (auto-`docker kill` if available
> RAM < ~8 GB / ~113 GB used — below the 114 GB the 8192 run reached without freezing) so a
> misjudged seq aborts cleanly instead of freezing the box (a freeze needs a power-cycle).

**Get ground truth with the real tokenizer (run once, in the container — Phase 3.3 deps must
be installed first):**

```python
# in-container: python /workspace/scripts/_audit.py  (or paste into a python REPL)
import json
from unsloth import FastModel
from unsloth.chat_templates import get_chat_template
_, tok = FastModel.from_pretrained("unsloth/gemma-4-26B-A4B-it", max_seq_length=8192,
                                   load_in_16bit=True, full_finetuning=False)
tok = get_chat_template(tok, chat_template="gemma-4")
L=[]
for line in open("/workspace/data/train-coach.jsonl"):
    if not line.strip(): continue
    convo=json.loads(line)["messages"]
    t=tok.apply_chat_template(convo, tokenize=True, add_generation_prompt=False)
    L.append(len(t))
L.sort(); n=len(L)
for thr in (4096,6144,8192):
    print(thr, f"{sum(x>thr for x in L)}/{n} ({100*sum(x>thr for x in L)/n:.1f}%) exceed")
print("p95", L[int(.95*n)], "p99", L[int(.99*n)], "max", L[-1])
```

**Decision rule:**
- If real p99 ≤ 4096 (the 3.5-char estimate is conservative — real may be lower) → use
  `--max-seq-length 4096` (proven memory-safe; GCSE run-4 ran 4096 fine).
- Else → use `--max-seq-length 6144` and **smoke-test memory** (Phase 3.4 watches peak).
- If 6144 peaks too hot on GB10 (>~100 GB), regenerate the data with completion compression:
  `prepare_coach_sft.py --max-completion-tokens 3200 --note-cap 200` (trims verbose notes;
  preserves decision + per-criterion result + issues — aligns with the "tighter reasoning"
  win condition) and use `--max-seq-length 4096`.

### 0.3 Verdict-validity + template alignment

The Coach is non-thinking structured JSON — there is **no `<think>` gate** (that's the
architect recipe). Instead:

```bash
python3 - <<'PY'
import json, os
p=os.path.expanduser("~/fine-tuning/data/train-coach.jsonl")
rows=[json.loads(l) for l in open(p) if l.strip()]
bad=0
for r in rows:
    c=r["messages"][-1]["content"]
    raw=c.strip().removeprefix("```json").removeprefix("```").rstrip("`").strip()
    try:
        o=json.loads(raw); assert o.get("decision") in ("approve","feedback")
    except Exception:
        bad+=1
print(f"{len(rows)-bad}/{len(rows)} assistant turns are valid verdict JSON with a decision")
assert bad==0, "fix malformed verdicts before training"
PY
```

**Serving-contract alignment — VERIFIED against the live `coach-verdict.gbnf` (2026-06-19,
see `SERVING-coach-ft.md`):**
- **Fence is kept** (`code-fence ::= "```json" … "```"`) → keep the prep default `--fence`.
- **The grammar requires `{task_id:str, turn:int, decision, …}` leading keys**, but the
  harvested corpus predates this contract (leads with `decision`, no task_id/turn). This is
  fixed by `prepare_coach_sft.py --coachsplit-schema` (**ON by default** — injects task_id/turn
  into prompt + verdict). Without it, the fine-tuned Coach emits the wrong schema and the
  COACHSPLIT parser/grammar **reject every verdict**. Confirm the prep log shows
  `coachsplit schema: ON -> NNN verdict(s) reshaped` and the verdict-validity check above
  passes 100%.
- **Two authored hard_case bugs** the verification surfaced (both in the 8 `synthetic_hardcase`
  rows): one mislabelled metadata `decision` (`path-string-mismatch` → really `approve`), and
  one malformed JSON (`TASK-BDDW-009`, trailing `}`). The prep WARNs on the malformed one;
  `--drop-malformed` removes it. Fix both in `hard_cases.jsonl` when convenient.

---

## Phase 0.5 / 1 / 2: Freeze-prevention, backup, stage

- **0.5 Freeze prevention** — identical to the architect runbook: `pkill -f
  "llama-swap|llama-server"`, confirm `nvidia-smi --query-compute-apps` is empty before
  launching Docker. The 26B fine-tune needs ~80–100 GB; llama-swap workers oversubscribe the
  121 GB unified pool and freeze the kernel.
- **1 Backup** — `sudo mv` any prior `~/fine-tuning/output/coach-gemma4-26b-moe` aside
  (root-owned from Docker; do not `chown`).
- **2 Stage** — `prepare_coach_sft.py` in Phase 0.1 already wrote `$STAGED_TRAIN`. Also copy
  the three scripts into the mounted scripts dir:
  ```bash
  cp "$SCRIPTS"/{train_coach_moe.py,eval_coach.py} ~/fine-tuning/scripts/
  ```

---

## Phase 3: Launch (manual SSH-paste from MacBook)

### 3.1–3.2 Container — same as architect runbook
`tmux new -s coach-ft "docker run --gpus all ... nvcr.io/nvidia/pytorch:25.11-py3"` with the
same bind-mounts (`data`, `output`, `scripts`, `~/.cache/huggingface`). 25.11 is proven for
this MoE (GCSE run-4). If you hit sm_121 MoE-routing kernel errors, fall back to 25.09 +
source triton/xformers per Unsloth's DGX Spark blog.

### 3.3 Deps (inside container) — pins matter, + Unsloth post-PR-4913

```bash
pip install transformers==5.5.4 peft hf_transfer "datasets==4.3.0" "trl==0.26.1" "accelerate==1.10.0"
pip install --no-deps unsloth unsloth_zoo bitsandbytes
```

⚠️ **Confirm Unsloth is a post-PR-4913 build (merged 2026-04-14).** Pre-fix builds silently
fail to attach LoRA to the MoE experts → trainable% collapses to ~0.23% and you train almost
nothing. The smoke run's `[G1]` guard catches this and aborts; if it fires, upgrade Unsloth.

### 3.4 Smoke (~14 min) — the baked-in guards do the validating

```bash
cd /workspace/scripts
mkdir -p /workspace/output/coach-gemma4-26b-moe-smoke
python train_coach_moe.py \
  --data-path /workspace/data/train-coach.jsonl \
  --output-dir /workspace/output/coach-gemma4-26b-moe-smoke \
  --max-seq-length 6144 \
  --max-steps 60 --skip-export 2>&1 | tee /workspace/output/coach-gemma4-26b-moe-smoke/train.log
```

In a 2nd SSH: `watch -n 5 nvidia-smi`. **Abort (`Ctrl-C`) if memory exceeds ~100 GB.**

`train_coach_moe.py` prints five guards — the smoke run PASSES only if all are green:

| Guard | Pass condition |
|---|---|
| **[G1]** trainable% | `Detected MoE ... num_experts = 128`, `Enabling LoRA on ... [experts.gate_up_proj, experts.down_proj]`, trainable **≥ ~1.0%** (expect ~1.88%). Aborts otherwise (PR-4913). |
| **[G2]** template render | rendered example contains `<\|turn>user`, `<\|turn>model`; note whether `<\|channel>thought` precedes the JSON |
| **[G3]** attention | `sdpa` (not flash_attention_2) |
| **[G4]** masking | a HIGH masked% (the verdict is the smaller, trained part); ~0% or ~100% = markers wrong, STOP |
| **[G5]** peak memory | reported `peak GPU memory` well under ~100 GB at your chosen seq |
| loss | `{'loss': …}` lines **decreasing** over 60 steps |

### 3.5 Full run (~71 min) — only after smoke is all-green

```bash
mkdir -p /workspace/output/coach-gemma4-26b-moe
python train_coach_moe.py \
  --data-path /workspace/data/train-coach.jsonl \
  --output-dir /workspace/output/coach-gemma4-26b-moe \
  --max-seq-length 6144 \
  2>&1 | tee /workspace/output/coach-gemma4-26b-moe/train.log
```

(Defaults: base `unsloth/gemma-4-26B-A4B-it`, template `gemma-4`, GGUF `q4_k_m`, r=16,
eff.batch 4, 1 epoch. Detach tmux with `Ctrl-B D` and let it cook.)

---

## Phase 4: Monitor
Same signals as the architect runbook (loss trajectory, GPU 50–100 GB, step rate, disk). The
`[G1]–[G5]` guards already ran at step 0; for the rest of the run watch loss + memory.

---

## Phase 5: Post-training validation

### 5.1 Inventory — `lora-adapter/`, `merged-16bit/`, `gguf/` present and non-empty.

### 5.2 "Beats base" eval (the win condition)

Serve the fine-tune and the base through llama-swap/llama.cpp, then:

```bash
python "$SCRIPTS/eval_coach.py" \
  --endpoint http://localhost:8080/v1 \
  --model coach-gemma4-moe --base-model gemma4-26b-a4b-it \
  --grammar /opt/llama-swap/grammars/coach.gbnf \
  --report ~/coach-dataset/curated/eval_report.json
```

**Win = on `holdout_eval.jsonl` (76, truly held out): correct-verdict ↑ AND false-approval ↓
vs base.** The harness prints a `BEATS-BASE VERDICT` line and breaks down the in-train symptom
probes (`hard_cases` + `relabelled`) separately. Note one hard_case is a *false-positive
trap* (path-string-mismatch → correct verdict is `approve`); the harness derives gold from the
completion, not the mislabelled metadata `decision` field.

### 5.3 Serving (llama.cpp / llama-swap)

- **Disable thinking with `--reasoning off`** (NOT `--reasoning-budget 0` / `--chat-template-kwargs`
  — reported ineffective on 26B-A4B).
- **Constrain JSON with `--grammar-file <coach.gbnf>`**, NOT `--json-schema` (the schema→GBNF
  path crashes sampler init on Gemma 4).
- **GGUF quant: UD-Q4_K_XL** for best int4 quality. `train_coach_moe.py` exports `q4_k_m` (the
  best `save_pretrained_gguf` flag offers); build true UD-Q4_K_XL with llama.cpp `quantize` +
  imatrix only if smoke JSON quality is marginal. **Never q4_0.**

### 5.4 Smoke-test #7 (highest value — train==serve round-trip)

Export the 60-step smoke adapter to `q4_k_m`, serve with `--grammar-file --reasoning off`,
send 3–5 Coach prompts and confirm: (a) valid grammar-constrained JSON, (b) **no leaked
`<\|channel>thought` tokens** in the parsed verdict, (c) verdict structure matches schema.
This is the only test that validates the template alignment + GGUF token carry-through —
**do not skip it.**

---

## Artefacts (this domain)

| File | Purpose |
|---|---|
| `prepare_coach_sft.py` | curated flat verdicts → ShareGPT + weight-oversample + leak/seqlen gates (+ optional verdict compression) |
| `train_coach_moe.py` | the fine-tune (Coach defaults + baked-in [G1]–[G5] guards) |
| `eval_coach.py` | "beats base" eval (correct-verdict + false-approval + symptom probes) |
| `RESEARCH-gemma4-qat-decision.md` | the adversarially-verified QAT decision + sources |

*Document version: 1.0 | 2026-06-19 | Companion to RUNBOOK-architect-fine-tune.md v1.2*
