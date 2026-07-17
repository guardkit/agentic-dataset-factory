"""DCL capability-language dataset domain — code half (G3 lane, 2026-07-17).

Mirrors the ``src/qav`` blueprint for a new corpus unit: the deterministic truth source is
the **DCL compiler** (vendored WASM @ pin ``4f9fbe56``), not a model. Two row modes —
``dcl_author`` (brief → compiler-clean capability, direct) and ``dcl_repair`` (broken +
real diagnostics → corrected capability, reasoning) — with hold-out contamination discipline
enforced in code against the four frozen ``dcl-heldout`` exam capabilities.

This package is mechanism + tests. A generation run wires an OpenAI-compatible endpoint via
``domains/dcl-capability-language/agent-config.draft.yaml``; tests use local stub clients —
ZERO real model calls.
"""

from __future__ import annotations

from dcl.checker import COMPILER_PIN, CompileResult, compile, compiles_clean
from dcl.contamination import ContaminationError, assert_clean, check_contamination
from dcl.contracts import (
    DOMAIN,
    MODES,
    SPLITS,
    SYSTEM_PROMPT,
    TYPES,
    VOCAB_PIN,
    RowValidationError,
    build_author_row,
    build_repair_row,
    validate_row,
)
from dcl.recipes import RECIPES, AnchorNotFound, apply_recipe, verify_breaks

__all__ = [
    "COMPILER_PIN",
    "VOCAB_PIN",
    "DOMAIN",
    "MODES",
    "SPLITS",
    "TYPES",
    "SYSTEM_PROMPT",
    "CompileResult",
    "compile",
    "compiles_clean",
    "RECIPES",
    "AnchorNotFound",
    "apply_recipe",
    "verify_breaks",
    "ContaminationError",
    "assert_clean",
    "check_contamination",
    "RowValidationError",
    "build_author_row",
    "build_repair_row",
    "validate_row",
]
