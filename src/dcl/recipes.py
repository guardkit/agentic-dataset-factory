"""DCL defect recipes — deterministic mutations that plant ONE compiler-rejected
defect into a known-green ``.dcl`` capability, for minting repair rows.

Each recipe is a pure ``(valid_dcl_text) -> broken_dcl_text`` transform grounded in the
compiler-verified closed vocabulary (``src/dcl/vocab-reference.md``) and the OBSERVED
zero-shot failure classes (see ``dcl-held-004``'s ``broken.dcl``: ``actor … is machine``,
``effect … is in_memory``). A recipe:

- raises :class:`AnchorNotFound` when its target shape is absent (never a silent no-op —
  the QAV injector discipline);
- changes the input by **exactly its one intended edit and nothing else** (single-line
  diff — the injector "NOTHING else" self-check);
- produces output that the REAL compiler REJECTS with the recipe's named ``DCL_*`` code
  (self-checked in :func:`apply_recipe` via ``checker.py`` — the deterministic truth
  source, never a model).

The corrected text of a repair row is the pre-injection original **by construction**: we
broke a known-green file, so we already hold its fix.
"""

from __future__ import annotations

import difflib
import re
from dataclasses import dataclass
from typing import Callable

from dcl import checker as _checker
from dcl.checker import CompileResult


class AnchorNotFound(ValueError):
    """A recipe's target shape is absent from the ``.dcl`` text it was applied to."""


class RecipeError(RuntimeError):
    """A recipe produced no change, or strayed beyond its single intended edit."""


class RecipeSelfCheckError(RuntimeError):
    """The broken output did NOT fail the compiler as the recipe's class requires."""


# --------------------------------------------------------------------------------------
# Single-edit helpers — each guarantees exactly one substitution or raises loudly.
# --------------------------------------------------------------------------------------
def _sub_once(text: str, pattern: str, repl: str, *, what: str, flags: int = re.M) -> str:
    new_text, n = re.subn(pattern, repl, text, count=1, flags=flags)
    if n == 0:
        raise AnchorNotFound(f"no anchor for {what} (pattern {pattern!r})")
    return new_text


def _remove_line_once(text: str, line_pattern: str, *, what: str) -> str:
    rx = re.compile(line_pattern, re.M)
    m = rx.search(text)
    if not m:
        raise AnchorNotFound(f"no anchor for {what} (pattern {line_pattern!r})")
    start = text.rfind("\n", 0, m.start()) + 1
    end = m.end()
    if end < len(text) and text[end] == "\n":
        end += 1
    return text[:start] + text[end:]


# --------------------------------------------------------------------------------------
# The recipes. Each is a pure text->text mutation. Verified against the WASM compiler
# (2026-07-17) to emit the paired DCL_* error code.
# --------------------------------------------------------------------------------------
_ACTOR_KINDS = ("human", "system", "agent", "scheduled_process")
_EFFECT_KINDS = ("persistence", "notification", "invocation", "tool")
_FAMILIES = (
    "reliability", "availability", "scalability", "performance", "security",
    "compliance", "governance", "data_protection", "confidence",
)
# Rename each family to one that shares NONE of its concerns (guarantees wrong-family).
_WRONG_FAMILY_MAP = {f: ("performance" if f == "reliability" else "reliability") for f in _FAMILIES}
_INVENTED_CONCERN = "resilience"  # not in any family's closed concern set
# req/allow/forbid-valued concerns whose value we can corrupt to an invalid literal.
_ENUM_CONCERNS = (
    "idempotency", "authentication", "authorization", "encryption", "audit", "approval",
    "evidence", "masking", "minimization", "deletion", "dependency_tolerance",
    "degradation", "queue",
)
# Concern keywords whose keyword we can rename to an invented (unknown) concern.
_RENAMEABLE_CONCERNS = (
    "timeout", "latency", "concurrency", "audit", "retention", "classification",
    "sensitivity", "throughput", "budget", "queue", "idempotency",
)


def _r_actor_kind(text: str) -> str:
    """Invent an actor kind (``… is machine``) — the observed held-004 defect."""
    return _sub_once(
        text,
        r"(\bactor\s+\w+\s+is\s+)(?:" + "|".join(_ACTOR_KINDS) + r")\b",
        r"\1machine",
        what="an `actor X is <kind>` declaration",
    )


def _r_effect_kind(text: str) -> str:
    """Invent an effect kind (``… is in_memory``) — the observed held-004 defect."""
    return _sub_once(
        text,
        r"(\beffect\s+\w+\s+is\s+)(?:" + "|".join(_EFFECT_KINDS) + r")\b",
        r"\1in_memory",
        what="an `effect X is <kind>` declaration",
    )


