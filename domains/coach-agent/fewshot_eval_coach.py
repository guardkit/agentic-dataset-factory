#!/usr/bin/env python3
"""
fewshot_eval_coach.py — Step-3 cheap judgment-transfer probe (no GB10)
=====================================================================
The decisive prototype test (HANDOFF-coach-v2 Step 3, "cheapest signal first"): does the
synthetic v2 data convey TRANSFERABLE judgment? We measure the base gemma4-coach on the
cue-immune REAL balanced holdout (`holdout_balanced_real.jsonl`, 16 fb / 16 ap real rows —
none of the synthetic lexical/numeric tells) in two conditions:

  * ZERO-SHOT  — base alone. The honest false-approval baseline on BALANCED real data
                 (v1's holdout was 79% approve and lied; this is the number v2 must beat).
  * FEW-SHOT   — base + N balanced synthetic exemplars prepended in-context. If demonstrated
                 judgment transfers, false-approval drops WITHOUT false-feedback ballooning.

Because the real holdout has none of the synthetic cues, an improvement here is genuine
judgment transfer, not cue-matching; and if the data taught a bad shortcut (e.g. "more tests
-> feedback") it would surface as elevated false-feedback. So this is a fair, robust gate.

The base is --reasoning auto (verdict lands in reasoning_content). We pass the FREE
coach-verdict grammar (reason-then-emit) so the model reasons over the exemplars before the
forced verdict fence. Reuses eval_coach.py's endpoint + verdict parsing.

Usage:
    python fewshot_eval_coach.py --endpoint http://localhost:9000/v1 --model gemma4-coach \
        --grammar /opt/llama-swap/grammars/coach-verdict.gbnf \
        --fewshot-n 4 --max-tokens 1200 \
        --report ~/coach-dataset/curated/step3_fewshot_report.json
"""
import argparse
import json
import os
import sys
import time
from collections import Counter
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from eval_coach import extract_decision, gen_endpoint, gold_decision  # noqa: E402

CUR = os.path.expanduser("~/coach-dataset/curated")


def report_body(prompt):
    """Strip the Coach instruction header + the fenced-json footer, leaving the Task +
    Player report — the variable content an exemplar should show."""
    body = prompt
    if "## Task:" in body:
        body = "## Task:" + body.split("## Task:", 1)[1]
    if "Return the verdict as a fenced" in body:
        body = body.split("Return the verdict as a fenced", 1)[0].rstrip()
    return body


def build_preamble(exemplars, calib=False):
    lead = ("You are the Coach. Study these worked examples of CORRECT verdicts, then apply "
            "the same standard of judgment to the new turn.\n")
    if calib:
        lead = ("You are the Coach. Study these worked examples of CORRECT verdicts. Apply the "
                "SAME calibrated standard: return `approve` when every acceptance criterion has "
                "genuine evidence (most well-done turns are approvable); return `feedback` ONLY "
                "for a concrete, evidenced gap — never invent a gap or reject merely because a "
                "turn could be more thorough.\n")
    parts = [lead]
    for i, ex in enumerate(exemplars, 1):
        gold, _ = gold_decision(ex)
        parts.append(f"===== WORKED EXAMPLE {i} (correct verdict: {gold}) =====")
        parts.append(report_body(ex["prompt"]))
        parts.append("--- correct verdict ---")
        parts.append(ex["completion"].strip())
        parts.append("")
    parts.append("===== NOW EVALUATE THIS TURN =====")
    return "\n".join(parts) + "\n"


def pick_exemplars(rows, n):
    """N balanced exemplars (n/2 feedback + n/2 approve), deterministic order."""
    fb = [r for r in rows if gold_decision(r)[0] == "feedback"]
    ap = [r for r in rows if gold_decision(r)[0] == "approve"]
    k = n // 2
    out = []
    for i in range(k):
        if i < len(fb):
            out.append(fb[i])
        if i < len(ap):
            out.append(ap[i])
    return out[:n]


def run(rows, gen_fn, max_tokens, grammar, preamble, label):
    confusion = Counter()
    n_parse_fail = 0
    t0 = time.time()
    per_row = []
    for i, r in enumerate(rows, 1):
        gold, _ = gold_decision(r)
        prompt = (preamble + r["prompt"]) if preamble else r["prompt"]
        try:
            text = gen_fn(prompt, max_tokens, grammar=grammar)
        except Exception as e:  # noqa: BLE001
            print(f"  [{label}] row {i}: {e}", file=sys.stderr)
            text = ""
        pred = extract_decision(text)
        if pred is None:
            n_parse_fail += 1
        confusion[(gold, pred or "PARSE_FAIL")] += 1
        per_row.append({"task_id": r.get("task_id"), "gold": gold, "pred": pred})
        if i % 8 == 0:
            print(f"  [{label}] {i}/{len(rows)}", file=sys.stderr)
    gold_fb = [x for x in per_row if x["gold"] == "feedback"]
    gold_ap = [x for x in per_row if x["gold"] == "approve"]
    correct = sum(1 for x in per_row if x["pred"] == x["gold"])
    false_appr = sum(1 for x in gold_fb if x["pred"] == "approve")
    false_fb = sum(1 for x in gold_ap if x["pred"] == "feedback")
    n = len(per_row)
    return {
        "label": label, "n": n,
        "parse_rate": round((n - n_parse_fail) / n, 3) if n else 0,
        "correct_verdict_rate": round(correct / n, 3) if n else 0,
        "false_approval_rate": round(false_appr / len(gold_fb), 3) if gold_fb else None,
        "false_feedback_rate": round(false_fb / len(gold_ap), 3) if gold_ap else None,
        "n_gold_feedback": len(gold_fb), "n_gold_approve": len(gold_ap),
        "confusion": {f"{g}->{p}": c for (g, p), c in sorted(confusion.items())},
        "seconds": round(time.time() - t0, 1),
        "per_row": per_row,
    }


