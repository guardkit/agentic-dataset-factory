"""Harvest transform — real historical bundles + post-hoc labels (PLAN §2).

Walks committed run artifacts, collects the real serialized CoachEvidenceBundle for each
task's final/approving turn, and assembles rows whose label is the *post-hoc* outcome the
curator supplies (from retros/reviews) — not a model guess. Ugly-green harvesting is
deliberate: approved-but-blemished bundles are the false-block ceiling's lever (GOAL.md
criterion 6).

On-disk reality (verified 2026-07-08): the serialized bundle is ``coach_evidence_turn_N.json``
(``CoachEvidenceBundle.to_dict()``), NOT ``coach_turn_N.json`` — the latter is the Coach's
*decision* record. See the dated note in ``OUTPUT-CONTRACT.md`` §2.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from qav.contracts import (
    GROUND_TRUTH_SOURCES,
    PINNED_BUNDLE_SCHEMA_SHA,
    RowValidationError,
    build_row,
    validate_bundle,
)

BUNDLE_GLOB = "coach_evidence_turn_*.json"


@dataclass
class BundleArtifact:
    """One serialized evidence bundle found on disk."""

    repo: str
    task: str
    turn: int
    path: Path
    bundle: dict[str, Any]


def _turn_of(path: Path) -> int:
    stem = path.stem  # coach_evidence_turn_N
    try:
        return int(stem.rsplit("_", 1)[1])
    except (IndexError, ValueError):
        return 0


def discover_bundles(
    corpus_roots: dict[str, Path], *, final_turn_only: bool = True
) -> list[BundleArtifact]:
    """Find CoachEvidenceBundle serializations under each repo's ``.guardkit`` tree.

    ``corpus_roots`` maps repo-name -> repo-root Path (read-only; venue rule). With
    ``final_turn_only`` (default) one artifact per task is returned — the highest turn,
    i.e. the approving/terminal bundle the outcome attaches to.
    """
    found: list[BundleArtifact] = []
    for repo, root in corpus_roots.items():
        for path in sorted(Path(root).rglob(BUNDLE_GLOB)):
            task = path.parent.name
            try:
                bundle = json.loads(path.read_text())
            except (json.JSONDecodeError, OSError):
                continue
            if not isinstance(bundle, dict):
                continue
            found.append(BundleArtifact(repo, task, _turn_of(path), path, bundle))

    if not final_turn_only:
        return found

    best: dict[tuple[str, str], BundleArtifact] = {}
    for art in found:
        key = (art.repo, art.task)
        if key not in best or art.turn > best[key].turn:
            best[key] = art
    return sorted(best.values(), key=lambda a: (a.repo, a.task))


# --------------------------------------------------------------------------------------
# Ugly-green detection — the deliberately-harvested approve-side blemishes (GOAL.md #6).
# --------------------------------------------------------------------------------------
def is_ugly_green(bundle: dict[str, Any]) -> bool:
    """True when an approved bundle carries advisory blemishes, demoted should_fix
    discrepancies, or an infrastructure-classified independent-test failure — the honest
    greens a rubber-stamp-in-reverse judge would wrongly reject."""
    if bundle.get("advisory_issues"):
        return True
    honesty = bundle.get("honesty") or {}
    if isinstance(honesty, dict) and (honesty.get("should_fix_count") or 0) > 0:
        return True
    cls = bundle.get("independent_test_classification") or {}
    if isinstance(cls, dict) and str(cls.get("failure_class", "")).lower() in {
        "infrastructure",
        "infra",
        "environment",
    }:
        return True
    return False


# --------------------------------------------------------------------------------------
# Post-hoc labelling — the curator supplies the outcome; we never infer the verdict.
# --------------------------------------------------------------------------------------
@dataclass
class Outcome:
    """The post-hoc truth for one harvested task (from a retro/review, curator-supplied)."""

    ground_truth_source: str  # one of GROUND_TRUTH_SOURCES
    feature: str
    run: str
    sha: str
    finding: dict[str, str] | None = None  # required for the *_caught (reject) sources

    def __post_init__(self) -> None:
        if self.ground_truth_source not in GROUND_TRUTH_SOURCES:
            raise RowValidationError(f"unknown ground_truth_source {self.ground_truth_source!r}")
        if self.ground_truth_source == "seeded":
            raise RowValidationError("harvest rows are real, not seeded")


def _verdict_for(source: str) -> str:
    return "approve" if source == "coach_correct" else "reject"


def evidence_grounded_draft_think(bundle: dict[str, Any], verdict: str) -> str:
    """A deterministic, evidence-grounded DRAFT ``<think>`` naming the bundle fields read.

    Placeholder for the teacher-model stage (GPU, generation run). It keeps harvested rows
    structurally valid and honest about which fields carry signal; the teacher rewrites it.
    """
    present = [k for k, v in bundle.items() if v not in (None, [], {}, "")]
    status = bundle.get("gathering_status")
    return (
        f"[DRAFT — teacher stage rewrites] gathering_status={status!r}; fields carrying signal: "
        f"{', '.join(sorted(present)) or 'none'}. Reading null fields against gathering_status. "
        f"Verdict: {verdict}."
    )


def build_harvest_row(
    artifact: BundleArtifact,
    outcome: Outcome,
    *,
    think: str | None = None,
    split: str = "train",
) -> dict[str, Any]:
    """Assemble one validated harvest row from a real bundle + its post-hoc outcome."""
    validate_bundle(artifact.bundle)
    verdict = _verdict_for(outcome.ground_truth_source)
    findings: list[dict[str, str]] = []
    if verdict == "reject":
        if not outcome.finding:
            raise RowValidationError(
                f"{outcome.ground_truth_source} outcome for {artifact.task} needs a finding"
            )
        findings = [outcome.finding]
    label = {
        "verdict": verdict,
        "findings": findings,
        "ground_truth_source": outcome.ground_truth_source,
    }
    dc_class = findings[0]["class"] if findings else None
    return build_row(
        bundle=artifact.bundle,
        think=think or evidence_grounded_draft_think(artifact.bundle, verdict),
        label=label,
        provenance={
            "repo": artifact.repo,
            "feature": outcome.feature,
            "task": artifact.task,
            "run": outcome.run,
            "sha": outcome.sha,
        },
        split=split,
        generation_mode="harvest",
        dc_class=dc_class,
        bundle_schema_sha=PINNED_BUNDLE_SCHEMA_SHA,
        reconstruction_fidelity=None,
        injection_recipe=None,
    )


def harvest(
    corpus_roots: dict[str, Path],
    outcomes: dict[tuple[str, str], Outcome],
    *,
    think_by_task: dict[str, str] | None = None,
) -> list[dict[str, Any]]:
    """End-to-end harvest: discover final-turn bundles, label those with a supplied outcome.

    ``outcomes`` is keyed by ``(repo, task)``. Tasks without an outcome are skipped (a row
    that cannot be traced to a committed post-hoc label does not enter the manifest —
    GOAL.md provenance rule).
    """
    think_by_task = think_by_task or {}
    rows: list[dict[str, Any]] = []
    for art in discover_bundles(corpus_roots):
        outcome = outcomes.get((art.repo, art.task))
        if outcome is None:
            continue
        rows.append(build_harvest_row(art, outcome, think=think_by_task.get(art.task)))
    return rows
