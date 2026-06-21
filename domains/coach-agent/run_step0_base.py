#!/usr/bin/env python3
"""run_step0_base.py — eval the BASE coach on a Step-0 evidence-format corpus.

Reuses eval_coach.gen_endpoint (llama.cpp/llama-swap grammar passthrough; reads
reasoning_content where the base lands its verdict) + extract_decision, so the
serving + parse path is identical to the v2 base measurement. Scores
false-approval / false-feedback and, when present, breaks feedback results down
by the label-free `bundle_signal` (whether the Player-side gates alone already
implied feedback) so we can see what the base catches vs misses.

Usage:
    python3 run_step0_base.py --file step0_eval.jsonl \
        --endpoint http://localhost:9000/v1 --model gemma4-coach \
        --grammar /opt/llama-swap/grammars/coach-verdict-strict.gbnf
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from collections import Counter
from pathlib import Path

from eval_coach import extract_decision, gen_endpoint


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", required=True)
    ap.add_argument("--endpoint", default="http://localhost:9000/v1")
    ap.add_argument("--model", default="gemma4-coach")
    ap.add_argument("--grammar", default="/opt/llama-swap/grammars/coach-verdict-strict.gbnf")
    ap.add_argument("--max-tokens", type=int, default=256)
    ap.add_argument("--report", default=None)
    args = ap.parse_args()

    rows = [json.loads(l) for l in Path(args.file).open() if l.strip()]
    grammar = Path(args.grammar).read_text() if args.grammar else None
    print(f"Loaded {len(rows)} rows from {args.file}; model={args.model} "
          f"grammar={'strict' if grammar else 'none'}")

    confusion = Counter()
    results = []
    t0 = time.time()
    for i, r in enumerate(rows, 1):
        gold = str(r.get("decision", "")).strip().lower() or None
        prompt = r.get("prompt")
        if not prompt:
            continue
        try:
            text = gen_endpoint(args.endpoint, args.model, prompt, args.max_tokens, grammar=grammar)
        except Exception as e:  # noqa: BLE001
            print(f"  row {i} ({r.get('task_id')}): error {e}", file=sys.stderr)
            text = ""
        pred = extract_decision(text)
        confusion[(gold, pred or "PARSE_FAIL")] += 1
        sig = r.get("bundle_signal") or {}
        recoverable = bool(sig.get("gate_failing") or sig.get("gate_absent_oracle"))
        results.append({
            "task_id": r.get("task_id"), "repo": r.get("repo"), "turn": r.get("turn"),
            "gold": gold, "pred": pred, "recoverable": recoverable, "raw": text[:1200],
        })
        if i % 8 == 0:
            print(f"  {i}/{len(rows)} done", file=sys.stderr)

    gold_fb = [x for x in results if x["gold"] == "feedback"]
    gold_ap = [x for x in results if x["gold"] == "approve"]
    fa = sum(1 for x in gold_fb if x["pred"] == "approve")
    ff = sum(1 for x in gold_ap if x["pred"] == "feedback")
    n = len(results)
    correct = sum(1 for x in results if x["pred"] == x["gold"])
    parse_fail = sum(1 for x in results if x["pred"] is None)

    print(f"\n=== BASE {args.model} on {Path(args.file).name} ({n} rows, {time.time()-t0:.0f}s) ===")
    print(f"parse_rate   : {(n-parse_fail)/n:.0%}  ({parse_fail} parse-fail)")
    print(f"correct      : {correct}/{n} = {correct/n:.1%}")
    if gold_fb:
        print(f"FALSE-APPROVAL: {fa}/{len(gold_fb)} = {fa/len(gold_fb):.1%}   (gold=feedback wrongly approved)")
    if gold_ap:
        print(f"false-feedback: {ff}/{len(gold_ap)} = {ff/len(gold_ap):.1%}   (gold=approve wrongly rejected)")
    print(f"confusion    : {{{', '.join(f'{g}->{p}: {c}' for (g,p),c in sorted(confusion.items()))}}}")

    # feedback breakdown by recoverability of the Player-side gate signal
    rec_fb = [x for x in gold_fb if x["recoverable"]]
    unr_fb = [x for x in gold_fb if not x["recoverable"]]
    if rec_fb or unr_fb:
        rec_caught = sum(1 for x in rec_fb if x["pred"] == "feedback")
        unr_caught = sum(1 for x in unr_fb if x["pred"] == "feedback")
        print("\n--- feedback breakdown by Player-side gate signal ---")
        print(f"  recoverable (gates already imply feedback): caught {rec_caught}/{len(rec_fb)}")
        print(f"  uninferable (gates clean; needs Coach's own signal): caught {unr_caught}/{len(unr_fb)}")

    if args.report:
        Path(args.report).write_text(json.dumps({
            "file": args.file, "model": args.model, "n": n,
            "false_approval": fa, "n_feedback": len(gold_fb),
            "false_feedback": ff, "n_approve": len(gold_ap),
            "correct": correct, "parse_fail": parse_fail,
            "confusion": {f"{g}->{p}": c for (g, p), c in confusion.items()},
            "results": results,
        }, indent=2))
        print(f"\nreport -> {args.report}")


if __name__ == "__main__":
    main()
