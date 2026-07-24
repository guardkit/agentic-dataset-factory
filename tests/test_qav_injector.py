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


# --- study_tutor per-repo anchor variant (R-DC03-callsite) ---------------------------
# Verbatim CorpusChunk construct lifted from study-tutor src/study_tutor/knowledge/corpus_models.py
# at the approved sha 94f3331 (FEAT-70A4 / TASK-PRV-001), plus the unit-payload call sites from
# tests/unit/knowledge/test_corpus_models.py that instantiate CorpusChunk(..., chunk_index=N). The
# fixture proves the study_tutor anchor matches the real code shape, not an assumed one.
STUDY_TUTOR_CORPUS_MODELS = (
    "class CorpusChunk(BaseModel):\n"
    '    """A single retrievable chunk of source material."""\n\n'
    '    model_config = ConfigDict(extra="forbid")\n\n'
    "    text: str\n"
    "    source_type: SourceType\n"
    "    source_path: str\n"
    "    text_name: str = Field(min_length=1)\n"
    "    citation_anchor: CitationAnchor | None = None\n"
    "    chunk_index: int\n"
)
STUDY_TUTOR_TEST_PAYLOAD = (
    "def _primary_chunk_payload() -> dict:\n"
    "    return dict(\n"
    '        text="Is this a dagger which I see before me?",\n'
    "        source_type=SourceType.PRIMARY_TEXT,\n"
    '        source_path="/corpus/primary/macbeth/act-2.txt",\n'
    '        text_name="Macbeth",\n'
    "        citation_anchor=PlayCitationAnchor(act=2, scene=1, line=33),\n"
    "        chunk_index=12,\n"
    "    )\n"
)
STUDY_TUTOR_FIXTURE = {
    "src/study_tutor/knowledge/corpus_models.py": STUDY_TUTOR_CORPUS_MODELS,
    "tests/unit/knowledge/test_corpus_models.py": STUDY_TUTOR_TEST_PAYLOAD,
}


def test_dc03_callsite_study_tutor_variant_retires_the_field_and_nothing_else():
    """The study_tutor anchor variant of R-DC03-callsite: retire CorpusChunk.chunk_index from the
    extra='forbid' model contract. It plants in the model file ONLY (the payload call site that
    still passes chunk_index= is left broken, which is the defect the unit scope surfaces)."""
    module = "src/study_tutor/knowledge/corpus_models.py"
    payload = "tests/unit/knowledge/test_corpus_models.py"
    result = inject(dict(STUDY_TUTOR_FIXTURE), "R-DC03-callsite")

    assert result.dc_class == "DC-03"
    assert result.changed_files == [module]  # model only
    assert payload not in result.changed_files
    # the field is genuinely gone from the contract
    assert "chunk_index: int" not in result.mutated_files[module]
    # the call site still passes chunk_index= — the dead call site the extra='forbid' contract kills
    assert "chunk_index=12" in result.mutated_files[payload]
    assert "chunk_index" in result.finding["locus"]
    assert module in result.finding["locus"]


def test_dc03_callsite_variants_are_mutually_exclusive_across_disjoint_trees():
    """First-unique-match: the guardkit fixture triggers the guardkit variant, the study_tutor
    fixture triggers the study_tutor variant, and neither anchor is present in the other's tree."""
    gk = inject(dict(FIXTURES["R-DC03-callsite"]), "R-DC03-callsite")
    st = inject(dict(STUDY_TUTOR_FIXTURE), "R-DC03-callsite")
    assert "full_doc_parser.py" in gk.finding["locus"]
    assert "corpus_models.py" in st.finding["locus"]
    assert set(gk.changed_files) != set(st.changed_files)


def test_dc03_callsite_raises_loudly_when_no_variant_anchors():
    """When neither the guardkit nor the study_tutor anchor is present, _first_anchor re-raises
    AnchorNotFound loudly (never a silent no-op) and names every variant it tried."""
    with pytest.raises(AnchorNotFound) as exc:
        inject({"unrelated.py": "x = 1\n"}, "R-DC03-callsite")
    assert "no per-repo anchor variant matched" in str(exc.value)


# --- jarvis per-repo anchor variant (R-DC05-skipguard) -------------------------------
# Verbatim skip-guard construct lifted from jarvis tests/test_fleet_memory_payloads.py @ 736399b
# (module-level nats_core guard). The variant plants the SAME DC-05 skip-guard-defeat as guardkit's
# IMPORTS_AVAILABLE weaken, expressed in jarvis's own dependency-guard vocabulary. The fixture
# proves the anchor matches the real code shape, not an assumed one.
# (study_tutor's DC-05 skip-guard was attempted and recorded as an honest ceiling — control-red at
#  its approved sha; see recipes._plan_dc05_skipguard and the receipt — so no study_tutor fixture.)
JARVIS_TEST_PAYLOADS = (
    '"""Unit tests for Jarvis fleet-memory episode construction.\n\n'
    "These assert the outbound episode shape without any live store (no publish).\n"
    '"""\n'
    "from __future__ import annotations\n\n"
    "import importlib.util\n"
    "import pytest\n\n"
    '_HAS_NATS_CORE = importlib.util.find_spec("nats_core") is not None\n'
    "pytestmark = pytest.mark.skipif(\n"
    '    not _HAS_NATS_CORE, reason="nats_core (memory write dep) not installed"\n'
    ")\n\n\n"
    "def test_colons_and_hyphens_become_underscores():\n"
    "    assert True\n"
)
JARVIS_SKIPGUARD_FIXTURE = {
    "tests/test_fleet_memory_payloads.py": JARVIS_TEST_PAYLOADS,
}


