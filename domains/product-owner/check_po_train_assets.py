#!/usr/bin/env python3
"""
check_po_train_assets.py — STATIC, CPU-ONLY verification of the PO training assets.
===================================================================================
No GPU, no model weights, no service calls: tokenizers only, from the local snapshots.
Run it before a GPU window so the window is spent training, not debugging.

It checks, against the REAL staged data:
  1. split_think() in train_po.py is byte-identical to stage_po_v3.py's (they must stay in step,
     or the audited "qwen-split" token counts stop describing the real render).
  2. Both pinned chat_template.jinja files still match their sha1 pins.
  3. Every row renders through BOTH students' pinned templates; [G2]'s marker assertions run for
     real (turn markers present, foreign markers absent, and for qwen38 NO double <think>).
  4. The Qwen double-think cost: how many rows double-emit under --qwen-think literal (the naive
     render) vs split (the default).
  5. An EMULATION of [G4]: the masked fraction train_on_responses_only will produce, computed as
     tokens(prefix up to and including the response marker) / tokens(full render).
  6. [G6]'s arithmetic re-run over both data files x both student views.

Usage (host, the ADF venv):
    ~/Projects/appmilla_github/agentic-dataset-factory/.venv/bin/python check_po_train_assets.py
"""
from __future__ import annotations

import inspect
import json
import os
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
os.environ.setdefault("HF_HUB_OFFLINE", "1")

import stage_po_v3  # noqa: E402
import train_po  # noqa: E402

HOME = Path.home()
DATA_FULL = HOME / "fine-tuning/data/train-po-v3.jsonl"
DATA_FIT = HOME / "fine-tuning/data/train-po-v3.fit-6144.jsonl"
AUDIT = HOME / "fine-tuning/data/train-po-v3.seq-audit.json"

fails = []


def meta_probe():
    """Instantiate Qwen3.8's architecture on the META device (allocates nothing, touches no GPU)
    and prove, by real module names, that:
      * the default target list reaches 64 distinct layer indices (the 48 Gated-DeltaNet layers
        included, via .mlp.*) while the bare attention list reaches only 16;
      * neither touches the vision tower (its linears are qkv / proj / linear_fc1 / linear_fc2);
      * a LOOSE 'anything with proj/qkv' match would grab the tower — the trap FROZEN_PREFIXES
        and [G1b] exist for.
    """
    os.environ["CUDA_VISIBLE_DEVICES"] = ""       # belt and braces: no GPU work here
    import torch
    from transformers import AutoConfig
    from transformers.models.qwen3_5 import Qwen3_5ForConditionalGeneration

    args = train_po.parse_args(["--student", "qwen38"])
    s = train_po.resolve(args)
    cfg = AutoConfig.from_pretrained(str(s["snapshot"]))
    with torch.device("meta"):
        m = Qwen3_5ForConditionalGeneration._from_config(cfg)
    lin = {n: mod for n, mod in m.named_modules() if isinstance(mod, torch.nn.Linear)}
    total = sum(p.numel() for p in m.parameters())
    r = s["lora_r"]

    def suffix_match(name, targets):     # how PEFT matches target_modules
        return any(name.endswith("." + t) or name == t for t in targets)

    import re as _re
    for label, targets, want_layers in (
            ("default list", s["target_modules"], 64),
            ("attention-only TRAP", ["q_proj", "k_proj", "v_proj", "o_proj"], 16)):
        hits = [n for n in lin if suffix_match(n, targets)]
        layers = {int(mm.group(1)) for n in hits
                  if (mm := _re.search(r"layers\.(\d+)\.", n))}
        lp = sum(r * (lin[n].in_features + lin[n].out_features) for n in hits)
        frozen_hits = [n for n in hits if any(p in n for p in train_po.FROZEN_PREFIXES)]
        print(f"  {label:<21} modules={len(hits):>4}  distinct layer idx={len(layers):>3}  "
              f"lora(r={r})={lp:,} = {100*lp/total:.3f}% of {total:,}  "
              f"frozen-prefix hits={len(frozen_hits)}")
        check(f"{label}: reaches {want_layers} layer indices", len(layers) == want_layers)
        check(f"{label}: touches NO vision-tower / MTP module", not frozen_hits)
    loose = [n for n in lin if "proj" in n.split(".")[-1]
             or n.split(".")[-1] in ("qkv", "linear_fc1", "linear_fc2")]
    tower = [n for n in loose if "visual." in n]
    print(f"  a LOOSE 'proj|qkv|linear_fc' match would take {len(loose)} modules, "
          f"{len(tower)} of them in the vision tower, e.g. {tower[:2]}")
    check("a loose match WOULD hit the tower (so the freeze assertion is load-bearing)",
          len(tower) > 0)


def check(label, ok, detail=""):
    print(f"[{'PASS' if ok else 'FAIL'}] {label}{(' — ' + detail) if detail else ''}")
    if not ok:
        fails.append(label)


