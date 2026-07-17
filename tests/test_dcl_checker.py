"""DCL compiler adapter tests — the deterministic truth source.

Skeleton compiles clean / a broken capability is rejected with its DCL_* code / a missing
``node`` refuses LOUDLY (never a silent "assume it compiles").
"""

from __future__ import annotations

import shutil

import pytest

from dcl import checker

requires_node = pytest.mark.skipif(shutil.which("node") is None, reason="node not on PATH")

VALID = """language dcl 1.0

actor Customer is human

shape OrderInput {
  orderId: Uuid required
}

capability PlaceOrder {
  intent OrderInput from Customer
  outcome Accepted
  when {
    always Accepted
  }
}
"""

BROKEN = VALID.replace("actor Customer is human", "actor Customer is machine")


@requires_node
def test_skeleton_compiles_clean():
    result = checker.compile(VALID)
    assert result.ok
    assert result.error_count == 0
    assert result.error_codes == []


@requires_node
def test_broken_capability_is_rejected():
    result = checker.compile(BROKEN)
    assert not result.ok
    assert result.error_count >= 1
    assert "DCL_SEM_ACTOR_KIND_UNKNOWN" in result.error_codes


@requires_node
def test_compiles_clean_helper():
    assert checker.compiles_clean(VALID)
    assert not checker.compiles_clean(BROKEN)


@requires_node
def test_diagnostics_json_is_deterministic():
    a = checker.compile(BROKEN).diagnostics_json()
    b = checker.compile(BROKEN).diagnostics_json()
    assert a == b
    assert "DCL_SEM_ACTOR_KIND_UNKNOWN" in a


def test_node_missing_refuses_loudly(monkeypatch):
    monkeypatch.setattr(checker.shutil, "which", lambda _name: None)
    with pytest.raises(checker.NodeUnavailableError):
        checker.compile(VALID)
