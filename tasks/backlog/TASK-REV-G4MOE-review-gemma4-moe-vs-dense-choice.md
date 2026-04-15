---
id: TASK-REV-G4MOE
title: Review Gemma 4 MoE vs Dense model choice for fine-tune
status: review_complete
task_type: review
decision_required: true
created: 2026-04-15T00:00:00Z
updated: 2026-04-15T00:00:00Z
priority: high
tags: [review, fine-tuning, gemma4, model-selection, decision-point]
complexity: 0
test_results:
  status: pending
  coverage: null
  last_run: null
review_results:
  mode: decision
  depth: standard
  decision: switch-to-moe-primary-keep-dense-as-offline-tier
  findings_count: 7
  recommendations_count: 6
  report_path: .claude/reviews/TASK-REV-G4MOE-review-report.md
  completed_at: 2026-04-15T00:00:00Z
  key_numbers:
    dense_31b_tok_s_single_gb10: 6.9
    moe_26b_a4b_tok_s_single_gb10: 52
    decode_speed_ratio: 7.5
    aime_quality_gap_points: 0.9
    unsloth_model_id: unsloth/Gemma-4-26B-A4B-it
    unsloth_loader_config: load_in_16bit=True (MoE QLoRA unsupported)
---

# Task: Review Gemma 4 MoE vs Dense model choice for fine-tune

## Description

We fine-tuned `unsloth/gemma-4-31B-it` (Dense) on the GCSE English tutor dataset
using [train_gemma4.py](docs/research/train_gemma4.py) following
[fine-tuning-getting-started.md](docs/research/fine-tuning-getting-started.md).

Concern: we may have picked the wrong Gemma 4 variant. Two NVIDIA forum posts
suggest the 26B **MoE** (A4B — 4B active params) variant is the better fit for
the GB10 / DGX Spark, running at ~45–60 tok/s:

- "Gemma 4 26B A4B MoE running at 45-60 tok/s on DGX Spark" — https://forums.developer.nvidia.com/t/someone-post-this-gemma-4-26b-a4b-moe-running-at-45-60-tok-s-on-dgx-spark/365547
- "Uncensored Gemma 4 26B at 45 tok/s on DGX Spark, actually feels great to use" — https://forums.developer.nvidia.com/t/guide-uncensored-gemma-4-26b-at-45-tok-s-on-dgx-spark-actually-feels-great-to-use/366442

**Caveat noted by user**: a later reply in the "uncensored" thread says that
approach didn't work — the reviewer must read the full thread and capture the
failure mode so we don't repeat it.

