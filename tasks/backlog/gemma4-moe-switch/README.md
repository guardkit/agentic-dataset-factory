# Feature: gemma4-moe-switch

**Parent review**: [TASK-REV-G4MOE](../TASK-REV-G4MOE-review-gemma4-moe-vs-dense-choice.md)
**Feature ID**: FEAT-G4MOE
**Status**: backlog
**Confidence**: HIGH (based on independently measured GB10 benchmarks and first-party Unsloth docs)

## Problem Statement

We fine-tuned `unsloth/gemma-4-31B-it` (Dense) on the GCSE English tutor dataset for interactive tutoring. On GB10, the 31B Dense is bandwidth-bound to **~6.9 tok/s** single-user decode (mechanical ceiling: 273 GB/s ÷ ~31 GB/token ≈ 8.8 tok/s), which NVIDIA forum users describe as *"unusable"*. A 200-token tutor response takes ~29 s wall-clock — not a real-time tutor. Quantisation cannot rescue this because the bottleneck is memory bandwidth, not compute.

The Gemma 4 26B A4B MoE variant runs at **52 tok/s** on the same hardware (measured, stable), with TTFT 53 ms and 16.5 GB footprint, while scoring within **0.9 points** of 31B Dense on AIME 2026 (88.3 vs 89.2) and only 2.6 pt on MMLU Pro. For GCSE English tutoring — where the bottleneck is the fine-tune data and tone, not base-model reasoning ceiling — that quality gap is invisible.

Unsloth has first-party support for `unsloth/Gemma-4-26B-A4B-it` with `load_in_16bit=True` (MoE QLoRA is officially not recommended — bitsandbytes cannot quantise Gemma 4's 3D fused expert tensors). Router-layer handling is automatic.

## Solution Approach

Switch primary fine-tune target from 31B Dense to 26B A4B MoE. Preserve the existing 31B Dense artifacts as an offline "quality tier" (Claude-style judge, dataset filtering, batch rewrites) where 7 tok/s is acceptable. Do not delete the Dense training script; split into two sibling scripts (`train_gemma4_dense.py`, `train_gemma4_moe.py`) so both tiers remain reproducible.

**Decision reversibility**: high. Dense artifacts are preserved; if MoE quality is a regression on GCSE-specific evaluation, we can fall back without re-training.

## Subtasks

| ID | Title | Wave | File | Mode | Status |
|---|---|---|---|---|---|
| [TASK-G4MOE-001](TASK-G4MOE-001-split-training-script.md) | Split `train_gemma4.py` into dense + moe siblings | 1 | [docs/research/train_gemma4.py](../../../docs/research/train_gemma4.py) | direct | backlog |
| [TASK-G4MOE-002](TASK-G4MOE-002-moe-script-config.md) | Configure `train_gemma4_moe.py` for 26B A4B MoE | 1 | `docs/research/train_gemma4_moe.py` | task-work | backlog |
| [TASK-G4MOE-003](TASK-G4MOE-003-update-getting-started-doc.md) | Update `fine-tuning-getting-started.md` for MoE primary | 1 | [docs/research/fine-tuning-getting-started.md](../../../docs/research/fine-tuning-getting-started.md) | direct | backlog |
| [TASK-G4MOE-004](TASK-G4MOE-004-moe-training-run.md) | Execute MoE fine-tune on GB10 (sanity + full + smoke test) | 2 | (on GB10, unattended) | manual | backlog |

Quality check after training is the Step 7 smoke-test in TASK-G4MOE-004 — same informal "does it feel like a GCSE tutor?" check the Dense run got. No separate eval harness.

See [IMPLEMENTATION-GUIDE.md](IMPLEMENTATION-GUIDE.md) for execution order, parallelisation strategy, and validation checklist.

## Non-goals

- **Deleting the 31B Dense training script or artifacts** — explicit sunk-cost preservation per review §7.2. Dense stays archived as a fallback if MoE turns out to have a quality problem on real use.
- **Formal eval harness / golden-question comparison** — we didn't build one for the Dense run and aren't building one now. Step 7 smoke-test in TASK-G4MOE-004 is the quality check, same as Dense got.
- **Migrating away from Unsloth / TRL SFTTrainer** — same pipeline, config changes only
- **Training on a different dataset** — no dataset changes; the existing `output/train.jsonl` and `<think>` / ShareGPT format transfer unchanged to MoE
- **Deploying NVFP4 checkpoints from third parties** — we serve what we fine-tune ourselves (explicit lesson from the forum failure analysis)
- **Adding tensor-parallel serving** — single-Spark MoE already hits 52 tok/s, no need for TP=2

## References

- Review report: [.claude/reviews/TASK-REV-G4MOE-review-report.md](../../../.claude/reviews/TASK-REV-G4MOE-review-report.md)
- Current Dense training script: [docs/research/train_gemma4.py](../../../docs/research/train_gemma4.py)
- Current getting-started guide: [docs/research/fine-tuning-getting-started.md](../../../docs/research/fine-tuning-getting-started.md)
- Unsloth MoE fine-tuning docs: https://unsloth.ai/docs/models/gemma-4/train
- Decisive MoE benchmark (52 tok/s): https://ai-muninn.com/en/blog/dgx-spark-gemma4-26b-nvfp4-52-toks
- NVIDIA forum 31B slow-inference thread: https://forums.developer.nvidia.com/t/slow-inference-with-31b-model-gemma-4-optimizations/366024
