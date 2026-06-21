#!/usr/bin/env python3
"""prep_teacher_args.py — from an assembled eval JSONL (prompt + scenario_id +
decision), write per-scenario prompt .txt files and a compact teacher-args JSON
(list of {scenario_id, gold, guard, prompt_path}) for the teacher-verdict /
blind-verify workflows (agents Read the path, avoiding huge inline args).
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--eval", required=True)
    ap.add_argument("--prompt-dir", required=True)
    ap.add_argument("--args-out", required=True)
    args = ap.parse_args()

    os.makedirs(args.prompt_dir, exist_ok=True)
    rows = [json.loads(l) for l in Path(args.eval).open() if l.strip()]
    out = []
    for r in rows:
        sid = r["scenario_id"]
        p = Path(args.prompt_dir) / f"{sid}.txt"
        p.write_text(r["prompt"])
        out.append({
            "scenario_id": sid,
            "gold": r["decision"],
            "guard": r.get("guard_targeted"),
            "prompt_path": str(p.resolve()),
        })
    Path(args.args_out).write_text(json.dumps(out))
    print(f"wrote {len(out)} prompt files -> {args.prompt_dir} and args -> {args.args_out}")


if __name__ == "__main__":
    main()
