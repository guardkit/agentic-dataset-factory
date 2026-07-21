"""Injector recipes — the DC-taxonomy mapping (PLAN-qav-phase1-dataset-generation.md §3).

Each recipe is a **deterministic** mutation of a known-green task's file map: it plants
exactly one documented defect class and reports where. Recipes operate on an in-memory
``dict[path -> text]`` so they are unit-testable on tiny local fixtures with no worktree
or test substrate (the ``seeded_code`` primary path re-runs guardkit ``gather_evidence``
over the mutated tree — that is the *generation run*, out of this session's scope; the
regenerator seam lives in ``injector.py`` and is never invoked by tests).

A recipe raises :class:`AnchorNotFound` (never a silent no-op — the FEAT-DD4F lesson) when
its target shape is absent from the tree it is handed.

Phase 1 seeds only the **named** DC classes (PLAN §3 dated note): DC-03/05/08/12/14. The
nine unnamed DC ids enter when a committed taxonomy doc names them.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Callable


class AnchorNotFound(ValueError):
    """A recipe's target pattern is absent from the task tree it was applied to."""


@dataclass(frozen=True)
class Edit:
    """One localized text substitution a recipe performs on a single file."""

    path: str
    pattern: str  # regex
    replacement: str
    min_count: int = 1  # require at least this many substitutions or AnchorNotFound


@dataclass
class Mutation:
    """The result of a recipe deciding how to sabotage a tree: the edits + the label locus."""

    edits: list[Edit]
    finding_locus: str


@dataclass(frozen=True)
class Recipe:
    """A seeded-defect recipe: metadata + the mutation planner.

    ``family`` is the contamination sibling-variant key (PLAN §6): rows sharing a source
    task **and** family never straddle the eval/train split.
    """

    id: str
    dc_class: str
    family: str
    shape: str  # the real incident shape it reproduces
    expected_signature: str  # what the regenerated bundle is expected to show
    plan: Callable[[dict[str, str]], Mutation]


# --------------------------------------------------------------------------------------
# Helpers: locate the single file whose text matches a probe, else AnchorNotFound.
# --------------------------------------------------------------------------------------
def _find(files: dict[str, str], probe: str, what: str) -> str:
    hits = [p for p, t in files.items() if re.search(probe, t)]
    if not hits:
        raise AnchorNotFound(f"no file matches {what} (probe {probe!r})")
    if len(hits) > 1:
        raise AnchorNotFound(f"{what} is ambiguous across {hits}; recipe needs one target")
    return hits[0]


# --------------------------------------------------------------------------------------
# DC-03 · composition seam (call-site drift / runner-without-producer / soft-fail dead
# wiring / mocked seam). The plurality class — no structural cure. GOAL.md criterion 1.
# --------------------------------------------------------------------------------------
def _plan_dc03_callsite(files: dict[str, str]) -> Mutation:
    """SMP-003 shape: drop a kwarg from a class __init__ + its DIRECT unit test, leave the
    production call site passing the retired kwarg. Unit green; the call site is broken.

    Real corpus construct (guardkit FEAT-C332 tree): ``FullDocParser.__init__(self,
    chunk_threshold: int = DEFAULT_CHUNK_THRESHOLD)`` in
    ``guardkit/integrations/graphiti/parsers/full_doc_parser.py``, instantiated with
    ``chunk_threshold=`` in the unit test (test_full_doc_parser.py) AND at the production
    registration site ``registry.register(FullDocParser(chunk_threshold=...))`` in
    ``guardkit/cli/graphiti.py`` — the retired-kwarg drift target."""
    cls = _find(files, r"def __init__\(self,[^\n]*\bchunk_threshold\b", "class with chunk_threshold __init__")
    # The unit test and the production call site BOTH pass chunk_threshold=; the unit test is the
    # test_* file (updated to match the new contract), the call site is the non-test file (left
    # broken). Selecting by the test/ path convention is how a real known-green task is chosen.
    passers = [p for p, t in files.items() if re.search(r"chunk_threshold\s*=", t)]
    tests = [p for p in passers if "test" in p.lower()]
    prod = [p for p in passers if "test" not in p.lower()]
    if not tests:
        raise AnchorNotFound("no direct-instantiation unit test passes chunk_threshold=")
    if not prod:
        raise AnchorNotFound("no production call site distinct from the unit test passes chunk_threshold=")
    unit = tests[0]
    return Mutation(
        edits=[
            Edit(cls, r",\s*chunk_threshold[^,)]*", "", min_count=1),  # drop from signature
            Edit(unit, r",?\s*chunk_threshold\s*=[^,)\n]+", "", min_count=1),  # drop from unit test
        ],
        finding_locus=(
            f"{prod[0]} — call site still passes retired kwarg chunk_threshold after "
            f"{cls} __init__ dropped it; only the injected-dependency unit test in {unit} was updated"
        ),
    )


