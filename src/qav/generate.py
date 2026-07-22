"""Offline generation driver for the qa-verifier (QAV) seeded-defect dataset (PLAN §2).

Runnable WITHOUT a live seat by construction (the DCL/README-code-half pattern): the
mechanism is here; a real run wires an OpenAI-compatible teacher + coach endpoint and the
guardkit ``GatherEvidenceRegenerator`` from ``agent-config.yaml``, while tests drive it
against local stub clients. **Zero real model calls and zero live-seat/GPU work happen in
this module by construction** — the teacher, coach, and bundle regenerator are all injected
Protocols; the only code that touches a real network/guardkit substrate is marked
``# pragma: no cover - real network`` / ``- generation run`` and is never reached by tests.

Modes (config.mode):

- ``seeded_defect`` (the code change): three sub-pipelines through the SAME machinery —
  * ``seeded_code`` (primary): for each known-green source task (discovered from the config
    corpus roots → scratch worktree checkout at the task's approved sha) × weighted recipe,
    ``qav.injector.inject`` plants the labelled defect (label fixed by construction, never a
    model call) → the mutated tree is materialised into a scratch worktree →
    ``regenerator.regenerate(worktree)`` produces the REAL ``CoachEvidenceBundle`` → the
    teacher authors ONLY the ``<think>`` rationale against the fixed label → the Coach gate
    (schema-valid + rationale-consistent-with-label + cue-audit clean) admits or rejects.
  * seeded-control greens: the identical machinery with ``inject_control`` (a no-op patch) →
    a regenerated true-green bundle labelled ``approve`` (controls for any "was regenerated"
    cue, PLAN §2 seeded-control greens).
  * ``seeded_bundle`` (augmentation, capped at ``seeded_bundle_cap`` of the seeded rows):
    caller-supplied real bundles mutated to a documented defect signature, gated hard by the
    cue-leakage audit; inert when no mutation candidates are supplied.
- ``harvest``: ``qav.harvest`` over curator-supplied outcomes; inert-clean when none supplied.
- ``both``: seeded_defect + harvest.

Gold negatives are ALWAYS emitted to ``eval_qav`` via ``qav.gold_negatives`` (the must-catch
holdout); their four source tasks are excluded from seeded/harvest generation by construction.

**Split-at-creation + the straddle law (PLAN §6).** Every row's split (``train`` |
``eval_qav``) is assigned at creation by a seeded RNG keyed on ``(repo, task, recipe_family)``
— the SAME triple ``contamination.py`` uses for its sibling-variant check. Because all sibling
variants of one source task share that key, they land in the SAME split by construction, so the
``contamination.py`` straddle law is satisfied structurally rather than hoped for. The gold
negatives are ``eval_qav`` from birth and their source tasks never enter a training row.

Finalize: ``manifest.build_manifest`` embeds the contamination check, which MUST pass
(``validate_manifest``) or the run fails loud. Output: fresh-start ``OutputWriter`` with ``*.bak``
backups to ``output/qa-verifier/`` + the handover ``manifest.json``.
"""

from __future__ import annotations

import copy
import hashlib
import json
import logging
import re
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

import yaml

from qav.contracts import (
    PINNED_BUNDLE_SCHEMA_SHA,
    SYSTEM_PROMPT,
    RowValidationError,
    build_row,
    validate_bundle,
)
from qav.gold_negatives import GOLD_NEGATIVES, build_gold_negative_rows
from qav.harvest import BUNDLE_GLOB, BundleArtifact, Outcome, build_harvest_row
from qav.injector import (
    BundleRegenerator,
    InjectionResult,
    inject,
    inject_control,
)
from qav.manifest import build_manifest, check_balance, validate_manifest
from qav.recipes import RECIPES, AnchorNotFound

logger = logging.getLogger(__name__)

# The four gold-negative source tasks — excluded from every training-side pipeline by
# construction (the contamination gold-source rule, belt-and-braces over the check).
GOLD_SOURCE_TASKS: frozenset[tuple[str, str]] = frozenset(
    (gn.repo, gn.task) for gn in GOLD_NEGATIVES
)

_THINK_RE = re.compile(r"<think>(.*?)</think>", re.S)


# --------------------------------------------------------------------------------------
# Pluggable clients — injected. The real teacher/coach hit an OpenAI-compatible endpoint;
# the real regenerator drives guardkit. Nothing here constructs a real client automatically.
# --------------------------------------------------------------------------------------
class ModelClient(Protocol):
    def complete(self, system: str, user: str) -> str:  # pragma: no cover - protocol
        ...


@dataclass
class CoachVerdict:
    """The row-quality gate verdict (rationale-consistency, NOT content judgment — PLAN §7)."""

    decision: str  # "accept" | "revise"
    reasons: list[str] = field(default_factory=list)

    @property
    def accepted(self) -> bool:
        return self.decision == "accept"


class CoachClient(Protocol):
    def assess(  # pragma: no cover - protocol
        self, bundle: dict[str, Any], think: str, label: dict[str, Any]
    ) -> CoachVerdict:
        ...


@dataclass
class OpenAICompatibleClient:
    """Real teacher client against an OpenAI-compatible ``/chat/completions`` endpoint.

    NEVER instantiated or called by tests (the ZERO-real-model-calls law). Stdlib ``urllib``
    only (sibling convention) so a run wires it without new deps. Bounded retry/backoff on
    transient statuses mirrors ``src/dcl/generate.py`` (the overnight-batch 429 lesson).
    """

    endpoint: str
    model: str
    temperature: float = 0.4
    max_tokens: int = 4096
    timeout_seconds: float = 900.0
    retry_attempts: int = 6
    retry_base_seconds: float = 10.0
    _RETRYABLE = (429, 500, 502, 503, 504)

    def complete(self, system: str, user: str) -> str:  # pragma: no cover - real network
        import time as _time
        import urllib.error
        import urllib.request

        payload = json.dumps({
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
        }).encode()
        req = urllib.request.Request(
            self.endpoint.rstrip("/") + "/chat/completions",
            data=payload,
            headers={"Content-Type": "application/json"},
        )
        last_exc: Exception | None = None
        for attempt in range(self.retry_attempts):
            try:
                with urllib.request.urlopen(req, timeout=self.timeout_seconds) as resp:
                    body = json.loads(resp.read())
                return body["choices"][0]["message"]["content"]
            except urllib.error.HTTPError as exc:
                if exc.code not in self._RETRYABLE:
                    raise
                last_exc = exc
                retry_after = exc.headers.get("Retry-After") if exc.headers else None
            except (urllib.error.URLError, TimeoutError) as exc:
                last_exc = exc
                retry_after = None
            if attempt < self.retry_attempts - 1:
                delay = float(retry_after) if retry_after else self.retry_base_seconds * (2 ** attempt)
                _time.sleep(min(delay, 600.0))
        raise RuntimeError(
            f"teacher call failed after {self.retry_attempts} attempts (transient errors): {last_exc!r}"
        ) from last_exc


# --------------------------------------------------------------------------------------
# Source tasks + bundle mutations — the seeded pipelines' inputs.
# --------------------------------------------------------------------------------------
@dataclass
class SourceTask:
    """One known-green source task: an in-memory file map + provenance coordinates.

    ``files`` is the clean file map of the task's worktree at the approved ``sha`` (in a real
    run the provider reads the checked-out worktree into memory; in tests it is a tiny local
    fixture). The engine injects into a COPY and materialises the result into a scratch
    worktree before regeneration, so the same source task feeds many recipes independently.
    """

    repo: str
    feature: str
    task: str
    sha: str
    files: dict[str, str]
    run: str = "seeded"
    # The corpus-HEAD directory holding this task's original autobuild run record. Materialized
    # into each per-recipe scratch worktree at .guardkit/autobuild/<task>/ before regeneration so
    # guardkit gather_evidence reads the authentic record instead of short-circuiting to an
    # evidence-empty ``missing_results`` bundle (the round-3 poison). ``None`` in tiny test
    # fixtures (the stub regenerator ignores the worktree contents).
    record_dir: str | None = None


@dataclass
class BundleMutation:
    """A ``seeded_bundle`` candidate: a real bundle already mutated to a defect signature.

    The field mutation is applied by the curator/provider (PLAN §2: "mutate a real serialized
    bundle's fields to a documented defect signature"); the engine caps the share, runs the
    cue-leakage audit as a hard gate, authors the rationale, and Coach-gates the row. The
    label is fixed (reject + finding, ``ground_truth_source: seeded``)."""

    repo: str
    feature: str
    task: str
    sha: str
    run: str
    bundle: dict[str, Any]
    finding: dict[str, str]  # {"class": ..., "locus": ...}
    recipe_id: str

    @property
    def label(self) -> dict[str, Any]:
        return {"verdict": "reject", "findings": [self.finding], "ground_truth_source": "seeded"}


class SourceTaskProvider(Protocol):
    def discover(self) -> list[SourceTask]:  # pragma: no cover - protocol
        ...


