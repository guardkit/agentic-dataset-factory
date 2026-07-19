#!/usr/bin/env python3
"""
train_dcl_qwen3.py — Fine-tune the DCL LoRA on Qwen3-4B-Instruct-2507 (dense QLoRA)
==================================================================================
The DCL pilot fine-tune (Rich's go, 2026-07-19: "get it done now"). Trains a
capability-language author/repair LoRA on **Qwen/Qwen3-4B-Instruct-2507** (Apache-2.0,
DENSE, non-thinking instruct) via Unsloth + TRL inside the NVIDIA PyTorch container, from
the staged corpus produced by ``prepare_dcl_sft.py`` (staged OUTSIDE the repo under
``~/fine-tuning/data/`` — never committed; the corpus is private under DF-008).

Adapted from the proven MoE recipe (``../coach-agent/train_coach_moe.py`` and
``../../docs/research/train_gemma4_moe.py``). Deltas for this DENSE 4B base:

  * BASE = ``Qwen/Qwen3-4B-Instruct-2507`` loaded with ``load_in_4bit=True`` (QLoRA — a
    dense 4B quantises cleanly, unlike the 26B MoE which had to run 16-bit LoRA).
  * CHAT TEMPLATE = Qwen3's NATIVE tokenizer template (``<|im_start|>role\\n...<|im_end|>``).
    We do NOT apply a gemma chat template. This OVERRIDES the OUTPUT-CONTRACT.md line naming
    ``gemma-4`` — the base changed to Qwen3 on 2026-07-19 probe evidence
    (COMPARISON-2026-07-19.md: stock protocol 2/9 + perfect 3/3 repair = the trainable
    profile). OUTPUT-CONTRACT.md is left unedited; the deviation is recorded here and in the
    staging manifest.
  * ``train_on_responses_only`` masks on the Qwen markers ``<|im_start|>user\\n`` /
    ``<|im_start|>assistant\\n`` (not the gemma ``<|turn>`` markers).
  * LoRA r=16, alpha=32, dropout 0, targets q/k/v/o + gate/up/down (dense attention+MLP).
  * 2 epochs (small-corpus pilot: 507 unique rows, ~528 staged train at K=2 — a single epoch
    under-fits a corpus this small; 2 keeps it from memorising while still moving first-attempt
    quality). Row floor 507 is BELOW the architect runbook's 1500 MIN_ACCEPTED — deliberate,
    Rich-approved for a pilot (recorded, not hidden).

Rows are trained AS-IS. Repair rows carry a ``<think>...</think>`` prefix in the assistant
turn (374/415 in the repair set); author rows are direct. Both are kept verbatim.

Target hardware: Dell DGX Spark GB10 (`promaxgb10-41b1`), 121 GB unified memory.
Container:       nvcr.io/nvidia/pytorch:25.11-py3
Deps (inside container — pins from RUNBOOK-coach-fine-tune.md §3.3):
    pip install transformers==5.5.4 peft hf_transfer "datasets==4.3.0" "trl==0.26.1" "accelerate==1.10.0"
    pip install --no-deps unsloth unsloth_zoo bitsandbytes

Input:   ShareGPT JSONL from prepare_dcl_sft.py (default /workspace/data/train-dcl.jsonl,
         eval /workspace/data/eval-dcl.jsonl — eval is loss-only, skipped cleanly if absent).
Output:  /workspace/output/dcl-qwen3-4b/ (lora-adapter + merged-16bit + gguf q4_k_m).

Usage inside the container:
    python train_dcl_qwen3.py --output-dir /workspace/output/dcl-qwen3-4b-smoke \\
        --max-steps 40 --skip-export                        # smoke
    python train_dcl_qwen3.py --output-dir /workspace/output/dcl-qwen3-4b   # full run

Heavy ML imports (unsloth/torch/trl/transformers/datasets) are DEFERRED into functions so
that on the host (no GPU deps installed) ``python3 -m py_compile`` and ``--help`` both work.
"""

