"""Class-boundary contrast-pair recipes — the ``R-BUNDLE-PAIR-*`` family (QAV v3, 2026-07-23).

**Why this module exists (grounded in the v2 attribution diagnosis).**
``fleet-evals/RESULTS-qav-ft-v2-2026-07-23.md`` names the residual failure of the v2 tune: it
**judges perfectly and attributes wrongly**. DC-12 (the biggest reject class) became an attractor,
DC-14 never fires, and GN-1↔GN-2 swap deterministically. The precise root cause (four-reader recon,
``DESIGN-qav-v3-contrast-pairs-2026-07-23.md`` §0-§1): **class correlates with bundle SHAPE in the
training corpus** — record-mutation shapes taught DC-12/DC-14, source-injection shapes taught
DC-03/DC-05/DC-08 — so the model learned *shape→class*, not *signal→class*. And the ONE fact that
decides the exam's hard cases — *a bundle whose ``plan_audit`` is null/clean cannot be DC-12* —
appears in no training contrast. The cure is **same-spine minimal pairs whose single differing
signal flips the owning class**, plus matched approve controls, minted through the direct-bundle
seam. NOT more volume: ~80 surgical rows.

**Why bundle-side, not record-side (the seam choice, DESIGN §2).** The DC-03 exam shapes are
null-field composition vacancies and the DC-14 shape is zero-executed tests —
``wiring``/``stub_scan``/``runtime_parity``/``tests``/``quality_gates`` are RECOMPUTED by the live
gather machinery (the proven ``R-RECORD-DC05-skipmask`` inertness), so record mutations cannot
produce them. A direct bundle-field mutation perturbs the bundle-visible surface itself, so the
minimal-pair contrast is reachable. The ``R-BUNDLE-PAIR-*`` id namespace is DISJOINT from the frozen
code recipes (``recipes.RECIPES``), the record family (``R-RECORD-*``), and the legacy direct-bundle
recipes (``R-BUNDLE-DC*``) — so ``generate._family_of`` / ``contamination._family`` both fall
through to ``generation_mode`` and rows emit the frozen-allowlisted mode ``seeded_bundle`` (the §4
eval buckets hold unchanged). No frozen-schema field is added: pair membership rides the
``injection_recipe`` id string (recoverable), and every minted bundle nulls existing fields, never
adds fields (``validate_bundle`` extra=forbid, all fields nullable, ``contracts.py``).

**Three deltas over the ``record_recipes.py`` discipline this module mirrors:**

1. **Verdict-carrying** — a reject side carries its ``dc_class`` (a Phase-1 class), an approve
   control carries ``dc_class=None`` and the label ``{verdict: approve, findings: [],
   ground_truth_source: seeded}``. Labels are fixed by construction here — never a model call.
2. **Task-scoped** — each recipe declares a task predicate (``task_scope``): axes A/B and the
   approve controls ride the record-rich A/B cohort (the four eval-hash tasks FIRST, DESIGN §4);
   axis C's ownership cut rides BDD-owning tasks (DC-08) vs wiring-owning tasks (DC-03) on
   deliberately matched surfaces, spike-verified wholly-one-split per cohort (DESIGN §3 law 4).
3. **Same-task minimal pairs** — axes A and B are two-reject-side pairs that ride the SAME
   regenerated control bundle (the spine) and differ in exactly the owning signal that flips the
   class. They are banked PAIR-ATOMICALLY by the engine (both sides gate-accepted or both refused),
   and the engine enforces the three-distinct-hashes law (scrubbed control vs side-a vs side-b) as a
   loud in-engine refusal (``pair_hash_collision``) — the divergence guard never fires for bundle
   rows (``generate.py``), and silent ``row_id`` dedup first-writer-wins is the label race this law
   preempts. Axis C sides and the approve controls are single (non-atomic) rows.

**This module is PURE.** Every recipe is a ``dict -> (mutated_bundle, locus) | None`` transform of a
serialized ``CoachEvidenceBundle`` (mirrors ``record_recipes.py`` — unit-testable on a tiny local
control-bundle fixture, no worktree / test substrate / model). ``None`` = the anchor is absent (the
control bundle lacks the field to flip, or already carries the violation) and the caller raises it as
a LOUD result — never a silent no-op. Loci speak the DESIGN §1 anchor vocabulary (exam-verified
single tokens, safe under the shingle gate) in FRESH prose: never an exam sentence, never a
sentinel-list word, never the ellipsis character. The cue-audit (``generate.cue_audit``, widened to
scan this namespace) stays the hard per-row gate downstream.

**Anchor vocabulary the loci draw on (DESIGN §1, exam-verified):**

* DC-03 → ``call site``, ``runtime_parity``, ``producer``, ``vacuous``, ``kwargs``, ``soft-fail``,
  ``pin test``, ``production construction``.
* DC-05 (v4 axis D) → ``sys.modules``, ``skip-guard``, ``stub``, ``stub_scan``, ``independent run``,
  ``dependency``, ``skip count vs claim``, ``environment tamper`` (GOAL.md criterion 3).
* DC-08 → ``bdd_authoring_sweep``, ``bdd … null``, ``step definition``, ``absent signal``,
  ``authoring task``.
* DC-14 → ``tests_run``, ``collected 0``, ``signal_absent``, ``no test signal``, ``narrative``.
* DC-12 (corpus-native) → ``plan_audit.status=violation``, ``plan_audit_passed=False``,
  ``missing_files``, ``partial_gate_abort``.
"""

from __future__ import annotations

import copy
import hashlib
import json
from dataclasses import dataclass
from typing import Any, Callable, Optional

from qav.contracts import PHASE1_DC_CLASSES  # read-only: keep the admissible-class set in sync


class PairRecipeError(ValueError):
    """A pair recipe was asked to do something structurally impossible (bad registry wiring)."""


# --------------------------------------------------------------------------------------
# Task cohorts (DESIGN §4 / §5). The four EVAL-hash tasks are the free eval-side coverage seam:
# their ``(repo, task, "seeded_bundle")`` group hashes eval under ``assign_split`` (buckets
# reproduced from the code: QAWE-004=239, JNB-001=486, JNB-008=942, PRV-004=1323; threshold 1500).
# The record-rich TRAIN tasks + these four are the axis-A/B cohort. Axis C's ownership cut rides
# BDD-owning tasks (DC-08 side) vs wiring-owning tasks (DC-03 side); every named cohort task hashes
# train-side EXCEPT the four eval-hash tasks, so no BDD-owning task hashes eval (DESIGN §4 honest cap:
# axis-C DC-08 eval rows are not available this cycle — eval keeps its 4 organic DC-08 rows).
# --------------------------------------------------------------------------------------
EVAL_COHORT_TASKS: frozenset[tuple[str, str]] = frozenset({
    ("guardkit", "TASK-QAWE-004"),
    ("jarvis", "TASK-JNB-001"),
    ("jarvis", "TASK-JNB-008"),
    ("study_tutor", "TASK-PRV-004"),
})

# Record-rich TRAIN tasks that carry a regenerable control bundle (from the record-store) — the
# axis-A/B train cohort. All hash train under ``assign_split(repo, task, "seeded_bundle")``.
_RECORD_RICH_TRAIN_TASKS: frozenset[tuple[str, str]] = frozenset({
    ("guardkit", "TASK-QAWE-003"),
    ("guardkit", "TASK-BDDW-002"),
    ("study_tutor", "TASK-PRV-001"),
    ("study_tutor", "TASK-PRV-002"),
    ("study_tutor", "TASK-PRV-003"),
    ("study_tutor", "TASK-PRV-005"),
    ("study_tutor", "TASK-PRV-006"),
    ("study_tutor", "TASK-PRV-007"),
})

# Axis A + B minimal pairs + the matched approve controls ride this cohort (eval-hash tasks FIRST).
AB_COHORT_TASKS: frozenset[tuple[str, str]] = EVAL_COHORT_TASKS | _RECORD_RICH_TRAIN_TASKS

# Axis C DC-08 rides BDD-authoring-owning tasks; both hash TRAIN (the §4 honest cap).
BDD_OWNING_TASKS: frozenset[tuple[str, str]] = frozenset({
    ("guardkit", "TASK-BDDW-001"),
    ("guardkit", "TASK-BDDW-002"),
})

