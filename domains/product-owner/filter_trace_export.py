#!/usr/bin/env python3
"""filter_trace_export.py — quality-gated PO corpus slice from the raw trace export.

Input: ``output/trace-export/raw/player_imitation.jsonl`` (rows produced by
specialist-agent's ``export_sft_corpus.py``: record_id, dataset, session_id,
iteration, prompt, completion, mask_prompt, prompt_mask_label).
``coach_critique.jsonl`` is banked untouched and out of scope (it trains a
coach, not the PO).

Pipeline (each stage counts its drops into the manifest):
  1. PLAYER ROWS ONLY — only player_imitation.jsonl is processed.
  2. SURVIVOR JOIN — join each row to its source trace
     (``specialist-agent/output/*<session_id>*.json``, READ-ONLY); keep only
     rows whose completion verdict is GOOD/ACCEPTABLE with score >= 0.6
     (per-iteration ``adjusted_score``; trace ``result.final_score`` fallback).
  3. PROBE DROP — drop rows whose prompt's user content is < 150 chars
     (robust to role-prefixed text, messages lists/dicts, JSON-encoded text).
  4. SHAPE TAG — greenfield/idea/scope/evolve (roadmap ``"mode"`` regex),
     feature-spec (Feature:+Scenario+assumption markers), feature-plan
     (.guardkit/features + tasks/backlog markers), else other.
  5. DISTINCT-BRIEF DEDUP — hash the FIRST-iteration user content per session;
     sessions sharing a brief hash keep only (highest final_score, then
     earliest session date); losers logged as duplicate_of.
  6. LEAKAGE GATE — any held-out/estate term is a discard, logged to
     discarded_leakage.jsonl.
  7. STAMPS — surviving rows gain {source, weight, harvest{...}} merged
     non-destructively alongside the existing masking fields.

Outputs (to ``output/trace-export/``): po_player_filtered.jsonl,
discarded_leakage.jsonl, MANIFEST-trace-filter.md (per-stage drop counts +
per-shape surviving counts — the table that sizes the synthetic slice).

All stage logic is in pure importable functions; only ``run_filter``/``main``
touch the filesystem. specialist-agent is never written to.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import glob as _glob
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MIN_USER_CHARS = 150
MIN_SCORE = 0.6
GOOD_VERDICTS = frozenset({"GOOD", "ACCEPTABLE"})
EXPORT_RECEIPT = "receipt-2026-08-11.json"

# Leakage gate (the lane's law): matched case-insensitively, so this base list
# covers every listed variant (FinProxy/finproxy, RoundRoute/roundroute,
# HomeStretch/homestretch, kiln-firing/'kiln firing',
# member-directory-search/'member directory search', po-held-0).
LEAKAGE_TERMS = (
    "finproxy",
    "roundroute",
    "homestretch",
    "kiln-firing",
    "kiln firing",
    "member-directory-search",
    "member directory search",
    "po-held-0",
)

ROADMAP_MODES = ("greenfield", "idea", "scope", "evolve")
_MODE_RE = re.compile(r'"mode"\s*:\s*"(greenfield|idea|scope|evolve)"')
_ROLE_LINE_RE = re.compile(r"^(system|user|assistant|tool)\s*:\s*", re.IGNORECASE)

_ADF_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_RAW = _ADF_ROOT / "output" / "trace-export" / "raw" / "player_imitation.jsonl"
DEFAULT_OUT_DIR = _ADF_ROOT / "output" / "trace-export"
DEFAULT_TRACE_DIR = _ADF_ROOT.parent / "specialist-agent" / "output"


# ---------------------------------------------------------------------------
# Stage 3 helpers — user-content extraction / probe drop
# ---------------------------------------------------------------------------

def _content_text(content) -> str:
    """Flatten a message ``content`` value (str, or list of str/text blocks)."""
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict):
                text = block.get("text") or block.get("content") or ""
                if isinstance(text, str):
                    parts.append(text)
        return "\n".join(p for p in parts if p)
    if isinstance(content, dict):
        text = content.get("text") or content.get("content") or ""
        return text if isinstance(text, str) else ""
    return str(content)


def _user_text_from_role_string(text: str) -> str:
    """Extract user-section content from role-prefixed text.

    Handles the exporter's assembled form (``user: ...`` with the content
    continuing on following lines until the next role marker). If the string
    carries no role markers at all, the whole string is the user content.
    """
    lines = text.splitlines()
    has_marker = any(_ROLE_LINE_RE.match(ln) for ln in lines)
    if not has_marker:
        return text
    user_parts: list[str] = []
    current_role = None
    buf: list[str] = []

    def flush():
        if current_role == "user" and buf:
            user_parts.append("\n".join(buf))

    for ln in lines:
        m = _ROLE_LINE_RE.match(ln)
        if m:
            flush()
            current_role = m.group(1).lower()
            buf = [ln[m.end():]]
        else:
            buf.append(ln)
    flush()
    return "\n".join(user_parts)


def extract_user_content(prompt) -> str:
    """Return the user-authored content of a prompt, robust to shape.

    Accepts: role-prefixed text (``user: ...``), a messages list, a dict
    (``{"messages": [...]}`` or a single message), or a JSON string encoding
    either of those.
    """
    if prompt is None:
        return ""
    if isinstance(prompt, list):
        parts = []
        for msg in prompt:
            if isinstance(msg, dict) and str(msg.get("role", "")).lower() == "user":
                parts.append(_content_text(msg.get("content")))
        return "\n".join(p for p in parts if p)
    if isinstance(prompt, dict):
        if isinstance(prompt.get("messages"), list):
            return extract_user_content(prompt["messages"])
        if str(prompt.get("role", "")).lower() == "user":
            return _content_text(prompt.get("content"))
        if "content" in prompt and "role" not in prompt:
            return _content_text(prompt.get("content"))
        return ""
    if isinstance(prompt, str):
        stripped = prompt.strip()
        if stripped[:1] in "[{":
            try:
                parsed = json.loads(stripped)
            except (json.JSONDecodeError, ValueError):
                parsed = None
            if isinstance(parsed, (list, dict)):
                return extract_user_content(parsed)
        return _user_text_from_role_string(prompt)
    return str(prompt)


def is_trivial_prompt(prompt, min_chars: int = MIN_USER_CHARS) -> bool:
    """Stage 3 predicate: True when the prompt's user content is a probe."""
    return len(extract_user_content(prompt).strip()) < min_chars


