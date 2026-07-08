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
    production call site passing the retired kwarg. Unit green; the call site is broken."""
    cls = _find(files, r"def __init__\(self,[^\n]*\bwrite_helper\b", "class with write_helper __init__")
    # The unit test and the production call site BOTH pass write_helper=; the unit test is the
    # test_* file (updated to match the new contract), the call site is the non-test file (left
    # broken). Selecting by the test/ path convention is how a real known-green task is chosen.
    passers = [p for p, t in files.items() if re.search(r"write_helper\s*=", t)]
    tests = [p for p in passers if "test" in p.lower()]
    prod = [p for p in passers if "test" not in p.lower()]
    if not tests:
        raise AnchorNotFound("no direct-instantiation unit test passes write_helper=")
    if not prod:
        raise AnchorNotFound("no production call site distinct from the unit test passes write_helper=")
    unit = tests[0]
    return Mutation(
        edits=[
            Edit(cls, r",\s*write_helper[^,)]*", "", min_count=1),  # drop from signature
            Edit(unit, r",?\s*write_helper\s*=[^,)\n]+", "", min_count=1),  # drop from unit test
        ],
        finding_locus=(
            f"{prod[0]} — call site still passes retired kwarg write_helper after "
            f"{cls} __init__ dropped it; only the injected-dependency unit test in {unit} was updated"
        ),
    )


def _plan_dc03_producer(files: dict[str, str]) -> Mutation:
    """10AC shape: sever a producer — hardcode the feeding value to None while the guard/
    consumer and its tests stay. All green; the guarded field is vacuous."""
    prod = _find(files, r"behavioural_oracle\s*=\s*_?compute", "producer assignment")
    return Mutation(
        edits=[Edit(prod, r"behavioural_oracle\s*=\s*[^\n]+", "behavioural_oracle = None", min_count=1)],
        finding_locus=(
            f"{prod} — producer hardcoded behavioural_oracle=None while its guard/consumer ship "
            "and pass; runner-without-producer, guard permanently vacuous"
        ),
    )


def _plan_dc03_kwargs(files: dict[str, str]) -> Mutation:
    """DD4F shape: change a callee's kwargs and wrap the caller in a broad soft-fail; the
    permissive pin fakes still pass. TypeError swallowed; feature dead with green suites."""
    caller = _find(files, r"compose_planning\(", "soft-fail composition call site")
    text = files[caller]
    if "try:" in text and "except Exception" in text:
        raise AnchorNotFound("call site already soft-failed; recipe needs a bare call to wrap")
    return Mutation(
        edits=[
            Edit(
                caller,
                r"^(?P<i>[ \t]*)(?P<call>compose_planning\([^\n]*\))",
                r"\g<i>try:\n\g<i>    \g<call>  # nonexistent kwargs\n\g<i>except Exception:\n\g<i>    pass",
                min_count=1,
            )
        ],
        finding_locus=(
            f"{caller} — compose_planning(...) called with nonexistent kwargs behind a broad "
            "try/except soft-fail; permissive *args/**kwargs pin fakes codify the wrong contract"
        ),
    )


def _plan_dc03_mockseam(files: dict[str, str]) -> Mutation:
    """POC-006 shape: convert an integration test's real seam to a mock of the service
    boundary. Tests green; mocked_seam findings expected."""
    test = _find(files, r"real_(client|seam|adapter)\s*=", "integration test using the real seam")
    return Mutation(
        edits=[
            Edit(
                test,
                r"real_(client|seam|adapter)\s*=\s*[^\n]+",
                r"real_\1 = MagicMock()  # seam mocked out",
                min_count=1,
            )
        ],
        finding_locus=f"{test} — integration test replaced its real service-boundary seam with a MagicMock",
    )


# --------------------------------------------------------------------------------------
# DC-05 · environment tamper. GOAL.md criterion 3.
# --------------------------------------------------------------------------------------
def _plan_dc05_sysmod(files: dict[str, str]) -> Mutation:
    """ABL-001 run-2 shape: plant a sys.modules stub of a required sibling package in an
    __init__.py so dependency-missing tests pass via the stub."""
    inits = [p for p in files if p.endswith("__init__.py")]
    if not inits:
        raise AnchorNotFound("no __init__.py present to poison with a sys.modules stub")
    if len(inits) > 1:
        raise AnchorNotFound(f"multiple __init__.py candidates {inits}; recipe needs one target")
    init = inits[0]
    stub = (
        "import sys as _sys, types as _types\n"
        "if 'nats_core' not in _sys.modules:  # seeded env tamper\n"
        "    _sys.modules['nats_core'] = _types.ModuleType('nats_core')\n"
    )
    return Mutation(
        edits=[Edit(init, r"\A", stub, min_count=1)],
        finding_locus=f"{init} — planted sys.modules['nats_core'] stub defeating the dependency skip-guard",
    )


def _plan_dc05_skipguard(files: dict[str, str]) -> Mutation:
    """Alter a skip-guard so dependency-missing tests silently skip instead of fail."""
    test = _find(files, r"pytest\.mark\.skipif\(", "test carrying a skipif dependency guard")
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
    """SMP-002 bare-phrasing shape: delete one step-definition variant a scenario needs."""
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
    """Stub a responsible step as pending on a scenario this task must make executable."""
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
    """Record a plan_audit block sequencing a gate before its test exists / an unverifiable AC."""
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
    """FMDR-004 / ABL-001-run-3 shape: Player report over-claims files/results vs disk."""
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
    """Suppress the independent junit for the authoring task while the self-report claims pass."""
    conftest = _find(files, r"junit|--junitxml|def test_|@(given|when|then)", "a test/junit surface")
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