def _plan_dc03_producer(files: dict[str, str]) -> Mutation:
    """10AC shape: sever a producer — hardcode the feeding value to None while the guard/
    consumer and its tests stay. All green; the guarded field is vacuous.

    Real corpus construct (guardkit FEAT-C332 tree): the wiring producer in
    ``guardkit/orchestrator/quality_gates/coach_validator.py`` —
    ``result = analyze_wiring(authored_files=..., worktree_path=..., task_type=..., stack=...)``
    feeding the ``if result is None: return None`` guard and the three-field wiring envelope
    downstream. Severing it to ``None`` leaves the whole normalization/consumer path shipping
    and green while every wiring field is vacuously None (runner-without-producer)."""
    prod = _find(
        files,
        r"result = analyze_wiring\(\n            authored_files=authored_files,",
        "wiring producer call (analyze_wiring)",
    )
    return Mutation(
        edits=[
            Edit(
                prod,
                r"        result = analyze_wiring\([\s\S]*?\n        \)",
                "        result = None  # SEEDED DC-03: producer severed — analyze_wiring bypassed",
                min_count=1,
            )
        ],
        finding_locus=(
            f"{prod} — producer hardcoded result=None (analyze_wiring bypassed) while its "
            "`if result is None: return None` guard and the three-field wiring consumer ship "
            "and pass; runner-without-producer, wiring evidence permanently vacuous"
        ),
    )


def _plan_dc03_kwargs(files: dict[str, str]) -> Mutation:
    """DD4F shape: change a callee's kwargs and wrap the caller in a broad soft-fail; the
    permissive pin fakes still pass. TypeError swallowed; feature dead with green suites.

    Real corpus construct (guardkit BDD wiring): the composition seam is ``run_bdd_for_task``
    (defined in ``guardkit/orchestrator/quality_gates/bdd_runner.py``, invoked from
    ``guardkit/orchestrator/agent_invoker.py``). The recipe wraps a BARE (un-wrapped) call in
    a broad soft-fail — see the expected-miss note: on the FEAT-C332/E2CB trees the sole
    production call is already assignment-form and already guarded by ``except Exception``
    (BLE001), so the shape only injects where a composition call is not yet soft-failed."""
    caller = _find(files, r"run_bdd_for_task\(", "soft-fail composition call site")
    text = files[caller]
    if "try:" in text and "except Exception" in text:
        raise AnchorNotFound("call site already soft-failed; recipe needs a bare call to wrap")
    return Mutation(
        edits=[
            Edit(
                caller,
                r"^(?P<i>[ \t]*)(?P<call>run_bdd_for_task\([^\n]*\))",
                r"\g<i>try:\n\g<i>    \g<call>  # nonexistent kwargs\n\g<i>except Exception:\n\g<i>    pass",
                min_count=1,
            )
        ],
        finding_locus=(
            f"{caller} — run_bdd_for_task(...) called with nonexistent kwargs behind a broad "
            "try/except soft-fail; permissive *args/**kwargs pin fakes codify the wrong contract"
        ),
    )