# ---------------------------------------------------------------------------
# Stage 4 — shape classification
# ---------------------------------------------------------------------------

def classify_shape(completion: str) -> str:
    """Classify a completion's shape.

    Roadmap modes win (the mode field is definitive), then feature-spec,
    then feature-plan, else other.
    """
    text = completion or ""
    m = _MODE_RE.search(text)
    if m:
        return m.group(1)
    if ("Feature:" in text and "Scenario" in text
            and re.search(r"assumption", text, re.IGNORECASE)):
        return "feature-spec"
    if ".guardkit/features" in text and "tasks/backlog" in text:
        return "feature-plan"
    return "other"


# ---------------------------------------------------------------------------
# Stage 2 helpers — survivor join against the source trace (READ-ONLY)
# ---------------------------------------------------------------------------

def find_trace_file(session_id: str, trace_dir: Path) -> Path | None:
    """Locate the trace whose filename carries ``session_id`` (glob match)."""
    if not session_id:
        return None
    hits = sorted(_glob.glob(str(Path(trace_dir) / f"*{session_id}*.json")))
    return Path(hits[0]) if hits else None


def _numeric(value):
    return value if isinstance(value, (int, float)) and not isinstance(value, bool) else None


def trace_iteration(trace: dict, iteration) -> dict | None:
    for it in trace.get("iterations") or []:
        if isinstance(it, dict) and it.get("iteration") == iteration:
            return it
    return None


