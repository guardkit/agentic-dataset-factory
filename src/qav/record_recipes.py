"""Record-native mutation recipes — the ``seeded_record`` family (WS2-B11, 2026-07-23).

**Why this module exists (grounded in the attribution diagnosis).**
``fleet-evals/RESULTS-qav-ft-v1-2026-07-23.md`` names one residual failure axis for the pilot
tune: **defect-class/locus attribution**. The tune rejected 12/12 gold negatives at verdict level
but attributed DC-12 as the misattribution sink and caught the DC-14 narrative false-green (RC-01)
**never with class DC-14** (DC-14 train support = 0 rows in-name; DC-05 = 2 rows). The receipt's
own cure is *"a corpus that grows reject-side class diversity (a new mechanism class)"* — not more
epochs. ``seeded_record`` is that new mechanism class, and it is the **only** mechanism that can
produce genuine DC-12 and DC-14 rejects: ``recipes.py``'s own docstrings prove DC-12/DC-14 are
**EXPECTED-MISS** for source-tree injection because the bundle's ``plan_audit`` / honesty signal is
sourced from ``task_work_results`` under ``.guardkit/autobuild/<task>/`` — gitignored, excluded from
the scoped source map, and **materialized verbatim at regeneration time**. Source-tree injection
(``seeded_code``) structurally cannot reach them; a ``seeded_record`` recipe mutates that
materialized record **before** ``gather_evidence`` replays it, so the divergence is earned through
the real gather machinery.

**The tier + the frozen-schema threading (the decisive finding).** ``contracts.py`` is byte-frozen
(``ed00704``): its ``GENERATION_MODES`` allowlist is ``{seeded_code, seeded_bundle, harvest,
gold_negative}`` and cannot admit a new ``seeded_record`` mode, and its metadata key set is fixed.
So the family threads through the frozen schema: a record mutation re-runs the **real** gather
machinery over a mutated worktree INPUT (the record), exactly as ``seeded_code`` re-runs it over a
mutated worktree INPUT (the source tree) — the same generation MODE, a different mutation SURFACE.
Record rows are therefore emitted with ``generation_mode="seeded_code"`` and an ``injection_recipe``
in the disjoint ``R-RECORD-*`` namespace (never in the frozen ``recipes.RECIPES``, never in the
``R-BUNDLE-*`` namespace), so ``generate._family_of`` / ``contamination._family`` both fall through
to the mode key and every record variant of one task shares its split (the PLAN §6 straddle law,
structurally). No information is lost: ``injection_recipe`` fully identifies the record-native
family for any downstream filter.

**This module is PURE.** Every recipe is a ``dict -> (mutated_record, locus) | None`` transform of a
parsed ``task_work_results`` record (mirrors ``recipes.py`` philosophy — unit-testable on tiny local
fixtures, no worktree / test substrate / model). ``None`` = the anchor is absent (the record already
carries a violation, or lacks the field) and the caller raises it as a LOUD ``record_anchor_skipped``
RESULT — never a silent no-op (the FEAT-DD4F law). The verdict + finding of every row are fixed by
construction here (``ground_truth_source: seeded``); a teacher authors only the ``<think>``.

**The anti-shortcut law (this family's soul).** The model's input is the *bundle*, not the record —
so a record touch is only a shortcut if it leaves a *bundle-visible* cue correlated with reject.
Every reject recipe is therefore matched by a **control** recipe that populates the *same*
bundle-field family in an **approve-legitimate** configuration, labelled ``approve``, through the
identical machinery. The control is not a trivial no-op; it is a semantically-neutral (or
Layer-2-legitimate) edit of the identical surface. This defeats "surface-populated ⇒ reject" and
supplies the two-sided calibration rows GOAL.md criterion 6 needs.

**Bundle-visible mutation surface** (traced through guardkit ``gather_evidence`` →
``CoachEvidenceBundle``; mutating anything else is inert and the divergence guard refuses it):

* ``plan_audit`` (dict)  → ``bundle.plan_audit`` **verbatim** + drives ``quality_gates
  .plan_audit_passed`` (``severity=="high"`` OR ``violations>0`` when ``status ∉ {skipped,
  auditor_error}`` ⇒ gate fails ⇒ ``partial_gate_abort``).  → DC-12.
* ``completion_promises[].implementation_files`` / ``files_created`` / ``files_modified``  →
  ``bundle.honesty.discrepancies`` (existence-on-disk).  A ``promise_file_existence`` or **≥2**
  ``file_existence`` critical discrepancies are must_fix ⇒ ``partial_honesty_abort``; a **single**
  ``file_existence`` is Layer-2-demoted to a should_fix advisory (approve-legitimate).  → DC-14.
* ``quality_gates`` (dict)  → ``bundle.quality_gates`` + ``bundle.tests`` (``all_passed`` resting on
  zero executed / skipped tests = the claim-vs-skip divergence).  → DC-05 (medium fidelity — see the
  ``R-RECORD-DC05-*`` note; the strong sys.modules/skip-guard DC-05 is source-native and owned by
  ``seeded_code``).
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Callable, Optional

from qav.contracts import PHASE1_DC_CLASSES  # read-only: keep the admissible-class set in sync

# The record artifact filename the whole family reads/writes (guardkit
# ``TaskArtifactPaths.TASK_WORK_RESULTS`` basename — the engine materializes it into
# ``.guardkit/autobuild/<task>/`` before regeneration).
RUN_RECORD_FILENAME = "task_work_results.json"

# Plausible source-module suffixes for deriving nonexistent-but-realistic file paths. Deliberately
# ordinary engineering words — NEVER a sentinel/injection token (the cue-audit families) — so the
# regenerated bundle carries no telltale correlated with reject.
_PLAUSIBLE_SUFFIXES: tuple[str, ...] = (
    "helpers", "adapter", "wiring", "runtime", "gateway", "bridge", "handlers", "coordinator",
)
_FALLBACK_PATHS: tuple[str, ...] = (
    "src/service/handlers.py", "src/core/adapter.py", "src/app/wiring.py", "src/lib/runtime.py",
)


class RecordRecipeError(ValueError):
    """A record recipe was asked to do something structurally impossible (bad registry wiring)."""


# --------------------------------------------------------------------------------------
# Deterministic helpers (pure). Same record in -> same mutation out (the reproducibility law).
# --------------------------------------------------------------------------------------
def _stable_seed(record: dict[str, Any]) -> int:
    """A stable integer derived from the record's identity — deterministic across processes.

    Prefers ``task_id`` (present on every real record); falls back to a canonical hash of the
    file lists so tiny fixtures without a ``task_id`` are still deterministic."""
    ident = record.get("task_id")
    if not isinstance(ident, str) or not ident:
        ident = json.dumps(
            [record.get("files_created"), record.get("files_modified")],
            sort_keys=True, ensure_ascii=False,
        )
    return int(hashlib.sha256(ident.encode("utf-8")).hexdigest()[:8], 16)


def _stable_count(record: dict[str, Any], lo: int, hi: int, *, salt: str) -> int:
    """A deterministic count in ``[lo, hi]`` — varies across tasks (defeats a constant-count cue),
    reproducible for one record. ``salt`` decorrelates counts between recipes on the same task."""
    if lo > hi:
        raise RecordRecipeError(f"bad count range [{lo}, {hi}]")
    span = hi - lo + 1
    h = int(hashlib.sha256(f"{salt}:{_stable_seed(record)}".encode()).hexdigest()[:8], 16)
    return lo + (h % span)


def _stable_pct(record: dict[str, Any], lo: float, hi: float, *, salt: str) -> float:
    """A deterministic percentage in ``[lo, hi]`` rounded to one decimal — for loc_variance_pct."""
    h = int(hashlib.sha256(f"{salt}:{_stable_seed(record)}".encode()).hexdigest()[:8], 16)
    return round(lo + (h % 1000) / 1000.0 * (hi - lo), 1)


def _all_record_paths(record: dict[str, Any]) -> set[str]:
    """Every path string the record already names (created/modified/authored/tests/promise files)
    — the set a derived path must avoid to be genuinely nonexistent."""
    paths: set[str] = set()
    for key in ("files_created", "files_modified", "files_authored", "tests_written"):
        vals = record.get(key)
        if isinstance(vals, list):
            paths.update(str(v) for v in vals if isinstance(v, str))
    promises = record.get("completion_promises")
    if isinstance(promises, list):
        for pr in promises:
            if isinstance(pr, dict):
                impl = pr.get("implementation_files")
                if isinstance(impl, list):
                    paths.update(str(v) for v in impl if isinstance(v, str))
                tf = pr.get("test_file")
                if isinstance(tf, str):
                    paths.add(tf)
    return paths


def _relative_source_seeds(record: dict[str, Any]) -> list[str]:
    """Relative ``.py`` paths under a source-looking tree, oldest-first-deterministic — the seeds a
    plausible nonexistent sibling is derived from. Excludes absolute paths and ``.guardkit`` /
    dotfile records (they are run-artifacts, not source the plan/honesty judges against)."""
    seeds: list[str] = []
    for key in ("files_created", "files_modified", "files_authored"):
        vals = record.get(key)
        if not isinstance(vals, list):
            continue
        for v in vals:
            if not isinstance(v, str) or not v.endswith(".py"):
                continue
            if v.startswith("/") or v.startswith(".") or "/." in v:
                continue
            if v not in seeds:
                seeds.append(v)
    return seeds


def _derive_nonexistent_paths(record: dict[str, Any], k: int, *, salt: str) -> list[str]:
    """``k`` plausible, deterministic, genuinely-nonexistent ``.py`` paths derived from the record's
    own source tree (a real module's dir + a plausible sibling stem) — realistic + cue-clean. Falls
    back to generic source paths when the record names no relative source files."""
    existing = _all_record_paths(record)
    seeds = _relative_source_seeds(record) or list(_FALLBACK_PATHS)
    start = _stable_seed(record) % len(_PLAUSIBLE_SUFFIXES)
    out: list[str] = []
    # Rotate seed × suffix deterministically until we have k novel paths.
    attempt = 0
    max_attempts = len(seeds) * len(_PLAUSIBLE_SUFFIXES) * 4 + k + 8
    while len(out) < k and attempt < max_attempts:
        seed = seeds[(_stable_seed(record) + attempt) % len(seeds)]
        suffix = _PLAUSIBLE_SUFFIXES[(start + attempt) % len(_PLAUSIBLE_SUFFIXES)]
        if "/" in seed:
            parent, _, base = seed.rpartition("/")
            stem = base[:-3] if base.endswith(".py") else base
            candidate = f"{parent}/{stem}_{suffix}.py"
        else:
            stem = seed[:-3] if seed.endswith(".py") else seed
            candidate = f"{stem}_{suffix}.py"
        if candidate not in existing and candidate not in out:
            out.append(candidate)
        attempt += 1
    # Last-resort deterministic uniquifier (never a sentinel — a numeric ordinal on a real dir).
    while len(out) < k:
        base = seeds[len(out) % len(seeds)]
        parent = base.rpartition("/")[0] or "src"
        candidate = f"{parent}/module_{len(out)}_{salt}.py"
        if candidate not in existing and candidate not in out:
            out.append(candidate)
    return out


def _plan_audit_template(record: dict[str, Any]) -> dict[str, Any]:
    """The authentic ``plan_audit`` dict as the base to override (preserves guardkit's full key
    shape so the verbatim passthrough stays schema-plausible). Empty base when absent."""
    pa = record.get("plan_audit")
    return dict(pa) if isinstance(pa, dict) else {}


def _plan_audit_is_violation(record: dict[str, Any]) -> bool:
    pa = record.get("plan_audit")
    if not isinstance(pa, dict):
        return False
    return pa.get("status") == "violation" or bool(pa.get("violations"))


def _created_count(record: dict[str, Any]) -> int:
    vals = record.get("files_created")
    return len(vals) if isinstance(vals, list) else 0


# --------------------------------------------------------------------------------------
# The recipe registry types.
# --------------------------------------------------------------------------------------
# A plan returns (mutated_record, locus) for a firing recipe, or None when the anchor is absent
# (the record already carries the violation, or lacks the field to mutate) — a LOUD skip, never a
# silent no-op. ``locus`` is unused for approve controls (their label carries no finding).
RecordPlan = Callable[[dict[str, Any]], "Optional[tuple[dict[str, Any], str]]"]


@dataclass(frozen=True)
class RecordRecipe:
    """A record-native mutation: metadata + a pure planner over the ``task_work_results`` dict.

    ``verdict`` is fixed by construction. ``dc_class`` is the finding class for rejects (``None`` for
    approve controls — the calibration rows that populate the same surface, approve-legitimate)."""

    id: str
    dc_class: Optional[str]  # a PHASE-1 class for rejects; None for approve controls
    verdict: str             # "reject" | "approve"
    shape: str               # the real incident shape / calibration intent it reproduces
    expected_signature: str  # what the regenerated bundle is expected to show
    plan: RecordPlan


@dataclass
class RecordInjectionResult:
    """The applied mutation: the mutated record + the fixed-by-construction label."""

    recipe_id: str
    dc_class: Optional[str]
    verdict: str
    mutated_record: dict[str, Any]
    finding: Optional[dict[str, str]]  # {"class", "locus"} for rejects; None for approve controls

    @property
    def label(self) -> dict[str, Any]:
        if self.verdict == "reject":
            if not self.finding:
                raise RecordRecipeError(f"reject recipe {self.recipe_id} produced no finding")
            return {"verdict": "reject", "findings": [self.finding], "ground_truth_source": "seeded"}
        return {"verdict": "approve", "findings": [], "ground_truth_source": "seeded"}


# ======================================================================================
# DC-12 · plan_audit (the flagship — highest fidelity: plan_audit is a verbatim passthrough).
# ======================================================================================
def _rec_dc12_missingfiles(record: dict[str, Any]) -> Optional[tuple[dict[str, Any], str]]:
    """Reject: the plan declared files the implementation never produced. Sets ``plan_audit`` to a
    high-severity violation with ``missing_files`` drawn from the task's own tree (plausible), and
    a varied ``violations`` count (1-4) to defeat a constant-count cue. Bundle: ``plan_audit_passed
    =False`` (severity high) ⇒ ``partial_gate_abort``; ``plan_audit.missing_files`` non-empty vs
    green tests. Anchor-absent ⇒ None when the record already carries a plan violation."""
    if "plan_audit" not in record or _plan_audit_is_violation(record):
        return None
    k = _stable_count(record, 1, 4, salt="dc12-missing")
    missing = _derive_nonexistent_paths(record, k, salt="missing")
    pa = _plan_audit_template(record)
    pa.update({
        "status": "violation", "severity": "high", "violations": k,
        "missing_files": missing, "discrepancies_count": k,
        "message": f"{k} planned file(s) not created: {', '.join(missing)}",
    })
    mutated = dict(record)
    mutated["plan_audit"] = pa
    locus = (
        f"bundle.plan_audit.missing_files (+ quality_gates.plan_audit_passed=False) — "
        f"{k} plan-declared file(s) absent while tests report green"
    )
    return mutated, locus


def _rec_dc12_extramod(record: dict[str, Any]) -> Optional[tuple[dict[str, Any], str]]:
    """Reject: scope-creep — the implementation strayed beyond the approved plan. Drives the
    ``violations>0`` gate-fail path DELIBERATELY WITHOUT ``severity`` (so the model never learns
    "severity key ⇒ reject"), with ``extra_modifications`` + a high ``loc_variance_pct``. Bundle:
    ``plan_audit_passed=False`` via violations>0 ⇒ ``partial_gate_abort``."""
    if "plan_audit" not in record or _plan_audit_is_violation(record):
        return None
    m = _stable_count(record, 1, 3, salt="dc12-extra")
    extra = _derive_nonexistent_paths(record, m, salt="extra")
    pct = _stable_pct(record, 35.0, 70.0, salt="dc12-extra")
    pa = _plan_audit_template(record)
    pa.update({
        "status": "violation", "severity": None, "violations": m,
        "extra_modifications": extra, "loc_variance_pct": pct, "discrepancies_count": m,
        "message": f"{m} file(s) modified outside the approved plan; LOC variance {pct}%",
    })
    mutated = dict(record)
    mutated["plan_audit"] = pa
    locus = (
        "bundle.plan_audit.extra_modifications + loc_variance_pct — implementation strayed "
        "beyond the approved plan (violations>0, plan_audit_passed=False)"
    )
    return mutated, locus


def _rec_dc12_gateorder(record: dict[str, Any]) -> Optional[tuple[dict[str, Any], str]]:
    """Reject (the PLAN §3 canonical): a gate sequenced before its test exists / an unverifiable AC
    at gate time. ``plan_audit.message`` names the ordering finding, severity high, standing against
    otherwise-green gates — the bundle-visible plan defect PLAN §3 R-DC12-planvisible intended but
    could not reach via source injection."""
    if "plan_audit" not in record or _plan_audit_is_violation(record):
        return None
    pa = _plan_audit_template(record)
    pa.update({
        "status": "violation", "severity": "high", "violations": 1, "discrepancies_count": 1,
        "message": (
            "plan sequences a quality gate before the test that would verify it exists; "
            "one acceptance criterion is unverifiable at gate time"
        ),
    })
    mutated = dict(record)
    mutated["plan_audit"] = pa
    locus = (
        "bundle.plan_audit.message (severity=high) — a gate is sequenced before its test exists "
        "(plan_audit finding standing against green gates)"
    )
    return mutated, locus


def _rec_dc12_control_clean(record: dict[str, Any]) -> Optional[tuple[dict[str, Any], str]]:
    """Approve control: the SAME ``plan_audit`` surface, populated + PASSING (plan honored). Defeats
    "plan_audit elaborated beyond `skipped` ⇒ reject." Anchor-absent ⇒ None when the authentic audit
    is already a violation (no clean green to falsify)."""
    if "plan_audit" not in record or _plan_audit_is_violation(record):
        return None
    n = _created_count(record)
    pa = _plan_audit_template(record)
    pa.update({
        "status": "passed", "severity": None, "violations": 0,
        "missing_files": [], "extra_modifications": [], "loc_variance_pct": 0.0,
        "discrepancies_count": 0, "message": f"plan honored; {n} file(s) as planned",
    })
    mutated = dict(record)
    mutated["plan_audit"] = pa
    return mutated, ""


def _rec_dc12_control_lowvar(record: dict[str, Any]) -> Optional[tuple[dict[str, Any], str]]:
    """Approve control (a MANDATORY ugly-green): a passing ``plan_audit`` carrying a small non-zero
    ``loc_variance_pct`` + benign note = an honest green with in-tolerance drift. The anti-over-reject
    lever GOAL.md criterion 6 measures."""
    if "plan_audit" not in record or _plan_audit_is_violation(record):
        return None
    pct = _stable_pct(record, 1.0, 6.0, salt="dc12-lowvar")
    pa = _plan_audit_template(record)
    pa.update({
        "status": "passed", "severity": None, "violations": 0,
        "missing_files": [], "extra_modifications": [], "loc_variance_pct": pct,
        "discrepancies_count": 0,
        "message": f"plan honored; minor in-tolerance LOC drift {pct}%",
    })
    mutated = dict(record)
    mutated["plan_audit"] = pa
    return mutated, ""


# ======================================================================================
# DC-14 · honesty over-claim (high fidelity — the exact RC-01 class the tune misattributed).
# ======================================================================================
def _first_complete_promise_idx(record: dict[str, Any]) -> Optional[int]:
    promises = record.get("completion_promises")
    if not isinstance(promises, list):
        return None
    for i, pr in enumerate(promises):
        if (
            isinstance(pr, dict)
            and pr.get("status") == "complete"
            and isinstance(pr.get("implementation_files"), list)
            and pr["implementation_files"]
        ):
            return i
    return None


def _rec_dc14_promisefile(record: dict[str, Any]) -> Optional[tuple[dict[str, Any], str]]:
    """Reject: a completion promise claims an ``implementation_file`` not on disk — the FEAT-6CC5
    sophisticated-lie shape (a ``promise_file_existence`` discrepancy is must_fix, retained not
    demoted ⇒ ``partial_honesty_abort``) with ``status=="complete"``. The exact RC-01 class the tune
    caught but attributed as DC-03. Anchor-absent ⇒ None when no complete promise carries impl files."""
    idx = _first_complete_promise_idx(record)
    if idx is None:
        return None
    fake = _derive_nonexistent_paths(record, 1, salt="promise")[0]
    promises = [dict(pr) if isinstance(pr, dict) else pr for pr in record["completion_promises"]]
    pr = dict(promises[idx])
    pr["implementation_files"] = list(pr["implementation_files"]) + [fake]
    promises[idx] = pr
    mutated = dict(record)
    mutated["completion_promises"] = promises
    cid = pr.get("criterion_id", f"promise[{idx}]")
    locus = (
        f"bundle.honesty.discrepancies[promise_file_existence] — completion promise {cid} claims "
        f"implementation_file {fake} not present on disk (status=complete, gates green)"
    )
    return mutated, locus


def _rec_dc14_multifile(record: dict[str, Any]) -> Optional[tuple[dict[str, Any], str]]:
    """Reject: the narrative claims a BATCH of files (>=2) it never wrote — multiple ``file_existence``
    critical discrepancies retain must_fix ⇒ ``partial_honesty_abort``. Anchor-absent ⇒ None when the
    record names no ``files_created`` to over-claim against."""
    if not isinstance(record.get("files_created"), list) or not record["files_created"]:
        return None
    k = 2 + _stable_count(record, 0, 1, salt="dc14-multi")  # 2 or 3 (>=2 is the must_fix threshold)
    fakes = _derive_nonexistent_paths(record, k, salt="multi")
    mutated = dict(record)
    mutated["files_created"] = list(record["files_created"]) + fakes
    locus = (
        f"bundle.honesty.discrepancies[file_existence]x{k} — narrative claims {k} created file(s) "
        f"not present on disk while gates report green"
    )
    return mutated, locus


def _rec_dc14_control_demoted(record: dict[str, Any]) -> Optional[tuple[dict[str, Any], str]]:
    """Approve control (the single most valuable calibration row this family emits — triple duty):
    append EXACTLY ONE nonexistent path to ``files_created``. ``_honesty_issues_from`` demotes a lone
    ``file_existence`` critical to should_fix (the path-string-mismatch-is-not-dishonesty Layer-2
    demotion): ``gathering_status`` stays ``complete``, ``advisory_issues`` populated,
    ``verified=False`` **but approve-legitimate** — the ugly-green the judge must NOT false-block.
    (i) defeats "honesty.discrepancies non-empty ⇒ reject"; (ii) IS a mandatory ugly-green; (iii)
    touches the identical honesty surface as the rejects."""
    if not isinstance(record.get("files_created"), list) or not record["files_created"]:
        return None
    fake = _derive_nonexistent_paths(record, 1, salt="demoted")[0]
    mutated = dict(record)
    mutated["files_created"] = list(record["files_created"]) + [fake]
    return mutated, ""


# ======================================================================================
# DC-05 · claim-vs-skip divergence (MEDIUM fidelity — PROVISIONAL, see the note).
#
# GOAL.md criterion 3's record-native slice: a green verdict resting on skips / zero executed
# tests — ``quality_gates.all_passed=True`` while the guarded suite was skipped, not run. The strong
# sys.modules / skip-guard DC-05 is SOURCE-native and already owned by ``seeded_code``
# ``R-DC05-sysmod/skipguard``; this is the complementary claim-vs-skip slice.
#
# FIDELITY FINDING (micro-spike 2026-07-23, REAL guardkit bridge — CONFIRMED INERT): the bundle's
# ``quality_gates`` / ``tests`` is RECOMPUTED by gather_evidence from the live pinned pytest run, NOT
# replayed from the record's ``quality_gates`` — so a record-only quality_gates mutation is
# overwritten and the mutated bundle comes out BYTE-IDENTICAL to the control (spike: control ==
# mutated, both ``gathering_status=complete``, ``tests_run=None`` from the real run). DC-05 is
# therefore NOT record-native as a quality_gates edit; it ships **weight-0 by default** and, were it
# enabled, the evidence-divergence guard would REFUSE it as ``evidence_invariant_injection`` (a LOUD
# result — no mislabelled row can ever bank). The strong DC-05 stays SOURCE-native (``seeded_code``
# ``R-DC05-sysmod/skipguard``), exactly as the design anticipated. Recipe retained (guard-protected)
# to document the attempt + the finding, never to generate rows.
# ======================================================================================
def _rec_dc05_skipmask(record: dict[str, Any]) -> Optional[tuple[dict[str, Any], str]]:
    """Reject (PROVISIONAL): a green ``all_passed`` resting on ZERO executed tests — the claim-vs-skip
    divergence. Sets ``quality_gates`` to ``all_passed=True`` with ``tests_passed/tests_passing=0``
    and ``tests_failed=0`` (the suite was skipped, not run). Anchor-absent ⇒ None when the record has
    no green ``quality_gates`` with real executed tests to mask."""
    qg = record.get("quality_gates")
    if not isinstance(qg, dict) or not qg.get("all_passed"):
        return None
    ran = qg.get("tests_passing") or qg.get("tests_passed") or 0
    if not isinstance(ran, int) or ran <= 0:
        return None  # nothing executed to mask — no claim-vs-skip divergence to plant
    new_qg = dict(qg)
    new_qg.update({"all_passed": True, "tests_passed": 0, "tests_passing": 0, "tests_failed": 0})
    mutated = dict(record)
    mutated["quality_gates"] = new_qg
    locus = (
        "bundle.quality_gates.all_passed=True with bundle.tests showing zero executed tests — a "
        "green verdict resting on skips (claim-vs-skip divergence; the guarded suite was not run)"
    )
    return mutated, locus


# --------------------------------------------------------------------------------------
# The registry. Reject/control pairs per class. Namespace ``R-RECORD-*`` — DISJOINT from the frozen
# ``recipes.RECIPES`` (code) and ``R-BUNDLE-*`` (direct bundle) so the family key falls through to
# ``generation_mode`` (== "seeded_code" for record rows). Ordered deterministically.
# --------------------------------------------------------------------------------------
RECORD_RECIPES: dict[str, RecordRecipe] = {
    r.id: r
    for r in (
        # DC-12 rejects (flagship) + matched controls.
        RecordRecipe(
            id="R-RECORD-DC12-missingfiles", dc_class="DC-12", verdict="reject",
            shape="plan declared files never created (plan_audit missing_files vs green tests)",
            expected_signature="plan_audit.status=violation severity=high missing_files!=[]; "
            "quality_gates.plan_audit_passed=False; gathering_status=partial_gate_abort",
            plan=_rec_dc12_missingfiles,
        ),
        RecordRecipe(
            id="R-RECORD-DC12-extramod", dc_class="DC-12", verdict="reject",
            shape="scope-creep beyond the approved plan (extra_modifications + loc variance)",
            expected_signature="plan_audit.status=violation severity=null violations>0 "
            "extra_modifications!=[]; plan_audit_passed=False; partial_gate_abort",
            plan=_rec_dc12_extramod,
        ),
        RecordRecipe(
            id="R-RECORD-DC12-gateorder", dc_class="DC-12", verdict="reject",
            shape="a gate sequenced before its test exists / unverifiable AC (PLAN §3 canonical)",
            expected_signature="plan_audit.message names the ordering finding; severity=high; "
            "plan_audit_passed=False; partial_gate_abort",
            plan=_rec_dc12_gateorder,
        ),
        RecordRecipe(
            id="R-RECORD-DC12-control-clean", dc_class=None, verdict="approve",
            shape="plan honored; plan_audit populated + PASSING (anti-shortcut control)",
            expected_signature="plan_audit.status=passed violations=0; gates green; complete",
            plan=_rec_dc12_control_clean,
        ),
        RecordRecipe(
            id="R-RECORD-DC12-control-lowvar", dc_class=None, verdict="approve",
            shape="honest green with in-tolerance LOC drift (mandatory ugly-green)",
            expected_signature="plan_audit.status=passed loc_variance_pct small; complete",
            plan=_rec_dc12_control_lowvar,
        ),
        # DC-14 rejects + the triple-duty demoted control.
        RecordRecipe(
            id="R-RECORD-DC14-promisefile", dc_class="DC-14", verdict="reject",
            shape="completion promise claims an implementation_file not on disk (FEAT-6CC5)",
            expected_signature="honesty.discrepancies[promise_file_existence] must_fix; "
            "verified=False; partial_honesty_abort; promise status=complete",
            plan=_rec_dc14_promisefile,
        ),
        RecordRecipe(
            id="R-RECORD-DC14-multifile", dc_class="DC-14", verdict="reject",
            shape="narrative claims a batch (>=2) of files never written",
            expected_signature="honesty.discrepancies[file_existence]x>=2 must_fix; verified=False; "
            "partial_honesty_abort",
            plan=_rec_dc14_multifile,
        ),
        RecordRecipe(
            id="R-RECORD-DC14-control-demoted", dc_class=None, verdict="approve",
            shape="exactly ONE nonexistent file — Layer-2-demoted should_fix (anti-shortcut + "
            "mandatory ugly-green; the most valuable calibration row)",
            expected_signature="single file_existence demoted to should_fix; advisory_issues "
            "populated; verified=False; gathering_status=complete; approve-legitimate",
            plan=_rec_dc14_control_demoted,
        ),
        # DC-05 claim-vs-skip (medium fidelity, provisional — spike-gated, weight-0 default).
        RecordRecipe(
            id="R-RECORD-DC05-skipmask", dc_class="DC-05", verdict="reject",
            shape="green all_passed resting on zero executed / skipped tests (claim-vs-skip)",
            expected_signature="quality_gates.all_passed=True with bundle.tests zero executed; "
            "PROVISIONAL — may be recomputed by the live run (see module note)",
            plan=_rec_dc05_skipmask,
        ),
    )
}

# Registry self-consistency (fail LOUD at import if a recipe is mis-wired).
for _rid, _r in RECORD_RECIPES.items():
    if _r.verdict not in ("reject", "approve"):
        raise RecordRecipeError(f"{_rid}: bad verdict {_r.verdict!r}")
    if _r.verdict == "reject" and _r.dc_class not in PHASE1_DC_CLASSES:
        raise RecordRecipeError(
            f"{_rid}: reject dc_class {_r.dc_class!r} not in Phase-1 admissible {sorted(PHASE1_DC_CLASSES)}"
        )
    if _r.verdict == "approve" and _r.dc_class is not None:
        raise RecordRecipeError(f"{_rid}: approve control must have dc_class=None, got {_r.dc_class!r}")
    if not _rid.startswith("R-RECORD-"):
        raise RecordRecipeError(f"{_rid}: record recipe id must be in the R-RECORD-* namespace")


# --------------------------------------------------------------------------------------
# The apply entrypoint (pure). Loud on an unknown recipe; None-passthrough on anchor-absent.
# --------------------------------------------------------------------------------------
def apply_record_recipe(
    record: dict[str, Any], recipe_id: str
) -> Optional[RecordInjectionResult]:
    """Apply ``recipe_id`` to a parsed ``task_work_results`` record. Returns a
    :class:`RecordInjectionResult` (mutated record + fixed label), or ``None`` when the recipe's
    anchor is absent (the caller raises that as a LOUD ``record_anchor_skipped`` result — never a
    silent no-op). Pure: no I/O, no worktree, no model."""
    if recipe_id not in RECORD_RECIPES:
        raise KeyError(f"unknown record recipe {recipe_id!r}; known: {sorted(RECORD_RECIPES)}")
    recipe = RECORD_RECIPES[recipe_id]
    planned = recipe.plan(record)
    if planned is None:
        return None
    mutated_record, locus = planned
    finding = (
        {"class": recipe.dc_class, "locus": locus}
        if recipe.verdict == "reject" and recipe.dc_class
        else None
    )
    return RecordInjectionResult(
        recipe_id=recipe.id,
        dc_class=recipe.dc_class,
        verdict=recipe.verdict,
        mutated_record=mutated_record,
        finding=finding,
    )
