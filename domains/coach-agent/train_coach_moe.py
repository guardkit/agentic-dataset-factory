#!/usr/bin/env python3
"""
train_coach_moe.py — Fine-tune the Coach LoRA on Gemma-4-26B-A4B MoE
====================================================================
Forked from the validated `train_gemma4_moe.py` (architect/GCSE recipe) with the deltas
mandated by the adversarially-verified QAT research (see RESEARCH-gemma4-qat-decision.md):

  * BASE UNCHANGED — `unsloth/gemma-4-26B-A4B-it` (bf16). The QAT base swap was REFUTED:
    `qat-q4_0-unquantized` is "for research/compilation", and Q4_0-from-QAT collapses to
    70.2% top-1 on 26B-A4B (vs 85.6% for UD-Q4_K_XL). Nothing about QAT changes training.
  * TEMPLATE `gemma-4` (NON-thinking), not `gemma-4-thinking`. The Coach emits a fenced
    ```json verdict, not <think> reasoning. (Adversarially SUPPORTED.)
  * SEQ 6144 default — the Coach corpus is completion-heavy. Real gemma4-tokenizer measurement
    (2026-06-19): 3.50 chars/token, seq p99~6447, max~7215. 6144 covers 98% of verdicts intact;
    4096 truncates 27%; 8192 covers 100% but is GB10-memory-risky. Smoke-test peak memory; if
    6144 runs hot, fall back to 4096 + prepare_coach_sft.py --max-completion-tokens 3200.
  * GGUF export `q4_k_m` (NEVER q4_0; q4_k_m is the pragmatic stand-in for UD-Q4_K_XL,
    which `save_pretrained_gguf` cannot emit via flag — build it with llama.cpp if needed).

Baked-in smoke guards (abort cheaply, before the full run wastes ~71 min):
  [G1] trainable-% guard — PR #4913: experts (`experts.gate_up_proj/down_proj`) must attach.
       Aborts if trainable% < --min-trainable-pct (default 1.0) unless --allow-low-trainable.
  [G2] template render check — prints the first rendered example, asserts Gemma-4 turn
       markers, and reports whether the empty `<|channel>thought\n<channel|>` block precedes
       the JSON (train==serve alignment for the 26B-A4B non-thinking path).
  [G3] sdpa check — FA2 is unsupported (head_dim 512 > 256); warns if not sdpa.
  [G4] masking sanity — prints masked %% from train_on_responses_only.
  [G5] peak-memory print — torch.cuda.max_memory_allocated (GB10 freeze watch).

Target hardware: Dell DGX Spark GB10 (121 GB unified memory).
Container:       nvcr.io/nvidia/pytorch:25.11-py3  (deps per RUNBOOK-coach-fine-tune.md)
Input:           ShareGPT JSONL from prepare_coach_sft.py (default /workspace/data/train-coach.jsonl)
Output:          /workspace/output/coach-gemma4-26b-moe/ (lora-adapter + merged-16bit + gguf)

Usage inside the container:
    python train_coach_moe.py --max-steps 60 --skip-export      # smoke (~14 min)
    python train_coach_moe.py                                   # full run (~71 min)
"""

import argparse
import json
import os
import sys
from pathlib import Path

import torch
from datasets import Dataset
from unsloth import FastModel
from unsloth.chat_templates import (
    get_chat_template,
    standardize_data_formats,
    train_on_responses_only,
)
from trl import SFTTrainer, SFTConfig


DEFAULTS = {
    "model_name": "unsloth/gemma-4-26B-A4B-it",   # bf16 base — QAT swap REFUTED
    "max_seq_length": 4096,                       # PRACTICAL GB10 ceiling: seq>=6144 OOM-climbs
                                                  # over the epoch (alloc high-water grows ~6GB/40
                                                  # steps -> 112-114GB, watchdog-killed; even
                                                  # expandable_segments only shifts ~5GB). 4096
                                                  # completes (~75-85GB). Verdicts are long
                                                  # (p99~6447 tok) so pair with prepare's
                                                  # --max-completion-tokens to cut truncation.
    "lora_r": 16,
    "lora_alpha": 16,
    "learning_rate": 2e-4,
    "batch_size": 1,
    "gradient_accumulation": 4,
    "warmup_steps": 10,
    "num_epochs": 1,
    "logging_steps": 1,
    "save_steps": 100,
    "output_dir": "/workspace/output/coach-gemma4-26b-moe",
    "data_path": "/workspace/data/train-coach.jsonl",
    "chat_template": "gemma-4",                    # NON-thinking (Coach emits JSON, not <think>)
    "gguf_quant": "q4_k_m",                        # NEVER q4_0; stand-in for UD-Q4_K_XL
    "report_to": "none",
}


