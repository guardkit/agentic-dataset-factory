#!/usr/bin/env python
"""Regenerator bridge — runs guardkit ``CoachValidator.gather_evidence`` over a mutated worktree
and serializes the ``CoachEvidenceBundle`` to JSON.

This script is EXEC'd by ``qav.regenerate.SubprocessBridgeRegenerator`` under the
**guardkit-importing interpreter** (``config.interpreters['guardkit']``). It is never imported by
the factory process (which cannot import guardkit) and never touched by the unit suite (tests use
a fake bridge). The target repo's pytest substrate is pinned to the repo's own interpreter via
``--venv-python`` (``CoachValidator(venv_python=...)`` — the SIBTESTENV01 seam): the bridge runs
under guardkit's venv while the worktree tests run under the target repo's venv.

Usage (constructed by the regenerator, not run by hand):

    <guardkit-venv-python> qav_regenerate_bridge.py \
        --worktree <mutated-scratch-worktree> --task-id <task> \
        --venv-python <target-repo-interpreter> --schema-sha <pinned> --out <bundle.json>
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def main(argv: list[str] | None = None) -> int:  # pragma: no cover - generation run (real guardkit)
    ap = argparse.ArgumentParser(description="guardkit gather_evidence bridge for QAV regeneration")
    ap.add_argument("--worktree", required=True, help="mutated scratch worktree to gather evidence over")
    ap.add_argument("--task-id", required=True, help="task id (stamped into the gathered bundle)")
    ap.add_argument(
        "--venv-python", required=True,
        help="the TARGET repo's interpreter — pins the worktree pytest substrate (SIBTESTENV01)",
    )
    ap.add_argument("--schema-sha", default="", help="pinned bundle schema sha (provenance)")
    ap.add_argument("--out", required=True, help="path to write the serialized bundle JSON")
    args = ap.parse_args(argv)

    # Imported here (not at module top) so the fake-bridge tests never need guardkit and the
    # ImportError surfaces with the honest cause if the wrong interpreter is used.
    from guardkit.orchestrator.quality_gates.coach_validator import CoachValidator

    validator = CoachValidator(
        worktree_path=args.worktree,
        task_id=args.task_id,
        venv_python=args.venv_python,  # target repo interpreter pins the worktree pytest subprocess
        in_autobuild_context=False,
    )
    bundle = validator.gather_evidence(
        task_id=args.task_id,
        turn=1,
        task={"acceptance_criteria": []},
    )
    Path(args.out).write_text(json.dumps(bundle.to_dict(), ensure_ascii=False), encoding="utf-8")
    return 0


if __name__ == "__main__":  # pragma: no cover - generation run
    sys.exit(main())
