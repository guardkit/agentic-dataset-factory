# Receipt — ANCHOR DIVERSITY: jarvis gains a DC-05 skip-guard anchor (its 2nd DC-class); study_tutor DC-05 = honest ceiling (2026-07-22)

> **CYCLE-5 CONSTRAINT WAS ANCHOR SATURATION** (`deduped=14` — one mutation shape × many same-sha
> tasks collapses under dedup). The lever is MULTIPLE DISTINCT DC-classes per corpus repo. jarvis
> and study_tutor were each MONO-DC-class (jarvis DC-08 only, study_tutor DC-03 only), so their
> many tasks — all sharing ONE sha per repo — produced one bundle shape that dedup crushed. This
> lane extends `R-DC05-skipguard` to a NEW repo via the `_first_anchor` per-repo variant mechanism,
> giving that repo a genuine SECOND DC-class. **ONE variant ships: jarvis R-DC05-skipguard**
> (SPIKE GREEN). **study_tutor R-DC05-skipguard is an HONEST CEILING** — its only unique
> service-free skip-guard is control-red at the approved sha (fails the known-green premise). No
> frozen file touched; the evidence-divergence guard is unchanged (control + mutated diverge on
> real evidence).

Factory HEAD at start: `bf00f05`. Corpus repos read-only (jarvis `1fc7309` HEAD unchanged,
study-tutor `f843cb5` HEAD unchanged — detached scratch worktrees only, all removed). `contracts.py`
/ recipe ids / families / dc_classes / mutation-SEMANTICS / `injector.py` / `scrub.py` byte-frozen;
the evidence-divergence guard UNTOUCHED; the opened scope is recipes-anchors + the `_first_anchor`
variant mechanism (ed00704). Labels never model-derived. Flock-guard: holder PID 1185504 verified
alive before every regeneration (keepalive paused via the standing exclusive hold — CPU/pytest only,
zero model/GPU/fleet). Suite green. No push. DF-008.

---

## 1. The diversity mechanism, grounded in the actual task set

The cycle-5 regen cells (from `run_logs/growth_cycle5_…`) and the resolved approved shas show why
dedup crushes these repos:

| repo | tasks (cycle 5) | approved sha(s) | DC-classes anchored (before) |
|---|---|---|---|
| jarvis | JNB-001/002/003/008 (4) | **all @ `736399b`** | DC-08 only (undefstep+pendmask) |
| study_tutor | PRV-001…007 (7) | **all @ `94f3331`** | DC-03 only (callsite) |
| study_tutor | VOX-002…005/007 (5) | **all @ `5d57b022`** | DC-03 only (callsite) |

Row dedup is a sha256 of the **scrubbed regenerated evidence bundle** (`generate.bundle_content_hash`
→ `OutputWriter._seen_row_ids`), so N tasks sharing ONE tree-state + ONE mutation shape yield ONE
distinct row. jarvis's 4 tasks are all at a single sha → its DC-08 anchor is at most 1–2 distinct
rows. Adding a DISTINCT DC-class (a different mutated file → different evidence) is the only lever
that pays; more tasks on the same anchor do not.

## 2. SHIPPED — jarvis R-DC05-skipguard (its second DC-class)

