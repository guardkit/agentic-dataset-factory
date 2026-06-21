#!/usr/bin/env python3
"""
assemble_synthetic_v2.py — gate, balance, and split the synthetic v2 Coach corpus
=================================================================================
The v1 Coach LoRA became a RUBBER-STAMP (87.5% false-approval) because the corpus
was 81% approve / 19% feedback (see RETRO-coach-finetune.md). v2 fixes the DATA: a
taxonomy-driven generator (the `coach-v2-synthetic-generator` workflow — Opus acting
as the teacher Coach, grounded in guardkit/.claude/rules/) mints BALANCED, matched
(clean -> approve / flaw-injected -> feedback) cases plus approve-traps, then
blind-verifies every row. This script is the deterministic back-end that turns those
generated rows into trainable, gated, balanced JSONL.

INPUT  (--raw): kept rows from the workflow (one JSON object per line), each with:
    rule, scenario_id, task_id, turn, task_title, variant, decision,
    player_report, verdict (object), prompt, completion,
    blind_decision, blind_agrees   (+ flaw_mechanism, acceptance_criteria, ...)

OUTPUT (under --curated, default ~/coach-dataset/curated/):
    synthetic_v2_train.jsonl     balanced smoke batch (matched pairs + capped traps)
    synthetic_v2_holdout.jsonl   balanced, scenario-DISJOINT holdout
    synthetic_v2_dropped.jsonl   every dropped row + the reason (gate fail / balance excess)
    holdout_balanced_real.jsonl  (--real-balanced, default ON) 50/50 slice of the REAL
                                 holdout_eval.jsonl — the honest gate v1 never had

GATES (mirror prepare_coach_sft.py + the live coach-verdict.gbnf contract):
  * template-token leak (<|turn> / <|channel> ...) anywhere -> ABORT (fatal corpus bug)
  * verdict body parses as JSON, is an object, decision in {approve, feedback}
  * verdict.decision == row.decision == decision parsed from the rendered completion
  * NO backtick inside the verdict JSON body (coach-verdict.gbnf `char` forbids it —
    a stray backtick crashes the serving parser; load-bearing)
  * blind_agrees is True (the Opus blind re-verdict matched the intended label)
  * prompt carries the Coach header + "## Task:" + "## Player report" (format sanity)
  * prompt disjoint from the real train_final.jsonl AND holdout_eval.jsonl (leakage)

SPLIT: by SCENARIO (a scenario's feedback + its matched approve control/trap never
straddle the train/holdout boundary), keeping every rule represented in both splits.
BALANCE: keep all feedback + matched approve controls (1:1), then add approve-traps up
to a cap so the corpus stays ~50% feedback (anti-rubber-stamp) without over-rejecting.

Usage:
    python assemble_synthetic_v2.py --raw ~/coach-dataset/curated/synthetic_v2_raw.jsonl
    python assemble_synthetic_v2.py --raw ... --feedback-frac 0.5 --holdout-scenario-frac 0.4
    python assemble_synthetic_v2.py --raw ... --no-real-balanced   # skip the real-data gate slice
"""

import argparse
import json
import os
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

CUR = os.path.expanduser("~/coach-dataset/curated")
LEAK_MARKERS = ["<|turn>", "<turn|>", "<|channel>", "<channel|>"]
DECISIONS = {"approve", "feedback"}


def parse_args():
    p = argparse.ArgumentParser(description="Gate/balance/split synthetic v2 Coach corpus")
    p.add_argument("--raw", default=os.path.join(CUR, "synthetic_v2_raw.jsonl"),
                   help="JSONL of kept rows from the generator workflow")
    p.add_argument("--curated", default=CUR, help="output dir (also holds the real eval sets)")
    p.add_argument("--out-prefix", default="synthetic_v2",
                   help="basename prefix for train/holdout/dropped outputs "
                        "(e.g. synthetic_v21 to keep rounds side by side)")
    p.add_argument("--feedback-frac", type=float, default=0.5,
                   help="target feedback fraction per split (default 0.5 = 50/50)")
    p.add_argument("--holdout-scenario-frac", type=float, default=0.4,
                   help="fraction of each rule's scenarios sent to the holdout (default 0.4)")
    p.add_argument("--trap-cap-frac", type=float, default=0.34,
                   help="max approve-traps as a fraction of feedback count per split "
                        "(anti-over-rejection ballast without flooding approves)")
    p.add_argument("--weight", type=float, default=1.0,
                   help="weight written on every row (v2 balances by COUNT, not oversampling)")
    p.add_argument("--real-balanced", dest="real_balanced", action="store_true", default=True,
                   help="also write a 50/50 slice of the real holdout_eval.jsonl (default ON)")
    p.add_argument("--no-real-balanced", dest="real_balanced", action="store_false")
    p.add_argument("--real-holdout", default=os.path.join(CUR, "holdout_eval.jsonl"))
    p.add_argument("--train-final", default=os.path.join(CUR, "train_final.jsonl"),
                   help="real train corpus, checked for prompt overlap (leakage guard)")
    p.add_argument("--seed", type=int, default=3407)
    return p.parse_args()


