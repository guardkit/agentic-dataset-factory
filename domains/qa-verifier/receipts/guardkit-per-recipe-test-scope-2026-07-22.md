# Receipt — GUARDKIT PER-RECIPE TEST-SCOPE: 2 recipes RECOVERED + SPIKED GREEN, 3 honest source-package expected-misses (2026-07-22)

> **THE CYCLE-4 24-REFUSAL BLOCK IS SPLIT INTO ITS TWO HONEST HALVES.** Cycle 4's remaining
> recoverable block was 24 `evidence_invariant_injection` refusals, almost all guardkit: its single
> per-repo pin (`tests/orchestrator/test_wiring_seam_real_factory.py`) only exercises **one** of its
> anchoring recipes (R-DC03-mockseam), so the others regenerated a bundle byte-identical to the no-op
> control and the guard honestly turned them away. This lane adds a MINIMAL per-repo **per-recipe**
> test-command override, threaded through the bridge, and — critically — regenerates each override
> recipe's control under the SAME command (a **scope-matched control**) so a scope-only difference can
> never masquerade as the defect. **Two recipes RECOVERED + SPIKED GREEN** (R-DC05-skipguard,
> R-ABSENT-junit); **three are honest expected-misses** — their mutations are to guardkit's OWN
> `guardkit/` source package, which is **shadowed by the editable install** (proven with cwd=worktree:
> `import guardkit.*` always resolves to the corpus tree, never the mutated worktree copy). No frozen
> file touched; the evidence-divergence guard **strengthened, never weakened**.

Factory HEAD at start: `46c5547` → rebased onto the concurrent `e34ec74` (recruiter-agent S1 landed
mid-session); committed path-limited, sweeping no foreign hunk. Corpus repos read-only: guardkit
`b68c9e9d` HEAD unchanged (detached scratch worktrees only, all removed). `contracts.py` / recipe ids
/ families / dc_classes / mutation-SEMANTICS / `injector.py` / `scrub.py` byte-frozen; the
evidence-divergence guard UNTOUCHED. Labels never model-derived. Flock-guard `-x
/var/lock/llama-swap-keepalive.lock` held UNCONDITIONALLY over every regeneration; keepalive timer
never touched (CPU/pytest only — zero model / GPU / fleet). No push. DF-008.

---

## 1. The per-recipe verdict (the ask) — the 6 guardkit-anchoring recipes from `9c212db`

Ran the real `qav.discover.discover_source_tasks` + `qav.injector.inject` over every guardkit source
task at its approved sha (QAWE-001/002/003/004 @ `799cefd0`, BDDW-001/002 @ `917bcef7`) and read the
EXACT mutated files per recipe, then classified each by the L2 editable-install shadow caveat
(test-file mutations immune; `guardkit/` source-package mutations shadowed).

| recipe | mutated file(s) @ approved sha | class | verdict |
|---|---|---|---|
| **R-DC03-mockseam** | `tests/orchestrator/test_wiring_seam_real_factory.py` | TEST (immune) | **already recovered** — the per-repo default pin (render-collapse spike) |
| **R-DC05-skipguard** | `tests/knowledge/test_seeding.py` | TEST (immune) | **RECOVERED + SPIKED GREEN** (per-recipe pin) |
| **R-ABSENT-junit** | `tests/unit/orchestrator/quality_gates/test_bdd_runner.py` | TEST (immune) | **RECOVERED + SPIKED GREEN** (per-recipe pin) |
| R-DC03-producer | `guardkit/orchestrator/quality_gates/coach_validator.py` | SOURCE-package | **honest expected-miss** — shadowed by the editable install |
| R-DC05-sysmod | `guardkit/orchestrator/quality_gates/__init__.py` | SOURCE-package | **honest expected-miss** — shadowed by the editable install |
| R-DC03-callsite | `guardkit/integrations/graphiti/parsers/full_doc_parser.py` (SRC) + `tests/.../test_full_doc_parser.py` (TEST, stays green-by-design) | SOURCE-package | **honest expected-miss** — SRC shadowed; the unit test is updated to the new contract (green); the broken call site (`cli/graphiti.py`) has NO service-free covering test |

## 2. The shadow, proven (not assumed)

guardkit is `-e`-installed at the corpus path: `import guardkit` → `…/guardkit/guardkit/__init__.py`.
Materializing R-DC05-sysmod's mutated `guardkit/orchestrator/quality_gates/__init__.py` into a scratch
worktree and importing it **with cwd = that worktree**:

```
RESOLVED: /home/…/guardkit/guardkit/orchestrator/quality_gates/__init__.py   (the CORPUS tree)
```

The editable-install `.pth` pins the corpus root on `sys.path`, so ANY `import guardkit.*`
source-package mutation in a worktree is loaded from the corpus, never the mutated copy — the planted
defect cannot surface through a Python import. Forcing a test scope for these is config for a dead
path (declined per the no-gold-plating discipline — the same call the render-collapse appendix and the
study_tutor lane made). Recorded as structural expected-misses, matching the discipline of the
existing ones (semantic fidelity over hit-rate).

## 3. The MINIMAL mechanism — per-recipe override + scope-matched control

