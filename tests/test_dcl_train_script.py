"""Host-side tests for domains/dcl-capability-language/train_dcl_qwen3.py.

These verify ONLY what must hold on the host without any ML deps or a GPU: the heavy
imports (unsloth/torch/trl/transformers/datasets) are DEFERRED into functions, so the
module compiles and ``--help`` runs dep-free. No training is invoked.
"""

from __future__ import annotations

import py_compile
import subprocess
import sys
from pathlib import Path

_SCRIPT = (Path(__file__).resolve().parents[1]
           / "domains" / "dcl-capability-language" / "train_dcl_qwen3.py")


def test_script_exists():
    assert _SCRIPT.is_file(), f"trainer script missing: {_SCRIPT}"


def test_py_compile_passes_without_ml_deps():
    # py_compile must succeed on the host — proves heavy imports are deferred, not top-level.
    py_compile.compile(str(_SCRIPT), doraise=True)


def test_help_exits_zero_and_names_the_base_model():
    proc = subprocess.run(
        [sys.executable, str(_SCRIPT), "--help"],
        capture_output=True, text=True, timeout=60,
    )
    assert proc.returncode == 0, f"--help exit {proc.returncode}; stderr:\n{proc.stderr}"
    out = proc.stdout
    # The default base model must be discoverable from --help alone.
    assert "Qwen/Qwen3-4B-Instruct-2507" in out, out
    # Key flags surfaced.
    for flag in ("--output-dir", "--max-seq-length", "--eval-path", "--skip-export",
                 "--base-model"):
        assert flag in out, f"{flag} not in --help output:\n{out}"


def test_output_dir_is_required():
    # --output-dir is required: invoking with no args must fail (argparse exit 2), not run.
    proc = subprocess.run(
        [sys.executable, str(_SCRIPT)],
        capture_output=True, text=True, timeout=60,
    )
    assert proc.returncode != 0
    assert "output-dir" in (proc.stderr + proc.stdout).lower()
