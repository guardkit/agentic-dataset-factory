#!/usr/bin/env python3
"""
extract_workflow_rows.py — pull a Coach-generator Workflow's result into JSONL
=============================================================================
The coach-v2 / coach-v2.1 generator workflows return {rows, all_rows, cue_audit,
quarantined, stats}. The runtime saves that to a task .output file. This unpacks it
into the files the assembler / cue gate consume, so reprocessing is one command.

Usage:
    python extract_workflow_rows.py <task.output> <out_prefix>
        e.g. python extract_workflow_rows.py /tmp/.../wuorwb04z.output \\
                 ~/coach-dataset/curated/synthetic_v21
    writes <out_prefix>_raw.jsonl (kept rows), <out_prefix>_allrows.jsonl,
           <out_prefix>_cue_audit.json, <out_prefix>_quarantined.json
"""
import json
import sys
from pathlib import Path


def main():
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    src, prefix = Path(sys.argv[1]), sys.argv[2]
    d = json.load(src.open())
    payload = None
    for cand in (d.get("result"), d):
        if isinstance(cand, dict) and "rows" in cand:
            payload = cand
            break
    if payload is None and isinstance(d.get("result"), str):
        payload = json.loads(d["result"])
    if payload is None:
        sys.exit("could not find a payload with 'rows' in the output file")

    rows = payload.get("rows", [])
    allrows = payload.get("all_rows", rows)
    with open(f"{prefix}_raw.jsonl", "w") as o:
        for r in rows:
            o.write(json.dumps(r, ensure_ascii=False) + "\n")
    with open(f"{prefix}_allrows.jsonl", "w") as o:
        for r in allrows:
            o.write(json.dumps(r, ensure_ascii=False) + "\n")
    json.dump(payload.get("cue_audit", {}), open(f"{prefix}_cue_audit.json", "w"), indent=2)
    json.dump(payload.get("quarantined", []), open(f"{prefix}_quarantined.json", "w"), indent=2)
    print("stats:", json.dumps(payload.get("stats", {})))
    print(f"wrote {prefix}_raw.jsonl (kept={len(rows)}), _allrows.jsonl ({len(allrows)}), "
          f"_cue_audit.json, _quarantined.json")


if __name__ == "__main__":
    main()
