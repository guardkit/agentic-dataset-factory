#!/usr/bin/env python3
"""
train_qav.py — Fine-tune the QAV judgment LoRA on Gemma-4-26B-A4B MoE (16-bit LoRA)
==================================================================================
The QAV pilot PROBE fine-tune (Rich ruled Option A on plateau card #2, 2026-07-22: the pilot
tune fires on the 108-corpus). Trains the L5 judgment seat — reads a CoachEvidenceBundle and
renders approve/reject-with-findings — on **unsloth/gemma-4-26B-A4B-it** (the coach-ft lineage,
D9 different-family) via Unsloth + TRL inside the NVIDIA PyTorch container, from the staged
corpus produced by ``prepare_qav_sft.py`` (staged OUTSIDE the repo under ``~/fine-tuning/data/``
— never committed; the corpus is private under DF-008).

Forked from the validated ``../coach-agent/train_coach_moe.py`` (same base + served fleet).
Deltas for QAV, plus the THREE DCL-tune catches as numbered laws:

  * BASE = ``unsloth/gemma-4-26B-A4B-it`` (bf16), loaded ``load_in_16bit=True`` /
    ``load_in_4bit=False``. The 26B-A4B MoE cannot do 4-bit QLoRA — its 3D fused expert
    tensors block it (the coach finding). So "QLoRA" in SCOPE §3 is realized here as 16-bit
    LoRA, exactly as the coach/architect/tutor runs on this base. ``attn_implementation=sdpa``
    (FA2 unsupported: head_dim 512 > 256).
  * CATCH #1 — FORCE THE SERVING TEMPLATE, ban the silent hybrid swap. The chat template is
    ``gemma-4`` (NON-thinking) via get_chat_template — the coach-proven serving template
    (embedded into the GGUF at export; verified by the export->serve round-trip). ``[GT]``
    below (a) REFUSES ``--chat-template gemma-4-thinking``, and (b) asserts the applied
    template carries no thinking-only constructs (``reasoning_content`` / reverse-slice) — the
    exact hybrid swap the DCL live-catch banned. Optional ``--chat-template-file`` forces a
    stock gemma jinja verbatim if the embedded one ever misbehaves (coach SERVING fallback).
  * CATCH #2 — never train targets on near-untrained added tokens. QAV rows carry a <think>
    block (OUTPUT-CONTRACT §1); ``prepare_qav_sft.py`` STRIPS it from staged targets by
    default. ``[G6]`` aborts if any rendered target still contains <think>. (In gemma-4 the
    literal ``<think>`` is ordinary text, not a special token — but the serving contract still
    bans the reasoning prose, and a long think block risks truncating the END-positioned
    verdict under the runner's max_tokens ceiling; strip is the byte-match cure either way.)
  * CATCH #3 — staged targets must byte-match the serving contract. The qav-heldout serving
    prompt (fleet-evals/harness/run_qav_heldout.py) demands "ONLY the verdict JSON object — no
    prose, no explanation, no markdown fences" and extracts via a ```json fence OR the first
    balanced {...} object (the balanced scanner is the robust path). ``prepare_qav_sft.py``
    unwraps the ```json fence to a BARE verdict object by default; ``[G6]`` aborts on any
    ``` fence in a rendered target.
  * EPOCHS 3 (small-corpus PROBE: 86 staged train rows; 1 epoch badly under-fits at ~22
    steps/epoch, 3 lets the judgment shape land without a large corpus — a probe knob, smoke
    first). LoRA r=16 / alpha=16 (coach precedent on this exact base). lr 2e-4 cosine.

The MERGED-16BIT GENERATION SANITY GATE IS MANDATORY BEFORE ANY GGUF/SERVE STEP (the DCL
process rule that burned a probe cycle). This script therefore writes merged-16bit by default
and only exports GGUF when ``--export-gguf`` is passed — run the Phase-5.2 merged-gen sanity
between them. ``--skip-export`` (smoke) writes only the adapter.

Target hardware: Dell DGX Spark GB10 (121 GB unified memory).
Container:       nvcr.io/nvidia/pytorch:25.11-py3  (deps per ../coach-agent/RUNBOOK §3.3)
Input:           ShareGPT JSONL from prepare_qav_sft.py (train-qav.jsonl / eval-qav.jsonl)
Output:          /workspace/output/qav-gemma4-26b-moe/ (lora-adapter + merged-16bit [+ gguf])

Usage inside the container:
    python train_qav.py --output-dir /workspace/output/qav-gemma4-26b-moe-smoke \\
        --max-steps 40 --skip-export                 # smoke
    python train_qav.py --output-dir /workspace/output/qav-gemma4-26b-moe   # full (no gguf yet)
    python train_qav.py --output-dir .../qav-gemma4-26b-moe --export-gguf   # after Phase 5.2

Heavy ML imports (unsloth/torch/trl/transformers/datasets) are DEFERRED into main() so that on
the host (no GPU deps) ``python3 -m py_compile`` and ``--help`` both work.
"""