# --------------------------------------------------------------------------- #
# verdict helpers
# --------------------------------------------------------------------------- #
def strip_fence(text: str) -> str:
    t = text.strip()
    if t.startswith("```"):
        nl = t.find("\n")
        if nl != -1:
            t = t[nl + 1:]
        if t.rstrip().endswith("```"):
            t = t.rstrip()[:-3].rstrip()
    return t


def find_leaks(text: str):
    return [m for m in LEAK_MARKERS if m in text]


def gate_row(r):
    """Return (ok: bool, reason: str|None). Re-checks every contract independently of
    the workflow — never trust upstream for a training-data gate."""
    prompt = (r.get("prompt") or "").strip()
    completion = (r.get("completion") or "").strip()
    if not prompt or not completion:
        return False, "empty prompt/completion"
    for field, txt in (("prompt", prompt), ("completion", completion)):
        hits = find_leaks(txt)
        if hits:
            return False, f"template-token leak in {field}: {hits}"  # caller escalates to abort
    if "## Task:" not in prompt or "## Player report" not in prompt:
        return False, "prompt missing Task/Player-report sections"

    body = strip_fence(completion)
    if "`" in body:
        return False, "backtick inside verdict body (coach-verdict.gbnf forbids it)"
    try:
        obj = json.loads(body)
    except json.JSONDecodeError as e:
        return False, f"verdict JSON does not parse: {e}"
    if not isinstance(obj, dict):
        return False, "verdict is not a JSON object"
    dec = str(obj.get("decision", "")).strip().lower()
    if dec not in DECISIONS:
        return False, f"verdict.decision invalid: {obj.get('decision')!r}"

    row_dec = str(r.get("decision", "")).strip().lower()
    if row_dec not in DECISIONS:
        return False, f"row.decision invalid: {r.get('decision')!r}"
    if dec != row_dec:
        return False, f"verdict.decision ({dec}) != row.decision ({row_dec})"

    # label-integrity: feedback must reject something + raise a real issue;
    # approve must verify all + carry no blocking issue.
    cvs = obj.get("criteria_verification") or []
    issues = obj.get("issues") or []
    results = [str(c.get("result", "")).strip().lower() for c in cvs if isinstance(c, dict)]
    sevs = [str(i.get("severity", "")).strip().lower() for i in issues if isinstance(i, dict)]
    if dec == "feedback":
        if not any(x in ("rejected", "fail", "failed", "not_met", "unmet") for x in results):
            return False, "feedback verdict has no rejected criterion"
        if not any(s in ("must_fix", "should_fix", "blocking", "major") for s in sevs):
            return False, "feedback verdict has no actionable issue"
    else:  # approve
        if any(x in ("rejected", "fail", "failed", "not_met", "unmet") for x in results):
            return False, "approve verdict has a rejected criterion"
        if any(s in ("must_fix", "blocking", "critical") for s in sevs):
            return False, "approve verdict carries a blocking issue"

    if not r.get("blind_agrees", False):
        return False, "blind-verify disagreed (quarantined upstream)"
    return True, None


def out_row(r, split, weight):
    """Project to the train_final-compatible flat shape consumed by prepare_coach_sft.py
    and eval_coach.py (gold read from the completion)."""
    return {
        "prompt": r["prompt"],
        "completion": r["completion"],
        "decision": r["decision"],
        "source": "synthetic_v2",
        "rule": r.get("rule"),
        "variant": r.get("variant"),
        "task_id": r.get("task_id"),
        "turn": r.get("turn", 1),
        "task_title": r.get("task_title"),
        "scenario_id": r.get("scenario_id"),
        "flaw_mechanism": r.get("flaw_mechanism"),
        "weight": weight,
        "split": split,
    }


