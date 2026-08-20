#!/usr/bin/env python3
"""
stage_po_v3.py — stage PO corpus v3 into ONE uniform trainer-ready file + seq audit
==================================================================================
Lane: PO bake-off training assets (Rich's training word 2026-08-20).
Spec: ai-transition `docs/po-lane-state-2026-08-18.md` §10 item 1 + §1.3.

WHAT IT DOES
  Reads the three v3 slices (default root
  `~/Projects/appmilla_github/agentic-dataset-factory/corpora/v3-2026-08-20/`):
    harvest/train_harvest.jsonl      13 rows  {messages:[system,user,assistant], metadata}
    synthetic/train_synthetic.jsonl 158 rows  {messages:[system,user,assistant], metadata}
    trace-export/po_player_filtered.jsonl 84  {prompt, completion, mask_prompt:true, ...}
                                              (every prompt begins with the literal "user: ")
  Writes ONE uniform file the house trainer consumes unchanged:
    ~/fine-tuning/data/train-po-v3.jsonl
      {"messages":[{"role":"system",...}?,{"role":"user",...},{"role":"assistant",...}],
       "metadata":{"mode","source","row_id","weight",...}}
  Trace rows: the leading "user: " prefix is stripped into the user turn, `completion`
  becomes the assistant turn, and `harvest.shape` becomes `metadata.mode`. Trace rows carry
  NO system turn (there is none in the export) — that is preserved, not invented.

LOSS MASKING — train-on-assistant-only for ALL rows, structurally, not per-row.
  train_coach_moe.py masks with unsloth's `train_on_responses_only(trainer,
  instruction_part=..., response_part=...)`, i.e. by the CHAT TEMPLATE's own turn markers
  ([G4] prints the masked %). That mechanism is uniform over the file and needs no per-row
  field, so the trace slice's `mask_prompt:true` / `prompt_mask_label:-100` are NOT copied
  forward as flags — they are honoured by construction (they are recorded in
  metadata.mask_prompt_source for provenance). train_po.py applies the same call per student
  (gemma4: "<|turn>user\n"/"<|turn>model\n"; qwen38: "<|im_start|>user\n"/"<|im_start|>assistant\n").

THE QWEN TEMPLATE HAZARD AND THE DECISION TAKEN (report §1.3)
  Qwen3.8-27B's own chat template (snapshot 1d4bf0f2, chat_template.jinja sha1 08a763ee5e33)
  does two things a trainer must handle:
    (1) it injects "Reasoning effort is set to xhigh. ..." into the SYSTEM turn whenever
        enable_thinking is undefined/true;
    (2) for the trailing assistant turn it ALWAYS emits `<think>\n{reasoning_content}\n</think>\n\n`
        before `content` — the `preserve_thinking` kwarg cannot suppress it, because the guard is
        `preserve_thinking is undefined or ... or loop.index0 > ns.last_query_index` and the final
        assistant turn is always past the last user index. 171 of the 255 v3 rows (harvest 13 +
        synthetic 158) carry an INLINE `<think>…</think>` at the head of assistant content, so the
        naive render produces a DOUBLE think block:
            <|im_start|>assistant\n<think>\n\n</think>\n\n<think>real reasoning</think>\n```json…
  DECISION (documented here because it is the load-bearing choice of this script):
    * The STAGED FILE STAYS BASE-MODEL-NEUTRAL. Assistant content keeps the literal
      `<think>…</think>` text exactly as the corpus authored it. That literal-text convention IS
      the Gemma convention (Gemma 4 has no `<think>` special token — it tokenises as 3 plain
      tokens), and no chat template is baked into the file.
    * PER-STUDENT RENDERING HAPPENS AT TRAIN TIME. For qwen38, train_po.py (default
      `--qwen-think split`) lifts the leading `<think>…</think>` out of `content` into the
      message's `reasoning_content` field, which the model's OWN template then renders as its
      native SINGLE think block — no double emit, and train == serve for a `--reasoning`-splitting
      server. `--qwen-think literal` reproduces the naive double-think render if ever wanted.
    * The template is PINNED BY FILE at train time (sha1 asserted) and `reasoning_effort` is passed
      explicitly (default xhigh = the template's own default), so train == serve is a checked fact.
  This audit therefore reports THREE tokenised views per row: gemma (as train_po.py renders it),
  qwen-split (as train_po.py renders it by default) and qwen-literal (the naive double-think cost).

SEQ AUDIT
  Tokenises every staged row with BOTH real tokenizers from their LOCAL snapshots (no network):
    Gemma 4  unsloth/gemma-4-26b-a4b-it @ 60941ad6...
    Qwen3.8  Qwen/Qwen3.8-27B          @ 1d4bf0f2...
  apply_chat_template view, add_generation_prompt=False (the trainer's view). Prints
  min/median/p95/max + counts >4096 / >6144 / >8192 overall, per source and per mode, and
  ASSERTS max <= --max-seq (default 6144) across the AS-TRAINED views; on violation it NAMES
  the offending rows and exits 3 (override: --allow-over-limit).
  NOTE: the Gemma view here uses the HF SNAPSHOT template. The trainer renders with unsloth's
  `get_chat_template(..., "gemma-4-thinking")`, a shorter pinned template; the snapshot view is
  therefore the conservative (>=) estimate. run_po_smoke_gemma.sh re-runs the audit in-container
  with the real unsloth template before the first step — that is the gate of record.

  --emit-fit-subset additionally writes train-po-v3.fit-<seq>.jsonl containing only the rows that
  fit --max-seq under BOTH as-trained views. Needed because §10's claim "corpus max ~5.9k tokens"
  holds for harvest+synthetic ONLY: the 84 trace rows are the long ones (§1.3 measured the 93-row
  trace slice at median ~12.9k / max ~49k tokens — their prompts embed the /feature-plan and
  /feature-spec methodology templates).

USAGE (host-side, CPU only, no GPU, no model load — tokenizers only):
    ~/Projects/appmilla_github/agentic-dataset-factory/.venv/bin/python stage_po_v3.py
    ... --max-seq 6144 --emit-fit-subset --allow-over-limit
"""

