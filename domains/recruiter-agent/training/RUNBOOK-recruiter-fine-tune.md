# Runbook — the RECRUITER fine-tune (Qwen3-4B-Instruct-2507, dense QLoRA)

**Purpose.** Train the **recruiter tune** — a small, fast Qwen3-4B-class model that drafts office
clerks and pipelines and passes the owner's hiring exam. The durable cure for the 2026-07-21 gate
refusal (office-manager `docs/receipts/2026-07-21-recruiter-first-gate-refusal.md`), following the
DCL pilot's exact discipline (stock 2/9 → tuned 7/9 on a frozen exam), re-aimed at hiring turns.

**This runbook is the DCL fine-tune runbook re-aimed** (`../../dcl-capability-language/RUNBOOK-dcl-fine-tune.md`
v1.2 — its three catches are BINDING). One mental model: *this is the DCL tune with the SAME base,
the SAME forced stock template, and the SAME QLoRA shape — but the recruiter's serve contract is the
`file:`-fenced block protocol `parse_turn` reads, so the fences are KEPT (DCL stripped them).*

**Venue (Rich's 2026-07-22 call, "the Spark for both").** Training, packaging, and latency
measurement all run on **spark-fcf6** (~/fine-tuning/recruiter-tune/). The GB10 stays with the QAV
loop. `cr0-comfyui` and the Spark's llama-swap config are UNTOUCHED — this lane never stops the
serving service (it trains in the free-memory headroom and watches the pool).

**Base.** `Qwen/Qwen3-4B-Instruct-2507` (Apache-2.0, dense, non-thinking instruct) — the DCL pilot's
measured trainable base; upholds the client-path-never-frontier-dependent ruling.

---

## The three BINDING catches (RUNBOOK-dcl-fine-tune v1.2), as implemented here

| Catch | DCL | Recruiter (this lane) | Where |
|---|---|---|---|
| **1 — stock 2507 template forced by file** | `--chat-template-file qwen3-2507-stock.jinja` (Unsloth silently swaps in the hybrid-THINKING template) | IDENTICAL — same base, same `qwen3-2507-stock.jinja` (sha256 `64f85b19…`), forced by file; a thinking-template file is hard-rejected | `train_recruiter_qwen3.py` load step + `[G2]` |
| **2 — never train near-untrained added tokens (`<think>`)** | staging strips `<think>` from repair rows | Corpus is THINK-FREE by construction (teacher `enable_thinking:false`, reasoning lands in a separate `reasoning_content` field the harness never reads) — no strip needed; `[G6]` still ABORTS on any `<think>` in a rendered target | `[G6]` |
| **3 — targets byte-match the serve contract** | DCL serves BARE source → fences stripped; `[G6]` aborts on fences | Recruiter serves the `file:`-fenced protocol `parse_turn` reads → fences KEPT (load-bearing). `[G6]` byte-matches each rendered target span against the row's raw assistant `content` (proving the template altered nothing) and reports the `file:` block count | `[G6]` |

**Merged-generation gate is MANDATORY before any GGUF/serve step** (the DCL v1 run skipped it and
burned a probe cycle on a model that teacher-forced perfectly but collapsed under free generation).

---

## The corpus is already serve-faithful — no staging transform

Unlike DCL (which needs `prepare_dcl_sft.py` to strip think + fences + oversample), the recruiter
freeze (`../generate.py` `freeze_corpus`) writes `corpus/train.jsonl` + `corpus/val.jsonl` ALREADY in
final serve-faithful ShareGPT shape:

- **system** = the recruiter seed's `system_prompt` verbatim (vocab-in-prompt operating mode);
- **user** = `hire.loop.build_user_turn` → `"The owner says:\n<request>"`;
- **assistant** = the raw drafting turn (message + `file:` blocks), think-free, fences kept.

So training reads `corpus/train.jsonl` and `corpus/val.jsonl` directly. `val.jsonl` is a real,
per-class-stratified, deterministic-by-`row_id`, disjoint ~10% held-out set — **loss-only** monitoring,
NOT the pass exam (the four banked sessions are the exam; the denylist keeps them out by construction).

Recruiter rows are **target-heavy** (system ~1.4KB / user ~0.1KB / assistant ~3KB) — the OPPOSITE of
DCL's prompt-heavy rows — so `--max-seq-length` defaults to **4096** (confirm with the real-tokenizer
audit) and `[G4]` masked% runs LOWER than DCL's.

