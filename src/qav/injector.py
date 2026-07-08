"""Injector — apply a seeded-defect recipe to a known-green task and label the result.

The core operation (:func:`inject`) is a **pure** transform of an in-memory file map: it
applies exactly the recipe's declared edits, self-checks that *nothing else* changed
(the WS2-B11 gate: "injector on a known-green task produces the labelled defect and
NOTHING else"), and returns the mutated tree + the fixed-by-construction label.

The downstream ``seeded_code`` step re-runs guardkit's ``CoachValidator.gather_evidence``
over the mutated worktree to produce the real bundle — that is a **generation run** (needs
the target repo's pytest substrate; GB10; post-window). It is *not* invoked here: the
:class:`BundleRegenerator` protocol is the seam, and :class:`GatherEvidenceRegenerator`
is a real adapter that lazy-imports guardkit and raises loudly if used unconfigured —
tests never call it.
"""

from __future__ import annotations

import difflib
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from qav.recipes import RECIPES, AnchorNotFound, Edit, Recipe


@dataclass
class InjectionResult:
    """A planted defect: the mutated tree, the diff evidence, and the fixed label."""

    recipe_id: str
    dc_class: str
    family: str
    mutated_files: dict[str, str]
    changed_files: list[str]
    diff: str
    finding: dict[str, str]  # {"class": ..., "locus": ...}

    @property
    def label(self) -> dict[str, Any]:
        """The reject label fixed by construction (source=seeded). Verdict is never a model call."""
        return {
            "verdict": "reject",
            "findings": [self.finding],
            "ground_truth_source": "seeded",
        }


class InjectionError(RuntimeError):
    """The recipe's edits did not apply cleanly, or changed more than declared."""


def _apply_edit(text: str, edit: Edit) -> str:
    new_text, count = re.subn(edit.pattern, edit.replacement, text, flags=re.M)
    if count < edit.min_count:
        raise AnchorNotFound(
            f"edit on {edit.path} matched {count}<{edit.min_count} times (pattern {edit.pattern!r})"
        )
    return new_text


def _unified_diff(before: dict[str, str], after: dict[str, str]) -> tuple[list[str], str]:
    changed: list[str] = []
    chunks: list[str] = []
    for path in sorted(set(before) | set(after)):
        b = before.get(path, "").splitlines(keepends=True)
        a = after.get(path, "").splitlines(keepends=True)
        if b == a:
            continue
        changed.append(path)
        chunks.extend(
            difflib.unified_diff(b, a, fromfile=f"a/{path}", tofile=f"b/{path}")
        )
    return changed, "".join(chunks)


def inject(files: dict[str, str], recipe_id: str) -> InjectionResult:
    """Apply ``recipe_id`` to a known-green task's file map. Pure; raises if the anchor is
    absent (never a silent no-op) or if the mutation strays beyond the recipe's declared
    files (the "NOTHING else" self-check)."""
    if recipe_id not in RECIPES:
        raise KeyError(f"unknown recipe {recipe_id!r}; known: {sorted(RECIPES)}")
    recipe: Recipe = RECIPES[recipe_id]
    before = dict(files)
    mutation = recipe.plan(before)  # AnchorNotFound if the shape is absent
    declared = {e.path for e in mutation.edits}

    after = dict(before)
    for edit in mutation.edits:
        if edit.path not in after:
            raise InjectionError(f"recipe {recipe_id} targets missing file {edit.path}")
        after[edit.path] = _apply_edit(after[edit.path], edit)

    changed, diff = _unified_diff(before, after)
    stray = set(changed) - declared
    if stray:
        raise InjectionError(
            f"recipe {recipe_id} changed undeclared files {sorted(stray)} — refuses to plant "
            "more than the labelled defect (NOTHING-else guarantee)"
        )
    if not changed:
        raise InjectionError(f"recipe {recipe_id} produced no change — anchor matched but edit was inert")

    return InjectionResult(
        recipe_id=recipe_id,
        dc_class=recipe.dc_class,
        family=recipe.family,
        mutated_files=after,
        changed_files=changed,
        diff=diff,
        finding={"class": recipe.dc_class, "locus": mutation.finding_locus},
    )


def inject_control(files: dict[str, str]) -> InjectionResult:
    """Seeded-control: a no-op injection. Produces the same machinery path with an EMPTY
    diff and NO finding, so a regenerated true-green bundle can be labelled approve —
    controlling for any "was regenerated" cue (PLAN §2 seeded-control greens)."""
    return InjectionResult(
        recipe_id="R-CONTROL-noop",
        dc_class="",
        family="R-CONTROL",
        mutated_files=dict(files),
        changed_files=[],
        diff="",
        finding={},
    )


# --------------------------------------------------------------------------------------
# Bundle regeneration seam — the generation-run boundary. Never called by tests.
# --------------------------------------------------------------------------------------
class BundleRegenerator(Protocol):
    """Turns a mutated worktree into a serialized CoachEvidenceBundle dict."""

    def regenerate(self, worktree: Path) -> dict[str, Any]:  # pragma: no cover - seam
        ...


@dataclass
class GatherEvidenceRegenerator:
    """Real regenerator: drives guardkit ``CoachValidator.gather_evidence`` as a LIBRARY
    call (no Player, no autobuild turn, no llama-swap) over a mutated worktree.

    Instantiating this is fine; calling :meth:`regenerate` performs real work against a
    repo's pytest substrate — a **generation run**. It raises loudly if guardkit is not
    importable (the SIBTESTENV01 lesson: per-repo interpreter resolution). Left un-wired
    into any run in this session per the GB10 calendar guardrail.
    """

    task_id: str
    profile_name: str | None = None

    def regenerate(self, worktree: Path) -> dict[str, Any]:  # pragma: no cover - generation run
        try:
            from guardkit.orchestrator.quality_gates.coach_validator import (  # type: ignore
                CoachValidator,
            )
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError(
                "guardkit CoachValidator unavailable — seeded_code regeneration is a generation "
                "run; wire a per-repo interpreter and run it on the GB10, never in unit tests"
            ) from exc
        validator = CoachValidator()  # type: ignore[call-arg]
        bundle = validator.gather_evidence(task_id=self.task_id, repo_path=str(worktree))
        return bundle.to_dict()