Real corpus construct (jarvis `736399b`): `tests/test_fleet_memory_payloads.py` (docstring "Unit
tests for Jarvis fleet-memory episode construction") carries a MODULE-level
`pytestmark = pytest.mark.skipif(not _HAS_NATS_CORE, reason="nats_core (memory write dep) not
installed")` — a genuine sibling-package dependency guard. `nats_core` IS installed in the jarvis
venv, so the control runs the module green; the module asserts the outbound episode shape "without
any live store (no publish)" → **service-free**. Weakening the guard to always-skip
(`True or not _HAS_NATS_CORE`) makes the regenerated junit report the whole module skipped where the
control reported passes — the DC-05 "green-with-skips; skip counts vs claims diverge" signature, in
jarvis's own dependency-guard vocabulary.

- **Anchor uniqueness:** the `not _HAS_NATS_CORE` token also appears as per-test decorators in a
  SIBLING module (`test_fleet_memory_client.py`), so the recipe anchors on the UNIQUE per-module
  docstring (`_find`, exactly 1 match @ `736399b`) and the edit then targets the one module-level
  skipif within that file.
- **Scope pin** (`test_commands_per_recipe.jarvis.R-DC05-skipguard`):
  `pytest tests/test_fleet_memory_payloads.py -q -p no:cacheprovider -p no:warnings` — tokenisation
  law obeyed (every token whitespace-free; guardkit `test_cmd.split()` shell=False). The per-repo
  jarvis default (`-k publishes` BDD file) covers the DC-08 anchor, not this skip-guard, so the DC-05
  scope MUST be pinned; the engine regenerates its scope-matched control automatically
  (`generate._run_seeded_code`), so divergence proves the DEFECT surfaced, not a scope difference.

### THE LIVE MICRO-SPIKE — real bridge, integration profile, TASK-JNB-001 @ 736399b, run twice

Real `SubprocessBridgeRegenerator.from_config(shipped config)` → per-recipe command SELECTED by
path-derivation → guardkit `gather_evidence` over the mutated worktree, record materialized from the
corpus HEAD, every bundle scrubbed before hashing. **Zero model / GPU / fleet.** Scope-matched
control + mutated ×2:

| leg | scrubbed bundle sha[:16] | evidence |
|---|---|---|
| CONTROL | `684305a58542e9a0` | `.........` — **9 passed** (clean-green, real tests run) |
| MUT run1 | `d296a4029c49f5b8` | `sssssssss` — **9 skipped** (module always-skips; skip-count vs claims diverge) |
| MUT run2 | `d296a4029c49f5b8` | — |

- **(A) DIVERGED** — mutated ≠ its scope-matched control; the evidence-divergence guard PASSES (no
  false refusal).
- **(B) REAL EVIDENCE of THAT defect** — control over the same scope is 9-passed clean-green (its
  approve baseline is honest); the mutated leg carries the skip-guard defeat (9-skipped).
- **(C) DETERMINISTIC** — run1 == run2 byte-for-byte.

## 3. HONEST CEILING — study_tutor DC-05 (attempted, not shipped)

study_tutor's ONLY unique service-free skip-guard at its approved shas is
`tests/unit/planner/test_protocols.py`'s AC-002 mypy-strict guard
(`@pytest.mark.skipif(shutil.which("mypy") is None, …)`; unique @ both `94f3331` and `5d57b022`). A
live micro-spike (TASK-PRV-001 @ `94f3331`, real bridge, run twice) DIVERGED and was DETERMINISTIC,
but the **scope-matched CONTROL is RED**: `mypy --strict` genuinely fails on the inline sample in the
regeneration environment (`1 failed, 28 passed`), and the mutation only makes an already-FAILING test
SKIP (`28 passed, 1 skipped`) — not the clean green-with-hidden-skip DC-05 shape. Seeding a defect on
a non-green scope violates the known-green premise, so this construct is **not admissible**. The
other study_tutor skipifs (at `5d57b022`) are all live-server `_skip_no_server` guards — not
service-free — and non-unique. **study_tutor offers no viable second (DC-05) construct; it stays
DC-03-only.** Recorded in `recipes.py` (above `_plan_dc05_skipguard_jarvis`) and `agent-config.yaml`,
not force-fit. guardkit already spans 3 DC-classes; a same-repo 2nd skip-guard variant cannot fire
under first-match (its primary anchor is present in every guardkit tree), so guardkit gains nothing
here — also recorded.

## 4. Projected distinct-row yield

- **jarvis R-DC05-skipguard:** jarvis's 4 JNB tasks are all at ONE sha → the mutated bundle over the
  pinned scope is identical across them → **+1 distinct DC-05 reject row** after dedup (modulo the
  0.075 recipe weight's sampling). The qualitative win is the diversity itself: **jarvis DC-class
  count 1 → 2** (DC-08 + DC-05), converting an `anchor_skipped` cell into a real row and giving the
  corpus a jarvis defect shape it never had. study_tutor tasks now cleanly `anchor_skipped` for
  R-DC05-skipguard (verified — no refusal noise).
- **Corpus effect:** small (+~1 distinct row) but on-thesis — the cycle-5 receipt already named the
  refusal-recovery well as drying and anchor breadth (not more tasks) as the path forward. This lane
  adds breadth where the tree honestly allowed it (1 of 3 attempted repo×DC-class cells) and records
  the 2 ceilings.

## 5. Tests + suite

- `tests/test_qav_injector.py` (+3, net): jarvis R-DC05-skipguard plants the labelled DC-05 defect
  and nothing else (verbatim `test_fleet_memory_payloads.py` skip-guard fixture); guardkit ⊥ jarvis
  first-unique-match across disjoint trees; `_first_anchor` re-raises AnchorNotFound loudly when
  neither anchor is present.
- `tests/test_qav_generate.py`: the shipped-config tokenisation-law guard now also asserts the jarvis
  R-DC05-skipguard per-recipe pin is present.
- Full suite: `uv run --no-sync pytest -q` → **PASS** (2508 baseline maintained; +2 net new tests →
  see run). `ruff` clean on the changed lines.

## 6. Files (adf-side; path-limited commit; no push; frozen surfaces untouched)

- `src/qav/recipes.py` — `_plan_dc05_skipguard` now dispatches via `_first_anchor(guardkit, jarvis)`;
  `_plan_dc05_skipguard_guardkit` (existing body, byte-identical mutation) + `_plan_dc05_skipguard_jarvis`
  (new); study_tutor ceiling recorded as a comment. ids/families/dc_classes/expected_signature frozen.
- `domains/qa-verifier/agent-config.yaml` — `test_commands_per_recipe.jarvis.R-DC05-skipguard` pin +
  provenance comment (+ study_tutor ceiling note).
- `tests/test_qav_injector.py`, `tests/test_qav_generate.py` — the tests above.
- `domains/qa-verifier/receipts/anchor-diversity-dc05-jarvis-2026-07-22.md` — this receipt.
- Corpus repos read-only (jarvis `1fc7309` / study-tutor `f843cb5` HEADs unchanged; scratch worktrees
  removed). ed00704 validators byte-frozen. Keepalive timer never touched (flock-guard held). No push.