def parse_args():
    p = argparse.ArgumentParser(description="Fine-tune the Coach LoRA on Gemma-4-26B-A4B MoE")
    p.add_argument("--model-name", default=DEFAULTS["model_name"])
    p.add_argument("--max-seq-length", type=int, default=DEFAULTS["max_seq_length"])
    p.add_argument("--lora-r", type=int, default=DEFAULTS["lora_r"])
    p.add_argument("--lora-alpha", type=int, default=DEFAULTS["lora_alpha"])
    p.add_argument("--lr", type=float, default=DEFAULTS["learning_rate"])
    p.add_argument("--batch-size", type=int, default=DEFAULTS["batch_size"])
    p.add_argument("--grad-accum", type=int, default=DEFAULTS["gradient_accumulation"])
    p.add_argument("--warmup-steps", type=int, default=DEFAULTS["warmup_steps"])
    p.add_argument("--max-steps", type=int, default=None,
                   help="Override epochs; set 60 for the smoke run")
    p.add_argument("--epochs", type=int, default=DEFAULTS["num_epochs"])
    p.add_argument("--logging-steps", type=int, default=DEFAULTS["logging_steps"])
    p.add_argument("--save-steps", type=int, default=DEFAULTS["save_steps"])
    p.add_argument("--data-path", default=DEFAULTS["data_path"])
    p.add_argument("--output-dir", default=DEFAULTS["output_dir"])
    p.add_argument("--chat-template", default=DEFAULTS["chat_template"],
                   choices=["gemma-4", "gemma-4-thinking"],
                   help="gemma-4 (non-thinking) is correct for the JSON Coach")
    p.add_argument("--gguf-quant", default=DEFAULTS["gguf_quant"],
                   choices=["q4_k_m", "q8_0", "f16"],
                   help="save_pretrained_gguf only supports these. q4_k_m ~ UD-Q4_K_XL; "
                        "NEVER q4_0 (collapses 26B-A4B to 70.2%% top-1)")
    p.add_argument("--report-to", default=DEFAULTS["report_to"],
                   choices=["none", "wandb", "tensorboard"])
    p.add_argument("--min-trainable-pct", type=float, default=1.0,
                   help="[G1] Abort if trainable%% is below this (PR #4913 expert-attach guard)")
    p.add_argument("--allow-low-trainable", action="store_true",
                   help="Bypass the [G1] trainable-%% abort (NOT recommended)")
    p.add_argument("--resume", action="store_true")
    p.add_argument("--skip-export", action="store_true")
    return p.parse_args()


# ---------------------------------------------------------------------------
# Dataset loading (ShareGPT) — same contract as the shared recipe
# ---------------------------------------------------------------------------
def load_sharegpt_jsonl(path: str) -> Dataset:
    records = []
    with open(path) as f:
        for i, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError as e:
                print(f"WARNING: skipping malformed line {i}: {e}")
                continue
            messages = obj.get("messages") or obj.get("conversations") or []
            conversations = []
            for msg in messages:
                cleaned = {k.strip(): v for k, v in msg.items()}
                role = cleaned.get("role") or cleaned.get("from", "")
                content = cleaned.get("content") or cleaned.get("value", "")
                if role in ("gpt", "bot", "model"):
                    role = "assistant"
                elif role == "human":
                    role = "user"
                if not role or not content:
                    continue
                conversations.append({"role": role, "content": content})
            if conversations:
                records.append({"conversations": conversations})
    if not records:
        sys.exit(f"ERROR: no valid records in {path}")
    print(f"Loaded {len(records)} training examples from {path}")
    roles = [m["role"] for m in records[0]["conversations"]]
    print(f"  First example roles: {roles}")
    return Dataset.from_list(records)


