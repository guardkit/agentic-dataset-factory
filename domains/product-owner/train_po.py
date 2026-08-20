#!/usr/bin/env python3
"""
train_po.py — the PO bake-off trainer: ONE script, TWO students
===============================================================
Lane: PO corpus v3 -> two-student bake-off (Rich's training word, 2026-08-20).
Corpus of record: agentic-dataset-factory/corpora/v3-2026-08-20 (13 harvest + 84 trace-export
+ 158 synthetic = 255 rows), staged by scripts/stage_po_v3.py into
    ~/fine-tuning/data/train-po-v3.jsonl            255 rows (the default here)
    ~/fine-tuning/data/train-po-v3.fit-6144.jsonl   187 rows — the NO-TRUNCATION option at 6144
    ~/fine-tuning/data/train-po-v3.seq-audit.json   per-row tokens, real tokenizers, 3 views

    STUDENTS
  gemma4  unsloth/gemma-4-26b-a4b-it   MoE 26B-A4B. QLoRA is BLOCKED for this family (3D fused
          expert tensors) -> load_in_16bit bf16 LoRA. attn sdpa (head_dim 512 > FA2's 256).
          [G1] guards the confirmed Unsloth expert-attach bug (issue #4907 / PR #4913): a
          no-op tune trains 0.91% of params by skipping the experts; expect ~1.88%.
  qwen38  Qwen/Qwen3.8-27B             HYBRID 64 layers: 16 full_attention + 48 Gated-DeltaNet
          (config.text_config.layer_types, verified in the local snapshot). NO QLoRA for this
          family (Unsloth: "not recommended ... higher than normal quantization differences")
          -> bf16 LoRA. Two traps, both guarded here:
            * a bare ["q_proj","k_proj","v_proj","o_proj"] target list touches ONLY the 16
              attention layers. MEASURED on a meta-device build of this exact config
              (2026-08-20, no weights, no GPU): 64 modules / 16 layer indices / 10,485,760 LoRA
              params at r=16 = 0.038% of 27,356,728,560 — a near no-op, and the number the
              [G1] floor exists to catch. The default list below adds gate/up/down_proj, which
              exist in ALL 64 layers (checkpoint index: 64x mlp.{gate,up,down}_proj vs 16x
              self_attn.*_proj) -> 256 modules / 64 layer indices / 79,691,776 params = 0.291%.
              [G1b] counts adapters BY LAYER INDEX and aborts below 64.
            * it is natively MULTIMODAL: `model.visual.*` (27 blocks: attn.qkv / attn.proj /
              mlp.linear_fc1 / mlp.linear_fc2 / merger.linear_fc*) — a loose regex silently
              spends LoRA capacity on the vision tower. Frozen BY NAME here (FROZEN_PREFIXES)
              and asserted: any trainable parameter under `visual.` or `mtp.` aborts.
          Names are NOT guessed: they come from the local snapshot's model.safetensors.index.json
          and transformers/models/qwen3_5/modeling_qwen3_5.py (Qwen3_5Model.visual /
          .language_model, Qwen3_5DecoderLayer.{self_attn|linear_attn}/.mlp).

THE QWEN THINK HAZARD (and why split_think() lives in two files)
  Qwen3.8's own template ALWAYS emits `<think>\n{reasoning_content}\n</think>` before the final
  assistant `content`; 171 of the 255 staged rows already carry an INLINE <think> block (measured
  2026-08-20 by check_po_train_assets.py), so a naive render DOUBLE-emits on exactly those 171. `--qwen-think split` (default) lifts the leading block into the message's
  `reasoning_content` so the template renders ONE native think block — this is exactly what the
  audit's "qwen-split" view measured, so the audited token counts are the ones that materialise.
  split_think() below MUST STAY IN STEP with stage_po_v3.py:split_think() (copied verbatim; if
  you change one, change the other and re-run the audit).

TEMPLATES ARE PINNED BY FILE (sha1 asserted) so train == audit == serve is a checked fact:
  gemma4 chat_template.jinja sha1 5a538c54b0feb1e8704a38dedf6f4e4755203d80 (refreshed July
         template, snapshot 60941ad6; weights byte-identical to April)
  qwen38 chat_template.jinja sha1 08a763ee5e339981deac7c2761751798f063e444 (snapshot 1d4bf0f2)
  Override with --chat-template-file / --allow-template-drift, loudly.

GATES (each prints one line a receipt can quote)
  [G1]  trainable-% (abort below --min-trainable-pct; per-student default, see STUDENTS table)
  [G1b] qwen38 only: adapters present on >= --min-adapter-layers (64) distinct layer indices,
        i.e. the DeltaNet layers are attached too, not just the 16 attention ones; plus the
        vision-tower/MTP freeze assertion.
  [G2]  render the first example, assert this student's turn markers, assert the other
        student's markers did NOT leak, and (qwen38) assert NO double <think> anywhere.
  [G3]  attention implementation; qwen38 also prints whether flash-linear-attention is
        importable (it is NOT installed on this box: the 48 DeltaNet layers then run the slow
        pure-PyTorch path — a GB10 report measured 451 -> 3,461 tok/s after installing it).
        Printed, never silently assumed.
  [G4]  masked-% from train_on_responses_only over a sample of rows (abort at ~0% or ~100%).
  [G5]  peak allocated memory + a step-40 / step-80 trajectory print (the high-water CLIMBS
        ~6 GB/40 steps on this box — judging at step 1 is how a run gets watchdog-killed at 45).
  [G6]  SEQ GATE: reads train-po-v3.seq-audit.json, prints how many rows exceed
        --max-seq-length IN THIS STUDENT'S VIEW, and REFUSES to start unless 0 rows truncate or
        --allow-truncation is passed. This is the bundle decision made explicit: 68 of the 255
        rows are "=== FILE:" bundles (feature-spec/feature-plan) at up to 38k tokens. Either
        train the 187-row fit file at 6144, or raise the sequence, or say --allow-truncation
        out loud.
  MERGED-GEN GATE (house law): mandatory before ANY GGUF. Written defensively — a harness
  shape error logs loudly and SKIPS the export; it never destroys a completed training run.

SERVING QUANT LAW (2026-08-19, the architect re-export): this estate serves q8_0. The
Q4_K_M mix of the Gemma-4 family decodes CUT on the GB10 (q8_0 6/6 clean vs q4_k_m 5/6 cut,
attention Q4_K the culprit). --gguf-quant defaults to q8_0; q4_k_m is reachable but shouts.

USAGE (inside the house container; the host launchers are run_po_smoke.sh / run_po_full.sh)
    python train_po.py --student gemma4 --data-path /workspace/data/train-po-v3.fit-6144.jsonl \
        --max-seq-length 6144 --max-steps 40 --skip-export      # smoke
    python train_po.py --student qwen38 --data-path /workspace/data/train-po-v3.fit-6144.jsonl \
        --max-seq-length 6144 --epochs 3                        # full
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from collections import Counter
from pathlib import Path

# ---------------------------------------------------------------------------
# Per-student defaults — ONE dict, printed at startup so the receipt shows what ran
# ---------------------------------------------------------------------------
HF_HUB = Path(os.environ.get("HF_HOME", str(Path.home() / ".cache/huggingface"))) / "hub"

GEMMA_SNAPSHOT = HF_HUB / ("models--unsloth--gemma-4-26b-a4b-it/snapshots/"
                           "60941ad6341d0b7af91277ff25c4175f08b56819")
QWEN_SNAPSHOT = HF_HUB / ("models--Qwen--Qwen3.8-27B/snapshots/"
                          "1d4bf0f2ff6012fd82039f2fa52739d0dd7c60c0")

# Names taken from the LOCAL snapshot (model.safetensors.index.json) + transformers
# models/qwen3_5/modeling_qwen3_5.py. NOT guessed.
QWEN_TEXT_TARGETS = ["q_proj", "k_proj", "v_proj", "o_proj",      # 16 full_attention layers
                     "gate_proj", "up_proj", "down_proj"]         # mlp — ALL 64 layers
# Optional, OFF by default (never validated on this box): the Gated-DeltaNet projections
# model.language_model.layers.N.linear_attn.{in_proj_qkv,in_proj_z,in_proj_b,in_proj_a,out_proj}
QWEN_DELTANET_TARGETS = ["in_proj_qkv", "in_proj_z", "out_proj"]
# Anything trainable under these names is a bug: the vision tower and the MTP head.
FROZEN_PREFIXES = ("visual.", "model.visual.", "mtp.", "model.mtp.")

STUDENTS = {
    "gemma4": {
        "model_name": "unsloth/gemma-4-26b-a4b-it",
        "snapshot": GEMMA_SNAPSHOT,
        "template_sha1": "5a538c54b0feb1e8704a38dedf6f4e4755203d80",
        "load_in_16bit": True,            # MoE QLoRA blocked (3D fused expert tensors)
        "load_in_4bit": False,
        "attn_implementation": "sdpa",    # FA2 unsupported: head_dim 512 > 256
        "instruction_part": "<|turn>user\n",
        "response_part": "<|turn>model\n",
        "leak_tokens": ["<|im_start|>", "<|im_end|>"],
        "target_modules": None,           # unsloth's finetune_* flags (experts attach via PR#4913)
        "seq_view": "gemma",              # the audit view that describes this render
        "max_seq_length": 6144,
        "lora_r": 16, "lora_alpha": 16,
        "min_trainable_pct": 1.0,         # expect ~1.88%; <1% == experts did not attach
        "strip_bos_prefix": True,         # the template emits a literal <bos>; SFTTrainer adds it
        "output_slug": "po-gemma4-26b-moe",
    },
    "qwen38": {
        "model_name": "Qwen/Qwen3.8-27B",
        "snapshot": QWEN_SNAPSHOT,
        "template_sha1": "08a763ee5e339981deac7c2761751798f063e444",
        "load_in_16bit": True,            # NO QLoRA for this family (Unsloth's own guidance)
        "load_in_4bit": False,
        "attn_implementation": "sdpa",
        "instruction_part": "<|im_start|>user\n",
        "response_part": "<|im_start|>assistant\n",
        "leak_tokens": ["<|turn>", "<|channel>", "<start_of_turn>"],
        "target_modules": QWEN_TEXT_TARGETS,
        "seq_view": "qwen-split",         # --qwen-think split (the default) == this audit view
        "max_seq_length": 6144,
        "lora_r": 16, "lora_alpha": 32,
        # MEASURED (meta-device, no weights): the full list = 0.291% trainable, the
        # attention-only trap = 0.038%. A 1.0 floor would abort a CORRECT run; 0.15 sits
        # between the two, which is the only job this number has.
        "min_trainable_pct": 0.15,
        "strip_bos_prefix": False,
        "output_slug": "po-qwen38-27b",
    },
}

# MUST MATCH stage_po_v3.py:split_think() — the Qwen reasoning_content lift. If you change one,
# change the other and re-run stage_po_v3.py so the seq audit still describes the real render.
THINK_RE = re.compile(r"\A\s*<think>(.*?)</think>\s*", re.DOTALL)


def split_think(content: str):
    """Lift a LEADING inline <think>...</think> out of assistant content.

    Returns (reasoning, remainder). No leading think block -> ("", content) unchanged.
    MUST MATCH stage_po_v3.py:split_think().
    """
    m = THINK_RE.match(content)
    if not m:
        return "", content
    return m.group(1).strip(), content[m.end():]


DOUBLE_THINK = "</think>\n\n<think>"   # the naive-render signature we refuse to train on


def sha1_file(path: Path) -> str:
    return hashlib.sha1(Path(path).read_bytes()).hexdigest()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def parse_args(argv=None):
    p = argparse.ArgumentParser(
        description="PO bake-off trainer (gemma4 | qwen38) — corpus v3, house gates G1-G6")
    p.add_argument("--student", required=True, choices=sorted(STUDENTS),
                   help="Which student to train. Every other default resolves from this.")
    p.add_argument("--model-name", default=None, help="Override the student's base model")
    p.add_argument("--data-path", default="/workspace/data/train-po-v3.jsonl",
                   help="Staged corpus (default: the 255-row file). "
                        "/workspace/data/train-po-v3.fit-6144.jsonl is the NO-TRUNCATION "
                        "option at --max-seq-length 6144 (187 rows; drops the 68 long bundles).")
    p.add_argument("--seq-audit", default="/workspace/data/train-po-v3.seq-audit.json",
                   help="[G6] per-row token counts from stage_po_v3.py")
    p.add_argument("--output-dir", default=None,
                   help="Default /workspace/output/<student output_slug>")
    p.add_argument("--max-seq-length", type=int, default=None)
    p.add_argument("--lora-r", type=int, default=None)
    p.add_argument("--lora-alpha", type=int, default=None)
    p.add_argument("--lora-dropout", type=float, default=0.0)
    p.add_argument("--lr", type=float, default=2e-4)
    p.add_argument("--batch-size", type=int, default=1)
    p.add_argument("--grad-accum", type=int, default=4)
    p.add_argument("--warmup-steps", type=int, default=10)
    p.add_argument("--epochs", type=int, default=3)
    p.add_argument("--max-steps", type=int, default=None, help="Override epochs (smoke: 40)")
    p.add_argument("--logging-steps", type=int, default=1)
    p.add_argument("--save-steps", type=int, default=200)
    p.add_argument("--seed", type=int, default=3407)
    p.add_argument("--report-to", default="none", choices=["none", "wandb", "tensorboard"])
    p.add_argument("--attn-implementation", default=None)
    # student-specific knobs
    p.add_argument("--qwen-think", default="split", choices=["split", "literal"],
                   help="qwen38: 'split' lifts the inline <think> into reasoning_content (the "
                        "audited view). 'literal' reproduces the naive DOUBLE-think render.")
    p.add_argument("--qwen-reasoning-effort", default="xhigh",
                   choices=["xhigh", "high", "medium", "low"],
                   help="qwen38: passed to the template explicitly (its own default is xhigh)")
    p.add_argument("--qwen-deltanet-proj", action="store_true",
                   help="qwen38: ALSO target the Gated-DeltaNet projections "
                        f"{QWEN_DELTANET_TARGETS} (never validated on this box; off by default "
                        f"— the MLP targets already reach all 64 layers)")
    p.add_argument("--chat-template-file", default=None,
                   help="Override the pinned template file (default: the student's snapshot)")
    p.add_argument("--allow-template-drift", action="store_true",
                   help="Proceed when the template sha1 does not match the pin (LOUD)")
    # gates
    p.add_argument("--min-trainable-pct", type=float, default=None,
                   help="[G1] abort below this (default: the student's, see startup table)")
    p.add_argument("--allow-low-trainable", action="store_true")
    p.add_argument("--min-adapter-layers", type=int, default=64,
                   help="[G1b] qwen38: distinct layer indices that must carry a LoRA adapter")
    p.add_argument("--allow-truncation", action="store_true",
                   help="[G6] proceed even though rows exceed --max-seq-length (they will be "
                        "silently cut mid-answer). Say it out loud or use the fit- file.")
    p.add_argument("--mask-sample", type=int, default=16,
                   help="[G4] how many rows to measure masking over")
    p.add_argument("--mem-probe-steps", default="1,40,80",
                   help="[G5] steps at which to print the memory trajectory")
    # export
    p.add_argument("--gguf-quant", default="q8_0", choices=["q8_0", "f16", "q4_k_m"],
                   help="SERVING LAW 2026-08-19: this estate serves q8_0. q4_k_m decodes CUT "
                        "for the Gemma-4 family on the GB10 (q8_0 6/6 clean vs q4_k_m 5/6).")
    p.add_argument("--skip-export", action="store_true",
                   help="Smoke setting: stop after training (no merge, no gate, no GGUF)")
    p.add_argument("--gate-rows", type=int, default=8,
                   help="Merged-gen gate: how many training rows to generate on")
    p.add_argument("--gate-max-new", type=int, default=512)
    p.add_argument("--force-gguf", action="store_true",
                   help="Export GGUF even if the merged-gen gate FAILED or could not run "
                        "(house law says do not; this exists for a named exception)")
    p.add_argument("--gate-only", action="store_true",
                   help="Run ONLY the merged-gen gate against an existing merged-16bit dir")
    p.add_argument("--resume", action="store_true")
    p.add_argument("--dry-run", action="store_true",
                   help="Resolve defaults, run [G6] and the CPU-side checks, then STOP. "
                        "No model is loaded, no GPU is touched.")
    return p.parse_args(argv)


def resolve(args):
    s = dict(STUDENTS[args.student])
    s["model_name"] = args.model_name or s["model_name"]
    s["max_seq_length"] = args.max_seq_length or s["max_seq_length"]
    s["lora_r"] = args.lora_r or s["lora_r"]
    s["lora_alpha"] = args.lora_alpha or s["lora_alpha"]
    s["attn_implementation"] = args.attn_implementation or s["attn_implementation"]
    s["min_trainable_pct"] = (args.min_trainable_pct if args.min_trainable_pct is not None
                              else s["min_trainable_pct"])
    s["output_dir"] = args.output_dir or f"/workspace/output/{s['output_slug']}"
    s["chat_template_file"] = Path(args.chat_template_file) if args.chat_template_file \
        else Path(s["snapshot"]) / "chat_template.jinja"
    if args.student == "qwen38":
        s["target_modules"] = list(QWEN_TEXT_TARGETS)
        if args.qwen_deltanet_proj:
            s["target_modules"] += QWEN_DELTANET_TARGETS
        if args.qwen_think == "literal":
            s["seq_view"] = "qwen-literal"
    return s


def print_defaults(args, s):
    print("=" * 78)
    print(f"train_po.py — student {args.student}")
    print("=" * 78)
    rows = [
        ("model_name", s["model_name"]),
        ("snapshot (pin)", s["snapshot"]),
        ("chat_template_file", s["chat_template_file"]),
        ("template sha1 pin", s["template_sha1"]),
        ("load_in_16bit / 4bit", f"{s['load_in_16bit']} / {s['load_in_4bit']}"),
        ("attn_implementation", s["attn_implementation"]),
        ("instruction_part", repr(s["instruction_part"])),
        ("response_part", repr(s["response_part"])),
        ("target_modules", s["target_modules"] or "unsloth finetune_* flags (MoE experts)"),
        ("frozen by name", FROZEN_PREFIXES if args.student == "qwen38" else "(n/a)"),
        ("seq audit view", s["seq_view"]),
        ("max_seq_length", s["max_seq_length"]),
        ("lora r / alpha / drop", f"{s['lora_r']} / {s['lora_alpha']} / {args.lora_dropout}"),
        ("lr / bs / grad-accum", f"{args.lr} / {args.batch_size} / {args.grad_accum}"),
        ("epochs / max_steps", f"{args.epochs} / {args.max_steps}"),
        ("min_trainable_pct [G1]", s["min_trainable_pct"]),
        ("min_adapter_layers[G1b]", args.min_adapter_layers if args.student == "qwen38" else "(n/a)"),
        ("qwen think mode", f"{args.qwen_think} (effort {args.qwen_reasoning_effort})"
                            if args.student == "qwen38" else "(n/a)"),
        ("data_path", args.data_path),
        ("seq_audit", args.seq_audit),
        ("output_dir", s["output_dir"]),
        ("gguf_quant", f"{args.gguf_quant}   (estate law 2026-08-19: serve q8_0)"),
    ]
    for k, v in rows:
        print(f"  {k:<26} {v}")
    print("=" * 78)


# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------
def load_staged(path: str):
    rows = []
    with open(path) as f:
        for i, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                o = json.loads(line)
            except json.JSONDecodeError as e:
                sys.exit(f"ABORT: {path}:{i} is not JSON: {e}")
            msgs = o.get("messages") or []
            roles = [m.get("role") for m in msgs]
            if not msgs or roles[-1] != "assistant":
                sys.exit(f"ABORT: {path}:{i} does not end in an assistant turn ({roles})")
            meta = o.get("metadata") or {}
            rows.append({"messages": [{"role": m["role"], "content": m["content"]} for m in msgs],
                         "row_id": meta.get("row_id", f"row-{i:04d}"),
                         "source": meta.get("source", "?"),
                         "mode": meta.get("mode") or "?"})
    if not rows:
        sys.exit(f"ABORT: no rows in {path}")
    print(f"Loaded {len(rows)} rows from {path}")
    print(f"  by source: {dict(Counter(r['source'] for r in rows))}")
    print(f"  by mode  : {dict(Counter(r['mode'] for r in rows))}")
    print(f"  with a system turn: {sum(1 for r in rows if r['messages'][0]['role'] == 'system')}"
          f" / {len(rows)}  (the 84 trace rows have none — preserved, not invented)")
    return rows


def gate_g6_seq(args, s, rows):
    """[G6] seq gate — the bundle decision made explicit. Pure arithmetic over the audit file."""
    view = s["seq_view"]
    limit = s["max_seq_length"]
    p = Path(args.seq_audit)
    if not p.is_file():
        sys.exit(f"\nABORT [G6]: seq audit {p} not found. Run stage_po_v3.py "
                 f"(host, CPU) first — the gate refuses to guess sequence lengths.\n")
    audit = json.loads(p.read_text())
    if view not in audit.get("views", []):
        sys.exit(f"\nABORT [G6]: audit has views {audit.get('views')}, need {view!r}.\n")
    by_id = {r["row_id"]: r["tokens"] for r in audit["rows"]}
    missing = [r["row_id"] for r in rows if r["row_id"] not in by_id]
    counts = [(r, by_id[r["row_id"]][view]) for r in rows if r["row_id"] in by_id]
    over = sorted([(r, n) for r, n in counts if n > limit], key=lambda x: -x[1])
    vals = sorted(n for _, n in counts)
    med = vals[len(vals) // 2] if vals else 0
    print(f"[G6] seq gate | view={view} limit={limit} | rows audited {len(counts)}/{len(rows)}"
          f" | median {med} | max {vals[-1] if vals else 0} | over-limit {len(over)}")
    for r, n in over[:10]:
        print(f"       over: {n:>7} tok  {r['source']:<10} {r['mode']:<13} {r['row_id'][:40]}")
    if len(over) > 10:
        print(f"       ... and {len(over)-10} more")
    if over:
        by_src = dict(Counter(r["source"] for r, _ in over))
        by_mode = dict(Counter(r["mode"] for r, _ in over))
        print(f"[G6] over-limit by source {by_src} by mode {by_mode}")
    if missing:
        print(f"[G6] {len(missing)} row(s) NOT in the audit (e.g. {missing[:3]}) — the audit "
              f"does not describe this data file.")
    if (over or missing) and not args.allow_truncation:
        sys.exit(
            f"\nABORT [G6]: {len(over)} row(s) exceed max_seq_length={limit} in the {view} view"
            f"{f' and {len(missing)} row(s) are unaudited' if missing else ''}. They would be cut "
            f"mid-answer and the model would learn truncated targets.\n"
            f"  THE BUNDLE DECISION — pick one, out loud:\n"
            f"   (a) --data-path /workspace/data/train-po-v3.fit-6144.jsonl  (187 rows, 0 cut at "
            f"6144; drops the feature-spec/feature-plan '=== FILE:' bundles)\n"
            f"   (b) --max-seq-length <bigger>  (MEASURED CEILING on this box: 6144 completed at "
            f"63.2 GB allocated; 8192 climbed to ~114 GB system and was watchdog-killed at step "
            f"45 — the bundles reach 38k tokens, so no reachable sequence fits them)\n"
            f"   (c) --allow-truncation  (train on cut targets deliberately)\n")
    if over or missing:
        print(f"[G6] --allow-truncation given: proceeding with {len(over)} truncated row(s).")
    return {"view": view, "limit": limit, "over": len(over), "missing": len(missing),
            "median": med, "max": vals[-1] if vals else 0}


def build_texts(rows, tokenizer, args, s):
    """Render every row through the PINNED template. Returns list[str]."""
    texts = []
    for r in rows:
        msgs = []
        for m in r["messages"]:
            if (m["role"] == "assistant" and args.student == "qwen38"
                    and args.qwen_think == "split"):
                reasoning, rest = split_think(m["content"])
                msgs.append({"role": "assistant", "reasoning_content": reasoning,
                             "content": rest})
            else:
                msgs.append(dict(m))
        kw = {}
        if args.student == "qwen38":
            kw["reasoning_effort"] = args.qwen_reasoning_effort
        t = tokenizer.apply_chat_template(msgs, tokenize=False, add_generation_prompt=False, **kw)
        if s["strip_bos_prefix"]:
            t = t.removeprefix("<bos>")
        texts.append(t)
    return texts


def gate_g2_render(texts, args, s):
    """[G2] markers present, other student's markers absent, no double <think>."""
    sample = texts[0]
    print(f"\n--- [G2] first rendered example (first 700 chars) ---\n{sample[:700]}\n--- end ---")
    have_i = s["instruction_part"] in sample
    have_r = s["response_part"] in sample
    leaked = [t for t in s["leak_tokens"] if t in sample]
    print(f"[G2] markers: instruction {s['instruction_part']!r}={have_i}  "
          f"response {s['response_part']!r}={have_r}  foreign-token leak={leaked or 'none'}")
    if not (have_i and have_r):
        sys.exit(f"\nABORT [G2]: expected turn markers missing — train_on_responses_only would "
                 f"mask nothing (or everything) and train==serve would be false. Check the "
                 f"pinned template file.\n")
    if leaked:
        sys.exit(f"\nABORT [G2]: foreign chat-template tokens {leaked} in the render — the wrong "
                 f"template was applied.\n")
    if args.student == "qwen38":
        dbl = [i for i, t in enumerate(texts) if DOUBLE_THINK in t]
        multi = sum(1 for t in texts if t.count("<think>") > 1)
        print(f"[G2] qwen think check: rows with the double-think signature "
              f"{DOUBLE_THINK!r}: {len(dbl)} | rows with >1 <think>: {multi} | "
              f"mode={args.qwen_think}")
        if args.qwen_think == "split" and (dbl or multi):
            sys.exit(f"\nABORT [G2]: {len(dbl)}/{multi} rows DOUBLE-emit <think> under "
                     f"--qwen-think split. split_think() has drifted from stage_po_v3.py, or the "
                     f"template changed. Fix before training — the model would learn to open an "
                     f"empty think block and then another.\n")
    return {"instruction": have_i, "response": have_r, "leak": leaked}


