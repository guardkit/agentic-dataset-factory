#!/usr/bin/env python3
"""
eval_coach.py — "beats base" evaluation for the fine-tuned Coach
================================================================
Implements the HANDOFF win condition: on the held-out eval set the fine-tune must show
**higher correct-verdict rate AND lower false-approval rate** than the base 26B-A4B model,
with tighter reasoning. False-approval (saying `approve` when the gold verdict is
`feedback`) is the headline anti-rubber-stamp metric — a Coach that rubber-stamps is worse
than no Coach.

Eval sets (under ~/coach-dataset/curated/):
  * holdout_eval.jsonl   (76)  — TRUE held-out; the primary generalisation metric.
  * hard_cases.jsonl     (8)   — authored symptom->ideal-catch; tagged `symptom_modelled`.
  * relabelled.jsonl     (9)   — corrected false-approvals; tagged `rule_cited`.
        hard_cases + relabelled are FOLDED INTO train_final, so they measure "did training
        take on these symptoms", NOT generalisation. Reported separately and flagged.
  * tierb_holdout.jsonl  (6)   — full Claude trajectories; qualitative/few-shot only, skipped here.

Backends (pick one; --endpoint is the faithful one — it hits the real serving stack):
  --endpoint http://localhost:8080/v1   OpenAI-compatible chat completions (llama-swap/llama.cpp/vLLM)
  --model-path /path/to/merged-16bit    transformers load (lazy import; for a quick post-train check)

Usage:
    # Compare fine-tune vs base through llama-swap (greedy):
    python eval_coach.py --endpoint http://localhost:8080/v1 \
        --model coach-gemma4-moe --base-model gemma4-26b-a4b-it \
        --report ~/coach-dataset/curated/eval_report.json

    # Single model only:
    python eval_coach.py --endpoint http://localhost:8080/v1 --model coach-gemma4-moe

    # Optional: constrain decoding with the serving GBNF grammar (llama.cpp `grammar` field):
    python eval_coach.py --endpoint ... --model coach --grammar /opt/llama-swap/grammars/coach.gbnf
"""

import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from collections import Counter, defaultdict
from pathlib import Path

CUR = os.path.expanduser("~/coach-dataset/curated")
DECISIONS = {"approve", "feedback"}
_DEC_RE = re.compile(r'"decision"\s*:\s*"(approve|feedback)"', re.IGNORECASE)


# --------------------------------------------------------------------------- #
# Verdict parsing
# --------------------------------------------------------------------------- #
def extract_decision(text: str):
    """Return 'approve' | 'feedback' | None from a model completion."""
    if not text:
        return None
    # 1) strict: find a JSON object with a decision key
    for blob in _iter_json_objects(text):
        try:
            obj = json.loads(blob)
        except json.JSONDecodeError:
            continue
        d = str(obj.get("decision", "")).strip().lower()
        if d in DECISIONS:
            return d
    # 2) lenient: regex the decision field directly
    m = _DEC_RE.search(text)
    if m:
        return m.group(1).lower()
    # 3) last resort: a bare word near the start
    head = text.strip().lower()[:200]
    if "feedback" in head and "approve" not in head:
        return "feedback"
    if "approve" in head and "feedback" not in head:
        return "approve"
    return None


def _iter_json_objects(text: str):
    """Yield candidate {...} substrings (handles ```json fences and brace nesting)."""
    depth, start = 0, None
    for i, ch in enumerate(text):
        if ch == "{":
            if depth == 0:
                start = i
            depth += 1
        elif ch == "}":
            if depth > 0:
                depth -= 1
                if depth == 0 and start is not None:
                    yield text[start:i + 1]
                    start = None


