"""Brief seed bank validity — 50 briefs, unique ids, none hold-out contaminated, and every
render compiles clean against the real DCL compiler."""

from __future__ import annotations

import shutil

import pytest

from dcl import checker, contamination
from dcl.briefs import load_briefs, render_reference_capability

requires_node = pytest.mark.skipif(shutil.which("node") is None, reason="node not on PATH")

BRIEFS = load_briefs(enforce_denylist=False)  # load raw; denylist asserted separately below


def test_fifty_briefs_with_unique_deterministic_ids():
    assert len(BRIEFS) == 50
    ids = [b.id for b in BRIEFS]
    assert len(set(ids)) == 50
    assert ids == [f"brief-{i:03d}" for i in range(1, 51)]


def test_briefs_name_the_required_structure():
    kinds = {"human", "system", "agent", "scheduled_process"}
    effects = {"persistence", "notification", "invocation", "tool"}
    for b in BRIEFS:
        assert b.actor_kind in kinds
        assert b.effect_kind in effects
        assert b.fields and b.event_fields
        assert b.success_outcome and b.failure_outcome and b.policy_family and b.concerns


def test_no_brief_is_holdout_contaminated():
    for b in BRIEFS:
        assert contamination.scan(b.brief_text) == [], f"{b.id} paragraph tripped the denylist"
        assert contamination.scan(render_reference_capability(b)) == [], f"{b.id} render tripped"


def test_load_briefs_enforces_denylist():
    # enforce_denylist=True path must succeed on the clean bank (no raise).
    assert len(load_briefs(enforce_denylist=True)) == 50


@requires_node
@pytest.mark.parametrize("brief", BRIEFS, ids=[b.id for b in BRIEFS])
def test_every_brief_renders_to_a_compiling_capability(brief):
    result = checker.compile(render_reference_capability(brief))
    assert result.ok, f"{brief.id} render failed: {result.error_codes}"