# ---------------------------------------------------------------------------
# Merged-generation gate (house law — mandatory before ANY GGUF)
# ---------------------------------------------------------------------------
FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL)
BUNDLE_MODES = {"feature-spec", "feature-plan"}


def po_contract_check(text: str, mode: str):
    """(ok, how, detail) for the PO serving contract.

    PO-JSON modes: strip one leading <think> block if present, then parse the payload RAW or
    from a ```json fence (the serving parser is fence-tolerant — Phase-B, 2026-08-18).
    Bundle modes (feature-spec / feature-plan): the target is a '=== FILE:' bundle, not JSON.
    """
    body = text
    m = THINK_RE.match(body)
    how = "raw"
    if m:
        body, how = body[m.end():], "think-stripped"
    if mode in BUNDLE_MODES:
        return ("=== FILE:" in body), how + "/bundle", body[:120]
    candidates = [("", body)]
    fm = FENCE_RE.search(body)
    if fm:
        candidates.append(("/fenced", fm.group(1)))
    err = "no ```json fence found"
    for label, cand in candidates:
        try:
            obj = json.loads(cand.strip())
        except Exception as e:
            err = str(e)
            continue
        if not isinstance(obj, dict):
            return False, how + label, f"top-level {type(obj).__name__}, expected object"
        return True, how + label, sorted(obj)[:8]
    return False, how, f"no parseable JSON payload ({err})"