from __future__ import annotations

import argparse
import json
import os
import re
import statistics
import sys
from pathlib import Path

HOME = Path.home()
DEFAULT_CORPUS = HOME / "Projects/appmilla_github/agentic-dataset-factory/corpora/v3-2026-08-20"
DEFAULT_OUT = HOME / "fine-tuning/data/train-po-v3.jsonl"
GEMMA_SNAPSHOT = (HOME / ".cache/huggingface/hub/models--unsloth--gemma-4-26b-a4b-it/"
                  "snapshots/60941ad6341d0b7af91277ff25c4175f08b56819")
QWEN_SNAPSHOT = (HOME / ".cache/huggingface/hub/models--Qwen--Qwen3.8-27B/"
                 "snapshots/1d4bf0f2ff6012fd82039f2fa52739d0dd7c60c0")

# MUST MATCH train_po.py:split_think() — the Qwen reasoning_content lift.
THINK_RE = re.compile(r"\A\s*<think>(.*?)</think>\s*", re.DOTALL)


def split_think(content: str):
    """Lift a LEADING inline <think>...</think> out of assistant content.

    Returns (reasoning, remainder). No leading think block -> ("", content) unchanged.
    MUST MATCH train_po.py:split_think().
    """
    m = THINK_RE.match(content)
    if not m:
        return "", content
    return m.group(1).strip(), content[m.end():]


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------
def read_jsonl(path: Path):
    rows = []
    with open(path) as f:
        for i, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError as e:
                sys.exit(f"ERROR: {path}:{i} is not JSON: {e}")
    return rows


def stage_messages_slice(path: Path, source: str):
    """harvest / synthetic: {messages:[system,user,assistant], metadata} -> uniform row."""
    out = []
    for idx, o in enumerate(read_jsonl(path)):
        msgs = o.get("messages") or []
        roles = [m.get("role") for m in msgs]
        if roles[-1:] != ["assistant"] or "user" not in roles:
            sys.exit(f"ERROR: {path}#{idx} unexpected role sequence {roles}")
        meta = dict(o.get("metadata") or {})
        h = meta.get("harvest") or {}
        row_id = h.get("row_id") or f"{source}-{idx:04d}"
        out.append({
            "messages": [{"role": m["role"], "content": m["content"]} for m in msgs],
            "metadata": {
                "mode": meta.get("mode"),
                "source": source,
                "row_id": row_id,
                "weight": meta.get("weight", 1.0),
                "src_index": idx,
                "src_file": str(path),
                "mask_prompt_source": "structural (train_on_responses_only)",
                "layer": meta.get("layer"),
                "type": meta.get("type"),
                "dimension": meta.get("dimension"),
                "topic": meta.get("topic"),
            },
        })
    return out