# --------------------------------------------------------------------------------------
# Config — loaded from agent-config.yaml (or constructed directly).
# --------------------------------------------------------------------------------------
@dataclass
class GenerateConfig:
    mode: str = "seeded_defect"  # seeded_defect | harvest | both
    limit: int | None = None
    holdout_fraction: float = 0.15
    seeded_bundle_cap: float = 0.25
    recipes: dict[str, float] = field(default_factory=lambda: {r: 1.0 for r in RECIPES})
    output_dir: str = "output/qa-verifier"
    manifest_path: str = "domains/qa-verifier/manifests/qav-phase1-train.manifest.json"
    scratch_dir: str = "output/qa-verifier/_scratch"
    seed: str = "qav-phase1"
    corpus_roots: dict[str, str] = field(default_factory=dict)
    bundle_schema_sha: str = PINNED_BUNDLE_SCHEMA_SHA
    # Per-repo interpreter/venv resolution for the regenerator's pytest substrate
    # (the SIBTESTENV01 lesson: config, not hardcode). Consumed at worktree/regeneration
    # setup time in a real run; recorded here so the driver/runbook can thread it.
    interpreters: dict[str, str] = field(default_factory=dict)
    dataset_id: str = "qav-phase1-train-v1"
    # Path to the ratified harvest-outcomes yaml (census §2 labeling policy). ``None`` => the
    # harvest path is inert-clean (no committed outcome file => no harvested rows). The file
    # carries ONLY committed-record labels; the loader schema-validates it (loud on malformed)
    # and consumes only ``disposition: consumable`` entries (queued/flagged are skipped + counted).
    harvest_outcomes_path: str | None = None
    # Factory-side record-store roots (additive; recovered HEAD-missing run records). Each is laid
    # out as ``<root>/<repo>/<task>/`` and searched by discover.locate_run_record_dir AFTER the
    # corpus ``.guardkit`` globs. Empty => pre-recovery behaviour (corpus globs only). Never a
    # corpus write — the store is a factory-owned copy of authentic records (S-B, 2026-07-21).
    record_store_roots: list[str] = field(default_factory=list)
    # --- L2 deep-regeneration bridge config (render-collapse layers 1+2, 2026-07-21) -----------
    # LAYER 1 (profile-gate): the guardkit task_type whose quality-gate PROFILE's REQUIRED gates
    # match what the materialized task_work_results record actually carries — tests + plan_audit,
    # but NOT arch_review (arch runs in a separate guardkit phase and is never captured in
    # task_work_results, so the default ``feature`` profile requiring it aborts regeneration at
    # ``partial_gate_abort`` before any worktree test runs). Threaded into the bridge's ``task``
    # dict so gather_evidence resolves that profile. This is the SANCTIONED profile-selection path,
    # NOT ``skip_arch_review`` (render-collapse proved skip_arch_review alone net-harmful). ``None``
    # => the bridge default (feature) — i.e. pre-fix behaviour. No guardkit code change.
    regen_task_type: str | None = None
    # LAYER 2 (per-repo stack pin): ``repo -> pytest test command`` (the interpreters-map pattern).
    # Pins the worktree test command so the oracle never MISDETECTS node/npm on a Python repo (the
    # render-collapse ``returncode 127`` wall). Each command MUST start with ``pytest`` so guardkit
    # runs it under the repo's pinned venv interpreter (coach_validator subprocess path). Its scope
    # must include the mutated files' tests (layer 4) so a planted defect surfaces. Absent repo =>
    # the bridge falls back to guardkit's own detection (pre-fix behaviour).
    test_commands: dict[str, str] = field(default_factory=dict)
    # LAYER 4 (per-RECIPE test-scope override): an OPTIONAL ``repo -> {recipe_id -> pytest command}``
    # map that OVERRIDES the per-repo ``test_commands`` default for the NAMED recipes only. The
    # per-repo command applies to ALL of a repo's recipes, but different recipes mutate different
    # files; a recipe whose mutated-file tests live OUTSIDE the per-repo scope regenerates a bundle
    # byte-identical to the no-op control and is honestly refused (``evidence_invariant_injection``).
    # A per-recipe override pins that recipe's OWN mutated-file test scope so its planted defect
    # surfaces as a real failing/absent/skip-masked test. Every command obeys the SAME laws as
    # ``test_commands``: it MUST start with ``pytest``, every token whitespace-free (guardkit's
    # ``test_cmd.split()`` shell=False tokenisation law), and it MUST stay control-green on the no-op
    # (each override recipe is compared against a control regenerated under the SAME command — see
    # ``_run_seeded_code`` scope-matched controls — so a trivial scope-difference can never masquerade
    # as the defect). Absent recipe => the per-repo default. Empty => pre-override behaviour.
    test_commands_per_recipe: dict[str, dict[str, str]] = field(default_factory=dict)
    # Independent-test subprocess timeout (seconds) threaded to CoachValidator.test_timeout.
    regen_test_timeout: int = 1800

    @classmethod
    def from_yaml(cls, path: str | Path) -> "GenerateConfig":
        data = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
        gen = data.get("generation", {}) or {}
        out = data.get("output", {}) or {}
        corpus = data.get("corpus", {}) or {}
        regen = data.get("regeneration", {}) or {}
        # The ``corpus:`` block mixes repo-name -> path entries with a few scalar/list config keys
        # (bundle_schema_sha, record_store_roots). Only the string-valued path entries are corpus
        # roots; excluding the non-repo keys keeps the discovery/harvest walks from iterating a
        # stringified list as a bogus root (harmless before, but now the feature-tracker walk reads
        # each root's .guardkit — a real filesystem read).
        _NON_ROOT_CORPUS_KEYS = {"bundle_schema_sha", "record_store_roots"}
        corpus_roots = {
            k: v for k, v in corpus.items()
            if k not in _NON_ROOT_CORPUS_KEYS and isinstance(v, str)
        }
        return cls(
            mode=gen.get("mode", "seeded_defect"),
            limit=gen.get("limit"),
            holdout_fraction=gen.get("holdout_fraction", 0.15),
            seeded_bundle_cap=gen.get("seeded_bundle_cap", 0.25),
            recipes=gen.get("recipes") or {r: 1.0 for r in RECIPES},
            output_dir=out.get("dir", "output/qa-verifier"),
            manifest_path=out.get(
                "manifest", "domains/qa-verifier/manifests/qav-phase1-train.manifest.json"
            ),
            scratch_dir=gen.get("scratch_dir", "output/qa-verifier/_scratch"),
            seed=gen.get("seed", "qav-phase1"),
            corpus_roots={str(k): str(v) for k, v in corpus_roots.items()},
            bundle_schema_sha=corpus.get("bundle_schema_sha", PINNED_BUNDLE_SCHEMA_SHA),
            interpreters={str(k): str(v) for k, v in (data.get("interpreters", {}) or {}).items()},
            dataset_id=gen.get("dataset_id", "qav-phase1-train-v1"),
            harvest_outcomes_path=gen.get("harvest_outcomes"),
            record_store_roots=[
                str(p) for p in (corpus.get("record_store_roots") or [])
            ],
            regen_task_type=regen.get("task_type"),
            test_commands={
                str(k): str(v) for k, v in (regen.get("test_commands", {}) or {}).items()
            },
            test_commands_per_recipe={
                str(repo): {
                    str(rid): str(cmd) for rid, cmd in (per or {}).items()
                }
                for repo, per in (regen.get("test_commands_per_recipe", {}) or {}).items()
            },
            regen_test_timeout=int(regen.get("test_timeout", 1800)),
        )


# --------------------------------------------------------------------------------------
# Split assignment — seeded at creation, keyed to satisfy the straddle law by construction.
# --------------------------------------------------------------------------------------
def _family_of(recipe_id: str | None, generation_mode: str) -> str:
    """The sibling-variant family key — IDENTICAL to ``contamination._family`` so the split
    grouping and the contamination check agree by construction."""
    if recipe_id and recipe_id in RECIPES:
        return RECIPES[recipe_id].family
    return generation_mode


def assign_split(
    repo: str, task: str, family: str, *, holdout_fraction: float, seed: str
) -> str:
    """Deterministically assign ``train`` | ``eval_qav`` for a ``(repo, task, family)`` group.

    Stable across processes and IDENTICAL for every sibling variant of one source task (they
    share the group key), so no ``(repo, task, family)`` group ever straddles the split."""
    if not 0.0 <= holdout_fraction <= 1.0:
        raise ValueError("holdout_fraction must be in [0, 1]")
    key = f"{seed}:{repo}:{task}:{family}"
    bucket = int(hashlib.sha256(key.encode()).hexdigest()[:8], 16) % 10_000
    return "eval_qav" if bucket < round(holdout_fraction * 10_000) else "train"


# --------------------------------------------------------------------------------------
# Cue-leakage audit — the per-row deterministic gate (PLAN §2 / GOAL.md).
# --------------------------------------------------------------------------------------
_CUE_SENTINELS = (
    "__seeded__",
    "seeded_defect",
    "__injected__",
    "injected_by_recipe",
    "sentinel",
    "xxxcue",
)


# --------------------------------------------------------------------------------------
# Evidence-empty pre-gate — THE LOUDNESS LAW (round-3 poison-path closure).
#
# guardkit gather_evidence returns ``gathering_status="partial_exception"`` (with a
# ``gathering_error`` like ``missing_results: …``) when the gathering pipeline could not run:
# invalid task type, missing task_work_results record, missing profile, or an unexpected helper
# exception. Those bundles are near-all-null — no tests/coverage/gates/wiring signal — yet the
# round-3 spike proved teacher + coach BOTH wave such a bundle through into train.jsonl as an
# approve row. That is the exact false-green class QAV exists to catch: a verdict model must never
# learn "missing evidence -> approve". This gate rejects them DETERMINISTICALLY before any teacher
# call (no wasted GPU) and before any row is built (never train).
#
# ``"complete"`` is guardkit's healthy value (coach_validator.py:3221/3742). The evidence-BEARING
# early stops ``partial_gate_abort`` (gates failed) and ``partial_honesty_abort`` (honesty
# discrepancies) are NOT rejected here: they carry populated quality_gates / honesty evidence and
# are legitimate reject-side signal (a verdict model SHOULD learn from failed gates). Only the
# ``partial_exception`` crash class and any bundle carrying a ``missing_results`` error are
# evidence-empty. (OPEN POINT: the tension with a literal "reject anything != complete" reading is
# recorded in the RUNBOOK — over-rejecting would discard genuine reject rows.)
# --------------------------------------------------------------------------------------
HEALTHY_GATHERING_STATUS = "complete"
EVIDENCE_BEARING_ABORTS: frozenset[str] = frozenset(
    {"partial_gate_abort", "partial_honesty_abort"}
)