def judge_row(trace: dict, iteration) -> tuple[bool, str]:
    """Stage 2 verdict for one row: (survives, reason-if-dropped).

    Verdict/score come from the row's own iteration record; the trace-level
    ``result`` block (final_verdict/final_score) is the fallback when the
    iteration record lacks them.
    """
    result = trace.get("result") or {}
    it = trace_iteration(trace, iteration)
    verdict = (it or {}).get("verdict") or result.get("final_verdict")
    score = None
    if it is not None:
        score = _numeric(it.get("adjusted_score"))
        if score is None:
            score = _numeric(it.get("score"))
    if score is None:
        score = _numeric(result.get("final_score"))

    if it is None and not result:
        return False, "iteration_missing"
    if not isinstance(verdict, str) or verdict.upper() not in GOOD_VERDICTS:
        return False, "verdict_not_good"
    if score is None or score < MIN_SCORE:
        return False, "score_below_threshold"
    return True, ""


def session_score(trace: dict) -> float:
    """Session-level final score: result.final_score, else the last
    iteration's adjusted_score/score, else 0.0."""
    result = trace.get("result") or {}
    score = _numeric(result.get("final_score"))
    if score is not None:
        return float(score)
    iterations = [it for it in (trace.get("iterations") or []) if isinstance(it, dict)]
    for it in reversed(iterations):
        score = _numeric(it.get("adjusted_score"))
        if score is None:
            score = _numeric(it.get("score"))
        if score is not None:
            return float(score)
    return 0.0


def session_date(trace: dict, trace_path: Path | None = None) -> str:
    """Session date: first iteration timestamp, else file mtime, else ''."""
    for it in trace.get("iterations") or []:
        if isinstance(it, dict):
            ts = it.get("timestamp")
            if isinstance(ts, str) and ts:
                return ts
    if trace_path is not None:
        try:
            mtime = os.path.getmtime(trace_path)
            return _dt.datetime.fromtimestamp(
                mtime, tz=_dt.timezone.utc).isoformat()
        except OSError:
            pass
    return ""


# ---------------------------------------------------------------------------
# Stage 5 — distinct-brief dedup
# ---------------------------------------------------------------------------

def brief_hash(text: str) -> str:
    return hashlib.sha256((text or "").strip().encode("utf-8")).hexdigest()


def build_brief_hashes(rows: list[dict]) -> dict[str, str]:
    """Per-session brief hash from the FIRST-iteration row's user content.

    Built from the full raw row set (pre-drop) so the brief is identified
    even when iteration 1 itself falls to an earlier stage.
    """
    first_rows: dict[str, dict] = {}
    for row in rows:
        sid = row.get("session_id")
        if sid is None:
            continue
        cur = first_rows.get(sid)
        if cur is None or _iter_key(row) < _iter_key(cur):
            first_rows[sid] = row
    return {
        sid: brief_hash(extract_user_content(row.get("prompt")))
        for sid, row in first_rows.items()
    }


def _iter_key(row: dict):
    it = row.get("iteration")
    return it if isinstance(it, (int, float)) and not isinstance(it, bool) else float("inf")


def dedup_sessions(
    rows: list[dict],
    brief_hashes: dict[str, str],
    session_meta: dict[str, dict],
) -> tuple[list[dict], list[dict]]:
    """Stage 5: among sessions sharing a brief hash keep one session.

    Winner = highest final_score, then earliest session date (then session_id
    for determinism). ALL iterations of the kept session survive. Returns
    (kept_rows, duplicate_log) where each log entry names ``duplicate_of``.

    ``session_meta``: {session_id: {"score": float, "date": str}}.
    """
    groups: dict[str, list[str]] = {}
    seen_order: dict[str, None] = {}
    for row in rows:
        sid = row.get("session_id")
        if sid in seen_order:
            continue
        seen_order[sid] = None
        h = brief_hashes.get(sid) or f"__no-brief__{sid}"
        groups.setdefault(h, []).append(sid)

    losers: dict[str, str] = {}
    duplicate_log: list[dict] = []
    for h, sids in groups.items():
        if len(sids) < 2:
            continue
        def keep_key(sid: str):
            meta = session_meta.get(sid, {})
            score = meta.get("score", 0.0) or 0.0
            date = meta.get("date", "") or "￿"  # missing date sorts last
            return (-score, date, sid)
        winner = min(sids, key=keep_key)
        for sid in sids:
            if sid == winner:
                continue
            losers[sid] = winner
            meta = session_meta.get(sid, {})
            duplicate_log.append({
                "session_id": sid,
                "duplicate_of": winner,
                "brief_hash": h,
                "final_score": meta.get("score"),
                "session_date": meta.get("date"),
            })

    kept = [row for row in rows if row.get("session_id") not in losers]
    return kept, duplicate_log


