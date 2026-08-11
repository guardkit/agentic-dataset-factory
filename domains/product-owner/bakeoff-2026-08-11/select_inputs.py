#!/usr/bin/env python3
"""Bake-off input selector — deterministic, run ONCE before any candidate generates.

Selects the 9 pre-declared inputs for the 2026-08-11 teacher bake-off:
  GF-1..3  greenfield briefs   — real capture survivors, replayed verbatim
  FS-1..3  feature-spec briefs — real capture survivors, replayed verbatim
  EX-1..3  extract corpora     — POHARVEST mode=extract source docs + the
                                 production extract system prompt

The idea shape is EXCLUDED, with the receipt in the selection run: every one
of the 34 idea-mode captures carries a probe-grade input (23-49 chars: "x",
"Test", "AI-powered code review tool") — there are no real idea briefs to
replay, so grading teachers on that shape would grade toy inputs. Idea-mode
corpus rows are teacher-authored (synthetic, marked) like extract and scope.

Selection is position-based (first / middle / last of each sorted survivor
list), so re-running this script reproduces the identical manifest.
A leakage guard aborts if any payload carries exam-identifying content.

Sources are read-only. Payloads land beside this script in inputs/, with
MANIFEST.sha256 as the anti-fishing receipt (committed before generation).
"""

import hashlib
import json
import re
import sys
from pathlib import Path

CAPTURE_DIR = Path("/home/richardwoollcott/Projects/appmilla_github/specialist-agent/output")
POHARVEST = Path("/home/richardwoollcott/po-dataset/po_history_records.jsonl")
EXTRACT_PROMPT = Path(
    "/home/richardwoollcott/Projects/appmilla_github/specialist-agent/roles/product-owner/prompts/player_extract.md"
)
OUT_DIR = Path(__file__).parent / "inputs"

# Strings that identify the eight frozen exam tasks. Any hit in any payload is fatal:
# the exam must never leak into teacher inputs (and thus never into the corpus).
EXAM_MARKERS = [
    "FinProxy", "finproxy",
    "RoundRoute", "roundroute",
    "HomeStretch", "homestretch",
    "kiln-firing", "kiln firing",
    "member-directory-search", "member directory search",
    "po-held-0",
]

MIN_SCORE = 0.6
MIN_OUTPUT_CHARS = 1500
MIN_INPUT_CHARS = 150
EXTRACT_DOC_MIN = 10_000
EXTRACT_DOC_MAX = 120_000


def load_captures():
    records = []
    for f in sorted(CAPTURE_DIR.glob("*.json")):
        if f.name in ("-session-log.json", "validation.json"):
            continue
        try:
            d = json.loads(f.read_text())
        except (json.JSONDecodeError, UnicodeDecodeError):
            continue
        if d.get("schema_version") != "2.0":
            continue
        records.append((f, d))
    return records


def survivor_shape(d):
    comp = d.get("completion") or {}
    if comp.get("verdict") not in ("GOOD", "ACCEPTABLE"):
        return None
    if (comp.get("final_score") or 0) < MIN_SCORE:
        return None
    its = d.get("iterations") or []
    if not its:
        return None
    first, last = its[0], its[-1]
    pi = first.get("player_input")
    if not isinstance(pi, dict) or not pi.get("messages"):
        return None
    total_in = sum(len(m.get("content") or "") for m in pi["messages"])
    if total_in < MIN_INPUT_CHARS:
        return None
    out = last.get("stripped_output") or last.get("raw_output") or ""
    if len(out) < MIN_OUTPUT_CHARS:
        return None
    if re.search(r'"mode"\s*:\s*"greenfield"', out):
        return "GF"
    if re.search(r'"mode"\s*:\s*"idea"', out):
        return "ID"
    if "Feature:" in out and "Scenario" in out and ("_assumptions" in out or "ASSUM-" in out):
        return "FS"
    return None