def main():
    args = parse_args()

    # 1. Load model -----------------------------------------------------------
    print(f"\n{'='*64}\nLoading {args.model_name}\n"
          f"  16-bit LoRA: True | 4-bit: False (MoE QLoRA blocked) | "
          f"seq: {args.max_seq_length}\n{'='*64}\n")
    model, tokenizer = FastModel.from_pretrained(
        model_name=args.model_name,
        max_seq_length=args.max_seq_length,
        dtype=None,
        load_in_4bit=False,         # MoE QLoRA blocked (3D fused expert tensors)
        load_in_16bit=True,
        full_finetuning=False,
        use_gradient_checkpointing="unsloth",
        attn_implementation="sdpa",  # FA2 unsupported: head_dim 512 > 256
    )

    # [G3] sdpa check
    impl = getattr(getattr(model, "config", None), "_attn_implementation", "unknown")
    if impl and "flash" in str(impl).lower():
        print(f"WARNING [G3]: attn_implementation={impl} — expected sdpa; FA2 will crash "
              f"on Gemma 4's head_dim=512 global layers.")
    else:
        print(f"[G3] attention implementation: {impl}")

    # 2. LoRA -----------------------------------------------------------------
    # PEFT torchao version-gate workaround (TASK-REV-G4R1) — we don't use torchao.
    import peft.import_utils
    import peft.tuners.lora.torchao
    peft.import_utils.is_torchao_available = lambda: False
    peft.tuners.lora.torchao.is_torchao_available = lambda: False

    model = FastModel.get_peft_model(
        model,
        finetune_vision_layers=False,
        finetune_language_layers=True,
        finetune_attention_modules=True,
        finetune_mlp_modules=True,
        r=args.lora_r,
        lora_alpha=args.lora_alpha,
        lora_dropout=0,
        bias="none",
        random_state=3407,
    )

    # [G1] trainable-% guard (PR #4913: experts must actually attach)
    trainable = sum(p.numel() for p in model.parameters() if p.requires_grad)
    total = sum(p.numel() for p in model.parameters())
    pct = 100 * trainable / max(total, 1)
    print(f"[G1] Trainable params: {trainable:,} / {total:,} ({pct:.2f}%)")
    if pct < args.min_trainable_pct and not args.allow_low_trainable:
        sys.exit(
            f"\nABORT [G1]: trainable% {pct:.2f} < {args.min_trainable_pct} — the MoE expert "
            f"LoRA almost certainly did NOT attach (Unsloth issue #4907, fixed in PR #4913, "
            f"merged 2026-04-14). Expected ~1.88%. Upgrade Unsloth to a post-PR-4913 build, or "
            f"pass --allow-low-trainable to override (NOT recommended).\n")

    # 3. Chat template --------------------------------------------------------
    tokenizer = get_chat_template(tokenizer, chat_template=args.chat_template)
    print(f"Chat template: {args.chat_template}")

    # 4. Dataset --------------------------------------------------------------
    dataset = load_sharegpt_jsonl(args.data_path)
    dataset = standardize_data_formats(dataset)

    def formatting_prompts_func(examples):
        convos = examples["conversations"]
        texts = [
            tokenizer.apply_chat_template(
                convo, tokenize=False, add_generation_prompt=False
            ).removeprefix("<bos>")
            for convo in convos
        ]
        return {"text": texts}

    dataset = dataset.map(formatting_prompts_func, batched=True)

    # [G2] template render check — verify train==serve framing for 26B-A4B
    sample = dataset[0]["text"]
    print(f"\n--- [G2] first rendered example (first 700 chars) ---\n{sample[:700]}\n--- end ---")
    have_user = "<|turn>user" in sample
    have_model = "<|turn>model" in sample
    have_thought = "<|channel>thought" in sample
    print(f"[G2] markers: <|turn>user={have_user}  <|turn>model={have_model}  "
          f"empty-thought-block={have_thought}")
    if not (have_user and have_model):
        print("WARNING [G2]: Gemma-4 turn markers missing — train_on_responses_only masking "
              "and serve-time alignment will break. Check the chat-template name/version.")
    if not have_thought:
        print("NOTE [G2]: no '<|channel>thought' block in the rendered ASSISTANT turn. The 26B-A4B "
              "non-thinking path still injects an empty thought block at SERVE time via "
              "add_generation_prompt. If serve != train here, the JSON position differs — verify "
              "with the export+grammar-serve round-trip (RUNBOOK smoke-test #7) before trusting.")

    # 5. Trainer --------------------------------------------------------------
    training_args = SFTConfig(
        dataset_text_field="text",
        per_device_train_batch_size=args.batch_size,
        gradient_accumulation_steps=args.grad_accum,
        warmup_steps=args.warmup_steps,
        num_train_epochs=args.epochs if args.max_steps is None else 1,
        max_steps=args.max_steps if args.max_steps else -1,
        learning_rate=args.lr,
        logging_steps=args.logging_steps,
        save_steps=args.save_steps,
        save_strategy="steps",
        optim="adamw_8bit",
        weight_decay=0.001,
        lr_scheduler_type="linear",
        seed=3407,
        output_dir=args.output_dir,
        report_to=args.report_to,
        fp16=not torch.cuda.is_bf16_supported(),
        bf16=torch.cuda.is_bf16_supported(),
    )
    trainer = SFTTrainer(
        model=model, tokenizer=tokenizer, train_dataset=dataset,
        eval_dataset=None, args=training_args,
    )
    trainer = train_on_responses_only(
        trainer,
        instruction_part="<|turn>user\n",
        response_part="<|turn>model\n",
    )

    # [G4] masking sanity
    labels = trainer.train_dataset[0]["labels"]
    masked = sum(1 for x in labels if x == -100)
    print(f"[G4] response-only masking: {masked}/{len(labels)} masked "
          f"({100*masked/len(labels):.1f}%). The Coach verdict is the LARGER, trained part, so "
          f"expect a MODERATE masked%% (the prompt; ~29%% observed, like architect's 27.7%%). "
          f"~0%% or ~100%% means the markers are wrong — STOP.")

    # 6. Train ----------------------------------------------------------------
    print(f"\n{'='*64}\nStarting training | eff.batch {args.batch_size*args.grad_accum} | "
          f"lr {args.lr} | {'steps '+str(args.max_steps) if args.max_steps else 'epochs '+str(args.epochs)}\n{'='*64}\n")
    stats = trainer.train(resume_from_checkpoint=args.resume)
    print(f"\nTraining complete. steps={stats.global_step} loss={stats.training_loss:.4f}")

    # [G5] peak memory (GB10 freeze watch)
    if torch.cuda.is_available():
        print(f"[G5] peak GPU memory: {torch.cuda.max_memory_allocated()/1e9:.1f} GB "
              f"(GB10 freeze watch — keep well under ~100 GB)")

    # 7. Save -----------------------------------------------------------------
    lora_dir = os.path.join(args.output_dir, "lora-adapter")
    merged_dir = os.path.join(args.output_dir, "merged-16bit")
    gguf_dir = os.path.join(args.output_dir, "gguf")

    print(f"\nSaving LoRA adapter -> {lora_dir}")
    model.save_pretrained(lora_dir)
    tokenizer.save_pretrained(lora_dir)

    print(f"Saving merged 16-bit -> {merged_dir}")
    model.save_pretrained_merged(merged_dir, tokenizer, save_method="merged_16bit")

    if not args.skip_export:
        print(f"Exporting GGUF ({args.gguf_quant}) -> {gguf_dir}")
        os.makedirs(gguf_dir, exist_ok=True)
        try:
            model.save_pretrained_gguf(
                gguf_dir, tokenizer, quantization_method=args.gguf_quant)
            print(f"  Exported: {args.gguf_quant}")
            print("  NOTE: for best int4 serving quality build true UD-Q4_K_XL with llama.cpp "
                  "`quantize` + Unsloth's imatrix (q4_k_m here is the pragmatic stand-in; "
                  "NEVER q4_0). See RESEARCH-gemma4-qat-decision.md §3.")
        except Exception as e:
            print(f"  GGUF export failed (non-fatal): {e}\n  Export manually from {merged_dir}.")

    print(f"\n{'='*64}\nDone. Next: eval_coach.py against holdout (RUNBOOK Phase 5).\n{'='*64}\n")


if __name__ == "__main__":
    main()