def _r_invented_concern(text: str) -> str:
    """Rename a real concern keyword to an invented one (DCL_SEM_POLICY_CONCERN_UNKNOWN)."""
    for kw in _RENAMEABLE_CONCERNS:
        m = re.search(rf"^(\s*){kw}(\s+\S)", text, re.M)
        if m:
            return _sub_once(
                text, rf"^(\s*){kw}(\s+\S)", rf"\1{_INVENTED_CONCERN}\2",
                what=f"a `{kw}` concern line",
            )
    raise AnchorNotFound("no renameable policy concern line present")


def _r_wrong_family(text: str) -> str:
    """Rename a policy family block to one that rejects its concerns (WRONG_FAMILY)."""
    m = re.search(r"^(\s*)(" + "|".join(_FAMILIES) + r")(\s*\{)", text, re.M)
    if not m:
        raise AnchorNotFound("no policy family block present")
    fam = m.group(2)
    return _sub_once(
        text, rf"^(\s*){fam}(\s*\{{)", rf"\g<1>{_WRONG_FAMILY_MAP[fam]}\2",
        what=f"a `{fam}` policy family block",
    )


def _r_invented_value(text: str) -> str:
    """Corrupt an enum concern's value to an invalid literal (CONCERN_VALUE_INVALID)."""
    for kw in _ENUM_CONCERNS:
        if re.search(rf"\b{kw}\s+(required|allowed|forbidden)\b", text):
            return _sub_once(
                text, rf"(\b{kw}\s+)(required|allowed|forbidden)\b", r"\1maybe",
                what=f"a `{kw} <required|allowed|forbidden>` line",
            )
    raise AnchorNotFound("no required/allowed/forbidden concern value present")


def _r_lexer_char(text: str) -> str:
    """Inject a lexer-illegal ``%`` into a declared identifier (DCL_LEX_UNEXPECTED_CHAR)."""
    m = re.search(r"\b(capability|shape|actor|event|effect|policy)\s+([A-Za-z])(\w+)", text)
    if not m:
        raise AnchorNotFound("no declared identifier to corrupt")
    kw, first, rest = m.group(1), m.group(2), m.group(3)
    return _sub_once(
        text, rf"\b{kw}\s+{first}{re.escape(rest)}\b", f"{kw} {first}%{rest}",
        what=f"a `{kw} <Name>` identifier",
    )


def _r_undeclared_outcome(text: str) -> str:
    """Reference an undeclared outcome in ``when`` (DCL_SEM_UNKNOWN_OUTCOME)."""
    m = re.search(r"\bwhen\s*\{", text)
    if not m:
        raise AnchorNotFound("no `when` block present")
    tail = text[m.end():]
    tm = re.search(r"(\bthen\s+)([A-Z]\w+)", tail)
    if not tm:
        raise AnchorNotFound("no `then <Outcome>` branch in the when block")
    absolute = m.end() + tm.start()
    prefix, name = tm.group(1), tm.group(2)
    return (
        text[:absolute]
        + f"{prefix}{name}Nowhere"
        + text[absolute + tm.end() - tm.start():]
    )


def _r_undeclared_symbol(text: str) -> str:
    """Reference an undeclared actor in the intent (DCL_SEM_UNKNOWN_ACTOR)."""
    return _sub_once(
        text, r"(\bintent\s+\w+\s+from\s+)([A-Z]\w+)", r"\1Nonexistent\2",
        what="an `intent <Shape> from <Actor>` line",
    )


def _r_missing_lifecycle(text: str) -> str:
    """Drop the required ``begin`` from a lifecycle (DCL_SEM_LIFECYCLE_BEGIN_REQUIRED)."""
    return _remove_line_once(
        text, r"^\s*begin\s+(?:step\s+)?\w+\s*$", what="a lifecycle `begin` declaration"
    )


def _r_retry_no_idempotency(text: str) -> str:
    """Remove idempotency while a retry policy is attached (RETRY_REQUIRES_IDEMPOTENCY)."""
    if not re.search(r"\bretry\s*\{", text):
        raise AnchorNotFound("no `retry { … }` concern present")
    if not re.search(r"^\s*idempotency\s+\w+\s*$", text, re.M):
        raise AnchorNotFound("no `idempotency <value>` line to remove")
    return _remove_line_once(
        text, r"^\s*idempotency\s+\w+\s*$", what="an `idempotency` line under a retry policy"
    )


@dataclass(frozen=True)
class Recipe:
    """A seeded-defect recipe: metadata + the pure mutation planner."""

    id: str
    defect_class: str
    description: str
    expected_error_code: str
    apply: Callable[[str], str]