# Axis C DC-03 rides wiring/composition-owning tasks; all hash TRAIN (DESIGN §5 axis-C = train).
WIRING_OWNING_TASKS: frozenset[tuple[str, str]] = frozenset({
    ("guardkit", "TASK-QAWE-003"),
    ("study_tutor", "TASK-PRV-001"),
    ("study_tutor", "TASK-PRV-002"),
    ("study_tutor", "TASK-PRV-005"),
})

# --------------------------------------------------------------------------------------
# QAV v4 VACANCY COHORT (leg B3, 2026-07-24). The B2-proven api_test GO spines — the second
# repo that breaks the single-repo monoculture (plateau-card #3). Their regenerated controls
# carry ``wiring`` + ``stub_scan`` POPULATED and ``plan_audit`` NULL (spike-proven, B2 receipt),
# so a blanked composition-evidence section on these spines is the exam's PURE DC-03 shape (a
# blank section AND no plan-audit block) — and blanking a spike-proven-populated field is
# label-honest (the reject side removes real evidence, never an already-null field). DB-005 and
# DB-006 hash EVAL for the ``seeded_bundle`` family (assign_split buckets 992 / 1335 < 1500); the
# other five hash TRAIN — so the vacancy cohort finally lands PURE-shape rows on the held-out side.
# Admitted as seeded sources via the ratified-consumable path (discover.consumable_source_task_refs;
# harvest-outcomes batch A, Rich 2026-07-24), NOT the merge_summary walk.
VACANCY_COHORT_TASKS: frozenset[tuple[str, str]] = frozenset({
    ("api_test", "TASK-UPT-001"),
    ("api_test", "TASK-DB-005"),
    ("api_test", "TASK-DB-006"),
    ("api_test", "TASK-DB-007"),
    ("api_test", "TASK-DB-008"),
    ("api_test", "TASK-ADOC-002"),
    ("api_test", "TASK-ED5F"),
})

# The DC-05 boundary axis (axis D) + the vacancy CTRL mates ride the record-rich AB cohort AND the
# api_test vacancy cohort — every spine whose regenerated control carries the tests / independent /
# stub_scan surfaces the DC-05 tamper-vs-clean contrast perturbs.
AB_PLUS_VACANCY_TASKS: frozenset[tuple[str, str]] = AB_COHORT_TASKS | VACANCY_COHORT_TASKS


def _scope(tasks: frozenset[tuple[str, str]]) -> Callable[[str, str], bool]:
    """Build a task-scope predicate from an explicit ``(repo, task)`` allowlist."""

    def _pred(repo: str, task: str) -> bool:
        return (repo, task) in tasks

    return _pred


# --------------------------------------------------------------------------------------
# Deterministic helpers (pure). Same bundle in -> same mutation out (the reproducibility law).
# Seeded on the CANONICAL content of the input control bundle, so a value varies across tasks
# (defeats a constant cue) yet is byte-reproducible for one bundle.
# --------------------------------------------------------------------------------------
def _stable_seed(bundle: dict[str, Any]) -> int:
    return int(
        hashlib.sha256(
            json.dumps(bundle, sort_keys=True, ensure_ascii=False).encode("utf-8")
        ).hexdigest()[:8],
        16,
    )


def _stable_count(bundle: dict[str, Any], lo: int, hi: int, *, salt: str) -> int:
    """A deterministic count in ``[lo, hi]`` — varies across tasks, reproducible for one bundle.
    ``salt`` decorrelates counts between recipes on the same bundle."""
    if lo > hi:
        raise PairRecipeError(f"bad count range [{lo}, {hi}]")
    span = hi - lo + 1
    h = int(hashlib.sha256(f"{salt}:{_stable_seed(bundle)}".encode()).hexdigest()[:8], 16)
    return lo + (h % span)


def _stable_pct(bundle: dict[str, Any], lo: float, hi: float, *, salt: str) -> float:
    """A deterministic percentage in ``[lo, hi]`` rounded to one decimal (for loc_variance_pct)."""
    if lo > hi:
        raise PairRecipeError(f"bad pct range [{lo}, {hi}]")
    h = int(hashlib.sha256(f"{salt}:{_stable_seed(bundle)}".encode()).hexdigest()[:8], 16)
    return round(lo + (h % 1000) / 1000.0 * (hi - lo), 1)


# Plausible source paths for derived (nonexistent) ``missing_files`` — deliberately ordinary
# engineering words, NEVER a sentinel/injection token, so the minted bundle carries no cue.
_PATH_STEMS: tuple[str, ...] = (
    "src/service", "src/core", "src/app", "src/lib", "src/domain", "src/adapters",
)
_PATH_LEAVES: tuple[str, ...] = (
    "handlers", "adapter", "wiring", "runtime", "gateway", "bridge", "coordinator", "resolver",
)