---

## Procedure

### 0. Pre-train verify (host / office venv — ZERO model calls)

```bash
cd ~/Projects/appmilla_github/office-manager
DOMAIN=~/Projects/appmilla_github/agentic-dataset-factory/domains/recruiter-agent
OFFICE_AGENTS_ROOT=/tmp PYTHONPATH="$DOMAIN" ./.venv/bin/python \
  "$DOMAIN/training/verify_corpus.py" --corpus "$DOMAIN/corpus" \
  --seed-config ~/Projects/appmilla_github/office-manager/seed/agents/recruiter/config.yaml
# expect: VERIFY: ALL GREEN (disjoint · shape · think-free · parse_turn round-trip · contamination · stratification)
```

### 1. Transfer the corpus to the Spark

```bash
export SSH_AUTH_SOCK=/run/user/1000/keyring/ssh
scp "$DOMAIN"/corpus/train.jsonl spark-fcf6:~/fine-tuning/recruiter-tune/data/train-recruiter.jsonl
scp "$DOMAIN"/corpus/val.jsonl   spark-fcf6:~/fine-tuning/recruiter-tune/data/val-recruiter.jsonl
# scripts + qwen3-2507-stock.jinja already staged under ~/fine-tuning/recruiter-tune/scripts/
```

### 2. Container + deps (in-container — pins from DCL v1.2 §3.3, do NOT bump)

```bash
tmux new -s rc-ft "docker run --gpus all --ulimit memlock=-1 --ulimit stack=67108864 -it --rm \
  -v \$HOME/fine-tuning/recruiter-tune/data:/workspace/data \
  -v \$HOME/fine-tuning/recruiter-tune/output:/workspace/output \
  -v \$HOME/fine-tuning/recruiter-tune/scripts:/workspace/scripts \
  -v \$HOME/.cache/huggingface:/root/.cache/huggingface \
  --entrypoint /usr/bin/bash --name rc-ft-\$(date +%Y%m%d-%H%M%S) nvcr.io/nvidia/pytorch:25.11-py3"
# inside:
pip install transformers==5.5.4 peft hf_transfer "datasets==4.3.0" "trl==0.26.1" "accelerate==1.10.0"
pip install --no-deps unsloth unsloth_zoo bitsandbytes
```