def show(s):
    fa = s["false_approval_rate"]
    ff = s["false_feedback_rate"]
    print(f"  {s['label']}: n={s['n']} parse={s['parse_rate']:.0%} "
          f"correct={s['correct_verdict_rate']:.0%} "
          f"false-approval={fa:.0%} (of {s['n_gold_feedback']} fb) "
          f"false-feedback={ff:.0%} (of {s['n_gold_approve']} ap)  [{s['seconds']}s]")
    print(f"    confusion: {s['confusion']}")


def main():
    ap = argparse.ArgumentParser(description="Step-3 few-shot judgment-transfer probe")
    ap.add_argument("--endpoint", default="http://localhost:9000/v1")
    ap.add_argument("--model", default="gemma4-coach")
    ap.add_argument("--holdout", default=os.path.join(CUR, "holdout_balanced_real.jsonl"))
    ap.add_argument("--fewshot", default=os.path.join(CUR, "synthetic_v2final_train.jsonl"))
    ap.add_argument("--fewshot-n", type=int, default=4)
    ap.add_argument("--grammar", default="/opt/llama-swap/grammars/coach-verdict.gbnf")
    ap.add_argument("--max-tokens", type=int, default=1200)
    ap.add_argument("--zero-shot-only", action="store_true")
    ap.add_argument("--few-shot-only", action="store_true", help="skip the zero-shot pass")
    ap.add_argument("--calib", action="store_true", help="use the calibrated anti-over-rejection preamble")
    ap.add_argument("--report")
    args = ap.parse_args()

    holdout = [json.loads(l) for l in Path(args.holdout).open() if l.strip()]
    exemplar_rows = [json.loads(l) for l in Path(args.fewshot).open() if l.strip()]
    exemplars = pick_exemplars(exemplar_rows, args.fewshot_n)
    grammar = Path(args.grammar).read_text() if args.grammar else None

    gen = lambda p, mt, grammar=None: gen_endpoint(args.endpoint, args.model, p, mt, grammar=grammar)
    print(f"Step-3 probe: model={args.model} holdout={len(holdout)} "
          f"(fb={sum(1 for r in holdout if gold_decision(r)[0]=='feedback')}/"
          f"ap={sum(1 for r in holdout if gold_decision(r)[0]=='approve')}) "
          f"fewshot_n={len(exemplars)} grammar={'on' if grammar else 'off'} max_tokens={args.max_tokens}")

    zs = None
    if not args.few_shot_only:
        print("\n=== ZERO-SHOT (base baseline on balanced REAL holdout) ===")
        zs = run(holdout, gen, args.max_tokens, grammar, None, "zero-shot")
        show(zs)

    fs = None
    if not args.zero_shot_only:
        preamble = build_preamble(exemplars, calib=args.calib)
        print(f"\n=== FEW-SHOT (+{len(exemplars)} synthetic exemplars) ===")
        fs = run(holdout, gen, args.max_tokens, grammar, preamble, "few-shot" + ("/calib" if args.calib else ""))
        show(fs)

    if zs and fs:
        print(f"\n{'='*64}\nSTEP-3 VERDICT (judgment transfer on cue-immune real holdout)\n{'='*64}")
        dfa = (fs["false_approval_rate"] or 0) - (zs["false_approval_rate"] or 0)
        dff = (fs["false_feedback_rate"] or 0) - (zs["false_feedback_rate"] or 0)
        dco = fs["correct_verdict_rate"] - zs["correct_verdict_rate"]
        print(f"  false-approval : {zs['false_approval_rate']:.0%} -> {fs['false_approval_rate']:.0%}  (Δ {dfa:+.0%}; want down)")
        print(f"  false-feedback : {zs['false_feedback_rate']:.0%} -> {fs['false_feedback_rate']:.0%}  (Δ {dff:+.0%}; want NOT up much)")
        print(f"  correct        : {zs['correct_verdict_rate']:.0%} -> {fs['correct_verdict_rate']:.0%}  (Δ {dco:+.0%})")
        promising = dfa < -0.05 and dff < 0.15
        print(f"  => {'PROMISING — judgment transferred; scale to a tiny LoRA' if promising else 'WEAK — iterate the generator/realism before scaling'}")

    if args.report:
        Path(args.report).write_text(json.dumps(
            {"zero_shot": zs, "few_shot": fs, "fewshot_n": len(exemplars),
             "model": args.model, "holdout": args.holdout}, indent=2))
        print(f"\nWrote report -> {args.report}")


if __name__ == "__main__":
    main()
