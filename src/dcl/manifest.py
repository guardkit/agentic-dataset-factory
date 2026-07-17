"""Manifest writer + validator for the dcl domain — the WS4-facing handover format.

Builds the train manifest with per-mode / per-recipe / per-split counts and the
**embedded** contamination-check result (row_id disjointness + hold-out denylist sweep).
A manifest without a passing embedded check is *invalid by contract* — enforced in
:func:`validate_manifest`, mirroring the QAV manifest discipline. Datasets are private
(DF-008).
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from dcl.contamination import ContaminationResult, check_contamination
from dcl.contracts import MODES, RowValidationError, SPLITS, TYPES
from dcl.recipes import RECIPES

MANIFEST_VERSION = 1
ROW_CONTRACT_POINTER = "domains/dcl-capability-language/OUTPUT-CONTRACT.md"


def _jsonl_bytes(rows: list[dict[str, Any]]) -> bytes:
    return ("\n".join(json.dumps(r, ensure_ascii=False, sort_keys=True) for r in rows) + "\n").encode()


def _counts(rows: list[dict[str, Any]]) -> dict[str, Any]:
    by_mode = {m: 0 for m in sorted(MODES)}
    by_type = {t: 0 for t in sorted(TYPES)}
    by_split = {s: 0 for s in sorted(SPLITS)}
    by_recipe = {rid: 0 for rid in sorted(RECIPES)}
    compile_verified = 0
    for r in rows:
        meta = r["metadata"]
        by_mode[meta["mode"]] += 1
        by_type[meta["type"]] += 1
        by_split[meta["split"]] += 1
        rid = meta.get("recipe_id")
        if rid in by_recipe:
            by_recipe[rid] += 1
        if meta.get("compile_verified") is True:
            compile_verified += 1
    return {
        "by_mode": by_mode,
        "by_type": by_type,
        "by_split": by_split,
        "by_recipe": by_recipe,
        "compile_verified": compile_verified,
        "total": len(rows),
    }


def build_manifest(
    train_rows: list[dict[str, Any]],
    eval_rows: list[dict[str, Any]],
    *,
    dataset_id: str,
    created: str,
    factory_sha: str,
    train_file_path: str = "output/dcl-capability-language/train.jsonl",
    eval_file_path: str = "output/dcl-capability-language/eval_dcl.jsonl",
) -> dict[str, Any]:
    """Assemble the train manifest, embedding the contamination check over train vs eval.

    ``created`` / ``factory_sha`` are passed in (no wall-clock dependency) so manifests are
    reproducible and testable — mirroring the QAV manifest builder.
    """
    contamination: ContaminationResult = check_contamination(train_rows, eval_rows)
    train_bytes = _jsonl_bytes(train_rows)
    eval_bytes = _jsonl_bytes(eval_rows)
    return {
        "manifest_version": MANIFEST_VERSION,
        "dataset_id": dataset_id,
        "domain": "dcl-capability-language",
        "created": created,
        "factory_sha": factory_sha,
        "vocab_pin": "4f9fbe56",
        "compiler_pin": "4f9fbe56",
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
            },
            {
                "path": eval_file_path,
                "rows": len(eval_rows),
                "sha256": hashlib.sha256(eval_bytes).hexdigest(),
            },
        ],
        "counts": {"train": _counts(train_rows), "eval_dcl": _counts(eval_rows)},
        "contamination_check": contamination.to_dict(),
        "visibility": "private (DF-008)",
        "consumer": "WS4 training pipeline (G3 architect/dcl fine-tune lane)",
    }


_REQUIRED_MANIFEST_KEYS = {
    "manifest_version", "dataset_id", "domain", "created", "factory_sha",
    "vocab_pin", "compiler_pin", "format", "files", "counts",
    "contamination_check", "visibility", "consumer",
}


def validate_manifest(manifest: dict[str, Any]) -> None:
    """Structural validation + the hard rule: no valid manifest without a PASSING embedded
    contamination check, and datasets stay private (DF-008)."""
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
    for split in ("train", "eval_dcl"):
        if split not in counts:
            raise RowValidationError(f"counts missing {split}")
    train_counts = counts["train"]
    train_file_rows = next(
        (f["rows"] for f in manifest["files"] if f["path"].endswith("train.jsonl")), None
    )
    if train_file_rows is not None and train_counts["total"] != train_file_rows:
        raise RowValidationError("train counts.total does not match the train file row count")
    if train_counts["compile_verified"] != train_counts["total"]:
        raise RowValidationError(
            "every row must be compile_verified — an unverified label is not admissible"
        )

    check = manifest["contamination_check"]
    if check.get("status") != "pass":
        raise RowValidationError(
            "manifest carries a non-passing (or absent) embedded contamination check — invalid "
            "by contract"
        )
    if manifest["visibility"] != "private (DF-008)":
        raise RowValidationError("dcl datasets are private (DF-008)")
