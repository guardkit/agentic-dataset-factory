"""Non-determinism scrub for regenerated evidence bundles — L2 deep-regeneration layer 3
(render-collapse root-cause, 2026-07-21).

Once layers 1+2 (the profile-gate + the per-repo stack pin) let guardkit ``gather_evidence``
actually RUN the mutated worktree's pytest, the regenerated ``CoachEvidenceBundle`` carries genuine
test evidence — but that evidence is threaded with WALL-CLOCK JITTER and per-run RANDOM PATHS that
differ between two runs of the SAME mutated tree. Left un-scrubbed they poison the row surface two
ways:

  (1) they split a re-run of one mutated tree into two "unique" ``row_id``s (a non-reproducible
      corpus — the contamination/dedup surface stops being content-addressed), and
  (2) they let a source-blind reject bundle drift a hair off its control by TIMING ALONE, DEFEATING
      the evidence-divergence guard — exactly the failure render-collapse warned of
      (``skip_arch_review`` alone is net-harmful: "defeat dedup by timing noise, minting 'unique'
      rows that carry identical evidence with divergent labels").

So the scrub runs at the ENGINE layer, on EVERY regenerated bundle, BEFORE both the divergence
guard's content-hash AND the ``row_id`` user-message rendering. ``contracts.py`` is FROZEN — the
scrub cannot live there; it lives here and is applied by ``qav.generate`` where it hands the
regenerated bundle to ``build_row`` (contracts.build_user_message → row_id hashes THIS content).

THE DOCUMENTED FIELD LIST — ``NONDETERMINISTIC_BUNDLE_KEYS`` (dropped recursively, anywhere in the
bundle):

  * ``duration_seconds`` — the wall-clock float on ``IndependentTestResult`` /
    ``RuntimeParityResult`` / any nested timing dict (guardkit ``coach_validator.py`` ~L1518,
    4914…). The exact field the render-collapse receipt named (``0.0666`` vs ``0.0562``).

THE DOCUMENTED TEXT NORMALIZATIONS — ``NONDET_TEXT_SUBS`` (value rewritten in place; failing-test
NAMES / assertion messages / exception types survive byte-identical so the reject keeps its real
evidence, while the jitter riding alongside them is replaced by a stable token):

  * pytest per-test / session timing (``in 0.34s``, ``0.34s call``, the ``=== … in 0.34s ===``
    summary and the "slowest durations" table),
  * per-run pytest tmp / ``--basetemp`` dirs (random suffix) and ``pytest-of-<user>`` paths,
  * CPython object-repr memory addresses (``<X object at 0x7f…>``),
  * incidental tmp/session hex ids.

The concrete pattern list was PINNED EMPIRICALLY against the two-run spike diff (the spike ran one
mutated tree twice and every surface that differed was added here until the two scrubbed bundles
hashed byte-identical). Extend ``NONDET_TEXT_SUBS`` ONLY with a diff that proves a new jitter
surface — never speculatively (over-scrubbing could erase real defect signal).
"""

from __future__ import annotations

import copy
import re
from typing import Any

# Keys dropped recursively (pure wall-clock jitter, no defect signal).
NONDETERMINISTIC_BUNDLE_KEYS: frozenset[str] = frozenset({"duration_seconds"})

# (regex, replacement) — ordered; each applied to every string leaf of the bundle.
NONDET_TEXT_SUBS: tuple[tuple["re.Pattern[str]", str], ...] = (
    # pytest "slowest durations" rows FIRST (more specific than the bare-seconds sub):
    #   "0.34s call tests/…::test_x"  ->  "<t>s call tests/…::test_x"
    (re.compile(r"\b\d+\.\d+s (call|setup|teardown)\b"), r"<t>s \1"),
    # pytest per-test / session timing: "in 0.34s", "0.34s", "=== 3 passed in 0.34s ==="
    (re.compile(r"\b\d+\.\d+s\b"), "<t>s"),
    # per-run pytest tmp / basetemp dirs (random suffix) + the isolated_basetemp injection:
    (re.compile(r"--basetemp=\S+"), "--basetemp=<tmp>"),
    (re.compile(r"(?:/[^\s'\"]+)?pytest-of-[^\s'\"/]+(?:/[^\s'\"]*)?"), "<pytest-tmp>"),
    (re.compile(r"/tmp/[^\s'\"]*pytest[^\s'\"]*"), "/tmp/<pytest-tmp>"),
    # CPython object repr memory addresses: "<X object at 0x7f…>"
    (re.compile(r"0x[0-9a-fA-F]{6,}"), "0x<addr>"),
    # incidental tmp / session hex ids occasionally embedded in output
    (re.compile(r"\btmp[0-9a-f]{6,}\b"), "tmp<hash>"),
)


def scrub_nondeterministic_bundle(
    bundle: dict[str, Any], *, worktree_path: str | None = None
) -> dict[str, Any]:
    """Return a deep copy of ``bundle`` with the documented non-deterministic surfaces removed /
    normalized (see ``NONDETERMINISTIC_BUNDLE_KEYS`` + ``NONDET_TEXT_SUBS``).

    Idempotent and total: two regenerations of the SAME mutated worktree scrub to byte-identical
    bundles, while a genuinely-divergent regeneration (a real defect surfacing in a failing test)
    keeps its distinguishing evidence. Never mutates its argument.

    ``worktree_path`` — when given, the ABSOLUTE scratch worktree path is normalized to the token
    ``<worktree>`` everywhere it appears (pytest's ``rootdir:`` line, collected-item paths, tmp
    roots). Two full generation runs on the same box share the scratch path so this is a no-op for
    determinism THERE, but it makes the ``row_id`` location-INDEPENDENT: identical evidence from a
    differently-rooted scratch dir (a moved factory, a different box) still content-addresses to the
    same row. Relative test node ids (``tests/…::test_x`` — the defect signal) are untouched."""
    path_subs: list[tuple[str, str]] = []
    if worktree_path:
        wp = str(worktree_path).rstrip("/")
        if wp:
            path_subs.append((wp, "<worktree>"))

    def _scrub(node: Any) -> Any:
        if isinstance(node, dict):
            return {
                k: _scrub(v)
                for k, v in node.items()
                if k not in NONDETERMINISTIC_BUNDLE_KEYS
            }
        if isinstance(node, list):
            return [_scrub(v) for v in node]
        if isinstance(node, str):
            out = node
            for needle, token in path_subs:
                out = out.replace(needle, token)
            for pat, repl in NONDET_TEXT_SUBS:
                out = pat.sub(repl, out)
            return out
        return node

    return _scrub(copy.deepcopy(bundle))