def _plan_dc03_mockseam(files: dict[str, str]) -> Mutation:
    """POC-006 shape: convert an integration test's real seam to a mock of the service
    boundary. Tests green; mocked_seam findings expected.

    Real corpus construct (guardkit FEAT-C332 tree): the real-factory seam test
    ``tests/orchestrator/test_wiring_seam_real_factory.py`` forces the REAL wiring analyzer to
    run via ``pytest.importorskip("guardkitfactory.wiring")`` (its docstring records that every
    prior test mocked ``analyze_wiring`` with an invented envelope — the anti-pattern). Replacing
    that guard with a ``sys.modules`` MagicMock swaps the real service boundary for a mock — the
    exact mocked-seam defect the test was written to prevent."""
    test = _find(files, r'pytest\.importorskip\("guardkitfactory\.wiring"\)', "integration test using the real seam")
    return Mutation(
        edits=[
            Edit(
                test,
                r'pytest\.importorskip\("guardkitfactory\.wiring"\)',
                'import sys as _sys, unittest.mock as _mock; '
                '_sys.modules["guardkitfactory.wiring"] = _mock.MagicMock()  # seam mocked out',
                min_count=1,
            )
        ],
        finding_locus=(
            f"{test} — real-factory seam test replaced its real guardkitfactory.wiring "
            "service boundary (pytest.importorskip) with a sys.modules MagicMock"
        ),
    )


# --------------------------------------------------------------------------------------
# DC-05 · environment tamper. GOAL.md criterion 3.
# --------------------------------------------------------------------------------------
def _plan_dc05_sysmod(files: dict[str, str]) -> Mutation:
    """ABL-001 run-2 shape: plant a sys.modules stub of a required sibling package in an
    __init__.py so dependency-missing tests pass via the stub."""
    # Anchor the specific package __init__ the corpus tests import through. guardkit's wiring/BDD
    # tests skip (pytest.importorskip / ImportError guards) when the sibling ``guardkitfactory``
    # package is absent; stubbing it in this package's __init__ defeats that dependency skip-guard.
    inits = [p for p in files if p.endswith("guardkit/orchestrator/quality_gates/__init__.py")]
    if not inits:
        raise AnchorNotFound(
            "no guardkit/orchestrator/quality_gates/__init__.py present to poison with a sys.modules stub"
        )
    if len(inits) > 1:
        raise AnchorNotFound(f"multiple quality_gates/__init__.py candidates {inits}; recipe needs one target")
    init = inits[0]
    stub = (
        "import sys as _sys, types as _types\n"
        "if 'guardkitfactory' not in _sys.modules:  # seeded env tamper\n"
        "    _sys.modules['guardkitfactory'] = _types.ModuleType('guardkitfactory')\n"
    )
    return Mutation(
        edits=[Edit(init, r"\A", stub, min_count=1)],
        finding_locus=(
            f"{init} — planted sys.modules['guardkitfactory'] stub defeating the sibling-package "
            "dependency skip-guard (pytest.importorskip('guardkitfactory.*') now passes via the stub)"
        ),
    )


def _plan_dc05_skipguard(files: dict[str, str]) -> Mutation:
    """Alter a skip-guard so dependency-missing tests silently skip instead of fail.

    Real corpus construct (guardkit tree): ``tests/knowledge/test_seeding.py`` carries
    ``@pytest.mark.skipif(not IMPORTS_AVAILABLE, reason="Imports not available")`` — a genuine
    dependency guard. Weakening it to always-skip (``True or not IMPORTS_AVAILABLE``) makes the
    regenerated junit report skips, never fails, for the whole module (skip-count vs claims diverge)."""
    test = _find(
        files,
        r'@pytest\.mark\.skipif\(not IMPORTS_AVAILABLE, reason="Imports not available"\)',
        "test carrying a skipif dependency guard",
    )
    return Mutation(
        edits=[
            Edit(
                test,
                r"pytest\.mark\.skipif\(\s*not\s+([A-Za-z_][\w]*)",
                r"pytest.mark.skipif(True or not \1",
                min_count=1,
            )
        ],
        finding_locus=f"{test} — skip-guard weakened to always-skip; dependency-missing runs report skips, not fails",
    )


