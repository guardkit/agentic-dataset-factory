"""The 4 gold-negative rows — real escaped-seam cases (SPEC-qav-gold-negatives.md).

These are the must-catch rows of FEAT-EVAL-QAV (B12): ``split: eval_qav`` from birth,
``generation_mode: gold_negative``, verdict always ``reject``. **No training row is ever
generated from these four source tasks** (the contamination sibling-variant rule).

Reconstruction protocol (SPEC "Reconstruction protocol"):
1. **Verbatim first** — probe each source repo for the original approving-turn evidence
   bundle; if present, that file *is* the user message (``reconstruction_fidelity:
   "verbatim"``). Verbatim beats reconstruction.
2. **Else reconstruct** strictly from the retro/review evidence tables below; unwitnessed
   fields stay ``null``; no invented detail (``reconstruction_fidelity: "reconstructed"``).

On-disk survival (verified 2026-07-08): **GN-3 (10AC/TASK-QAV-005) survives VERBATIM** as
``coach_evidence_turn_2.json`` in the FEAT-10AC worktree (older schema: behavioural_oracle
present as null, pre-L2/L3 — additively compatible per OUTPUT-CONTRACT §2). GN-1/GN-2 dirs
hold only ``progress.log``; GN-4 is a fix commit with no bundle → all three reconstructed.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from qav.contracts import (
    PINNED_BUNDLE_SCHEMA_SHA,
    build_row,
    validate_bundle,
)


@dataclass(frozen=True)
class GoldNegative:
    """One gold-negative spec: verbatim-probe coordinates + reconstruction fallback + label."""

    gn_id: str
    repo: str
    feature: str
    task: str
    approving_turn: int
    provenance_run: str
    provenance_sha: str
    dc_class: str
    finding_locus: str
    ground_truth_source: str
    reconstructed_bundle: dict[str, Any]
    verbatim_schema_sha: str  # schema sha to stamp when the verbatim bytes are used
    think: str

    @property
    def label(self) -> dict[str, Any]:
        return {
            "verdict": "reject",
            "findings": [{"class": self.dc_class, "locus": self.finding_locus}],
            "ground_truth_source": self.ground_truth_source,
        }


# --------------------------------------------------------------------------------------
# GN-1 · SMP-002 — undefined BDD step approved (DC-08). operator_caught. Reconstructed.
# --------------------------------------------------------------------------------------
GN1 = GoldNegative(
    gn_id="GN-1",
    repo="study-tutor",
    feature="FEAT-SMP-002",
    task="TASK-SMP2-07",
    approving_turn=2,
    provenance_run="reconstructed",
    provenance_sha="54ab79fd",  # guardkit retro 2026-07-04-autobuild-coach-missed-undefined-bdd-step.md
    dc_class="DC-08",
    finding_locus=(
        "bdd=null on the step-def authoring task itself (no TASK-SMP2-07_junit.xml); approval "
        "leaned on Player-self-reported scenario counts — absent signal ≠ pass"
    ),
    ground_truth_source="operator_caught",
    reconstructed_bundle={
        "honesty": {"discrepancies": []},  # turn-2 corrected; no blocking discrepancies
        "gathering_status": "complete",
        "bdd": None,  # the load-bearing absence: no fresh independent BDD run for the authoring task
        "bdd_authoring_sweep": None,  # the sweep gate did not exist/fire that turn
        "tests": {"passed": True},  # green per the approving record (Player-side signal)
        "quality_gates": {"tests_passed": True},
        "independent_tests": {"passed": True, "tests_passed": 109},  # integration green — the trap
    },
    verbatim_schema_sha=PINNED_BUNDLE_SCHEMA_SHA,
    think=(
        "The task's whole job (TASK-SMP2-07) is authoring BDD step definitions, yet bdd is null "
        "and bdd_authoring_sweep is null — no independent junit for the authoring task itself. "
        "Reading null against gathering_status='complete': the oracle never ran for THIS task, so "
        "that null is absent signal, not clean signal. The 109-passing integration suite in "
        "independent_tests witnesses other code, not the new scenarios. Approving here would lean "
        "on Player-self-reported scenario counts. Absent signal is not success. Reject: DC-08."
    ),
)

# --------------------------------------------------------------------------------------
# GN-2 · SMP-003 — signature change, production call sites broken (DC-03). operator_caught.
# --------------------------------------------------------------------------------------
GN2 = GoldNegative(
    gn_id="GN-2",
    repo="study-tutor",
    feature="FEAT-SMP-003",
    task="TASK-SMP3-06",
    approving_turn=1,
    provenance_run="reconstructed",
    provenance_sha="99bf79d5",  # guardkit retro 2026-07-04-autobuild-signature-change-missed-production-callsites.md
    dc_class="DC-03",
    finding_locus=(
        "cli/main.py:serve + _build_nats_runtime — MCPAdapter(...) call sites pass retired kwargs; "
        "only injected-dependency unit test updated (validates class contract, never call sites); "
        "runtime_parity absent"
    ),
    ground_truth_source="operator_caught",
    reconstructed_bundle={
        "honesty": {"discrepancies": []},  # the Player honestly did what it claimed; claim insufficient
        "gathering_status": "complete",
        "tests": {"passed": True, "tests_passed": 1049},  # canonical green-looking bundle
        "quality_gates": {"tests_passed": True},
        "independent_tests": {"passed": True},  # green in the worktree
        "wiring": None,  # UNWIRED_PATH did not cover cross-file call-site drift
        "runtime_parity": None,  # COACHRUNPARITY01 did not exist/fire — its null is part of the weight
        "bdd": None,
    },
    verbatim_schema_sha=PINNED_BUNDLE_SCHEMA_SHA,
    think=(
        "Every gate is green — tests 1049 passed, independent_tests green, honesty clean. But "
        "nothing here witnesses production construction of MCPAdapter: the updated unit test injects "
        "dependencies directly, validating the class contract, never the cli/main.py call sites. "
        "wiring is null (UNWIRED_PATH does not cover cross-file call-site drift) and runtime_parity "
        "is null — no boot/parity witness exists. Per-task green is not feature green; an all-green "
        "bundle with no production-construction witness is exactly the DC-03 signature. Reject: DC-03."
    ),
)

# --------------------------------------------------------------------------------------
# GN-3 · 10AC — L4 guard merged without its producer (DC-03). merge_review_caught. VERBATIM.
# --------------------------------------------------------------------------------------
GN3 = GoldNegative(
    gn_id="GN-3",
    repo="guardkit",
    feature="FEAT-10AC",
    task="TASK-QAV-005",
    approving_turn=2,
    provenance_run="run-3",
    provenance_sha="888906f2",
    dc_class="DC-03",
    finding_locus=(
        "gather_evidence hardcodes behavioural_oracle=None while _apply_behavioural_oracle_guard "
        "ships — runner-without-producer; fs-01 AC soft-pedaled to match"
    ),
    ground_truth_source="merge_review_caught",
    reconstructed_bundle={
        "tests": {"passed": True},
        "quality_gates": {"tests_passed": True},
        "independent_tests": {"passed": True},  # 5/5 approved, "all tasks completed cleanly"
        "honesty": {"discrepancies": []},  # no blocking discrepancies; AC soft-pedal is the tell
        "behavioural_oracle": None,  # the very field this task was supposed to make real
        "wiring": None,  # UNWIRED_PATH existed in this feature — reconstruct as gathered-then
        "plan_audit": None,
        "gathering_status": "complete",
    },
    verbatim_schema_sha="888906f2",  # the verbatim bytes predate L2/L3/sweep fields (additive-compatible)
    think=(
        "The bundle is all green — tests, independent_tests, honesty clean. The tell is "
        "behavioural_oracle=None: TASK-QAV-005's job was to make that evidence field real, and it is "
        "null. A guard whose producer hardcodes None is a runner-without-producer — the guard ships, "
        "its tests pass, and it protects nothing. The scope was quietly narrowed (fs-01 AC "
        "soft-pedaled) so the green matches the missing producer. Adding evidence machinery whose own "
        "evidence field stays null is not a working feature. Reject: DC-03."
    ),
)

# --------------------------------------------------------------------------------------
# GN-4 · DD4F — wiring fix calls three fns with nonexistent kwargs (DC-03, recursive).
# --------------------------------------------------------------------------------------
GN4 = GoldNegative(
    gn_id="GN-4",
    repo="forge",
    feature="FEAT-DD4F",
    task="FEAT-DD4F (wiring-fix 1ad98c0)",
    approving_turn=1,
    provenance_run="n/a (fix commit)",
    provenance_sha="1ad98c0",
    dc_class="DC-03",
    finding_locus=(
        "serve-boot shim → three composition-fn calls with nonexistent kwargs, TypeError swallowed "
        "by DDR-007 soft-fail; MP-011 pin tests are permissive *args/**kwargs fakes codifying the "
        "wrong contract"
    ),
    ground_truth_source="merge_review_caught",
    reconstructed_bundle={
        "tests": {"passed": True},  # both pin-test suites passed
        "quality_gates": {"tests_passed": True},
        "independent_tests": {"passed": True},
        "honesty": {"discrepancies": []},  # clean on file claims; narrative asserts wiring works
        "stub_scan": None,  # permissive-fake pattern is the teachable core whether or not then-flagged
        "wiring": None,  # wrong-signature calls behind try/except; likely no findings then
        "runtime_parity": None,  # forge venue, no smoke command threaded
        "gathering_status": "complete",
    },
    verbatim_schema_sha=PINNED_BUNDLE_SCHEMA_SHA,
    think=(
        "Both pin-test suites are green and honesty is clean, but the pin tests use permissive "
        "*args/**kwargs fakes — they codify whatever the caller passes, so they pin nothing. The "
        "serve-boot shim calls three composition functions with kwargs that do not exist; the "
        "resulting TypeError is swallowed by a DDR-007 soft-fail. Green suites over a soft-failed "
        "TypeError is a dead feature with good manners. This is the signature-binding lesson as a "
        "judgment: a fix for the green-but-dead class that itself carries the class. Reject: DC-03."
    ),
)

GOLD_NEGATIVES: list[GoldNegative] = [GN1, GN2, GN3, GN4]


# --------------------------------------------------------------------------------------
# Verbatim probe + row assembly.
# --------------------------------------------------------------------------------------
def _probe_verbatim(root: Path, task: str, turn: int) -> Path | None:
    """Find the approving-turn CoachEvidenceBundle serialization for ``task`` under ``root``.

    The real filename is ``coach_evidence_turn_N.json`` (``coach_turn_N.json`` is the Coach
    *decision* record — see the OUTPUT-CONTRACT §2 dated note). Prefers an exact-turn match.
    """
    matches = sorted(Path(root).rglob(f"{task}/coach_evidence_turn_{turn}.json"))
    for path in matches:
        try:
            data = json.loads(path.read_text())
        except (json.JSONDecodeError, OSError):
            continue
        if isinstance(data, dict) and "gathering_status" in data:
            return path
    return None


def probe_survival(corpus_roots: dict[str, Path]) -> dict[str, dict[str, Any]]:
    """Report, per gold negative, whether its approving-turn bundle survives verbatim on disk.

    Returns ``{gn_id: {"fidelity": "verbatim"|"reconstructed", "path": str|None}}``. This is
    the "verify on-disk survival of the original coach_turn_N.json" deliverable — run it
    against the live corpus before B2/B12.
    """
    report: dict[str, dict[str, Any]] = {}
    for gn in GOLD_NEGATIVES:
        root = corpus_roots.get(gn.repo)
        path = _probe_verbatim(Path(root), gn.task, gn.approving_turn) if root else None
        report[gn.gn_id] = {
            "fidelity": "verbatim" if path else "reconstructed",
            "path": str(path) if path else None,
        }
    return report


def build_gold_negative_row(gn: GoldNegative, corpus_roots: dict[str, Path] | None = None) -> dict[str, Any]:
    """Assemble one validated gold-negative row, preferring the verbatim on-disk bundle."""
    fidelity = "reconstructed"
    bundle = gn.reconstructed_bundle
    schema_sha = PINNED_BUNDLE_SCHEMA_SHA
    if corpus_roots and gn.repo in corpus_roots:
        path = _probe_verbatim(Path(corpus_roots[gn.repo]), gn.task, gn.approving_turn)
        if path is not None:
            bundle = json.loads(path.read_text())
            fidelity = "verbatim"
            schema_sha = gn.verbatim_schema_sha
    validate_bundle(bundle)
    return build_row(
        bundle=bundle,
        think=gn.think,
        label=gn.label,
        provenance={
            "repo": gn.repo,
            "feature": gn.feature,
            "task": gn.task,
            "run": gn.provenance_run,
            "sha": gn.provenance_sha,
        },
        split="eval_qav",
        generation_mode="gold_negative",
        dc_class=gn.dc_class,
        bundle_schema_sha=schema_sha,
        reconstruction_fidelity=fidelity,
        injection_recipe=None,
    )


def build_gold_negative_rows(corpus_roots: dict[str, Path] | None = None) -> list[dict[str, Any]]:
    """All four gold-negative rows, verbatim where the bundle survives on disk."""
    return [build_gold_negative_row(gn, corpus_roots) for gn in GOLD_NEGATIVES]
