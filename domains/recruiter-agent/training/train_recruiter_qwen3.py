#!/usr/bin/env python3
"""
train_recruiter_qwen3.py — Fine-tune the RECRUITER LoRA on Qwen3-4B-Instruct-2507 (dense QLoRA)
================================================================================================
The recruiter fine-tune (Rich's green-light, 2026-07-22: "the Spark for both"). Trains an
office-authoring clerk LoRA on **Qwen/Qwen3-4B-Instruct-2507** (Apache-2.0, DENSE, non-thinking
instruct) via Unsloth + TRL inside the NVIDIA PyTorch container, from the FROZEN corpus produced
by ``domains/recruiter-agent/generate.py`` freeze (``corpus/train.jsonl`` + ``corpus/val.jsonl``,
private under DF-008). Its one job: draft office clerks and pipelines that PASS the office's own
validators and the owner's hiring exam — the durable cure for the 2026-07-21 gate refusal.

This is the DCL fine-tune (``../dcl-capability-language/train_dcl_qwen3.py``) re-aimed at the
recruiter's serve contract. The THREE binding catches from RUNBOOK-dcl-fine-tune v1.2 hold, but
catch 3 is re-aimed because the recruiter's serve format is DIFFERENT from the DCL model's:

  * Catch 1 — STOCK Qwen3-2507 chat template FORCED BY FILE (``--chat-template-file``, required).
    Unsloth silently swaps in the hybrid-THINKING template (injects <think> pairs, breaks under
    llama.cpp minja at serve). ``[G2]`` confirms the render; a thinking-template file is rejected.
  * Catch 2 — never train targets on near-untrained added tokens. The recruiter corpus is
    generated with the teacher's thinking channel DISABLED, so targets carry NO ``<think>`` by
    construction. ``[G6]`` still ABORTS on any ``<think>`` in a rendered target (the guard stays).
  * Catch 3 (RE-AIMED) — **targets byte-match the serve contract**. The DCL serve contract is BARE
    source (fences were stripped). The RECRUITER serve contract is the ``file:``-fenced block
    protocol that ``office_manager.hire.protocol.parse_turn`` reads — so the fences are LOAD-BEARING
    and are KEPT. ``[G6]`` therefore does NOT abort on fences; instead it BYTE-MATCHES each rendered
    target span against the raw assistant ``content`` of the row (proving the stock template altered
    nothing — no think injection, no fence mangling, no escaping) and reports the ``file:`` block
    count that ``parse_turn`` will read. That IS the serve-contract byte-match for this model.

Row shape (serve-faithful, verified against the office serving code — see RUNBOOK-recruiter-generation.md):
  system    = the recruiter seed's ``system_prompt`` verbatim (vocab-in-prompt operating mode)
  user      = ``hire.loop.build_user_turn`` → ``"The owner says:\\n<request>"``
  assistant = the raw drafting turn: a conversational message + zero or more ```` ```file:<path> ````
              blocks. UNLIKE DCL, recruiter rows are TARGET-heavy (system ~1.4KB / user ~0.1KB /
              assistant ~3KB), so ``[G4]`` masked% runs LOWER than DCL's (the target span is the
              long part). max_seq_length defaults to 4096 (a real-tokenizer audit confirms the p99).

Target hardware: Dell DGX Spark GB10 (`spark-fcf6`), 121 GB unified memory (Rich's 2026-07-22 call).
Container:       nvcr.io/nvidia/pytorch:25.11-py3
Deps (inside container — pins from RUNBOOK-dcl-fine-tune v1.2 §3.3, inherited-proven, do NOT bump):
    pip install transformers==5.5.4 peft hf_transfer "datasets==4.3.0" "trl==0.26.1" "accelerate==1.10.0"
    pip install --no-deps unsloth unsloth_zoo bitsandbytes

Input:   ShareGPT JSONL from the recruiter freeze (default /workspace/data/train-recruiter.jsonl,
         eval /workspace/data/val-recruiter.jsonl — val is loss-only, skipped cleanly if absent).
Output:  /workspace/output/recruiter-qwen3-4b/ (lora-adapter + merged-16bit + gguf q4_k_m).

Usage inside the container:
    python train_recruiter_qwen3.py --output-dir /workspace/output/recruiter-qwen3-4b-smoke \\
        --max-steps 40 --skip-export                        # smoke
    python train_recruiter_qwen3.py --output-dir /workspace/output/recruiter-qwen3-4b   # full run

Heavy ML imports (unsloth/torch/trl/transformers/datasets) are DEFERRED into functions so that on
the host (no GPU deps installed) ``python3 -m py_compile`` and ``--help`` both work.
"""

from __future__ import annotations

import argparse
import os
import re
import sys