from __future__ import annotations

import argparse
import os
import sys


DEFAULTS = {
    "model_name": "Qwen/Qwen3-4B-Instruct-2507",   # Apache-2.0 dense non-thinking instruct
    "max_seq_length": 8192,                         # a 4B at QLoRA affords it (staging audit
                                                    # recommends; overridable). The DCL user
                                                    # turns embed the vocab reference (~12.5KB)
                                                    # so rows are prompt-heavy — 8192 covers p99.
    "lora_r": 16,
    "lora_alpha": 32,
    "lora_dropout": 0.0,
    "learning_rate": 2e-4,
    "batch_size": 1,
    "gradient_accumulation": 4,
    "warmup_ratio": 0.03,
    "num_epochs": 2,                                # small-corpus pilot (see module docstring)
    "logging_steps": 1,
    "output_dir": None,                             # REQUIRED
    "data_path": "/workspace/data/train-dcl.jsonl",
    "eval_path": "/workspace/data/eval-dcl.jsonl",
    "gguf_quant": "q4_k_m",
    "report_to": "none",
    "seed": 3407,
}

# Dense LoRA target modules — attention (q,k,v,o) + MLP (gate,up,down).
TARGET_MODULES = ["q_proj", "k_proj", "v_proj", "o_proj",
                  "gate_proj", "up_proj", "down_proj"]

# Qwen3 native chat-template markers (train == serve alignment).
INSTRUCTION_PART = "<|im_start|>user\n"
RESPONSE_PART = "<|im_start|>assistant\n"

# Tokens that must NOT appear in a Qwen3-rendered example — their presence means a gemma
# template leaked in (wrong template applied). [G2] aborts on any of these.
GEMMA_LEAK_TOKENS = ["<start_of_turn>", "<end_of_turn>", "<|turn>", "<|channel>"]