from __future__ import annotations

import argparse
import os
import sys


DEFAULTS = {
    "model_name": "unsloth/gemma-4-26B-A4B-it",    # coach-ft lineage; QAT swap REFUTED
    "max_seq_length": 8192,                         # QAV rows are the LONGEST in the fleet (the
                                                    # user turn is a full serialized bundle, the
                                                    # verdict sits at the END). 8192 covers the
                                                    # bundles; confirm on the real gemma-4
                                                    # tokenizer (Phase 3.3a) and watch memory —
                                                    # the coach found seq>=6144 OOM-climbs on the
                                                    # 26B, so smoke-test peak memory before trust.
    "lora_r": 16,
    "lora_alpha": 16,                               # coach precedent on this base
    "learning_rate": 2e-4,
    "batch_size": 1,
    "gradient_accumulation": 4,
    "warmup_ratio": 0.03,
    "num_epochs": 3,                                # small-corpus probe (see module docstring)
    "logging_steps": 1,
    "data_path": "/workspace/data/train-qav.jsonl",
    "eval_path": "/workspace/data/eval-qav.jsonl",
    "chat_template": "gemma-4",                     # NON-thinking (catch #1)
    "gguf_quant": "q4_k_m",                         # NEVER q4_0; stand-in for UD-Q4_K_XL
    "report_to": "none",
    "seed": 3407,
}

# gemma-4 native chat-template markers (train == serve alignment).
INSTRUCTION_PART = "<|turn>user\n"
RESPONSE_PART = "<|turn>model\n"