def stage_trace_slice(path: Path, source: str = "trace"):
    """trace-export: {prompt:'user: ...', completion, mask_prompt:true} -> uniform row."""
    out = []
    stripped = 0
    for idx, o in enumerate(read_jsonl(path)):
        prompt = o.get("prompt", "")
        if prompt.startswith("user: "):
            prompt = prompt[len("user: "):]
            stripped += 1
        completion = o.get("completion", "")
        h = o.get("harvest") or {}
        out.append({
            # No system turn: the trace export has none. Not invented here.
            "messages": [{"role": "user", "content": prompt},
                         {"role": "assistant", "content": completion}],
            "metadata": {
                "mode": h.get("shape"),
                "source": source,
                "row_id": o.get("record_id") or f"{source}-{idx:04d}",
                "weight": o.get("weight", 1.0),
                "src_index": idx,
                "src_file": str(path),
                "mask_prompt_source": (
                    f"row flag mask_prompt={o.get('mask_prompt')} "
                    f"label={o.get('prompt_mask_label')} -> structural (train_on_responses_only)"),
                "session_id": o.get("session_id"),
                "iteration": o.get("iteration"),
                "dataset": o.get("dataset"),
            },
        })
    return out, stripped


# ---------------------------------------------------------------------------
# Hygiene screen (reports, never silently drops)
# ---------------------------------------------------------------------------
RUN_RE = re.compile(r"(.)\1{1999,}", re.DOTALL)


def hygiene(rows):
    flags = []
    for i, r in enumerate(rows):
        m = r["metadata"]
        a = r["messages"][-1]["content"]
        u = [x for x in r["messages"] if x["role"] == "user"][-1]["content"]
        why = []
        if not a.strip():
            why.append("empty assistant")
        if not u.strip():
            why.append("empty user")
        for label, text in (("assistant", a), ("user", u)):
            mm = RUN_RE.search(text)
            if mm:
                why.append(f"{label}: >=2000-char run of {mm.group(1)!r}")
        if m.get("mode") is None:
            why.append("no mode")
        if why:
            flags.append((i, m.get("source"), m.get("row_id"), "; ".join(why)))
    return flags


# ---------------------------------------------------------------------------
# Seq audit
# ---------------------------------------------------------------------------
def n_tokens(tok, text):
    return len(tok(text, add_special_tokens=False)["input_ids"])


def render_gemma(tok, msgs):
    return tok.apply_chat_template(msgs, tokenize=False, add_generation_prompt=False)


def render_qwen(tok, msgs, mode, reasoning_effort):
    """mode='split' -> reasoning_content lift (the train_po.py default);
       mode='literal' -> content verbatim (the naive DOUBLE-think render)."""
    out = []
    for m in msgs:
        if m["role"] == "assistant" and mode == "split":
            reasoning, rest = split_think(m["content"])
            out.append({"role": "assistant", "reasoning_content": reasoning, "content": rest})
        else:
            out.append(dict(m))
    return tok.apply_chat_template(out, tokenize=False, add_generation_prompt=False,
                                   reasoning_effort=reasoning_effort)


def describe(vals):
    v = sorted(vals)
    n = len(v)
    if n == 0:
        return dict(n=0)
    return dict(n=n, min=v[0], median=int(statistics.median(v)),
                p95=v[min(n - 1, int(round(0.95 * (n - 1))))], max=v[-1],
                over4096=sum(x > 4096 for x in v), over6144=sum(x > 6144 for x in v),
                over8192=sum(x > 8192 for x in v))


