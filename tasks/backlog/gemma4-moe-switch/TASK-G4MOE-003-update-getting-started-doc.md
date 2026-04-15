---
id: TASK-G4MOE-003
title: Update fine-tuning-getting-started.md for MoE primary
status: backlog
created: 2026-04-15T00:00:00Z
updated: 2026-04-15T00:00:00Z
priority: high
tags: [docs, fine-tuning, gemma4, moe]
complexity: 2
parent_review: TASK-REV-G4MOE
feature_id: FEAT-G4MOE
wave: 1
implementation_mode: direct
dependencies: []
---

# Task: Update fine-tuning-getting-started.md for MoE primary

## Description

[docs/research/fine-tuning-getting-started.md](../../../docs/research/fine-tuning-getting-started.md) currently documents the 31B Dense fine-tune as the default path. Review TASK-REV-G4MOE inverts this: MoE is now primary, Dense is the offline quality tier. Rewrite the affected sections to reflect the new primary, add the MoE-specific vLLM serving flags, and correct the memory expectations.

**Do not delete the Dense instructions wholesale.** Demote them to a "Dense tier (offline)" subsection so the offline quality-tier workflow stays reproducible.

## Specific edits

### §"Why Gemma 4 31B Dense (not Nemotron 3 Nano)" (lines 17–33)

**Replace** the entire subsection with a new one:

```markdown
### Why Gemma 4 26B A4B MoE (primary) and 31B Dense (offline tier) on GB10

| Factor | 26B A4B MoE (primary) | 31B Dense (offline) |
|---|---|---|
| Architecture | MoE (3.8B active of 25.2B total) | Dense (all 31B active) |
| Measured decode speed on GB10 | ~52 tok/s | ~6.9 tok/s (bandwidth-bound) |
| TTFT (512-tok prompt) | ~53 ms | ~333 ms |
| 200-tok response wall-clock | ~4 s | ~29 s |
| AIME 2026 | 88.3% | 89.2% (Δ 0.9 pt) |
| MMLU Pro | 82.6% | 85.2% (Δ 2.6 pt) |
| Unsloth QLoRA 4-bit | **not supported** — use 16-bit LoRA | supported |
| VRAM for training | ~48 GB (16-bit LoRA) | ~22 GB (QLoRA 4-bit) |
| Router layers | handled automatically by Unsloth | n/a |
| Licence | Apache 2.0 | Apache 2.0 |

**Decision**: Use 26B A4B MoE as the **primary interactive tutor** backend. GB10
is bandwidth-bound at ~273 GB/s, so the 31B Dense decode ceiling is ~7–9 tok/s
regardless of quantisation — unusable for real-time tutoring. The MoE hits
52 tok/s measured, with only a <1 pt AIME gap. See
[TASK-REV-G4MOE review report](../../.claude/reviews/TASK-REV-G4MOE-review-report.md)
for full benchmark evidence and source links.

**Retain** the 31B Dense fine-tune as an **offline quality tier** for
non-interactive work: Claude-style judge evaluation, overnight batch rewrites,
hard-example mining, dataset curation. At 7 tok/s those workloads are fine.
Do not use it for the interactive tutor.

Training scripts live in two siblings so both tiers remain reproducible:
- `docs/research/train_gemma4_moe.py`    — MoE primary
- `docs/research/train_gemma4_dense.py`  — Dense offline tier
```

### §"Training data compatibility" (lines 34–44)

- [ ] No changes. Gemma 4 26B A4B has the same `<think>` thinking-mode and `gemma-4-thinking` chat template as 31B Dense, so the 75/25 reasoning split and ShareGPT format transfer unchanged.

### §"Prerequisites" (lines 48–58)

- [ ] No changes. Docker image and CUDA version are identical.

### §"Step 5: Verify the setup" (lines 140–168)

- [ ] Update "~60GB for Gemma 4 31B" → "~48GB for Gemma 4 26B A4B MoE (16-bit)"
- [ ] Update loss-range note: "Loss should be in the 1–3 range for the 31B model" → "Loss should be in the 1–3 range for the 26B MoE; higher rank (16) may give slightly higher initial loss than Dense rank 8"
- [ ] **Remove** the `num_kv_shared_layers = 0` troubleshooting bullet (Dense-variant Unsloth bug, not applicable to MoE)
- [ ] Keep the "gradient accumulation loss explosion" bullet (still relevant)
- [ ] Keep the "training hang on long runs" bullet (known Spark issue affects both variants)

