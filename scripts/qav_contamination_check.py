#!/usr/bin/env python3
"""qav_contamination_check — hold-out discipline gate (PLAN §6, OUTPUT-CONTRACT §5).

Asserts the train/eval split is clean before a training manifest is finalized:
  * ``train.row_id ∩ eval.row_id = ∅``
  * no (repo, task, recipe_family) sibling-variant straddles the split
  * no training row is generated from a gold-negative source task

Exit 0 = PASS (safe to embed in the manifest), 1 = FAIL (refuse the manifest).

Usage:
    python scripts/qav_contamination_check.py --train output/qa-verifier/train.jsonl \\
        --eval output/qa-verifier/eval_qav.jsonl [--eval-manifest qav-phase1-eval.manifest.json]

Runnable now (no GPU, no generation run) — it operates on already-written jsonl.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Allow running as a script without installing the package (pythonpath=src in pytest,
# but the CLI may be invoked directly).
_SRC = Path(__file__).resolve().parent.parent / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from qav.contamination import check_contamination, load_jsonl  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="QAV train/eval contamination gate")
    ap.add_argument("--train", required=True, help="training rows JSONL")
    ap.add_argument("--eval", required=True, help="eval_qav rows JSONL")
    ap.add_argument("--eval-manifest", default=None, help="eval manifest path (recorded in output)")
    ap.add_argument("--json", action="store_true", help="emit the contamination_check block as JSON")
    args = ap.parse_args(argv)

    train = load_jsonl(args.train)
    eval_rows = load_jsonl(args.eval)
    result = check_contamination(train, eval_rows, eval_manifest=args.eval_manifest)

    if args.json:
        print(json.dumps(result.to_dict(), indent=2))
    else:
        print(f"train rows: {len(train)}  eval rows: {len(eval_rows)}")
        print(f"row_id intersection: {len(result.intersection)}")
        print(f"sibling-variant violations: {len(result.sibling_violations)}")
        print(f"gold-negative source-task violations: {len(result.gold_source_violations)}")
        for v in result.intersection:
            print(f"  INTERSECTION row_id {v}")
        for v in result.sibling_violations:
            print(f"  SIBLING {v['repo']}/{v['task']} family={v['family']}")
        for v in result.gold_source_violations:
            print(f"  GOLD-SOURCE train row from {v['repo']}/{v['task']}")
        print(f"VERDICT: {result.status.upper()}")

    return 0 if result.passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