def pick_three(items):
    if len(items) < 3:
        raise SystemExit(f"FATAL: fewer than 3 survivors for a shape ({len(items)})")
    return [items[0], items[len(items) // 2], items[-1]]


def leakage_check(payload_text, bakeoff_id):
    hits = [m for m in EXAM_MARKERS if m in payload_text]
    if hits:
        raise SystemExit(f"FATAL leakage: {bakeoff_id} carries exam markers {hits}")


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    by_shape = {"GF": [], "ID": [], "FS": []}
    for f, d in load_captures():
        shape = survivor_shape(d)
        if shape:
            by_shape[shape].append((d.get("session_id") or f.stem, f, d))
    for shape in by_shape:
        by_shape[shape].sort(key=lambda t: t[0])

    # Greenfield: 43 records collapse to 6 distinct briefs (the same real feature
    # captured repeatedly). Select across DISTINCT briefs — earliest session per
    # brief — so the bake-off never grades the same brief twice. Feature-spec is
    # already 39-distinct-in-39, so dedup is a no-op there.
    for shape in by_shape:
        seen = set()
        distinct = []
        for session_id, f, d in by_shape[shape]:
            content = "\n".join(str(m.get("content")) for m in d["iterations"][0]["player_input"]["messages"])
            h = hashlib.sha256(content.encode()).hexdigest()
            if h in seen:
                continue
            seen.add(h)
            distinct.append((session_id, f, d))
        by_shape[shape] = distinct

    payloads = []
    for shape in ("GF", "FS"):
        for i, (session_id, f, d) in enumerate(pick_three(by_shape[shape]), 1):
            msgs = d["iterations"][0]["player_input"]["messages"]
            head = (msgs[0].get("content") or "")[:80].replace("\n", " ")
            print(f"{shape}-{i} input head: {head!r}")
            payloads.append({
                "bakeoff_id": f"{shape}-{i}",
                "source": {"type": "capture", "file": f.name, "session_id": session_id},
                "messages": msgs,
            })

    rows = [json.loads(l) for l in POHARVEST.read_text().splitlines() if l.strip()]
    ex = []
    for r in rows:
        if r.get("mode") != "extract":
            continue
        p = Path(r["source_path"].replace("/Users/richardwoollcott", "/home/richardwoollcott"))
        if not p.exists():
            continue
        size = p.stat().st_size
        if not (EXTRACT_DOC_MIN <= size <= EXTRACT_DOC_MAX):
            continue
        ex.append((r["date"], str(p), r))
    ex.sort(key=lambda t: (t[0], t[1]))
    system_prompt = EXTRACT_PROMPT.read_text()
    for i, (date, p, r) in enumerate(pick_three(ex), 1):
        doc = Path(p).read_text(errors="replace")
        payloads.append({
            "bakeoff_id": f"EX-{i}",
            "source": {"type": "poharvest", "date": date, "source_path": p},
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"## File: {Path(p).name}\n\n{doc}"},
            ],
        })

    manifest_lines = []
    for payload in payloads:
        text = json.dumps(payload, indent=2, sort_keys=True)
        leakage_check(text, payload["bakeoff_id"])
        out = OUT_DIR / f"{payload['bakeoff_id']}.json"
        out.write_text(text)
        sha = hashlib.sha256(text.encode()).hexdigest()
        manifest_lines.append(f"{sha}  {out.name}")
        print(f"{payload['bakeoff_id']}: {payload['source']}  sha256={sha[:16]}…")

    (OUT_DIR / "MANIFEST.sha256").write_text("\n".join(manifest_lines) + "\n")
    counts = {s: len(v) for s, v in by_shape.items()}
    print(f"\nsurvivor pools: {counts}, extract pool: {len(ex)}")
    print(f"{len(payloads)} inputs + MANIFEST.sha256 written to {OUT_DIR}")


if __name__ == "__main__":
    sys.exit(main())
