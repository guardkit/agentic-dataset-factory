"""Manifest writer + validator — the WS4 handover format (OUTPUT-CONTRACT §5).

Builds ``qav-phase1-train.manifest.json`` with per-verdict / per-DC / per-source / per-mode
counts, a two-sided balance report, and the **embedded** contamination-check result. A
manifest without a passing embedded check is *invalid by contract* — enforced in
:func:`validate_manifest`, not left to convention.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from qav.contamination import ContaminationResult, check_contamination
from qav.contracts import (
    GENERATION_MODES,
    GROUND_TRUTH_SOURCES,
    PHASE1_DC_CLASSES,
    PINNED_BUNDLE_SCHEMA_SHA,
    RowValidationError,
    extract_bundle,
    extract_label,
)
from qav.harvest import is_ugly_green

MANIFEST_VERSION = 1
BALANCE_TOLERANCE = 0.10  # approve share = 0.5 ± 0.10 (PLAN §5)
MIN_UGLY_GREEN_SHARE = 0.45  # of approves (PLAN §5 / GOAL.md #6)
ROW_CONTRACT_POINTER = "domains/qa-verifier/OUTPUT-CONTRACT.md"


def _jsonl_bytes(rows: list[dict[str, Any]]) -> bytes:
    return ("\n".join(json.dumps(r, ensure_ascii=False, sort_keys=True) for r in rows) + "\n").encode()


def _counts(rows: list[dict[str, Any]]) -> dict[str, Any]:
    by_verdict = {"approve": 0, "reject": 0}
    by_dc = {c: 0 for c in sorted(PHASE1_DC_CLASSES)}
    by_source = {s: 0 for s in sorted(GROUND_TRUTH_SOURCES)}
    by_mode = {m: 0 for m in sorted(GENERATION_MODES)}
    for r in rows:
        label = extract_label(r)
        by_verdict[label["verdict"]] += 1
        by_source[label["ground_truth_source"]] += 1
        by_mode[r["metadata"]["generation_mode"]] += 1
        dc = r["metadata"].get("dc_class")
        if dc in by_dc:
            by_dc[dc] += 1
    return {
        "by_verdict": by_verdict,
        "by_dc_class": by_dc,
        "by_ground_truth_source": by_source,
        "by_generation_mode": by_mode,
    }


def balance_report(rows: list[dict[str, Any]]) -> dict[str, Any]:
    approves = [r for r in rows if extract_label(r)["verdict"] == "approve"]
    n = len(rows)
    approve_share = (len(approves) / n) if n else 0.0
    ugly = sum(1 for r in approves if is_ugly_green(extract_bundle(r)))
    ugly_share = (ugly / len(approves)) if approves else 0.0
    return {
        "approve_share": round(approve_share, 4),
        "tolerance": BALANCE_TOLERANCE,
        "ugly_green_share_of_approves": round(ugly_share, 4),
        "plan_ref": "PLAN §5",
    }


def check_balance(report: dict[str, Any]) -> list[str]:
    """The Step-4 balance gate (PLAN §5). Returns human-readable violations (empty = ok).

    Separate from structural validation: a *pilot* manifest may be intentionally off-balance,
    so this is the bulk-generation gate, not part of ``validate_manifest``.
    """
    violations: list[str] = []
    share = report["approve_share"]
    if abs(share - 0.5) > report["tolerance"]:
        violations.append(
            f"approve_share {share:.2f} outside 0.50±{report['tolerance']:.2f}"
        )
    if report["ugly_green_share_of_approves"] < MIN_UGLY_GREEN_SHARE:
        violations.append(
            f"ugly_green share {report['ugly_green_share_of_approves']:.2f} < {MIN_UGLY_GREEN_SHARE}"
        )
    return violations


def build_manifest(
    train_rows: list[dict[str, Any]],
    eval_rows: list[dict[str, Any]],
    *,
    dataset_id: str,
    created: str,
    factory_sha: str,
    train_file_path: str = "output/qa-verifier/train.jsonl",
    eval_manifest: str = "qav-phase1-eval.manifest.json",
    bundle_schema_shas: list[str] | None = None,
) -> dict[str, Any]:
    """Assemble the train manifest, embedding the contamination-check result computed over
    ``train_rows`` vs ``eval_rows``. ``created``/``factory_sha`` are passed in (no wall-clock
    dependency) so manifests are reproducible and testable."""
    contamination: ContaminationResult = check_contamination(
        train_rows, eval_rows, eval_manifest=eval_manifest
    )
    shas = bundle_schema_shas or sorted(
        {r["metadata"]["bundle_schema_sha"] for r in train_rows} or {PINNED_BUNDLE_SCHEMA_SHA}
    )
    train_bytes = _jsonl_bytes(train_rows)
    return {
        "manifest_version": MANIFEST_VERSION,
        "dataset_id": dataset_id,
        "created": created,
        "factory_sha": factory_sha,
        "bundle_schema_shas": shas,
        "format": {
            "envelope": "sharegpt-jsonl",
            "chat_template": "gemma-4",
            "row_contract": ROW_CONTRACT_POINTER,
        },
        "files": [
            {
                "path": train_file_path,
                "rows": len(train_rows),
                "sha256": hashlib.sha256(train_bytes).hexdigest(),
            }
        ],
        "counts": _counts(train_rows),
        "balance_report": balance_report(train_rows),
        "contamination_check": contamination.to_dict(),
        "visibility": "private (DF-008)",
        "consumer": "WS4 training pipeline (WS4-S8 QAV scope doc; gate = FEAT-EVAL-QAV)",
    }


_REQUIRED_MANIFEST_KEYS = {
    "manifest_version",
    "dataset_id",
    "created",
    "factory_sha",
    "bundle_schema_shas",
    "format",
    "files",
    "counts",
    "balance_report",
    "contamination_check",
    "visibility",
    "consumer",
}


def validate_manifest(manifest: dict[str, Any]) -> None:
    """Structural validation + the hard contract rule: no valid manifest without a PASSING
    embedded contamination check (OUTPUT-CONTRACT §5)."""
    missing = _REQUIRED_MANIFEST_KEYS - set(manifest)
    if missing:
        raise RowValidationError(f"manifest missing keys {sorted(missing)}")
    if manifest["manifest_version"] != MANIFEST_VERSION:
        raise RowValidationError(f"unsupported manifest_version {manifest['manifest_version']}")
    fmt = manifest["format"]
    if set(fmt) != {"envelope", "chat_template", "row_contract"}:
        raise RowValidationError("format block malformed")
    if fmt["chat_template"] != "gemma-4":
        raise RowValidationError("chat_template must be gemma-4 (NOT gemma-4-thinking)")

    counts = manifest["counts"]
    for block in ("by_verdict", "by_dc_class", "by_ground_truth_source", "by_generation_mode"):
        if block not in counts:
            raise RowValidationError(f"counts missing {block}")
    total_rows = sum(f["rows"] for f in manifest["files"])
    if sum(counts["by_verdict"].values()) != total_rows:
        raise RowValidationError("by_verdict counts do not sum to the file row total")

    check = manifest["contamination_check"]
    if check.get("status") != "pass":
        raise RowValidationError(
            "manifest carries a non-passing (or absent) embedded contamination check — invalid "
            "by contract (OUTPUT-CONTRACT §5)"
        )
    if manifest["visibility"] != "private (DF-008)":
        raise RowValidationError("QAV datasets are private (DF-008)")