def parse_args(argv=None):
    p = argparse.ArgumentParser(
        description="Fine-tune the QAV judgment LoRA on unsloth/gemma-4-26B-A4B-it "
                    "(16-bit LoRA — MoE QLoRA blocked; Unsloth + TRL; gemma-4 non-thinking "
                    "chat template)")
    p.add_argument("--base-model", "--model-name", dest="model_name",
                   default=DEFAULTS["model_name"],
                   help=f"Base model (default: {DEFAULTS['model_name']} — coach-ft lineage, "
                        f"D9 different-family; the judge must not share a family with the "
                        f"Player it judges)")
    p.add_argument("--max-seq-length", type=int, default=DEFAULTS["max_seq_length"],
                   help=f"Max sequence length (default {DEFAULTS['max_seq_length']}). QAV rows "
                        f"are the longest in the fleet and the verdict is at the END — "
                        f"truncation eats the label. Confirm on the real gemma-4 tokenizer.")
    p.add_argument("--lora-r", type=int, default=DEFAULTS["lora_r"])
    p.add_argument("--lora-alpha", type=int, default=DEFAULTS["lora_alpha"])
    p.add_argument("--lr", type=float, default=DEFAULTS["learning_rate"])
    p.add_argument("--batch-size", type=int, default=DEFAULTS["batch_size"])
    p.add_argument("--grad-accum", type=int, default=DEFAULTS["gradient_accumulation"])
    p.add_argument("--warmup-ratio", type=float, default=DEFAULTS["warmup_ratio"])
    p.add_argument("--epochs", type=int, default=DEFAULTS["num_epochs"],
                   help=f"Training epochs (default {DEFAULTS['num_epochs']} — small-corpus "
                        f"probe; 1 under-fits 86 rows, 3 lets the judgment shape land)")
    p.add_argument("--max-steps", type=int, default=None,
                   help="Override epochs with a fixed step count; set ~40 for the smoke run")
    p.add_argument("--logging-steps", type=int, default=DEFAULTS["logging_steps"])
    p.add_argument("--data-path", default=DEFAULTS["data_path"])
    p.add_argument("--eval-path", default=DEFAULTS["eval_path"],
                   help="Eval JSONL for loss-only tracking (skipped cleanly if absent)")
    p.add_argument("--output-dir", required=True,
                   help="Output dir (REQUIRED). Convention: ~/fine-tuning/output/"
                        "qav-gemma4-26b-moe (full) or -smoke (smoke)")
    p.add_argument("--chat-template", default=DEFAULTS["chat_template"],
                   choices=["gemma-4", "gemma-4-thinking"],
                   help="gemma-4 (non-thinking) is correct for the JSON QAV; gemma-4-thinking "
                        "is REFUSED (catch #1 — the tutor template-leak lesson)")
    p.add_argument("--chat-template-file", default=None,
                   help="Optional: force a STOCK gemma jinja from a file verbatim (catch #1 "
                        "file-forcing; the coach SERVING fallback if the embedded template "
                        "misbehaves). A thinking-template file is REFUSED.")
    p.add_argument("--gguf-quant", default=DEFAULTS["gguf_quant"],
                   choices=["q4_k_m", "q8_0", "f16"],
                   help="save_pretrained_gguf quant (q4_k_m ~ UD-Q4_K_XL stand-in; NEVER q4_0 "
                        "— collapses 26B-A4B to 70.2%% top-1)")
    p.add_argument("--report-to", default=DEFAULTS["report_to"],
                   choices=["none", "wandb", "tensorboard"])
    p.add_argument("--min-trainable-pct", type=float, default=1.0,
                   help="[G1] Abort if trainable%% is below this (PR #4913 expert-attach guard; "
                        "expected ~1.88%% on this MoE)")
    p.add_argument("--allow-low-trainable", action="store_true",
                   help="Bypass the [G1] trainable-%% abort (NOT recommended)")
    p.add_argument("--allow-think-targets", action="store_true",
                   help="Permit <think>/``` in rendered training targets (catch #2/#3 override; "
                        "only if you staged with --keep-think/--keep-fence on purpose)")
    p.add_argument("--seed", type=int, default=DEFAULTS["seed"])
    p.add_argument("--resume", action="store_true")
    p.add_argument("--skip-export", action="store_true",
                   help="Skip merged-16bit + GGUF export (smoke runs; writes only the adapter)")
    p.add_argument("--export-gguf", action="store_true",
                   help="Export GGUF. DEFAULT IS OFF: the merged-16bit generation sanity gate "
                        "(Phase 5.2) is MANDATORY before any GGUF/serve step (the DCL process "
                        "rule). Run the full run, pass Phase 5.2, THEN re-invoke with this flag "
                        "(or export manually from merged-16bit/).")
    return p.parse_args(argv)


# ---------------------------------------------------------------------------
# Dataset loading (ShareGPT: {messages:[{role,content}], metadata:{...}})
# ---------------------------------------------------------------------------
def load_sharegpt_jsonl(path: str):
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


