#!/usr/bin/env python3
"""
finalize_v2_corpus.py — deterministic clean-up that closes the cue-hardening loop
================================================================================
After 3 generation rounds the SPURIOUS cues (round-1 lexical, round-2 numeric) are fixed;
the residuals are mechanical and best removed deterministically rather than with a 4th
prose round (see project_coach_v2_synthetic memory / RETRO). This merges the best of the
last two rounds into one final raw corpus:

  * BASE = round 3 (`synthetic_v22_raw.jsonl`) — numeric leak fixed, namespace fixed.
  * DROP `hard_pair` rows — they were meant to invert cues but BACKFIRED twice, and are the
    main source of the intensifier skew (they were told to put approve-words in feedback).
  * BACKFILL the collapsed rule (harness-cancellation, 0 feedback in round 3) from round 2
    (`synthetic_v21_raw.jsonl`), which had a healthy 5 fb / 5 ap for it — taking only its
    `standard` matched pairs so the rule regains both classes.
  * STRIP decorative intensifier phrases from player-reports (both labels) so self-assured
    tone cannot stand in for judgment; prompts are re-rendered from the cleaned report.

Output: <out_prefix>_raw.jsonl (feed to audit_cue_leakage.py then assemble_synthetic_v2.py).

Usage:
    python finalize_v2_corpus.py \
        --round3 ~/coach-dataset/curated/synthetic_v22_raw.jsonl \
        --round2 ~/coach-dataset/curated/synthetic_v21_raw.jsonl \
        --out    ~/coach-dataset/curated/synthetic_v2final_raw.jsonl
"""
import argparse
import json
import re
from pathlib import Path

HARNESS = "harness-cancellation-contract.md"

# Decorative self-assurance phrases that leaked toward feedback (round-2/3 residual).
# Mapped to neutral text (or removed) so tone is not a class signal. Order matters.
INTENSIFIERS = [
    (r"\bno shortcuts?\b", ""),
    (r"\brock[- ]solid\b", "working"),
    (r"\bend[- ]to[- ]end\b", "integration"),
    (r"\bgenuinely\b", ""),
    (r"\bgenuine\b", "actual"),
    (r"\bconfident(?:ly)?\b", ""),
    (r"\brigorous(?:ly)?\b", ""),
    (r"\bthoroughly\b", ""),
    (r"\bproperly\b", ""),
]

HEADER = ("You are the Coach in an adversarial Player-Coach build loop. Verify the Player's "
          "work against EACH acceptance criterion and return a verdict: `approve` only when "
          "every criterion is genuinely met with real (not mocked, not absent, not "
          "zero-cardinality) evidence; otherwise `feedback` naming the specific gap.")
FOOTER = ("Return the verdict as a fenced ```json block with keys: decision, "
          "criteria_verification, issues, rationale.")


def strip_intensifiers(text):
    out = text
    for pat, repl in INTENSIFIERS:
        out = re.sub(pat, repl, out, flags=re.IGNORECASE)
    out = re.sub(r"  +", " ", out)            # collapse double spaces left by removals
    out = re.sub(r" ([,.;:])", r"\1", out)     # tidy " ," -> ","
    return out


def rerender_prompt(row):
    acs = "\n".join(f"- [ ] {a}" for a in (row.get("acceptance_criteria") or []))
    return (f"{HEADER}\n\n## Task: {row['task_title']}\n{acs}\n\n"
            f"## Player report\n{row['player_report']}\n\n{FOOTER}")


def load(path):
    return [json.loads(l) for l in Path(path).open() if l.strip()]


def main():
    ap = argparse.ArgumentParser(description="Finalize the v2 Coach corpus deterministically")
    ap.add_argument("--round3", required=True)
    ap.add_argument("--round2", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--keep-hard-pair", action="store_true",
                    help="keep hard_pair rows (default drops them — they backfired)")
    ap.add_argument("--no-strip", action="store_true", help="skip intensifier stripping")
    args = ap.parse_args()

    r3 = load(args.round3)
    r2 = load(args.round2)

    final = []
    # round 3 base: drop hard_pair, drop the collapsed harness rule (backfilled below)
    for r in r3:
        if not args.keep_hard_pair and r.get("kind") == "hard_pair":
            continue
        if r.get("rule") == HARNESS:
            continue
        final.append(r)
    # backfill harness from round 2 (standard matched pairs only)
    backfilled = 0
    for r in r2:
        if r.get("rule") == HARNESS and r.get("kind") == "standard":
            final.append(r)
            backfilled += 1

    # strip intensifiers + re-render the prompt from the cleaned report
    n_stripped = 0
    if not args.no_strip:
        for r in final:
            cleaned = strip_intensifiers(r["player_report"])
            if cleaned != r["player_report"]:
                n_stripped += 1
            r["player_report"] = cleaned
            r["prompt"] = rerender_prompt(r)
            r["source_round"] = "r2" if r.get("rule") == HARNESS else "r3"

    out = Path(args.out)
    with out.open("w") as f:
        for r in final:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    from collections import Counter
    dec = Counter(r["decision"] for r in final)
    print(f"finalized {len(final)} rows -> {out}")
    print(f"  decisions: {dict(dec)}")
    print(f"  harness backfilled from round 2: {backfilled} rows")
    print(f"  hard_pair dropped: {'no' if args.keep_hard_pair else 'yes'}")
    print(f"  intensifier-stripped reports: {n_stripped}")
    print("  per-rule fb/ap:")
    rules = sorted({r["rule"] for r in final})
    for rule in rules:
        rr = [r for r in final if r["rule"] == rule]
        cfb = sum(1 for r in rr if r["decision"] == "feedback")
        cap = sum(1 for r in rr if r["decision"] == "approve")
        print(f"    fb={cfb:>2} ap={cap:>2}  {rule}")


if __name__ == "__main__":
    main()