DEFAULTS = {
    "model_name": "Qwen/Qwen3-4B-Instruct-2507",   # Apache-2.0 dense non-thinking instruct
    "max_seq_length": 4096,                         # recruiter rows are far shorter than DCL's
                                                    # (vocab is NOT embedded in the row's system
                                                    # prompt — it was given to the teacher only),
                                                    # so 4096 covers p99 with headroom. A
                                                    # real-tokenizer audit confirms before commit.
    "lora_r": 16,
    "lora_alpha": 32,
    "lora_dropout": 0.0,
    "learning_rate": 2e-4,
    "batch_size": 1,
    "gradient_accumulation": 4,
    "warmup_ratio": 0.03,
    "num_epochs": 2,                                # small-corpus pilot (DCL precedent)
    "logging_steps": 1,
    "output_dir": None,                             # REQUIRED
    "data_path": "/workspace/data/train-recruiter.jsonl",
    "eval_path": "/workspace/data/val-recruiter.jsonl",
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

# The recruiter serve contract's file-block fence (info string ``file:<path>``) — parse_turn reads
# exactly this shape. [G6] reports how many rendered targets carry at least one such block.
_FILE_FENCE = re.compile(r"^```file:[^\n`]+?[ \t]*$", re.MULTILINE)


def parse_args(argv=None):
    p = argparse.ArgumentParser(
        description="Fine-tune the RECRUITER LoRA on Qwen/Qwen3-4B-Instruct-2507 (dense QLoRA, "
                    "Unsloth + TRL, forced stock Qwen3-2507 chat template)")
    p.add_argument("--base-model", "--model-name", dest="model_name",
                   default=DEFAULTS["model_name"],
                   help=f"Base model (default: {DEFAULTS['model_name']} — Apache-2.0 dense "
                        f"non-thinking instruct; the DCL pilot's measured trainable base)")
    p.add_argument("--max-seq-length", type=int, default=DEFAULTS["max_seq_length"],
                   help=f"Max sequence length (default {DEFAULTS['max_seq_length']}; recruiter "
                        f"rows are short — confirm against the real Qwen3 tokenizer before commit)")
    p.add_argument("--lora-r", type=int, default=DEFAULTS["lora_r"])
    p.add_argument("--lora-alpha", type=int, default=DEFAULTS["lora_alpha"])
    p.add_argument("--lora-dropout", type=float, default=DEFAULTS["lora_dropout"])
    p.add_argument("--lr", type=float, default=DEFAULTS["learning_rate"])
    p.add_argument("--batch-size", type=int, default=DEFAULTS["batch_size"])
    p.add_argument("--grad-accum", type=int, default=DEFAULTS["gradient_accumulation"])
    p.add_argument("--warmup-ratio", type=float, default=DEFAULTS["warmup_ratio"])
    p.add_argument("--epochs", type=int, default=DEFAULTS["num_epochs"],
                   help=f"Training epochs (default {DEFAULTS['num_epochs']} — small-corpus pilot; "
                        f"1 under-fits, 2 lifts first-attempt quality without memorising)")
    p.add_argument("--max-steps", type=int, default=None,
                   help="Override epochs with a fixed step count; set ~40 for the smoke run")
    p.add_argument("--logging-steps", type=int, default=DEFAULTS["logging_steps"])
    p.add_argument("--data-path", default=DEFAULTS["data_path"])
    p.add_argument("--eval-path", default=DEFAULTS["eval_path"],
                   help="Val JSONL for loss-only tracking (skipped cleanly if absent)")
    p.add_argument("--output-dir", required=True,
                   help="Output dir (REQUIRED). Convention: "
                        "~/fine-tuning/recruiter-tune/output/recruiter-qwen3-4b (full) or "
                        "recruiter-qwen3-4b-smoke (smoke)")
    p.add_argument("--gguf-quant", default=DEFAULTS["gguf_quant"],
                   choices=["q4_k_m", "q8_0", "f16"],
                   help="save_pretrained_gguf quant (default q4_k_m — the laptop/CPU-runnable "
                        "bundled-seat target)")
    p.add_argument("--report-to", default=DEFAULTS["report_to"],
                   choices=["none", "wandb", "tensorboard"])
    p.add_argument("--min-trainable-pct", type=float, default=0.1,
                   help="[G1] Abort if trainable%% is below this (nothing attached). A dense 4B "
                        "LoRA sits ~1-3%%; <0.1%% means the adapter did not attach.")
    p.add_argument("--seed", type=int, default=DEFAULTS["seed"])
    p.add_argument("--resume", action="store_true")
    p.add_argument("--skip-export", action="store_true",
                   help="Skip merged-16bit + GGUF export (smoke runs)")
    p.add_argument("--chat-template-file", default="/workspace/scripts/qwen3-2507-stock.jinja",
                   help="Jinja file with the STOCK Qwen3-2507 chat template, applied to the "
                        "tokenizer after load (catch 1: Unsloth silently overrides the tokenizer "
                        "with the hybrid-THINKING Qwen3 template, which injects <think> pairs and "
                        "breaks under llama.cpp minja at serve). REQUIRED to exist — no fallback.")
    p.add_argument("--allow-think-targets", action="store_true",
                   help="Permit <think> in rendered training targets (catch 2: think tokens are "
                        "near-untrained in this base and training on them collapsed generation "
                        "onto <tool_call> spam). The recruiter corpus is think-free by "
                        "construction; only set this if you know why a target carries <think>.")
    return p.parse_args(argv)


# ---------------------------------------------------------------------------
# Dataset loading (ShareGPT: {messages:[{role,content}], metadata:{...}})
# ---------------------------------------------------------------------------
def load_sharegpt_jsonl(path: str):
    """Load a ShareGPT-shaped JSONL into a HuggingFace Dataset of {"conversations": [...]}.
    The raw assistant ``content`` is preserved verbatim in a parallel ``_assistant_raw`` field so
    [G6] can byte-match the rendered target span against it (the serve-contract check)."""
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
            assistant_raw = ""
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
                if role == "assistant":
                    assistant_raw = content
            if conversations:
                records.append({"conversations": conversations, "_assistant_raw": assistant_raw})
    if not records:
        sys.exit(f"ERROR: no valid records in {path}")
    print(f"Loaded {len(records)} examples from {path}")
    print(f"  First example roles: {[m['role'] for m in records[0]['conversations']]}")
    return Dataset.from_list(records)


def format_dataset(dataset, tokenizer):
    """Render each conversation with the (forced stock) Qwen3-2507 chat template into a ``text``
    field, carrying ``_assistant_raw`` through unchanged for the [G6] byte-match."""
    from unsloth.chat_templates import standardize_data_formats

    # standardize_data_formats only touches the conversations column; _assistant_raw rides along.
    dataset = standardize_data_formats(dataset)

    def _fmt(examples):
        texts = [
            tokenizer.apply_chat_template(convo, tokenize=False, add_generation_prompt=False)
            for convo in examples["conversations"]
        ]
        return {"text": texts}

    return dataset.map(_fmt, batched=True)


def _target_span(text: str) -> str:
    """The trained span: everything after the LAST assistant marker, with a trailing <|im_end|>
    (and any trailing whitespace) removed — i.e. the bytes the model is taught to emit."""
    span = text.rsplit(RESPONSE_PART, 1)[-1]
    # the stock template appends <|im_end|>\n after the assistant content for a full turn.
    span = span.rsplit("<|im_end|>", 1)[0]
    return span


def main():
    args = parse_args()

    if not args.output_dir:
        sys.exit("ERROR: --output-dir is required")

    # ---- deferred heavy imports (host py_compile / --help stay dep-free) --------------
    import torch
    from datasets import Dataset  # noqa: F401  (keep the import surface honest)
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
        load_in_4bit=True,          # dense 4B quantises cleanly
        full_finetuning=False,
    )

    # Catch 1 — force the STOCK Qwen3-2507 chat template. Unsloth overrides the tokenizer with
    # the hybrid-thinking template (injects <think> pairs, breaks under llama.cpp minja).
    if not os.path.isfile(args.chat_template_file):
        sys.exit(f"\nABORT: --chat-template-file {args.chat_template_file} not found. The stock "
                 f"Qwen3-2507 template is REQUIRED (ships beside this script as "
                 f"qwen3-2507-stock.jinja; the launch step copies it into scripts/).\n")
    stock_template = open(args.chat_template_file, encoding="utf-8").read()
    if "reasoning_content" in stock_template or "[::-1]" in stock_template:
        sys.exit("\nABORT: the supplied chat-template file looks like the hybrid-THINKING template "
                 "(reasoning_content / reverse-slice present) — the exact template catch 1 bans. "
                 "Supply the stock 2507 instruct template.\n")
    tokenizer.chat_template = stock_template
    print(f"[template] stock Qwen3-2507 template applied from {args.chat_template_file} "
          f"({len(stock_template)} chars; unsloth hybrid override discarded)")

    # [G3] attention implementation
    impl = getattr(getattr(model, "config", None), "_attn_implementation", "unknown")
    print(f"[G3] attention implementation: {impl}")

    # 2. LoRA (dense: attention + MLP) ---------------------------------------------------
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

    # 3. Dataset (forced stock Qwen3 template) -------------------------------------------
    train_dataset = format_dataset(load_sharegpt_jsonl(args.data_path), tokenizer)

    eval_dataset = None
    if args.eval_path and os.path.isfile(args.eval_path):
        eval_dataset = format_dataset(load_sharegpt_jsonl(args.eval_path), tokenizer)
        print(f"Val set loaded (loss-only): {len(eval_dataset)} rows")
    else:
        print(f"NOTE: no val file at {args.eval_path} — training without eval loss.")

    # [G2] template render check — Qwen markers present, NO gemma tokens.
    sample = train_dataset[0]["text"]
    print(f"\n--- [G2] first rendered example (first 900 chars) ---\n{sample[:900]}\n--- end ---")
    have_user = "<|im_start|>user" in sample
    have_asst = "<|im_start|>assistant" in sample
    gemma_hits = [t for t in GEMMA_LEAK_TOKENS if t in sample]
    print(f"[G2] markers: <|im_start|>user={have_user}  <|im_start|>assistant={have_asst}  "
          f"gemma-token-leak={gemma_hits or 'none'}")
    if not (have_user and have_asst) or gemma_hits:
        sys.exit("\nABORT [G2]: expected Qwen3 markers <|im_start|>user + <|im_start|>assistant "
                 "and NO gemma tokens. Either the stock template did not apply or a gemma template "
                 "leaked in — train==serve alignment would break.\n")

    # [G6] serve-contract gate (catch 2 + RE-AIMED catch 3). The recruiter serve contract is the
    # ``file:``-fenced block protocol parse_turn reads, so fences are KEPT (unlike DCL). Two checks:
    #   (2) NO <think> in any rendered target (near-untrained added tokens — the collapse risk).
    #   (3) each rendered target span BYTE-MATCHES the row's raw assistant content (the stock
    #       template altered nothing: no think injection, no fence mangling, no escaping) — the
    #       serve-contract byte-match. Also reports how many targets carry a ```file: block.
    think_rows = 0
    fileblock_rows = 0
    mismatch = []
    for i, r in enumerate(train_dataset):
        span = _target_span(r["text"])
        if "<think>" in span:
            think_rows += 1
        if _FILE_FENCE.search(span):
            fileblock_rows += 1
        # byte-match: the rendered target span must equal the raw assistant content the row carries
        # (the stock template only wraps it in <|im_start|>assistant\n ... <|im_end|>). Compare with
        # a single trailing-newline tolerance (the template adds one before <|im_end|>).
        raw = r["_assistant_raw"]
        if span != raw and span.rstrip("\n") != raw.rstrip("\n"):
            if len(mismatch) < 3:
                mismatch.append((i, raw[:80], span[:80]))
    n = len(train_dataset)
    print(f"[G6] serve-contract gate: think={think_rows}/{n} (expect 0) · "
          f"file-block targets={fileblock_rows}/{n} (KEPT — the recruiter serve contract) · "
          f"byte-match mismatches={len(mismatch)}/{n} (expect 0)")
    if think_rows and not args.allow_think_targets:
        sys.exit(f"\nABORT [G6/catch2]: {think_rows} rendered targets contain <think>. The "
                 f"recruiter corpus is think-free by construction — a thinking template survived, "
                 f"or a bad row leaked. Re-check the corpus, or pass --allow-think-targets if you "
                 f"truly mean it.\n")
    if mismatch:
        for idx, raw80, span80 in mismatch:
            print(f"    row {idx}: raw[:80]={raw80!r}\n            span[:80]={span80!r}")
        sys.exit(f"\nABORT [G6/catch3]: {len(mismatch)} rendered target(s) do NOT byte-match the "
                 f"row's raw assistant content — the stock template altered the target (think "
                 f"injection / fence mangling / escaping). train==serve would break.\n")

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
        save_strategy="epoch",
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

    # [G4] masking sanity. UNLIKE DCL (prompt-heavy: vocab embedded in the user turn), the recruiter
    # is TARGET-heavy (system ~1.4KB + user ~0.1KB prompt vs ~3KB drafted answer), so masked% runs
    # LOWER here. Abort only on ~0% (nothing masked) or ~100% (all masked — markers wrong).
    labels = trainer.train_dataset[0]["labels"]
    masked = sum(1 for x in labels if x == -100)
    masked_pct = 100 * masked / max(len(labels), 1)
    print(f"[G4] response-only masking: {masked}/{len(labels)} masked ({masked_pct:.1f}%). "
          f"Recruiter rows are TARGET-heavy (short prompt, long drafted answer), so a LOWER "
          f"masked% than DCL is EXPECTED and correct.")
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
              f"(GB10 freeze watch — a dense 4B QLoRA should sit well under ~40 GB; the high-water "
              f"can keep climbing over the first ~40 steps, so keep watching nvidia-smi past step 40)")

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
    print(f"\nNext: the MERGED-GENERATION GATE (mandatory pre-GGUF verdict) — generate on >=10 "
          f"val-held prompts, parse_turn + office checkers, tuned vs stock. See "
          f"merged_gen_gate.py.\n{'='*64}\n")


if __name__ == "__main__":
    main()