RECIPES: dict[str, Recipe] = {
    r.id: r
    for r in [
        Recipe("R-actor-kind", "invented_actor_kind",
               "actor declared with an out-of-vocabulary kind (e.g. `is machine`)",
               "DCL_SEM_ACTOR_KIND_UNKNOWN", _r_actor_kind),
        Recipe("R-effect-kind", "invented_effect_kind",
               "effect declared with an out-of-vocabulary kind (e.g. `is in_memory`)",
               "DCL_SEM_EFFECT_KIND_UNKNOWN", _r_effect_kind),
        Recipe("R-invented-concern", "invented_policy_concern",
               "a policy family carries an invented (unknown) concern keyword",
               "DCL_SEM_POLICY_CONCERN_UNKNOWN", _r_invented_concern),
        Recipe("R-wrong-family", "concern_in_wrong_family",
               "a concern placed under a family that does not admit it",
               "DCL_SEM_POLICY_CONCERN_WRONG_FAMILY", _r_wrong_family),
        Recipe("R-invented-value", "invented_concern_value",
               "an enum concern given a value outside its closed set",
               "DCL_SEM_POLICY_CONCERN_VALUE_INVALID", _r_invented_value),
        Recipe("R-lexer-char", "lexer_breaking_char",
               "a lexer-illegal character injected into an identifier",
               "DCL_LEX_UNEXPECTED_CHAR", _r_lexer_char),
        Recipe("R-undeclared-outcome", "undeclared_outcome_in_when",
               "a `when` branch causes an outcome that was never declared",
               "DCL_SEM_UNKNOWN_OUTCOME", _r_undeclared_outcome),
        Recipe("R-undeclared-symbol", "undeclared_symbol",
               "the intent binds an actor that was never declared",
               "DCL_SEM_UNKNOWN_ACTOR", _r_undeclared_symbol),
        Recipe("R-missing-lifecycle", "missing_lifecycle_block",
               "a lifecycle block missing its required `begin` declaration",
               "DCL_SEM_LIFECYCLE_BEGIN_REQUIRED", _r_missing_lifecycle),
        Recipe("R-retry-no-idempotency", "retry_without_idempotency",
               "a retry policy attached without the required idempotency guarantee",
               "DCL_SEM_RETRY_REQUIRES_IDEMPOTENCY", _r_retry_no_idempotency),
    ]
}


@dataclass(frozen=True)
class BrokenResult:
    """A planted defect: the broken text, the minimal diff, and the recipe metadata."""

    recipe_id: str
    defect_class: str
    expected_error_code: str
    source_text: str
    broken_text: str
    diff: str
    changed_line_count: int


def _unified_diff(before: str, after: str) -> tuple[str, int]:
    b = before.splitlines(keepends=True)
    a = after.splitlines(keepends=True)
    hunk = list(difflib.unified_diff(b, a, fromfile="a.dcl", tofile="b.dcl"))
    changed = sum(
        1 for ln in hunk if (ln.startswith("+") or ln.startswith("-"))
        and not ln.startswith("+++") and not ln.startswith("---")
    )
    return "".join(hunk), changed


def apply_recipe(source_text: str, recipe_id: str) -> BrokenResult:
    """Apply ``recipe_id`` to a known-green ``.dcl`` file (pure; no compiler call).

    Raises :class:`KeyError` for an unknown recipe, :class:`AnchorNotFound` when the
    target shape is absent, and :class:`RecipeError` if the edit was inert.
    """
    if recipe_id not in RECIPES:
        raise KeyError(f"unknown recipe {recipe_id!r}; known: {sorted(RECIPES)}")
    recipe = RECIPES[recipe_id]
    broken = recipe.apply(source_text)
    if broken == source_text:
        raise RecipeError(f"recipe {recipe_id} produced no change (inert edit)")
    diff, changed = _unified_diff(source_text, broken)
    return BrokenResult(
        recipe_id=recipe_id,
        defect_class=recipe.defect_class,
        expected_error_code=recipe.expected_error_code,
        source_text=source_text,
        broken_text=broken,
        diff=diff,
        changed_line_count=changed,
    )


def verify_breaks(result: BrokenResult, *, checker=_checker) -> CompileResult:
    """Self-check: compile the broken text and assert the compiler REJECTS it with the
    recipe's named error code (the deterministic truth source, never a model).

    Returns the :class:`CompileResult` so the caller can embed the REAL diagnostics in
    the repair row. Raises :class:`RecipeSelfCheckError` if the mutation compiled clean
    or the expected code is absent.
    """
    compiled = checker.compile(result.broken_text)
    if compiled.ok or compiled.error_count == 0:
        raise RecipeSelfCheckError(
            f"recipe {result.recipe_id} did NOT break compilation — broken text compiled "
            "clean; the recipe is not planting its defect class"
        )
    if result.expected_error_code not in compiled.error_codes:
        raise RecipeSelfCheckError(
            f"recipe {result.recipe_id} broke compilation but with codes "
            f"{compiled.error_codes}, not the expected {result.expected_error_code!r}"
        )
    return compiled
