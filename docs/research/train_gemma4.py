#!/usr/bin/env python3
"""
train_gemma4.py — Fine-tune Gemma 4 31B on GCSE tutor dataset
=============================================================
Target hardware: Dell DGX Spark GB10 (128GB unified memory)
Framework:       Unsloth + TRL SFTTrainer
Input:           /workspace/data/train.jsonl (ShareGPT format)
Output:          /workspace/output/gcse-tutor-gemma4-31b/ (merged 16-bit + GGUF)

Usage inside Docker:
    python train_gemma4.py                          # Full training run
    python train_gemma4.py --max-steps 60           # Quick validation run
    python train_gemma4.py --resume                 # Resume from checkpoint

Environment variables (optional):
    HF_TOKEN            Hugging Face token for gated model access
    WANDB_API_KEY       Weights & Biases key (set --report-to wandb)
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


# ---------------------------------------------------------------------------
# Configuration defaults
# ---------------------------------------------------------------------------
DEFAULTS = {
    "model_name": "unsloth/gemma-4-31B-it",
    "max_seq_length": 8192,
    "load_in_4bit": True,           # QLoRA — uses ~22GB on GB10
    "lora_r": 8,
    "lora_alpha": 8,
    "learning_rate": 2e-4,          # Reduce to 2e-5 for longer runs
    "batch_size": 1,
    "gradient_accumulation": 4,     # Effective batch = 4
    "warmup_steps": 10,
    "max_steps": None,              # None = full epochs
    "num_epochs": 1,
    "logging_steps": 1,
    "save_steps": 100,
    "output_dir": "/workspace/output/gcse-tutor-gemma4-31b",
    "data_path": "/workspace/data/train.jsonl",
    "chat_template": "gemma-4-thinking",  # Preserves <think> blocks
    "report_to": "none",
}


def parse_args():
    p = argparse.ArgumentParser(description="Fine-tune Gemma 4 31B for GCSE tutor")
    p.add_argument("--model-name", default=DEFAULTS["model_name"])
    p.add_argument("--max-seq-length", type=int, default=DEFAULTS["max_seq_length"])
    p.add_argument("--no-4bit", action="store_true",
                   help="Use 16-bit LoRA instead of QLoRA (needs more memory)")
    p.add_argument("--lora-r", type=int, default=DEFAULTS["lora_r"])
    p.add_argument("--lora-alpha", type=int, default=DEFAULTS["lora_alpha"])
    p.add_argument("--lr", type=float, default=DEFAULTS["learning_rate"])
    p.add_argument("--batch-size", type=int, default=DEFAULTS["batch_size"])
    p.add_argument("--grad-accum", type=int, default=DEFAULTS["gradient_accumulation"])
    p.add_argument("--max-steps", type=int, default=DEFAULTS["max_steps"],
                   help="Override num_epochs; set to 60 for a quick test")
    p.add_argument("--epochs", type=int, default=DEFAULTS["num_epochs"])
    p.add_argument("--data-path", default=DEFAULTS["data_path"])
    p.add_argument("--output-dir", default=DEFAULTS["output_dir"])
    p.add_argument("--chat-template", default=DEFAULTS["chat_template"],
                   choices=["gemma-4-thinking", "gemma-4"],
                   help="gemma-4-thinking preserves <think> blocks (use this)")
    p.add_argument("--report-to", default=DEFAULTS["report_to"],
                   choices=["none", "wandb", "tensorboard"])
    p.add_argument("--resume", action="store_true",
                   help="Resume training from last checkpoint")
    p.add_argument("--skip-export", action="store_true",
                   help="Skip GGUF export after training")
    return p.parse_args()


# ---------------------------------------------------------------------------
# Dataset loading
# ---------------------------------------------------------------------------
def load_sharegpt_jsonl(path: str) -> Dataset:
    """Load ShareGPT-format JSONL as a HuggingFace Dataset.
    
    Expected format per line:
    {"messages": [{"role": "system"|"user"|"assistant", "content": "..."}], ...}
    
    The dataset factory outputs this format. Any extra metadata fields
    (layer, type, topic, etc.) are preserved but ignored by the trainer.
    """
    records = []
    first_line_keys = None
    with open(path, "r") as f:
        for i, line in enumerate(f):
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError as e:
                print(f"WARNING: Skipping malformed line {i+1}: {e}")
                continue

            if first_line_keys is None:
                first_line_keys = list(obj.keys())
                print(f"  First record keys: {first_line_keys}")
                first_msg = (obj.get("messages") or obj.get("conversations") or obj.get("conversation") or [None])[0]
                if first_msg:
                    print(f"  First message keys: {list(first_msg.keys())}")

            # Support multiple ShareGPT format variants:
            #   Modern:  {"messages": [{"role": "user", "content": "..."}]}
            #   Classic: {"conversations": [{"from": "human", "value": "..."}]}
            #   Also:    {"messages": [{"from": "human", "value": "..."}]}
            messages = (
                obj.get("messages")
                or obj.get("conversations")
                or obj.get("conversation")
                or []
            )
            if not messages:
                print(f"WARNING: Skipping line {i+1}: no messages/conversations field")
                continue

            # Normalise role names and key names for Gemma 4 compatibility
            conversations = []
            for msg in messages:
                # Handle both "role"/"content" and "from"/"value" key styles
                role = msg.get("role") or msg.get("from", "")
                content = msg.get("content") or msg.get("value", "")

                # Normalise role names
                if role in ("gpt", "bot", "model"):
                    role = "assistant"
                elif role in ("human",):
                    role = "user"

                if not role or not content:
                    print(f"WARNING: Skipping empty message in line {i+1}: {msg}")
                    continue

                conversations.append({"role": role, "content": content})

            records.append({"conversations": conversations})

    if not records:
        print(f"ERROR: No valid records found in {path}")
        sys.exit(1)

    print(f"Loaded {len(records)} training examples from {path}")

    # Show first record's structure for debugging
    first = records[0]["conversations"]
    print(f"  First example: {len(first)} turns, roles: {[m['role'] for m in first]}")
    print(f"  First user msg (truncated): {first[0]['content'][:120]}...")

    return Dataset.from_list(records)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    args = parse_args()

    # -----------------------------------------------------------------------
    # 1. Load model
    # -----------------------------------------------------------------------
    print(f"\n{'='*60}")
    print(f"Loading {args.model_name}")
    print(f"  QLoRA 4-bit: {not args.no_4bit}")
    print(f"  Max sequence length: {args.max_seq_length}")
    print(f"{'='*60}\n")

    model, tokenizer = FastModel.from_pretrained(
        model_name=args.model_name,
        max_seq_length=args.max_seq_length,
        dtype=None,                         # Auto-detect
        load_in_4bit=not args.no_4bit,
        full_finetuning=False,
        use_gradient_checkpointing="unsloth",  # Critical for memory
        # token=os.environ.get("HF_TOKEN"),  # Uncomment if needed
    )

    # -----------------------------------------------------------------------
    # 2. Attach LoRA adapters
    # -----------------------------------------------------------------------
    model = FastModel.get_peft_model(
        model,
        finetune_vision_layers=False,       # Text-only fine-tune
        finetune_language_layers=True,
        finetune_attention_modules=True,
        finetune_mlp_modules=True,
        r=args.lora_r,
        lora_alpha=args.lora_alpha,
        lora_dropout=0,
        bias="none",
        random_state=3407,
    )

    # -----------------------------------------------------------------------
    # 3. Apply Gemma 4 chat template
    # -----------------------------------------------------------------------
    tokenizer = get_chat_template(
        tokenizer,
        chat_template=args.chat_template,
    )
    print(f"Chat template: {args.chat_template}")

    # -----------------------------------------------------------------------
    # 4. Load and format dataset
    # -----------------------------------------------------------------------
    dataset = load_sharegpt_jsonl(args.data_path)

    # Standardise any format variations
    dataset = standardize_data_formats(dataset)

    # Apply Gemma 4 chat template to each conversation
    # Remove <bos> prefix — the processor adds it during training
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

    # Quick sanity check
    print(f"\n--- Sample formatted text (first 500 chars) ---")
    print(dataset[0]["text"][:500])
    print(f"--- End sample ---\n")

    # -----------------------------------------------------------------------
    # 5. Configure trainer
    # -----------------------------------------------------------------------
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
        model=model,
        tokenizer=tokenizer,
        train_dataset=dataset,
        eval_dataset=None,
        args=training_args,
    )

    # Only train on assistant responses, not user prompts
    trainer = train_on_responses_only(
        trainer,
        instruction_part="<|turn>user\n",
        response_part="<|turn>model\n",
    )

    # Verify masking is working
    print("Verifying response-only masking...")
    sample_labels = trainer.train_dataset[0]["labels"]
    masked_count = sum(1 for x in sample_labels if x == -100)
    total_count = len(sample_labels)
    print(f"  Masked tokens: {masked_count}/{total_count} "
          f"({100*masked_count/total_count:.1f}% masked)")

    # -----------------------------------------------------------------------
    # 6. Train
    # -----------------------------------------------------------------------
    print(f"\n{'='*60}")
    print("Starting training...")
    if args.max_steps and args.max_steps > 0:
        print(f"  Max steps: {args.max_steps}")
    else:
        print(f"  Epochs: {args.epochs}")
    print(f"  Effective batch size: {args.batch_size * args.grad_accum}")
    print(f"  Learning rate: {args.lr}")
    print(f"  Output: {args.output_dir}")
    print(f"{'='*60}\n")

    trainer_stats = trainer.train(
        resume_from_checkpoint=args.resume
    )

    print(f"\nTraining complete!")
    print(f"  Total steps: {trainer_stats.global_step}")
    print(f"  Final loss: {trainer_stats.training_loss:.4f}")

    # -----------------------------------------------------------------------
    # 7. Save model
    # -----------------------------------------------------------------------
    lora_dir = os.path.join(args.output_dir, "lora-adapter")
    merged_dir = os.path.join(args.output_dir, "merged-16bit")
    gguf_dir = os.path.join(args.output_dir, "gguf")

    # Save LoRA adapter (small, fast)
    print(f"\nSaving LoRA adapter to {lora_dir}...")
    model.save_pretrained(lora_dir)
    tokenizer.save_pretrained(lora_dir)

    # Save merged 16-bit model (for vLLM serving)
    print(f"Saving merged 16-bit model to {merged_dir}...")
    model.save_pretrained_merged(merged_dir, tokenizer, save_method="merged_16bit")

    # Export to GGUF (for llama.cpp / Ollama)
    if not args.skip_export:
        print(f"Exporting GGUF to {gguf_dir}...")
        os.makedirs(gguf_dir, exist_ok=True)
        try:
            model.save_pretrained_gguf(
                gguf_dir, tokenizer, quantization_method="q4_k_m"
            )
            print("  Exported: q4_k_m")
        except Exception as e:
            print(f"  GGUF export failed (non-fatal): {e}")
            print("  You can export manually later from the merged model.")

    print(f"\n{'='*60}")
    print("All done! Next steps:")
    print(f"  1. Test with vLLM:  vllm serve {merged_dir}")
    print(f"  2. Or use GGUF:     ls {gguf_dir}/")
    print(f"  3. LoRA adapter:    {lora_dir}/")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