def merged_gen_gate(merged_dir, rows, args, s):
    """Returns (verdict, report). NEVER raises: a harness error is reported, not fatal."""
    report = {"gate": "ERROR", "results": [], "note": ""}
    try:
        import random

        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer

        random.seed(args.seed)
        by_mode = {}
        for r in rows:
            by_mode.setdefault(r["mode"], []).append(r)
        picks, modes = [], sorted(by_mode)
        while len(picks) < min(args.gate_rows, len(rows)):
            for mo in modes:
                if by_mode[mo] and len(picks) < min(args.gate_rows, len(rows)):
                    picks.append(by_mode[mo].pop(random.randrange(len(by_mode[mo]))))
        tok = AutoTokenizer.from_pretrained(merged_dir)
        model = AutoModelForCausalLM.from_pretrained(merged_dir, dtype=torch.bfloat16,
                                                     device_map="auto")
        n_ok = 0
        for r in picks:
            prompt_msgs = [m for m in r["messages"] if m["role"] != "assistant"]
            kw = {"reasoning_effort": args.qwen_reasoning_effort} if args.student == "qwen38" else {}
            enc = tok.apply_chat_template(prompt_msgs, tokenize=True, add_generation_prompt=True,
                                          return_dict=True, return_tensors="pt", **kw)
            enc = {k: v.to(model.device) for k, v in enc.items()}
            out = model.generate(**enc, max_new_tokens=args.gate_max_new, do_sample=False,
                                 pad_token_id=tok.eos_token_id)
            text = tok.decode(out[0][enc["input_ids"].shape[1]:], skip_special_tokens=True)
            ok, how, detail = po_contract_check(text, r["mode"])
            n_ok += bool(ok)
            report["results"].append({"row_id": r["row_id"], "mode": r["mode"], "ok": bool(ok),
                                      "how": how, "detail": str(detail)[:200],
                                      "head": text[:200]})
            print(f"  [{'OK' if ok else 'FAIL'}:{how}] mode={r['mode']:<13} "
                  f"head={text[:70]!r}")
        report["gate"] = "PASS" if n_ok == len(picks) and picks else "FAIL"
        report["contract_clean"] = f"{n_ok}/{len(picks)}"
        del model
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
    except Exception as e:  # harness shape error — LOUD, never fatal
        report["note"] = f"{type(e).__name__}: {e}"
        print("\n" + "!" * 78)
        print(f"MERGED-GEN GATE COULD NOT RUN: {type(e).__name__}: {e}")
        print("The TRAINING RUN AND MERGED WEIGHTS ARE INTACT — this is a gate-harness fault, "
              "not a model fault. Re-run the gate alone with:\n"
              f"    python train_po.py --student {args.student} --gate-only "
              f"--output-dir {s['output_dir']} --data-path {args.data_path}")
        print("!" * 78 + "\n")
    return report["gate"], report


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------
def main(argv=None):
    args = parse_args(argv)
    s = resolve(args)
    print_defaults(args, s)

    # Template pin (CPU, cheap, before anything expensive) ---------------------
    tf = Path(s["chat_template_file"])
    if not tf.is_file():
        sys.exit(f"\nABORT: pinned chat template {tf} not found. Inside the container the HF "
                 f"cache must be mounted at /root/.cache/huggingface.\n")
    got = sha1_file(tf)
    if got != s["template_sha1"]:
        msg = (f"chat template sha1 {got} != pin {s['template_sha1']} ({tf}). train==serve is no "
               f"longer a checked fact; re-run stage_po_v3.py's audit against the new template.")
        if args.allow_template_drift:
            print(f"WARNING [template]: {msg} — proceeding on --allow-template-drift")
        else:
            sys.exit(f"\nABORT [template]: {msg}\n")
    else:
        print(f"[template] pinned OK sha1={got} ({tf})")

    rows = load_staged(args.data_path)
    g6 = gate_g6_seq(args, s, rows)          # [G6] runs BEFORE any weights are touched

    if args.dry_run:
        print("\n--dry-run: defaults resolved, template pinned, [G6] evaluated. "
              "No model loaded, no GPU touched. Stopping here.")
        return 0

    if args.gate_only:
        merged_dir = os.path.join(s["output_dir"], "merged-16bit")
        print(f"\n=== MERGED-GEN GATE ONLY -> {merged_dir} ===")
        verdict, report = merged_gen_gate(merged_dir, rows, args, s)
        out = os.path.join(s["output_dir"], "merged-gen-gate.json")
        try:
            json.dump(report, open(out, "w"), indent=2)
            print(f"MERGED-GEN GATE: {verdict} -> {out}")
        except Exception as e:
            print(f"(could not write {out}: {e})")
        return 0 if verdict == "PASS" else 1

    # ---- heavy imports only past this point ---------------------------------
    import torch
    from datasets import Dataset
    from unsloth import FastModel
    from unsloth.chat_templates import train_on_responses_only
    from transformers import TrainerCallback
    from trl import SFTConfig, SFTTrainer

    print(f"\nLoading {s['model_name']} | 16bit={s['load_in_16bit']} 4bit={s['load_in_4bit']} "
          f"| seq {s['max_seq_length']} | attn {s['attn_implementation']}")
    model, tokenizer = FastModel.from_pretrained(
        model_name=s["model_name"],
        max_seq_length=s["max_seq_length"],
        dtype=None,
        load_in_4bit=s["load_in_4bit"],
        load_in_16bit=s["load_in_16bit"],
        full_finetuning=False,
        use_gradient_checkpointing="unsloth",
        attn_implementation=s["attn_implementation"],
    )

    # [G3] attention implementation (+ fla probe for qwen38) -------------------
    impl = getattr(getattr(model, "config", None), "_attn_implementation", "unknown")
    print(f"[G3] attention implementation: {impl}")
    if "flash" in str(impl).lower() and args.student == "gemma4":
        print("WARNING [G3]: FA2 on Gemma 4 will crash (head_dim 512 > FA2's 256) — expected sdpa")
    if args.student == "qwen38":
        try:
            import fla  # noqa: F401
            fla_ok, fla_ver = True, getattr(fla, "__version__", "?")
        except Exception as e:
            fla_ok, fla_ver = False, f"{type(e).__name__}"
        print(f"[G3] flash-linear-attention importable: {fla_ok} ({fla_ver}). 48 of the 64 layers "
              f"are Gated-DeltaNet; WITHOUT fla they run the slow pure-PyTorch path (a GB10 "
              f"report measured 451 -> 3,461 tok/s after installing it). Not installed on this "
              f"box as of 2026-08-20 — this line is the receipt either way.")

    # Force the PINNED template (unsloth may substitute its own) ---------------
    tokenizer.chat_template = tf.read_text(encoding="utf-8")
    print(f"[template] applied pinned file to the tokenizer ({len(tokenizer.chat_template)} chars)")

    # LoRA --------------------------------------------------------------------
    try:  # PEFT torchao version-gate workaround (TASK-REV-G4R1) — we don't use torchao.
        import peft.import_utils
        import peft.tuners.lora.torchao
        peft.import_utils.is_torchao_available = lambda: False
        peft.tuners.lora.torchao.is_torchao_available = lambda: False
    except Exception as e:
        print(f"(torchao shim skipped: {e})")

    peft_kwargs = dict(
        finetune_vision_layers=False,       # tower frozen; asserted BY NAME below
        finetune_language_layers=True,
        finetune_attention_modules=True,
        finetune_mlp_modules=True,
        r=s["lora_r"], lora_alpha=s["lora_alpha"], lora_dropout=args.lora_dropout,
        bias="none", random_state=args.seed,
    )
    if s["target_modules"]:
        peft_kwargs["target_modules"] = s["target_modules"]
    try:
        model = FastModel.get_peft_model(model, **peft_kwargs)
    except TypeError as e:
        sys.exit(f"\nABORT: FastModel.get_peft_model rejected {sorted(peft_kwargs)}: {e}\n"
                 f"Do NOT drop target_modules to work around this — for qwen38 that silently "
                 f"trains the 16 attention layers only (0.039%).\n")

    # [G1] trainable-% --------------------------------------------------------
    trainable = sum(p.numel() for p in model.parameters() if p.requires_grad)
    total = sum(p.numel() for p in model.parameters())
    pct = 100 * trainable / max(total, 1)
    print(f"[G1] Trainable params: {trainable:,} / {total:,} ({pct:.3f}%) | floor "
          f"{s['min_trainable_pct']}% | expect ~1.88% (gemma4, experts attached) / 0.291% "
          f"(qwen38 attn+mlp over 64 layers; 0.038% == attention-only = the trap)")
    if pct < s["min_trainable_pct"] and not args.allow_low_trainable:
        sys.exit(f"\nABORT [G1]: trainable% {pct:.3f} < {s['min_trainable_pct']}. "
                 f"gemma4: the MoE experts did not attach (Unsloth #4907 / PR #4913 — needs a "
                 f"post-PR build). qwen38: the target list did not reach the MLPs. "
                 f"--allow-low-trainable overrides (NOT recommended).\n")

    # [G1b] qwen38: per-layer attach + tower/MTP freeze ------------------------
    if args.student == "qwen38":
        lora_layers, attn_layers, mlp_layers = set(), set(), set()
        for name, p in model.named_parameters():
            if not p.requires_grad or "lora_" not in name:
                continue
            m = re.search(r"layers\.(\d+)\.", name)
            if not m:
                continue
            idx = int(m.group(1))
            lora_layers.add(idx)
            if "self_attn" in name:
                attn_layers.add(idx)
            if ".mlp." in name:
                mlp_layers.add(idx)
        print(f"[G1b] adapters on {len(lora_layers)} distinct layer indices "
              f"(attention {len(attn_layers)}, mlp {len(mlp_layers)}) | floor "
              f"{args.min_adapter_layers}. The 48 Gated-DeltaNet layers only carry an adapter "
              f"via .mlp.* — attention-only would show 16.")
        if len(lora_layers) < args.min_adapter_layers:
            sys.exit(f"\nABORT [G1b]: only {len(lora_layers)} layers carry a LoRA adapter "
                     f"(need {args.min_adapter_layers}). The DeltaNet layers are NOT being "
                     f"trained — this tune would be a near no-op on 3/4 of the model.\n")
        bad = [n for n, p in model.named_parameters()
               if p.requires_grad and any(pref in n for pref in FROZEN_PREFIXES)]
        print(f"[G1b] vision-tower / MTP freeze: {len(bad)} trainable param(s) under "
              f"{FROZEN_PREFIXES}")
        if bad:
            sys.exit(f"\nABORT [G1b]: LoRA capacity is being spent on the vision tower / MTP "
                     f"head: {bad[:5]}{' ...' if len(bad) > 5 else ''}. Tighten target_modules "
                     f"(the tower's linears are named qkv / proj / linear_fc1 / linear_fc2).\n")

    # Dataset + [G2] ----------------------------------------------------------
    texts = build_texts(rows, tokenizer, args, s)
    g2 = gate_g2_render(texts, args, s)
    dataset = Dataset.from_list([{"text": t, "row_id": r["row_id"], "mode": r["mode"]}
                                 for t, r in zip(texts, rows)])

    # Trainer -----------------------------------------------------------------
    use_bf16 = torch.cuda.is_bf16_supported()
    sft_kwargs = dict(
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
        seed=args.seed,
        output_dir=s["output_dir"],
        report_to=args.report_to,
        fp16=not use_bf16,
        bf16=use_bf16,
    )
    # trl renamed SFTConfig's sequence cap (max_seq_length -> max_length). Try both, then
    # neither, rather than dying on a keyword after the model is already resident.
    training_args = None
    for key in ("max_length", "max_seq_length", None):
        try:
            kw = dict(sft_kwargs)
            if key:
                kw[key] = s["max_seq_length"]
            training_args = SFTConfig(**kw)
            print(f"[trainer] SFTConfig sequence cap passed as {key or '(not passed — trl will '
                  f'use its own default; unsloth caps at load time)'}")
            break
        except TypeError as e:
            print(f"[trainer] SFTConfig rejected {key!r}: {e}")
    if training_args is None:
        sys.exit("\nABORT: could not construct SFTConfig — check the trl pin (house: 0.26.1).\n")

    trainer = SFTTrainer(model=model, tokenizer=tokenizer, train_dataset=dataset,
                         eval_dataset=None, args=training_args)
    trainer = train_on_responses_only(trainer,
                                      instruction_part=s["instruction_part"],
                                      response_part=s["response_part"])

    # [G4] masking ------------------------------------------------------------
    n = min(args.mask_sample, len(trainer.train_dataset))
    pcts = []
    for i in range(n):
        labels = trainer.train_dataset[i]["labels"]
        pcts.append(100 * sum(1 for x in labels if x == -100) / max(len(labels), 1))
    mean_pct = sum(pcts) / max(len(pcts), 1)
    print(f"[G4] response-only masking over {n} rows: mean {mean_pct:.1f}% masked "
          f"(min {min(pcts):.1f}% max {max(pcts):.1f}%). PO prompts are long (brief + context) "
          f"and answers substantial, so a MODERATE-to-HIGH masked% is expected. ~0% or ~100% "
          f"means the markers are wrong.")
    if mean_pct < 1.0 or mean_pct > 99.0:
        sys.exit(f"\nABORT [G4]: masked% {mean_pct:.1f} is ~0 or ~100 — train_on_responses_only "
                 f"did not find {s['instruction_part']!r} / {s['response_part']!r}.\n")

    # [G5] trajectory callback ------------------------------------------------
    probe_steps = {int(x) for x in str(args.mem_probe_steps).split(",") if x.strip()}

    class MemTrajectory(TrainerCallback):
        def on_step_end(self, cfg, state, control, **kw):
            if state.global_step in probe_steps and torch.cuda.is_available():
                avail = "?"
                try:
                    for line in open("/proc/meminfo"):
                        if line.startswith("MemAvailable"):
                            avail = f"{int(line.split()[1])/1024/1024:.0f}GiB"
                except Exception:
                    pass
                print(f"[G5] step {state.global_step}: allocated "
                      f"{torch.cuda.memory_allocated()/1e9:.1f} GB | peak "
                      f"{torch.cuda.max_memory_allocated()/1e9:.1f} GB | host MemAvailable "
                      f"{avail} (the high-water CLIMBS ~6 GB/40 steps — judge at 40 and 80)")

    trainer.add_callback(MemTrajectory())

    print(f"\n{'='*72}\nTraining {args.student} | eff.batch {args.batch_size*args.grad_accum} | "
          f"lr {args.lr} | "
          f"{'steps '+str(args.max_steps) if args.max_steps else 'epochs '+str(args.epochs)} | "
          f"seq {s['max_seq_length']} | rows {len(dataset)}\n{'='*72}\n")
    stats = trainer.train(resume_from_checkpoint=args.resume)
    print(f"\nTraining complete. steps={stats.global_step} loss={stats.training_loss:.4f}")
    if torch.cuda.is_available():
        print(f"[G5] peak GPU memory: {torch.cuda.max_memory_allocated()/1e9:.1f} GB "
              f"(measured ceilings on this box: seq 4096 = 61.2 GB allocated; seq 6144 = 63.2 GB; "
              f"seq 8192 climbed to ~114 GB SYSTEM and was watchdog-killed at step 45)")

    # Save --------------------------------------------------------------------
    lora_dir = os.path.join(s["output_dir"], "lora-adapter")
    merged_dir = os.path.join(s["output_dir"], "merged-16bit")
    gguf_dir = os.path.join(s["output_dir"], "gguf")
    print(f"\nSaving LoRA adapter -> {lora_dir}")
    model.save_pretrained(lora_dir)
    tokenizer.save_pretrained(lora_dir)
    receipt = {"student": args.student, "resolved": {k: str(v) for k, v in s.items()},
               "args": {k: str(v) for k, v in vars(args).items()},
               "g2": g2, "g6": g6, "g4_mean_masked_pct": mean_pct,
               "trainable_pct": pct, "steps": stats.global_step,
               "loss": float(stats.training_loss)}
    try:
        json.dump(receipt, open(os.path.join(s["output_dir"], "train-receipt.json"), "w"), indent=2)
    except Exception as e:
        print(f"(receipt not written: {e})")

    if args.skip_export:
        print("\n--skip-export: stopping before merge/gate/GGUF (smoke setting).")
        return 0

    print(f"Saving merged 16-bit -> {merged_dir}")
    model.save_pretrained_merged(merged_dir, tokenizer, save_method="merged_16bit")

    # MERGED-GEN GATE — mandatory before any GGUF -----------------------------
    print(f"\n=== MERGED-GEN GATE ({args.gate_rows} rows, house law: no GGUF before it) ===")
    verdict, report = merged_gen_gate(merged_dir, rows, args, s)
    try:
        json.dump(report, open(os.path.join(s["output_dir"], "merged-gen-gate.json"), "w"),
                  indent=2)
    except Exception as e:
        print(f"(gate report not written: {e})")
    print(f"MERGED-GEN GATE: {verdict} ({report.get('contract_clean', 'n/a')})")

    if verdict != "PASS" and not args.force_gguf:
        print(f"\nGGUF export SKIPPED — the merged-gen gate did not PASS ({verdict}). The LoRA "
              f"and merged weights are on disk; fix or re-run the gate "
              f"(--gate-only), then export. --force-gguf overrides.")
        return 0 if verdict == "ERROR" else 1

    print(f"Exporting GGUF ({args.gguf_quant}) -> {gguf_dir}")
    os.makedirs(gguf_dir, exist_ok=True)
    if args.gguf_quant == "q4_k_m":
        print("WARNING: q4_k_m — the 2026-08-19 architect re-export measured this family's "
              "Q4_K_M mix decoding CUT on the GB10 (q8_0 6/6 clean vs q4_k_m 5/6). This estate "
              "serves q8_0. Do not seat a q4_k_m export here.")
    try:
        model.save_pretrained_gguf(gguf_dir, tokenizer, quantization_method=args.gguf_quant)
        print(f"  Exported: {args.gguf_quant}")
    except Exception as e:
        print(f"  GGUF export failed (non-fatal): {e}\n  Convert manually from {merged_dir} "
              f"(scripts/llama-cpp-convert).")

    print(f"\n{'='*72}\nDone: {s['output_dir']}\nNext: the FROZEN PO exam against the untuned "
          f"baseline (never these training rows).\n{'='*72}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