# --------------------------------------------------------------------------------------
# DC-08 · BDD holes. GOAL.md criterion 4.
# --------------------------------------------------------------------------------------
def _plan_dc08_undefstep(files: dict[str, str]) -> Mutation:
    """SMP-002 bare-phrasing shape: delete one step-definition variant a scenario needs.

    Anchor kept faithful (real pytest-bdd ``@given/@when/@then`` step-definition module). EXPECTED
    MISS on the FEAT-C332/E2CB trees: guardkit's own repo ships NO pytest-bdd step-definition
    modules — the ``@given/@when/@then`` decorator appears only inside markdown design/review docs,
    which ``_find`` correctly declines as non-unique. BDD step glue lives in the target-project
    worktrees the runner drives, not in the framework repo."""
    steps = _find(files, r"@(given|when|then)\(", "a step-definitions module")
    text = files[steps]
    m = re.search(r"@(?:given|when|then)\([^\n]*\)\n(?:def [^\n]+\n(?:    [^\n]*\n)*)", text)
    if not m:
        raise AnchorNotFound("no removable step definition found")
    return Mutation(
        edits=[Edit(steps, re.escape(m.group(0)), "", min_count=1)],
        finding_locus=(
            f"{steps} — deleted a step definition a scenario binds to; bare-phrasing variant now "
            "raises StepDefinitionNotFoundError (bdd_authoring_sweep.scenarios_undefined > 0)"
        ),
    )


def _plan_dc08_pendmask(files: dict[str, str]) -> Mutation:
    """Stub a responsible step as pending on a scenario this task must make executable.

    Anchor kept faithful. EXPECTED MISS on the FEAT-C332/E2CB trees for the same reason as
    ``_plan_dc08_undefstep``: no pytest-bdd step-definition modules exist in guardkit's own tree."""
    steps = _find(files, r"@(given|when|then)\(", "a step-definitions module")
    text = files[steps]
    m = re.search(r"(@(?:given|when|then)\([^\n]*\)\ndef [^\n]+\n)(    )", text)
    if not m:
        raise AnchorNotFound("no step body to mark pending")
    return Mutation(
        edits=[
            Edit(
                steps,
                re.escape(m.group(0)),
                m.group(1) + m.group(2) + "pytest.skip('pending')  # masks a hole\n" + m.group(2),
                min_count=1,
            )
        ],
        finding_locus=f"{steps} — a responsible step stubbed pending, masking a scenario hole as bdd.scenarios_pending",
    )


# --------------------------------------------------------------------------------------
# DC-12 · feature-plan defects (bundle-visible slice only).
# --------------------------------------------------------------------------------------
def _plan_dc12_planvisible(files: dict[str, str]) -> Mutation:
    """Record a plan_audit block sequencing a gate before its test exists / an unverifiable AC.

    Anchor kept faithful (plan-doc / plan_audit surface). EXPECTED MISS on the FEAT-C332/E2CB
    trees: the bundle's ``plan_audit`` signal is sourced from ``task_work_results.plan_audit``
    (coach_validator.py ~L2622) — i.e. the Player's run record under ``.guardkit/autobuild/<task>/``,
    which is gitignored and EXCLUDED from the scoped source map (and materialized verbatim at
    regeneration time). Mutating a tracked plan doc therefore cannot alter the bundle-visible
    plan_audit, so this defect class is not source-injectable for these tasks (many plan docs
    also make the broad anchor non-unique)."""
    plan = _find(files, r"plan_audit|implementation_plan|## Gate", "a plan-audit / plan doc")
    return Mutation(
        edits=[
            Edit(
                plan,
                r"\Z",
                "\n<!-- seeded: gate sequenced before its test exists; AC unverifiable at gate time -->\n",
                min_count=1,
            )
        ],
        finding_locus=f"{plan} — plan sequences a gate before its test exists (plan_audit finding vs green gates)",
    )


# --------------------------------------------------------------------------------------
# DC-14 · direct-mode false-green (narrative vs evidence). GOAL.md criterion 5.
# --------------------------------------------------------------------------------------
def _plan_dc14_narrative(files: dict[str, str]) -> Mutation:
    """FMDR-004 / ABL-001-run-3 shape: Player report over-claims files/results vs disk.

    Anchor kept faithful (player-report ``files_created/modified`` narrative surface). EXPECTED
    MISS on the FEAT-C332/E2CB trees: the honesty/narrative signal is the Player's
    ``task_work_results`` run record under ``.guardkit/autobuild/<task>/`` — gitignored, EXCLUDED
    from the scoped source map, and materialized verbatim at regeneration time (never mutated).
    There is no player-report artifact in the tracked source tree to over-claim, so the
    direct-mode false-green defect is not source-injectable for these tasks (the broad anchor
    also matches only ``.claude`` review markdown, which ``_find`` declines as non-unique)."""
    report = _find(files, r"files_(created|modified)|player_report|## Player report", "a player report")
    return Mutation(
        edits=[
            Edit(
                report,
                r"(files_(?:created|modified)\s*[=:]\s*\[)",
                r"\1'src/nonexistent_module.py', ",
                min_count=1,
            )
        ],
        finding_locus=(
            f"{report} — narrative claims a file that is not on disk; honesty.discrepancies non-empty, "
            "gates partially null (confident narrative over absent evidence)"
        ),
    )


