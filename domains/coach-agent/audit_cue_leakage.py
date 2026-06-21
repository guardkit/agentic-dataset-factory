#!/usr/bin/env python3
"""
audit_cue_leakage.py — deterministic surface-cue / shortcut gate for Coach data
===============================================================================
The v1 Coach rubber-stamped because of class imbalance; the v2 *quality* risk is the
opposite trap: a balanced corpus whose feedback vs approve rows are separable by a
LEXICAL SHORTCUT (a token/phrase that tracks the label), so the model learns the cue
instead of judgment. The cue-audit critic in the generator workflow flagged this as
HIGH; this script turns that into a hard, repeatable number and a CI-style gate
(cue-audit recommendation #8).

It reads rows with a Coach prompt (or raw player_report) + a gold decision, then on the
*player-report text only* (the part that varies and carries the tell) computes:

  1. Per-token document-frequency diff between feedback and approve rows
     (unigrams + bigrams). Big |diff| = a token that tracks the label.
  2. PERFECT SEPARATORS: tokens appearing in >= MIN_DF rows of one class and ZERO of the
     other. The fraction of rows reachable by at least one perfect separator is the
     "cue-only @100%-precision coverage" — a trivial classifier's free wins.
  3. Numeric shortcuts: mean files-touched / tests-count per class (approve skewing
     larger is a count proxy for the label).
  4. Per-rule separability (mode collapse concentrates inside a rule).

GATE (fail = the data would teach shortcuts; iterate the generator, not the size):
  * any single token/bigram with |DF-diff| > --max-df-diff (default 0.25), OR
  * cue-only @100%-precision coverage > --max-cue-coverage (default 0.05).

Usage:
    python audit_cue_leakage.py --rows ~/coach-dataset/curated/synthetic_v2_raw.jsonl
    python audit_cue_leakage.py --rows synthetic_v2_train.jsonl --max-cue-coverage 0.05
    # exit code 0 = PASS, 1 = FAIL (usable as a pipeline gate)
"""

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

WORD = re.compile(r"[a-z0-9][a-z0-9._\-]*[a-z0-9]|[a-z0-9]")
STOP = set("the a an and or of to in is are be it its this that for with as on at by "
           "from has have was were will not no all any one two more most each per "
           "if then so but into out up down over under than".split())


def player_report(row):
    """Return the discriminative text: the '## Player report' section if the row carries a
    full Coach prompt, else the raw player_report field."""
    p = row.get("prompt") or ""
    if "## Player report" in p:
        seg = p.split("## Player report", 1)[1]
        # trim the trailing fenced-json instruction footer
        seg = seg.split("Return the verdict", 1)[0]
        return seg
    return row.get("player_report") or p


def gold(row):
    d = str(row.get("decision", "")).strip().lower()
    return d if d in ("approve", "feedback") else None


def tokenize(text):
    toks = [t for t in WORD.findall(text.lower()) if t not in STOP and len(t) > 1]
    grams = set(toks)
    for i in range(len(toks) - 1):
        grams.add(toks[i] + " " + toks[i + 1])
    return grams


def get_test_count(text):
    """Best-effort 'how many tests the report claims passed' — the numeric field that
    leaked in round 2 (feedback systematically cited MORE tests)."""
    best = 0
    for pat in (r"tests?_passed[^0-9\n]{0,14}(\d+)",
                r"(\d+)\s+(?:tests?|scenarios?)\s+pass",
                r"tests?_passed:\s*True\s*\((\d+)\)",
                r"(\d+)\s+passing"):
        for m in re.findall(pat, text, re.IGNORECASE):
            best = max(best, int(m))
    return best


def get_file_count(text):
    """Distinct file paths cited in files_modified / files_created (label-independent
    cardinality should not track the decision)."""
    paths = set(re.findall(r"['\"]([\w./\-]+\.[a-z]{1,4})['\"]", text))
    if paths:
        return len(paths)
    return len(re.findall(r"\.(?:py|cs|ts|js|go|rs|java|rb)\b", text))


