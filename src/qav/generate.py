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
from qav.harvest import Outcome, harvest as harvest_transform
from qav.injector import (
    BundleRegenerator,
    InjectionResult,
    inject,
    inject_control,
)
from qav.manifest import build_manifest, validate_manifest
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

    @classmethod
    def from_yaml(cls, path: str | Path) -> "GenerateConfig":
        data = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
        gen = data.get("generation", {}) or {}
        out = data.get("output", {}) or {}
        corpus = data.get("corpus", {}) or {}
        corpus_roots = {k: v for k, v in corpus.items() if k != "bundle_schema_sha"}
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
# Summary.
# --------------------------------------------------------------------------------------
@dataclass
class GenerationSummary:
    seeded_code_written: int = 0
    seeded_control_written: int = 0
    seeded_bundle_written: int = 0
    seeded_bundle_capped: int = 0  # candidates dropped by the ≤cap share rule
    harvest_written: int = 0
    gold_negatives_written: int = 0
    teacher_refused: int = 0
    coach_rejected: int = 0
    cue_rejected: int = 0
    evidence_empty_rejected: int = 0  # regenerated bundle had no usable evidence (loudness law)
    schema_rejected: int = 0
    anchor_skipped: int = 0  # recipe anchor absent from a source task (loud, not silent)
    gold_source_skipped: int = 0  # source tasks excluded as gold-negative sources
    deduped: int = 0
    train: int = 0
    eval_qav: int = 0


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
) -> tuple[str, dict[str, Any] | None, dict[str, Any] | None]:
    """Run the Coach gate (schema + rationale-consistency + cue-audit) for one candidate row.

    Returns ``("accepted", row, None)`` or ``("rejected", None, reject_record)``. Refusals and
    rejections are loud RESULTS (recorded), never retries or silent degrades (honesty law 3)."""
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
    think_by_task: dict[str, str] | None = None,
    emit_gold_negatives: bool = True,
    write_manifest: bool = True,
    created: str = "unset",
    factory_sha: str = "unset",
) -> GenerationSummary:
    """Run the offline QAV generation. ``teacher``/``coach``/``regenerator`` are injected
    (stubs in tests). ``source_tasks``/``bundle_mutations``/``outcomes`` are the pipeline
    inputs; when a seeded pipeline's input is ``None`` the engine discovers it from the config
    (a generation-run path, never reached by tests) or runs inert (``bundle_mutations``/
    ``outcomes`` default to empty)."""
    summary = GenerationSummary()
    scratch_dir = Path(config.scratch_dir)
    schema_sha = config.bundle_schema_sha

    if source_tasks is None and config.mode in ("seeded_defect", "both"):
        source_tasks = _discover_source_tasks(config)  # pragma: no cover - generation run
    source_tasks = source_tasks or []
    bundle_mutations = bundle_mutations or []
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

        # --- harvest transform (inert-clean when no outcomes supplied) --------------------
        if config.mode in ("harvest", "both") and outcomes:
            _run_harvest(config, writer, summary, outcomes, think_by_task or {})

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
            # MUST pass or the run fails loud (contamination embedded, OUTPUT-CONTRACT §5).
            validate_manifest(manifest)
            manifest_paths = {Path(config.output_dir) / "manifest.json", Path(config.manifest_path)}
            for mp in manifest_paths:
                mp.parent.mkdir(parents=True, exist_ok=True)
                mp.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")

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
        if (src.repo, src.task) in GOLD_SOURCE_TASKS:
            summary.gold_source_skipped += 1
            logger.info("SKIP seeded source %s/%s — gold-negative source task", src.repo, src.task)
            continue
        provenance = {
            "repo": src.repo, "feature": src.feature, "task": src.task,
            "run": src.run, "sha": src.sha,
        }
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
            )
            if row:
                summary.seeded_code_written += 1
        # Seeded-control green: the identical machinery with a no-op injection.
        if _seeded_limit_hit(config, writer):
            return
        control = inject_control(dict(src.files))
        approve_label = {"verdict": "approve", "findings": [], "ground_truth_source": "seeded"}
        row = _seeded_row_from_injection(
            config, writer, summary, src, provenance, control,
            verdict_label=approve_label, generation_mode="seeded_code",
            dc_class=None, injection_recipe=control.recipe_id,
            teacher=teacher, coach=coach, regenerator=regenerator,
            scratch_dir=scratch_dir, schema_sha=schema_sha,
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
) -> bool:
    """Materialise the mutated worktree, regenerate the REAL bundle, gate + write. Returns True
    iff a fresh (non-duplicate) row was written."""
    worktree = _materialize_worktree(
        scratch_dir, src.repo, src.task, result.recipe_id, result.mutated_files,
        record_dir=src.record_dir,
    )
    try:
        bundle = regenerator.regenerate(worktree)
    finally:
        shutil.rmtree(worktree, ignore_errors=True)
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
    think_by_task: dict[str, str],
) -> None:
    """Harvest real bundles + post-hoc curator outcomes. Gold-negative source tasks and rows
    whose (repo, task) is a gold source are excluded; split is assigned per (repo, task,
    'harvest') so a task's harvested rows never straddle the split."""
    corpus_roots = {k: Path(v) for k, v in config.corpus_roots.items()}
    clean_outcomes = {
        key: oc for key, oc in outcomes.items() if key not in GOLD_SOURCE_TASKS
    }
    summary.gold_source_skipped += len(outcomes) - len(clean_outcomes)
    for row in harvest_transform(corpus_roots, clean_outcomes, think_by_task=think_by_task):
        prov = row["metadata"]["provenance"]
        split = assign_split(
            prov["repo"], prov["task"], "harvest",
            holdout_fraction=config.holdout_fraction, seed=config.seed,
        )
        # Re-stamp split + row_id-independent metadata (harvest built them at split=train).
        if row["metadata"]["split"] != split:
            row = _restamp_split(row, split)
        if writer.write_row(row):
            summary.harvest_written += 1
        else:
            summary.deduped += 1


def _restamp_split(row: dict[str, Any], split: str) -> dict[str, Any]:
    """Return the row with its split re-stamped (row_id is content-addressed on the user
    message, which is unchanged, so it stays valid)."""
    row = json.loads(json.dumps(row))  # deep copy
    row["metadata"]["split"] = split
    return row


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
