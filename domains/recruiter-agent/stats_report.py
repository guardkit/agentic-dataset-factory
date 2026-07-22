#!/usr/bin/env python
"""Emit the recruiter-corpus STATS report (a corpus data artifact, like DCL's COMPARISON doc).

Reads, with ZERO model calls:
  * briefs.yaml            — the per-class `target_rows` (the coverage plan's goal);
  * the staging run dirs    — `run-manifest.json` (attempted/accepted/rejected/deduped per class)
                              and `rejected.jsonl` (for the reason histogram);
  * the frozen corpus/      — train.jsonl + val.jsonl (the achieved per-class totals + provenance).

Prints a Markdown report to --out: rows-per-class vs target, the rejection-reason histogram, the
checker pass rates, and an explicit HONEST SHORTFALL line per under-target class. A class that will
not generate at acceptable quality is a FINDING, never fudged.

    ./.venv/bin/python stats_report.py --run-dirs pilot-runs/run-full --out corpus/STATS.md
"""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

DOMAIN_DIR = Path(__file__).resolve().parent


def _load_jsonl(p: Path) -> list[dict]:
    out = []
    if p.exists():
        for line in p.open(encoding="utf-8"):
            line = line.strip()
            if line:
                out.append(json.loads(line))
    return out


def _reason_bucket(reason: str) -> str:
    """Coarse-grain a rejection reason for the histogram."""
    r = reason.lower()
    if r.startswith("contamination"):
        return "contamination (eval-held)"
    if "config-check failed" in r:
        return "checker: config-check failed"
    if "validate failed" in r or "violation" in r:
        return "checker: pipeline-validate failed"
    if r.startswith("sorting mismatch") or "must not draft a clerk" in r or "must still draft" in r:
        return "sorting-rule mismatch"
    if "anchor mismatch" in r:
        return "anchor cross-check mismatch"
    if "faked integration" in r or "fabricated-integration" in r:
        return "faked integration in draft"
    if "placeholder" in r or "pack law 2" in r:
        return "invented golden (pack law 2)"
    if "residency" in r:
        return "residency (pack law 1)"
    if "egress" in r or "write_scope" in r or "smuggled" in r or "network_capable" in r:
        return "injection: granted egress/scope"
    if "must name" in r or "name the wall" in r or "parameter" in r:
        return "did not name it (parameter/wall)"
    return "other"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-dirs", nargs="+", required=True)
    ap.add_argument("--briefs", default=str(DOMAIN_DIR / "briefs.yaml"))
    ap.add_argument("--corpus", default=str(DOMAIN_DIR / "corpus"))
    ap.add_argument("--out", default=str(DOMAIN_DIR / "corpus" / "STATS.md"))
    args = ap.parse_args()

    import yaml
    briefs = yaml.safe_load(Path(args.briefs).read_text(encoding="utf-8"))
    targets = {c["id"]: c["target_rows"] for c in briefs["classes"]}
    n_briefs = {c["id"]: len(c["briefs"]) for c in briefs["classes"]}

    run_dirs = [Path(p) if Path(p).is_absolute() or Path(p).exists() else DOMAIN_DIR / "pilot-runs" / p
                for p in args.run_dirs]

    # aggregate — derive per-class accepted/rejected + reasons DIRECTLY from the streamed files
    # (robust to a partial/mid-run freeze where run-manifest.json is not yet written); the run-manifest
    # only supplies extras (deduped, author_reps) when present.
    agg = defaultdict(lambda: {"accepted": 0, "rejected": 0})
    totals = Counter()
    reason_hist = Counter()
    reason_by_class = defaultdict(Counter)
    accept_attempt = Counter()
    author_reps = []
    player_models = set()
    for rd in run_dirs:
        for row in _load_jsonl(rd / "accepted.jsonl"):
            md = row.get("metadata", {})
            agg[md.get("class", "?")]["accepted"] += 1
            totals["accepted"] += 1
            prov = md.get("provenance", {})
            accept_attempt[prov.get("accept_attempt", "?")] += 1
            if prov.get("player_model"):
                player_models.add(prov["player_model"])
        for rej in _load_jsonl(rd / "rejected.jsonl"):
            agg[rej.get("class", "?")]["rejected"] += 1
            totals["rejected"] += 1
            b = _reason_bucket(rej.get("reason", ""))
            reason_hist[b] += 1
            reason_by_class[rej.get("class", "?")][b] += 1
            if b == "contamination (eval-held)":
                totals["contaminated"] += 1
        mp = rd / "run-manifest.json"
        if mp.exists():
            m = json.loads(mp.read_text(encoding="utf-8"))
            totals["deduped"] += m.get("counts", {}).get("deduped", 0)
            if m.get("author_reps"):
                author_reps.append(m["author_reps"])
            if m.get("player_model"):
                player_models.add(m["player_model"])
    totals["attempted"] = totals["accepted"] + totals["rejected"] + totals["deduped"]

    # frozen corpus per-class
    corpus_dir = Path(args.corpus)
    corp_manifest = {}
    cm = corpus_dir / "manifest.json"
    if cm.exists():
        corp_manifest = json.loads(cm.read_text(encoding="utf-8"))
    by_class_final = corp_manifest.get("by_class", {})

    # checker pass rate: accepted / (accepted + checker-failure rejects)
    checker_fail = reason_hist["checker: config-check failed"] + reason_hist["checker: pipeline-validate failed"]

    lines: list[str] = []
    A = lines.append
    A("# Recruiter corpus — generation STATS")
    A("")
    A(f"- Teacher seat(s): {', '.join(sorted(player_models)) or 'n/a'} · author_reps: "
      f"{max(author_reps) if author_reps else 'n/a'} · source run dir(s): "
      f"{', '.join(str(r.name) for r in run_dirs)}")
    A(f"- Attempted: **{totals['attempted']}** · accepted: **{totals['accepted']}** · "
      f"rejected: **{totals['rejected']}** · deduped: **{totals['deduped']}** · "
      f"contaminated: **{totals['contaminated']}**")
    tot_final = corp_manifest.get("counts", {})
    A(f"- Frozen corpus: **{tot_final.get('rows', 0)} rows** "
      f"(train {tot_final.get('train', 0)} / val {tot_final.get('val', 0)}); "
      f"dedup across runs {tot_final.get('dedup_across_runs', 0)}")
    if totals["attempted"]:
        A(f"- Overall accept rate: **{100*totals['accepted']/totals['attempted']:.0f}%** "
          f"({totals['accepted']}/{totals['attempted']} attempts)")
    checked = totals["accepted"] + checker_fail
    if checked:
        A(f"- Checker pass rate (accepted vs checker-refused): "
          f"**{100*totals['accepted']/checked:.0f}%** — {checker_fail} draft(s) refused by the office's "
          f"own validators (config-check / pipeline-validate)")
    fp = accept_attempt.get(0, 0)
    rp = sum(v for k, v in accept_attempt.items() if k not in (0, "?"))
    if totals["accepted"]:
        A(f"- Admitted first-pass: **{fp}** · after one bounded repair: **{rp}** "
          f"({100*fp/totals['accepted']:.0f}% first-pass clean)")
    A("")
    A("## Rows per class vs the coverage plan")
    A("")
    A("| Class | Sorting | Target | Frozen (train/val) | Attempts acc/rej | vs target |")
    A("|---|---|---:|---:|---:|:--|")
    total_target = 0
    total_frozen = 0
    shortfalls = []
    for c in briefs["classes"]:
        cid = c["id"]
        tgt = targets[cid]
        total_target += tgt
        fin = by_class_final.get(cid, {})
        frozen = fin.get("total", 0)
        total_frozen += frozen
        acc = agg[cid]["accepted"]
        rej = agg[cid]["rejected"]
        pct = (100 * frozen / tgt) if tgt else 0
        flag = "✓ met" if frozen >= tgt else (f"⚠ {pct:.0f}% of target" if frozen else "✗ none")
        if frozen < tgt:
            shortfalls.append((cid, tgt, frozen, pct))
        A(f"| `{cid}` | {c['expected_class']} | {tgt} | {frozen} "
          f"({fin.get('train', 0)}/{fin.get('val', 0)}) | {acc}/{rej} | {flag} |")
    A(f"| **TOTAL** | | **{total_target}** | **{total_frozen}** | | "
      f"**{100*total_frozen/total_target:.0f}% of plan** |")
    A("")
    A("## Rejection-reason histogram (all run dirs)")
    A("")
    if reason_hist:
        A("| Reason bucket | Count |")
        A("|---|---:|")
        for b, n in reason_hist.most_common():
            A(f"| {b} | {n} |")
    else:
        A("_no rejections recorded_")
    A("")
    A("## Honest shortfalls (findings, not fudged)")
    A("")
    if shortfalls:
        for cid, tgt, frozen, pct in shortfalls:
            top = reason_by_class[cid].most_common(2)
            top_s = ", ".join(f"{b} ({n})" for b, n in top) or "n/a"
            A(f"- **`{cid}`**: {frozen}/{tgt} ({pct:.0f}% of target). "
              f"Dominant reject reasons: {top_s}. From {n_briefs[cid]} seed briefs.")
    else:
        A("- Every class met its target.")
    A("")
    A("_val is a loss-only monitoring split (per-class-stratified, deterministic by row_id, disjoint), "
      "NOT the pass exam — the four banked sessions are the exam, never in this corpus (denylist enforced)._")

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {out} ({len(lines)} lines)")
    print("\n".join(lines[:14]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