# ---------------------------------------------------------------------------
# Stage 6 — leakage gate
# ---------------------------------------------------------------------------

def leakage_hits(row: dict, terms=LEAKAGE_TERMS) -> list[str]:
    """Return the forbidden terms present anywhere in the row (case-insensitive)."""
    haystack = json.dumps(row, ensure_ascii=False).lower()
    return [t for t in terms if t.lower() in haystack]


# ---------------------------------------------------------------------------
# Stage 7 — stamps
# ---------------------------------------------------------------------------

def stamp_row(
    row: dict,
    *,
    shape: str,
    trace_file: str,
    filter_version: str,
    export_receipt: str = EXPORT_RECEIPT,
) -> dict:
    """Return a new row carrying harvest metadata, merged non-destructively:
    every existing field (masking fields included) is preserved untouched,
    and pre-existing values win over the stamp."""
    out = dict(row)
    out.setdefault("source", "harvest")
    out.setdefault("weight", 1.0)
    stamp = {
        "session_id": row.get("session_id"),
        "trace_file": trace_file,
        "shape": shape,
        "iteration": row.get("iteration"),
        "export_receipt": export_receipt,
        "filter_version": filter_version,
    }
    existing = row.get("harvest")
    if isinstance(existing, dict):
        stamp.update(existing)  # existing values win
    out["harvest"] = stamp
    return out


