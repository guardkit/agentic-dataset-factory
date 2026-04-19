---
id: TASK-G4MOE-002
title: Create train_gemma4_moe.py configured for 26B A4B MoE
status: completed
created: 2026-04-15T00:00:00Z
updated: 2026-04-15T00:00:00Z
priority: high
tags: [fine-tuning, gemma4, moe, unsloth]
complexity: 3
parent_review: TASK-REV-G4MOE
feature_id: FEAT-G4MOE
wave: 1
implementation_mode: task-work
dependencies: [TASK-G4MOE-001]
---

# Task: Create train_gemma4_moe.py configured for 26B A4B MoE

## Description

Create `docs/research/train_gemma4_moe.py` as a sibling to `train_gemma4_dense.py` (produced by TASK-G4MOE-001). Start from a copy of the Dense script and apply the MoE-specific configuration changes required by Unsloth's first-party fine-tuning guide for `unsloth/Gemma-4-26B-A4B-it`.

**Critical**: do not try to "parameterise" the two scripts into one with a flag. Keep them as siblings so each tier remains a single-file reproducible artifact. If the dense script is lost or archived, the MoE script must still run standalone, and vice versa.

## Required config changes (relative to the dense script)

From the Unsloth docs (https://unsloth.ai/docs/models/gemma-4/train) and review §4 / §8.1:

### `DEFAULTS` dict (around line 40 of the dense copy)

```python
DEFAULTS = {
    "model_name": "unsloth/Gemma-4-26B-A4B-it",   # was: "unsloth/gemma-4-31B-it"
    "max_seq_length": 4096,                        # was: 8192 — Unsloth MoE starting point
    "load_in_4bit": False,                         # was: True — MoE QLoRA not recommended
    "load_in_16bit": True,                         # NEW — bf16 LoRA for MoE
    "lora_r": 16,                                  # was: 8 — Unsloth MoE guidance
    "lora_alpha": 16,                              # was: 8 — match lora_r
    "learning_rate": 2e-4,                         # unchanged
    "batch_size": 1,                               # unchanged
    "gradient_accumulation": 4,                    # unchanged
    "warmup_steps": 10,                            # unchanged
    "max_steps": None,                             # unchanged
    "num_epochs": 1,                               # unchanged
    "logging_steps": 1,                            # unchanged
    "save_steps": 100,                             # unchanged
    "output_dir": "/workspace/output/gcse-tutor-gemma4-26b-moe",  # was: gcse-tutor-gemma4-31b
    "data_path": "/workspace/data/train.jsonl",    # unchanged
    "chat_template": "gemma-4-thinking",           # unchanged
    "report_to": "none",                           # unchanged
}
```

### `FastModel.from_pretrained` call (around line 194 of the dense copy)

Add `load_in_16bit=True` alongside `load_in_4bit`:

```python
model, tokenizer = FastModel.from_pretrained(
    model_name=args.model_name,
    max_seq_length=args.max_seq_length,
    dtype=None,
    load_in_4bit=not args.no_4bit,   # defaults to False for MoE
    load_in_16bit=True,               # NEW — required for MoE
    full_finetuning=False,
    use_gradient_checkpointing="unsloth",
    attn_implementation="sdpa",
)
```

### CLI arg parser

- Keep `--no-4bit` as a legacy flag (semantics: force dense-style QLoRA, not recommended for MoE — but wired for completeness)
- Add `--load-in-16bit` / `--no-16bit` pair, defaulting to `load-in-16bit`
- Validate that `--no-4bit` and `--no-16bit` are not both set simultaneously (exit with error)

### Top-of-file docstring

Rewrite the module docstring to clearly say:

```
train_gemma4_moe.py — Fine-tune Gemma 4 26B A4B MoE on GCSE tutor dataset
=========================================================================
Target hardware: Dell DGX Spark GB10 (128 GB unified memory)
Framework:       Unsloth + TRL SFTTrainer
Model:           unsloth/Gemma-4-26B-A4B-it (Mixture-of-Experts)
Quantisation:    16-bit LoRA (MoE QLoRA unsupported — bitsandbytes cannot
                 quantise Gemma 4's 3D fused expert tensors)
Memory:          ~48 GB during training (vs ~22 GB for Dense QLoRA 4-bit)
Router layers:   handled automatically by Unsloth — no manual freezing
```

### Code comments for the load_in_16bit line

Add a short comment at the `DEFAULTS` entry explaining the why:

```python
"load_in_16bit": True,  # MoE path. QLoRA 4-bit blocked by bitsandbytes
                         # on Gemma 4's 3D fused expert tensors. Unsloth
                         # recommends 16-bit LoRA for Gemma-4-26B-A4B.
```

## Scope

- [ ] `cp docs/research/train_gemma4_dense.py docs/research/train_gemma4_moe.py`
- [ ] Apply the `DEFAULTS` changes above
- [ ] Apply the `FastModel.from_pretrained` change
- [ ] Add/update CLI flags
- [ ] Rewrite top-of-file docstring
- [ ] Run `python docs/research/train_gemma4_moe.py --help` locally and confirm it parses
- [ ] Run `ruff check docs/research/train_gemma4_moe.py` (if ruff is configured for this repo)
- [ ] Add `--moe` or similar suffix to the output-dir arg help text so operators don't collide with Dense outputs on disk

## Acceptance Criteria

- [ ] `docs/research/train_gemma4_moe.py` exists and `--help` runs
- [ ] `DEFAULTS["model_name"]` is `"unsloth/Gemma-4-26B-A4B-it"`
- [ ] `DEFAULTS["load_in_4bit"]` is `False`
- [ ] `DEFAULTS["load_in_16bit"]` is `True`
- [ ] `DEFAULTS["lora_r"]` is `16`
- [ ] `DEFAULTS["output_dir"]` ends in `gcse-tutor-gemma4-26b-moe`
- [ ] `FastModel.from_pretrained(..., load_in_16bit=True, ...)` is present in the main() body
- [ ] Top-of-file docstring names the MoE variant and memory expectations
- [ ] The `train_on_responses_only` instruction/response markers (`<|turn>user\n` / `<|turn>model\n`) are unchanged — Gemma 4 chat template is the same for both variants
- [ ] `train_gemma4_dense.py` is untouched by this task

## Notes

- **Do not try to run this on GB10 as part of this task.** That is TASK-G4MOE-004. This task only produces a working script.
- **Do not import anything from `train_gemma4_dense.py`.** Siblings, not inheritance.
- **Do not delete `train_gemma4_dense.py`.** Sunk-cost preservation per review §7.2.
- The Unsloth MoE loader example uses `max_seq_length = 2048` as a conservative starting point. We're starting at `4096` because our ShareGPT records regularly exceed 2048 tokens — Unsloth says "start short and scale up after pipeline stability", and 4096 is a sensible midpoint. If the training run hangs or OOMs, fall back to 2048 (TASK-G4MOE-004 will flag this).
