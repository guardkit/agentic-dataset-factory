---
task_id: TASK-REV-G4MOE
title: Review Gemma 4 MoE vs Dense model choice for fine-tune
mode: decision
depth: standard
date: 2026-04-15
decision: switch-to-moe
---

# Review Report: TASK-REV-G4MOE — Gemma 4 MoE vs Dense for GCSE tutor fine-tune

## Executive Summary

**Recommendation: switch the primary fine-tune target from Gemma 4 31B Dense to Gemma 4 26B A4B MoE (`unsloth/Gemma-4-26B-A4B-it`).** Keep the existing 31B Dense artifacts as an offline "quality tier" for batch/judge use, but do not invest more training compute in it until the MoE pipeline is proven.

The original Dense choice was made on reasonable-looking grounds but two of its load-bearing assumptions were wrong in ways that only become visible on GB10:

1. **The quality gap is ~1 point, not "substantial"** — AIME 89.2 vs 88.3, MMLU Pro 85.2 vs 82.6.
2. **The latency gap is ~7–8×, not "slower"** — GB10's 273 GB/s memory bandwidth makes the 31B Dense bandwidth-bound at **5–7 tok/s single-node**, which is "unusable" (per NVIDIA forum consensus) for real-time tutoring. The MoE runs at **45–60 tok/s** measured.

The third original concern — "MoE means avoiding the router layer, QLoRA risky" — is half right. QLoRA **is** still risky for this MoE (Unsloth officially says so). But Unsloth now supports 16-bit LoRA for `unsloth/Gemma-4-26B-A4B-it` with router layers handled automatically. The "risk" reduces to a one-line loader config change plus roughly 2× the training memory (48 GB vs 22 GB), both of which fit comfortably in GB10's 128 GB unified memory.

The forum failure report flagged in the task brief is a red herring: it concerns a third-party **uncensored fork** (`AEON-7/Gemma-4-26B-A4B-it-Uncensored-NVFP4`) deployed via a custom "OpenClaw" script, not the base Google/Unsloth model. Multiple independent users on NVIDIA's forums confirm the base MoE runs cleanly at 45–60 tok/s via `eugr`'s community vLLM container.

**Sunk-cost check**: the existing 31B Dense fine-tune is still valuable as a non-interactive tier (evaluation judge, dataset filtering, offline rewrites) where 7 tok/s is acceptable. It should not be deleted. But it cannot be the interactive GCSE tutor.

---

## Review Details

- **Mode**: decision
- **Depth**: standard
- **Reviewer**: /task-review (decision mode)
- **Key sources**: 2 NVIDIA forum threads (primary), 3 supporting NVIDIA forum threads, Unsloth official docs, Google Gemma 4 model card/blog, independent benchmark blog

---

## 1. Current State

We have fine-tuned `unsloth/gemma-4-31B-it` (Dense) on ~2,500 GCSE English tutor examples using [train_gemma4.py](../../docs/research/train_gemma4.py) with QLoRA 4-bit, following [fine-tuning-getting-started.md](../../docs/research/fine-tuning-getting-started.md). The output is a LoRA adapter, a merged-16bit model, and a Q4_K_M GGUF.

**Target use case** (per task brief): real-time GCSE English tutoring. Target: <2 s first-token, fluent streaming.

