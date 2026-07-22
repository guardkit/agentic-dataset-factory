# Receipt — SHADOW-CLAIM RECOVERY: 2 SOURCE-package recipes RECOVERED + SPIKED GREEN (2026-07-22)

> **THE EDITABLE-INSTALL SHADOW CLAIM WAS FALSIFIED — AND TWO OF ITS THREE EXPECTED-MISSES RECOVER.**
> The `guardkit-per-recipe-test-scope` lane recorded R-DC03-producer, R-DC03-callsite, and
> R-DC05-sysmod as *honest expected-misses* on the theory that any `import guardkit.*` in a
> mutated worktree resolves to the corpus editable install, never the worktree copy. The cycle-5
> coach challenged that. This lane **verified the import model directly** and the shadow claim is
> **false for `guardkit` itself**: `guardkit` is installed by a PLAIN `sys.path`-append `.pth`
> (`.venv/.../_editable_impl_guardkit_py.pth` = the bare corpus-root string), not a meta-path
> finder. `gather_evidence` runs the independent test with **cwd=<worktree>**
> (`coach_validator.py:3810/3977`), and pytest's rootdir/conftest insertion puts the worktree root
> on `sys.path[0]` **ahead** of the `.pth` corpus entry — so `import guardkit.*` binds to the
> **MUTATED worktree copy**. **R-DC03-producer + R-DC03-callsite RECOVER + SPIKE GREEN** on the real
> bridge; **R-DC05-sysmod stays an honest expected-miss** for a *different* reason (its
> `sys.modules['guardkitfactory']` stub is inert — guardkitfactory is genuinely installed). No
> frozen file touched; recipes/anchors/variant-mechanism byte-unchanged; guard/scrub untouched.

Factory HEAD at start: `bf00f05`. Corpus repos read-only: guardkit `b68c9e9d` HEAD unchanged
(detached scratch worktrees only, all created + removed by `checkout_scoped_file_map`; `git worktree
list` shows none left; `git worktree prune` run). `contracts.py` / recipe ids / families / dc_classes
/ mutation-SEMANTICS / `injector.py` / `scrub.py` byte-frozen; the evidence-divergence guard
UNTOUCHED. Labels never model-derived. Flock-guard: keepalive paused under Rich's standing
exclusive-use hold (`flock … llama-swap-keepalive.lock`, holder **PID 1185504** verified live before
every run); all work CPU/pytest only — zero model / GPU / fleet. No push. DF-008.

---

## 1. The import model, verified (the coach's probe — not assumed)

The prior receipt's §2 "shadow proof" ran a bare probe and reported `import guardkit.*` resolving to
the corpus. That did not replicate how the independent test actually runs. The real harness:

- **The install mechanism.** In guardkit's own venv, `guardkit` is editable-installed by
  `_editable_impl_guardkit_py.pth`, whose entire content is the bare path
  `/home/richardwoollcott/Projects/appmilla_github/guardkit` — a **plain `sys.path` directory
  append**. Only `guardkitfactory` uses a PEP 660 `_EditableFinder` on `sys.meta_path` (cwd-immune).
  A plain path entry is **preceded** by `sys.path[0]`.
- **The run context.** `coach_validator.py:3810` and `:3977` both spawn the independent test with
  `cwd=str(self.worktree_path)`. Under pytest's default `prepend` import mode, the rootdir
  conftest's directory (the worktree root) is inserted at `sys.path[0]`, ahead of the `.pth` corpus
  entry. So `import guardkit.integrations.…` / `import guardkit.orchestrator.…` binds to
  **`<worktree>/guardkit/…`** — the mutated copy.
- **Empirical confirmation.** Real guardkit-venv `pytest`, `cwd=<materialized worktree>`, over the
  scoped file map at the approved sha: the mutated `guardkit/…` source changed the test outcome
  (below). A `guardkit/`-source mutation is therefore **not** shadowed. The prior "always resolves to
  corpus" claim is false for `guardkit`.

## 2. Per-recipe verdict

| recipe | mutated file(s) @ 799cefd0 | class | verdict |
|---|---|---|---|
| **R-DC03-producer** | `guardkit/orchestrator/quality_gates/coach_validator.py` | SOURCE-package | **RECOVERED + SPIKED GREEN** (per-recipe pin) |
| **R-DC03-callsite** | `guardkit/integrations/graphiti/parsers/full_doc_parser.py` (SRC) + its direct unit test | SOURCE-package | **RECOVERED + SPIKED GREEN** (per-recipe pin) |
| R-DC05-sysmod | `guardkit/orchestrator/quality_gates/__init__.py` | SOURCE-package | **honest expected-miss — inert stub** (not a shadow: guardkitfactory genuinely installed) |

### R-DC03-producer — covering scope `tests/orchestrator/test_qawe_003_mocked_seam.py`
The producer sever replaces `result = analyze_wiring(…)` with `result = None` inside
`_run_wiring_analysis`. The reach-guard `if not _is_wiring_factory_available() or analyze_wiring is
None: return None` sits ahead of it, so a scope that only exercises the factory-absent path (e.g.
`test_coach_wiring_bundle.py`) is **inert** (control==mutated, 28/28 — verified). The chosen scope
**patches through**: `patch(_AVAIL_PATCH, return_value=True)` + `patch(_FACTORY_PATCH, …)` then
`_run_wiring_analysis(...)` and `assert result is not None` / `result["wiring"]["status"] ==
"complete"`. With the producer severed those assertions fail. Service-free (all wiring mocked).