def test_dc05_skipguard_jarvis_variant_weakens_the_module_guard_and_nothing_else():
    """The jarvis anchor variant of R-DC05-skipguard: weaken the module-level nats_core skip-guard
    to always-skip (True or not _HAS_NATS_CORE). The unique per-module docstring anchors the file;
    the edit targets the one module-level skipif within it."""
    module = "tests/test_fleet_memory_payloads.py"
    result = inject(dict(JARVIS_SKIPGUARD_FIXTURE), "R-DC05-skipguard")

    assert result.dc_class == "DC-05"
    assert result.changed_files == [module]
    mutated = result.mutated_files[module]
    assert "pytest.mark.skipif(True or not _HAS_NATS_CORE" in mutated
    # the _HAS_NATS_CORE definition line is untouched (only the pytestmark predicate weakened)
    assert '_HAS_NATS_CORE = importlib.util.find_spec("nats_core") is not None' in mutated
    assert module in result.finding["locus"]


# --- forge per-repo anchor variant (R-DC05-skipguard) — v4 leg B3, SPIKE-GATED -------
# Verbatim git-adapter seam-test construct lifted from forge tests/forge/adapters/git/
# test_operations.py @ 34b17d0 (TASK-GCI-006): _HAS_GIT = shutil.which("git") is not None, and two
# @pytest.mark.skipif(not _HAS_GIT, reason="git binary not available") seam guards. The variant
# plants the SAME DC-05 skip-guard-defeat as guardkit's IMPORTS_AVAILABLE / jarvis's _HAS_NATS_CORE
# weakens, in forge's own dependency-guard vocabulary. The exact skipif string is unique across the
# forge tree, so it anchors directly (guardkit-variant style). SPIKE-GATED: the forge per-recipe
# test-command pin + control-green x2 are unproven — this fixture proves the ANCHOR matches the real
# code shape (the source-recipe half), not that the regeneration bridge divergence was run.
FORGE_GIT_OPERATIONS = (
    '"""Unit + seam tests for ``forge.adapters.git.operations`` (TASK-GCI-006)."""\n\n'
    "import shutil\n"
    "import pytest\n\n"
    '_GIT = shutil.which("git")\n'
    "_HAS_GIT = _GIT is not None\n\n\n"
    "@pytest.mark.seam\n"
    '@pytest.mark.skipif(not _HAS_GIT, reason="git binary not available")\n'
    "@pytest.mark.asyncio\n"
    "async def test_seam_prepare_worktree_and_commit_against_real_git():\n"
    "    assert True\n\n\n"
    '@pytest.mark.skipif(not _HAS_GIT, reason="git binary not available")\n'
    "def test_seam_remove_missing_worktree_is_noop():\n"
    "    assert True\n"
)
FORGE_SKIPGUARD_FIXTURE = {
    "tests/forge/adapters/git/test_operations.py": FORGE_GIT_OPERATIONS,
}


def test_dc05_skipguard_forge_variant_weakens_the_git_guard_and_nothing_else():
    """The forge anchor variant of R-DC05-skipguard: weaken the _HAS_GIT git-binary skip-guard to
    always-skip (True or not _HAS_GIT). The unique skipif string anchors the file; BOTH occurrences
    of the decorator weaken (re.subn replaces all; min_count=1 requires at least one)."""
    module = "tests/forge/adapters/git/test_operations.py"
    result = inject(dict(FORGE_SKIPGUARD_FIXTURE), "R-DC05-skipguard")

    assert result.dc_class == "DC-05"
    assert result.changed_files == [module]
    mutated = result.mutated_files[module]
    assert mutated.count("pytest.mark.skipif(True or not _HAS_GIT") == 2
    assert "pytest.mark.skipif(not _HAS_GIT" not in mutated  # every guard weakened
    # the _HAS_GIT definition line is untouched (only the skipif predicates weakened)
    assert "_HAS_GIT = _GIT is not None" in mutated
    assert module in result.finding["locus"]


def test_dc05_skipguard_variants_are_mutually_exclusive_across_disjoint_trees():
    """First-unique-match across the THREE disjoint repo trees: the guardkit fixture triggers the
    guardkit variant, the jarvis fixture the jarvis variant, the forge fixture the forge variant —
    each names a different locus and no repo's anchor is present in another's tree."""
    gk = inject(dict(FIXTURES["R-DC05-skipguard"]), "R-DC05-skipguard")
    jv = inject(dict(JARVIS_SKIPGUARD_FIXTURE), "R-DC05-skipguard")
    fg = inject(dict(FORGE_SKIPGUARD_FIXTURE), "R-DC05-skipguard")
    assert "test_seeding.py" in gk.finding["locus"]
    assert "test_fleet_memory_payloads.py" in jv.finding["locus"]
    assert "test_operations.py" in fg.finding["locus"]
    loci = {gk.finding["locus"], jv.finding["locus"], fg.finding["locus"]}
    assert len(loci) == 3  # three distinct loci, one per repo variant
    assert len({tuple(gk.changed_files), tuple(jv.changed_files), tuple(fg.changed_files)}) == 3


def test_dc05_skipguard_raises_loudly_when_no_variant_anchors():
    """When neither per-repo anchor is present, _first_anchor re-raises AnchorNotFound loudly
    (never a silent no-op) and names every variant it tried."""
    with pytest.raises(AnchorNotFound) as exc:
        inject({"tests/unrelated.py": "def test_x():\n    assert True\n"}, "R-DC05-skipguard")
    assert "no per-repo anchor variant matched" in str(exc.value)


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
