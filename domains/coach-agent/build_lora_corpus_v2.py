#!/usr/bin/env python3
"""
build_lora_corpus_v2.py — balanced LoRA training corpus from CURRENT data (no new generation)
=============================================================================================
Step-3 proved the cue-hardened synthetic data carries strong judgment (false-approval 94%->12%
on the cue-immune real holdout) but few-shot over-rejects — calibration needs balanced-gradient
fine-tuning. The 28-row synthetic-only set is too small to calibrate a 26B MoE LoRA. This builds
the proper "tiny" balanced corpus the v1 RETRO called for ("rebalance toward feedback, target
~40-50%"), combining what we already have:

  feedback = ALL real feedback (train_final.jsonl) + ALL synthetic v2 feedback (the new
             taxonomy-grounded failure coverage)
  approve  = an equal-sized slice (real approves + synthetic approve controls/traps)

Result: ~50/50 by COUNT (weight 1.0 everywhere; stage with prepare_coach_sft --weight-mode none).
No leakage: real rows come from train_final (disjoint from holdout_eval by curation); synthetic
rows come from synthetic_v2final_train (scenario-disjoint from synthetic_v2final_holdout).
prepare_coach_sft re-checks leakage against the holdout when staging.

Usage:
    python build_lora_corpus_v2.py \
        --real ~/coach-dataset/curated/train_final.jsonl \
        --synth ~/coach-dataset/curated/synthetic_v2final_train.jsonl \
        --out ~/coach-dataset/curated/lora_v2_balanced.jsonl
"""
import argparse
import json
import os
import random
from collections import Counter
from pathlib import Path

CUR = os.path.expanduser("~/coach-dataset/curated")


def load(path):
    return [json.loads(l) for l in Path(path).open() if l.strip()]


def dec(r):
    return str(r.get("decision", "")).strip().lower()


def main():
    ap = argparse.ArgumentParser(description="Build a balanced real+synthetic LoRA corpus")
    ap.add_argument("--real", default=os.path.join(CUR, "train_final.jsonl"))
    ap.add_argument("--synth", default=os.path.join(CUR, "synthetic_v2final_train.jsonl"))
    ap.add_argument("--out", default=os.path.join(CUR, "lora_v2_balanced.jsonl"))
    ap.add_argument("--seed", type=int, default=3407)
    ap.add_argument("--approve-ratio", type=float, default=1.0,
                    help="approves per feedback (1.0 = 50/50; >1 leans approve to soften over-rejection)")
    args = ap.parse_args()
    rng = random.Random(args.seed)

    real = load(args.real)
    synth = load(args.synth)
    real_fb = [r for r in real if dec(r) == "feedback"]
    real_ap = [r for r in real if dec(r) == "approve"]
    synth_fb = [r for r in synth if dec(r) == "feedback"]
    synth_ap = [r for r in synth if dec(r) == "approve"]

    feedback = real_fb + synth_fb
    n_fb = len(feedback)
    n_ap_target = round(n_fb * args.approve_ratio)

    # prefer synthetic approves (cue-reduced, matched controls), then fill from real approves
    rng.shuffle(real_ap)
    approve = synth_ap + real_ap[:max(0, n_ap_target - len(synth_ap))]
    approve = approve[:n_ap_target]

    rows = feedback + approve
    # normalize weight so the balance is purely by count (stage with --weight-mode none)
    for r in rows:
        r["weight"] = 1.0
    rng.shuffle(rows)

    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    with open(args.out, "w") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    src = Counter(r.get("source", "?") for r in rows)
    print(f"wrote {len(rows)} rows -> {args.out}")
    print(f"  feedback={n_fb} (real {len(real_fb)} + synth {len(synth_fb)})  "
          f"approve={len(approve)} (synth {len(synth_ap)} + real {len(approve)-len(synth_ap)})")
    print(f"  balance: {Counter(dec(r) for r in rows)}")
    print(f"  source : {dict(src)}")


if __name__ == "__main__":
    main()
