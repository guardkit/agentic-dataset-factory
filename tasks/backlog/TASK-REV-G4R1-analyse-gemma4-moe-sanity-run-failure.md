---
id: TASK-REV-G4R1
title: Analyse Gemma 4 MoE sanity run failure (torchao incompatibility)
status: review_complete
created: 2026-04-18T00:00:00Z
updated: 2026-04-18T00:00:00Z
priority: high
tags: [review, fine-tuning, gemma4, moe, gb10, dependency, torchao]
complexity: 3
task_type: review
parent_task: TASK-G4MOE-004
feature_id: FEAT-G4MOE
review_results:
  mode: decision
  depth: standard
  score: 85
  findings_count: 5
  recommendations_count: 5
  decision: implement
  report_path: .claude/reviews/TASK-REV-G4R1-review-report.md
  completed_at: 2026-04-18T00:00:00Z
---

# Task: Analyse Gemma 4 MoE sanity run failure (torchao incompatibility)

## Description

The first attempt at TASK-G4MOE-004 Step 4 (sanity run with `--max-steps 30`) failed during LoRA adapter injection. The full error log is captured in [docs/reviews/training-gemma4-moe/run-1.md](../../../docs/reviews/training-gemma4-moe/run-1.md).

The model downloaded successfully (~51.6 GB), Unsloth detected the MoE architecture (128 experts), and correctly identified MoE-specific LoRA targets (`experts.gate_up_proj`, `experts.down_proj`). However, when PEFT attempted to create LoRA modules, it crashed with:

```
ImportError: Found an incompatible version of torchao. Found version 0.14.0+git, but only versions above 0.16.0 are supported
```

The crash occurs in the PEFT library's LoRA dispatcher (`peft/tuners/lora/torchao.py:142`) when checking `is_torchao_available()`, which enforces a minimum `torchao >= 0.16.0` version gate.

### Key observations from the log

1. **Environment**: Unsloth 2026.4.6, Transformers 5.5.4, Torch 2.10.0a0 (nv25.11), CUDA 12.1, Toolkit 13.0
2. **Container**: `nvcr.io/nvidia/pytorch:25.11-py3` — ships `torchao 0.14.0+git` which is below PEFT's minimum
3. **Flash Attention**: Correctly fell back to SDPA (FA2 max head dim 256 vs Gemma4's 512) — this is expected, not an error
4. **MoE detection worked**: Unsloth correctly identified 128 experts and MoE-specific target modules
5. **Failure point**: `FastModel.get_peft_model()` at `train_gemma4_moe.py:241` → PEFT → torchao version check

## Analysis Questions

1. **Root cause**: Is the `torchao` version pinned by the NVIDIA base image (`nvcr.io/nvidia/pytorch:25.11-py3`) or by one of the pip-installed packages? Can it be upgraded independently without breaking PyTorch/CUDA compatibility?

2. **Fix options**:
   - (a) `pip install --upgrade torchao>=0.16.0` inside the container — will this conflict with the NVIDIA PyTorch build?
   - (b) `pip install --upgrade peft` — does a newer PEFT relax or remove the torchao version gate?
   - (c) Pin a specific PEFT version that doesn't enforce torchao>=0.16.0 (e.g., roll back PEFT)
   - (d) Use a newer NVIDIA base image that ships torchao>=0.16.0

3. **Step 3 dependency list gap**: The TASK-G4MOE-004 Step 3 install command does not mention `torchao`. Should it be added explicitly, or should it be pulled transitively?

4. **Dense script comparison**: Did the Dense training run (`train_gemma4_dense.py`) encounter this same issue? If not, why — does Dense avoid the PEFT torchao dispatcher path?

5. **Unsloth compatibility**: Unsloth 2026.4.6 patches PEFT's `_create_and_replace` (`vision.py:1469`). Does the Unsloth patch interact with the torchao check, or is this purely a PEFT-level issue?

## Acceptance Criteria

- [ ] Root cause identified: which package introduced the torchao>=0.16.0 requirement
- [ ] Recommended fix with specific version pins or install commands
- [ ] Updated Step 3 dependency install command for TASK-G4MOE-004
- [ ] Assessment of whether this affects the Dense training path
- [ ] Confirmed that the fix doesn't break PyTorch/CUDA/Unsloth compatibility on GB10

## Source Materials

- Error log: [docs/reviews/training-gemma4-moe/run-1.md](../../../docs/reviews/training-gemma4-moe/run-1.md)
- Implementation guide: [tasks/backlog/gemma4-moe-switch/IMPLEMENTATION-GUIDE.md](gemma4-moe-switch/IMPLEMENTATION-GUIDE.md)
- Task with execution steps: [tasks/backlog/gemma4-moe-switch/TASK-G4MOE-004-moe-training-run.md](gemma4-moe-switch/TASK-G4MOE-004-moe-training-run.md)
- Training script: [docs/research/train_gemma4_moe.py](../../docs/research/train_gemma4_moe.py)

## Suggested Workflow

```
1. /task-review TASK-REV-G4R1           — analyse and recommend fix
2. Implement fix on GB10 (manual)       — update Step 3 installs, re-run Step 4
3. /task-complete TASK-REV-G4R1         — once sanity run passes
```