def best_threshold_acc(values, labels):
    """Max accuracy of any single threshold (either direction) on a 1-D numeric feature,
    vs the majority-class baseline. A big gain = the number alone separates the classes."""
    n = len(values)
    if n == 0:
        return 0.0, 0.0
    base = max(labels.count(1), labels.count(0)) / n
    best = base
    for t in sorted(set(values)):
        for direction in (1, -1):
            pred = [1 if (v >= t if direction == 1 else v < t) else 0 for v in values]
            # try both polarities (>=t -> feedback, or >=t -> approve)
            acc1 = sum(1 for p, y in zip(pred, labels) if p == y) / n
            acc0 = sum(1 for p, y in zip(pred, labels) if (1 - p) == y) / n
            best = max(best, acc1, acc0)
    return best, base


def top_diff(fb_tok, ap_tok, nfb, nap, min_df=2):
    """Return (max_abs_diff, token, df_fb, df_ap) for the strongest label-tracking token
    (DF-diff) among tokens seen in >= min_df rows. Robust at small N; the deterministic
    gate's primary signal. Per-rule semantic cues below this frequency are left to the
    Opus cue-audit critic, which reasons about MEANING (small-N lexical detection is
    unreliable — at 4-5 rows/class almost any rare token is a chance 'separator')."""
    df_fb, df_ap = Counter(), Counter()
    for s in fb_tok:
        for t in s:
            df_fb[t] += 1
    for s in ap_tok:
        for t in s:
            df_ap[t] += 1
    best = (0.0, None, 0, 0)
    for t in set(df_fb) | set(df_ap):
        if df_fb[t] + df_ap[t] < min_df:
            continue
        diff = df_fb[t] / nfb - df_ap[t] / nap
        if abs(diff) > abs(best[0]):
            best = (diff, t, df_fb[t], df_ap[t])
    return best


