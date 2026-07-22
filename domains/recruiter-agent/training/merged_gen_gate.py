#!/usr/bin/env python3
"""
merged_gen_gate.py — the MERGED-GENERATION GATE (mandatory pre-GGUF verdict) for the recruiter tune
====================================================================================================
RUNBOOK-dcl-fine-tune v1.2 bakes in a hard process rule: **merged-16bit generation sanity is
mandatory before any GGUF/serve step** (the DCL v1 run skipped it and burned a probe cycle on a
model that teacher-forced perfectly but collapsed under free generation). This is that gate, re-aimed
at the recruiter's serve contract.

The gate generates the recruiter's FIRST drafting turn on held-out VAL prompts (never train), for
BOTH the tuned merged model AND the stock Qwen3-4B-Instruct-2507 base — an apples-to-apples A/B on
the same prompts — then verifies:

  * every output PARSES under the REAL serve contract (``office_manager.hire.protocol.parse_turn``);
  * each draft PASSES the office's OWN checkers + per-class predicate (the exact ``acceptance.accept``
    the corpus was built on: deckhand config-check / office pipeline validate / the sorting-rule
    label / placeholder goldens / honest walls / the injection-probe grant check);
  * the tuned pass-rate is MATERIALLY ABOVE the stock base — the durable cure for the 2026-07-21
    gate refusal (stock workhorse failed 4/5 + a disqualifying egress grant).

Two modes (the split respects the fences: generation is a Spark-GPU job in the NVIDIA container;
grading runs the office checkers read-only under office-manager's venv on the CPU box):

  --mode generate  (IN-CONTAINER, Spark GPU)
      Load a model dir (merged-16bit, or the stock base id), FORCE the stock Qwen3-2507 chat
      template, and greedily generate the assistant turn for each val prompt. Writes outputs.jsonl:
      {row_id, class, expected_class, system, user, output}. Run once per model (tuned + stock).

  --mode grade  (office venv, CPU box)
      Read one or more outputs.jsonl, run parse_turn + acceptance.accept per row, and print a
      per-class + overall pass table. Two files ⇒ an A/B delta line.

Usage:
    # in-container, per model:
    python merged_gen_gate.py --mode generate \\
      --model /workspace/output/recruiter-qwen3-4b/merged-16bit \\
      --prompts /workspace/data/val-recruiter.jsonl \\
      --chat-template-file /workspace/scripts/qwen3-2507-stock.jinja \\
      --out /workspace/output/recruiter-qwen3-4b/gate/tuned-outputs.jsonl --label tuned
    python merged_gen_gate.py --mode generate \\
      --model Qwen/Qwen3-4B-Instruct-2507 --prompts /workspace/data/val-recruiter.jsonl \\
      --chat-template-file /workspace/scripts/qwen3-2507-stock.jinja \\
      --out /workspace/output/recruiter-qwen3-4b/gate/stock-outputs.jsonl --label stock

    # grade (office venv, domain on PYTHONPATH):
    OFFICE_AGENTS_ROOT=/tmp PYTHONPATH="$DOMAIN" ./.venv/bin/python \\
      "$DOMAIN/training/merged_gen_gate.py" --mode grade \\
      --tuned gate/tuned-outputs.jsonl --stock gate/stock-outputs.jsonl \\
      --held-root ~/office-authoring

Heavy ML imports are DEFERRED so host py_compile / --help stay dep-free.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from collections import defaultdict
from pathlib import Path


def _load_jsonl(path: Path) -> list[dict]:
    rows = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


# ---------------------------------------------------------------------------
# generate (in-container, Spark GPU)
# ---------------------------------------------------------------------------
def do_generate(args) -> int:
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer

    if not os.path.isfile(args.chat_template_file):
        sys.exit(f"ABORT: --chat-template-file {args.chat_template_file} not found (the stock "
                 f"Qwen3-2507 template is REQUIRED — train==serve).")
    stock_template = open(args.chat_template_file, encoding="utf-8").read()
    if "reasoning_content" in stock_template or "[::-1]" in stock_template:
        sys.exit("ABORT: chat-template-file looks like the hybrid-THINKING template — supply the "
                 "stock 2507 instruct template (the same one training forced).")

    prompts = _load_jsonl(Path(args.prompts))
    if args.limit:
        prompts = prompts[: args.limit]
    print(f"[generate:{args.label}] model={args.model} prompts={len(prompts)} "
          f"greedy max_new_tokens={args.max_new_tokens}")

    tok = AutoTokenizer.from_pretrained(args.model)
    tok.chat_template = stock_template  # force stock template (train==serve)
    model = AutoModelForCausalLM.from_pretrained(
        args.model, torch_dtype=torch.bfloat16, device_map="cuda")
    model.eval()

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w") as out:
        for i, row in enumerate(prompts, 1):
            msgs = row["messages"]
            system = next(m["content"] for m in msgs if m["role"] == "system")
            user = next(m["content"] for m in msgs if m["role"] == "user")
            convo = [{"role": "system", "content": system}, {"role": "user", "content": user}]
            inputs = tok.apply_chat_template(
                convo, return_tensors="pt", add_generation_prompt=True).to("cuda")
            with torch.no_grad():
                gen = model.generate(inputs, max_new_tokens=args.max_new_tokens, do_sample=False)
            output = tok.decode(gen[0][inputs.shape[1]:], skip_special_tokens=True)
            rec = {
                "row_id": row["metadata"]["row_id"],
                "class": row["metadata"]["class"],
                "expected_class": row["metadata"]["expected_class"],
                "system": system,
                "user": user,
                "output": output,
            }
            out.write(json.dumps(rec) + "\n")
            out.flush()
            if i % 5 == 0 or i == len(prompts):
                print(f"  … {i}/{len(prompts)} generated")
    print(f"[generate:{args.label}] wrote {out_path}")
    return 0


# ---------------------------------------------------------------------------
# grade (office venv, CPU box)
# ---------------------------------------------------------------------------
def _grade_file(path: Path, denylist, accept, stub_ctx) -> dict:
    rows = _load_jsonl(path)
    from office_manager.hire.protocol import parse_turn

    per_class = defaultdict(lambda: {"total": 0, "pass": 0, "parse_fail": 0})
    passes = parse_fails = 0
    detail = []
    ctx = stub_ctx()
    for r in rows:
        cls = r["expected_class"]
        per_class[cls]["total"] += 1
        raw = r["output"]
        # parse_turn is total by design; a parse that yields no message AND no files is a null turn.
        turn = parse_turn(raw)
        with tempfile.TemporaryDirectory() as td:
            res = accept(cls, raw, Path(td), denylist=denylist, estate_context=ctx)
        ok = bool(res.ok)
        if ok:
            passes += 1
            per_class[cls]["pass"] += 1
        if not turn.files:
            parse_fails += 1
            per_class[cls]["parse_fail"] += 1
        detail.append({"row_id": r["row_id"], "class": cls, "pass": ok,
                       "files": len(turn.files), "reason": res.reason})
    return {"n": len(rows), "pass": passes, "parse_fail": parse_fails,
            "per_class": {k: dict(v) for k, v in per_class.items()}, "detail": detail}


def _print_grade(label: str, g: dict) -> None:
    n = g["n"]
    rate = 100 * g["pass"] / max(n, 1)
    print(f"\n[{label}] {g['pass']}/{n} pass ({rate:.1f}%)  ·  no-file-block turns: {g['parse_fail']}")
    print(f"  {'class':<24} {'pass/total':>12}")
    for cls in sorted(g["per_class"]):
        c = g["per_class"][cls]
        print(f"  {cls:<24} {str(c['pass'])+'/'+str(c['total']):>12}   (no-file={c['parse_fail']})")


def do_grade(args) -> int:
    # office venv + domain on PYTHONPATH
    from acceptance import accept, stub_estate_context
    import denylist as denylist_mod

    dl = denylist_mod.Denylist.build(held_root=args.held_root)
    print(f"denylist: {len(dl.phrases)} phrase(s), {len(dl.file_hashes)} file-hash(es), "
          f"corpus_seen={dl.corpus_seen}")

    tuned = _grade_file(Path(args.tuned), dl, accept, stub_estate_context)
    _print_grade("tuned", tuned)

    stock = None
    if args.stock:
        stock = _grade_file(Path(args.stock), dl, accept, stub_estate_context)
        _print_grade("stock", stock)
        t = 100 * tuned["pass"] / max(tuned["n"], 1)
        s = 100 * stock["pass"] / max(stock["n"], 1)
        print(f"\n=== A/B DELTA ===  tuned {t:.1f}%  vs  stock {s:.1f}%  →  +{t - s:.1f} pts")
        verdict = "PASS (materially above stock)" if (t - s) >= args.min_delta_pts and t >= args.min_tuned_pct \
            else "REVIEW (delta or tuned floor not cleared)"
        print(f"BAR: tuned >= {args.min_tuned_pct:.0f}% AND delta >= {args.min_delta_pts:.0f} pts → {verdict}")

    if args.json_out:
        Path(args.json_out).write_text(json.dumps(
            {"tuned": tuned, "stock": stock,
             "bar": {"min_tuned_pct": args.min_tuned_pct, "min_delta_pts": args.min_delta_pts}},
            indent=2))
        print(f"\nwrote {args.json_out}")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description="Recruiter merged-generation gate (generate | grade).")
    sub = ap.add_subparsers(dest="_unused")
    ap.add_argument("--mode", required=True, choices=["generate", "grade"])

    # generate
    ap.add_argument("--model", help="[generate] model dir (merged-16bit) or HF id (stock base)")
    ap.add_argument("--prompts", help="[generate] val JSONL (held-out prompts, never train)")
    ap.add_argument("--chat-template-file", help="[generate] the stock Qwen3-2507 jinja (train==serve)")
    ap.add_argument("--out", help="[generate] outputs.jsonl path")
    ap.add_argument("--label", default="model", help="[generate] a label for logs")
    ap.add_argument("--max-new-tokens", type=int, default=2048, help="[generate]")
    ap.add_argument("--limit", type=int, default=None, help="[generate] cap prompt count")

    # grade
    ap.add_argument("--tuned", help="[grade] tuned outputs.jsonl")
    ap.add_argument("--stock", help="[grade] stock outputs.jsonl (for the A/B delta)")
    ap.add_argument("--held-root", default="~/office-authoring", help="[grade] eval-held root for the denylist")
    ap.add_argument("--min-tuned-pct", type=float, default=60.0, help="[grade] tuned pass-rate floor")
    ap.add_argument("--min-delta-pts", type=float, default=25.0, help="[grade] tuned-minus-stock floor")
    ap.add_argument("--json-out", help="[grade] write the full grade record here")

    args = ap.parse_args(argv)
    if args.mode == "generate":
        for req in ("model", "prompts", "chat_template_file", "out"):
            if not getattr(args, req):
                sys.exit(f"--{req.replace('_','-')} is required for --mode generate")
        return do_generate(args)
    else:
        if not args.tuned:
            sys.exit("--tuned is required for --mode grade")
        return do_grade(args)


if __name__ == "__main__":
    sys.exit(main())
