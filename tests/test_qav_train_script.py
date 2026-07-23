"""Host-side tests for domains/qa-verifier/train_qav.py.

These verify ONLY what must hold on the host without ML deps or a GPU: the heavy imports
(unsloth/torch/trl/transformers/datasets) are DEFERRED into main(), so the module compiles and
``--help`` runs dep-free. No training is invoked.
"""

from __future__ import annotations

import py_compile
import subprocess
import sys
from pathlib import Path

_SCRIPT = (Path(__file__).resolve().parents[1]
           / "domains" / "qa-verifier" / "train_qav.py")


def test_script_exists():
    assert _SCRIPT.is_file(), f"trainer script missing: {_SCRIPT}"


def test_py_compile_passes_without_ml_deps():
    py_compile.compile(str(_SCRIPT), doraise=True)


def test_help_exits_zero_and_names_the_base_model():
    proc = subprocess.run([sys.executable, str(_SCRIPT), "--help"],
                          capture_output=True, text=True, timeout=60)
    assert proc.returncode == 0, f"--help exit {proc.returncode}; stderr:\n{proc.stderr}"
    out = proc.stdout
    assert "unsloth/gemma-4-26B-A4B-it" in out, out
    for flag in ("--output-dir", "--max-seq-length", "--eval-path", "--skip-export",
                 "--export-gguf", "--chat-template", "--base-model"):
        assert flag in out, f"{flag} not in --help output:\n{out}"


def test_output_dir_is_required():
    proc = subprocess.run([sys.executable, str(_SCRIPT)],
                          capture_output=True, text=True, timeout=60)
    assert proc.returncode != 0
    assert "output-dir" in (proc.stderr + proc.stdout).lower()


def test_thinking_template_is_refused_by_choices():
    # gemma-4-thinking is a valid argparse choice but the run aborts on it (catch #1). At the
    # host we can only confirm argparse accepts the choice and rejects a bogus one.
    proc = subprocess.run(
        [sys.executable, str(_SCRIPT), "--output-dir", "/tmp/x", "--chat-template", "bogus"],
        capture_output=True, text=True, timeout=60)
    assert proc.returncode != 0
    assert "chat-template" in (proc.stderr + proc.stdout).lower()
