#!/usr/bin/env python
"""Re-screen an already-staged ``accepted.jsonl`` against the office's OWN acceptance checkers.

Purpose: when the acceptance path is TIGHTENED (the growth doctrine forbids relaxing a checker but
permits closing a known gap), rows that slipped into a prior run's ``accepted.jsonl`` under the looser
rules can now be QUARANTINED — without re-authoring anything. This is a deterministic, offline harness:
it runs ZERO model calls. It simply re-plays :func:`acceptance.accept` (plus generate.py's prose-leak
gate) over each banked row exactly as ``generate.run_generation`` did when the row was first admitted,
and reports which rows the (current) checkers would now refuse. The known target is the poison row
``rec-aec4014c84260b46`` (class ``missing-capability``), which reached ``accepted.jsonl`` through two
checker gaps (the missing-capability branch ran no draft-validation; the fabricated-integration token
scan was literal, missing ``Google Calendar``). A sibling builder is hardening ``acceptance.py`` in
parallel; the coordinator re-runs THIS tool after the merge, so this file is a FAITHFUL harness, not
the catch itself.

The re-screen decision mirrors ``generate.run_generation`` byte-for-byte:

    with tempfile.TemporaryDirectory(prefix="rec-accept-") as td:
        result = acceptance.accept(expected_class, raw, Path(td), denylist=denylist)
    still_accepted = result.ok and generate._prose_leak(raw) is None

where ``expected_class`` is the row's ``metadata.expected_class``, ``raw`` is the assistant turn
(``messages[2].content``), and ``denylist`` is ``Denylist.build(cfg.held_corpus_root)`` built from the
same ``agent-config.yaml``. Run it under office-manager's own venv (so the office checkers import) with
``OFFICE_AGENTS_ROOT`` set, e.g.:

    # from the office-manager repo root:
    DOMAIN=$HOME/Projects/appmilla_github/agentic-dataset-factory/domains/recruiter-agent
    OFFICE_AGENTS_ROOT=/tmp PYTHONPATH=$DOMAIN ./.venv/bin/python $DOMAIN/rescreen_accepted.py \
        --config $DOMAIN/agent-config.yaml --run-dir run-full            # report-only (default)
    # ... same, add --apply to quarantine in place (originals are backed up first, never deleted):
    ... $DOMAIN/rescreen_accepted.py --config $DOMAIN/agent-config.yaml --run-dir run-full --apply

Report-only (default) prints the per-row failure verdicts + a by-class summary and writes
``<run-dir>/rescreen-report.json``. ``--apply`` additionally: backs the original up to
``<run-dir>/accepted.jsonl.bak-<UTC ts>`` FIRST, rewrites ``accepted.jsonl`` to the still-accepted
rows only, and writes the refused rows to ``<run-dir>/quarantined.jsonl`` (data is never deleted).
Datasets are PRIVATE (DF-008).
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import tempfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

# allow running from anywhere: this domain dir is importable for its sibling modules (the same
# pattern run_recruiter_generation.py uses to reach generate/acceptance/denylist).
DOMAIN_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(DOMAIN_DIR))

import acceptance  # noqa: E402
from denylist import Denylist  # noqa: E402
from generate import GenConfig, _prose_leak  # noqa: E402  (reuse the exact admission gate)


def _assistant_turn(row: dict) -> str:
    """The raw drafting turn a row was trained on == the assistant message (messages[2].content)."""
    msgs = row["messages"]
    for m in msgs:
        if m.get("role") == "assistant":
            return m["content"]
    # fall back to positional (generate always writes [system, user, assistant])
    return msgs[2]["content"]


def _expected_class(row: dict) -> str:
    md = row.get("metadata", {})
    exp = md.get("expected_class")
    if exp:
        return exp
    return md.get("recipe", {}).get("expected_class", "")


def screen_row(row: dict, denylist: Denylist) -> tuple[bool, str, str]:
    """Re-play the acceptance decision for one banked row.

    Returns ``(still_accepted, reason, stage)`` where ``stage`` is ``""`` when accepted, else
    ``"acceptance"`` (a checker refusal) or ``"prose-leak"`` (a repair-narration leak). This is the
    SAME two-part gate generate.run_generation applies: the office's own checkers first, then the
    prose-leak scan on an otherwise-clean turn.
    """
    raw = _assistant_turn(row)
    expected_class = _expected_class(row)
    with tempfile.TemporaryDirectory(prefix="rec-accept-") as td:
        result = acceptance.accept(expected_class, raw, Path(td), denylist=denylist)
    if not result.ok:
        return False, result.reason, "acceptance"
    leak = _prose_leak(raw)
    if leak is not None:
        return False, f"prose-leak (message narrates a correction): {leak!r}", "prose-leak"
    return True, "", ""


def _resolve_run_dir(name_or_path: str) -> Path:
    """Resolve --run-dir like run_recruiter_generation.py: an absolute/existing path is used as-is,
    otherwise it names a dir under this domain's ``pilot-runs/``."""
    p = Path(name_or_path)
    if p.is_absolute() or p.exists():
        return p
    return DOMAIN_DIR / "pilot-runs" / name_or_path


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="Re-screen a staged accepted.jsonl against the office's own acceptance checkers "
        "(deterministic, zero model calls). Report-only by default; --apply quarantines in place."
    )
    ap.add_argument("--config", required=True, help="path to agent-config.yaml (for the denylist / held-corpus root)")
    ap.add_argument("--run-dir", required=True,
                    help="staging run dir NAME (under pilot-runs/) or a path containing accepted.jsonl")
    ap.add_argument("--apply", action="store_true",
                    help="rewrite accepted.jsonl to still-accepted rows only + write quarantined.jsonl "
                    "(the original is backed up to accepted.jsonl.bak-<UTC ts> first; data is never deleted)")
    args = ap.parse_args(argv)

    config_path = Path(args.config).resolve()
    run_dir = _resolve_run_dir(args.run_dir)
    accepted_path = run_dir / "accepted.jsonl"
    if not accepted_path.exists():
        print(f"ERROR: no accepted.jsonl in run dir {run_dir}", file=sys.stderr)
        return 2

    # Build the denylist EXACTLY as generate.run_generation does (from the same config's held root).
    cfg = GenConfig.from_yaml(config_path)
    denylist = Denylist.build(cfg.held_corpus_root)
    print(
        f"denylist: {len(denylist.phrases)} phrase(s), {len(denylist.file_hashes)} held file-hash(es), "
        f"corpus_seen={denylist.corpus_seen}"
    )
    print(f"rescreen: {accepted_path}\n")

    # Read every line, preserving the RAW bytes so a rewrite/quarantine never re-serialises (and so
    # nothing that cannot be parsed is ever lost). Each record carries its verdict.
    records: list[dict] = []
    for lineno, line in enumerate(accepted_path.read_text(encoding="utf-8").splitlines(), start=1):
        stripped = line.strip()
        if not stripped:
            continue
        try:
            row = json.loads(stripped)
        except json.JSONDecodeError as exc:
            records.append({"raw": line, "row": None, "ok": None, "reason": f"unparseable line: {exc}",
                            "stage": "parse", "lineno": lineno})
            continue
        ok, reason, stage = screen_row(row, denylist)
        records.append({"raw": line, "row": row, "ok": ok, "reason": reason, "stage": stage, "lineno": lineno})

    parsed = [r for r in records if r["row"] is not None]
    unparseable = [r for r in records if r["row"] is None]
    still_ok = [r for r in parsed if r["ok"]]
    quarantined = [r for r in parsed if not r["ok"]]

    def _cls(rec: dict) -> str:
        return rec["row"].get("metadata", {}).get("class", "?")

    def _rid(rec: dict) -> str:
        return rec["row"].get("metadata", {}).get("row_id", "?")

    def _brief(rec: dict) -> str:
        return rec["row"].get("metadata", {}).get("recipe", {}).get("brief", "")

    # ---- per-row failure verdicts -----------------------------------------------------------------
    if quarantined:
        print(f"QUARANTINE — {len(quarantined)} row(s) the current checkers now refuse:\n")
        for rec in quarantined:
            brief = _brief(rec)
            brief_short = (brief[:110] + "…") if len(brief) > 110 else brief
            print(f"  [{_rid(rec)}] class={_cls(rec)} expected={_expected_class(rec['row'])} stage={rec['stage']}")
            print(f"      reason: {rec['reason']}")
            if brief_short:
                print(f"      brief:  {brief_short}")
        print()
    else:
        print("QUARANTINE — none: every banked row still passes the current checkers.\n")
    if unparseable:
        print(f"WARNING — {len(unparseable)} unparseable line(s) preserved as-is "
              f"(lines: {[r['lineno'] for r in unparseable]}).\n")

    # ---- by-class summary table -------------------------------------------------------------------
    classes = sorted({_cls(r) for r in parsed})
    total_by = Counter(_cls(r) for r in parsed)
    ok_by = Counter(_cls(r) for r in still_ok)
    quar_by = Counter(_cls(r) for r in quarantined)

    w = max([len("class")] + [len(c) for c in classes]) if classes else len("class")
    print(f"{'class'.ljust(w)}   {'total':>6}   {'still-accepted':>14}   {'quarantined':>11}")
    print("-" * (w + 3 + 6 + 3 + 14 + 3 + 11))
    for c in classes:
        print(f"{c.ljust(w)}   {total_by[c]:>6}   {ok_by[c]:>14}   {quar_by[c]:>11}")
    print("-" * (w + 3 + 6 + 3 + 14 + 3 + 11))
    print(f"{'TOTAL'.ljust(w)}   {len(parsed):>6}   {len(still_ok):>14}   {len(quarantined):>11}")
    if unparseable:
        print(f"({len(unparseable)} unparseable line(s) not screened)")
    print()

    # ---- the JSON report --------------------------------------------------------------------------
    report = {
        "tool": "rescreen_accepted",
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "domain": "recruiter-agent",
        "visibility": "private (DF-008)",
        "config": str(config_path),
        "run_dir": str(run_dir),
        "accepted_path": str(accepted_path),
        "applied": bool(args.apply),
        "denylist": {
            "phrases": len(denylist.phrases),
            "held_file_hashes": len(denylist.file_hashes),
            "held_corpus_seen": denylist.corpus_seen,
        },
        "counts": {
            "total": len(parsed),
            "still_accepted": len(still_ok),
            "quarantined": len(quarantined),
            "unparseable": len(unparseable),
        },
        "by_class": {
            c: {"total": total_by[c], "still_accepted": ok_by[c], "quarantined": quar_by[c]}
            for c in classes
        },
        "quarantined": [
            {
                "row_id": _rid(rec),
                "class": _cls(rec),
                "expected_class": _expected_class(rec["row"]),
                "stage": rec["stage"],
                "reason": rec["reason"],
                "brief": _brief(rec),
            }
            for rec in quarantined
        ],
        "unparseable_lines": [r["lineno"] for r in unparseable],
    }

    # ---- apply: back up, rewrite accepted.jsonl, write quarantined.jsonl (never delete data) -------
    if args.apply and quarantined:
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        backup_path = run_dir / f"accepted.jsonl.bak-{ts}"
        shutil.copy2(accepted_path, backup_path)  # original preserved verbatim, FIRST

        # kept = still-accepted rows AND any unparseable line (can't be screened → preserved).
        kept_lines = [r["raw"] for r in records if r["row"] is None or r["ok"]]
        quar_lines = [r["raw"] for r in quarantined]
        accepted_path.write_text(("\n".join(kept_lines) + "\n") if kept_lines else "", encoding="utf-8")
        quarantined_path = run_dir / "quarantined.jsonl"
        quarantined_path.write_text(("\n".join(quar_lines) + "\n") if quar_lines else "", encoding="utf-8")

        report["backup_path"] = str(backup_path)
        report["quarantined_path"] = str(quarantined_path)
        print(f"APPLIED: {len(quarantined)} row(s) quarantined.")
        print(f"  backup:      {backup_path}")
        print(f"  accepted:    {accepted_path}  ({len(kept_lines)} row(s) kept)")
        print(f"  quarantined: {quarantined_path}")
    elif args.apply:
        print("APPLY requested but nothing to quarantine — accepted.jsonl left unchanged (no backup written).")

    report_path = run_dir / "rescreen-report.json"
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"\nreport: {report_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