def parse_args(argv=None):
    p = argparse.ArgumentParser(
        description="Fine-tune the DCL LoRA on Qwen/Qwen3-4B-Instruct-2507 (dense QLoRA, "
                    "Unsloth + TRL, native Qwen3 chat template)")
    p.add_argument("--base-model", "--model-name", dest="model_name",
                   default=DEFAULTS["model_name"],
                   help=f"Base model (default: {DEFAULTS['model_name']} — Apache-2.0 dense "
                        f"non-thinking instruct; chosen on 2026-07-19 probe evidence)")
    p.add_argument("--max-seq-length", type=int, default=DEFAULTS["max_seq_length"],
                   help=f"Max sequence length (default {DEFAULTS['max_seq_length']}; a 4B at "
                        f"QLoRA affords it — the staging seq-audit recommends the smallest "
                        f"bucket with ~0%% truncation)")
    p.add_argument("--lora-r", type=int, default=DEFAULTS["lora_r"])
    p.add_argument("--lora-alpha", type=int, default=DEFAULTS["lora_alpha"])
    p.add_argument("--lora-dropout", type=float, default=DEFAULTS["lora_dropout"])
    p.add_argument("--lr", type=float, default=DEFAULTS["learning_rate"])
    p.add_argument("--batch-size", type=int, default=DEFAULTS["batch_size"])
    p.add_argument("--grad-accum", type=int, default=DEFAULTS["gradient_accumulation"])
    p.add_argument("--warmup-ratio", type=float, default=DEFAULTS["warmup_ratio"])
    p.add_argument("--epochs", type=int, default=DEFAULTS["num_epochs"],
                   help=f"Training epochs (default {DEFAULTS['num_epochs']} — small-corpus "
                        f"pilot; 1 under-fits 507 rows, 2 lifts first-attempt quality without "
                        f"memorising)")
    p.add_argument("--max-steps", type=int, default=None,
                   help="Override epochs with a fixed step count; set ~40 for the smoke run")
    p.add_argument("--logging-steps", type=int, default=DEFAULTS["logging_steps"])
    p.add_argument("--data-path", default=DEFAULTS["data_path"])
    p.add_argument("--eval-path", default=DEFAULTS["eval_path"],
                   help="Eval JSONL for loss-only tracking (skipped cleanly if absent)")
    p.add_argument("--output-dir", required=True,
                   help="Output dir (REQUIRED). Convention: ~/fine-tuning/output/dcl-qwen3-4b "
                        "(full) or dcl-qwen3-4b-smoke (smoke)")
    p.add_argument("--gguf-quant", default=DEFAULTS["gguf_quant"],
                   choices=["q4_k_m", "q8_0", "f16"],
                   help="save_pretrained_gguf quant (default q4_k_m — the laptop-runnable gift "
                        "target)")
    p.add_argument("--report-to", default=DEFAULTS["report_to"],
                   choices=["none", "wandb", "tensorboard"])
    p.add_argument("--min-trainable-pct", type=float, default=0.1,
                   help="[G1] Abort if trainable%% is below this (nothing attached). A dense "
                        "4B LoRA sits ~1-3%%; <0.1%% means the adapter did not attach.")
    p.add_argument("--seed", type=int, default=DEFAULTS["seed"])
    p.add_argument("--resume", action="store_true")
    p.add_argument("--skip-export", action="store_true",
                   help="Skip merged-16bit + GGUF export (smoke runs)")
    p.add_argument("--chat-template-file", default="/workspace/scripts/qwen3-2507-stock.jinja",
                   help="Jinja file with the STOCK Qwen3-2507 chat template, applied to the "
                        "tokenizer after load (live-catch 2026-07-19: Unsloth silently "
                        "overrides the tokenizer with the hybrid-THINKING Qwen3 template, "
                        "which injects <think> pairs into assistant turns and breaks under "
                        "llama.cpp's minja at serve). REQUIRED to exist — no silent fallback.")
    p.add_argument("--allow-think-targets", action="store_true",
                   help="Permit <think> in rendered training targets (live-catch 2026-07-19: "
                        "think tokens are near-untrained in this base and training on them "
                        "collapsed generation onto <tool_call> spam; only set this if you "
                        "know why staging kept them)")
    return p.parse_args(argv)


# ---------------------------------------------------------------------------
# Dataset loading (ShareGPT: {messages:[{role,content}], metadata:{...}})
# ---------------------------------------------------------------------------
def load_sharegpt_jsonl(path: str):
    """Load a ShareGPT-shaped JSONL into a HuggingFace Dataset of {"conversations": [...]}.
    System/user/assistant turns are preserved; metadata is ignored by the trainer."""
    import json

    from datasets import Dataset

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
    print(f"Loaded {len(records)} examples from {path}")
    print(f"  First example roles: {[m['role'] for m in records[0]['conversations']]}")
    return Dataset.from_list(records)


def format_dataset(dataset, tokenizer):
    """Render each conversation with the tokenizer's NATIVE Qwen3 chat template into a
    ``text`` field. No get_chat_template() call — the Qwen3-Instruct-2507 tokenizer ships its
    own <|im_start|>...<|im_end|> template, which we use faithfully for system+user+assistant."""
    from unsloth.chat_templates import standardize_data_formats

    dataset = standardize_data_formats(dataset)

    def _fmt(examples):
        texts = [
            tokenizer.apply_chat_template(convo, tokenize=False, add_generation_prompt=False)
            for convo in examples["conversations"]
        ]
        return {"text": texts}

    return dataset.map(_fmt, batched=True)