# --------------------------------------------------------------------------- #
# Backends
# --------------------------------------------------------------------------- #
def gen_endpoint(base_url, model, prompt, max_tokens, grammar=None, timeout=180):
    url = base_url.rstrip("/") + "/chat/completions"
    body = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.0,
        "top_p": 1.0,
        "max_tokens": max_tokens,
        "stream": False,
    }
    if grammar:
        body["grammar"] = grammar  # llama.cpp / llama-swap passthrough
    data = json.dumps(body).encode()
    req = urllib.request.Request(
        url, data=data, headers={"Content-Type": "application/json",
                                 "Authorization": "Bearer sk-no-key-required"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        out = json.loads(resp.read())
    msg = out["choices"][0]["message"]
    # --reasoning auto models (e.g. base gemma4-coach) emit the verdict into reasoning_content
    # with empty content; concat both so the verdict is found wherever it lands.
    content = msg.get("content") or ""
    reasoning = msg.get("reasoning_content") or ""
    return content if content.strip() else reasoning


def make_transformers_gen(model_path, max_seq_len=4096):
    import torch  # lazy
    from transformers import AutoTokenizer, AutoModelForCausalLM
    tok = AutoTokenizer.from_pretrained(model_path)
    model = AutoModelForCausalLM.from_pretrained(
        model_path, dtype=torch.bfloat16, device_map="cuda",
        attn_implementation="sdpa")  # Gemma-4 head_dim 512 > 256 -> FA2 crashes; force sdpa
    model.eval()

    def _gen(prompt, max_tokens, grammar=None):
        msgs = [{"role": "user", "content": prompt}]
        # transformers 5.x: apply_chat_template(return_tensors=...) returns a BatchEncoding dict,
        # not a bare tensor — pass it expanded to generate() and slice off the prompt by length.
        enc = tok.apply_chat_template(
            msgs, return_tensors="pt", add_generation_prompt=True, return_dict=True)
        enc = {k: v.to(model.device) for k, v in enc.items()}
        in_len = enc["input_ids"].shape[1]
        with torch.no_grad():
            out = model.generate(**enc, max_new_tokens=max_tokens, do_sample=False)
        return tok.decode(out[0][in_len:], skip_special_tokens=True)

    return _gen


# --------------------------------------------------------------------------- #
# Eval loop + metrics
# --------------------------------------------------------------------------- #
def load_rows(path):
    p = Path(path)
    if not p.exists():
        return []
    return [json.loads(l) for l in p.open() if l.strip()]


def gold_decision(r):
    """Gold = the decision in the REFERENCE completion (the literal ideal target),
    falling back to the metadata `decision` label only when no completion is present.
    Returns (gold, label_mismatch) where label_mismatch flags corpus rows whose metadata
    `decision` disagrees with their own completion (e.g. the mislabelled path-string-mismatch
    hard_case — gold=approve from the completion, but metadata says feedback)."""
    meta = str(r.get("decision", "")).strip().lower() or None
    comp = extract_decision(r.get("completion") or "")
    gold = comp or meta
    return gold, (comp is not None and meta is not None and comp != meta)


def run_set(rows, gen_fn, max_tokens, grammar, label):
    """Generate + score one eval set. Returns (per_row results, summary dict)."""
    results = []
    confusion = Counter()          # (gold, pred)
    n_parse_fail = 0
    label_mismatches = []
    t0 = time.time()
    for i, r in enumerate(rows, 1):
        gold, mismatch = gold_decision(r)
        if mismatch:
            label_mismatches.append(r.get("task_id") or r.get("symptom_modelled", "")[:60])
        prompt = r.get("prompt") or (r.get("messages") and r["messages"][-2]["content"])
        if not prompt:
            continue
        try:
            text = gen_fn(prompt, max_tokens, grammar=grammar)
        except (urllib.error.URLError, urllib.error.HTTPError, KeyError) as e:
            print(f"  [{label}] row {i}: generation error: {e}", file=sys.stderr)
            text = ""
        pred = extract_decision(text)
        if pred is None:
            n_parse_fail += 1
        confusion[(gold, pred or "PARSE_FAIL")] += 1
        results.append({
            "task_id": r.get("task_id"), "gold": gold, "pred": pred,
            "symptom_modelled": r.get("symptom_modelled"),
            "rule_cited": r.get("rule_cited"), "raw": text[:4000],
        })
        if i % 10 == 0:
            print(f"  [{label}] {i}/{len(rows)} done", file=sys.stderr)
    if label_mismatches:
        print(f"  [{label}] NOTE: {len(label_mismatches)} row(s) have metadata.decision != "
              f"completion.decision (used completion as gold): {label_mismatches}", file=sys.stderr)

    n = len(results)
    gold_fb = [x for x in results if x["gold"] == "feedback"]
    gold_ap = [x for x in results if x["gold"] == "approve"]
    correct = sum(1 for x in results if x["pred"] == x["gold"])
    false_appr = sum(1 for x in gold_fb if x["pred"] == "approve")
    false_fb = sum(1 for x in gold_ap if x["pred"] == "feedback")

    summary = {
        "label": label, "n": n,
        "parse_fail": n_parse_fail,
        "parse_rate": round((n - n_parse_fail) / n, 4) if n else 0.0,
        "correct_verdict_rate": round(correct / n, 4) if n else 0.0,
        # THE metric: of the cases that SHOULD be feedback, how many were wrongly approved.
        "false_approval_rate": round(false_appr / len(gold_fb), 4) if gold_fb else None,
        "false_feedback_rate": round(false_fb / len(gold_ap), 4) if gold_ap else None,
        "n_gold_feedback": len(gold_fb), "n_gold_approve": len(gold_ap),
        "label_mismatches": len(label_mismatches),
        "confusion": {f"{g}->{p}": c for (g, p), c in sorted(confusion.items())},
        "seconds": round(time.time() - t0, 1),
    }
    return results, summary


def symptom_breakdown(results, key):
    """Per-symptom 'matches the ideal verdict' rate (pred==gold) for the in-train probe
    sets. Note the probe is mostly gold=feedback, but includes at least one gold=approve
    false-positive trap (path-string-mismatch), so match (not 'caught feedback') is correct."""
    by = defaultdict(lambda: [0, 0])  # tag -> [matched, total]
    for x in results:
        tag = (x.get(key) or "untagged")[:80]
        by[tag][1] += 1
        if x["pred"] == x["gold"]:
            by[tag][0] += 1
    return {tag: {"matched": c, "total": t, "gold": None, "rate": round(c / t, 3) if t else 0.0}
            for tag, (c, t) in sorted(by.items())}


def print_summary(s):
    fa = s["false_approval_rate"]
    print(f"  n={s['n']}  parse={s['parse_rate']:.0%}  "
          f"correct={s['correct_verdict_rate']:.1%}  "
          f"false-approval={fa:.1%} (of {s['n_gold_feedback']} feedback)"
          if fa is not None else
          f"  n={s['n']}  parse={s['parse_rate']:.0%}  correct={s['correct_verdict_rate']:.1%}")
    print(f"  confusion: {s['confusion']}")


def main():
    ap = argparse.ArgumentParser(description="Coach 'beats base' eval")
    ap.add_argument("--endpoint", help="OpenAI-compatible base URL, e.g. http://localhost:8080/v1")
    ap.add_argument("--model", help="served model name (fine-tune) for --endpoint")
    ap.add_argument("--base-model", help="served base model name for side-by-side comparison")
    ap.add_argument("--model-path", help="transformers model dir (alternative to --endpoint)")
    ap.add_argument("--grammar", help="optional GBNF grammar file passed to llama.cpp `grammar`")
    ap.add_argument("--curated", default=CUR, help="curated dir holding the eval JSONLs")
    ap.add_argument("--holdout-file", default=None,
                    help="override the holdout path (e.g. holdout_balanced_real.jsonl — the "
                         "cue-immune balanced gate); default: <curated>/holdout_eval.jsonl")
    ap.add_argument("--max-tokens", type=int, default=1536)
    ap.add_argument("--report", help="write full JSON report here")
    args = ap.parse_args()

    if not args.endpoint and not args.model_path:
        ap.error("provide --endpoint (with --model) or --model-path")

    grammar = None
    if args.grammar:
        grammar = Path(args.grammar).read_text()

    holdout = load_rows(Path(args.holdout_file) if args.holdout_file
                        else Path(args.curated) / "holdout_eval.jsonl")
    hard = load_rows(Path(args.curated) / "hard_cases.jsonl")
    relabelled = load_rows(Path(args.curated) / "relabelled.jsonl")
    print(f"Loaded: holdout={len(holdout)} hard_cases={len(hard)} relabelled={len(relabelled)}")

    def build_gen(model_name):
        if args.model_path:
            return make_transformers_gen(args.model_path)
        return lambda prompt, mt, grammar=None: gen_endpoint(
            args.endpoint, model_name, prompt, mt, grammar=grammar)

    def eval_model(model_name, tag):
        gen = build_gen(model_name)
        print(f"\n=== {tag}: {model_name or args.model_path} ===")
        ho_res, ho_sum = run_set(holdout, gen, args.max_tokens, grammar, f"{tag}/holdout")
        print("[holdout — TRUE held-out, the generalisation metric]")
        print_summary(ho_sum)

        probe_rows = hard + relabelled
        pr_res, pr_sum = run_set(probe_rows, gen, args.max_tokens, grammar, f"{tag}/probe")
        print("[symptom probe — IN-TRAIN (hard_cases + relabelled); 'did training take', NOT generalisation]")
        print_summary(pr_sum)
        sym = symptom_breakdown([x for x in pr_res if x.get("symptom_modelled")], "symptom_modelled")
        rule = symptom_breakdown([x for x in pr_res if x.get("rule_cited")], "rule_cited")
        return {"holdout": ho_sum, "probe": pr_sum,
                "symptom_breakdown": sym, "rule_breakdown": rule,
                "holdout_rows": ho_res, "probe_rows": pr_res}

    report = {"curated": str(args.curated), "grammar": bool(grammar)}
    ft = eval_model(args.model, "fine-tune")
    report["fine_tune"] = ft

    if args.base_model:
        base = eval_model(args.base_model, "base")
        report["base"] = base
        # ---- WIN CONDITION ----
        ho_ft, ho_b = ft["holdout"], base["holdout"]
        d_correct = ho_ft["correct_verdict_rate"] - ho_b["correct_verdict_rate"]
        fa_ft = ho_ft["false_approval_rate"] or 0.0
        fa_b = ho_b["false_approval_rate"] or 0.0
        d_fa = fa_ft - fa_b  # want negative
        win = d_correct > 0 and d_fa < 0
        print(f"\n{'='*64}\nBEATS-BASE VERDICT (holdout)\n{'='*64}")
        print(f"  correct-verdict: base {ho_b['correct_verdict_rate']:.1%} -> "
              f"fine-tune {ho_ft['correct_verdict_rate']:.1%}  (Δ {d_correct:+.1%})")
        print(f"  false-approval : base {fa_b:.1%} -> fine-tune {fa_ft:.1%}  (Δ {d_fa:+.1%})")
        print(f"  => {'WIN ✅  (correct ↑ AND false-approval ↓)' if win else 'NOT A WIN ❌  (need correct ↑ AND false-approval ↓)'}")
        report["verdict"] = {"win": win, "delta_correct": round(d_correct, 4),
                             "delta_false_approval": round(d_fa, 4)}

    if args.report:
        Path(args.report).write_text(json.dumps(report, indent=2))
        print(f"\nWrote report -> {args.report}")


if __name__ == "__main__":
    main()