def git_short_sha(repo_root: Path) -> str:
    try:
        proc = subprocess.run(
            ["git", "-C", str(repo_root), "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True, timeout=10, check=False,
        )
        sha = proc.stdout.strip()
        return sha if proc.returncode == 0 and sha else "unknown"
    except OSError:
        return "unknown"


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------

def run_filter(
    raw_path: Path = DEFAULT_RAW,
    trace_dir: Path = DEFAULT_TRACE_DIR,
    out_dir: Path = DEFAULT_OUT_DIR,
    filter_version: str | None = None,
    export_receipt: str = EXPORT_RECEIPT,
) -> dict:
    """Run the full filter. Reads traces READ-ONLY; writes only into out_dir."""
    raw_path, trace_dir, out_dir = Path(raw_path), Path(trace_dir), Path(out_dir)
    if filter_version is None:
        filter_version = git_short_sha(_ADF_ROOT)

    # Stage 1 — player rows only.
    rows: list[dict] = []
    with open(raw_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    total_player = len(rows)
    rows = [r for r in rows if r.get("dataset", "player_imitation") == "player_imitation"]
    stage1_dropped = total_player - len(rows)

    coach_path = raw_path.parent / "coach_critique.jsonl"
    coach_rows_banked = 0
    if coach_path.exists():
        with open(coach_path, encoding="utf-8") as f:
            coach_rows_banked = sum(1 for ln in f if ln.strip())

    # Brief hashes come from the FULL raw player set (pre-drop) so stage 5
    # still sees the true iteration-1 brief.
    brief_hashes = build_brief_hashes(rows)

    # Stage 2 — survivor join.
    join_reasons: dict[str, int] = {}
    survivors: list[dict] = []
    trace_files: dict[str, str] = {}
    session_meta: dict[str, dict] = {}
    trace_cache: dict[str, dict | None] = {}
    for row in rows:
        sid = row.get("session_id", "")
        if sid not in trace_cache:
            path = find_trace_file(sid, trace_dir)
            trace = None
            if path is not None:
                try:
                    with open(path, encoding="utf-8") as f:
                        trace = json.load(f)
                except (OSError, json.JSONDecodeError):
                    trace = None
            trace_cache[sid] = trace
            if trace is not None:
                trace_files[sid] = path.name
                session_meta[sid] = {
                    "score": session_score(trace),
                    "date": session_date(trace, path),
                }
        trace = trace_cache[sid]
        if trace is None:
            join_reasons["trace_missing"] = join_reasons.get("trace_missing", 0) + 1
            continue
        ok, reason = judge_row(trace, row.get("iteration"))
        if not ok:
            join_reasons[reason] = join_reasons.get(reason, 0) + 1
            continue
        survivors.append(row)
    stage2_in, stage2_out = len(rows), len(survivors)

    # Stage 3 — probe drop.
    rows_after_probe = [r for r in survivors if not is_trivial_prompt(r.get("prompt"))]
    stage3_dropped = stage2_out - len(rows_after_probe)

    # Stage 4 — shape tag (no drops).
    shapes = {id(r): classify_shape(r.get("completion", "")) for r in rows_after_probe}

    # Stage 5 — distinct-brief dedup.
    rows_after_dedup, duplicate_log = dedup_sessions(
        rows_after_probe, brief_hashes, session_meta)
    stage5_dropped = len(rows_after_probe) - len(rows_after_dedup)

    # Stage 6 — leakage gate.
    kept: list[dict] = []
    leakage_discards: list[dict] = []
    for row in rows_after_dedup:
        hits = leakage_hits(row)
        if hits:
            leakage_discards.append({
                "reason": "leakage",
                "matched_terms": hits,
                "record_id": row.get("record_id"),
                "session_id": row.get("session_id"),
                "iteration": row.get("iteration"),
                "row": row,
            })
        else:
            kept.append(row)

    # Stage 7 — stamps.
    stamped = [
        stamp_row(
            row,
            shape=shapes[id(row)],
            trace_file=trace_files.get(row.get("session_id", ""), ""),
            filter_version=filter_version,
            export_receipt=export_receipt,
        )
        for row in kept
    ]

    shape_counts: dict[str, int] = {}
    for row in stamped:
        shape = row["harvest"]["shape"]
        shape_counts[shape] = shape_counts.get(shape, 0) + 1

    # ---- outputs ----
    out_dir.mkdir(parents=True, exist_ok=True)
    filtered_path = out_dir / "po_player_filtered.jsonl"
    with open(filtered_path, "w", encoding="utf-8") as f:
        for row in stamped:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    leakage_path = out_dir / "discarded_leakage.jsonl"
    with open(leakage_path, "w", encoding="utf-8") as f:
        for entry in leakage_discards:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    stats = {
        "generated_at": _dt.datetime.now(_dt.timezone.utc).isoformat(),
        "filter_version": filter_version,
        "export_receipt": export_receipt,
        "raw_path": str(raw_path),
        "trace_dir": str(trace_dir),
        "coach_rows_banked_out_of_scope": coach_rows_banked,
        "stage1": {"in": total_player, "dropped_non_player": stage1_dropped,
                   "out": len(rows)},
        "stage2": {"in": stage2_in, "dropped": stage2_in - stage2_out,
                   "out": stage2_out, "reasons": join_reasons},
        "stage3": {"in": stage2_out, "dropped": stage3_dropped,
                   "out": len(rows_after_probe)},
        "stage4": {"in": len(rows_after_probe), "dropped": 0,
                   "out": len(rows_after_probe)},
        "stage5": {"in": len(rows_after_probe), "dropped": stage5_dropped,
                   "out": len(rows_after_dedup),
                   "duplicate_sessions": duplicate_log},
        "stage6": {"in": len(rows_after_dedup), "dropped": len(leakage_discards),
                   "out": len(kept)},
        "stage7": {"in": len(kept), "dropped": 0, "out": len(stamped)},
        "surviving_rows": len(stamped),
        "shape_counts": shape_counts,
    }
    manifest_path = out_dir / "MANIFEST-trace-filter.md"
    manifest_path.write_text(render_manifest(stats), encoding="utf-8")
    stats["outputs"] = {
        "filtered": str(filtered_path),
        "leakage": str(leakage_path),
        "manifest": str(manifest_path),
    }
    return stats


def render_manifest(stats: dict) -> str:
    """Render MANIFEST-trace-filter.md from the pipeline stats."""
    s = stats
    lines = [
        "# MANIFEST — trace-export filter (PO player slice)",
        "",
        f"- Generated: {s['generated_at']}",
        f"- Filter version (adf git sha): `{s['filter_version']}`",
        f"- Export receipt: `{s['export_receipt']}`",
        f"- Raw input: `{s['raw_path']}`",
        f"- Trace dir (read-only): `{s['trace_dir']}`",
        f"- coach_critique.jsonl: {s['coach_rows_banked_out_of_scope']} rows"
        " banked untouched, out of scope (trains a coach, not the PO)",
        "",
        "## Per-stage drop counts",
        "",
        "| Stage | Description | In | Dropped | Out |",
        "|---|---|---:|---:|---:|",
    ]
    descriptions = {
        "stage1": "Player rows only (non-player rows in file dropped)",
        "stage2": "Survivor join (verdict GOOD/ACCEPTABLE, score >= 0.6)",
        "stage3": f"Probe drop (user content < {MIN_USER_CHARS} chars)",
        "stage4": "Shape tag (classification only)",
        "stage5": "Distinct-brief dedup (one session per brief hash)",
        "stage6": "Leakage gate (held-out/estate terms)",
        "stage7": "Stamps (harvest metadata merged non-destructively)",
    }
    for key in ("stage1", "stage2", "stage3", "stage4", "stage5", "stage6", "stage7"):
        st = s[key]
        dropped = st.get("dropped", st.get("dropped_non_player", 0))
        lines.append(
            f"| {key[5:]} | {descriptions[key]} | {st['in']} | {dropped} | {st['out']} |")
    lines += ["", f"**Surviving rows: {s['surviving_rows']}**", ""]

    reasons = s["stage2"].get("reasons") or {}
    if reasons:
        lines += ["## Stage 2 drop reasons", ""]
        for reason, n in sorted(reasons.items()):
            lines.append(f"- {reason}: {n}")
        lines.append("")

    dups = s["stage5"].get("duplicate_sessions") or []
    if dups:
        lines += ["## Stage 5 duplicate sessions (losers)", "",
                  "| Session | duplicate_of | final_score | session_date |",
                  "|---|---|---:|---|"]
        for d in dups:
            lines.append(
                f"| {d['session_id']} | {d['duplicate_of']} | "
                f"{d.get('final_score')} | {d.get('session_date')} |")
        lines.append("")

    lines += [
        "## Per-shape surviving counts (sizes the synthetic slice)",
        "",
        "| Shape | Surviving rows |",
        "|---|---:|",
    ]
    order = list(ROADMAP_MODES) + ["feature-spec", "feature-plan", "other"]
    counts = s["shape_counts"]
    for shape in order:
        if shape in counts:
            lines.append(f"| {shape} | {counts[shape]} |")
    for shape in sorted(counts):
        if shape not in order:
            lines.append(f"| {shape} | {counts[shape]} |")
    lines.append(f"| **total** | **{s['surviving_rows']}** |")
    lines.append("")
    return "\n".join(lines)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Filter the raw trace export into a quality-gated PO corpus slice.")
    parser.add_argument("--raw", type=Path, default=DEFAULT_RAW,
                        help="player_imitation.jsonl path")
    parser.add_argument("--trace-dir", type=Path, default=DEFAULT_TRACE_DIR,
                        help="specialist-agent output dir (read-only)")
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR,
                        help="output directory")
    parser.add_argument("--filter-version", default=None,
                        help="override the adf git short sha stamp")
    args = parser.parse_args(argv)
    stats = run_filter(args.raw, args.trace_dir, args.out_dir,
                       filter_version=args.filter_version)
    summary = {k: v for k, v in stats.items() if k not in ("stage5",)}
    summary["stage5"] = {k: v for k, v in stats["stage5"].items()
                         if k != "duplicate_sessions"}
    summary["stage5"]["duplicate_sessions"] = len(
        stats["stage5"]["duplicate_sessions"])
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