def main():
    args = parse_args()

    if not args.output_dir:
        sys.exit("ERROR: --output-dir is required")

    # ---- deferred heavy imports (host py_compile / --help stay dep-free) --------------
    import torch
    from datasets import Dataset  # noqa: F401  (used transitively; keep import surface honest)
    from unsloth import FastLanguageModel
    from unsloth.chat_templates import train_on_responses_only
    from trl import SFTTrainer, SFTConfig

    # 1. Load model (dense QLoRA 4-bit) --------------------------------------------------
    print(f"\n{'='*64}\nLoading {args.model_name}\n"
          f"  QLoRA 4-bit: True | seq: {args.max_seq_length}\n{'='*64}\n")
    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name=args.model_name,
        max_seq_length=args.max_seq_length,
        dtype=None,                 # auto-detect (bf16 on GB10)
        load_in_4bit=True,          # dense 4B quantises cleanly (unlike the 26B MoE)
        full_finetuning=False,
    )

    # Force the STOCK Qwen3-2507 chat template (live-catch 2026-07-19): Unsloth overrides
    # the tokenizer with the hybrid-thinking template (injects <think> pairs, breaks under
    # llama.cpp minja). Train == serve on the stock template, no exceptions.
    if not os.path.isfile(args.chat_template_file):
        sys.exit(f"\nABORT: --chat-template-file {args.chat_template_file} not found. The "
                 f"stock Qwen3-2507 template is REQUIRED (ships beside this script as "
                 f"qwen3-2507-stock.jinja; the launch step copies it into scripts/).\n")
    stock_template = open(args.chat_template_file, encoding="utf-8").read()
    if "reasoning_content" in stock_template or "[::-1]" in stock_template:
        sys.exit("\nABORT: the supplied chat-template file looks like the hybrid-THINKING "
                 "template (reasoning_content / reverse-slice present) — that is the exact "
                 "template the live-catch bans. Supply the stock 2507 instruct template.\n")
    tokenizer.chat_template = stock_template
    print(f"[template] stock Qwen3-2507 template applied from {args.chat_template_file} "
          f"({len(stock_template)} chars; unsloth hybrid override discarded)")

    # [G3] attention implementation
    impl = getattr(getattr(model, "config", None), "_attn_implementation", "unknown")
    print(f"[G3] attention implementation: {impl}")

    # 2. LoRA (dense: attention + MLP) ---------------------------------------------------
    # PEFT torchao version-gate workaround (inherited from the MoE recipe; we don't use
    # torchao). Patch both the source and the importing module.
    try:
        import peft.import_utils
        import peft.tuners.lora.torchao
        peft.import_utils.is_torchao_available = lambda: False
        peft.tuners.lora.torchao.is_torchao_available = lambda: False
    except Exception as e:  # pragma: no cover — defensive; never fatal on host-absent peft
        print(f"NOTE: torchao gate patch skipped ({e})")

    model = FastLanguageModel.get_peft_model(
        model,
        r=args.lora_r,
        target_modules=TARGET_MODULES,
        lora_alpha=args.lora_alpha,
        lora_dropout=args.lora_dropout,
        bias="none",
        use_gradient_checkpointing="unsloth",
        random_state=args.seed,
    )

    # [G1] trainable-% guard — a dense 4B LoRA sits ~1-3%; <0.1% = nothing attached.
    trainable = sum(p.numel() for p in model.parameters() if p.requires_grad)
    total = sum(p.numel() for p in model.parameters())
    pct = 100 * trainable / max(total, 1)
    print(f"[G1] Trainable params: {trainable:,} / {total:,} ({pct:.2f}%) "
          f"(dense LoRA, expect ~1-3%)")
    if pct < args.min_trainable_pct:
        sys.exit(f"\nABORT [G1]: trainable% {pct:.2f} < {args.min_trainable_pct} — the LoRA "
                 f"adapter did NOT attach to the dense modules. Check target_modules / the "
                 f"Unsloth build.\n")

    # 3. Dataset (native Qwen3 template) -------------------------------------------------
    train_dataset = format_dataset(load_sharegpt_jsonl(args.data_path), tokenizer)

    eval_dataset = None
    if args.eval_path and os.path.isfile(args.eval_path):
        eval_dataset = format_dataset(load_sharegpt_jsonl(args.eval_path), tokenizer)
        print(f"Eval set loaded (loss-only): {len(eval_dataset)} rows")
    else:
        print(f"NOTE: no eval file at {args.eval_path} — training without eval loss.")

    # [G2] template render check — Qwen markers present, NO gemma tokens.
    sample = train_dataset[0]["text"]
    print(f"\n--- [G2] first rendered example (first 800 chars) ---\n{sample[:800]}\n--- end ---")
    have_user = "<|im_start|>user" in sample
    have_asst = "<|im_start|>assistant" in sample
    gemma_hits = [t for t in GEMMA_LEAK_TOKENS if t in sample]
    print(f"[G2] markers: <|im_start|>user={have_user}  <|im_start|>assistant={have_asst}  "
          f"gemma-token-leak={gemma_hits or 'none'}")
    if not (have_user and have_asst) or gemma_hits:
        sys.exit("\nABORT [G2]: expected Qwen3 markers <|im_start|>user + <|im_start|>assistant "
                 "and NO gemma tokens. Either the native template did not apply or a gemma "
                 "template leaked in — train==serve alignment would break.\n")

    # [G6] target-format gate (live-catches 2026-07-19): the TRAINED span (after the last
    # assistant marker) must contain neither <think> (near-untrained added tokens — the v1
    # run collapsed onto <tool_call> spam) nor ``` fences (the frozen exam's pinned serving
    # prompt demands bare DCL source — the v2 run failed every author rep at the lexer on
    # the backticks). User turns legitimately contain fenced examples; only the target
    # span is gated.
    def _target_span(text):
        return text.rsplit("<|im_start|>assistant\n", 1)[-1]
    think_rows = sum(1 for r in train_dataset if "<think>" in _target_span(r["text"]))
    fenced_rows = sum(1 for r in train_dataset if "```" in _target_span(r["text"]))
    print(f"[G6] target-format gate: think={think_rows}/{len(train_dataset)} "
          f"fenced={fenced_rows}/{len(train_dataset)} rendered targets "
          f"(expect 0/0 — strip-think + strip-fence staging, stock template)")
    if (think_rows or fenced_rows) and not args.allow_think_targets:
        sys.exit(f"\nABORT [G6]: {think_rows} think / {fenced_rows} fenced targets. Staging "
                 f"ran with --keep-think/--keep-fence, or a thinking template survived. "
                 f"Re-stage with the defaults, or pass --allow-think-targets if you truly "
                 f"mean it.\n")

    # 4. Trainer -------------------------------------------------------------------------
    use_bf16 = torch.cuda.is_bf16_supported()
    sft_kwargs = dict(
        dataset_text_field="text",
        per_device_train_batch_size=args.batch_size,
        gradient_accumulation_steps=args.grad_accum,
        warmup_ratio=args.warmup_ratio,
        num_train_epochs=args.epochs if args.max_steps is None else 1,
        max_steps=args.max_steps if args.max_steps else -1,
        learning_rate=args.lr,
        logging_steps=args.logging_steps,
        save_strategy="epoch",              # save at epoch end
        optim="adamw_8bit",
        weight_decay=0.001,
        lr_scheduler_type="cosine",
        seed=args.seed,
        output_dir=args.output_dir,
        report_to=args.report_to,
        fp16=not use_bf16,
        bf16=use_bf16,
    )
    if eval_dataset is not None:
        sft_kwargs.update(per_device_eval_batch_size=args.batch_size, eval_strategy="epoch")

    training_args = SFTConfig(**sft_kwargs)
    trainer = SFTTrainer(
        model=model, tokenizer=tokenizer,
        train_dataset=train_dataset, eval_dataset=eval_dataset,
        args=training_args,
    )

    # Train only on assistant responses (Qwen markers).
    trainer = train_on_responses_only(
        trainer,
        instruction_part=INSTRUCTION_PART,
        response_part=RESPONSE_PART,
    )

    # [G4] masking sanity — DCL prompts are long (vocab reference embedded), answers shorter,
    # so expect a HIGH masked% (~70-95%). Abort only on ~0% (nothing masked) or ~100% (all
    # masked — the response markers are wrong).
    labels = trainer.train_dataset[0]["labels"]
    masked = sum(1 for x in labels if x == -100)
    masked_pct = 100 * masked / max(len(labels), 1)
    print(f"[G4] response-only masking: {masked}/{len(labels)} masked ({masked_pct:.1f}%). "
          f"DCL user turns embed the vocab reference (long prompts) vs shorter ```dcl answers, "
          f"so a HIGH masked% (~70-95%) is EXPECTED and correct.")
    if masked_pct < 1.0 or masked_pct > 99.0:
        sys.exit(f"\nABORT [G4]: masked% {masked_pct:.1f} is ~0 or ~100 — the "
                 f"instruction/response markers are wrong (train_on_responses_only failed). "
                 f"Expected {INSTRUCTION_PART!r} / {RESPONSE_PART!r}.\n")

    # 5. Train ---------------------------------------------------------------------------
    print(f"\n{'='*64}\nTraining | eff.batch {args.batch_size*args.grad_accum} | lr {args.lr} "
          f"cosine | "
          f"{'steps '+str(args.max_steps) if args.max_steps else 'epochs '+str(args.epochs)}\n"
          f"{'='*64}\n")
    stats = trainer.train(resume_from_checkpoint=args.resume)
    print(f"\nTraining complete. steps={stats.global_step} loss={stats.training_loss:.4f}")

    # [G5] peak memory (GB10 freeze watch)
    if torch.cuda.is_available():
        print(f"[G5] peak GPU memory: {torch.cuda.max_memory_allocated()/1e9:.1f} GB "
              f"(GB10 freeze watch — a dense 4B QLoRA should sit well under ~40 GB; the "
              f"high-water can keep climbing over the first ~40 steps as the longest rows "
              f"appear, so keep watching nvidia-smi past step 40)")

    # 6. Export --------------------------------------------------------------------------
    lora_dir = os.path.join(args.output_dir, "lora-adapter")
    merged_dir = os.path.join(args.output_dir, "merged-16bit")
    gguf_dir = os.path.join(args.output_dir, "gguf")

    print(f"\nSaving LoRA adapter -> {lora_dir}")
    model.save_pretrained(lora_dir)
    tokenizer.save_pretrained(lora_dir)

    if not args.skip_export:
        print(f"Saving merged 16-bit -> {merged_dir}")
        model.save_pretrained_merged(merged_dir, tokenizer, save_method="merged_16bit")

        print(f"Exporting GGUF ({args.gguf_quant}) -> {gguf_dir}")
        os.makedirs(gguf_dir, exist_ok=True)
        try:
            model.save_pretrained_gguf(
                gguf_dir, tokenizer, quantization_method=args.gguf_quant)
            print(f"  Exported: {args.gguf_quant}")
        except Exception as e:
            print(f"  GGUF export failed (non-fatal): {e}\n  Export manually from {merged_dir}.")

    # 7. Inventory -----------------------------------------------------------------------
    print(f"\n{'='*64}\nInventory\n{'='*64}")
    for label, d in (("lora-adapter", lora_dir),
                     ("merged-16bit", merged_dir),
                     ("gguf", gguf_dir)):
        if os.path.isdir(d):
            files = sorted(os.listdir(d))
            print(f"  {label:<14} {d}  ({len(files)} file(s))")
        else:
            print(f"  {label:<14} {d}  (not written"
                  + (" — --skip-export" if args.skip_export else "") + ")")
    print(f"\nNext: A/B on the frozen exam (dcl-tuned-qwen3-4b vs stock; must demolish stock "
          f"2/9 and hold repair 3/3). See RUNBOOK-dcl-fine-tune.md Phase 5.\n{'='*64}\n")


if __name__ == "__main__":
    main()
