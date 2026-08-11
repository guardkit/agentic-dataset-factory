"""Spec §6 (Enum row) acceptance: write-path validation accepts ``source: harvest``
and still rejects ``source: bogus`` — via the same GOAL-parsed valid_values lookup
the lift replicates (write_output step 9)."""

from pathlib import Path

import pytest

from domain_config.parser import parse_goal_md

GOAL = Path(__file__).parent.parent / "domains" / "product-owner" / "GOAL.md"


@pytest.fixture(scope="module")
def schema_lookup():
    goal = parse_goal_md(GOAL)
    return {f.field: f.valid_values for f in goal.metadata_schema if f.valid_values}


def test_source_row_carries_harvest_and_flywheel(schema_lookup):
    assert "source" in schema_lookup, "GOAL Metadata Schema must constrain 'source'"
    values = schema_lookup["source"]
    assert "synthetic" in values
    assert "harvest" in values, "spec §3: the harvest enum value must be legal"
    assert "flywheel" in values, "spec §3: flywheel reserved-with-named-producer"


def test_source_bogus_still_rejected(schema_lookup):
    assert "bogus" not in schema_lookup["source"]


def test_shape_aware_routing_note_present_and_extractable():
    raw = GOAL.read_text()
    assert "Shape-aware criteria routing" in raw, "gate-3 precondition (spec §5.4)"
    import re

    m = re.search(r"^### Shape-aware criteria routing.*?(?=^#{2,3} |\Z)", raw, re.M | re.S)
    assert m and "ENRICHMENT_LEAK" in m.group(0), "the routing block must be extractable for the Coach-prompt append"