The getting-started doc itself flagged this trade-off at [fine-tuning-getting-started.md:30-32](docs/research/fine-tuning-getting-started.md#L30-L32):
"If inference latency becomes a problem for real-time tutoring, quantise the
trained model (Q4_K_M GGUF) or evaluate the 26B MoE later." This review is the
"later".

This is an analysis/decision task, not an implementation task. Use `/task-review`.

## Review Questions

1. **Which Gemma 4 variant is actually better for real-time GCSE tutoring on GB10?**
   - Dense 31B (current choice): higher reasoning quality ceiling, slower inference
   - MoE 26B (forum guide): ~45 tok/s on DGX Spark, smaller active params
2. **Was the original Dense-vs-MoE reasoning at [fine-tuning-getting-started.md:17-33](docs/research/fine-tuning-getting-started.md#L17-L33) sound?**
   - Original claim: "MoE = must avoid router layer, QLoRA risky"
   - Does the NVIDIA forum guide contradict or confirm this? What does it do about the router layer?
3. **What is the real inference latency of our current fine-tuned 31B Dense** on GB10, and is it acceptable for interactive tutoring (target: <2s first-token, streaming fluent)?
4. **Can we QLoRA fine-tune the 26B MoE safely?** Check current Unsloth support, known MoE fine-tuning pitfalls, router-layer handling.
5. **If we should switch**, what is the minimum-cost path? (re-run existing `train_gemma4.py` with `--model-name unsloth/gemma-4-26B-MoE-it` or equivalent, vs. script changes needed)
6. **Sunk-cost check**: is the 31B Dense fine-tune usable in production regardless? Keep it as the quality tier, add MoE as the latency tier?

## Acceptance Criteria

- [ ] Read both NVIDIA forum threads end-to-end **including all replies** — extract exact model ID, tok/s numbers, quality observations, and document the "didn't work" failure mode from the later reply in the uncensored thread
- [ ] Search NVIDIA Developer Forums for additional Gemma 4 / DGX Spark / GB10 reports and collate findings
- [ ] Check spark-arena.com/leaderboard for Gemma 4 26B MoE and 31B Dense rankings on Spark hardware
- [ ] Confirm the exact Unsloth model ID for the Gemma 4 26B MoE variant (and whether an `-it` instruction-tuned version exists)
- [ ] Verify current Unsloth MoE fine-tuning support and any router-layer freezing requirements
- [ ] Benchmark (or estimate from published numbers) real inference latency of both variants on GB10 for typical GCSE tutor prompts
- [ ] Produce a decision recommendation with one of: (a) keep Dense, (b) switch to MoE, (c) train both as tiers
- [ ] If switch recommended: list exact script changes needed in [train_gemma4.py](docs/research/train_gemma4.py) and doc updates needed in [fine-tuning-getting-started.md](docs/research/fine-tuning-getting-started.md)
- [ ] Document the decision and rationale for future reference

## Sources to Review

### Primary forum threads (read in full, including all replies)

- https://forums.developer.nvidia.com/t/someone-post-this-gemma-4-26b-a4b-moe-running-at-45-60-tok-s-on-dgx-spark/365547 — original tok/s claim for 26B A4B MoE
- https://forums.developer.nvidia.com/t/guide-uncensored-gemma-4-26b-at-45-tok-s-on-dgx-spark-actually-feels-great-to-use/366442 — setup guide; **note**: a later reply reports it didn't work. Capture exactly what failed.

### Required searches

- **NVIDIA Developer Forums** (https://forums.developer.nvidia.com/) — search for `gemma 4 26b`, `gemma 4 moe`, `dgx spark gemma`, `gb10 gemma fine-tune`, `gemma 4 a4b`. Collate community experience reports, known bugs, and working configurations on DGX Spark / GB10 specifically.
- **Spark Arena leaderboard** (https://spark-arena.com/leaderboard) — find where Gemma 4 26B MoE and 31B Dense rank for latency and quality on Spark hardware. This is the authoritative community benchmark for our target platform.

### Local sources

- [docs/research/fine-tuning-getting-started.md](docs/research/fine-tuning-getting-started.md) — current rationale for Dense choice (lines 17-33)
- [docs/research/train_gemma4.py](docs/research/train_gemma4.py) — current training script (`model_name` at line 41)

### External docs

- Unsloth docs / release notes — MoE fine-tuning support status, router-layer handling, any `gemma-4-26B-A4B` model IDs
- Google Gemma 4 model card — Dense 31B and 26B A4B MoE variants, intended use cases, licence differences

## Implementation Notes

Full review report: [.claude/reviews/TASK-REV-G4MOE-review-report.md](../../.claude/reviews/TASK-REV-G4MOE-review-report.md)

### Decision
**Switch primary fine-tune to `unsloth/Gemma-4-26B-A4B-it` (MoE). Keep the existing 31B Dense fine-tune as an offline "quality tier" for judge/batch work. Do not invest further compute in the Dense line until the MoE is deployed and golden-eval'd.**

### One-paragraph rationale
On GB10 the 31B Dense is bandwidth-bound to **~7 tok/s** (273 GB/s ÷ ~31 GB/token — quantisation can't rescue this), which NVIDIA forum users call "unusable". The 26B A4B MoE runs at a measured **52 tok/s** on the same hardware (7.5× faster) with **TTFT 53 ms** and **16.5 GB** footprint, while scoring within **0.9 points** of 31B Dense on AIME 2026 (88.3 vs 89.2). Unsloth has day-zero first-party support for fine-tuning `unsloth/Gemma-4-26B-A4B-it` — the only change required is `load_in_16bit=True` (MoE QLoRA is unsupported because bitsandbytes can't quantise Gemma 4's 3D fused expert tensors yet). Router-layer handling is automatic. The forum-reported "didn't work" reply is scoped to a third-party AEON-7 uncensored fork + custom OpenClaw deployment, **not** the base model, which is independently confirmed working by ≥4 users.

### Required script changes ([train_gemma4.py](../../docs/research/train_gemma4.py))
1. `DEFAULTS["model_name"]`: `"unsloth/gemma-4-31B-it"` → `"unsloth/Gemma-4-26B-A4B-it"`
2. `DEFAULTS["load_in_4bit"]`: `True` → `False`
3. Add `DEFAULTS["load_in_16bit"] = True`
4. Add `load_in_16bit=True` to the `FastModel.from_pretrained` call (around line 194)
5. `DEFAULTS["max_seq_length"]`: `8192` → `4096` (Unsloth's conservative MoE starting point; scale up after stability)
6. `DEFAULTS["lora_r"]` / `lora_alpha`: `8` → `16` (Unsloth MoE guidance)
7. `DEFAULTS["output_dir"]`: `gcse-tutor-gemma4-31b` → `gcse-tutor-gemma4-26b-moe`
8. Recommended: `git mv train_gemma4.py train_gemma4_dense.py` and create a sibling `train_gemma4_moe.py` so both tiers are reproducible.

### Required doc changes ([fine-tuning-getting-started.md](../../docs/research/fine-tuning-getting-started.md))
- Replace "Why Gemma 4 31B Dense (not Nemotron 3 Nano)" section (lines 17–33) with new "Why Gemma 4 26B A4B MoE (not 31B Dense) on GB10" section citing GB10 bandwidth ceiling, 7.5× decode gap, <1 pt AIME gap.
- Update memory expectations: `~22–30GB` → `~48–55GB` at 16-bit LoRA (still comfortable in 128 GB unified).
- Add MoE-specific vLLM serving flags to Step 9: `--quantization modelopt --moe-backend marlin --kv-cache-dtype fp8`.
- Remove the "num_kv_shared_layers = 0" troubleshooting note (Dense-variant bug, not applicable to MoE).
- Replace "Why QLoRA 4-bit" subsection with "Why 16-bit LoRA for MoE" explaining the bitsandbytes/expert-tensor incompatibility.

### Estimated effort
~30 min code changes + ~1 h doc changes + 3–6 h unattended re-training + ~2 h golden-eval comparison ≈ **one working day**.

### Decision status
Review complete, awaiting human decision: [A]ccept / [R]evise / [I]mplement / [C]ancel.

## Test Execution Log

_N/A — review task._