def main():
    print("=" * 78)
    print("1. split_think() parity  (train_po.py vs stage_po_v3.py)")
    a = inspect.getsource(train_po.split_think)
    b = inspect.getsource(stage_po_v3.split_think)
    body_a = "".join(l.strip() for l in a.splitlines() if "MUST MATCH" not in l and l.strip())
    body_b = "".join(l.strip() for l in b.splitlines() if "MUST MATCH" not in l and l.strip())
    check("split_think source identical (modulo the cross-reference comment)", body_a == body_b)
    check("THINK_RE pattern identical", train_po.THINK_RE.pattern == stage_po_v3.THINK_RE.pattern,
          train_po.THINK_RE.pattern)

    rows = train_po.load_staged(str(DATA_FULL))
    same = sum(1 for r in rows
               if train_po.split_think(r["messages"][-1]["content"])
               == stage_po_v3.split_think(r["messages"][-1]["content"]))
    n_think = sum(1 for r in rows if train_po.split_think(r["messages"][-1]["content"])[0])
    check(f"both split_think agree on all {len(rows)} staged rows", same == len(rows),
          f"{n_think} rows carry a leading inline <think>")

    print("\n" + "=" * 78)
    print("2. pinned chat templates")
    toks = {}
    for student in ("gemma4", "qwen38"):
        args = train_po.parse_args(["--student", student])
        s = train_po.resolve(args)
        got = train_po.sha1_file(s["chat_template_file"])
        check(f"{student} template sha1", got == s["template_sha1"], got)
        from transformers import AutoTokenizer
        t = AutoTokenizer.from_pretrained(str(s["snapshot"]))
        t.chat_template = Path(s["chat_template_file"]).read_text(encoding="utf-8")
        toks[student] = (args, s, t)

    print("\n" + "=" * 78)
    print("3+4. render every row, run [G2] for real, measure the double-think cost")
    rendered = {}
    for student, (args, s, tok) in toks.items():
        print(f"\n---------------- {student} ----------------")
        texts = train_po.build_texts(rows, tok, args, s)
        rendered[student] = texts
        print(f"FIRST 200 CHARS: {texts[0][:200]!r}")
        train_po.gate_g2_render(texts, args, s)   # aborts the process on failure
        check(f"{student}: instruction+response markers on all {len(texts)} rows",
              all(s["instruction_part"] in t and s["response_part"] in t for t in texts))
        check(f"{student}: no foreign template tokens in any row",
              not any(x in t for t in texts for x in s["leak_tokens"]))
        if student == "qwen38":
            dbl = sum(1 for t in texts if train_po.DOUBLE_THINK in t)
            multi = sum(1 for t in texts if t.count("<think>") > 1)
            check("qwen38 split render: zero double-<think> rows", dbl == 0 and multi == 0,
                  f"double-signature {dbl}, >1 think {multi}")
            largs = train_po.parse_args(["--student", "qwen38", "--qwen-think", "literal"])
            ls = train_po.resolve(largs)
            lit = train_po.build_texts(rows, tok, largs, ls)
            ldbl = sum(1 for t in lit if train_po.DOUBLE_THINK in t)
            print(f"       (contrast) --qwen-think literal double-emits on {ldbl}/{len(lit)} rows"
                  f" — that is the render [G2] refuses")
            check("literal mode would be caught by [G2]", ldbl > 0, f"{ldbl} rows")

    print("\n" + "=" * 78)
    print("5. [G4] masking EMULATION (tokens before the response marker / total tokens)")
    for student, (args, s, tok) in toks.items():
        pcts = []
        for t in rendered[student][:64]:
            i = t.rfind(s["response_part"])
            prefix = t[:i + len(s["response_part"])]
            n_pre = len(tok(prefix, add_special_tokens=False)["input_ids"])
            n_all = len(tok(t, add_special_tokens=False)["input_ids"])
            pcts.append(100 * n_pre / max(n_all, 1))
        print(f"  {student}: mean {statistics.mean(pcts):.1f}%  median "
              f"{statistics.median(pcts):.1f}%  min {min(pcts):.1f}%  max {max(pcts):.1f}%  "
              f"(n=64 rows)")
        check(f"{student}: emulated masked% is neither ~0 nor ~100",
              1.0 < statistics.mean(pcts) < 99.0)

    print("\n" + "=" * 78)
    print("6. [G6] arithmetic over both data files x both views (limit 6144)")
    audit = json.loads(AUDIT.read_text())
    by_id = {r["row_id"]: r["tokens"] for r in audit["rows"]}
    for path in (DATA_FULL, DATA_FIT):
        rws = [json.loads(l) for l in open(path)]
        ids = [r["metadata"]["row_id"] for r in rws]
        for view in ("gemma", "qwen-split"):
            vals = [by_id[i][view] for i in ids if i in by_id]
            over = [v for v in vals if v > 6144]
            print(f"  {path.name:<30} {view:<11} n={len(vals):>3} audited "
                  f"median={int(statistics.median(vals)):>5} max={max(vals):>6} "
                  f">6144={len(over)}")
            check(f"{path.name}/{view}: every row audited", len(vals) == len(ids))
            if path == DATA_FIT:
                check(f"{path.name}/{view}: zero over 6144", not over)

    print("\n" + "=" * 78)
    print("7. qwen38 target-list proof on a META-DEVICE build (no weights, no GPU, no memory)")
    meta_probe()

    print("\n" + "=" * 78)
    print(f"RESULT: {'ALL CHECKS PASS' if not fails else 'FAILURES: ' + ', '.join(fails)}")
    return 0 if not fails else 1


if __name__ == "__main__":
    sys.exit(main())
