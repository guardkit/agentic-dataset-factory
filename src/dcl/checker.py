"""DCL compiler adapter — the deterministic truth source for the dcl domain.

Wraps the vendored WASM DCL compiler (``src/dcl/bin/dcl-check.mjs`` driving
``dcl.wasm`` @ pin ``4f9fbe56``) as a Python subprocess. This is the ONLY authority
on whether a ``.dcl`` capability compiles: every label the domain fixes (a repair
row's corrected text, an author row's accepted text) is verified here, never by a
model.

The adapter is offline and LLM-free — it shells out to ``node`` on a tempfile and
returns the compiler's JSON envelope. ``node`` absence is a LOUD refusal (never a
silent skip), mirroring the QAV ``GatherEvidenceRegenerator`` "raise loudly if
unconfigured" discipline: a generation run that cannot verify its labels must fail,
not emit unverified rows.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

# Vendored checker location (byte-identical from fleet-evals, sha-verified on copy).
BIN_DIR = Path(__file__).resolve().parent / "bin"
CHECKER_MJS = BIN_DIR / "dcl-check.mjs"
COMPILER_PIN = "4f9fbe56"


class NodeUnavailableError(RuntimeError):
    """``node`` is not on PATH — the DCL compiler cannot run.

    Raised loudly rather than degrading to "assume it compiles": an unverifiable
    label is worse than a hard stop (the SIBTESTENV01 refuse-on-missing-substrate
    lesson).
    """


class CheckerError(RuntimeError):
    """The checker harness itself errored (exit 2 / non-JSON / missing wasm)."""


@dataclass(frozen=True)
class CompileResult:
    """The compiler's JSON envelope, normalized.

    Attributes mirror ``dcl-check.mjs``'s wire contract (which itself mirrors the
    real ``dcl validate --json`` CLI): ``ok`` (no error diagnostics), ``error_count``,
    and the full ``diagnostics`` list (each ``{severity, code, message, ...}``).
    """

    ok: bool
    error_count: int
    warning_count: int
    diagnostics: list[dict[str, Any]]
    raw: dict[str, Any]

    @property
    def error_codes(self) -> list[str]:
        """The ``DCL_*`` codes of the error-severity diagnostics, in order."""
        return [d.get("code", "") for d in self.diagnostics if d.get("severity") == "error"]

    def diagnostics_json(self) -> str:
        """The diagnostics list serialized deterministically for a repair-row prompt."""
        return json.dumps(self.diagnostics, indent=2, sort_keys=True, ensure_ascii=False)


def _node() -> str:
    node = shutil.which("node")
    if node is None:
        raise NodeUnavailableError(
            "`node` not found on PATH — the vendored DCL WASM compiler "
            f"({CHECKER_MJS}) cannot run. The compiler is the domain's deterministic "
            "truth source; refusing to emit unverified rows. Install Node (v18+) or "
            "run on a box that has it (the GB10 Spark carries node v24)."
        )
    return node


def compile(text: str, *, timeout: float = 60.0) -> CompileResult:
    """Compile raw ``.dcl`` ``text`` and return the compiler envelope.

    Writes ``text`` to a tempfile and runs ``node dcl-check.mjs <file>``. Exit 0 =
    ``ok:true``; exit 1 = compile failure (``ok:false``, ``error_count>0``); exit 2 =
    harness error → :class:`CheckerError`.
    """
    if not CHECKER_MJS.is_file():  # pragma: no cover - vendoring guard
        raise CheckerError(f"vendored checker missing: {CHECKER_MJS}")
    node = _node()
    with tempfile.NamedTemporaryFile(
        "w", suffix=".dcl", encoding="utf-8", delete=False
    ) as fh:
        fh.write(text)
        tmp_path = fh.name
    try:
        proc = subprocess.run(
            [node, str(CHECKER_MJS), tmp_path],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    finally:
        try:
            Path(tmp_path).unlink()
        except OSError:  # pragma: no cover
            pass

    if proc.returncode == 2:
        raise CheckerError(
            f"dcl-check.mjs harness error (exit 2): {proc.stdout.strip()} "
            f"{proc.stderr.strip()}"
        )
    try:
        env = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:  # pragma: no cover - harness contract
        raise CheckerError(
            f"dcl-check.mjs returned non-JSON (exit {proc.returncode}): "
            f"{proc.stdout[:200]!r}"
        ) from exc

    diagnostics = env.get("diagnostics") or []
    return CompileResult(
        ok=bool(env.get("ok")),
        error_count=int(env.get("errorCount", 0)),
        warning_count=int(env.get("warningCount", 0)),
        diagnostics=diagnostics,
        raw=env,
    )


def compiles_clean(text: str, *, timeout: float = 60.0) -> bool:
    """True iff ``text`` compiles with zero error diagnostics."""
    return compile(text, timeout=timeout).ok