### R-DC03-callsite — covering scope `tests/integrations/graphiti/parsers/test_full_doc_parser.py`
The recipe drops `chunk_threshold` from `FullDocParser.__init__`'s signature; the `__init__` body
still binds `self._chunk_threshold = chunk_threshold`, so after the drop **every `FullDocParser()`
raises `NameError`** (the unbound name). The direct unit scope imports the mutated source and turns
red. (The call site `cli/graphiti.py` — the labelled locus — remains broken too; the direct unit
scope is simply the service-free surface that surfaces the same planted defect.)

### R-DC05-sysmod — honest expected-miss (corrected rationale)
Its edit prepends `sys.modules['guardkitfactory'] = ModuleType(...)` to defeat a sibling-package
skip-guard. But `guardkitfactory` **is** genuinely installed (PEP 660 finder), so the `if
'guardkitfactory' not in sys.modules` stub-guard never fires and no observable test outcome changes
(control==mutated, empirically). Unpinned — a dead path, no gold-plating.

## 3. THE LIVE MICRO-SPIKES — real `from_config` bridge, integration profile, TASK-QAWE-001 @ 799cefd0, run twice

`SubprocessBridgeRegenerator.from_config(shipped config)` selects each command by path-derivation
(not hand-passed); guardkit `gather_evidence`; record materialized from the corpus HEAD archive;
every bundle scrubbed before hashing. **Zero model / GPU / fleet.** Control (scope-matched) + mutated ×2:

| recipe | leg | scrubbed bundle sha[:16] | evidence |
|---|---|---|---|
| **R-DC03-producer** | CONTROL | `2b0e079687a41d99` | `failure_class=None` — clean-green (honest approve label) |
| | MUT run1 | `02bda7a961321d43` | `failure_class=code` — severed producer → populated-envelope assertions fail |
| | MUT run2 | `02bda7a961321d43` | — |
| **R-DC03-callsite** | CONTROL | `82a3fce357f7d1ce` | `failure_class=None` — clean-green |
| | MUT run1 | `69b5bc8cb64e746c` | `failure_class=code` — `NameError` on every `FullDocParser()` |
| | MUT run2 | `69b5bc8cb64e746c` | — |

Direct-harness cross-check (guardkit venv `pytest`, cwd=worktree, `-o addopts=`): producer CONTROL 18
passed / MUTATED 9 failed·9 passed (×2 identical); callsite CONTROL 50 passed / MUTATED 49 failed·1
passed.

- **(A) DIVERGED** — both mutated ≠ their scope-matched control; the evidence-divergence guard PASSES
  each (no false refusal).
- **(B) REAL EVIDENCE of THAT defect** — the CONTROL over the SAME scope is clean-green
  (`failure_class=None`); the mutated leg carries the planted defect's real signature
  (`failure_class=code`).
- **(C) DETERMINISTIC** — run1 == run2 byte-for-byte for both. (Hashes are session-anchored: the
  `pytest` version banner in `independent_tests.raw_output` is scrub-untouched, so the absolute value
  is not portable across a pytest-version change; within-session run1==run2 is the determinism claim.)

## 4. Projected refusal → row conversion

R-DC03-producer anchors on all 6 guardkit tasks (QAWE 4 + BDDW 2); R-DC03-callsite anchors where the
`FullDocParser(chunk_threshold=…)` construct is present (the FEAT-C332 tree — QAWE 4). Under the old
recording both were refused as evidence-invariant no-ops. Recovered, they mint up to **~10 new
seeded_code reject rows** (modulo weighted sampling + dedup), retiring most of cycle-5's residual 12
`evidence_invariant` refusals. The remaining residual is R-DC05-sysmod (inert) — a genuine cap.

## 5. The MINIMAL mechanism — additive per-recipe pins (no code change)

Both recipes already exist and anchor correctly; the recovery needs **no** recipe/injector/contract
change — only two additive `regeneration.test_commands_per_recipe.guardkit` pins (the exact layer-4
mechanism the prior lane shipped) plus the scope-matched control the engine already regenerates.

## 6. Tests + suite

- `tests/test_qav_generate.py` — `test_shipped_per_recipe_pins_obey_the_tokenisation_law` extended
  to assert the two recovered pins ship (they are also covered generically by the tokenisation-law
  loop over every shipped override). Full suite: `uv run --no-sync pytest -q` → **PASS (2508)** — see
  §7 for the exact line.
- No new violations; frozen surfaces untouched.

## 7. Files (adf-side; path-limited commit; no push; frozen surfaces untouched)

- `domains/qa-verifier/agent-config.yaml` — 2 recovered guardkit per-recipe pins + the falsified-shadow
  correction note; the R-DC05-sysmod expected-miss rationale corrected (inert stub, not a shadow).
- `tests/test_qav_generate.py` — presence assertions for the two recovered pins.
- `domains/qa-verifier/receipts/guardkit-shadow-claim-recovery-2026-07-22.md` — this receipt.
- Corpus repos read-only (guardkit `b68c9e9d` HEAD unchanged; scratch worktrees removed). ed00704
  validators byte-frozen. Keepalive timer never touched (flock-guard held, PID 1185504 live). No push.
  DF-008.
