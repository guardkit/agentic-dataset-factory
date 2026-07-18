"""Brief seed bank validity — 200 briefs, unique ids, none hold-out contaminated, and every
render compiles clean against the real DCL compiler."""

from __future__ import annotations

import collections
import shutil

import pytest

from dcl import checker, contamination
from dcl.briefs import LIFECYCLE_STEP_KINDS, load_briefs, render_reference_capability

requires_node = pytest.mark.skipif(shutil.which("node") is None, reason="node not on PATH")

BRIEF_COUNT = 200
BRIEFS = load_briefs(enforce_denylist=False)  # load raw; denylist asserted separately below


def test_brief_bank_has_unique_deterministic_ids():
    assert len(BRIEFS) == BRIEF_COUNT
    ids = [b.id for b in BRIEFS]
    assert len(set(ids)) == BRIEF_COUNT
    assert ids == [f"brief-{i:03d}" for i in range(1, BRIEF_COUNT + 1)]


def test_briefs_name_the_required_structure():
    kinds = {"human", "system", "agent", "scheduled_process"}
    effects = {"persistence", "notification", "invocation", "tool"}
    for b in BRIEFS:
        assert b.actor_kind in kinds
        assert b.effect_kind in effects
        # intent shapes may carry 0..5 fields now; the emitted event always carries a payload.
        assert b.event_fields
        assert b.success_outcome and b.failure_outcome and b.policy_family and b.concerns
        for s in b.lifecycle_steps:
            assert s.kind in LIFECYCLE_STEP_KINDS


def test_no_brief_is_holdout_contaminated():
    for b in BRIEFS:
        assert contamination.scan(b.brief_text) == [], f"{b.id} paragraph tripped the denylist"
        assert contamination.scan(render_reference_capability(b)) == [], f"{b.id} render tripped"


def test_load_briefs_enforces_denylist():
    # enforce_denylist=True path must succeed on the clean bank (no raise).
    assert len(load_briefs(enforce_denylist=True)) == BRIEF_COUNT


def test_brief_bank_diversity_coverage():
    """The grown bank spans the required diversity envelope (§ growth requirements)."""
    assert len({b.domain for b in BRIEFS}) >= 25
    # all four verified actor kinds + all four effect kinds present.
    assert {b.actor_kind for b in BRIEFS} == {"human", "system", "agent", "scheduled_process"}
    assert {b.effect_kind for b in BRIEFS} == {"persistence", "notification", "invocation", "tool"}
    # all nine verified policy families exercised (incl. confidence, unused by the first 50).
    families = {b.policy_family for b in BRIEFS}
    assert families == {
        "reliability", "availability", "scalability", "performance", "security",
        "compliance", "governance", "data_protection", "confidence",
    }
    # intent-shape field counts span 0..5; event payloads span 2..5.
    field_counts = {len(b.fields) for b in BRIEFS}
    assert 0 in field_counts and 5 in field_counts
    assert min(len(b.event_fields) for b in BRIEFS) == 2
    assert max(len(b.event_fields) for b in BRIEFS) >= 5
    # mixed field types incl. List<T>/Money/Email/Date appear somewhere.
    all_types = {f.type for b in BRIEFS for f in b.fields}
    assert {"Money", "Email", "Date", "List<Text>"} <= all_types
    # lifecycles range 2..4 states, exercising decision + waiting step kinds.
    state_counts = {2 + len(b.lifecycle_steps) for b in BRIEFS}
    assert state_counts >= {2, 3, 4}
    step_kinds = {s.kind for b in BRIEFS for s in b.lifecycle_steps}
    assert {"active", "decision", "waiting"} <= step_kinds
    # some multi-outcome capabilities (a third declared outcome).
    assert sum(1 for b in BRIEFS if b.extra_outcome) >= 10


def test_multi_outcome_and_multistate_briefs_declare_extra_structure():
    """Multi-outcome renders declare the third outcome + cause it; multi-state renders add
    the intermediate steps — proven against the real compiler for a representative sample."""
    multi_out = [b for b in BRIEFS if b.extra_outcome][:3]
    for b in multi_out:
        cap = render_reference_capability(b)
        assert f"    {b.extra_outcome}\n" in cap  # declared in outcomes
        assert f"unresolved then {b.extra_outcome}" in cap  # caused in when
    multi_state = [b for b in BRIEFS if len(b.lifecycle_steps) >= 1][:3]
    for b in multi_state:
        cap = render_reference_capability(b)
        for s in b.lifecycle_steps:
            assert f"step {s.name} {{" in cap


@requires_node
@pytest.mark.parametrize("brief", BRIEFS, ids=[b.id for b in BRIEFS])
def test_every_brief_renders_to_a_compiling_capability(brief):
    result = checker.compile(render_reference_capability(brief))
    assert result.ok, f"{brief.id} render failed: {result.error_codes}"
