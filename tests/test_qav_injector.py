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
FIXTURES: dict[str, dict[str, str]] = {
    "R-DC03-callsite": {
        "src/adapter.py": (
            "class MCPAdapter:\n"
            "    def __init__(self, store, write_helper, session_service):\n"
            "        self.store = store\n"
        ),
        "tests/test_adapter.py": (
            "def test_direct():\n"
            "    a = MCPAdapter(store=s, write_helper=w, session_service=x)\n"
            "    assert a\n"
        ),
        "src/main.py": (
            "def serve():\n"
            "    return MCPAdapter(store=s, write_helper=w, session_service=x)\n"
        ),
    },
    "R-DC03-producer": {
        "src/evidence.py": (
            "def gather():\n"
            "    behavioural_oracle = compute_oracle(tree)\n"
            "    return behavioural_oracle\n"
        ),
    },
    "R-DC03-kwargs": {
        "src/serve.py": "def boot():\n    compose_planning(db_path=p, nats_url=u)\n",
    },
    "R-DC03-mockseam": {
        "tests/test_integration.py": (
            "def test_it():\n    real_client = RealClient(url)\n    assert real_client.ping()\n"
        ),
    },
    "R-DC05-sysmod": {
        "pkg/__init__.py": "import os\n",
        "pkg/mod.py": "x = 1\n",
    },
    "R-DC05-skipguard": {
        "tests/test_dep.py": (
            '@pytest.mark.skipif(not HAVE_NATS, reason="needs nats")\n'
            "def test_x():\n    assert True\n"
        ),
    },
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
    "R-DC12-planvisible": {
        "docs/implementation_plan.md": "## Gate G1\n- run tests\n",
    },
    "R-DC14-narrative": {
        "run/player_report.py": "files_created = ['src/real.py']\ntests_passed = True\n",
    },
    "R-ABSENT-junit": {
        "tests/test_authoring.py": "def test_scenarios():\n    assert True\n",
    },
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
    result = inject(dict(FIXTURES["R-DC03-callsite"]), "R-DC03-callsite")
    assert set(result.changed_files) == {"src/adapter.py", "tests/test_adapter.py"}
    assert "src/main.py" not in result.changed_files
    assert "write_helper" in result.mutated_files["src/main.py"]  # defect preserved
    assert "write_helper" not in result.mutated_files["src/adapter.py"]  # signature dropped
    assert "src/main.py" in result.finding["locus"]


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