def table(title, groups, views):
    print(f"\n{title}")
    hdr = f"{'group':<14}{'view':<14}{'n':>5}{'min':>8}{'median':>9}{'p95':>9}{'max':>9}{'>4096':>7}{'>6144':>7}{'>8192':>7}"
    print(hdr)
    print("-" * len(hdr))
    for g, per_view in groups:
        for view in views:
            d = describe(per_view.get(view, []))
            if not d.get("n"):
                continue
            print(f"{g:<14}{view:<14}{d['n']:>5}{d['min']:>8}{d['median']:>9}{d['p95']:>9}"
                  f"{d['max']:>9}{d['over4096']:>7}{d['over6144']:>7}{d['over8192']:>7}")


def main():
    p = argparse.ArgumentParser(description="Stage PO corpus v3 + real-tokenizer seq audit")
    p.add_argument("--corpus-root", default=str(DEFAULT_CORPUS))
    p.add_argument("--out", default=str(DEFAULT_OUT))
    p.add_argument("--gemma-snapshot", default=str(GEMMA_SNAPSHOT))
    p.add_argument("--qwen-snapshot", default=str(QWEN_SNAPSHOT))
    p.add_argument("--max-seq", type=int, default=6144)
    p.add_argument("--qwen-reasoning-effort", default="xhigh", choices=["xhigh", "medium", "low"])
    p.add_argument("--allow-over-limit", action="store_true",
                   help="Report + name over-limit rows but exit 0 (default: exit 3)")
    p.add_argument("--emit-fit-subset", action="store_true",
                   help="Also write train-po-v3.fit-<max_seq>.jsonl (rows fitting BOTH as-trained views)")
    p.add_argument("--skip-audit", action="store_true", help="Stage only; no tokenizers loaded")
    args = p.parse_args()

    root = Path(args.corpus_root)
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    # 1. stage ---------------------------------------------------------------
    rows = []
    rows += stage_messages_slice(root / "harvest/train_harvest.jsonl", "harvest")
    trace_rows, stripped = stage_trace_slice(root / "trace-export/po_player_filtered.jsonl")
    rows += trace_rows
    rows += stage_messages_slice(root / "synthetic/train_synthetic.jsonl", "synthetic")

    by_source, by_mode = {}, {}
    for r in rows:
        by_source[r["metadata"]["source"]] = by_source.get(r["metadata"]["source"], 0) + 1
        by_mode[r["metadata"]["mode"]] = by_mode.get(r["metadata"]["mode"], 0) + 1
    n_think = sum(1 for r in rows if THINK_RE.match(r["messages"][-1]["content"]))
    n_system = sum(1 for r in rows if r["messages"][0]["role"] == "system")

    print("=" * 78)
    print(f"STAGED {len(rows)} rows from {root}")
    print(f"  by source: {by_source}")
    print(f"  by mode  : {dict(sorted(by_mode.items(), key=lambda kv: -kv[1]))}")
    print(f"  trace 'user: ' prefixes stripped: {stripped}")
    print(f"  rows with a leading inline <think> block: {n_think}")
    print(f"  rows carrying a system turn: {n_system}")
    print("=" * 78)

    with open(out_path, "w") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"WROTE {out_path} ({out_path.stat().st_size:,} B)")

    flags = hygiene(rows)
    print(f"\nHYGIENE SCREEN: {len(flags)} flagged (reported, NOT dropped)")
    for i, src, rid, why in flags:
        print(f"  [{i}] {src} {rid}: {why}")

    if args.skip_audit:
        return 0

    # 2. seq audit -----------------------------------------------------------
    from transformers import AutoTokenizer  # noqa: E402 (kept out of --skip-audit path)

    for path in (args.gemma_snapshot, args.qwen_snapshot):
        if not Path(path).is_dir():
            sys.exit(f"ERROR: tokenizer snapshot missing: {path}")
    print("\nLoading tokenizers (local snapshots, no network) ...")
    os.environ.setdefault("HF_HUB_OFFLINE", "1")
    gtok = AutoTokenizer.from_pretrained(args.gemma_snapshot)
    qtok = AutoTokenizer.from_pretrained(args.qwen_snapshot)
    print(f"  gemma: {type(gtok).__name__}   qwen: {type(qtok).__name__}")

    views = ["gemma", "qwen-split", "qwen-literal"]
    per_row = []
    for r in rows:
        msgs = r["messages"]
        counts = {
            "gemma": n_tokens(gtok, render_gemma(gtok, msgs)),
            "qwen-split": n_tokens(qtok, render_qwen(qtok, msgs, "split", args.qwen_reasoning_effort)),
            "qwen-literal": n_tokens(qtok, render_qwen(qtok, msgs, "literal", args.qwen_reasoning_effort)),
        }
        per_row.append({"row_id": r["metadata"]["row_id"], "source": r["metadata"]["source"],
                        "mode": r["metadata"]["mode"], "tokens": counts})

    def collect(pred):
        d = {v: [] for v in views}
        for pr in per_row:
            if pred(pr):
                for v in views:
                    d[v].append(pr["tokens"][v])
        return d

    groups = [("ALL", collect(lambda x: True))]
    for s in ("harvest", "trace", "synthetic"):
        groups.append((s, collect(lambda x, s=s: x["source"] == s)))
    table("SEQ AUDIT — by source (apply_chat_template view, add_generation_prompt=False)",
          groups, views)

    mode_groups = [(m or "none", collect(lambda x, m=m: x["mode"] == m))
                   for m in sorted(by_mode, key=lambda k: (k is None, k))]
    table("SEQ AUDIT — by mode", mode_groups, ["gemma", "qwen-split"])

    # Cost of the naive Qwen render (the double-think block)
    delta = [pr["tokens"]["qwen-literal"] - pr["tokens"]["qwen-split"] for pr in per_row]
    print(f"\nQWEN DOUBLE-THINK COST (literal - split): min {min(delta)} median "
          f"{int(statistics.median(delta))} max {max(delta)} tokens/row "
          f"(the empty outer <think></think> wrapper the template always emits)")

    audit_path = out_path.with_suffix(".seq-audit.json")
    with open(audit_path, "w") as f:
        json.dump({"max_seq": args.max_seq, "views": views,
                   "gemma_snapshot": args.gemma_snapshot, "qwen_snapshot": args.qwen_snapshot,
                   "qwen_reasoning_effort": args.qwen_reasoning_effort,
                   "rows": per_row}, f, indent=1)
    print(f"WROTE {audit_path} ({audit_path.stat().st_size:,} B)")

    # 3. the assert ----------------------------------------------------------
    as_trained = ["gemma", "qwen-split"]
    over = [pr for pr in per_row if max(pr["tokens"][v] for v in as_trained) > args.max_seq]
    print(f"\n[ASSERT] max seq <= {args.max_seq} across the AS-TRAINED views {as_trained}")
    if not over:
        print(f"  OK — all {len(per_row)} rows fit {args.max_seq}.")
    else:
        print(f"  VIOLATED — {len(over)}/{len(per_row)} rows exceed {args.max_seq}. Named:")
        for pr in sorted(over, key=lambda x: -max(x["tokens"][v] for v in as_trained)):
            print(f"    {pr['source']:<10} {pr['mode'] or '?':<14} {pr['row_id'][:44]:<46}"
                  f" gemma {pr['tokens']['gemma']:>7}  qwen-split {pr['tokens']['qwen-split']:>7}")
        by_src = {}
        for pr in over:
            by_src[pr["source"]] = by_src.get(pr["source"], 0) + 1
        print(f"  over-limit by source: {by_src}")

    if args.emit_fit_subset:
        fit_ids = {pr["row_id"] for pr in per_row
                   if max(pr["tokens"][v] for v in as_trained) <= args.max_seq}
        fit_path = out_path.with_name(f"{out_path.stem}.fit-{args.max_seq}.jsonl")
        with open(fit_path, "w") as f:
            for r in rows:
                if r["metadata"]["row_id"] in fit_ids:
                    f.write(json.dumps(r, ensure_ascii=False) + "\n")
        n_fit = sum(1 for r in rows if r["metadata"]["row_id"] in fit_ids)
        print(f"WROTE {fit_path} ({n_fit} rows fit {args.max_seq} under both as-trained views)")

    if over and not args.allow_over_limit:
        return 3
    return 0


if __name__ == "__main__":
    sys.exit(main())