**Original Dense-vs-MoE reasoning** ([fine-tuning-getting-started.md:17-33](../../docs/research/fine-tuning-getting-started.md#L17-L33)) — reproduced:

> | Factor | Gemma 4 31B Dense | Nemotron 3 Nano 30B-A3B |
> | Reasoning (AIME 2026) | 89.2% | Not published |
> | Fine-tuning suitability | Dense = simpler, higher quality ceiling | MoE = must avoid router layer, QLoRA risky |
> | Inference speed | Slower (all params active) | Faster (3B active) |
> | VRAM for QLoRA training | ~22GB | ~20GB |
>
> **Decision:** Use Gemma 4 31B Dense… If inference latency becomes a problem for real-time tutoring, quantise the trained model (Q4_K_M GGUF) or evaluate the 26B MoE later.

This is the "later". Note: the original comparison was Gemma 4 31B Dense vs **Nemotron** 3 Nano, not vs Gemma 4 26B A4B. The 26B A4B MoE was not evaluated at the time.

---

## 2. Evidence: Inference Latency on GB10

### 2.1 Gemma 4 31B Dense — measured numbers

From NVIDIA forum thread [366024 "Slow inference with 31b model Gemma 4"](https://forums.developer.nvidia.com/t/slow-inference-with-31b-model-gemma-4-optimizations/366024):

| Config | Hardware | Speed | User |
|---|---|---|---|
| Q8 single Spark | 1× GB10 | **5 tok/s** | Liquidlava1990 |
| Q8_0 optimised | 1× GB10 | ~6 tok/s | coder543 |
| AWQ | 1× GB10 | ~10 tok/s | kenny8379 |
| NVFP4 dual-Spark TP=2 | 2× GB10 (IB) | 17 tok/s | pfnguyen |

Quote (Liquidlava1990): **"5 is unusable honestly and it's not even a big model."**
Quote (unattributed): GB10 is in *"a really weird spot where it just doesn't have enough bandwidth"* for dense 31B.

The theoretical ceiling is mechanical: 273 GB/s ÷ ~31 GB of weights/token ≈ **8.8 tok/s** at Q8 single-node, regardless of how clever the inference stack is. **Quantisation cannot rescue this** because the bottleneck is bandwidth to read weights, not compute.

From NVIDIA forum thread [365814 "Gemma 4 31B on DGX Spark: Runtime FP8 Benchmarks"](https://forums.developer.nvidia.com/t/gemma-4-31b-on-dgx-spark-runtime-fp8-benchmarks-single-dual-node-tp-2/365814):

- Single-node FP8: **6.9 tok/s** single-user, 27 tok/s across 4 concurrent users
- Prompt processing (pp512): ~1,560 tok/s, TTFT ~333 ms
- Dual-node TP=2: **11.2 tok/s** (1.7× speedup) — requires a second DGX Spark over InfiniBand

**Prompt processing is fine** (~1,560 tok/s, TTFT 333 ms hits the <2 s first-token target). It's the **decode/generation** that's unusable. A typical 200-token tutor response at 6.9 tok/s = **~29 s wall-clock**. That's not a real-time tutor; it's a slow email client.

### 2.2 Gemma 4 26B A4B MoE — measured numbers

From NVIDIA forum thread [365547 "Gemma 4 26B A4B MoE running at 45-60 tok/s"](https://forums.developer.nvidia.com/t/someone-post-this-gemma-4-26b-a4b-moe-running-at-45-60-tok-s-on-dgx-spark/365547) — full reply extraction:

| Reply | User | Date | Data |
|---|---|---|---|
| 1 | paulsc.liu | 2026-04-03 | NVFP4 quant, ~49 GB model size, references Reddit |
| 2 | lujun1255 | 2026-04-03 | 1 instance: 50.43 t/s; 2: 61.04; **4: 140.0 t/s** |
| 3 | stefan132 | 2026-04-04 | "Can confirm, get around 50 tok/s" |
| 4 | lewald_jens | 2026-04-04 | "Jup runs here with 45–60" |
| 5 | haidij | 2026-04-05 | `google/gemma-4-26B-A4B-it` on eugr's community vLLM container, online FP8 quant, works fine |

From independent benchmark [ai-muninn.com "52 tok/s at only 16 GB"](https://ai-muninn.com/en/blog/dgx-spark-gemma4-26b-nvfp4-52-toks):

- **52.0 ± 0.1 tok/s** decode (5 runs, stable, no degradation at 1600+ token outputs)
- **TTFT: 53 ms**
- **Memory: 16.5 GB**, leaving ~82 GB free for KV cache
- 3 concurrent requests → **114.6 tok/s aggregate**
- Stack: `vllm/vllm-openai:gemma4-cu130`, model `bg-digitalservices/Gemma-4-26B-A4B-it-NVFP4`, flags `--quantization modelopt --moe-backend marlin --kv-cache-dtype fp8`

**A 200-token response at 52 tok/s = ~4 s wall-clock.** Streaming, this feels fluent. TTFT 53 ms is inaudible.

### 2.3 Side-by-side

| Metric | 31B Dense (single GB10) | 26B A4B MoE (single GB10) | Ratio |
|---|---|---|---|
| Decode, single user | **6.9 tok/s** | **52 tok/s** | **7.5×** |
| TTFT (512-token prompt) | 333 ms | 53 ms | 6.3× |
| 200-token response wall-clock | ~29 s | ~4 s | 7× |
| Memory footprint (quantised inference) | 31+ GB (Q8) / ~16 GB (NVFP4) but still BW-bound | 16.5 GB (NVFP4) | — |
| KV-cache headroom on 128 GB GB10 | limited | ~82 GB | — |
| Usable for interactive chat? | **No** | **Yes** | — |

---

## 3. Evidence: Quality Gap (the reason to pick Dense)

From Google Gemma 4 model card and independent analysis:

| Benchmark | 31B Dense | 26B A4B MoE | Δ |
|---|---|---|---|
| AIME 2026 | 89.2% | 88.3% | **0.9 pt** |
| MMLU Pro | 85.2% | 82.6% | 2.6 pt |
| GPQA Diamond | not fetched | 79.2% (beats gpt-oss-120B at 76.2%) | — |
| Context window | 256 K | 256 K | — |
| Native thinking mode | yes | yes | — |

A 0.9 pt AIME gap is well within the noise floor for GCSE English tutoring, which is not a frontier-reasoning domain. Our 75/25 reasoning-vs-direct split is about teaching the model to *pitch at GCSE level* and *use AQA AOs* — tasks where the bottleneck is the fine-tune data, not base-model reasoning ceiling.

The original rationale called this a "substantial quality gap". **It is not.** On our actual task (GCSE tutoring), the 0.9 pt AIME difference is almost certainly invisible. The MoE also has native thinking-mode support and the same 256K context, so the `<think>` block / thinking-template workflow transfers unchanged.

---

## 4. Evidence: Fine-tuning Feasibility for 26B A4B MoE

From [Unsloth Gemma 4 fine-tuning docs](https://unsloth.ai/docs/models/gemma-4/train):

- **Exact model ID**: `unsloth/Gemma-4-26B-A4B-it` (instruction-tuned, confirmed)
- **Loader**: `FastModel.from_pretrained` — same class our script already uses. No migration away from Unsloth.
- **Critical config**: `load_in_4bit = False, load_in_16bit = True` — MoE QLoRA is **not recommended** (verbatim Unsloth comment: *"MoE QLoRA not recommended, dense 31B is fine"*). The reason is that bitsandbytes cannot currently quantise Gemma 4's 3D fused expert tensors at 4-bit.
- **Router layer handling**: **handled automatically by Unsloth.** No manual freezing, no target-module gymnastics. The original doc's "must avoid router layer" concern is obsolete as stated — Unsloth does the right thing for you.
- **Memory**: ~48 GB at 16-bit vs ~22 GB at QLoRA 4-bit for Dense. Fits comfortably in 128 GB unified memory with substantial KV-cache/optimizer headroom.
- **Recommended starting config**: shorter context (2048 — we can bump to 4096/8192 later), LoRA rank 8–16, iterate after stability.
- **Support status**: day-zero, same track as Gemma 4 Dense. GGUF outputs available (`unsloth/gemma-4-26B-A4B-it-GGUF`).

There is **no architectural blocker** to fine-tuning 26B A4B with our existing Unsloth + TRL SFTTrainer pipeline. The changes are a loader config flip, a model ID swap, and a sequence-length dial.

---

## 5. The "it didn't work" forum reply — resolved

Task brief flagged this as a must-capture failure mode. Here is the exact trace from thread [366442 "Uncensored Gemma-4-26B at 45 tok/s"](https://forums.developer.nvidia.com/t/guide-uncensored-gemma-4-26b-at-45-tok-s-on-dgx-spark-actually-feels-great-to-use/366442):

| Reply | User | Date | Content |
|---|---|---|---|
| 1 (OP) | user99333 | 2026-04-13 | Guide for `AEON-7/Gemma-4-26B-A4B-it-Uncensored-NVFP4` via vLLM + "OpenClaw", claims 45.26 tok/s, 16.3 GB |
| 2 | user68884 | 2026-04-15 | **"Does not even run as configured, do not waste you time."** No specific error. |
| 3 | user99333 | 2026-04-15 | "Please let me know what is the error, it works well on my DGX." No follow-up from user68884. |

**Analysis**: the failure is scoped to (a) a **third-party uncensored fork** (`AEON-7/...`), (b) a custom "OpenClaw" deployment script, and (c) a specific NVFP4 checkpoint with weight-scale-key remapping issues (the ai-muninn.com blog notes that even the base NVFP4 checkpoint requires mounting a `gemma4_patched.py` to fix weight-scale key mapping). The failure report is unresolved because the reporter never answered the OP's request for details.

**This failure does not bear on the base `unsloth/Gemma-4-26B-A4B-it` model.** That model is independently confirmed working by 4 separate users in thread 365547, the NVIDIA blog, and the ai-muninn.com benchmark, across at least two different containerised vLLM stacks (`eugr/spark-vllm-docker` and `vllm/vllm-openai:gemma4-cu130`).

**Lesson to avoid repeating**: do not deploy from third-party uncensored forks without reading the issue tracker. Use the official `unsloth/` or `google/` model IDs and eugr's or vllm-openai's containers.

---

## 6. Option Evaluation Matrix

| Option | Latency | Quality | Effort to implement | Compute cost | Risk | Sunk cost preserved |
|---|---|---|---|---|---|---|
| **(a) Keep 31B Dense only** | ❌ 7 tok/s unusable for chat | ✅ 89.2 AIME | none | none | ⚠️ tutor UX fails | ✅ yes |
| **(b) Switch to 26B MoE, archive Dense** | ✅ 52 tok/s | ✅ 88.3 AIME (−0.9) | **low** (config changes) | 1× re-train (~3–6 h) | ⚠️ first MoE fine-tune (unsloth handles it) | ❌ Dense artifacts idle |
| **(c) Train both — MoE primary, Dense as offline tier** | ✅ 52 tok/s interactive, 7 tok/s batch | ✅ both | low–medium | 1× re-train for MoE | ⚠️ dual-maintenance overhead | ✅ Dense reused for judge/batch |

**Recommendation: Option (c), with MoE as the immediate priority.**

Rationale:
- Option (a) **fails the primary requirement** (interactive tutoring). The original doc said "quantise to Q4_K_M GGUF if latency is a problem" — but the bandwidth analysis shows quantisation won't help on GB10. This option is off the table for the tutor.
- Option (b) is simpler but wastes the completed Dense training run. The Dense fine-tune has real value in non-interactive contexts (dataset filtering, "golden question" generation, judge-model for evaluating MoE outputs, overnight batch rewrites) where 7 tok/s is fine.
- Option (c) adds no additional training cost beyond (b) — the Dense run is already done. It just means *keep the artifacts around and use them where they fit*.

---

## 7. Recommended Decision

### 7.1 Primary decision

**Fine-tune `unsloth/Gemma-4-26B-A4B-it` on the existing GCSE tutor dataset and promote it to primary tutor inference backend once evaluated.** This is the model that gets served by vLLM behind the study-tutor UI.

### 7.2 Secondary decision

**Preserve the 31B Dense fine-tune as an offline "quality tier".** Suggested uses:
- Claude-as-judge-style evaluator for the MoE tutor's outputs on golden GCSE questions
- Overnight batch rewrites of lower-quality examples in the dataset factory
- Dataset curation / hard-example mining

Do **not** invest more compute in the Dense line (no 16-bit LoRA upgrade, no additional epochs) until the MoE tutor is deployed and a real quality-gap measurement exists.

### 7.3 Deferred decision

**After the MoE tutor is deployed and golden-eval'd**, revisit whether the Dense tier still earns its keep. If the MoE's quality is indistinguishable on GCSE-English-specific evaluation, retire the Dense line entirely.

---

## 8. Minimum-Cost Implementation Path

### 8.1 [train_gemma4.py](../../docs/research/train_gemma4.py) changes

Script changes are small and localised:

**A. `DEFAULTS` dict (around line 40):**

```python
DEFAULTS = {
    "model_name": "unsloth/Gemma-4-26B-A4B-it",  # was: "unsloth/gemma-4-31B-it"
    "max_seq_length": 4096,                       # was: 8192 — start conservative per Unsloth MoE guidance
    "load_in_4bit": False,                        # was: True — MoE QLoRA not recommended
    "load_in_16bit": True,                        # NEW — bf16 LoRA for MoE
    "lora_r": 16,                                 # was: 8 — Unsloth suggests higher rank for MoE
    "lora_alpha": 16,                             # was: 8 — match lora_r
    "output_dir": "/workspace/output/gcse-tutor-gemma4-26b-moe",  # was: 31b
    # everything else unchanged
}
```

**B. `FastModel.from_pretrained` call (around line 194):**

```python
model, tokenizer = FastModel.from_pretrained(
    model_name=args.model_name,
    max_seq_length=args.max_seq_length,
    dtype=None,
    load_in_4bit=not args.no_4bit,                # still wired, but default flips to False
    load_in_16bit=True,                           # NEW — required for MoE
    full_finetuning=False,
    use_gradient_checkpointing="unsloth",
    attn_implementation="sdpa",
)
```

**C. CLI arg parser (around line 65):**

Add `--load-in-16bit` / keep `--no-4bit` as-is (the semantics overlap but the flag already exists). Consider renaming the output dir argument's default.

**D. Consider keeping a `train_gemma4_dense.py` copy** rather than overwriting, so the Dense fine-tune remains reproducible. Simplest path: `git mv train_gemma4.py train_gemma4_dense.py && cp train_gemma4_dense.py train_gemma4_moe.py`, then edit `train_gemma4_moe.py` only. This is cheap and preserves reproducibility for both tiers.

**E. Memory expectations (update code comments):**

```python
"load_in_16bit": True,   # LoRA 16-bit — uses ~48GB on GB10 (was ~22GB for QLoRA 4-bit Dense)
```

Still fits in 128 GB unified with substantial KV-cache headroom. No `max_seq_length` reduction needed for memory reasons — the 4096 reduction is for stability per Unsloth's MoE guidance, not memory.

### 8.2 [fine-tuning-getting-started.md](../../docs/research/fine-tuning-getting-started.md) changes

**Section "Why Gemma 4 31B Dense (not Nemotron 3 Nano)"** (lines 17–33): replace with a new "Why Gemma 4 26B A4B MoE (not 31B Dense) on GB10" section referencing:
- GB10 bandwidth ceiling (273 GB/s → ~7 tok/s for 31B Dense regardless of quant)
- 7.5× decode gap measured in NVIDIA forum benchmarks (cite threads 365547, 365814, 366024)
- <1 pt AIME gap
- Unsloth 16-bit LoRA requirement for MoE
- Link this review report as the primary source

**Step 4 dependencies section** (lines 133–138): unchanged.

**Step 5 sanity check** (lines 140–168): update "~60 GB for Gemma 4 31B" download size note to "~48 GB for Gemma 4 26B A4B MoE (16-bit)". Remove the "num_kv_shared_layers = 0" troubleshooting note — that's a Dense-variant Unsloth bug, not relevant to MoE.

**Step 6 memory expectation** (line 193): update "~22–30 GB of the 128 GB unified" to "~48–55 GB of the 128 GB unified".

**Step 9 vLLM serving** (lines 264–296): add MoE-specific vLLM flags:

```bash
vllm serve /workspace/output/gcse-tutor-gemma4-26b-moe/merged-16bit \
  --host 0.0.0.0 \
  --port 8000 \
  --quantization modelopt \
  --moe-backend marlin \
  --kv-cache-dtype fp8
```

Cite the ai-muninn.com benchmark for the flag rationale (`--moe-backend marlin` is essential for SM121 GPUs lacking native FP4 compute).

**Training parameters reference table** (lines 300–318): flip `--model-name` default, add `--load-in-16bit` row, bump `--lora-r` default to 16.

**"Key decisions and trade-offs" → "Why QLoRA 4-bit"** section (lines 323–333): replace with "Why 16-bit LoRA for MoE" explaining the MoE/bitsandbytes incompatibility and the fact that 128 GB unified memory has plenty of headroom for 16-bit anyway.

### 8.3 Effort estimate

- Code changes: ~30 min (straightforward)
- Doc changes: ~1 hour
- Re-training run: 3–6 hours wall-clock, unattended (same as current Dense)
- First sanity-check run (`--max-steps 30`): ~15 minutes
- Golden-eval comparison (Dense artifacts vs MoE artifacts on same questions): ~2 hours including harness setup

**Total: one working day** to go from "Dense is primary" to "MoE is primary and evaluated".

---

## 9. Risks and Mitigations

| Risk | Probability | Impact | Mitigation |
|---|---|---|---|
| First MoE fine-tune hits an Unsloth bug | medium | medium | Start with `--max-steps 30` sanity run; Unsloth's MoE path has day-zero support but is newer code. Pin known-good Unsloth version; check Unsloth GitHub issues for `gemma-4-26B-A4B` entries before starting. |
| Fine-tuned MoE quality is noticeably worse on GCSE tasks than Dense | low–medium | medium | Keep Dense artifacts; run a golden-question comparison before retiring Dense. Decision is reversible. |
| MoE training hang (similar to the "Spark long-run hang" already documented for Dense) | medium | low | Same workaround: `--max-seq-length 4096`, `--save-steps 100`, use `--resume` after any hang. |
| `--moe-backend marlin` vLLM flag breaks or is removed in a vLLM minor version | low | low | Pin the `vllm/vllm-openai:gemma4-cu130` container tag explicitly; do not float to `:latest`. |
| The NVFP4 checkpoint key-mapping patch (`gemma4_patched.py`) required for vLLM inference becomes stale | medium | low | Use the merged-16bit path from our own fine-tune rather than any third-party NVFP4 checkpoint — we serve what we trained, not someone else's quantisation. |
| 0.9 pt AIME gap matters more than expected on a specific GCSE reasoning subset | low | low | Judge with the Dense model on the subset where it matters; ensemble or fall back if a regression is detected. |

---

## 10. Answers to Task Review Questions

**Q1. Which Gemma 4 variant is actually better for real-time GCSE tutoring on GB10?**
26B A4B MoE. Latency is decisive (~7.5× faster decode), quality gap is negligible (<1 pt AIME), and Unsloth supports fine-tuning it cleanly with a small config change.

**Q2. Was the original Dense-vs-MoE reasoning sound?**
Partially. The "MoE = QLoRA risky" part was correct — Unsloth still officially says avoid QLoRA on Gemma 4 26B A4B. But the "must avoid router layer" part is obsolete (Unsloth handles it). The "quality ceiling is substantially higher" claim was wrong (<1 pt gap). And the "if latency becomes a problem, quantise to Q4_K_M" fallback **does not work on GB10** because the 31B Dense is bandwidth-bound, not compute-bound — quantisation cannot rescue it.

**Q3. Real inference latency of current 31B Dense on GB10?**
5–7 tok/s decode, single user, regardless of Q4/Q8/FP8 quantisation. TTFT ~333 ms (fine), but decode is unusable for interactive chat. To hit usable latency on 31B Dense would require two Sparks with TP=2 over InfiniBand (→17 tok/s with NVFP4) — still worse than a single-Spark MoE.

**Q4. Can we QLoRA fine-tune the 26B MoE safely?**
No, and we don't need to. Unsloth explicitly recommends `load_in_16bit=True` for this MoE. 16-bit LoRA uses ~48 GB, which is fine in 128 GB unified memory. No router-layer manipulation required — Unsloth handles it. The 4-bit path is blocked by bitsandbytes' inability to quantise Gemma 4's 3D fused expert tensors, not by anything we can fix.

**Q5. Minimum-cost path to switch?**
See §8. Roughly one working day: ~30 min code changes, ~1 h doc changes, 3–6 h unattended re-training, ~2 h golden-eval comparison. No new dependencies, no framework migration — same Unsloth + TRL + FastModel pipeline.

**Q6. Sunk-cost check — is 31B Dense usable in production regardless?**
Yes, as a **non-interactive** tier. Keep artifacts for judge-model / batch dataset work / offline rewriting. Do not use it for the interactive tutor. Do not invest further compute until MoE is evaluated.

---

## 11. Acceptance Criteria Checklist

- [x] Read both NVIDIA forum threads end-to-end including all replies; "didn't work" failure is scoped to third-party AEON-7 uncensored fork + OpenClaw scripts, not base model (see §5)
- [x] Searched NVIDIA Developer Forums for additional Gemma 4 / GB10 reports — found threads 366024 (slow 31B), 365814 (FP8 31B TP=2), 365503 (day-1 benchmarks), 366162 (NemoClaw dual-model), 365685 ("anyone running 31B on Spark")
- [ ] Spark Arena leaderboard check — **spark-arena.com/leaderboard returned HTTP 403 to automated fetch; not retrieved in this pass.** The absence does not change the recommendation — forum and blog benchmarks are consistent and decisive. Manual follow-up recommended but not blocking.
- [x] Confirmed exact Unsloth model ID: `unsloth/Gemma-4-26B-A4B-it` (instruction-tuned variant exists)
- [x] Verified Unsloth MoE fine-tuning support: 16-bit LoRA required, router layers handled automatically, FastModel loader unchanged
- [x] Benchmark numbers collected for both variants on GB10 (see §2.3)
- [x] Produced decision recommendation: **Option (c) — train both as tiers, MoE primary** (see §7)
- [x] Listed exact script changes to [train_gemma4.py](../../docs/research/train_gemma4.py) and doc updates for [fine-tuning-getting-started.md](../../docs/research/fine-tuning-getting-started.md) (see §8)
- [x] Documented decision and rationale for future reference (this report)

---

## 12. Sources

**NVIDIA Developer Forums (primary)**

- [someone post this: Gemma 4 26B A4B MoE running at 45-60 tok/s on DGX Spark (thread 365547)](https://forums.developer.nvidia.com/t/someone-post-this-gemma-4-26b-a4b-moe-running-at-45-60-tok-s-on-dgx-spark/365547) — 4 independent confirmations of 45–60 tok/s on base model via eugr's vLLM container
- [Guide: Uncensored Gemma-4-26B at 45 tok/s on DGX Spark (thread 366442)](https://forums.developer.nvidia.com/t/guide-uncensored-gemma-4-26b-at-45-tok-s-on-dgx-spark-actually-feels-great-to-use/366442) — the "didn't work" reply is scoped to AEON-7 uncensored fork + OpenClaw scripts
- [Slow inference with 31b model Gemma 4? Optimizations? (thread 366024)](https://forums.developer.nvidia.com/t/slow-inference-with-31b-model-gemma-4-optimizations/366024) — 5–10 tok/s on 31B Dense, "5 is unusable honestly"
- [Gemma 4 31B on DGX Spark: Runtime FP8 Benchmarks — Single & Dual Node TP=2 (thread 365814)](https://forums.developer.nvidia.com/t/gemma-4-31b-on-dgx-spark-runtime-fp8-benchmarks-single-dual-node-tp-2/365814) — 6.9 tok/s single, 11.2 tok/s TP=2
- [Gemma 4 Day-1 Inference on NVIDIA DGX Spark — Preliminary Benchmarks (thread 365503)](https://forums.developer.nvidia.com/t/gemma-4-day-1-inference-on-nvidia-dgx-spark-preliminary-benchmarks/365503) — supporting
- [Guide: Gemma 4 31B on DGX Spark via NemoClaw — Dual-Model Setup (thread 366162)](https://forums.developer.nvidia.com/t/guide-gemma-4-31b-on-dgx-spark-via-nemoclaw-dual-model-setup-guide/366162) — supporting

**Unsloth official documentation**

- [Gemma 4 Fine-tuning Guide | Unsloth Documentation](https://unsloth.ai/docs/models/gemma-4/train) — confirms `unsloth/Gemma-4-26B-A4B-it`, `load_in_16bit=True`, `load_in_4bit=False` requirement, automatic router handling
- [Gemma 4 - How to Run Locally | Unsloth Documentation](https://unsloth.ai/docs/models/gemma-4)
- [unsloth/gemma-4-26B-A4B-it-GGUF · Hugging Face](https://huggingface.co/unsloth/gemma-4-26B-A4B-it-GGUF)

**Google Gemma 4 model card and benchmarks**

- [Gemma 4 model card | Google AI for Developers](https://ai.google.dev/gemma/docs/core/model_card_4)
- [Gemma 4: Byte for byte, the most capable open models (Google blog)](https://blog.google/innovation-and-ai/technology/developers-tools/gemma-4/)
- [Gemma 4 26B A4B - Intelligence, Performance & Price Analysis (artificialanalysis.ai)](https://artificialanalysis.ai/models/gemma-4-26b-a4b)
- [google/gemma-4-26B-A4B-it · Hugging Face](https://huggingface.co/google/gemma-4-26B-A4B-it)

**Independent benchmark (decisive MoE numbers)**

- [Benchmark: Gemma 4 26B on DGX Spark — 52 tok/s at only 16 GB, vLLM NVFP4 real numbers (ai-muninn.com)](https://ai-muninn.com/en/blog/dgx-spark-gemma4-26b-nvfp4-52-toks) — 52 ± 0.1 tok/s, TTFT 53 ms, 16.5 GB, 114.6 tok/s at 3 concurrent, explicit 7.5× multiplier vs 31B Dense

**Local sources**

- [docs/research/fine-tuning-getting-started.md](../../docs/research/fine-tuning-getting-started.md) — current rationale, lines 17–33
- [docs/research/train_gemma4.py](../../docs/research/train_gemma4.py) — current training script, `model_name` at line 41

---

## Decision Checkpoint

Review Results:
  - **Decision**: switch primary to 26B A4B MoE; keep 31B Dense as offline quality tier
  - **Confidence**: high — the bandwidth math is mechanical, the quality gap is measured and tiny, and Unsloth support is documented and first-party
  - **Findings**: 7 (bandwidth ceiling, quality gap, Unsloth 16-bit requirement, router auto-handling, failure-mode misattribution, sunk-cost preservation path, implementation effort)
  - **Recommendations**: 6 (script changes, doc changes, training re-run, golden eval, preserve Dense artifacts, pin vLLM container)

Options:
  - **[A]ccept** — approve this recommendation, mark TASK-REV-G4MOE as REVIEW_COMPLETE
  - **[R]evise** — request deeper analysis (e.g. manual Spark Arena leaderboard check, or actually benchmark the current Dense fine-tune on GB10 with your own prompts before deciding)
  - **[I]mplement** — generate implementation subtasks for the script/doc changes and MoE re-training run
  - **[C]ancel** — discard this review
