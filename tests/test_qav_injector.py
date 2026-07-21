"""Injector seeded-control tests — the WS2-B11 gate:

"injector on a known-green task produces the labelled defect and NOTHING else."

Each recipe runs against a small, local, in-memory known-green fixture. We assert the
mutation plants exactly the labelled defect (correct DC class + only the declared files
change), that a missing anchor raises loudly (never a silent no-op), and that the
seeded-control (no-op) injection produces an empty diff and no finding.
"""

from __future__ import annotations

import pytest

from qav.contracts import PHASE1_DC_CLASSES
from qav.injector import inject, inject_control
from qav.recipes import RECIPES, AnchorNotFound

# --- small local known-green fixtures, one per recipe --------------------------------
# Each fixture QUOTES a realistic shape lifted from the actual corpus repos the round-4 pilot
# ran against — guardkit at the FEAT-C332 (799cefd0) / FEAT-E2CB (917bcef7) approved shas. The
# constructs below are verbatim (or minimally trimmed) from those trees, so a fixture that plants
# here proves the rewritten anchor matches the real code shape, not an assumed one.
FIXTURES: dict[str, dict[str, str]] = {
    # FullDocParser.__init__(chunk_threshold=...) — dropped from the signature + its unit test,
    # left passing at the guardkit/cli/graphiti.py registration call site (retired-kwarg drift).
    "R-DC03-callsite": {
        "guardkit/integrations/graphiti/parsers/full_doc_parser.py": (
            "class FullDocParser:\n"
            "    def __init__(self, chunk_threshold: int = DEFAULT_CHUNK_THRESHOLD):\n"
            '        """Initialize the parser."""\n'
        ),
        "tests/integrations/graphiti/parsers/test_full_doc_parser.py": (
            "def test_custom_chunk_threshold():\n"
            "    parser = FullDocParser(chunk_threshold=50)\n"
            "    assert parser\n"
        ),
        "guardkit/cli/graphiti.py": (
            "def register_parsers(registry):\n"
            "    registry.register(FullDocParser(chunk_threshold=effective_chunk_size))\n"
        ),
    },
    # coach_validator's analyze_wiring producer, feeding the `if result is None: return None`
    # guard + the three-field wiring consumer — severed to None (runner-without-producer).
    "R-DC03-producer": {
        "guardkit/orchestrator/quality_gates/coach_validator.py": (
            "    try:\n"
            "        result = analyze_wiring(\n"
            "            authored_files=authored_files,\n"
            "            worktree_path=worktree_path,\n"
            "            task_type=task_type,\n"
            "            stack=stack_obj,\n"
            "        )\n"
            "        if result is None:\n"
            "            return None\n"
        ),
    },
    # The real BDD composition seam (run_bdd_for_task) shown here as a BARE, un-wrapped call so
    # the recipe plants. On the real trees this call is assignment-form and already soft-failed
    # (agent_invoker.py try/except BLE001) — see EXPECTED_MISS_ON_CORPUS.
    "R-DC03-kwargs": {
        "guardkit/orchestrator/bdd_oracle.py": (
            "def invoke(task_id, worktree_path):\n"
            "    run_bdd_for_task(task_id, worktree_path, python_executable=None)\n"
        ),
    },
    # The real-factory seam test forces the REAL analyzer via importorskip; mocking it swaps the
    # service boundary for a MagicMock (the anti-pattern its docstring warns against).
    "R-DC03-mockseam": {
        "tests/orchestrator/test_wiring_seam_real_factory.py": (
            "import pytest\n\n"
            'pytest.importorskip("guardkitfactory.wiring")\n\n'
            "def test_real_seam():\n    assert True\n"
        ),
    },
    # The quality_gates package __init__ — stubbing the sibling guardkitfactory in sys.modules
    # defeats the importorskip / ImportError dependency guards the wiring+BDD tests rely on.
    "R-DC05-sysmod": {
        "guardkit/orchestrator/quality_gates/__init__.py": (
            '"""Quality gates for feature-build via task-work delegation."""\n'
        ),
        "guardkit/orchestrator/quality_gates/coach_validator.py": "x = 1\n",
    },
    # tests/knowledge/test_seeding.py's real dependency guard — weakened to always-skip.
    "R-DC05-skipguard": {
        "tests/knowledge/test_seeding.py": (
            "import pytest\n\n"
            '@pytest.mark.skipif(not IMPORTS_AVAILABLE, reason="Imports not available")\n'
            "def test_seed():\n    assert True\n"
        ),
    },
    # Realistic pytest-bdd step-definition module (EXPECTED MISS on the corpus: guardkit's own
    # tree ships no such modules — BDD glue lives in the driven target worktrees).
    "R-DC08-undefstep": {
        "tests/steps.py": (
            "from pytest_bdd import given, when, then\n\n"
            '@when("her recent misconceptions are read")\n'
            "def _read():\n    pass\n\n"
            '@then("the result shows")\n'
            "def _show():\n    pass\n"
        ),
    },
    "R-DC08-pendmask": {
        "tests/steps.py": (
            "import pytest\n\n"
            '@when("her recent misconceptions are read")\n'
            "def _read():\n    do_it()\n"
        ),
    },
    # Realistic plan doc (EXPECTED MISS on the corpus: bundle plan_audit is sourced from the
    # excluded .guardkit run record, not a tracked plan doc).
    "R-DC12-planvisible": {
        "docs/implementation_plan.md": "## Gate G1\n- run tests\n",
    },
    # Realistic player report (EXPECTED MISS on the corpus: the narrative signal is the excluded
    # .guardkit task_work_results record, absent from the tracked source tree).
    "R-DC14-narrative": {
        "run/player_report.py": "files_created = ['src/real.py']\ntests_passed = True\n",
    },
    # The BDD-oracle runner's own unit module — whole-module skip suppresses its independent junit.
    "R-ABSENT-junit": {
        "tests/unit/orchestrator/quality_gates/test_bdd_runner.py": (
            '"""Unit tests for the task-level BDD oracle runner (TASK-BDD-E8954)."""\n\n'
            "def test_run_bdd_for_task_smoke():\n    assert True\n"
        ),
    },
}