- **`agent-config.yaml → regeneration.test_commands_per_recipe`** (NEW, optional): a
  `repo -> {recipe_id -> pytest command}` map that OVERRIDES the per-repo `test_commands` default for
  the named recipes only. The recipe is the third worktree-path segment
  (`<scratch>/<repo>/<task>/<recipe_id>`), so selection needs **no** new Protocol argument — the bridge
  threading is purely additive (`--test-command` is now selected per (repo, recipe), else per repo,
  else auto-detect). Every command obeys the **tokenisation law** (starts with `pytest`, every token
  whitespace-free — guardkit's `test_cmd.split()` shell=False) — guarded by a test that reads the
  SHIPPED config.
- **Scope-matched control (the honesty core, in `_run_seeded_code`).** A per-recipe override runs a
  DIFFERENT test scope than the per-repo default, so comparing the reject against the DEFAULT-scope
  control would diverge **trivially** (different tests ran), not because the defect surfaced. So each
  override recipe is compared against a control regenerated under its OWN command — materialized at the
  recipe's own worktree path so the regenerator selects the same pinned command, one control per
  DISTINCT command (cached). Recipes without an override keep comparing against the default control
  (fully additive — the block is a no-op when no overrides are configured). A dedicated hermetic test
  (`test_layer4_scope_matched_control_refuses_invisible_defect`) proves the guard REFUSES a reject
  whose bundle equals its scope-matched control but differs from the default control — i.e. scope-only
  differences can never mint a poison reject row.

## 4. THE LIVE MICRO-SPIKES — real bridge, integration profile, TASK-QAWE-001 @ 799cefd0, run twice

Real `SubprocessBridgeRegenerator.from_config(shipped config)` → the per-recipe command is SELECTED by
path-derivation (not hand-passed) → guardkit `gather_evidence`, record materialized from the corpus
HEAD archive, every bundle scrubbed before hashing. **Zero model / GPU / fleet.** Control + mutated ×2:

| recipe | leg | scrubbed bundle sha[:16] | evidence |
|---|---|---|---|
| **R-DC05-skipguard** | CONTROL | `1dccf9317d5dc6db` | `54 passed, 4 skipped` — clean-green, real tests run |
| | MUT run1 | `7d98de3e24e367e3` | `58 skipped` — the skip-guard defeat surfaces as the DC-05 skip-count divergence (green-with-skips; skips vs claims diverge) |
| | MUT run2 | `7d98de3e24e367e3` | — |
| **R-ABSENT-junit** | CONTROL | `3747a9eb2c1ede3d` | `50 passed` — clean-green |
| | MUT run1 | `00bbf436fab228f4` | `failure_class=collection_error` — the independent junit is ABSENT (the module's `pytestmark = skip` prepend lands ahead of `from __future__ import annotations`, a genuine collection failure = the SMP-002 turn-2 absent-signal shape) |
| | MUT run2 | `00bbf436fab228f4` | — |

- **(A) DIVERGED** — both mutated ≠ their scope-matched control; the evidence-divergence guard PASSES
  each (no false refusal). skipguard earns it with the passed→skipped result change; junit earns it
  with the absent-junit collection failure.
- **(B) REAL EVIDENCE of THAT defect** — the CONTROL over the SAME scope is clean-green (its approve
  label is honest); the mutated leg carries the planted defect's real signature.
- **(C) DETERMINISTIC** — run1 == run2 byte-for-byte for both (identical to a prior hand-built spike,
  cross-checking the from_config path-selection).

## 5. Projected refusal → row conversion

The 6 guardkit tasks anchor these reject recipes (QAWE: all 6; BDDW: callsite/sysmod/skipguard/junit —
producer + mockseam don't anchor at `917bcef7`). Under the old single per-repo pin only mockseam
surfaced; every other anchoring recipe was refused.

- **Recovered → real reject rows:** R-DC05-skipguard + R-ABSENT-junit across all 6 guardkit tasks =
  **up to 12 new seeded_code reject rows** (modulo weighted sampling + dedup).
- **Remaining honest expected-misses (source-package shadowed):** R-DC03-callsite (6 tasks) +
  R-DC05-sysmod (6) + R-DC03-producer (4 QAWE) = **~16 legs** — now RECORDED as a structural limit
  (editable-install shadow), no longer an open recovery block.

So of cycle-4's 24 guardkit-dominated refusals, roughly **half convert to rows** and the rest are
reclassified from "recoverable" to "honest structural expected-miss." The next real reject-volume
levers for guardkit source classes are unchanged: a validated non-editable regeneration (surface the
`guardkit/` source mutations) or the seeded_bundle / harvest paths.

## 6. Tests + suite

- `tests/test_qav_regenerate.py` (+4): per-recipe override wins over per-repo default; override
  scoped to its own repo; `_select_test_command` precedence unit; `from_config` threads the map.
- `tests/test_qav_generate.py` (+5): config loads `test_commands_per_recipe` (+ default-empty); the
  SHIPPED per-recipe pins obey the tokenisation law; an override reject banks against its
  scope-matched control; **the scope-matched control REFUSES an invisible-defect reject** (the honesty
  guard). Full suite: `uv run --no-sync pytest -q` → **2508 passed** (2499 baseline + 9). `ruff` clean
  on the changed lines (no new violations).

## 7. Files (adf-side; path-limited commit; no push; frozen surfaces untouched)

- `src/qav/generate.py` — `GenerateConfig.test_commands_per_recipe` field + `from_yaml` parse;
  `_run_seeded_code` scope-matched controls (additive). Divergence guard / `contracts.py` byte-frozen.
- `src/qav/regenerate.py` — `SubprocessBridgeRegenerator.test_commands_per_recipe` + `from_config`
  threading; `_repo_task_recipe` (recipe = 3rd path segment) + `_select_test_command` precedence.
- `domains/qa-verifier/agent-config.yaml` — the guardkit `test_commands_per_recipe` block (2 recovered
  pins) + provenance comment naming the 3 source-package expected-misses.
- `domains/qa-verifier/receipts/guardkit-per-recipe-test-scope-2026-07-22.md` — this receipt.
- Corpus repos read-only (guardkit `b68c9e9d` HEAD unchanged; scratch worktrees removed). ed00704
  validators byte-frozen. Keepalive timer never touched (flock-guard held). No push. DF-008.