def main():
    ap = argparse.ArgumentParser(description="Surface-cue / shortcut gate for Coach data")
    ap.add_argument("--rows", required=True, help="JSONL with prompt/player_report + decision")
    ap.add_argument("--min-df", type=int, default=2,
                    help="min rows a token must appear in to count as a perfect separator")
    ap.add_argument("--max-df-diff", type=float, default=0.25,
                    help="FAIL if any token's |feedback%-approve%| exceeds this")
    ap.add_argument("--max-cue-coverage", type=float, default=0.05,
                    help="FAIL if perfect-separator coverage exceeds this fraction of rows")
    ap.add_argument("--sep-class-frac", type=float, default=0.20,
                    help="a perfect separator must cover at least this fraction of its own "
                         "class (filters small-N df=2 noise that is not a learnable cue)")
    ap.add_argument("--max-num-gain", type=float, default=0.12,
                    help="FAIL if any numeric field's best single-threshold accuracy beats the "
                         "majority baseline by more than this (number alone separates classes)")
    ap.add_argument("--max-pair-skew", type=float, default=0.75,
                    help="FAIL if within matched feedback/approve pairs the test-count is higher "
                         "on the same side more than this fraction of the time (want ~0.5)")
    ap.add_argument("--top", type=int, default=25, help="how many top cue tokens to print")
    args = ap.parse_args()

    rows = [json.loads(l) for l in Path(args.rows).open() if l.strip()]
    rows = [r for r in rows if gold(r)]
    fb = [r for r in rows if gold(r) == "feedback"]
    ap_ = [r for r in rows if gold(r) == "approve"]
    nfb, nap = len(fb), len(ap_)
    if not nfb or not nap:
        sys.exit(f"need both classes; got feedback={nfb} approve={nap}")

    fb_tok = [tokenize(player_report(r)) for r in fb]
    ap_tok = [tokenize(player_report(r)) for r in ap_]
    vocab = set().union(*fb_tok, *ap_tok)

    df_fb = Counter()
    df_ap = Counter()
    for s in fb_tok:
        for t in s:
            df_fb[t] += 1
    for s in ap_tok:
        for t in s:
            df_ap[t] += 1

    scored = []
    for t in vocab:
        if df_fb[t] + df_ap[t] < args.min_df:
            continue
        diff = df_fb[t] / nfb - df_ap[t] / nap
        scored.append((diff, t, df_fb[t], df_ap[t]))
    scored.sort(key=lambda x: -abs(x[0]))

    # perfect separators: present in ZERO rows of one class and, in the other class, in
    # both >= min_df rows AND >= sep_class_frac of that class (the frac filter removes the
    # small-N df=2 tokens that are perfect by chance, not because they are learnable cues).
    fb_floor = max(args.min_df, int(args.sep_class_frac * nfb + 0.999))
    ap_floor = max(args.min_df, int(args.sep_class_frac * nap + 0.999))
    perfect = [(t, df_fb[t], df_ap[t], "feedback" if df_ap[t] == 0 else "approve")
               for (_, t, _, _) in scored
               if (df_fb[t] >= fb_floor and df_ap[t] == 0)
               or (df_ap[t] >= ap_floor and df_fb[t] == 0)]
    perfect_set = {t for (t, _, _, _) in perfect}

    def covered(toks):
        return bool(toks & perfect_set)
    cov_fb = sum(1 for s in fb_tok if covered(s))
    cov_ap = sum(1 for s in ap_tok if covered(s))
    coverage = (cov_fb + cov_ap) / (nfb + nap)

    # ---- numeric-field leakage (round-2 regression: test-count tracked the label) ----
    fb_tests = [get_test_count(player_report(r)) for r in fb]
    ap_tests = [get_test_count(player_report(r)) for r in ap_]
    fb_files = [get_file_count(player_report(r)) for r in fb]
    ap_files = [get_file_count(player_report(r)) for r in ap_]
    f_tests, a_tests = sum(fb_tests) / nfb, sum(ap_tests) / nap
    f_files, a_files = sum(fb_files) / nfb, sum(ap_files) / nap
    labels = [1] * nfb + [0] * nap
    test_acc, base = best_threshold_acc(fb_tests + ap_tests, labels)
    file_acc, _ = best_threshold_acc(fb_files + ap_files, labels)
    num_gain = max(test_acc, file_acc) - base

    # within-matched-pair directionality (pair feedback vs approve_control by scenario_id):
    # the strongest form of a count cue — does feedback have more tests than its own clean twin?
    pairs = defaultdict(dict)
    for r in rows:
        sid, var = r.get("scenario_id"), r.get("variant")
        if sid and var in ("feedback", "approve_control"):
            pairs[sid][var] = get_test_count(player_report(r))
    fb_hi = sum(1 for p in pairs.values()
                if "feedback" in p and "approve_control" in p and p["feedback"] > p["approve_control"])
    ap_hi = sum(1 for p in pairs.values()
                if "feedback" in p and "approve_control" in p and p["feedback"] < p["approve_control"])
    tie = sum(1 for p in pairs.values()
              if "feedback" in p and "approve_control" in p and p["feedback"] == p["approve_control"])
    nonzero = fb_hi + ap_hi
    pair_skew = max(fb_hi, ap_hi) / nonzero if nonzero else 0.0

    # per-rule separability + class balance
    by_rule = defaultdict(list)
    for r in rows:
        by_rule[r.get("rule", "?")].append(r)

    max_diff = abs(scored[0][0]) if scored else 0.0

    print(f"\n{'='*70}\ncue-leakage audit — {Path(args.rows).name}\n{'='*70}")
    print(f"rows={len(rows)}  feedback={nfb}  approve={nap}  "
          f"(feedback frac={nfb/len(rows):.0%})")
    print(f"\ntop {args.top} label-tracking tokens (DF-diff = feedback% - approve%):")
    print(f"  {'diff':>6}  {'fb':>3} {'ap':>3}  token")
    for diff, t, a, b in scored[:args.top]:
        flag = "  <-- PERFECT" if t in perfect_set else ""
        print(f"  {diff:+.2f}  {a:>3} {b:>3}  {t!r}{flag}")
    print(f"\nperfect separators (0 in one class, >= {args.sep_class_frac:.0%} of the other): "
          f"{len(perfect)}")
    for t, a, b, cls in perfect[:15]:
        print(f"    {t!r:32} fb={a} ap={b}  -> {cls}")
    print(f"cue-only @100%-precision coverage: {cov_fb+cov_ap}/{len(rows)} = {coverage:.1%}"
          f"  (feedback {cov_fb}/{nfb}, approve {cov_ap}/{nap})")
    print(f"\nnumeric-field leakage (round-2 regressed here):")
    print(f"  test-count mean  fb={f_tests:.1f}  ap={a_tests:.1f}   "
          f"best-threshold acc={test_acc:.0%} (baseline {base:.0%})")
    print(f"  file-count mean  fb={f_files:.2f} ap={a_files:.2f}   "
          f"best-threshold acc={file_acc:.0%}")
    print(f"  within-pair test-count: feedback>approve in {fb_hi}, approve>feedback in {ap_hi}, "
          f"tie in {tie}  -> skew {pair_skew:.0%} (want ~50%)")
    print("\nper-rule class balance (mode-collapse guard; need >= 2 of each):")
    for rule, rr in sorted(by_rule.items()):
        cfb = sum(1 for r in rr if gold(r) == "feedback")
        cap = sum(1 for r in rr if gold(r) == "approve")
        flag = "  <-- COLLAPSE" if (cfb < 2 or cap < 2) else ""
        print(f"  fb={cfb:>2} ap={cap:>2}  {rule}{flag}")
    print("\nper-rule strongest cue token (DF-diff; small N -> indicative, not a hard gate):")
    for rule, rr in sorted(by_rule.items()):
        rfb = [player_report(r) for r in rr if gold(r) == "feedback"]
        rap = [player_report(r) for r in rr if gold(r) == "approve"]
        if not rfb or not rap:
            print(f"  {rule}: single-class only")
            continue
        diff, t, a, b = top_diff([tokenize(x) for x in rfb], [tokenize(x) for x in rap],
                                 len(rfb), len(rap))
        print(f"  {diff:+.2f}  fb={a} ap={b}  {t!r:28} {rule}")

    collapsed = [rule for rule, rr in by_rule.items()
                 if sum(1 for r in rr if gold(r) == "feedback") < 2
                 or sum(1 for r in rr if gold(r) == "approve") < 2]

    fail_diff = max_diff > args.max_df_diff
    fail_cov = coverage > args.max_cue_coverage
    fail_num = num_gain > args.max_num_gain
    fail_pair = nonzero >= 6 and pair_skew > args.max_pair_skew
    fail_collapse = bool(collapsed)
    fail = fail_diff or fail_cov or fail_num or fail_pair or fail_collapse
    print(f"\n{'-'*70}")
    print(f"max |DF-diff|      = {max_diff:.2f}  (<= {args.max_df_diff})        "
          f"{'FAIL' if fail_diff else 'ok'}")
    print(f"cue coverage       = {coverage:.1%}  (<= {args.max_cue_coverage:.0%})        "
          f"{'FAIL' if fail_cov else 'ok'}")
    print(f"numeric best-thr Δ = {num_gain:+.0%}  (<= +{args.max_num_gain:.0%} over baseline) "
          f"{'FAIL' if fail_num else 'ok'}")
    print(f"within-pair skew   = {pair_skew:.0%}  (<= {args.max_pair_skew:.0%})        "
          f"{'FAIL' if fail_pair else 'ok'}")
    print(f"per-rule collapse  = {len(collapsed)} rule(s)             "
          f"{'FAIL: ' + ', '.join(c.replace('.md','') for c in collapsed) if fail_collapse else 'ok'}")
    print("NOTE: deterministic gate catches GLOBAL lexical + numeric + structural cues; "
          "per-rule semantic cues at 4-5 rows/class are best judged by the Opus cue-audit critic.")
    verdict = "FAIL — data teaches shortcuts; iterate the generator" if fail \
        else "PASS — no strong lexical/numeric/structural shortcut"
    print(f"VERDICT: {verdict}\n{'='*70}\n")
    sys.exit(1 if fail else 0)


if __name__ == "__main__":
    main()