def evidence_empty_reason(bundle: dict[str, Any]) -> str | None:
    """Return a loud reason string when ``bundle`` is an evidence-empty regeneration that must be
    rejected before the teacher stage, or ``None`` when it carries usable evidence.

    Deterministic. Triggers on guardkit's ``partial_exception`` crash class (or any absent/unknown
    status) and on any bundle carrying a ``missing_results`` gathering_error — the round-3 shape."""
    status = bundle.get("gathering_status")
    error = str(bundle.get("gathering_error") or "")
    if "missing_results" in error:
        return (
            f"gathering_status={status!r} with missing_results — the task-work record was not "
            f"materialized into the worktree; gathering_error={error!r}"
        )
    if status == HEALTHY_GATHERING_STATUS or status in EVIDENCE_BEARING_ABORTS:
        return None
    detail = f" (gathering_error={error!r})" if error else ""
    return (
        f"gathering_status={status!r} is not {HEALTHY_GATHERING_STATUS!r} and carries no "
        f"evidence-bearing abort — the regeneration gathered no usable evidence{detail}"
    )


# --------------------------------------------------------------------------------------
# THE EVIDENCE-DIVERGENCE GUARD — the render-collapse poison-path closure (2026-07-21).
#
# Proven (receipts/render-collapse-rootcause-2026-07-21.md): on the current corpus the
# regeneration replay is SOURCE-BLIND — guardkit gather_evidence short-circuits at
# ``partial_gate_abort`` and replays the static task-work record, so a mutated worktree's
# bundle comes out BYTE-IDENTICAL to its task's no-op control bundle. Write-order then let a
# reject recipe claim the shared row_id first and bank a GREEN bundle wearing a reject label
# (the growth-cycle-1 corpus carried 4 such rows) — the exact false-BLOCK poison QAV exists to
# prevent. The guard makes the class STRUCTURALLY IMPOSSIBLE: the control bundle is regenerated
# FIRST per task and content-hashed; any seeded REJECT candidate whose regenerated bundle
# hashes equal to that control baseline is REFUSED to rejected.jsonl with reason
# ``evidence_invariant_injection`` — the planted defect did not surface in the evidence, so no
# reject label may ride it. Controls themselves are unaffected (their approve label describes
# the real record). Deterministic; runs BEFORE any teacher call (no wasted GPU).
# --------------------------------------------------------------------------------------
EVIDENCE_INVARIANT_REASON = "evidence_invariant_injection"


# --------------------------------------------------------------------------------------
# NON-DETERMINISM SCRUB — L2 layer 3 (render-collapse deep-regeneration, 2026-07-21).
#
# Once layers 1+2 (profile-gate + per-repo stack pin) let gather_evidence actually RUN the
# worktree's pytest, the regenerated bundle carries genuine test evidence — but that evidence
# is threaded with WALL-CLOCK JITTER and per-run RANDOM PATHS that differ between two runs of
# the SAME mutated tree. Left un-scrubbed they poison the row surface two ways:
#   (1) they split a re-run of one mutated tree into two "unique" row_ids (non-reproducible
#       corpus), and
#   (2) they let a source-blind reject bundle drift a hair off its control by timing alone,
#       DEFEATING the evidence-divergence guard (render-collapse §"skip_arch_review alone is
#       net-harmful": "defeat dedup by timing noise, minting 'unique' rows that carry identical
#       evidence with divergent labels").
# So the scrub runs at the ENGINE layer, on EVERY regenerated bundle, BEFORE both the guard's
# content-hash AND the row_id user-message rendering (contracts.py is FROZEN — the scrub cannot
# live there; it lives here, where the engine hands the regenerated bundle to build_row).
#
# THE DOCUMENTED FIELD LIST (drop = key removed recursively anywhere in the bundle):
#   - ``duration_seconds`` — wall-clock float on IndependentTestResult / RuntimeParityResult /
#     any nested timing dict (guardkit coach_validator.py:1518, 4914…). The field the receipt
#     named (`0.0666` vs `0.0562`).
# THE DOCUMENTED TEXT NORMALIZATIONS (value rewritten in place, signal preserved):
#   Applied to every string value so failing-test NAMES/messages survive while the jitter that
#   rides alongside them (pytest's timing summary, per-run --basetemp/tmp dirs, session hashes,
#   memory addresses) is replaced by a stable token. The concrete pattern list is pinned in
#   ``_NONDET_TEXT_SUBS`` and was fixed empirically against the two-run spike diff (receipt).
# --------------------------------------------------------------------------------------
# The scrub itself (the documented key-drop list + text normalizations + optional worktree-path
# normalization) lives in ``qav.scrub`` — a single source of truth, hermetically unit-tested. It is
# re-exported here because this engine module is where it is APPLIED (the two regeneration sites in
# ``_run_seeded_code`` / ``_seeded_row_from_injection``, right after ``regenerator.regenerate``).
from qav.scrub import (  # noqa: E402
    NONDET_TEXT_SUBS,
    NONDETERMINISTIC_BUNDLE_KEYS,
    scrub_nondeterministic_bundle,
)


def bundle_content_hash(bundle: dict[str, Any]) -> str:
    """Canonical content hash of a serialized bundle — the byte-identity surface the
    render-collapse receipt proved (sorted-key JSON, the same canonicalization the row_id
    user-message rendering uses). Two bundles hash equal iff their evidence is identical.

    NOTE: callers hash the SCRUBBED bundle (``scrub_nondeterministic_bundle``) so wall-clock
    jitter cannot split a re-run or slip a source-blind reject past the divergence guard."""
    return hashlib.sha256(
        json.dumps(bundle, sort_keys=True, ensure_ascii=False).encode("utf-8")
    ).hexdigest()


def cue_audit(bundle: dict[str, Any]) -> list[str]:
    """Deterministic surface-cue scan (reusing ``coach-agent/audit_cue_leakage.py``
    conventions) — the ``seeded_bundle`` gate and a cheap check on every seeded row.

    Catches the artefact families GOAL.md names: sentinel/injection markers, a PLAN §3 recipe
    id leaking into the evidence text, and truncated-shape ellipsis sentinels. Corpus-level
    field-distribution comparison vs real bundles (the coach script's other convention) runs
    at the bulk-audit step over the written jsonl, not per row — recorded as an open point."""
    issues: list[str] = []
    blob = json.dumps(bundle, ensure_ascii=False)
    low = blob.lower()
    for s in _CUE_SENTINELS:
        if s in low:
            issues.append(f"cue sentinel {s!r} present in bundle")
    for rid in RECIPES:
        if rid.lower() in low:
            issues.append(f"recipe id {rid!r} leaked into bundle evidence")
    if '"..."' in blob or "…" in blob:
        issues.append("truncated-shape ellipsis sentinel present in bundle")
    return issues


# --------------------------------------------------------------------------------------
# House output writer — routes by split, mirrors the DCL OutputWriter conventions.
# --------------------------------------------------------------------------------------
class OutputWriter:
    """Fresh-start writer with the house backup convention (prior files -> ``*.bak``)."""

    _SPLIT_FILES = {"train": "train.jsonl", "eval_qav": "eval_qav.jsonl"}

    def __init__(self, output_dir: str | Path) -> None:
        self.dir = Path(output_dir)
        self.counts = {"train": 0, "eval_qav": 0, "rejected": 0}
        self._fh: dict[str, Any] = {}
        self._seen_row_ids: set[str] = set()
        self.duplicates_skipped = 0

    @staticmethod
    def _backup(path: Path) -> None:
        if path.exists():
            path.replace(path.with_suffix(path.suffix + ".bak"))

    def __enter__(self) -> "OutputWriter":
        self.dir.mkdir(parents=True, exist_ok=True)
        for name in ("train.jsonl", "eval_qav.jsonl", "rejected.jsonl", "manifest.json"):
            self._backup(self.dir / name)
        self._fh["train"] = open(self.dir / "train.jsonl", "w", encoding="utf-8")
        self._fh["eval_qav"] = open(self.dir / "eval_qav.jsonl", "w", encoding="utf-8")
        self._fh["rejected"] = open(self.dir / "rejected.jsonl", "w", encoding="utf-8")
        self.train_rows: list[dict[str, Any]] = []
        self.eval_rows: list[dict[str, Any]] = []
        return self

    def write_row(self, row: dict[str, Any]) -> bool:
        """Write a row; return False if it was a byte-identical duplicate (same content-addressed
        row_id) and skipped."""
        rid = row["metadata"]["row_id"]
        if rid in self._seen_row_ids:
            self.duplicates_skipped += 1
            return False
        self._seen_row_ids.add(rid)
        split = row["metadata"]["split"]
        self._fh[split].write(json.dumps(row, ensure_ascii=False) + "\n")
        self._fh[split].flush()
        self.counts[split] += 1
        (self.train_rows if split == "train" else self.eval_rows).append(row)
        return True

    def write_rejected(self, record: dict[str, Any]) -> None:
        self._fh["rejected"].write(json.dumps(record, ensure_ascii=False) + "\n")
        self._fh["rejected"].flush()
        self.counts["rejected"] += 1

    def __exit__(self, *exc: Any) -> None:
        for fh in self._fh.values():
            fh.close()


# --------------------------------------------------------------------------------------
# Worktree materialisation — write a mutated file map to a fresh scratch worktree.
# --------------------------------------------------------------------------------------
def _materialize_worktree(
    scratch_dir: Path,
    repo: str,
    task: str,
    recipe_id: str,
    files: dict[str, str],
    *,
    record_dir: str | None = None,
) -> Path:
    """Write ``files`` (the mutated tree) into a fresh per-recipe scratch worktree and return
    its path. The regenerator runs guardkit ``gather_evidence`` over this tree.

    When ``record_dir`` is set (a real run — discovery resolved the task's HEAD run record), the
    authentic run-record artifacts are ALSO materialized into ``.guardkit/autobuild/<task>/`` — the
    exact path guardkit gather_evidence reads (``TaskArtifactPaths.TASK_WORK_RESULTS``). Without
    this, ``.guardkit`` (gitignored in the corpus) is absent from the checkout and gather_evidence
    short-circuits to the evidence-empty ``missing_results`` bundle the round-3 spike proved poison.
    Reconstruction of the authentic record, never fabrication (see ``qav.discover`` module note)."""
    worktree = scratch_dir / repo / task / recipe_id
    if worktree.exists():
        shutil.rmtree(worktree)
    worktree.mkdir(parents=True)
    for rel, text in files.items():
        dest = worktree / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(text, encoding="utf-8")
    if record_dir is not None:
        from qav.discover import materialize_run_record

        materialize_run_record(Path(record_dir), worktree, task)  # pragma: no cover - generation run
    return worktree