**GPU posture (this lane's fence).** llama-swap STAYS UP (never stopped — it is the serving service).
The 4B QLoRA trains in the free-memory headroom; watch the pool in a second shell and **abort if total
climbs toward ~110 GB** (of 121):

```bash
watch -n 5 'nvidia-smi --query-compute-apps=pid,process_name,used_memory --format=csv; free -g | head -2'
```

### 3. Real-tokenizer seq audit (confirm 4096 before commit)

```python
# in-container, after deps:
import json
from unsloth import FastLanguageModel
_, tok = FastLanguageModel.from_pretrained("Qwen/Qwen3-4B-Instruct-2507",
    max_seq_length=4096, load_in_4bit=True, full_finetuning=False)
tok.chat_template = open("/workspace/scripts/qwen3-2507-stock.jinja").read()
L=[len(tok.apply_chat_template(json.loads(l)["messages"], tokenize=True, add_generation_prompt=False))
   for l in open("/workspace/data/train-recruiter.jsonl") if l.strip()]
L.sort(); n=len(L)
for thr in (2048,3072,4096): print(thr, f"{sum(x>thr for x in L)}/{n} exceed")
print("p95", L[int(.95*n)], "p99", L[int(.99*n)], "max", L[-1])
# keep 4096 if p99 <= 4096; raise only if p99 exceeds it.
```

### 4. Smoke (~5 min) — the baked-in guards do the validating

```bash
cd /workspace/scripts
python train_recruiter_qwen3.py \
  --data-path /workspace/data/train-recruiter.jsonl \
  --eval-path /workspace/data/val-recruiter.jsonl \
  --output-dir /workspace/output/recruiter-qwen3-4b-smoke \
  --max-steps 40 --skip-export 2>&1 | tee /workspace/output/recruiter-qwen3-4b-smoke/train.log
```

Guards: `[G1]` trainable ~1-3% · `[G2]` Qwen markers, no gemma leak · `[G3]` attn impl · `[G4]`
masked% LOWER than DCL (target-heavy rows) · `[G5]` peak mem · `[G6]` think=0 + byte-match=0 +
file-block count reported · loss falling. **Judge by the log's `Training complete.` + no `ABORT [Gn]`
/ `Traceback`, never by a `tee` tail alone** (the §0 exit-code lesson).

### 5. Full run (~30-60 min incl. export) — only after an all-green smoke

```bash
python train_recruiter_qwen3.py \
  --data-path /workspace/data/train-recruiter.jsonl \
  --eval-path /workspace/data/val-recruiter.jsonl \
  --output-dir /workspace/output/recruiter-qwen3-4b \
  2>&1 | tee /workspace/output/recruiter-qwen3-4b/train.log
```

Defaults: seq 4096, LoRA r16/α32/dropout0, lr 2e-4 cosine, eff-batch 4, 2 epochs, adamw_8bit, seed
3407, GGUF q4_k_m. Writes `lora-adapter/` + `merged-16bit/` + `gguf/`.

### 6. MERGED-GENERATION GATE (mandatory pre-GGUF verdict)

Generate the first drafting turn on the val held-out prompts (never train) for BOTH the tuned merged
model and the stock base, then grade with the office's OWN checkers (`acceptance.accept`).

```bash
# in-container (Spark GPU), per model:
python /workspace/scripts/merged_gen_gate.py --mode generate \
  --model /workspace/output/recruiter-qwen3-4b/merged-16bit \
  --prompts /workspace/data/val-recruiter.jsonl \
  --chat-template-file /workspace/scripts/qwen3-2507-stock.jinja \
  --out /workspace/output/recruiter-qwen3-4b/gate/tuned-outputs.jsonl --label tuned
python /workspace/scripts/merged_gen_gate.py --mode generate \
  --model Qwen/Qwen3-4B-Instruct-2507 \
  --prompts /workspace/data/val-recruiter.jsonl \
  --chat-template-file /workspace/scripts/qwen3-2507-stock.jinja \
  --out /workspace/output/recruiter-qwen3-4b/gate/stock-outputs.jsonl --label stock

# grade (office venv on the CPU box — pull the two outputs.jsonl back first):
cd ~/Projects/appmilla_github/office-manager
OFFICE_AGENTS_ROOT=/tmp PYTHONPATH="$DOMAIN" ./.venv/bin/python \
  "$DOMAIN/training/merged_gen_gate.py" --mode grade \
  --tuned <local>/tuned-outputs.jsonl --stock <local>/stock-outputs.jsonl \
  --held-root ~/office-authoring --json-out "$DOMAIN/training/gate-results.json"
```

**The gate bar:** every tuned output parses under `parse_turn`; the tuned pass-rate is MATERIALLY
ABOVE the stock base on the same prompts (the A/B delta) — the durable cure for the 2026-07-21
refusal. This is the pre-GGUF sanity verdict, NOT the owner's exam: **Rich's attended, unlabelled
re-sit on the four banked sessions is the only pass that counts**, and it is his.

---

## Artefacts (this dir)

| File | Purpose |
|---|---|
| `train_recruiter_qwen3.py` | the fine-tune (Qwen3-4B dense QLoRA; `[G1]`–`[G6]` guards; stock template forced; catch-3 re-aimed to KEEP fences + byte-match the serve contract; merge + GGUF export) |
| `qwen3-2507-stock.jinja` | the stock Qwen3-2507 chat template (train == serve; forced via `--chat-template-file`; sha256 `64f85b19…`, identical to the DCL base template) |
| `verify_corpus.py` | pre-train gate on the frozen corpus (disjoint · shape · think-free · parse_turn round-trip · contamination re-scan · stratification) — host/office-venv, zero model calls |
| `merged_gen_gate.py` | the mandatory pre-GGUF gate: `generate` (in-container, tuned + stock on val prompts) / `grade` (office venv, `acceptance.accept` per row, A/B delta) |
| `RUNBOOK-recruiter-fine-tune.md` | this runbook |
| `RESULTS-*.md` / `gate-results.json` | the run's evidence (loss curve, guard lines, gate table) — written after the run |

Large binaries (adapter / merged / GGUF) stay on the Spark under
`~/fine-tuning/recruiter-tune/output/` and are NEVER committed (DF-008 private); manifests + sha256s
land here.