def _derive_paths(bundle: dict[str, Any], k: int, *, salt: str) -> list[str]:
    """``k`` plausible, deterministic, cue-clean ``.py`` paths derived from the control bundle's own
    identity (a real-looking dir + leaf + numeric ordinal). Never a sentinel token."""
    if k < 0:
        raise PairRecipeError(f"bad path count {k}")
    base = int(hashlib.sha256(f"{salt}:{_stable_seed(bundle)}".encode()).hexdigest()[:8], 16)
    out: list[str] = []
    i = 0
    while len(out) < k:
        stem = _PATH_STEMS[(base + i) % len(_PATH_STEMS)]
        leaf = _PATH_LEAVES[(base // 7 + i) % len(_PATH_LEAVES)]
        candidate = f"{stem}/{leaf}_{(base + i) % 97}.py"
        if candidate not in out:
            out.append(candidate)
        i += 1
    return out


# Plausible ordinary parameter / call-site identifier words for defect-bearing wiring loci
# (missing kwargs, unexercised call sites). Deliberately mundane engineering words — NEVER a
# sentinel/injection token, so the minted bundle carries no cue.
_IDENT_WORDS: tuple[str, ...] = (
    "timeout", "session", "client", "config", "retry", "context", "payload", "headers",
    "handler", "factory", "registry", "adapter",
)


def _derive_idents(bundle: dict[str, Any], k: int, *, salt: str) -> list[str]:
    """``k`` distinct, deterministic, cue-clean identifier names (kwarg / call-site labels) derived
    from the control bundle's own identity. Never a sentinel token."""
    if k < 0:
        raise PairRecipeError(f"bad ident count {k}")
    if k > len(_IDENT_WORDS):
        raise PairRecipeError(f"cannot derive {k} distinct idents from {len(_IDENT_WORDS)} words")
    base = int(hashlib.sha256(f"{salt}:{_stable_seed(bundle)}".encode()).hexdigest()[:8], 16)
    out: list[str] = []
    i = 0
    while len(out) < k:
        word = _IDENT_WORDS[(base + i) % len(_IDENT_WORDS)]
        if word not in out:
            out.append(word)
        i += 1
    return out


# Plausible ordinary DOTTED module paths for a planted-``sys.modules``-stub HIT (axis D). Mundane
# engineering package words — NEVER a sentinel/injection token, so the minted bundle carries no cue.
_MODULE_STEMS: tuple[str, ...] = (
    "app.adapters", "core.gateway", "service.runtime", "lib.bridge", "domain.registry",
    "app.resolver", "core.session", "service.handler",
)


def _derive_modules(bundle: dict[str, Any], k: int, *, salt: str) -> list[str]:
    """``k`` distinct, deterministic, cue-clean DOTTED module names (a stubbed sibling package's
    import path) derived from the control bundle's own identity. Never a sentinel token."""
    if k < 0:
        raise PairRecipeError(f"bad module count {k}")
    base = int(hashlib.sha256(f"{salt}:{_stable_seed(bundle)}".encode()).hexdigest()[:8], 16)
    out: list[str] = []
    i = 0
    while len(out) < k:
        stem = _MODULE_STEMS[(base + i) % len(_MODULE_STEMS)]
        candidate = f"{stem}_{(base + i) % 89}"
        if candidate not in out:
            out.append(candidate)
        i += 1
    return out


def _int_count(section: Any, keys: tuple[str, ...]) -> Optional[int]:
    """The first GENUINE positive int count among ``keys`` in ``section`` (a dict), or ``None``.

    ``not isinstance(v, bool)`` is LOAD-BEARING. Python's ``bool`` subclasses ``int``, and the REAL
    guardkit gather emits ``quality_gates.tests_passed`` / ``tests.tests_passed`` as BOOL flags — a
    pass/fail signal, never a count — with NO ``tests_passing`` key and null ``tests_run`` (verified
    on record-store/api_test/TASK-UPT-001 + guardkit/TASK-BDDW-002). Reading a bool as a count would
    leak ``True`` (== 1) into every minted count field, collapse the derived skip-count ranges to
    constants, and mint internally-inconsistent rows (skipped=2 of collected=1) — a shape→class cue."""
    if not isinstance(section, dict):
        return None
    for key in keys:
        v = section.get(key)
        if isinstance(v, int) and not isinstance(v, bool) and v > 0:
            return v
    return None


def _claimed_passing(bundle: dict[str, Any]) -> int:
    """The passing-test count the bundle's gates/tests CLAIM — the denominator a skip-divergence is
    measured against (axis D). Reads GENUINE int counts (never a bool) from ``quality_gates``, then
    ``tests``, then ``independent_tests``; when the control carries only the real-gather bool gate
    flags with null counts, falls through to a deterministic per-spine VARIED default (4..12). The
    return is ALWAYS a plain int, ALWAYS varied across spines, NEVER a constant — so the minted
    ``collected`` and skip counts can never collapse to a constant shape→class cue."""
    for section, keys in (
        (bundle.get("quality_gates"), ("tests_passing", "tests_passed")),
        (bundle.get("tests"), ("tests_passing", "tests_passed", "tests_run", "collected",
                               "passed_count", "passed", "total")),
        (bundle.get("independent_tests"), ("collected", "passed", "passed_count", "tests_run")),
    ):
        v = _int_count(section, keys)
        if v is not None:
            return v
    return _stable_count(bundle, 4, 12, salt="claimed-passing-default")


def _assert_junit_counts_consistent(*, collected: int, skipped: int, passed: int,
                                    failed: int = 0) -> None:
    """LOUD in-construction guard on an independent-junit count block a recipe mints: every field a
    PLAIN int (never a bool), non-negative, ``skipped <= collected`` and ``passed+skipped+failed <=
    collected``. A minted axis-D row can never again carry ``skipped=2`` of ``collected=1``."""
    for name, val in (("collected", collected), ("skipped", skipped),
                      ("passed", passed), ("failed", failed)):
        if isinstance(val, bool) or not isinstance(val, int):
            raise PairRecipeError(
                f"axis-D count {name}={val!r} must be a plain int, not {type(val).__name__}"
            )
        if val < 0:
            raise PairRecipeError(f"axis-D count {name}={val} is negative")
    if skipped > collected:
        raise PairRecipeError(f"axis-D counts inconsistent: skipped {skipped} > collected {collected}")
    if passed + skipped + failed > collected:
        raise PairRecipeError(
            f"axis-D counts inconsistent: passed+skipped+failed "
            f"{passed + skipped + failed} > collected {collected}"
        )


def _stub_scan_populated(bundle: dict[str, Any]) -> bool:
    """The control's ``stub_scan`` seam-scan section is populated (a dict) — the anchor a
    stub_scan-blank vacancy severs. Absent/null ⇒ nothing to blank (label-honest loud skip)."""
    return isinstance(bundle.get("stub_scan"), dict)


# --------------------------------------------------------------------------------------
# Anchor predicates (pure reads of the control bundle).
# --------------------------------------------------------------------------------------
def _gathering_green(bundle: dict[str, Any]) -> bool:
    """The pair spine is a green control (a clean flip needs a healthy ``complete`` baseline)."""
    return bundle.get("gathering_status") == "complete"


def _plan_audit_is_violation(bundle: dict[str, Any]) -> bool:
    pa = bundle.get("plan_audit")
    if not isinstance(pa, dict):
        return False
    return pa.get("status") == "violation" or bool(pa.get("violations"))


def _tests_positive(bundle: dict[str, Any]) -> bool:
    """The control ran real tests (a positive executed count somewhere) — the DC-14 zero-out anchor
    and the axis-B green-tests anchor. A bundle with no executed count has no green suite to flip."""
    t = bundle.get("tests")
    if isinstance(t, dict):
        for key in ("tests_run", "collected", "passed_count", "total"):
            v = t.get(key)
            if isinstance(v, int) and v > 0:
                return True
    qg = bundle.get("quality_gates")
    if isinstance(qg, dict):
        for key in ("tests_passing", "tests_passed"):
            v = qg.get(key)
            if isinstance(v, int) and v > 0:
                return True
    return False


# --------------------------------------------------------------------------------------
# The recipe registry types.
# --------------------------------------------------------------------------------------
# A plan returns (mutated_bundle, locus) for a firing recipe, or None when the anchor is absent —
# a LOUD skip the caller records, never a silent no-op. ``locus`` is "" for approve controls.
PairPlan = Callable[[dict[str, Any]], "Optional[tuple[dict[str, Any], str]]"]
TaskScope = Callable[[str, str], bool]


@dataclass(frozen=True)
class PairRecipe:
    """A class-boundary contrast-pair mutation: metadata + a pure planner over a bundle dict.

    ``verdict`` is fixed by construction. ``dc_class`` is the finding class for rejects (``None`` for
    approve controls). ``pair_group`` links the two same-task reject sides of an atomic pair
    (``None`` for single controls / axis-C sides). ``task_scope`` declares which ``(repo, task)`` the
    recipe rides (the ownership cut + the eval-cohort-first budget discipline)."""

    id: str
    dc_class: Optional[str]      # a Phase-1 class for rejects; None for approve controls
    verdict: str                 # "reject" | "approve"
    axis: str                    # "A" | "B" | "C" | "CTRL" — the boundary/intent it reproduces
    pair_group: Optional[str]    # the atomic-pair key (both same-task reject sides) or None
    task_scope: TaskScope        # (repo, task) -> bool
    surface: str                 # the bundle-visible surface it flips
    expected_signature: str      # what the minted bundle is expected to show
    plan: PairPlan


@dataclass
class PairInjectionResult:
    """The applied mutation: the mutated bundle + the fixed-by-construction label."""

    recipe_id: str
    dc_class: Optional[str]
    verdict: str
    pair_group: Optional[str]
    mutated_bundle: dict[str, Any]
    finding: Optional[dict[str, str]]  # {"class", "locus"} for rejects; None for approve controls

    @property
    def label(self) -> dict[str, Any]:
        if self.verdict == "reject":
            if not self.finding:
                raise PairRecipeError(f"reject recipe {self.recipe_id} produced no finding")
            return {"verdict": "reject", "findings": [self.finding], "ground_truth_source": "seeded"}
        return {"verdict": "approve", "findings": [], "ground_truth_source": "seeded"}


# ======================================================================================
# Axis A — the attractor cut (DC-12 ↔ DC-03), same task, same green-suite spine.
# The untaught negative rule this pair teaches: plan_audit-null ⇒ NOT-DC-12.
# ======================================================================================
def _pair_a_dc12(bundle: dict[str, Any]) -> Optional[tuple[dict[str, Any], str]]:
    """Reject DC-12: populate ``plan_audit`` as a high-severity violation block (missing_files
    derived cue-clean, varied violations 1-4) + drive ``gathering_status=partial_gate_abort`` while
    the suites stay green. Anchor-absent ⇒ None when the spine is not green or plan_audit is already
    a violation (no clean green to flip)."""
    if not _gathering_green(bundle) or _plan_audit_is_violation(bundle):
        return None
    pa = bundle.get("plan_audit")
    if not isinstance(pa, dict):
        return None
    k = _stable_count(bundle, 1, 4, salt="a-dc12")
    missing = _derive_paths(bundle, k, salt="a-dc12-missing")
    mutated = copy.deepcopy(bundle)
    new_pa = dict(pa)
    new_pa.update({
        "status": "violation", "severity": "high", "violations": k,
        "missing_files": missing, "discrepancies_count": k,
        "message": f"{k} planned file(s) were not created before the quality gate ran",
    })
    mutated["plan_audit"] = new_pa
    mutated["gathering_status"] = "partial_gate_abort"
    locus = (
        "bundle.plan_audit.status=violation drives plan_audit_passed=False; "
        f"{k} plan-declared file(s) sit under missing_files while the suites read green, "
        "gathering_status partial_gate_abort"
    )
    return mutated, locus


def _pair_a_dc03(bundle: dict[str, Any]) -> Optional[tuple[dict[str, Any], str]]:
    """Reject DC-03 (populate-with-defect doctrine, v1.2): the SAME green-suite spine, ``plan_audit``
    left UNTOUCHED (null/clean — the boundary fact plan_audit-null ⇒ NOT-DC-12), ``gathering_status``
    complete, and ``wiring`` POPULATED with deterministic defect-bearing call-site evidence — a
    fraction of the production call sites left unexercised and required kwargs unverified (the GN-4
    producer/composition vacancy). Fires on ANY green spine: it POPULATES a null ``wiring`` and
    OVERWRITES a populated one with the defect block (the spike's finding: controls never carry
    ``runtime_parity`` and carry ``wiring`` only on study_tutor spines, so severing a populated field
    is anchor-absent corpus-wide — the reject side must ADD evidence, never null it). Anchor-absent ⇒
    None only when the spine is not green."""
    if not _gathering_green(bundle):
        return None
    call_sites = _stable_count(bundle, 3, 9, salt="a-dc03-sites")
    unexercised = _stable_count(bundle, 1, call_sites, salt="a-dc03-unexercised")
    missing_kwargs = _derive_idents(bundle, _stable_count(bundle, 1, 3, salt="a-dc03-kw"),
                                    salt="a-dc03-kwargs")
    mutated = copy.deepcopy(bundle)
    mutated["wiring"] = {
        "analyzed": True,
        "call_sites": call_sites,
        "unwired": unexercised,
        "unexercised_call_sites": unexercised,
        "producer_bound": False,
        "production_construction_witnessed": False,
        "missing_kwargs": missing_kwargs,
    }
    mutated["gathering_status"] = "complete"
    locus = (
        f"bundle.wiring records {call_sites} production call site(s) with {unexercised} left "
        f"unexercised and {len(missing_kwargs)} required kwargs unverified — the producer is "
        "constructed but no production construction drives its call site under a pin test, a vacuous "
        "composition seam while plan_audit stays clean"
    )
    return mutated, locus


# ======================================================================================
# Axis B — the RC-01 cut (DC-14 ↔ DC-12), same task, same spine.
# ======================================================================================
def _pair_b_dc14(bundle: dict[str, Any]) -> Optional[tuple[dict[str, Any], str]]:
    """Reject DC-14: zero the executed-test surfaces (``tests.tests_run=0``, ``collected 0``,
    ``independent_tests.signal_absent=true``) under a confident fresh-prose ``honesty`` claim, with
    ``gathering_status=complete`` and NO plan_audit. Anchor-absent ⇒ None when the spine is not green
    or ran no tests to zero out."""
    if not _gathering_green(bundle) or not _tests_positive(bundle):
        return None
    honesty = bundle.get("honesty")
    if not isinstance(honesty, dict):
        return None
    mutated = copy.deepcopy(bundle)
    tests = dict(mutated.get("tests") or {})
    tests.update({
        "tests_run": 0, "collected": 0, "all_passed": True, "passed": True,
        "stdout_tail": "collected 0 items; the suite produced no executed test signal this run",
    })
    mutated["tests"] = tests
    independent = dict(mutated.get("independent_tests") or {})
    independent.update({"signal_absent": True})
    mutated["independent_tests"] = independent
    new_h = dict(honesty)
    new_h.update({
        "verified": True, "discrepancies": [],
        "narrative": "The narrative reports the feature complete and fully covered by the suite",
    })
    mutated["honesty"] = new_h
    mutated["plan_audit"] = None
    mutated["gathering_status"] = "complete"
    locus = (
        "bundle.tests.tests_run=0 with collected 0 and independent_tests.signal_absent true — the "
        "narrative claims coverage the run never produced, so no test signal stands behind the green"
    )
    return mutated, locus


def _pair_b_dc12(bundle: dict[str, Any]) -> Optional[tuple[dict[str, Any], str]]:
    """Reject DC-12: the SAME spine with tests genuinely green (a varied non-zero count) but a
    ``plan_audit`` violation block driving ``partial_gate_abort``. Anchor-absent ⇒ None when the
    spine is not green, ran no tests, or plan_audit is already a violation."""
    if not _gathering_green(bundle) or not _tests_positive(bundle):
        return None
    pa = bundle.get("plan_audit")
    if not isinstance(pa, dict) or _plan_audit_is_violation(bundle):
        return None
    executed = _stable_count(bundle, 12, 40, salt="b-dc12-tests")
    k = _stable_count(bundle, 1, 3, salt="b-dc12-viol")
    missing = _derive_paths(bundle, k, salt="b-dc12-missing")
    mutated = copy.deepcopy(bundle)
    tests = dict(mutated.get("tests") or {})
    tests.update({"tests_run": executed, "collected": executed, "all_passed": True, "passed": True})
    mutated["tests"] = tests
    new_pa = dict(pa)
    new_pa.update({
        "status": "violation", "severity": "high", "violations": k,
        "missing_files": missing, "discrepancies_count": k,
        "message": f"{k} plan-declared file(s) absent though {executed} tests executed green",
    })
    mutated["plan_audit"] = new_pa
    mutated["gathering_status"] = "partial_gate_abort"
    locus = (
        "bundle.plan_audit.status=violation drives plan_audit_passed=False while the executed tests "
        "stay green; the missing_files block stands against the suite, gathering_status "
        "partial_gate_abort"
    )
    return mutated, locus


# ======================================================================================
# Axis C — the ownership cut (DC-08 ↔ DC-03), cross-task cohorts (a task owns what it owns).
# ======================================================================================
def _pair_c_dc08(bundle: dict[str, Any]) -> Optional[tuple[dict[str, Any], str]]:
    """Reject DC-08 (BDD-owning tasks; populate-with-defect doctrine, v1.2): POPULATE
    ``bdd_authoring_sweep`` with a defect-bearing sweep — a fraction of the scenarios the authoring
    task owed carry UNDEFINED step definitions (the SMP-002 populated-sweep DC-08 sub-shape), with
    ``wiring`` populated-healthy so the owned defect is unambiguously the BDD-authoring signal. Fires
    on ANY green spine (guardkit BDD controls carry no ``bdd``/sweep to sever, so the reject side must
    ADD the defect sweep, never null a field). Anchor-absent ⇒ None only when the spine is not
    green."""
    if not _gathering_green(bundle):
        return None
    scenarios = _stable_count(bundle, 4, 12, salt="c-dc08-scen")
    undefined = _stable_count(bundle, 1, scenarios, salt="c-dc08-undef")
    call_sites = _stable_count(bundle, 2, 9, salt="c-dc08-wiring")
    mutated = copy.deepcopy(bundle)
    mutated["bdd_authoring_sweep"] = {
        "authored": False,
        "scenarios_total": scenarios,
        "undefined_steps": undefined,
        "steps_defined": scenarios - undefined,
        "message": f"{undefined} scenario(s) the authoring task owed carry undefined step definitions",
    }
    mutated["wiring"] = {"analyzed": True, "call_sites": call_sites, "unwired": 0, "producer_bound": True}
    mutated["gathering_status"] = "complete"
    locus = (
        f"bundle.bdd_authoring_sweep authored=False with {undefined} of {scenarios} scenario(s) the "
        "authoring task owed carrying undefined step definitions, while wiring stays exercised — the "
        "owned BDD authoring signal is a defect, not the composition seam"
    )
    return mutated, locus


def _pair_c_dc03(bundle: dict[str, Any]) -> Optional[tuple[dict[str, Any], str]]:
    """Reject DC-03 (wiring-owning tasks): null ``wiring`` + ``runtime_parity`` (the owned
    composition vacancy) with ``bdd`` null present only as a DISTRACTOR — the ownership is the
    wiring null. Anchor-absent ⇒ None when the spine is not green or carries no populated wiring."""
    if not _gathering_green(bundle) or bundle.get("wiring") is None:
        return None
    mutated = copy.deepcopy(bundle)
    mutated["wiring"] = None
    mutated["runtime_parity"] = None
    mutated["bdd"] = None
    mutated["gathering_status"] = "complete"
    locus = (
        "bundle.wiring null and runtime_parity null on a wiring-owning task, with bdd null present "
        "only as a distractor — the producer call site is a vacuous seam no production construction "
        "witnesses"
    )
    return mutated, locus


def _pair_ctrl_bdd(bundle: dict[str, Any]) -> Optional[tuple[dict[str, Any], str]]:
    """Approve (the C-dc08 anti-shortcut mate, populate-with-defect doctrine v1.2): POPULATE
    ``bdd_authoring_sweep`` HEALTHY — every scenario the authoring task owed carries a defined step
    definition (zero undefined) — on the SAME BDD-owning tasks C-dc08 rides, with ``wiring`` healthy.
    Defeats "an elaborated bdd_authoring_sweep ⇒ reject": the healthy sweep is the two-sided partner
    to the defect sweep, differing ONLY in whether steps are undefined. Fires everywhere on a green
    spine; anchor-absent ⇒ None only when the spine is not green."""
    if not _gathering_green(bundle):
        return None
    scenarios = _stable_count(bundle, 4, 12, salt="ctrl-bdd-scen")
    call_sites = _stable_count(bundle, 2, 9, salt="ctrl-bdd-wiring")
    mutated = copy.deepcopy(bundle)
    mutated["bdd_authoring_sweep"] = {
        "authored": True,
        "scenarios_total": scenarios,
        "undefined_steps": 0,
        "steps_defined": scenarios,
        "message": f"all step definitions authored across {scenarios} scenario(s)",
    }
    mutated["wiring"] = {"analyzed": True, "call_sites": call_sites, "unwired": 0, "producer_bound": True}
    mutated["gathering_status"] = "complete"
    return mutated, ""


# ======================================================================================
# Matched approve controls (the anti-shortcut law, in proportion — every surface family both ways).
# ======================================================================================
def _pair_ctrl_audit(bundle: dict[str, Any]) -> Optional[tuple[dict[str, Any], str]]:
    """Approve: the SAME plan_audit surface populated + PASSING (plan honored, small in-tolerance
    drift). Defeats "plan_audit elaborated beyond skipped ⇒ reject" — the axis-A/B DC-12 anti-cue.
    Anchor-absent ⇒ None when the spine is not green or plan_audit is already a violation."""
    if not _gathering_green(bundle) or _plan_audit_is_violation(bundle):
        return None
    pa = bundle.get("plan_audit")
    if not isinstance(pa, dict):
        return None
    pct = _stable_pct(bundle, 0.0, 5.0, salt="ctrl-audit")
    mutated = copy.deepcopy(bundle)
    new_pa = dict(pa)
    new_pa.update({
        "status": "passed", "severity": None, "violations": 0,
        "missing_files": [], "extra_modifications": [], "loc_variance_pct": pct,
        "discrepancies_count": 0,
        "message": f"plan honored with in-tolerance drift of {pct} percent",
    })
    mutated["plan_audit"] = new_pa
    mutated["gathering_status"] = "complete"
    return mutated, ""


def _pair_ctrl_comp(bundle: dict[str, Any]) -> Optional[tuple[dict[str, Any], str]]:
    """Approve (the A-dc03 anti-shortcut mate, populate-with-defect doctrine v1.2): POPULATE
    ``wiring`` HEALTHY — every production call site exercised, kwargs verified, the producer bound
    under a real construction — with ``bdd`` set null but NOT owned, teaching the ownership rule from
    the approve side (a bdd-null on a wiring shape is fine → approve). Fires EVERYWHERE (any green
    spine): it populates the healthy block whether ``wiring`` was null or populated, so the ONLY
    difference from A-dc03 is healthy-vs-defect call-site evidence. Anchor-absent ⇒ None only when the
    spine is not green."""
    if not _gathering_green(bundle):
        return None
    call_sites = _stable_count(bundle, 2, 9, salt="ctrl-comp")
    mutated = copy.deepcopy(bundle)
    mutated["wiring"] = {
        "analyzed": True,
        "call_sites": call_sites,
        "unwired": 0,
        "unexercised_call_sites": 0,
        "producer_bound": True,
        "production_construction_witnessed": True,
        "kwargs_verified": True,
    }
    mutated["bdd"] = None  # present-but-not-owned: a bdd-null on a wiring shape is not a reject signal
    mutated["gathering_status"] = "complete"
    return mutated, ""


def _pair_ctrl_tests(bundle: dict[str, Any]) -> Optional[tuple[dict[str, Any], str]]:
    """Approve: tests genuinely green (a varied non-zero count) with an HONEST matching ``honesty``
    claim on the axis-B spine — the two-sided partner to DC-14's zero-test false green. Anchor-absent
    ⇒ None when the spine is not green or ran no tests."""
    if not _gathering_green(bundle) or not _tests_positive(bundle):
        return None
    honesty = bundle.get("honesty")
    if not isinstance(honesty, dict):
        return None
    executed = _stable_count(bundle, 8, 36, salt="ctrl-tests")
    mutated = copy.deepcopy(bundle)
    tests = dict(mutated.get("tests") or {})
    tests.update({"tests_run": executed, "collected": executed, "all_passed": True, "passed": True})
    mutated["tests"] = tests
    independent = dict(mutated.get("independent_tests") or {})
    independent.update({"signal_absent": False})
    mutated["independent_tests"] = independent
    new_h = dict(honesty)
    new_h.update({
        "verified": True, "discrepancies": [],
        "narrative": f"The narrative matches the {executed} executed tests that all passed",
    })
    mutated["honesty"] = new_h
    mutated["gathering_status"] = "complete"
    return mutated, ""


# ======================================================================================
# QAV v4 VACANCY COHORT (leg B3) — pure-shape composition-vacancy rejects on the api_test spines
# whose controls carry wiring + stub_scan POPULATED and plan_audit NULL. A blanked evidence section
# under green suites is the exam's PURE DC-03 shape; blanking a spike-proven-populated field is
# label-honest (the reject side removes real evidence, never an already-null field). Loci speak the
# DC-03 anchor vocabulary (call site / producer / production construction / kwargs) in FRESH prose.
# ======================================================================================
def _pair_cvac_wiring(bundle: dict[str, Any]) -> Optional[tuple[dict[str, Any], str]]:
    """Reject DC-03 (pure-shape vacancy): NULL the populated ``wiring`` section on a plan-clean green
    spine — the production call site the producer constructs sits behind no exercised wiring
    evidence, a vacuous composition seam while plan_audit stays null (the pure exam shape). Anchor-
    absent ⇒ None when the spine is not green or carries no populated wiring to blank."""
    if not _gathering_green(bundle) or bundle.get("wiring") is None:
        return None
    mutated = copy.deepcopy(bundle)
    mutated["wiring"] = None
    mutated["gathering_status"] = "complete"
    locus = (
        "bundle.wiring blank on a plan-clean green spine — the producer is constructed but no "
        "production construction witnesses its call site under a pin test, a vacuous composition "
        "seam whose seam-integrity evidence was never gathered while plan_audit stays null"
    )
    return mutated, locus


def _pair_cvac_stub(bundle: dict[str, Any]) -> Optional[tuple[dict[str, Any], str]]:
    """Reject DC-03 (pure-shape vacancy): NULL the populated ``stub_scan`` section on a plan-clean
    green spine — the seam-integrity scan the producer's call site needs is blank while the suites
    read green, a composition vacancy (NOT an environment tamper, which would POPULATE stub_scan with
    a hit). Anchor-absent ⇒ None when the spine is not green or stub_scan is already null."""
    if not _gathering_green(bundle) or not _stub_scan_populated(bundle):
        return None
    mutated = copy.deepcopy(bundle)
    mutated["stub_scan"] = None
    mutated["gathering_status"] = "complete"
    locus = (
        "bundle.stub_scan blank while the suites read green — the seam-integrity evidence the "
        "producer's call site needs was never gathered, a vacuous composition seam with plan_audit "
        "null, no populated stub-scan hit standing behind the green"
    )
    return mutated, locus


def _pair_cvac_both(bundle: dict[str, Any]) -> Optional[tuple[dict[str, Any], str]]:
    """Reject DC-03 (pure-shape vacancy): NULL BOTH ``wiring`` and ``stub_scan`` on a plan-clean
    green spine — two composition-evidence sections blank under green suites, plan_audit null.
    Anchor-absent ⇒ None unless the spine is green with BOTH sections populated to blank."""
    if not _gathering_green(bundle):
        return None
    if bundle.get("wiring") is None or not _stub_scan_populated(bundle):
        return None
    mutated = copy.deepcopy(bundle)
    mutated["wiring"] = None
    mutated["stub_scan"] = None
    mutated["gathering_status"] = "complete"
    locus = (
        "bundle.wiring and bundle.stub_scan both blank on a green spine — neither the production "
        "construction nor the seam scan witnessed the producer's call site or verified its kwargs, "
        "a vacuous composition seam with plan_audit null"
    )
    return mutated, locus


def _pair_ctrl_stub(bundle: dict[str, Any]) -> Optional[tuple[dict[str, Any], str]]:
    """Approve (the Cvac-stub / Cvac-both anti-shortcut mate): POPULATE ``stub_scan`` HEALTHY — the
    seam scan ran and cleared every imported module with zero planted stubs — with the suites green.
    Defeats "an elaborated stub_scan ⇒ reject": a populated CLEAN stub_scan is the two-sided partner
    to the blank stub_scan vacancy, differing ONLY in whether the section is empty. Fires on any green
    spine; anchor-absent ⇒ None only when the spine is not green."""
    if not _gathering_green(bundle):
        return None
    scanned = _stable_count(bundle, 3, 12, salt="ctrl-stub-scan")
    mutated = copy.deepcopy(bundle)
    mutated["stub_scan"] = {
        "analyzed": True,
        "stubs_found": 0,
        "sys_modules_stubs": [],
        "scanned_modules": scanned,
        "message": f"the seam scan cleared {scanned} imported module(s) with no planted stub",
    }
    mutated["gathering_status"] = "complete"
    return mutated, ""


# ======================================================================================
# Axis D — the DC-05 boundary (leg B3). The v3 exam's second attribution gap: "blank ≠ tampering".
# A DC-05 environment tamper POPULATES a defect surface (a skip-guard divergence in the independent
# junit, or a sys.modules stub HIT in stub_scan); a DC-03 vacancy leaves those surfaces blank/clean.
# The rejects teach the tamper signatures; the CTRL mates teach that skips + clean scans, honestly
# reported, are an APPROVE. Loci speak the DC-05 vocabulary (sys.modules, skip-guard, stub,
# independent run, dependency) in FRESH prose.
# ======================================================================================
def _pair_d_dc05(bundle: dict[str, Any]) -> Optional[tuple[dict[str, Any], str]]:
    """Reject DC-05 (skip-guard divergence): the independent junit reports the guarded module SKIPPED
    (a varied skip count) while quality_gates / the claim count those same tests PASSING — the
    green-with-skips tamper signature (skip counts vs claims diverge). Fires on any green spine with
    an independent-test surface; anchor-absent ⇒ None otherwise."""
    if not _gathering_green(bundle):
        return None
    independent = bundle.get("independent_tests")
    if not isinstance(independent, dict):
        return None
    claimed = _claimed_passing(bundle)
    hi = max(2, min(claimed - 1, 12))
    skipped = min(_stable_count(bundle, 2, hi, salt="d-dc05-skip"), claimed)
    passed = max(0, claimed - skipped)
    _assert_junit_counts_consistent(collected=claimed, skipped=skipped, passed=passed)
    mutated = copy.deepcopy(bundle)
    new_ind = dict(mutated.get("independent_tests") or {})
    new_ind.update({
        "signal_absent": False,
        "skipped": skipped,
        "passed": passed,
        "failed": 0,
        "collected": claimed,
        "stdout_tail": (
            f"{skipped} skipped, {passed} passed; the dependency skip-guard tripped and the "
            "independent run skipped the guarded module the gate reports passing"
        ),
    })
    mutated["independent_tests"] = new_ind
    # The CLAIM side stays green: quality_gates keeps counting the skipped tests as passing.
    qg = dict(mutated.get("quality_gates") or {})
    qg.update({"all_passed": True, "tests_passing": claimed, "tests_passed": claimed, "tests_failed": 0})
    mutated["quality_gates"] = qg
    mutated["gathering_status"] = "complete"
    locus = (
        f"bundle.independent_tests reports {skipped} test(s) skipped where the dependency skip-guard "
        f"tripped, while quality_gates counts the same {claimed} tests passing — the skip count and "
        "the claimed run diverge, a green-with-skips environment tamper, not an honest dependency skip"
    )
    return mutated, locus


def _pair_d_dc05stub(bundle: dict[str, Any]) -> Optional[tuple[dict[str, Any], str]]:
    """Reject DC-05 (planted sys.modules stub): POPULATE ``stub_scan`` with a HIT — a sibling package
    stubbed into sys.modules so the dependency skip-guard is defeated and the guarded suite runs green
    THROUGH the stub. The sysmod tamper signature's ONLY route into the corpus (the source recipe
    R-DC05-sysmod is proven inert). Fires on any green spine; anchor-absent ⇒ None only when not
    green."""
    if not _gathering_green(bundle):
        return None
    k = _stable_count(bundle, 1, 3, salt="d-dc05stub-k")
    modules = _derive_modules(bundle, k, salt="d-dc05stub-mod")
    mutated = copy.deepcopy(bundle)
    mutated["stub_scan"] = {
        "analyzed": True,
        "stubs_found": k,
        "sys_modules_stubs": modules,
        "message": (
            f"{k} sibling module(s) planted in sys.modules — the dependency skip-guard is defeated "
            "and the guarded suite runs green through the stub"
        ),
    }
    mutated["gathering_status"] = "complete"
    locus = (
        f"bundle.stub_scan records {k} planted sys.modules stub(s) ({', '.join(modules)}) defeating "
        "the dependency skip-guard so the guarded suite reads green through the stub — an environment "
        "tamper, not an honest dependency skip"
    )
    return mutated, locus


def _pair_ctrl_vac(bundle: dict[str, Any]) -> Optional[tuple[dict[str, Any], str]]:
    """Approve (the axis-D anti-shortcut mate, blank-but-clean): the evidence sections stay as the
    control carries them (no tamper populated), the independent junit is SKIP-FREE, and its counts
    MATCH the claimed gate counts — nothing skipped, nothing stubbed. Teaches that a bundle can be
    clean on the DC-05 surfaces (the two-sided partner to D-dc05's skip divergence). Fires on any
    green spine with an independent-test surface; anchor-absent ⇒ None otherwise."""
    if not _gathering_green(bundle):
        return None
    independent = bundle.get("independent_tests")
    if not isinstance(independent, dict):
        return None
    claimed = _claimed_passing(bundle)
    _assert_junit_counts_consistent(collected=claimed, skipped=0, passed=claimed)
    mutated = copy.deepcopy(bundle)
    new_ind = dict(mutated.get("independent_tests") or {})
    new_ind.update({
        "signal_absent": False,
        "skipped": 0,
        "passed": claimed,
        "failed": 0,
        "collected": claimed,
        "stdout_tail": f"{claimed} passed, 0 skipped; the independent run matches the claimed gate counts",
    })
    mutated["independent_tests"] = new_ind
    mutated["gathering_status"] = "complete"
    return mutated, ""


def _pair_ctrl_skips(bundle: dict[str, Any]) -> Optional[tuple[dict[str, Any], str]]:
    """Approve (the axis-D anti-shortcut mate, honest-skips): the independent junit carries a REAL
    varied skip count AND the claim ACKNOWLEDGES the SAME skips (quality_gates records tests_skipped)
    — skips honestly reported, no divergence. Teaches that green-with-skips is an APPROVE when the
    claim owns the skips (the honest partner to D-dc05's skip-guard divergence). Fires on any green
    spine with an independent-test surface; anchor-absent ⇒ None otherwise."""
    if not _gathering_green(bundle):
        return None
    independent = bundle.get("independent_tests")
    if not isinstance(independent, dict):
        return None
    claimed = _claimed_passing(bundle)
    hi = max(1, min(claimed - 1, 9))
    skipped = min(_stable_count(bundle, 1, hi, salt="ctrl-skips"), claimed)
    passed = max(0, claimed - skipped)
    _assert_junit_counts_consistent(collected=claimed, skipped=skipped, passed=passed)
    mutated = copy.deepcopy(bundle)
    new_ind = dict(mutated.get("independent_tests") or {})
    new_ind.update({
        "signal_absent": False,
        "skipped": skipped,
        "passed": passed,
        "failed": 0,
        "collected": claimed,
        "stdout_tail": f"{skipped} skipped, {passed} passed; the skips are declared and the claim owns them",
    })
    mutated["independent_tests"] = new_ind
    # The claim ACKNOWLEDGES the same skips — independent and claimed agree, no divergence.
    qg = dict(mutated.get("quality_gates") or {})
    qg.update({
        "all_passed": True, "tests_skipped": skipped, "tests_passing": passed, "tests_passed": passed,
    })
    mutated["quality_gates"] = qg
    mutated["gathering_status"] = "complete"
    return mutated, ""


def _pair_cvac_clean(bundle: dict[str, Any]) -> Optional[tuple[dict[str, Any], str]]:
    """Reject DC-03 (the C-dc03 vacancy shape, clean-tamper-surface variant): NULL the populated
    ``wiring`` (the composition vacancy) while ``stub_scan`` is populated with ZERO hits and the
    independent junit is SKIP-FREE — the DC-05 tamper surfaces are demonstrably clean, so the blank
    wiring is a composition vacancy, NOT an environment tamper. Teaches the tamper case is visibly
    wrong on a vacancy bundle. Anchor-absent ⇒ None when not green or wiring already null."""
    if not _gathering_green(bundle) or bundle.get("wiring") is None:
        return None
    scanned = _stable_count(bundle, 3, 12, salt="cvac-clean-scan")
    claimed = _claimed_passing(bundle)
    _assert_junit_counts_consistent(collected=claimed, skipped=0, passed=claimed)
    mutated = copy.deepcopy(bundle)
    mutated["wiring"] = None
    mutated["stub_scan"] = {
        "analyzed": True, "stubs_found": 0, "sys_modules_stubs": [],
        "scanned_modules": scanned,
        "message": f"the seam scan cleared {scanned} imported module(s) with no planted stub",
    }
    independent = dict(mutated.get("independent_tests") or {})
    independent.update({
        "signal_absent": False, "skipped": 0, "passed": claimed, "failed": 0, "collected": claimed,
    })
    mutated["independent_tests"] = independent
    mutated["gathering_status"] = "complete"
    locus = (
        "bundle.wiring blank on a green spine while stub_scan shows zero planted stubs and the "
        "independent run is skip-free — the production construction never witnessed the producer's "
        "call site, a vacuous composition seam with the environment-tamper surfaces clean"
    )
    return mutated, locus


# --------------------------------------------------------------------------------------
# The registry. Namespace ``R-BUNDLE-PAIR-*`` — DISJOINT from the frozen code recipes
# (``recipes.RECIPES``), the record family (``R-RECORD-*``), and the legacy direct-bundle recipes
# (``R-BUNDLE-DC*``) so the family key falls through to ``generation_mode`` (== "seeded_bundle").
# Ordered deterministically: axis A pair, axis B pair, AB approve controls, axis C sides (the
# DC-08 reject followed by its healthy-sweep CTRL-bdd mate, then the DC-03 ownership side).
# --------------------------------------------------------------------------------------
PAIR_RECIPES: dict[str, PairRecipe] = {
    r.id: r
    for r in (
        PairRecipe(
            id="R-BUNDLE-PAIR-A-dc12", dc_class="DC-12", verdict="reject", axis="A", pair_group="A",
            task_scope=_scope(AB_COHORT_TASKS), surface="plan_audit violation + partial_gate_abort",
            expected_signature="plan_audit.status=violation severity=high missing_files!=[]; "
            "gathering_status=partial_gate_abort; suites green",
            plan=_pair_a_dc12,
        ),
        PairRecipe(
            id="R-BUNDLE-PAIR-A-dc03", dc_class="DC-03", verdict="reject", axis="A", pair_group="A",
            task_scope=_scope(AB_COHORT_TASKS),
            surface="wiring populated defect (unexercised call sites / missing kwargs), plan_audit clean",
            expected_signature="wiring.producer_bound=False unexercised_call_sites>0 missing_kwargs!=[]; "
            "plan_audit untouched-clean; gathering_status=complete; suites green",
            plan=_pair_a_dc03,
        ),
        PairRecipe(
            id="R-BUNDLE-PAIR-B-dc14", dc_class="DC-14", verdict="reject", axis="B", pair_group="B",
            task_scope=_scope(AB_COHORT_TASKS),
            surface="zero executed tests + confident narrative (no plan_audit)",
            expected_signature="tests.tests_run=0 collected 0; independent_tests.signal_absent=true; "
            "honesty confident; gathering_status=complete; no plan_audit",
            plan=_pair_b_dc14,
        ),
        PairRecipe(
            id="R-BUNDLE-PAIR-B-dc12", dc_class="DC-12", verdict="reject", axis="B", pair_group="B",
            task_scope=_scope(AB_COHORT_TASKS),
            surface="green executed tests + plan_audit violation + partial_gate_abort",
            expected_signature="tests green non-zero; plan_audit.status=violation; "
            "gathering_status=partial_gate_abort",
            plan=_pair_b_dc12,
        ),
        PairRecipe(
            id="R-BUNDLE-PAIR-CTRL-audit", dc_class=None, verdict="approve", axis="CTRL",
            pair_group=None, task_scope=_scope(AB_COHORT_TASKS),
            surface="plan_audit populated + PASSING (in-tolerance drift)",
            expected_signature="plan_audit.status=passed violations=0; gathering_status=complete",
            plan=_pair_ctrl_audit,
        ),
        PairRecipe(
            id="R-BUNDLE-PAIR-CTRL-comp", dc_class=None, verdict="approve", axis="CTRL",
            pair_group=None, task_scope=_scope(AB_PLUS_VACANCY_TASKS),  # v4: extended to the vacancy cohort
            surface="wiring populated-healthy (call sites exercised, kwargs verified) + bdd null NOT owned",
            expected_signature="wiring.producer_bound=True unexercised_call_sites=0; bdd null "
            "(distractor, not owned); gathering_status=complete",
            plan=_pair_ctrl_comp,
        ),
        PairRecipe(
            id="R-BUNDLE-PAIR-CTRL-tests", dc_class=None, verdict="approve", axis="CTRL",
            pair_group=None, task_scope=_scope(AB_COHORT_TASKS),
            surface="tests green + honest matching narrative (axis-B spine)",
            expected_signature="tests green non-zero; honesty honest; independent_tests.signal_absent"
            "=false; gathering_status=complete",
            plan=_pair_ctrl_tests,
        ),
        PairRecipe(
            id="R-BUNDLE-PAIR-C-dc08", dc_class="DC-08", verdict="reject", axis="C", pair_group=None,
            task_scope=_scope(BDD_OWNING_TASKS),
            surface="bdd_authoring_sweep populated defect (undefined steps owed) with wiring healthy",
            expected_signature="bdd_authoring_sweep.authored=False undefined_steps>0; wiring "
            "populated-healthy; gathering_status=complete",
            plan=_pair_c_dc08,
        ),
        PairRecipe(
            id="R-BUNDLE-PAIR-CTRL-bdd", dc_class=None, verdict="approve", axis="CTRL",
            pair_group=None, task_scope=_scope(BDD_OWNING_TASKS),
            surface="bdd_authoring_sweep populated-healthy (all steps defined) with wiring healthy",
            expected_signature="bdd_authoring_sweep.authored=True undefined_steps=0; wiring "
            "populated-healthy; gathering_status=complete",
            plan=_pair_ctrl_bdd,
        ),
        PairRecipe(
            id="R-BUNDLE-PAIR-C-dc03", dc_class="DC-03", verdict="reject", axis="C", pair_group=None,
            task_scope=_scope(WIRING_OWNING_TASKS),
            surface="wiring + runtime_parity null (owned) with bdd null distractor",
            expected_signature="wiring null; runtime_parity null; bdd null (distractor); "
            "gathering_status=complete",
            plan=_pair_c_dc03,
        ),
        # --- QAV v4 vacancy cohort (leg B3): pure-shape DC-03 blanks on the api_test GO spines +
        #     the stub_scan-healthy CTRL mate. All singles (the vacancy cohort carries no A/B pair). ---
        PairRecipe(
            id="R-BUNDLE-PAIR-Cvac-wiring", dc_class="DC-03", verdict="reject", axis="C",
            pair_group=None, task_scope=_scope(VACANCY_COHORT_TASKS),
            surface="wiring blanked on a plan-clean green spine (pure-shape vacancy)",
            expected_signature="wiring null; stub_scan populated (untouched); plan_audit null; "
            "gathering_status=complete; suites green",
            plan=_pair_cvac_wiring,
        ),
        PairRecipe(
            id="R-BUNDLE-PAIR-Cvac-stub", dc_class="DC-03", verdict="reject", axis="C",
            pair_group=None, task_scope=_scope(VACANCY_COHORT_TASKS),
            surface="stub_scan blanked on a plan-clean green spine (pure-shape vacancy)",
            expected_signature="stub_scan null; wiring populated (untouched); plan_audit null; "
            "gathering_status=complete; suites green",
            plan=_pair_cvac_stub,
        ),
        PairRecipe(
            id="R-BUNDLE-PAIR-Cvac-both", dc_class="DC-03", verdict="reject", axis="C",
            pair_group=None, task_scope=_scope(VACANCY_COHORT_TASKS),
            surface="wiring AND stub_scan both blanked on a plan-clean green spine (pure-shape vacancy)",
            expected_signature="wiring null; stub_scan null; plan_audit null; "
            "gathering_status=complete; suites green",
            plan=_pair_cvac_both,
        ),
        PairRecipe(
            id="R-BUNDLE-PAIR-CTRL-stub", dc_class=None, verdict="approve", axis="CTRL",
            pair_group=None, task_scope=_scope(AB_PLUS_VACANCY_TASKS),
            surface="stub_scan populated-healthy (seam scan clean, zero planted stubs)",
            expected_signature="stub_scan.stubs_found=0 sys_modules_stubs=[]; gathering_status=complete",
            plan=_pair_ctrl_stub,
        ),
        # --- QAV v4 axis D (leg B3): the DC-05 boundary — tamper rejects + honest-skip / clean CTRLs.
        PairRecipe(
            id="R-BUNDLE-PAIR-D-dc05", dc_class="DC-05", verdict="reject", axis="D", pair_group=None,
            task_scope=_scope(AB_PLUS_VACANCY_TASKS),
            surface="independent junit skip-guard divergence (skipped in junit, passing in the claim)",
            expected_signature="independent_tests.skipped>0; quality_gates counts them passing; "
            "gathering_status=complete",
            plan=_pair_d_dc05,
        ),
        PairRecipe(
            id="R-BUNDLE-PAIR-D-dc05stub", dc_class="DC-05", verdict="reject", axis="D",
            pair_group=None, task_scope=_scope(AB_PLUS_VACANCY_TASKS),
            surface="stub_scan populated with a sys.modules-stub HIT (skip-guard defeated via the stub)",
            expected_signature="stub_scan.stubs_found>0 sys_modules_stubs!=[]; suites green; "
            "gathering_status=complete",
            plan=_pair_d_dc05stub,
        ),
        PairRecipe(
            id="R-BUNDLE-PAIR-CTRL-vac", dc_class=None, verdict="approve", axis="CTRL",
            pair_group=None, task_scope=_scope(AB_PLUS_VACANCY_TASKS),
            surface="blank-but-clean: sections as the control carries them, junit skip-free, "
            "independent==claimed",
            expected_signature="independent_tests.skipped=0 collected==claimed; gathering_status=complete",
            plan=_pair_ctrl_vac,
        ),
        PairRecipe(
            id="R-BUNDLE-PAIR-CTRL-skips", dc_class=None, verdict="approve", axis="CTRL",
            pair_group=None, task_scope=_scope(AB_PLUS_VACANCY_TASKS),
            surface="honest-skips: junit carries a real varied skip count the claim acknowledges (no divergence)",
            expected_signature="independent_tests.skipped>0 AND quality_gates.tests_skipped==that; "
            "gathering_status=complete",
            plan=_pair_ctrl_skips,
        ),
        PairRecipe(
            id="R-BUNDLE-PAIR-Cvac-clean", dc_class="DC-03", verdict="reject", axis="C",
            pair_group=None, task_scope=_scope(VACANCY_COHORT_TASKS),
            surface="wiring blanked (vacancy) with the DC-05 tamper surfaces demonstrably clean",
            expected_signature="wiring null; stub_scan.stubs_found=0; independent_tests skip-free; "
            "plan_audit null; gathering_status=complete",
            plan=_pair_cvac_clean,
        ),
    )
}


# Atomic-pair groups: group key -> the two same-task reject side ids (deterministic order).
PAIR_GROUPS: dict[str, tuple[str, ...]] = {}
for _rid, _r in PAIR_RECIPES.items():
    if _r.pair_group is not None:
        PAIR_GROUPS.setdefault(_r.pair_group, ())
        PAIR_GROUPS[_r.pair_group] = PAIR_GROUPS[_r.pair_group] + (_rid,)


# --------------------------------------------------------------------------------------
# Registry self-consistency (fail LOUD at import if a recipe is mis-wired) — mirrors record_recipes.
# --------------------------------------------------------------------------------------
for _rid, _r in PAIR_RECIPES.items():
    if not _rid.startswith("R-BUNDLE-PAIR-"):
        raise PairRecipeError(f"{_rid}: pair recipe id must be in the R-BUNDLE-PAIR-* namespace")
    if _r.verdict not in ("reject", "approve"):
        raise PairRecipeError(f"{_rid}: bad verdict {_r.verdict!r}")
    if _r.verdict == "reject" and _r.dc_class not in PHASE1_DC_CLASSES:
        raise PairRecipeError(
            f"{_rid}: reject dc_class {_r.dc_class!r} not in Phase-1 admissible {sorted(PHASE1_DC_CLASSES)}"
        )
    if _r.verdict == "approve" and _r.dc_class is not None:
        raise PairRecipeError(f"{_rid}: approve control must have dc_class=None, got {_r.dc_class!r}")
    if not callable(_r.task_scope):
        raise PairRecipeError(f"{_rid}: task_scope must be callable")

for _group, _members in PAIR_GROUPS.items():
    if len(_members) != 2:
        raise PairRecipeError(
            f"pair group {_group!r} must have exactly 2 reject sides, got {list(_members)}"
        )
    for _m in _members:
        if PAIR_RECIPES[_m].verdict != "reject":
            raise PairRecipeError(f"pair group {_group!r} member {_m} must be a reject side")


# --------------------------------------------------------------------------------------
# Apply entrypoint (pure). Loud on an unknown recipe; None-passthrough on anchor-absent.
# --------------------------------------------------------------------------------------
def apply_pair_recipe(bundle: dict[str, Any], recipe_id: str) -> Optional[PairInjectionResult]:
    """Apply ``recipe_id`` to a serialized control bundle. Returns a :class:`PairInjectionResult`
    (mutated bundle + fixed label), or ``None`` when the recipe's anchor is absent (the caller
    records that as a LOUD result — never a silent no-op). Pure: no I/O, no worktree, no model."""
    if recipe_id not in PAIR_RECIPES:
        raise KeyError(f"unknown pair recipe {recipe_id!r}; known: {sorted(PAIR_RECIPES)}")
    recipe = PAIR_RECIPES[recipe_id]
    planned = recipe.plan(bundle)
    if planned is None:
        return None
    mutated_bundle, locus = planned
    finding = (
        {"class": recipe.dc_class, "locus": locus}
        if recipe.verdict == "reject" and recipe.dc_class
        else None
    )
    return PairInjectionResult(
        recipe_id=recipe.id,
        dc_class=recipe.dc_class,
        verdict=recipe.verdict,
        pair_group=recipe.pair_group,
        mutated_bundle=mutated_bundle,
        finding=finding,
    )


def applicable_pair_recipes(repo: str, task: str) -> list[str]:
    """The ``R-BUNDLE-PAIR-*`` recipe ids whose ``task_scope`` admits ``(repo, task)`` — registry
    order preserved (axis A pair, axis B pair, controls, axis C sides)."""
    return [rid for rid, r in PAIR_RECIPES.items() if r.task_scope(repo, task)]


def task_pair_plan(repo: str, task: str) -> tuple[
    list[tuple[str, tuple[str, ...]]], list[str]
]:
    """Split a task's applicable recipes into (atomic pair GROUPS, SINGLE recipes).

    ``groups`` = ordered ``(group_key, (id_a, id_b))`` for every pair whose BOTH reject sides are
    in scope (axes A/B — banked pair-atomically). ``singles`` = ordered single recipe ids (approve
    controls + axis-C sides — banked individually). A pair with only one side in scope is skipped
    (never a lone atomic side); by construction both sides share ``task_scope`` so this cannot
    happen, but the guard keeps the invariant explicit."""
    applicable = applicable_pair_recipes(repo, task)
    app_set = set(applicable)
    groups: list[tuple[str, tuple[str, ...]]] = []
    singles: list[str] = []
    seen_groups: set[str] = set()
    for rid in applicable:
        recipe = PAIR_RECIPES[rid]
        if recipe.pair_group is None:
            singles.append(rid)
            continue
        if recipe.pair_group in seen_groups:
            continue
        seen_groups.add(recipe.pair_group)
        members = PAIR_GROUPS[recipe.pair_group]
        if all(m in app_set for m in members):
            groups.append((recipe.pair_group, members))
    return groups, singles