# --------------------------------------------------------------------------------------
# Teacher rationale — authors ONLY the <think> against the label fixed by construction.
# --------------------------------------------------------------------------------------
def _build_think_prompt(bundle: dict[str, Any], label: dict[str, Any]) -> str:
    verdict = label["verdict"]
    findings_txt = (
        "; ".join(f"{f['class']} @ {f['locus']}" for f in label["findings"])
        if label["findings"]
        else "(none — this is an honest green)"
    )
    return (
        "## Evidence bundle\n```json\n"
        f"{json.dumps(bundle, indent=2, sort_keys=True, ensure_ascii=False)}\n```\n\n"
        f"## Fixed verdict (do NOT change it)\nverdict: {verdict}\nfindings: {findings_txt}\n\n"
        "## Task\nAuthor ONLY the <think>…</think> reasoning that leads to this exact verdict. "
        "Reason over the ACTUAL bundle fields by name (read null fields against gathering_status); "
        "do not summarise the verdict, do not restate it as the whole rationale, and never invent "
        "evidence not in the bundle. Emit a single <think> block."
    )


def _author_think(teacher: ModelClient, bundle: dict[str, Any], label: dict[str, Any]) -> str:
    """Return the teacher's ``<think>`` text, or ``""`` if the teacher refused (empty output).

    A refusal is a RESULT, not a retry (honesty law 3): the caller rejects the row loudly."""
    raw = teacher.complete(SYSTEM_PROMPT, _build_think_prompt(bundle, label))
    m = _THINK_RE.search(raw or "")
    think = (m.group(1) if m else (raw or "")).strip()
    return think


# --------------------------------------------------------------------------------------
# Census-safe bundle discovery — the harvest path's ONLY discovery seam.
#
# The bare ``qav.harvest.discover_bundles`` walks a repo's ``.guardkit`` tree with rglob and
# keys the final-turn winner by ``(repo, task = immediate-parent-dir-name)``. Two documented
# footguns (census §3, ``receipts/harvest-s1-census-2026-07-21.md``) make it WRONG for a real
# harvest run:
#   (1) JARVIS WORKTREE PATHS. Agent worktrees nested under ``.claude/worktrees/`` carry
#       duplicate bundle copies; on an rglob tie-break a ``.claude/worktrees/…`` path can WIN
#       and be recorded as the final-turn winner (the census's 82 came out clean ONLY because
#       it skipped them — the MacBook one-paste uses the same ``! -path '*/.claude/worktrees/*'``
#       filter). ``.guardkit/worktrees/`` is a LEGITIMATE record location and is NOT skipped.
#   (2) SAME-TASK-ID MERGE ACROSS FEATURES. Keying on the bare task-dir name silently merges
#       same-task bundles from different features/evidence-variants into one winner. We keep the
#       deterministic highest-turn (then lexical-path) tie-break, matching the census.
# The harvest path calls THIS function, never the bare one.
# --------------------------------------------------------------------------------------
HARVEST_SKIP_PATH_SUBSTRING = ".claude/worktrees"


