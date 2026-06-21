#!/usr/bin/env python3
"""extract_specs.py — recover the `SPEC_JSONL <json>` lines emitted by the
generation workflow (workflow scripts can't write files) into a specs JSONL.

Searches the workflow run transcript dir for lines containing the SPEC_JSONL
sentinel and writes the JSON payloads to --out, de-duplicated by scenario_id.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

SENTINEL = "SPEC_JSONL "


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-dir", required=True, help="workflow run transcript dir (contains agent-*.jsonl)")
    ap.add_argument("--out", default="step0_synth_specs.jsonl")
    args = ap.parse_args()

    seen: dict[str, dict] = {}
    for p in Path(args.run_dir).rglob("*.jsonl"):
        text = p.read_text(errors="ignore")
        for m in re.finditer(re.escape(SENTINEL) + r"(\{.*)$", text, re.MULTILINE):
            payload = m.group(1)
            # the sentinel may be embedded in an escaped JSON log string; try direct then unescape
            for candidate in (payload, payload.encode().decode("unicode_escape")):
                try:
                    obj = json.loads(candidate)
                    if isinstance(obj, dict) and obj.get("scenario_id"):
                        seen[obj["scenario_id"]] = obj
                    break
                except Exception:
                    continue

    rows = [seen[k] for k in sorted(seen)]
    Path(args.out).write_text("".join(json.dumps(r) + "\n" for r in rows))
    print(f"extracted {len(rows)} specs -> {args.out}")
    if rows:
        from collections import Counter
        print("balance:", dict(Counter(r.get("gold") for r in rows)))
        print("guards :", dict(Counter(r.get("guard_targeted") for r in rows)))


if __name__ == "__main__":
    main()
