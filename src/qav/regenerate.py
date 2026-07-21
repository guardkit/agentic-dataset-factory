"""Interpreter-bridged bundle regenerator — the third generation-run seam (PLAN §2).

Satisfies the :class:`qav.injector.BundleRegenerator` Protocol (``regenerate(worktree) -> dict``)
that ``qav.generate`` drives, but WITHOUT importing guardkit into the factory process: the
agentic-dataset-factory ``.venv`` cannot import guardkit (verified in the spike receipt), so this
regenerator shells out to a bridge script run under the **guardkit-importing interpreter**
(``config.interpreters['guardkit']`` — the only venv on the box that imports guardkit). The bridge
runs guardkit ``CoachValidator.gather_evidence`` over the mutated worktree and serializes the
``CoachEvidenceBundle`` back as JSON.

**The two interpreters (the SIBTESTENV01 seam, wired honestly).** ``gather_evidence`` runs the
worktree's test suite as a *subprocess* ``<venv_python> -m pytest`` pinned to the ``venv_python``
passed to ``CoachValidator.__init__`` (guardkit ``_pytest_interpreter`` /
``coach_verification._resolve_venv_python`` — an explicit on-disk interpreter path wins). So:

* the **bridge process** always runs under the guardkit-importing interpreter (only that venv
  imports guardkit); and
* the **target repo's pytest** runs under that repo's own interpreter,
  ``config.interpreters[repo]``, threaded in as ``venv_python``.

For a guardkit-repo task both are guardkit's venv. For a foreign repo (study-tutor / forge) the
bridge still runs under guardkit's venv while pytest runs under the foreign interpreter — exactly
the sibling-repo interpreter case guardkit designed ``venv_python`` for (TASK-FIX-SIBTESTENV01);
no guardkit change is needed. The repo is derived from the worktree path
(``<scratch_dir>/<repo>/<task>/<recipe>`` — how ``qav.generate._materialize_worktree`` lays it out)
so the Protocol stays single-argument.

Zero real model / seat / GPU work happens here or in tests: tests drive this against a FAKE bridge
executable, never real guardkit. The bundle is validated against the pinned bundle schema
(``contracts.validate_bundle`` — the ``PINNED_BUNDLE_SCHEMA_SHA`` field set) before it is returned,
and any non-zero bridge exit is surfaced loudly (never a silent skip).
"""

from __future__ import annotations

import json
import logging
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from qav.contracts import PINNED_BUNDLE_SCHEMA_SHA, validate_bundle

logger = logging.getLogger(__name__)

# The bridge script lives beside the run driver (it imports guardkit; it is never imported by the
# factory process — it is exec'd under the guardkit-importing interpreter).
DEFAULT_BRIDGE_SCRIPT = (
    Path(__file__).resolve().parents[2] / "domains" / "qa-verifier" / "qav_regenerate_bridge.py"
)


def resolve_guardkit_interpreter(interpreters: dict[str, str]) -> str:
    """Return the interpreter that imports guardkit — ``interpreters['guardkit']``, the only venv
    on the box verified to import guardkit (spike receipt §2). Raises loudly if absent."""
    gk = interpreters.get("guardkit")
    if not gk:
        raise RuntimeError(
            "no 'guardkit' entry in interpreters config — the regenerator bridge must run under "
            "the guardkit-importing interpreter (the only venv that imports guardkit); "
            f"configured interpreters: {sorted(interpreters)}"
        )
    return gk