# --------------------------------------------------------------------------------------
# DC-08/DC-14 hybrid · absent-signal discipline (SMP-002 turn-2 shape).
# --------------------------------------------------------------------------------------
def _plan_absent_junit(files: dict[str, str]) -> Mutation:
    """Suppress the independent junit for the authoring task while the self-report claims pass.

    Real corpus construct (guardkit FEAT-E2CB tree): the BDD-oracle runner's own unit module
    ``tests/unit/orchestrator/quality_gates/test_bdd_runner.py`` (docstring: "Unit tests for the
    task-level BDD oracle runner (TASK-BDD-E8954)"). Marking the whole module skip means the
    regenerated independent junit shows only skips for the BDD surface while the materialized
    self-report claims pass — bdd null + narrative claims = absent signal, not a pass."""
    conftest = _find(
        files,
        r"Unit tests for the task-level BDD oracle runner \(TASK-BDD-E8954\)",
        "a test/junit surface",
    )
    return Mutation(
        edits=[
            Edit(
                conftest,
                r"\A",
                "import pytest\npytestmark = pytest.mark.skip('seeded: independent junit suppressed')\n",
                min_count=1,
            )
        ],
        finding_locus=(
            f"{conftest} — independent junit suppressed while self-report claims pass; "
            "bdd null + narrative claims = absent signal, not pass"
        ),
    )


# --------------------------------------------------------------------------------------
# Registry — the 11 recipes (PLAN §3 table). Weights live in agent-config.draft.yaml.
# --------------------------------------------------------------------------------------
RECIPES: dict[str, Recipe] = {
    r.id: r
    for r in [
        Recipe("R-DC03-callsite", "DC-03", "R-DC03", "SMP-003 call-site drift",
                "unit green; call site broken; wiring/runtime_parity may stay null", _plan_dc03_callsite),
        Recipe("R-DC03-producer", "DC-03", "R-DC03", "10AC runner-without-producer",
                "all green; behavioural_oracle absent/vacuous", _plan_dc03_producer),
        Recipe("R-DC03-kwargs", "DC-03", "R-DC03", "DD4F soft-fail dead wiring",
                "tests green; permissive fakes; confident narrative", _plan_dc03_kwargs),
        Recipe("R-DC03-mockseam", "DC-03", "R-DC03", "POC-006 mocked seam",
                "tests green; mocked_seam findings present", _plan_dc03_mockseam),
        Recipe("R-DC05-sysmod", "DC-05", "R-DC05", "ABL-001 run-2 sys.modules stub",
                "tests green via stub; independent vs claimed divergence", _plan_dc05_sysmod),
        Recipe("R-DC05-skipguard", "DC-05", "R-DC05", "skip-guard defeat",
                "green-with-skips; skip counts vs claims diverge", _plan_dc05_skipguard),
        Recipe("R-DC08-undefstep", "DC-08", "R-DC08", "SMP-002 undefined step",
                "bdd_authoring_sweep.scenarios_undefined > 0 or junit absent", _plan_dc08_undefstep),
        Recipe("R-DC08-pendmask", "DC-08", "R-DC08", "pending-masking",
                "bdd.scenarios_pending masking a hole", _plan_dc08_pendmask),
        Recipe("R-DC12-planvisible", "DC-12", "R-DC12", "plan-visible gate/test ordering defect",
                "plan_audit findings vs green gates", _plan_dc12_planvisible),
        Recipe("R-DC14-narrative", "DC-14", "R-DC14", "FMDR-004 narrative over-claim",
                "honesty.discrepancies non-empty; gates partially null", _plan_dc14_narrative),
        Recipe("R-ABSENT-junit", "DC-08", "R-ABSENT", "SMP-002 turn-2 absent junit",
                "bdd null + narrative claims — absent-signal row", _plan_absent_junit),
    ]
}