### §"Step 6: Full training run" (lines 170–194)

- [ ] Update command from `python scripts/train_gemma4.py` to `python scripts/train_gemma4_moe.py`
- [ ] Update "QLoRA 4-bit should use ~22–30GB" → "16-bit LoRA should use ~48–55GB of the 128 GB unified memory. You have substantial headroom."
- [ ] Update output directory in Step 7 tree from `gcse-tutor-gemma4-31b/` → `gcse-tutor-gemma4-26b-moe/`

### §"Step 9: Serve via vLLM" (lines 264–296)

Add MoE-specific serving flags. Replace the `vllm serve` command with:

```bash
# Pin the container tag explicitly — do not float to :latest
docker run --gpus all --network host \
  vllm/vllm-openai:gemma4-cu130 \
  --model /workspace/output/gcse-tutor-gemma4-26b-moe/merged-16bit \
  --host 0.0.0.0 \
  --port 8000 \
  --quantization modelopt \
  --moe-backend marlin \
  --kv-cache-dtype fp8
```

Add a short note explaining the flags:

```markdown
- `--quantization modelopt`: Model Optimizer quantisation path
- `--moe-backend marlin`: **required** for SM121 (GB10 Blackwell) lacking native FP4 compute
- `--kv-cache-dtype fp8`: reduces KV-cache pressure, leaves more headroom for long GCSE conversations
```

Cite [ai-muninn.com/en/blog/dgx-spark-gemma4-26b-nvfp4-52-toks](https://ai-muninn.com/en/blog/dgx-spark-gemma4-26b-nvfp4-52-toks) as the source for the `--moe-backend marlin` requirement.

### §"Training parameters reference" table (lines 300–318)

- [ ] `--model-name` default: `unsloth/gemma-4-31B-it` → `unsloth/Gemma-4-26B-A4B-it`
- [ ] Add `--load-in-16bit` row: default `true`, note "required for MoE"
- [ ] `--max-seq-length` default: `8192` → `4096` (Unsloth MoE starting point; scale up after stability)
- [ ] `--lora-r` default: `8` → `16` (Unsloth MoE guidance)
- [ ] `--lora-alpha` default: `8` → `16`

### §"Why QLoRA 4-bit" subsection (lines 323–333)

**Replace** the entire subsection with:

```markdown
### Why 16-bit LoRA (not QLoRA 4-bit) for the MoE primary

The 26B A4B MoE has 3D fused expert tensors that bitsandbytes cannot currently
quantise at 4-bit. Unsloth's official guidance is: `load_in_4bit = False,
load_in_16bit = True`. Attempting QLoRA on the MoE will either fail to load or
produce broken gradients through the expert weights.

The 16-bit LoRA path uses ~48 GB during training — well within GB10's 128 GB
unified memory, with substantial KV-cache and optimiser headroom. There is no
quality penalty because we are not trading down from an otherwise-working
option; 16-bit is the only viable path for this architecture.

For the offline 31B Dense tier, QLoRA 4-bit remains the right choice — see
`train_gemma4_dense.py`.
```

## Scope

- [ ] Apply all section edits listed above
- [ ] Verify all internal links still resolve
- [ ] Add a link from the top of the file to the review report
- [ ] Leave the Troubleshooting section intact (CUDA OOM, loss 100+/NaN, hang, chat template mismatch) — all still relevant

## Acceptance Criteria

- [ ] Rationale section now names 26B A4B MoE as primary with benchmark numbers
- [ ] Dense tier retained as "offline quality tier" subsection, not deleted
- [ ] vLLM command includes `--quantization modelopt --moe-backend marlin --kv-cache-dtype fp8`
- [ ] Memory expectations updated from 22 GB to 48 GB
- [ ] `num_kv_shared_layers = 0` troubleshooting bullet removed
- [ ] Training parameters table reflects new defaults (model ID, lora-r 16, max-seq 4096)
- [ ] No lingering references to `train_gemma4.py` (should be `train_gemma4_moe.py` or `train_gemma4_dense.py`)
- [ ] Review report linked from the top of the file and from the rationale section