# Recipes whose defect class is faithfully authored but does NOT source-inject against the three
# round-4 processable tasks (guardkit QAWE-001/QAWE-002 @ 799cefd0, BDDW-001 @ 917bcef7). Recorded
# honestly rather than force-matched (semantic fidelity over hit-rate). Each still plants on its
# realistic fixture above — the miss is corpus-specific, not a broken recipe.
EXPECTED_MISS_ON_CORPUS: dict[str, str] = {
    "R-DC03-kwargs": (
        "the only production composition call (run_bdd_for_task in agent_invoker.py) is "
        "assignment-form and already soft-failed by a try/except BLE001; wrapping it would "
        "double-wrap, and the bare name is non-unique across review docs"
    ),
    "R-DC08-undefstep": "no pytest-bdd step-definition modules in guardkit's own tree",
    "R-DC08-pendmask": "no pytest-bdd step-definition modules in guardkit's own tree",
    "R-DC12-planvisible": (
        "bundle plan_audit is read from task_work_results (the gitignored .guardkit run record), "
        "so mutating a tracked plan doc cannot alter it"
    ),
    "R-DC14-narrative": (
        "the honesty/narrative signal is the .guardkit task_work_results record, excluded from "
        "the scoped source map — no player-report artifact in the tracked tree to over-claim"
    ),
}


def test_every_recipe_has_a_fixture():
    assert set(FIXTURES) == set(RECIPES)


@pytest.mark.parametrize("recipe_id", sorted(RECIPES))
def test_recipe_plants_labelled_defect_and_nothing_else(recipe_id):
    fixture = FIXTURES[recipe_id]
    result = inject(dict(fixture), recipe_id)

    # correct, admissible DC class + a non-empty locus
    assert result.dc_class == RECIPES[recipe_id].dc_class
    assert result.dc_class in PHASE1_DC_CLASSES
    assert result.finding["class"] == result.dc_class
    assert result.finding["locus"].strip()

    # label fixed by construction
    assert result.label == {
        "verdict": "reject",
        "findings": [result.finding],
        "ground_truth_source": "seeded",
    }

    # a real change was made, and ONLY declared files changed (self-check already ran)
    assert result.changed_files, "recipe made no change"
    changed = set(result.changed_files)
    unchanged = set(fixture) - changed
    for path in unchanged:
        assert result.mutated_files[path] == fixture[path], f"{recipe_id} strayed into {path}"
    assert result.diff  # unified diff produced as evidence


def test_callsite_leaves_the_production_call_site_broken():
    """The DC-03 call-site defect: unit test updated, production call site left passing the
    retired kwarg (that is the defect — it must NOT be 'fixed' by the injector)."""
    cls = "guardkit/integrations/graphiti/parsers/full_doc_parser.py"
    unit = "tests/integrations/graphiti/parsers/test_full_doc_parser.py"
    prod = "guardkit/cli/graphiti.py"
    result = inject(dict(FIXTURES["R-DC03-callsite"]), "R-DC03-callsite")
    assert set(result.changed_files) == {cls, unit}
    assert prod not in result.changed_files
    assert "chunk_threshold=effective_chunk_size" in result.mutated_files[prod]  # defect preserved
    assert "def __init__(self):" in result.mutated_files[cls]  # signature dropped the kwarg
    assert "chunk_threshold=" not in result.mutated_files[unit]  # unit test updated to new contract
    assert prod in result.finding["locus"]


def test_expected_miss_recipes_are_recorded_but_still_plant_on_their_fixture():
    """The recipes recorded as corpus expected-misses are faithful, not broken: each still plants
    its labelled defect on a realistic in-memory fixture. The miss is corpus-specific (verified out
    of band against the checked-out FEAT-C332/E2CB trees), and every reason is recorded."""
    assert set(EXPECTED_MISS_ON_CORPUS) <= set(RECIPES)
    for recipe_id, reason in EXPECTED_MISS_ON_CORPUS.items():
        assert reason.strip(), f"{recipe_id} missing an expected-miss reason"
        result = inject(dict(FIXTURES[recipe_id]), recipe_id)
        assert result.changed_files, f"{recipe_id} must still plant on its realistic fixture"
        assert result.dc_class == RECIPES[recipe_id].dc_class


def test_missing_anchor_raises_loudly():
    with pytest.raises(AnchorNotFound):
        inject({"a.py": "x = 1\n"}, "R-DC03-producer")


def test_seeded_control_is_a_true_noop():
    fixture = FIXTURES["R-DC03-producer"]
    result = inject_control(dict(fixture))
    assert result.diff == ""
    assert result.changed_files == []
    assert result.finding == {}
    assert result.mutated_files == fixture


def test_unknown_recipe_raises_keyerror():
    with pytest.raises(KeyError):
        inject({"a.py": "x"}, "R-NOPE")