def discover_final_turn_bundles(
    corpus_roots: dict[str, Path], *, skip_substring: str = HARVEST_SKIP_PATH_SUBSTRING
) -> dict[tuple[str, str], BundleArtifact]:
    """The census discovery method: one final-turn ``BundleArtifact`` per ``(repo, task)``,
    SKIPPING ``.claude/worktrees`` jarvis-duplicate paths. Deterministic: highest turn wins, then
    lexical path (so a re-run never flips winners). Mirrors the S1 census source of record
    (``run_logs/qav-harvest-census-2026-07-21.jsonl``)."""
    best: dict[tuple[str, str], BundleArtifact] = {}
    for repo, root in corpus_roots.items():
        for path in sorted(Path(root).rglob(BUNDLE_GLOB)):
            if skip_substring in path.as_posix():
                continue  # jarvis worktree duplicate — footgun (1)
            try:
                bundle = json.loads(path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                continue
            if not isinstance(bundle, dict):
                continue
            try:
                turn = int(path.stem.rsplit("_", 1)[1])
            except (IndexError, ValueError):
                turn = 0
            task = path.parent.name
            key = (repo, task)
            art = BundleArtifact(repo, task, turn, path, bundle)
            prev = best.get(key)
            if prev is None or turn > prev.turn or (turn == prev.turn and str(path) < str(prev.path)):
                best[key] = art
    return best


# --------------------------------------------------------------------------------------
# seeded_bundle input — REAL final-turn bundles mutated to a documented defect signature.
#
# PLAN §2 (the augmentation tier, capped ≤25% of seeded rows): "Mutate a real serialized
# bundle's fields to a documented defect signature without re-running anything." Unlike the
# seeded_code path — whose DC-03/DC-05 recipes regenerate a tree that RENDERS IDENTICAL to an
# already-banked bundle (render-collapse: 26 legs → 0 unique rows, seeded-sweep §4 bottleneck
# #2) — a bundle mutation perturbs a BUNDLE-VISIBLE field directly, so ``row_id`` (a sha256 of
# the serialized bundle, contracts.py:build_user_message) necessarily changes and the row never
# collapses. That bundle-field diversity is exactly what render-collapse starves.
#
# Each mutation is DETERMINISTIC and encodes ONE DC class BY CONSTRUCTION — the resulting label
# (reject + {class, locus}, ground_truth_source=seeded) is fixed by the mutation, NEVER derived
# by a model. Each recipe only fires where the field carries a real signal to sabotage (an
# already-null field is skipped — no signal to sever, and no perturbation), so a mutation always
# genuinely changes the serialized bundle. The mutation catalog is cue-clean by construction; the
# per-row cue-leakage audit (cue_audit) is still the hard gate downstream (_gate_and_build) — a
# real base bundle carrying an incidental token is turned away there, loudly, never dropped here.
#
# Recipe id namespace ``R-BUNDLE-*`` is DISJOINT from the frozen code recipes (RECIPES), so
# _family_of / contamination._family both fall through to generation_mode="seeded_bundle" — every
# mutation of one source task shares the split key (repo, task, "seeded_bundle") and never
# straddles (PLAN §6 straddle law, by construction).
# --------------------------------------------------------------------------------------
def _mutate_dc03_oracle(bundle: dict[str, Any]) -> tuple[dict[str, Any], dict[str, str]] | None:
    """DC-03 (composition seam, producer severed): null a populated ``behavioural_oracle`` —
    the PLAN §3 R-DC03-producer expected signature ("behavioural_oracle field absent or vacuous",
    the GN-3/QAV-005 gold shape). No-op-skip when already null (no producer output to sever)."""
    if bundle.get("behavioural_oracle") is None:
        return None
    mutated = copy.deepcopy(bundle)
    mutated["behavioural_oracle"] = None
    return mutated, {
        "class": "DC-03",
        "locus": "behavioural_oracle severed to null (producer output vacuous)",
    }


def _mutate_dc08_bdd(bundle: dict[str, Any]) -> tuple[dict[str, Any], dict[str, str]] | None:
    """DC-08 (BDD hole, independent oracle suppressed): null a populated ``bdd`` — the PLAN §3
    R-ABSENT-junit expected signature ("bdd null + narrative claims", the SMP-002 turn-2 shape).
    No-op-skip when already null (no independent BDD signal to drop)."""
    if bundle.get("bdd") is None:
        return None
    mutated = copy.deepcopy(bundle)
    mutated["bdd"] = None
    return mutated, {
        "class": "DC-08",
        "locus": "bdd evidence dropped to null (independent BDD oracle suppressed)",
    }


# A documented honesty discrepancy modeled on the REAL on-disk shape (the guardkit
# claim_audit_unmodified record: keys claim_type / player_claim / actual_value). Cue-clean —
# no sentinel token, no RECIPES id, no truncation ellipsis (the cue_audit families).
_PLANTED_HONESTY_DISCREPANCY = {
    "claim_type": "claim_audit_unmodified",
    "player_claim": "Player report claims the feature wiring was implemented and verified this run",
    "actual_value": (
        "git status shows the producer file was not modified in this run; the implementation "
        "narrative over-claims disk state relative to what was actually written"
    ),
}


def _mutate_dc14_honesty(bundle: dict[str, Any]) -> tuple[dict[str, Any], dict[str, str]] | None:
    """DC-14 (narrative false-green): plant one honesty discrepancy into a CONFIDENT-clean bundle
    (honesty present, no existing discrepancies) — the PLAN §3 R-DC14-narrative signature
    ("honesty.discrepancies non-empty; narrative confident", the FMDR-004 shape). No-op-skip when
    honesty already carries a discrepancy (not a confident green to falsify)."""
    honesty = bundle.get("honesty")
    if not isinstance(honesty, dict) or honesty.get("discrepancies"):
        return None
    mutated = copy.deepcopy(bundle)
    new_honesty = dict(mutated["honesty"])
    new_honesty["discrepancies"] = [dict(_PLANTED_HONESTY_DISCREPANCY)]
    new_honesty["verified"] = False
    mutated["honesty"] = new_honesty
    return mutated, {
        "class": "DC-14",
        "locus": "honesty.discrepancies planted (narrative over-claims vs disk)",
    }


# Ordered catalog — deterministic iteration so a re-run yields the same candidate sequence.
_BUNDLE_MUTATION_RECIPES: tuple[tuple[str, Any], ...] = (
    ("R-BUNDLE-DC03-oracle", _mutate_dc03_oracle),
    ("R-BUNDLE-DC08-bdd", _mutate_dc08_bdd),
    ("R-BUNDLE-DC14-honesty", _mutate_dc14_honesty),
)


def build_bundle_mutations(
    bundles: dict[tuple[str, str], dict[str, Any]],
    provenance: dict[tuple[str, str], dict[str, str]],
) -> list[BundleMutation]:
    """Assemble ``seeded_bundle`` mutation candidates from REAL discovered final-turn bundles.

    ``bundles`` maps ``(repo, task)`` -> the real serialized bundle (from
    ``discover_final_turn_bundles``); ``provenance`` maps the SAME key -> the record-resolved
    ``{feature, sha, run}`` (from the known-green source-task discovery, never a guessed sha). A
    ``(repo, task)`` with no provenance entry is EXCLUDED (the approved-sha honesty law — no
    fabricated coordinates), as is any evidence-empty bundle (a poison regeneration is not a
    documented signature and would be turned away by the evidence-empty pre-gate regardless).

    For each surviving bundle, every catalog recipe whose target field carries a real signal
    yields one ``BundleMutation`` (label fixed by the mutation). The ≤cap share and the cue-audit
    are enforced downstream in ``_run_seeded_bundle`` / ``_gate_and_build``."""
    out: list[BundleMutation] = []
    for key in sorted(bundles):
        repo, task = key
        prov = provenance.get(key)
        if prov is None:
            logger.info(
                "SEEDED_BUNDLE skip %s/%s — no record-resolved provenance (never a guessed sha)",
                repo, task,
            )
            continue
        base = bundles[key]
        if evidence_empty_reason(base) is not None:
            logger.info(
                "SEEDED_BUNDLE skip %s/%s — evidence-empty base bundle (not a documented signature)",
                repo, task,
            )
            continue
        for recipe_id, mutate in _BUNDLE_MUTATION_RECIPES:
            result = mutate(base)
            if result is None:
                continue
            mutated, finding = result
            out.append(
                BundleMutation(
                    repo=repo,
                    feature=str(prov["feature"]),
                    task=task,
                    sha=str(prov["sha"]),
                    run=str(prov.get("run", "seeded_bundle")),
                    bundle=mutated,
                    finding=finding,
                    recipe_id=recipe_id,
                )
            )
    return out


def _committed_bundle_provenance(
    config: GenerateConfig, source_tasks: list[SourceTask]
) -> dict[tuple[str, str], dict[str, str]]:
    """The record-resolved provenance POOL for ``seeded_bundle`` base bundles — assembled from
    EVERY committed-provenance source the estate really encodes, unioned:

      * the merge_summary-resolved known-green **source tasks** (``qav.discover`` already applied
        the approved-sha honesty law — each carries a resolved approved sha + feature), and
      * the **ratified consumable harvest outcomes** (the census §2 labels: each consumable entry
        carries a committed ``{feature, sha, run}`` keyed ``(repo, task)`` — the same real merge/FF
        provenance the outcomes yaml already encodes). ``queued``/``flagged`` entries are NOT
        ratified provenance and are dropped by ``load_harvest_outcomes`` (never guessed).

    THE ROOT-CAUSE FIX (growth-cycle-1 G3q plateau): the prior seam sourced provenance ONLY from
    ``source_tasks`` — but 11 of the 13 discovered source tasks (the FEAT-C332 / FEAT-70A4
    reconstructed-record tasks) have NO discovered final-turn bundle at all, and the 2 that do
    (BDDW-001/002) carry all-null target fields, so EVERY candidate skipped ``no record-resolved
    provenance`` → 0 rows. The ratified consumables ARE final-turn bundles on disk with committed
    coordinates — the real, honest provenance well.

    A ``(repo, task)`` present in NEITHER source has no committed provenance and is absent from the
    pool (its discovered bundle stays skipped downstream — never a guessed sha). Gold-negative
    source tasks are excluded belt-and-braces. On a key present in both, the ratified consumable
    committed sha wins (the census is the authoritative label record); a divergent sha is logged
    loudly rather than silently reconciled."""
    provenance: dict[tuple[str, str], dict[str, str]] = {}
    for src in source_tasks:
        key = (src.repo, src.task)
        if key in GOLD_SOURCE_TASKS:
            continue
        provenance[key] = {"feature": src.feature, "sha": src.sha, "run": "seeded_bundle"}
    loaded = load_harvest_outcomes(config.harvest_outcomes_path)
    for key, oc in loaded.outcomes.items():
        if key in GOLD_SOURCE_TASKS:
            continue
        prior = provenance.get(key)
        if prior is not None and prior["sha"] != oc.sha:
            logger.warning(
                "SEEDED_BUNDLE provenance sha divergence %s/%s — source-task sha %s vs ratified "
                "consumable sha %s; taking the ratified census sha (committed-label record)",
                key[0], key[1], prior["sha"], oc.sha,
            )
        provenance[key] = {"feature": oc.feature, "sha": oc.sha, "run": oc.run}
    return provenance


def _discover_bundle_mutations(
    config: GenerateConfig,
    source_tasks: list[SourceTask],
    summary: GenerationSummary | None = None,
) -> list[BundleMutation]:
    """Generation-run seam: wire the ``seeded_bundle`` input from the census-safe final-turn
    bundle discovery + the UNION committed-provenance pool (merge_summary source tasks ∪ ratified
    consumable outcomes — see ``_committed_bundle_provenance``). A discovered bundle with no
    committed provenance stays skipped and, when a ``summary`` is threaded, is COUNTED into
    ``seeded_bundle_no_provenance`` (the honesty law made a number, not just a log line)."""
    corpus_roots = {k: Path(v) for k, v in config.corpus_roots.items()}
    artifacts = discover_final_turn_bundles(corpus_roots)
    bundles = {key: art.bundle for key, art in artifacts.items()}
    provenance = _committed_bundle_provenance(config, source_tasks)
    if summary is not None:
        summary.seeded_bundle_no_provenance = sum(1 for key in bundles if key not in provenance)
    return build_bundle_mutations(bundles, provenance)


# --------------------------------------------------------------------------------------
# Ratified-outcomes ingestion — the harvest labels (census §2, Rich 2026-07-21).
#
# THE POLICY IS LAW: a bundle is labeled ONLY from a committed record. Undecidable/ambiguous
# outcomes are ``queued``/``flagged`` in the yaml — skipped here with a logged count, NEVER
# guessed. The verdict is never model-derived; the yaml carries it, and the teacher only authors
# the <think> against it (mirroring the seeded label-fixed law).
# --------------------------------------------------------------------------------------
_CONSUMABLE = "consumable"
_OUTCOME_DISPOSITIONS = frozenset({_CONSUMABLE, "queued", "flagged"})
_OUTCOME_REQUIRED_KEYS = frozenset(
    {"repo", "feature", "task", "run", "sha", "ground_truth_source", "disposition"}
)
_APPROVE_SOURCE = "coach_correct"


@dataclass
class LoadedOutcomes:
    """Result of ingesting the harvest-outcomes yaml: the consumable ``Outcome`` objects keyed
    ``(repo, task)`` + the count of non-consumable (queued/flagged) entries skipped."""

    outcomes: dict[tuple[str, str], Outcome]
    skipped: int
    skipped_keys: list[tuple[str, str]] = field(default_factory=list)


class OutcomesSchemaError(ValueError):
    """The harvest-outcomes yaml is malformed — loud, never silently degraded."""


def load_harvest_outcomes(path: str | Path | None) -> LoadedOutcomes:
    """Load + schema-validate the ratified harvest-outcomes yaml, returning ONLY the consumable
    labels as ``Outcome`` objects (queued/flagged skipped + counted). ``None``/missing path =>
    empty (inert-clean). Loud (``OutcomesSchemaError``) on any structural malformation — a bad
    label file must fail the run, never quietly drop rows."""
    if path is None:
        return LoadedOutcomes({}, 0)
    p = Path(path)
    if not p.exists():
        raise OutcomesSchemaError(f"harvest-outcomes path does not exist: {p}")
    try:
        data = yaml.safe_load(p.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise OutcomesSchemaError(f"harvest-outcomes yaml is not parseable: {exc}") from exc
    if not isinstance(data, dict):
        raise OutcomesSchemaError("harvest-outcomes yaml must be a mapping with a top-level 'outcomes'")
    if data.get("version") != 1:
        raise OutcomesSchemaError(f"unsupported harvest-outcomes version {data.get('version')!r} (want 1)")
    entries = data.get("outcomes")
    if not isinstance(entries, list):
        raise OutcomesSchemaError("harvest-outcomes 'outcomes' must be a list")

    outcomes: dict[tuple[str, str], Outcome] = {}
    skipped = 0
    skipped_keys: list[tuple[str, str]] = []
    for i, entry in enumerate(entries):
        if not isinstance(entry, dict):
            raise OutcomesSchemaError(f"outcomes[{i}] must be a mapping, got {type(entry).__name__}")
        missing = _OUTCOME_REQUIRED_KEYS - set(entry)
        if missing:
            raise OutcomesSchemaError(f"outcomes[{i}] missing keys {sorted(missing)}")
        disposition = entry["disposition"]
        if disposition not in _OUTCOME_DISPOSITIONS:
            raise OutcomesSchemaError(
                f"outcomes[{i}] disposition {disposition!r} not in {sorted(_OUTCOME_DISPOSITIONS)} "
                "(undecidable => queued/flagged, NEVER guessed)"
            )
        repo, task = str(entry["repo"]), str(entry["task"])
        if disposition != _CONSUMABLE:
            skipped += 1
            skipped_keys.append((repo, task))
            logger.info(
                "HARVEST OUTCOME SKIP %s/%s — disposition=%s (%s)",
                repo, task, disposition, entry.get("note", "held for curation"),
            )
            continue
        source = entry["ground_truth_source"]
        finding = entry.get("finding")
        # Reject-side labels require a finding carrying a DC class (R1); an approve does not.
        if source != _APPROVE_SOURCE and not isinstance(finding, dict):
            raise OutcomesSchemaError(
                f"outcomes[{i}] ({repo}/{task}) is a reject source {source!r} but carries no finding"
            )
        if (repo, task) in outcomes:
            raise OutcomesSchemaError(f"duplicate consumable outcome for {(repo, task)}")
        try:
            outcomes[(repo, task)] = Outcome(
                ground_truth_source=source,
                feature=str(entry["feature"]),
                run=str(entry["run"]),
                sha=str(entry["sha"]),
                finding={str(k): str(v) for k, v in finding.items()} if isinstance(finding, dict) else None,
            )
        except RowValidationError as exc:  # bad ground_truth_source / seeded => loud
            raise OutcomesSchemaError(f"outcomes[{i}] ({repo}/{task}) invalid: {exc}") from exc
    return LoadedOutcomes(outcomes, skipped, skipped_keys)


# --------------------------------------------------------------------------------------
# Summary.
# --------------------------------------------------------------------------------------
@dataclass
class GenerationSummary:
    seeded_code_written: int = 0
    seeded_control_written: int = 0
    seeded_bundle_written: int = 0
    seeded_bundle_capped: int = 0  # candidates dropped by the ≤cap share rule
    # Discovered final-turn bundles skipped because their (repo, task) has NO committed
    # provenance in the union pool (no merge_summary source task AND no ratified consumable
    # outcome) — the approved-sha honesty law, counted not just logged (never a guessed sha).
    seeded_bundle_no_provenance: int = 0
    harvest_written: int = 0
    harvest_outcomes_skipped: int = 0  # queued/flagged yaml entries (undecidable, never guessed)
    harvest_bundle_not_found: int = 0  # a consumable label with no skip-filtered bundle on disk
    gold_negatives_written: int = 0
    teacher_refused: int = 0
    coach_rejected: int = 0
    cue_rejected: int = 0
    evidence_empty_rejected: int = 0  # regenerated bundle had no usable evidence (loudness law)
    # THE EVIDENCE-DIVERGENCE GUARD: seeded reject candidates whose regenerated bundle was
    # byte-identical to their task's no-op control bundle — the defect never surfaced in the
    # evidence, so the reject label was refused (render-collapse poison-path closure).
    evidence_invariant_rejected: int = 0
    schema_rejected: int = 0
    anchor_skipped: int = 0  # recipe anchor absent from a source task (loud, not silent)
    gold_source_skipped: int = 0  # source tasks excluded as gold-negative sources
    deduped: int = 0
    train: int = 0
    eval_qav: int = 0
    # Manifest finalize verdict (honesty §2). validate_manifest gates ONLY the embedded
    # contamination check — NOT balance; balance (approve_share 0.5±0.10 + ugly-green floor) is
    # the separate advisory ``check_balance`` gate the finalize path records but never crashes on.
    # So a low-N approve-heavy set (round 4's approve-2/reject-0) DOES finalize; the imbalance is
    # recorded here + logged loudly, rows are banked, and the manifest is written honestly.
    manifest_finalized: bool = False
    manifest_balance_ok: bool = True
    manifest_balance_violations: list[str] = field(default_factory=list)
    manifest_approve_share: float = 0.0


# --------------------------------------------------------------------------------------
# One admissible-row attempt through the Coach gate (shared by every seeded pipeline).
# --------------------------------------------------------------------------------------
def _gate_and_build(
    *,
    bundle: dict[str, Any],
    label: dict[str, Any],
    provenance: dict[str, Any],
    split: str,
    generation_mode: str,
    dc_class: str | None,
    injection_recipe: str | None,
    bundle_schema_sha: str,
    teacher: ModelClient,
    coach: CoachClient,
    summary: GenerationSummary,
    control_bundle_hash: str | None = None,
) -> tuple[str, dict[str, Any] | None, dict[str, Any] | None]:
    """Run the Coach gate (schema + rationale-consistency + cue-audit) for one candidate row.

    Returns ``("accepted", row, None)`` or ``("rejected", None, reject_record)``. Refusals and
    rejections are loud RESULTS (recorded), never retries or silent degrades (honesty law 3).

    ``control_bundle_hash`` (seeded_code REJECT candidates only) arms the evidence-divergence
    guard: a reject candidate whose bundle content-hash equals its task's no-op CONTROL bundle
    hash is refused as ``evidence_invariant_injection`` — the planted defect did not surface in
    the evidence, so no reject label may ride it. Controls/approves never pass a hash here."""
    reject_base = {
        "repo": provenance["repo"], "task": provenance["task"],
        "generation_mode": generation_mode, "injection_recipe": injection_recipe,
    }
    # evidence-empty pre-gate (deterministic) — THE LOUDNESS LAW. A partial_exception /
    # missing_results regeneration gathered no usable evidence; it must never reach the teacher
    # (no wasted GPU) and never train (round-3 poison-path closure). Runs FIRST, before any
    # teacher call, so an evidence-empty bundle costs zero model legs.
    empty = evidence_empty_reason(bundle)
    if empty:
        summary.evidence_empty_rejected += 1
        return "rejected", None, {
            **reject_base, "reason": "evidence_empty_bundle", "detail": empty,
            "gathering_status": bundle.get("gathering_status"),
        }
    # THE EVIDENCE-DIVERGENCE GUARD (deterministic) — render-collapse poison-path closure.
    # Ordered AFTER the evidence-empty gate (an evidence-empty replay is rejected for the more
    # fundamental reason) and BEFORE any teacher call (a refused candidate costs zero model legs).
    # Belt-and-braces verdict check: only a REJECT label can be an evidence-invariant injection;
    # an approve/control describes the real record and is never refused here.
    if (
        control_bundle_hash is not None
        and label.get("verdict") == "reject"
        and bundle_content_hash(bundle) == control_bundle_hash
    ):
        summary.evidence_invariant_rejected += 1
        logger.warning(
            "EVIDENCE-DIVERGENCE GUARD refusal %s/%s recipe=%s — regenerated bundle is "
            "byte-identical to the task's no-op control bundle (content sha256 %s); the planted "
            "defect never surfaced in the evidence, so the reject label may not ride it",
            provenance["repo"], provenance["task"], injection_recipe, control_bundle_hash[:16],
        )
        return "rejected", None, {
            **reject_base,
            "reason": EVIDENCE_INVARIANT_REASON,
            "detail": (
                "regenerated bundle content-hash equals the task's no-op CONTROL bundle "
                "content-hash — the injected defect did not surface in the evidence, so no "
                "reject label may ride it (render-collapse poison-path closure)"
            ),
            "bundle_content_sha256": control_bundle_hash,
        }
    # cue-audit (deterministic) — the seeded_bundle gate, cheap on every seeded row.
    cue = cue_audit(bundle)
    if cue:
        summary.cue_rejected += 1
        return "rejected", None, {**reject_base, "reason": "cue_leakage", "cues": cue}
    # teacher authors the <think>; empty = a refusal RESULT.
    think = _author_think(teacher, bundle, label)
    if not think:
        summary.teacher_refused += 1
        return "rejected", None, {**reject_base, "reason": "teacher_refusal"}
    # schema — build_row validates the full envelope.
    try:
        row = build_row(
            bundle=bundle, think=think, label=label, provenance=provenance,
            split=split, generation_mode=generation_mode, dc_class=dc_class,
            bundle_schema_sha=bundle_schema_sha, reconstruction_fidelity=None,
            injection_recipe=injection_recipe,
        )
    except RowValidationError as exc:
        summary.schema_rejected += 1
        return "rejected", None, {**reject_base, "reason": "schema_invalid", "detail": str(exc)}
    # rationale-consistent-with-label — the injected Coach's only job (NOT content judgment).
    verdict = coach.assess(bundle, think, label)
    if not verdict.accepted:
        summary.coach_rejected += 1
        return "rejected", None, {
            **reject_base, "reason": "coach_rejected", "coach_reasons": verdict.reasons,
        }
    return "accepted", row, None


# --------------------------------------------------------------------------------------
# Driver.
# --------------------------------------------------------------------------------------
def _weighted_recipe_ids(config: GenerateConfig) -> list[str]:
    active = {rid: w for rid, w in config.recipes.items() if rid in RECIPES and w > 0}
    return sorted(active, key=lambda r: (-active[r], r))


def _seeded_limit_hit(config: GenerateConfig, writer: OutputWriter) -> bool:
    return (
        config.limit is not None
        and writer.counts["train"] + writer.counts["eval_qav"] >= config.limit
    )


def run_generation(
    config: GenerateConfig,
    *,
    teacher: ModelClient,
    coach: CoachClient,
    regenerator: BundleRegenerator,
    source_tasks: list[SourceTask] | None = None,
    bundle_mutations: list[BundleMutation] | None = None,
    outcomes: dict[tuple[str, str], Outcome] | None = None,
    emit_gold_negatives: bool = True,
    write_manifest: bool = True,
    created: str = "unset",
    factory_sha: str = "unset",
) -> GenerationSummary:
    """Run the offline QAV generation. ``teacher``/``coach``/``regenerator`` are injected
    (stubs in tests). ``source_tasks``/``bundle_mutations``/``outcomes`` are the pipeline
    inputs; when a seeded pipeline's input is ``None`` the engine discovers it from the config
    (``source_tasks`` via the corpus walk; ``outcomes`` via the ratified harvest-outcomes yaml) or
    runs inert (``bundle_mutations`` defaults to empty; an absent outcomes file harvests nothing).
    The harvest ``<think>`` is authored by the injected ``teacher`` against the fixed ratified
    label — never model-derived."""
    summary = GenerationSummary()
    scratch_dir = Path(config.scratch_dir)
    schema_sha = config.bundle_schema_sha

    if source_tasks is None and config.mode in ("seeded_defect", "both"):
        source_tasks = _discover_source_tasks(config)  # pragma: no cover - generation run
    source_tasks = source_tasks or []
    # seeded_bundle input: an injected list (tests) is used verbatim; ``None`` + a seeded mode
    # discovers the augmentation candidates from the REAL final-turn bundles keyed to the
    # record-resolved provenance of the known-green source tasks (PLAN §2 capped augmentation).
    if bundle_mutations is None and config.mode in ("seeded_defect", "both"):
        bundle_mutations = _discover_bundle_mutations(config, source_tasks, summary)
    bundle_mutations = bundle_mutations or []
    # outcomes: an injected dict (tests) is used verbatim; ``None`` + a harvest mode loads the
    # ratified, schema-validated outcomes yaml from config (queued/flagged skipped + counted).
    if outcomes is None and config.mode in ("harvest", "both"):
        loaded = load_harvest_outcomes(config.harvest_outcomes_path)
        outcomes = loaded.outcomes
        summary.harvest_outcomes_skipped += loaded.skipped
    outcomes = outcomes or {}

    with OutputWriter(config.output_dir) as writer:
        # --- seeded pipelines (seeded_code + control + seeded_bundle) ---------------------
        if config.mode in ("seeded_defect", "both"):
            _run_seeded_code(
                config, writer, summary, source_tasks,
                teacher=teacher, coach=coach, regenerator=regenerator,
                scratch_dir=scratch_dir, schema_sha=schema_sha,
            )
            _run_seeded_bundle(
                config, writer, summary, bundle_mutations,
                teacher=teacher, coach=coach, schema_sha=schema_sha,
            )
            # THE EVIDENCE-DIVERGENCE GUARD refusal count — loud in the summary, always.
            if summary.evidence_invariant_rejected:
                logger.warning(
                    "EVIDENCE-DIVERGENCE GUARD: %d seeded reject candidate(s) REFUSED as %s — "
                    "their regenerated bundles were byte-identical to their task's no-op control "
                    "bundle (no reject label may ride evidence the defect never reached)",
                    summary.evidence_invariant_rejected, EVIDENCE_INVARIANT_REASON,
                )

        # --- harvest (inert-clean when no outcomes supplied) ------------------------------
        if config.mode in ("harvest", "both") and outcomes:
            _run_harvest(config, writer, summary, outcomes, teacher=teacher, coach=coach)

        # --- gold negatives: ALWAYS eval_qav, the must-catch holdout ----------------------
        if emit_gold_negatives:
            corpus_roots = {k: Path(v) for k, v in config.corpus_roots.items()}
            for row in build_gold_negative_rows(corpus_roots or None):
                if writer.write_row(row):
                    summary.gold_negatives_written += 1
                else:
                    summary.deduped += 1

        summary.train = writer.counts["train"]
        summary.eval_qav = writer.counts["eval_qav"]
        summary.deduped += writer.duplicates_skipped

        if write_manifest:
            manifest = build_manifest(
                writer.train_rows, writer.eval_rows,
                dataset_id=config.dataset_id, created=created, factory_sha=factory_sha,
                train_file_path=str(Path(config.output_dir) / "train.jsonl"),
                bundle_schema_shas=None,
            )
            # MUST pass or the run fails loud (contamination embedded, OUTPUT-CONTRACT §5). This
            # is the ONLY hard finalize gate — it does NOT enforce balance.
            validate_manifest(manifest)
            # Balance is the SEPARATE advisory gate (check_balance): recorded honestly + logged
            # loudly, but it never crashes the run and never drops the already-banked rows. A low-N
            # approve-heavy set finalizes with a recorded balance refusal, not a silent skip.
            report = manifest["balance_report"]
            summary.manifest_approve_share = report["approve_share"]
            summary.manifest_balance_violations = check_balance(report)
            summary.manifest_balance_ok = not summary.manifest_balance_violations
            if summary.manifest_balance_violations:
                logger.warning(
                    "MANIFEST BALANCE ADVISORY FAIL (rows banked + manifest written honestly): %s",
                    "; ".join(summary.manifest_balance_violations),
                )
            manifest_paths = {Path(config.output_dir) / "manifest.json", Path(config.manifest_path)}
            for mp in manifest_paths:
                mp.parent.mkdir(parents=True, exist_ok=True)
                mp.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
            summary.manifest_finalized = True

    return summary


def _run_seeded_code(
    config: GenerateConfig,
    writer: OutputWriter,
    summary: GenerationSummary,
    source_tasks: list[SourceTask],
    *,
    teacher: ModelClient,
    coach: CoachClient,
    regenerator: BundleRegenerator,
    scratch_dir: Path,
    schema_sha: str,
) -> None:
    recipe_ids = _weighted_recipe_ids(config)
    for src in source_tasks:
        if _seeded_limit_hit(config, writer):
            return
        if (src.repo, src.task) in GOLD_SOURCE_TASKS:
            summary.gold_source_skipped += 1
            logger.info("SKIP seeded source %s/%s — gold-negative source task", src.repo, src.task)
            continue
        provenance = {
            "repo": src.repo, "feature": src.feature, "task": src.task,
            "run": src.run, "sha": src.sha,
        }
        # THE EVIDENCE-DIVERGENCE GUARD baseline: regenerate the task's no-op CONTROL bundle
        # FIRST (identical machinery — inject_control through the same worktree layout) and
        # content-hash it. Every reject recipe below is compared against this baseline in
        # _gate_and_build; a byte-identical reject bundle is refused (the defect never surfaced
        # in the evidence). The control ROW itself is still gated/written LAST from this same
        # single regeneration — one control regen per task, exactly as before.
        control = inject_control(dict(src.files))
        control_worktree = _materialize_worktree(
            scratch_dir, src.repo, src.task, control.recipe_id, control.mutated_files,
            record_dir=src.record_dir,
        )
        try:
            control_bundle = regenerator.regenerate(control_worktree)
        finally:
            shutil.rmtree(control_worktree, ignore_errors=True)
        validate_bundle(control_bundle)
        # L2 layer 3: scrub wall-clock jitter / per-run paths BEFORE the divergence-guard hash
        # AND before the control ROW is rendered (pre_regenerated_bundle below carries THIS scrubbed
        # bundle, so the guard compares against exactly the bundle the control row banks).
        control_bundle = scrub_nondeterministic_bundle(
            control_bundle, worktree_path=str(control_worktree)
        )
        control_hash = bundle_content_hash(control_bundle)
        # --- LAYER 4 scope-matched controls (per-recipe test-command overrides) ------------------
        # A per-recipe override runs a DIFFERENT test scope than the per-repo default, so a reject
        # under it would diverge from the DEFAULT-scope control TRIVIALLY (different tests ran) rather
        # than because the defect surfaced — the exact false-divergence the guard exists to prevent.
        # So each override recipe is compared against a control regenerated under its OWN command.
        # One control per DISTINCT override command (cached), materialized at that recipe's worktree
        # path so the regenerator selects the same pinned command. Recipes WITHOUT an override keep
        # comparing against ``control_hash`` (the default-scope control) — this whole block is a
        # no-op when no per-recipe overrides are configured for the repo (fully additive).
        per_recipe_cmds = config.test_commands_per_recipe.get(src.repo, {})
        scoped_control_hash: dict[str, str] = {}   # recipe_id -> matching-command control hash
        _cmd_control_cache: dict[str, str] = {}    # command -> control hash (dedupe equal commands)
        for recipe_id in recipe_ids:
            cmd = per_recipe_cmds.get(recipe_id)
            if not cmd:
                continue
            if cmd not in _cmd_control_cache:
                scoped_worktree = _materialize_worktree(
                    scratch_dir, src.repo, src.task, recipe_id, control.mutated_files,
                    record_dir=src.record_dir,
                )
                try:
                    scoped_bundle = regenerator.regenerate(scoped_worktree)
                finally:
                    shutil.rmtree(scoped_worktree, ignore_errors=True)
                validate_bundle(scoped_bundle)
                scoped_bundle = scrub_nondeterministic_bundle(
                    scoped_bundle, worktree_path=str(scoped_worktree)
                )
                _cmd_control_cache[cmd] = bundle_content_hash(scoped_bundle)
            scoped_control_hash[recipe_id] = _cmd_control_cache[cmd]
        # Reject-side: each weighted recipe (anchor-absent -> loud skip, never a silent no-op).
        for recipe_id in recipe_ids:
            if _seeded_limit_hit(config, writer):
                return
            try:
                result = inject(dict(src.files), recipe_id)
            except AnchorNotFound:
                summary.anchor_skipped += 1
                continue
            row = _seeded_row_from_injection(
                config, writer, summary, src, provenance, result,
                verdict_label=result.label, generation_mode="seeded_code",
                dc_class=result.dc_class, injection_recipe=recipe_id,
                teacher=teacher, coach=coach, regenerator=regenerator,
                scratch_dir=scratch_dir, schema_sha=schema_sha,
                control_bundle_hash=scoped_control_hash.get(recipe_id, control_hash),
            )
            if row:
                summary.seeded_code_written += 1
        # Seeded-control green: the identical machinery with a no-op injection, built from the
        # SAME regeneration that anchored the guard baseline (never re-regenerated — the guard
        # compares against exactly the bundle the control row carries).
        if _seeded_limit_hit(config, writer):
            return
        approve_label = {"verdict": "approve", "findings": [], "ground_truth_source": "seeded"}
        row = _seeded_row_from_injection(
            config, writer, summary, src, provenance, control,
            verdict_label=approve_label, generation_mode="seeded_code",
            dc_class=None, injection_recipe=control.recipe_id,
            teacher=teacher, coach=coach, regenerator=regenerator,
            scratch_dir=scratch_dir, schema_sha=schema_sha,
            pre_regenerated_bundle=control_bundle,
        )
        if row:
            summary.seeded_control_written += 1


def _seeded_row_from_injection(
    config: GenerateConfig,
    writer: OutputWriter,
    summary: GenerationSummary,
    src: SourceTask,
    provenance: dict[str, Any],
    result: InjectionResult,
    *,
    verdict_label: dict[str, Any],
    generation_mode: str,
    dc_class: str | None,
    injection_recipe: str | None,
    teacher: ModelClient,
    coach: CoachClient,
    regenerator: BundleRegenerator,
    scratch_dir: Path,
    schema_sha: str,
    control_bundle_hash: str | None = None,
    pre_regenerated_bundle: dict[str, Any] | None = None,
) -> bool:
    """Materialise the mutated worktree, regenerate the REAL bundle, gate + write. Returns True
    iff a fresh (non-duplicate) row was written.

    ``pre_regenerated_bundle`` (the control leg) skips materialise+regenerate and gates the
    already-regenerated bundle — the evidence-divergence guard's baseline regeneration IS the
    control row's bundle, never a second draw. ``control_bundle_hash`` (reject legs) arms the
    guard in ``_gate_and_build``."""
    if pre_regenerated_bundle is not None:
        bundle = pre_regenerated_bundle
    else:
        worktree = _materialize_worktree(
            scratch_dir, src.repo, src.task, result.recipe_id, result.mutated_files,
            record_dir=src.record_dir,
        )
        try:
            bundle = regenerator.regenerate(worktree)
        finally:
            shutil.rmtree(worktree, ignore_errors=True)
        # L2 layer 3: scrub non-determinism BEFORE the divergence-guard hash + row_id rendering
        # (the pre_regenerated_bundle control leg is already scrubbed upstream in _run_seeded_code).
        bundle = scrub_nondeterministic_bundle(bundle, worktree_path=str(worktree))
    validate_bundle(bundle)
    family = _family_of(injection_recipe, generation_mode)
    split = assign_split(
        src.repo, src.task, family,
        holdout_fraction=config.holdout_fraction, seed=config.seed,
    )
    status, row, reject = _gate_and_build(
        bundle=bundle, label=verdict_label, provenance=provenance, split=split,
        generation_mode=generation_mode, dc_class=dc_class, injection_recipe=injection_recipe,
        bundle_schema_sha=schema_sha, teacher=teacher, coach=coach, summary=summary,
        control_bundle_hash=control_bundle_hash,
    )
    if status == "accepted" and row is not None:
        if writer.write_row(row):
            return True
        summary.deduped += 1
        return False
    writer.write_rejected(reject or {})
    return False


def _run_seeded_bundle(
    config: GenerateConfig,
    writer: OutputWriter,
    summary: GenerationSummary,
    mutations: list[BundleMutation],
    *,
    teacher: ModelClient,
    coach: CoachClient,
    schema_sha: str,
) -> None:
    """Augmentation-only bundle-mutation rows, capped at ``seeded_bundle_cap`` of the seeded
    rows already written (PLAN §2: ``seeded_bundle`` ≤ 25% of seeded rows). Cue-audit is a hard
    gate. The cap is computed as a SHARE of the total seeded rows: with ``S`` primary seeded
    rows (seeded_code + control) already written and cap ``c``, at most ``floor(c·S/(1−c))``
    bundle rows are admitted so that bundle/(S+bundle) ≤ c."""
    if not mutations:
        return
    cap = config.seeded_bundle_cap
    primary = summary.seeded_code_written + summary.seeded_control_written
    max_bundle = 10**9 if cap >= 1.0 else int(cap * primary / (1.0 - cap))
    for mut in mutations:
        if (mut.repo, mut.task) in GOLD_SOURCE_TASKS:
            summary.gold_source_skipped += 1
            continue
        if summary.seeded_bundle_written >= max_bundle or _seeded_limit_hit(config, writer):
            summary.seeded_bundle_capped += 1
            continue
        validate_bundle(mut.bundle)
        provenance = {
            "repo": mut.repo, "feature": mut.feature, "task": mut.task,
            "run": mut.run, "sha": mut.sha,
        }
        family = _family_of(mut.recipe_id, "seeded_bundle")
        split = assign_split(
            mut.repo, mut.task, family,
            holdout_fraction=config.holdout_fraction, seed=config.seed,
        )
        status, row, reject = _gate_and_build(
            bundle=mut.bundle, label=mut.label, provenance=provenance, split=split,
            generation_mode="seeded_bundle", dc_class=mut.finding["class"],
            injection_recipe=mut.recipe_id, bundle_schema_sha=schema_sha,
            teacher=teacher, coach=coach, summary=summary,
        )
        if status == "accepted" and row is not None:
            if writer.write_row(row):
                summary.seeded_bundle_written += 1
            else:
                summary.deduped += 1
        else:
            writer.write_rejected(reject or {})


def _run_harvest(
    config: GenerateConfig,
    writer: OutputWriter,
    summary: GenerationSummary,
    outcomes: dict[tuple[str, str], Outcome],
    *,
    teacher: ModelClient,
    coach: CoachClient,
) -> None:
    """Harvest real committed bundles + ratified post-hoc outcomes (census §2). For each
    consumable label: locate the task's final-turn bundle via the CENSUS-SAFE, skip-filtered
    discovery (never the bare ``discover_bundles``), run the evidence-empty pre-gate (the SAME
    loudness law as the seeded path, before any teacher call), have the teacher author the
    ``<think>`` AGAINST the fixed ratified label (never model-derived), Coach-gate the row, then
    build it via ``build_harvest_row`` and write. Rejects route to ``rejected.jsonl`` with a
    reason, exactly as the seeded path does — a missing bundle, an evidence-empty regeneration, a
    teacher refusal, a schema failure, or a Coach revise is a loud RESULT, never a crash or a
    silent drop. Gold-negative source tasks are excluded; split is assigned per
    ``(repo, task, 'harvest')`` so a task's harvested rows never straddle the split.

    NOTE: the seeded cue-audit is deliberately NOT run here — these are AUTHENTIC serialized
    bundles, not injected/mutated ones, so a real ``"..."`` truncation or an incidental keyword in
    genuine evidence must not be treated as a synthetic cue-leak (cue-audit is the seeded_bundle
    gate). The evidence-empty pre-gate DOES apply — a poison regeneration is poison in any mode."""
    corpus_roots = {k: Path(v) for k, v in config.corpus_roots.items()}
    clean_outcomes = {
        key: oc for key, oc in outcomes.items() if key not in GOLD_SOURCE_TASKS
    }
    summary.gold_source_skipped += len(outcomes) - len(clean_outcomes)
    if not clean_outcomes:
        return
    index = discover_final_turn_bundles(corpus_roots)  # census-safe: skips .claude/worktrees
    for (repo, task), outcome in sorted(clean_outcomes.items()):
        reject_base = {"repo": repo, "task": task, "generation_mode": "harvest", "injection_recipe": None}
        art = index.get((repo, task))
        if art is None:
            summary.harvest_bundle_not_found += 1
            logger.info("HARVEST no bundle on disk for %s/%s — excluded (loud, never fabricated)", repo, task)
            writer.write_rejected({
                **reject_base, "reason": "bundle_not_found",
                "detail": "no skip-filtered final-turn bundle for (repo, task) under the corpus roots",
            })
            continue
        # The verdict is FIXED by the ratified label — never model-derived (mirrors _verdict_for /
        # the seeded label-fixed law). Approve => coach_correct; every other in-scope source rejects.
        verdict = "approve" if outcome.ground_truth_source == _APPROVE_SOURCE else "reject"
        label = {
            "verdict": verdict,
            "findings": [outcome.finding] if verdict == "reject" and outcome.finding else [],
            "ground_truth_source": outcome.ground_truth_source,
        }
        # evidence-empty pre-gate — THE LOUDNESS LAW, before any teacher call (same as seeded).
        empty = evidence_empty_reason(art.bundle)
        if empty:
            summary.evidence_empty_rejected += 1
            writer.write_rejected({
                **reject_base, "reason": "evidence_empty_bundle", "detail": empty,
                "gathering_status": art.bundle.get("gathering_status"),
            })
            continue
        # teacher authors ONLY the <think> against the fixed label; empty output = a refusal RESULT.
        think = _author_think(teacher, art.bundle, label)
        if not think:
            summary.teacher_refused += 1
            writer.write_rejected({**reject_base, "reason": "teacher_refusal"})
            continue
        # split per (repo, task, 'harvest') — never straddles; build the canonical harvest row.
        split = assign_split(
            repo, task, "harvest", holdout_fraction=config.holdout_fraction, seed=config.seed
        )
        try:
            row = build_harvest_row(art, outcome, think=think, split=split)
        except RowValidationError as exc:
            summary.schema_rejected += 1
            writer.write_rejected({**reject_base, "reason": "schema_invalid", "detail": str(exc)})
            continue
        # Coach gate — rationale-consistency only (NOT a content re-judgment; the label is fixed).
        cv = coach.assess(art.bundle, think, label)
        if not cv.accepted:
            summary.coach_rejected += 1
            writer.write_rejected({**reject_base, "reason": "coach_rejected", "coach_reasons": cv.reasons})
            continue
        if writer.write_row(row):
            summary.harvest_written += 1
        else:
            summary.deduped += 1


def _discover_source_tasks(config: GenerateConfig) -> list[SourceTask]:  # pragma: no cover - generation run
    """Discover known-green source tasks from the config corpus roots, checking each out at its
    record-resolved approved sha into a read-only scratch worktree and reading its scoped file
    map into memory.

    This is the generation-run seam (GB10, post-window): it does real git + filesystem work
    against the read-only corpus repos and is NEVER reached by unit tests (they inject
    ``source_tasks`` directly; ``qav.discover``'s record/scoping functions are unit-tested
    hermetically). Discovery resolves each approved sha from real on-disk record evidence
    (``.guardkit/archive/<FEAT>/merge_summary.json``) — a task with no resolvable sha is EXCLUDED
    with a logged reason, never guessed and never defaulted to HEAD (the approved-sha honesty law).
    ``config.interpreters`` feeds the interpreter-bridged ``SubprocessBridgeRegenerator``."""
    from qav.discover import discover_source_tasks as _discover

    resolved = _discover(config, limit=config.limit)
    return [
        SourceTask(
            repo=r.repo, feature=r.feature, task=r.task, sha=r.sha, files=r.files, run="seeded",
            record_dir=r.record_dir,
        )
        for r in resolved
    ]