@dataclass
class SubprocessBridgeRegenerator:
    """A :class:`qav.injector.BundleRegenerator` that bridges to guardkit via a subprocess.

    ``interpreters`` maps ``repo -> interpreter`` (``config.interpreters``); ``scratch_dir`` is the
    worktree root the repo/task is derived from; ``guardkit_interpreter`` runs the bridge script.
    """

    interpreters: dict[str, str]
    scratch_dir: str | Path
    guardkit_interpreter: str
    bridge_script: str | Path = field(default=DEFAULT_BRIDGE_SCRIPT)
    task_id_default: str = "qav-seeded"
    timeout_seconds: float = 1800.0
    bundle_schema_sha: str = PINNED_BUNDLE_SCHEMA_SHA
    # L2 deep-regeneration bridge config (render-collapse layers 1+2). ``regen_task_type`` selects
    # the guardkit quality-gate profile whose required gates match the materialized record (layer 1
    # — reach the worktree tests via the SANCTIONED profile, never skip_arch_review). ``test_commands``
    # pins ``repo -> pytest command`` so the oracle never misdetects the stack (layer 2). Both are
    # threaded to the bridge CLI; ``None``/absent => the bridge's pre-fix default (feature profile +
    # guardkit auto-detection).
    regen_task_type: str | None = None
    test_commands: dict[str, str] = field(default_factory=dict)

    @classmethod
    def from_config(cls, config: Any, *, bridge_script: str | Path | None = None) -> "SubprocessBridgeRegenerator":
        """Build from a ``qav.generate.GenerateConfig`` — threads ``config.interpreters`` and
        ``config.scratch_dir`` in, resolves the guardkit-importing interpreter, and carries the
        deep-regeneration profile-gate (``regen_task_type``) + per-repo stack pin (``test_commands``)
        + independent-test timeout (``regen_test_timeout``)."""
        interpreters = {str(k): str(v) for k, v in dict(config.interpreters or {}).items()}
        return cls(
            interpreters=interpreters,
            scratch_dir=config.scratch_dir,
            guardkit_interpreter=resolve_guardkit_interpreter(interpreters),
            bridge_script=bridge_script or DEFAULT_BRIDGE_SCRIPT,
            bundle_schema_sha=getattr(config, "bundle_schema_sha", PINNED_BUNDLE_SCHEMA_SHA),
            timeout_seconds=float(getattr(config, "regen_test_timeout", 1800) or 1800),
            regen_task_type=getattr(config, "regen_task_type", None),
            test_commands={
                str(k): str(v) for k, v in dict(getattr(config, "test_commands", {}) or {}).items()
            },
        )

    def _repo_task(self, worktree: Path) -> tuple[str, str]:
        """Derive ``(repo, task)`` from a materialised worktree path relative to ``scratch_dir``
        (``<scratch_dir>/<repo>/<task>/<recipe>``)."""
        scratch = Path(self.scratch_dir).resolve()
        try:
            rel = worktree.resolve().relative_to(scratch)
        except ValueError as exc:
            raise RuntimeError(
                f"worktree {worktree} is not under scratch_dir {scratch} — cannot derive repo/task "
                "for interpreter selection"
            ) from exc
        parts = rel.parts
        if len(parts) < 2:
            raise RuntimeError(
                f"worktree path {rel!s} under scratch does not encode <repo>/<task>/<recipe>"
            )
        return parts[0], parts[1]

    def regenerate(self, worktree: Path) -> dict[str, Any]:
        """Run the bridge over ``worktree`` and return the validated CoachEvidenceBundle dict."""
        worktree = Path(worktree)
        repo, task = self._repo_task(worktree)
        target_interpreter = self.interpreters.get(repo)
        if not target_interpreter:
            raise RuntimeError(
                f"no interpreter configured for repo {repo!r} (interpreters: "
                f"{sorted(self.interpreters)}) — cannot regenerate {worktree}"
            )

        with tempfile.TemporaryDirectory(prefix="qav-regen-") as tmp:
            out_path = Path(tmp) / "bundle.json"
            cmd = [
                str(self.guardkit_interpreter),
                str(self.bridge_script),
                "--worktree", str(worktree),
                "--task-id", task or self.task_id_default,
                "--venv-python", str(target_interpreter),
                "--schema-sha", str(self.bundle_schema_sha),
                "--out", str(out_path),
            ]
            # LAYER 1: the profile-gate task_type (reach the worktree tests via the sanctioned
            # profile whose required gates match the record; NOT skip_arch_review).
            if self.regen_task_type:
                cmd += ["--task-type", str(self.regen_task_type)]
            # LAYER 2: the per-repo pinned pytest command (no stack misdetect). Absent => the
            # bridge lets guardkit auto-detect (pre-fix behaviour, loud in the log).
            test_command = self.test_commands.get(repo)
            if test_command:
                cmd += ["--test-command", str(test_command)]
            cmd += ["--test-timeout", str(int(self.timeout_seconds))]
            logger.info(
                "REGEN bridge: repo=%s task=%s worktree=%s venv_python=%s task_type=%s "
                "test_command=%r (bridge under %s)",
                repo, task, worktree, target_interpreter, self.regen_task_type,
                test_command, self.guardkit_interpreter,
            )
            try:
                proc = subprocess.run(cmd, capture_output=True, text=True, timeout=self.timeout_seconds)
            except subprocess.TimeoutExpired as exc:
                raise RuntimeError(
                    f"regenerator bridge TIMED OUT after {self.timeout_seconds}s for {repo}/{task} "
                    f"at {worktree}"
                ) from exc
            if proc.returncode != 0:
                raise RuntimeError(
                    f"regenerator bridge FAILED (rc={proc.returncode}) for {repo}/{task} at {worktree}\n"
                    f"cmd: {' '.join(cmd)}\n"
                    f"stderr:\n{proc.stderr.strip()}\n"
                    f"stdout:\n{proc.stdout.strip()}"
                )
            if not out_path.exists():
                raise RuntimeError(
                    f"regenerator bridge produced no bundle at {out_path} (rc=0) for {repo}/{task}; "
                    f"stderr:\n{proc.stderr.strip()}"
                )
            try:
                bundle = json.loads(out_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError as exc:
                raise RuntimeError(
                    f"regenerator bridge wrote invalid JSON for {repo}/{task}: {exc}"
                ) from exc

        # Validate against the pinned bundle schema (the PINNED_BUNDLE_SCHEMA_SHA field set) —
        # a bridge that returns drift is a loud failure, not a written row.
        validate_bundle(bundle)
        return bundle
