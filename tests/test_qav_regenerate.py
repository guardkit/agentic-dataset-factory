"""QAV interpreter-bridged regenerator tests (seam (c), PLAN §2).

Zero real guardkit / model / seat / network: drives ``SubprocessBridgeRegenerator`` against a
FAKE bridge executable that records the argv it received (so per-repo interpreter selection is
asserted) and emits a scripted bundle / failure. Covers: repo->interpreter selection from the
worktree path, the guardkit-importing interpreter running the bridge, pinned-schema validation of
the returned bundle, and loud surfacing of a non-zero bridge exit / missing-output / bad-JSON /
schema-drift.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

from qav.contracts import RowValidationError
from qav.regenerate import SubprocessBridgeRegenerator, resolve_guardkit_interpreter

# A fake bridge: never imports guardkit. Records its argv + interpreter to $FAKE_BRIDGE_LOG, then
# behaves per $FAKE_BRIDGE_MODE. Run under sys.executable (our stand-in guardkit interpreter).
_FAKE_BRIDGE = '''\
import argparse, json, os, sys
from pathlib import Path

ap = argparse.ArgumentParser()
ap.add_argument("--worktree", required=True)
ap.add_argument("--task-id", required=True)
ap.add_argument("--venv-python", required=True)
ap.add_argument("--schema-sha", default="")
ap.add_argument("--out", required=True)
a = ap.parse_args()

log = os.environ.get("FAKE_BRIDGE_LOG")
if log:
    with open(log, "a", encoding="utf-8") as fh:
        fh.write(json.dumps({
            "interpreter": sys.executable,
            "worktree": a.worktree,
            "task_id": a.task_id,
            "venv_python": a.venv_python,
            "schema_sha": a.schema_sha,
        }) + "\\n")

mode = os.environ.get("FAKE_BRIDGE_MODE", "ok")
if mode == "fail":
    sys.stderr.write("guardkit CoachValidator unavailable — boom\\n")
    sys.exit(3)
if mode == "noout":
    sys.exit(0)  # rc=0 but writes nothing
if mode == "badjson":
    Path(a.out).write_text("{not valid json", encoding="utf-8")
    sys.exit(0)
if mode == "drift":
    Path(a.out).write_text(json.dumps({"honesty": {}, "not_a_pinned_field": 1}), encoding="utf-8")
    sys.exit(0)
# ok
Path(a.out).write_text(
    json.dumps({"honesty": {"discrepancies": []}, "gathering_status": "complete"}),
    encoding="utf-8",
)
sys.exit(0)
'''


@pytest.fixture
def bridge(tmp_path) -> Path:
    p = tmp_path / "fake_bridge.py"
    p.write_text(_FAKE_BRIDGE, encoding="utf-8")
    return p


@pytest.fixture
def log_path(tmp_path, monkeypatch) -> Path:
    lp = tmp_path / "bridge.log"
    monkeypatch.setenv("FAKE_BRIDGE_LOG", str(lp))
    return lp


def _regen(tmp_path, bridge, interpreters=None):
    return SubprocessBridgeRegenerator(
        interpreters=interpreters or {
            "guardkit": "/interp/guardkit/python",
            "study_tutor": "/interp/study/python",
            "forge": "/interp/forge/python",
        },
        scratch_dir=str(tmp_path / "scratch"),
        guardkit_interpreter=sys.executable,  # runs the fake bridge
        bridge_script=bridge,
    )


def _worktree(tmp_path, repo, task, recipe="R-DC03-producer") -> Path:
    wt = tmp_path / "scratch" / repo / task / recipe
    wt.mkdir(parents=True, exist_ok=True)
    return wt


def _log_records(log_path: Path) -> list[dict]:
    return [json.loads(line) for line in log_path.read_text().splitlines()]


# --------------------------------------------------------------------------------------
# Happy path + interpreter selection.
# --------------------------------------------------------------------------------------
def test_regenerate_returns_validated_bundle(tmp_path, bridge, log_path, monkeypatch):
    monkeypatch.setenv("FAKE_BRIDGE_MODE", "ok")
    r = _regen(tmp_path, bridge)
    wt = _worktree(tmp_path, "guardkit", "TASK-QAV-004")
    bundle = r.regenerate(wt)
    assert bundle["gathering_status"] == "complete"
    assert bundle["honesty"] == {"discrepancies": []}


def test_target_interpreter_selected_per_repo(tmp_path, bridge, log_path, monkeypatch):
    monkeypatch.setenv("FAKE_BRIDGE_MODE", "ok")
    r = _regen(tmp_path, bridge)

    r.regenerate(_worktree(tmp_path, "guardkit", "TASK-A"))
    r.regenerate(_worktree(tmp_path, "study_tutor", "TASK-B"))
    r.regenerate(_worktree(tmp_path, "forge", "TASK-C"))

    recs = _log_records(log_path)
    by_task = {rec["task_id"]: rec for rec in recs}
    # venv_python is the TARGET repo's interpreter (SIBTESTENV01 seam) ...
    assert by_task["TASK-A"]["venv_python"] == "/interp/guardkit/python"
    assert by_task["TASK-B"]["venv_python"] == "/interp/study/python"
    assert by_task["TASK-C"]["venv_python"] == "/interp/forge/python"
    # ... while the bridge itself always runs under the guardkit-importing interpreter.
    assert all(rec["interpreter"] == sys.executable for rec in recs)


def test_task_id_derived_from_worktree_path(tmp_path, bridge, log_path, monkeypatch):
    monkeypatch.setenv("FAKE_BRIDGE_MODE", "ok")
    r = _regen(tmp_path, bridge)
    r.regenerate(_worktree(tmp_path, "guardkit", "TASK-BDDW-001"))
    assert _log_records(log_path)[0]["task_id"] == "TASK-BDDW-001"


# --------------------------------------------------------------------------------------
# Loud failure surfacing — never a silent skip.
# --------------------------------------------------------------------------------------
def test_nonzero_bridge_exit_is_loud(tmp_path, bridge, monkeypatch):
    monkeypatch.setenv("FAKE_BRIDGE_MODE", "fail")
    r = _regen(tmp_path, bridge)
    with pytest.raises(RuntimeError) as exc:
        r.regenerate(_worktree(tmp_path, "guardkit", "TASK-A"))
    assert "rc=3" in str(exc.value) and "boom" in str(exc.value)


def test_missing_output_is_loud(tmp_path, bridge, monkeypatch):
    monkeypatch.setenv("FAKE_BRIDGE_MODE", "noout")
    r = _regen(tmp_path, bridge)
    with pytest.raises(RuntimeError) as exc:
        r.regenerate(_worktree(tmp_path, "guardkit", "TASK-A"))
    assert "no bundle" in str(exc.value)


def test_bad_json_is_loud(tmp_path, bridge, monkeypatch):
    monkeypatch.setenv("FAKE_BRIDGE_MODE", "badjson")
    r = _regen(tmp_path, bridge)
    with pytest.raises(RuntimeError) as exc:
        r.regenerate(_worktree(tmp_path, "guardkit", "TASK-A"))
    assert "invalid JSON" in str(exc.value)


def test_schema_drift_bundle_is_rejected(tmp_path, bridge, monkeypatch):
    # A bundle carrying a non-pinned field must fail the pinned-schema validation loudly.
    monkeypatch.setenv("FAKE_BRIDGE_MODE", "drift")
    r = _regen(tmp_path, bridge)
    with pytest.raises(RowValidationError):
        r.regenerate(_worktree(tmp_path, "guardkit", "TASK-A"))


# --------------------------------------------------------------------------------------
# Wiring guards.
# --------------------------------------------------------------------------------------
def test_worktree_outside_scratch_is_loud(tmp_path, bridge):
    r = _regen(tmp_path, bridge)
    with pytest.raises(RuntimeError) as exc:
        r.regenerate(tmp_path / "elsewhere" / "repo" / "task" / "recipe")
    assert "not under scratch_dir" in str(exc.value)


def test_unconfigured_repo_interpreter_is_loud(tmp_path, bridge):
    r = _regen(tmp_path, bridge, interpreters={"guardkit": "/interp/guardkit/python"})
    with pytest.raises(RuntimeError) as exc:
        r.regenerate(_worktree(tmp_path, "study_tutor", "TASK-B"))
    assert "no interpreter configured for repo 'study_tutor'" in str(exc.value)


def test_resolve_guardkit_interpreter_requires_entry():
    assert resolve_guardkit_interpreter({"guardkit": "/x"}) == "/x"
    with pytest.raises(RuntimeError):
        resolve_guardkit_interpreter({"forge": "/y"})


def test_from_config_threads_interpreters_and_scratch():
    class _Cfg:
        interpreters = {"guardkit": "/g/py", "forge": "/f/py"}
        scratch_dir = "out/_scratch"
        bundle_schema_sha = "41a0ebe457"

    r = SubprocessBridgeRegenerator.from_config(_Cfg())
    assert r.guardkit_interpreter == "/g/py"
    assert r.interpreters == {"guardkit": "/g/py", "forge": "/f/py"}
    assert str(r.scratch_dir) == "out/_scratch"