def balance_split(rows, feedback_frac, trap_cap_frac, rng):
    """From a pool of gated rows, keep all feedback + approve_control (matched pairs),
    then add approve_trap up to a cap, to approximate the target feedback fraction.
    Returns (kept_rows, excess_rows)."""
    fb = [r for r in rows if r["decision"] == "feedback"]
    ctrl = [r for r in rows if r["variant"] == "approve_control" and r["decision"] == "approve"]
    trap = [r for r in rows if r["variant"] == "approve_trap" and r["decision"] == "approve"]
    other_ap = [r for r in rows if r["decision"] == "approve"
                and r["variant"] not in ("approve_control", "approve_trap")]

    F = len(fb)
    # approves needed for the target fraction: ff = F / (F + A)  ->  A = F*(1-ff)/ff
    a_target = round(F * (1 - feedback_frac) / feedback_frac) if F else 0
    trap_cap = int(round(F * trap_cap_frac))

    approves_pool = ctrl + other_ap          # controls first (matched boundary)
    rng.shuffle(approves_pool)
    rng.shuffle(trap)

    chosen_ap = approves_pool[:a_target]
    remaining = max(0, a_target - len(chosen_ap))
    chosen_trap = trap[:min(trap_cap, remaining)] if remaining else trap[:trap_cap]
    # never let traps push approves past target
    if len(chosen_ap) + len(chosen_trap) > a_target:
        chosen_trap = chosen_trap[:max(0, a_target - len(chosen_ap))]

    kept = fb + chosen_ap + chosen_trap
    chosen_ids = {id(r) for r in kept}
    excess = [r for r in rows if id(r) not in chosen_ids]
    rng.shuffle(kept)
    return kept, excess


