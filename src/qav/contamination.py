"""Contamination check — hold-out discipline enforced in code (PLAN §6, OUTPUT-CONTRACT §5).

A training manifest is invalid without a *passing embedded* contamination check. The check
asserts three things across the train/eval split boundary:

1. **row_id disjointness** — ``train.row_id ∩ eval.row_id = ∅`` (content-addressed, so an
   identical bundle on both sides is caught even if metadata differs).
2. **sibling-variant rule** — same source task + same recipe family never straddles the
   split; sibling-variant leakage is contamination even when row hashes differ (a
   ``R-DC03`` seeded reject on train and another ``R-DC03`` variant of the *same task* on
   eval teaches the eval answer).
3. **gold-negative source-task exclusion** — no training row is generated from any of the
   four gold-negative source tasks (SPEC "Reconstruction protocol" §4).

Any violation ⇒ ``status="fail"``. The result embeds in the manifest verbatim.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from qav.recipes import RECIPES

CHECK_METHOD = (
    "row_id set intersection + sibling-variant (repo, task, recipe_family) split-straddle + "
    "gold-negative source-task exclusion"
)


def _row_id(row: dict[str, Any]) -> str:
    return row["metadata"]["row_id"]


def _repo_task(row: dict[str, Any]) -> tuple[str, str]:
    prov = row["metadata"]["provenance"]
    return prov["repo"], prov["task"]


def _family(row: dict[str, Any]) -> str:
    """Recipe family for the sibling-variant key. Seeded rows resolve via the recipe
    registry; non-seeded rows key on their generation mode."""
    meta = row["metadata"]
    recipe = meta.get("injection_recipe")
    if recipe and recipe in RECIPES:
        return RECIPES[recipe].family
    return meta.get("generation_mode", "unknown")


@dataclass
class ContaminationResult:
    status: str  # "pass" | "fail"
    method: str
    intersection: list[str]
    sibling_violations: list[dict[str, str]]
    gold_source_violations: list[dict[str, str]]
    eval_manifest: str | None = None

    @property
    def passed(self) -> bool:
        return self.status == "pass"

    def to_dict(self) -> dict[str, Any]:
        """The OUTPUT-CONTRACT §5 ``contamination_check`` block (embeds in the manifest)."""
        return {
            "status": self.status,
            "method": self.method,
            "eval_manifest": self.eval_manifest,
            "intersection": len(self.intersection),
            "intersection_row_ids": self.intersection,
            "sibling_variant_violations": self.sibling_violations,
            "gold_negative_source_violations": self.gold_source_violations,
        }


def check_contamination(
    train_rows: list[dict[str, Any]],
    eval_rows: list[dict[str, Any]],
    *,
    eval_manifest: str | None = None,
) -> ContaminationResult:
    """Run all three checks; ``status="fail"`` on any violation."""
    train_ids = {_row_id(r): r for r in train_rows}
    eval_ids = {_row_id(r): r for r in eval_rows}
    intersection = sorted(set(train_ids) & set(eval_ids))

    # sibling-variant: (repo, task, family) present on both sides
    train_sibs = {(_repo_task(r), _family(r)) for r in train_rows}
    eval_sibs = {(_repo_task(r), _family(r)) for r in eval_rows}
    sibling_violations = [
        {"repo": rt[0], "task": rt[1], "family": fam}
        for (rt, fam) in sorted(train_sibs & eval_sibs)
    ]

    # gold-negative source-task exclusion: no train row shares (repo, task) with an eval
    # gold_negative row (regardless of family).
    gold_source_tasks = {
        _repo_task(r) for r in eval_rows if r["metadata"].get("generation_mode") == "gold_negative"
    }
    train_repo_tasks = {_repo_task(r) for r in train_rows}
    gold_source_violations = [
        {"repo": repo, "task": task}
        for (repo, task) in sorted(gold_source_tasks & train_repo_tasks)
    ]

    status = "pass" if not (intersection or sibling_violations or gold_source_violations) else "fail"
    return ContaminationResult(
        status=status,
        method=CHECK_METHOD,
        intersection=intersection,
        sibling_violations=sibling_violations,
        gold_source_violations=gold_source_violations,
        eval_manifest=eval_manifest,
    )


def load_jsonl(path: str | Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in Path(path).read_text().splitlines():
        line = line.strip()
        if line:
            rows.append(json.loads(line))
    return rows