def main():
    args = parse_args()

    if not args.output_dir:
        sys.exit("ERROR: --output-dir is required")

    # ---- deferred heavy imports (host py_compile / --help stay dep-free) --------------
    import torch
    from datasets import Dataset  # noqa: F401  (keep the import surface honest)
    from unsloth import FastModel
    from unsloth.chat_templates import (
        get_chat_template,
        standardize_data_formats,
        train_on_responses_only,
    )
    from trl import SFTTrainer, SFTConfig

    # 1. Load model (16-bit LoRA — MoE QLoRA blocked) ------------------------------------
    print(f"\n{'='*64}\nLoading {args.model_name}\n"
          f"  16-bit LoRA: True | 4-bit: False (MoE QLoRA blocked) | "
          f"seq: {args.max_seq_length}\n{'='*64}\n")
    model, tokenizer = FastModel.from_pretrained(
        model_name=args.model_name,
        max_seq_length=args.max_seq_length,
        dtype=None,
        load_in_4bit=False,          # MoE QLoRA blocked (3D fused expert tensors)
        load_in_16bit=True,
        full_finetuning=False,
        use_gradient_checkpointing="unsloth",
        attn_implementation="sdpa",  # FA2 unsupported: head_dim 512 > 256
    )

    # [G3] sdpa check
    impl = getattr(getattr(model, "config", None), "_attn_implementation", "unknown")
    if impl and "flash" in str(impl).lower():
        print(f"WARNING [G3]: attn_implementation={impl} — expected sdpa; FA2 will crash on "
              f"Gemma 4's head_dim=512 global layers.")
    else:
        print(f"[G3] attention implementation: {impl}")

    # 2. LoRA ---------------------------------------------------------------------------
    # PEFT torchao version-gate workaround (inherited from the coach recipe; we don't use it).
    try:
        import peft.import_utils
        import peft.tuners.lora.torchao
        peft.import_utils.is_torchao_available = lambda: False
        peft.tuners.lora.torchao.is_torchao_available = lambda: False
    except Exception as e:  # pragma: no cover — defensive
        print(f"NOTE: torchao gate patch skipped ({e})")

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
        random_state=args.seed,
    )

    # [G1] trainable-% guard (PR #4913: MoE experts must actually attach)
    trainable = sum(p.numel() for p in model.parameters() if p.requires_grad)
    total = sum(p.numel() for p in model.parameters())
    pct = 100 * trainable / max(total, 1)
    print(f"[G1] Trainable params: {trainable:,} / {total:,} ({pct:.2f}%) (expect ~1.88%)")
    if pct < args.min_trainable_pct and not args.allow_low_trainable:
        sys.exit(
            f"\nABORT [G1]: trainable% {pct:.2f} < {args.min_trainable_pct} — the MoE expert "
            f"LoRA almost certainly did NOT attach (Unsloth #4907, fixed PR #4913). Upgrade "
            f"Unsloth, or pass --allow-low-trainable to override (NOT recommended).\n")

    # 3. Chat template — CATCH #1: force gemma-4 (non-thinking), ban the silent hybrid swap
    if args.chat_template == "gemma-4-thinking":
        sys.exit("\nABORT [GT]: --chat-template gemma-4-thinking is REFUSED for QAV (the tutor "
                 "template-leak lesson). The QAV emits a bare JSON verdict, not <think>.\n")
    if args.chat_template_file:
        if not os.path.isfile(args.chat_template_file):
            sys.exit(f"\nABORT [GT]: --chat-template-file {args.chat_template_file} not found.\n")
        stock = open(args.chat_template_file, encoding="utf-8").read()
        if "reasoning_content" in stock or "[::-1]" in stock:
            sys.exit("\nABORT [GT]: the supplied chat-template file looks like a THINKING "
                     "template (reasoning_content / reverse-slice present) — the exact swap "
                     "catch #1 bans. Supply the stock non-thinking gemma template.\n")
        tokenizer.chat_template = stock
        print(f"[GT] stock gemma template forced from {args.chat_template_file} ({len(stock)} "
              f"chars).")
    else:
        tokenizer = get_chat_template(tokenizer, chat_template=args.chat_template)
        # Guard: Unsloth must not have swapped in a thinking template under us.
        tmpl = getattr(tokenizer, "chat_template", "") or ""
        if "reasoning_content" in tmpl or "[::-1]" in tmpl:
            sys.exit("\nABORT [GT]: the applied chat template carries thinking-only constructs "
                     "(reasoning_content / reverse-slice) — a hybrid template leaked in "
                     "(catch #1). Force the stock non-thinking gemma template via "
                     "--chat-template-file.\n")
        print(f"[GT] chat template: {args.chat_template} (non-thinking, catch #1 guard passed)")

    # 4. Dataset ------------------------------------------------------------------------
    def format_dataset(ds):
        ds = standardize_data_formats(ds)

        def _fmt(examples):
            texts = [
                tokenizer.apply_chat_template(
                    convo, tokenize=False, add_generation_prompt=False
                ).removeprefix("<bos>")
                for convo in examples["conversations"]
            ]
            return {"text": texts}

        return ds.map(_fmt, batched=True)

    train_dataset = format_dataset(load_sharegpt_jsonl(args.data_path))

    eval_dataset = None
    if args.eval_path and os.path.isfile(args.eval_path):
        eval_dataset = format_dataset(load_sharegpt_jsonl(args.eval_path))
        print(f"Eval set loaded (loss-only): {len(eval_dataset)} rows")
    else:
        print(f"NOTE: no eval file at {args.eval_path} — training without eval loss.")

    # [G2] template render check — gemma-4 turn markers present, no thinking channel leak.
    sample = train_dataset[0]["text"]
    print(f"\n--- [G2] first rendered example (first 700 chars) ---\n{sample[:700]}\n--- end ---")
    have_user = "<|turn>user" in sample
    have_model = "<|turn>model" in sample
    print(f"[G2] markers: <|turn>user={have_user}  <|turn>model={have_model}")
    if not (have_user and have_model):
        sys.exit("\nABORT [G2]: gemma-4 turn markers missing — train_on_responses_only masking "
                 "and serve-time alignment would break. Check the chat-template name/version.\n")

    # [G6] target-format gate — CATCH #2/#3: the TRAINED span (after the last model marker)
    # must contain neither <think> (the serving contract bans reasoning prose; long think
    # risks truncating the END-positioned verdict) nor ``` fences (the serving prompt demands
    # bare JSON; the exam extractor's robust path is the balanced-object scanner). User turns
    # legitimately contain JSON braces; only the target span is gated.
    def _target_span(text):
        return text.rsplit(RESPONSE_PART, 1)[-1]
    think_rows = sum(1 for r in train_dataset if "<think>" in _target_span(r["text"]))
    fenced_rows = sum(1 for r in train_dataset if "```" in _target_span(r["text"]))
    print(f"[G6] target-format gate: think={think_rows}/{len(train_dataset)} "
          f"fenced={fenced_rows}/{len(train_dataset)} rendered targets "
          f"(expect 0/0 — strip-think + strip-fence staging)")
    if (think_rows or fenced_rows) and not args.allow_think_targets:
        sys.exit(f"\nABORT [G6]: {think_rows} think / {fenced_rows} fenced targets. Re-stage "
                 f"with prepare_qav_sft.py defaults (no --keep-think/--keep-fence), or pass "
                 f"--allow-think-targets if you truly mean it.\n")

    # 5. Trainer ------------------------------------------------------------------------
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

    trainer = SFTTrainer(
        model=model, tokenizer=tokenizer,
        train_dataset=train_dataset, eval_dataset=eval_dataset,
        args=SFTConfig(**sft_kwargs),
    )
    trainer = train_on_responses_only(
        trainer, instruction_part=INSTRUCTION_PART, response_part=RESPONSE_PART)

    # [G4] masking sanity — for QAV the USER turn (full bundle) is LARGE and the bare JSON
    # verdict is SMALL, so expect a HIGH masked% (~85-99%; the opposite of the coach, whose
    # verdict was the larger trained part). Abort only at ~0% (nothing masked → markers wrong)
    # or a full 100% (the whole target was masked/truncated away → the label is gone, the
    # seq-length lesson squared).
    labels = trainer.train_dataset[0]["labels"]
    masked = sum(1 for x in labels if x == -100)
    masked_pct = 100 * masked / max(len(labels), 1)
    print(f"[G4] response-only masking: {masked}/{len(labels)} masked ({masked_pct:.1f}%). "
          f"QAV: large bundle prompt, small verdict target → HIGH masked% (~85-99%) EXPECTED.")
    if masked_pct < 1.0 or masked_pct >= 99.9:
        sys.exit(f"\nABORT [G4]: masked% {masked_pct:.1f} is ~0 (markers wrong) or ~100 (the "
                 f"target was truncated/masked away — the verdict is at the END, so a too-small "
                 f"--max-seq-length ate the label). Expected {INSTRUCTION_PART!r} / "
                 f"{RESPONSE_PART!r} and a seq-length that fits the verdict.\n")

    # 6. Train --------------------------------------------------------------------------
    print(f"\n{'='*64}\nTraining | eff.batch {args.batch_size*args.grad_accum} | lr {args.lr} "
          f"cosine | "
          f"{'steps '+str(args.max_steps) if args.max_steps else 'epochs '+str(args.epochs)}\n"
          f"{'='*64}\n")
    stats = trainer.train(resume_from_checkpoint=args.resume)
    print(f"\nTraining complete. steps={stats.global_step} loss={stats.training_loss:.4f}")

    # [G5] peak memory (GB10 freeze watch)
    if torch.cuda.is_available():
        print(f"[G5] peak GPU memory: {torch.cuda.max_memory_allocated()/1e9:.1f} GB "
              f"(GB10 freeze watch — keep well under ~100 GB; seq>=6144 OOM-climbs on this 26B, "
              f"so keep watching nvidia-smi past step 40)")

    # 7. Export -------------------------------------------------------------------------
    lora_dir = os.path.join(args.output_dir, "lora-adapter")
    merged_dir = os.path.join(args.output_dir, "merged-16bit")
    gguf_dir = os.path.join(args.output_dir, "gguf")

    print(f"\nSaving LoRA adapter -> {lora_dir}")
    model.save_pretrained(lora_dir)
    tokenizer.save_pretrained(lora_dir)

    if not args.skip_export:
        print(f"Saving merged 16-bit -> {merged_dir}")
        model.save_pretrained_merged(merged_dir, tokenizer, save_method="merged_16bit")

        if args.export_gguf:
            print(f"Exporting GGUF ({args.gguf_quant}) -> {gguf_dir}")
            os.makedirs(gguf_dir, exist_ok=True)
            try:
                model.save_pretrained_gguf(
                    gguf_dir, tokenizer, quantization_method=args.gguf_quant)
                print(f"  Exported: {args.gguf_quant}  (NEVER q4_0; q4_k_m is the UD-Q4_K_XL "
                      f"stand-in — build true UD-Q4_K_XL with llama.cpp if serving quality needs)")
            except Exception as e:
                print(f"  GGUF export failed (non-fatal): {e}\n  Export manually from {merged_dir}.")
        else:
            print("\n*** GGUF NOT exported. The merged-16bit generation sanity gate (Phase 5.2) "
                  "is MANDATORY before any GGUF/serve step (the DCL process rule — a skipped "
                  "merged-gen check burned a probe cycle). Run Phase 5.2 against merged-16bit/, "
                  "then re-invoke with --export-gguf (or export manually).")

    # 8. Inventory ----------------------------------------------------------------------
    print(f"\n{'='*64}\nInventory\n{'='*64}")
    for label, d in (("lora-adapter", lora_dir), ("merged-16bit", merged_dir), ("gguf", gguf_dir)):
        if os.path.isdir(d):
            print(f"  {label:<14} {d}  ({len(os.listdir(d))} file(s))")
        else:
            note = " — --skip-export" if args.skip_export else (
                " — pass --export-gguf after Phase 5.2" if label == "gguf" else "")
            print(f"  {label:<14} {d}  (not written{note})")
    print(f"\nNext: Phase 5.2 merged-gen sanity (MANDATORY) → then A/B on the frozen exam "
          f"(qav-held-001/002; must-catch 4/4 gold negatives, hold the over-reject ceiling). "
          f"See RUNBOOK-qav-fine-tune.md.\n{'='*64}\n")


if __name__ == "__main__":
    main()