def main():
    args = parse_args()
    import random
    rng = random.Random(args.seed)

    raw = Path(args.raw)
    if not raw.exists():
        sys.exit(f"ERROR: raw file not found: {raw}\n"
                 f"  (write the workflow's `rows` output there first)")

    rows = [json.loads(l) for l in raw.open() if l.strip()]
    if not rows:
        sys.exit(f"ERROR: no rows in {raw}")

    # ---- gate ----
    gated, dropped = [], []
    abort_leaks = []
    for r in rows:
        ok, reason = gate_row(r)
        if ok:
            gated.append(r)
        else:
            if reason and "template-token leak" in reason:
                abort_leaks.append((r.get("scenario_id"), reason))
            dropped.append({**{k: r.get(k) for k in
                               ("rule", "scenario_id", "variant", "decision")},
                            "drop_reason": reason})
    if abort_leaks:
        print("ABORT: template-token leaks detected (runbook Phase 0.2). Fix the generator.")
        for sid, reason in abort_leaks[:20]:
            print(f"  {sid}: {reason}")
        sys.exit(1)

    # ---- dedup by exact prompt ----
    seen = set()
    deduped = []
    for r in gated:
        key = r["prompt"].strip()
        if key in seen:
            dropped.append({"rule": r.get("rule"), "scenario_id": r.get("scenario_id"),
                            "variant": r.get("variant"), "decision": r.get("decision"),
                            "drop_reason": "duplicate prompt"})
            continue
        seen.add(key)
        deduped.append(r)

    # ---- leakage guard vs the real corpus ----
    real_prompts = set()
    for path in (args.train_final, args.real_holdout):
        p = Path(path)
        if p.exists():
            for l in p.open():
                l = l.strip()
                if not l:
                    continue
                try:
                    real_prompts.add(json.loads(l).get("prompt", "").strip())
                except json.JSONDecodeError:
                    pass
    leaked = [r for r in deduped if r["prompt"].strip() in real_prompts]
    if leaked:
        sys.exit(f"ABORT: {len(leaked)} synthetic prompts overlap the real corpus — investigate.")

    # ---- split by scenario (disjoint), per-rule, then balance each split ----
    by_rule = defaultdict(lambda: defaultdict(list))   # rule -> scenario_id -> rows
    for r in deduped:
        by_rule[r.get("rule")][r.get("scenario_id")].append(r)

    train_pool, holdout_pool = [], []
    for rule, scen_map in by_rule.items():
        scen_ids = sorted(scen_map.keys())
        rng.shuffle(scen_ids)
        n_hold = max(1, round(len(scen_ids) * args.holdout_scenario_frac)) if len(scen_ids) > 1 else 0
        hold_ids = set(scen_ids[:n_hold])
        for sid in scen_ids:
            (holdout_pool if sid in hold_ids else train_pool).extend(scen_map[sid])

    train, train_excess = balance_split(train_pool, args.feedback_frac, args.trap_cap_frac, rng)
    holdout, hold_excess = balance_split(holdout_pool, args.feedback_frac, args.trap_cap_frac, rng)
    for r in train_excess + hold_excess:
        dropped.append({"rule": r.get("rule"), "scenario_id": r.get("scenario_id"),
                        "variant": r.get("variant"), "decision": r.get("decision"),
                        "drop_reason": "balance excess (approve over target)"})

    # ---- write ----
    out = Path(args.curated)
    out.mkdir(parents=True, exist_ok=True)
    train_path = out / f"{args.out_prefix}_train.jsonl"
    hold_path = out / f"{args.out_prefix}_holdout.jsonl"
    drop_path = out / f"{args.out_prefix}_dropped.jsonl"

    with train_path.open("w") as f:
        for r in train:
            f.write(json.dumps(out_row(r, "train", args.weight), ensure_ascii=False) + "\n")
    with hold_path.open("w") as f:
        for r in holdout:
            f.write(json.dumps(out_row(r, "holdout", args.weight), ensure_ascii=False) + "\n")
    with drop_path.open("w") as f:
        for d in dropped:
            f.write(json.dumps(d, ensure_ascii=False) + "\n")

    # ---- optional: real-balanced holdout (the honest gate) ----
    real_balanced_info = ""
    if args.real_balanced:
        rp = Path(args.real_holdout)
        if rp.exists():
            real = [json.loads(l) for l in rp.open() if l.strip()]
            fb = [r for r in real if str(r.get("decision", "")).lower() == "feedback"]
            ap = [r for r in real if str(r.get("decision", "")).lower() == "approve"]
            rng.shuffle(ap)
            k = min(len(fb), len(ap))
            balanced = fb[:k] + ap[:k]
            rng.shuffle(balanced)
            rb_path = out / "holdout_balanced_real.jsonl"
            with rb_path.open("w") as f:
                for r in balanced:
                    f.write(json.dumps(r, ensure_ascii=False) + "\n")
            real_balanced_info = (f"\nreal-balanced holdout: {rb_path}  "
                                  f"({k} feedback + {k} approve = {2*k} rows, 50/50)")
        else:
            real_balanced_info = f"\nreal-balanced holdout: SKIPPED (missing {rp})"

    # ---- report ----
    def dist(rows_):
        c = Counter(r["decision"] for r in rows_)
        n = sum(c.values()) or 1
        return f"{len(rows_)} rows | " + ", ".join(
            f"{k}={c[k]} ({100*c[k]/n:.0f}%)" for k in ("feedback", "approve"))

    print(f"\n{'='*68}\nsynthetic v2 assembly — {raw.name}\n{'='*68}")
    print(f"raw rows         : {len(rows)}")
    print(f"gated (passed)   : {len(gated)}   dropped at gate/dedup/balance: {len(dropped)}")
    print(f"rules covered    : {len(by_rule)}")
    print(f"\nTRAIN  -> {train_path}\n  {dist(train)}")
    print(f"  by variant: {dict(Counter(r['variant'] for r in train))}")
    print(f"  rules: {dict(Counter(r.get('rule') for r in train))}")
    print(f"\nHOLDOUT-> {hold_path}\n  {dist(holdout)}")
    print(f"  by variant: {dict(Counter(r['variant'] for r in holdout))}")
    print(f"  rules: {dict(Counter(r.get('rule') for r in holdout))}")
    print(f"\ndropped detail -> {drop_path}")
    drc = Counter(d["drop_reason"] for d in dropped)
    for reason, n in drc.most_common():
        print(f"  {n:3d}  {reason}")
    print(real_balanced_info)
    # scenario-disjointness assertion
    tr_sc = {r.get("scenario_id") for r in train}
    ho_sc = {r.get("scenario_id") for r in holdout}
    overlap = tr_sc & ho_sc
    print(f"\nscenario-disjoint train/holdout: {'OK' if not overlap else f'VIOLATED {overlap}'}")
    print(f"{'='*68}\n")


if __name__ == "__main__":
    main()
