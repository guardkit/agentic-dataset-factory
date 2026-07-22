# Receipt — STUDY_TUTOR EVIDENCE-SURFACING: the premise refuted, the substrate proven fit, one real scrub bug fixed (2026-07-22)

> **THE BRIEF'S PREMISE IS WRONG, AND THE EVIDENCE SAYS SO.** The coordinator's read —
> "study_tutor legs still refuse `evidence_invariant` (bundles identical to control)" — does not
> hold. Reproduced live through the REAL bridge (CPU-only, zero fleet): **no study_tutor seeded_code
> reject leg ever REACHES regeneration.** All 77 study_tutor recipe×task combos (7 discovered tasks ×
> 11 recipes) turn away as **`anchor_skipped`**, never as an `evidence_invariant` refusal — there is
> no bundle to compare, so nothing to refuse. The integration-profile fix (layer 1) DOES reach
> study_tutor: its CONTROL regenerates to `gathering_status=complete`, `all_gates_passed=True` (not
> the old `partial_gate_abort`). And study_tutor is **NOT** structurally service-dependent: a
> service-free unit surface exists at the approved sha and, under the fix + a pinned command,
> **surfaces a real source defect deterministically**. The one genuinely-fixable thing the probe
> uncovered was a latent determinism hole in the scrub (guardkit's `findings` lists come back in
> NON-DETERMINISTIC ORDER) — **fixed adf-side, hermetic tests + a live two-run spike, `contracts.py`
> frozen, the divergence guard STRENGTHENED.** No forced match; no speculative study_tutor recipe;
> the guard stays the arbiter.

Factory HEAD at investigation: `cbeb9a0`. Corpus repos read-only, HEADs unchanged: study-tutor
`f843cb5`, guardkit `b68c9e9d` (detached scratch worktrees only, cleaned). ed00704 validators
byte-frozen; `contracts.py`/`recipes.py`/`injector.py` untouched. No push. DF-008.

---

## 1. The finding — study_tutor legs ANCHOR-SKIP, they do not refuse

Full `inject()` path (not just `recipe.plan`) run over all 7 discovered study_tutor source tasks
(FEAT-70A4 TASK-PRV-001..007 @ `94f3331`, now record-resolvable via the factory record-store):

| outcome | count |
|---|---|
| `AnchorNotFound` → **`anchor_skipped`** | **77 / 77** |
| anchored (a reject leg regenerated) | **0** |
| `evidence_invariant` refusals | **0** |

- **10 / 11 recipes** fail at the PLAN phase — the recipe probes are guardkit-shaped
  (`chunk_threshold __init__`, `analyze_wiring`, `run_bdd_for_task`,
  `pytest.importorskip("guardkitfactory.wiring")`, `quality_gates/__init__.py`,
  `skipif(not IMPORTS_AVAILABLE)`, the `TASK-BDD-E8954` unit module) or match study_tutor's tree
  **ambiguously** (`@given/@when/@then` and `plan_audit` each hit many files — `_find` correctly
  declines a non-unique target).
- **R-DC14-narrative** is the ONLY recipe whose plan matches a unique file
  (`tasks/backlog/TASK-PRV-001-…​.md`), but its EDIT then fails:
  `edit … matched 0<1 times (pattern '(files_(?:created|modified)\s*[=:]\s*\[)')` — the markdown
  mentions "files_created" in PROSE, never as an injectable `files_created = [ … ]` list. So `inject`
  raises `AnchorNotFound` at edit-apply → **`anchor_skipped`**, exactly like the other ten.

**This reconciles the receipts.** The poison-guard run recorded "study_tutor: 0 refusals,
`anchor_skipped` unchanged"; growth-cycle-2 recorded "all 20 `evidence_invariant_rejected` were
guardkit." Both are the SAME fact seen here: study_tutor contributes zero seeded reject regenerations,
so it can produce zero refusals. The brief's "study_tutor legs still refuse evidence_invariant" is an
inaccurate read of the `anchor_skipped` tally — corrected here, evidenced.

## 2. The integration-profile fix REACHES study_tutor (layer 1 is not guardkit-only)

Real bridge, study_tutor TASK-PRV-001 @ `94f3331`, `task_type=integration`, record materialized from
the factory record-store, zero model/GPU/fleet:

- CONTROL bundle: `gathering_status = complete`, `quality_gates.all_gates_passed = true`.

The render-collapse receipt's Reproduction 2 ("study_tutor is fully source-blind … both
`partial_gate_abort`") described the PRE-FIX behaviour. Under the shipped 4-layer fix the study_tutor
control no longer aborts — the sanctioned `integration` profile (whose required gates match the
materialized record) proceeds. **The render-collapse receipt's "all 11 reject recipes are
EXPECTED-MISSES on study_tutor" verdict stands, but its STATED REASON ("partial_gate_abort makes it
source-blind") is now stale.** The accurate reason is §1: no recipe anchors.

## 3. study_tutor is NOT service-dependent — a service-free surface exists and works

The brief asked whether study_tutor's tests env-fail identically for control and mutated ⇒ honest
structural-unfit. Answer: **no — that is not the wall.**

- study_tutor's venv is runnable (`.venv/bin/python` → pytest 9.0.3).
- Many study_tutor integration tests DO need throwaway Postgres (`tests/integration/knowledge/store/…`,
  `session/service/…`, keycloak) — the historical service dependency is real.
- But the discovered task's own unit surface is **service-free**:
  `tests/unit/knowledge/test_corpus_models.py` → **15 passed in 0.02s**, no services, and BOTH it and
  its source (`src/study_tutor/knowledge/corpus_models.py`) exist at the approved sha `94f3331`.

**Source-sensitivity spike (real bridge, `task_type=integration`, `test_command` pinned to the
service-free unit scope, one manual source break, run twice):**

| leg | scrubbed bundle sha256[:16] |
|---|---|
| CONTROL (no-op) | `8da8d8305e71e5a2` |
| MUTATED run 1 | `61d32efc36518757` |
| MUTATED run 2 | `61d32efc36518757` |

- **(A) DIVERGED** — control ≠ mutated; the planted break surfaced as real evidence
  (`independent_test_classification.failure_class = "collection_error"`, the actual
  `cannot import name 'SourceType' …` in the excerpt). The evidence-divergence guard would PASS it.
- **(C) DETERMINISTIC** — run 1 == run 2 byte-for-byte (after the §4 fix).

So the substrate — profile + pinned service-free command + scrub — is **fit** for a study_tutor
source defect the moment a study_tutor-shaped recipe exists. What is missing is the RECIPE, not the
bridge/config plumbing.

## 4. The one real bug the probe found — `findings`-list order non-determinism (FIXED)

Before the fix the two MUTATED runs above hashed DIFFERENTLY (`28c06e19…` vs `a466c182…`) despite
identical inputs and the existing scrub. The two-run post-scrub diff isolated it to
**`mocked_seam.findings` — a list of dicts returned in a NON-DETERMINISTIC ORDER**: the identical
finding set (same `symbol`/`lineno`/`why` tuples for `pipeline_module`, `adapter_module`, …) came
back PERMUTED. The scrub normalized timing/paths/addresses but never list order.

This violates the scrub's own documented invariant ("two regenerations of the SAME mutated worktree
scrub to byte-identical bundles") and is an order-noise hole in the **evidence-divergence guard**: a
source-blind reject whose finding-set equals its control's could hash differently by ORDER ALONE and
slip past the guard as a false divergence — the exact "defeat dedup by noise" failure the timing
scrub was built to close. General to any repo (guardkit included), not study_tutor-specific.

**Fix (adf-side, `contracts.py` frozen):** `src/qav/scrub.py` gains `CANONICALIZE_LIST_KEYS =
{"findings"}` — after a list's dict elements are scrubbed, a `findings` list is re-sorted by canonical
element content. Sorting is **information-preserving** (set + multiplicity untouched; only order
changes), so unlike a key-drop or a text-sub it can ONLY strengthen the guard: a genuinely different
finding-SET still differs after the sort (hermetically tested). This is the sole list safe to
canonicalize structurally — it re-orders, it never drops.

- `src/qav/scrub.py` — `CANONICALIZE_LIST_KEYS` + `_canonicalize`, applied after element-scrub in
  `_scrub`; module docstring documents the surface and the empirical proof.
- `tests/test_qav_scrub.py` — +5 hermetic tests (order-permutation → identical; real set-difference
  preserved; sort key uses scrubbed content; non-`findings` lists keep order; scalar `findings`
  untouched). Scrub file 10 → 15 tests.
- Full suite: **`uv run --no-sync pytest -q` → 2494 passed**, zero failures.

## 5. Fixed vs unfit — per recipe class, for study_tutor

| layer | verdict |
|---|---|
| integration profile-gate (layer 1) reaching study_tutor | **FIXED already** — control regenerates `complete`, proven |
| per-repo stack pin (layer 2) on a service-free scope | **AVAILABLE** — `tests/unit/knowledge/test_corpus_models.py` runs service-free and surfaces a source break |
| scrub determinism on study_tutor bundles (layer 3) | **FIXED this lane** — `findings`-order canonicalized, spike deterministic |
| all 11 seeded_code REJECT recipes anchoring on study_tutor | **UNFIT — honest expected-miss** — recipes are guardkit-shaped; 77/77 `anchor_skipped`. NOT service-dependent, NOT source-blind. |

**No study_tutor `test_command` was pinned in `agent-config.yaml`** — deliberately. With zero
anchoring recipes there is no reject leg to run it against; pinning it would only perturb the 7
honest study_tutor CONTROL bundles (whose approve rides the authentic green record) for zero
reject-side gain. That is config for a dead path — declined per the no-gold-plating discipline. The
pin belongs WITH the study_tutor-shaped recipe that would use it, in a future recipes-anchors lane
(the surface explicitly EXCEPTED from the ed00704 freeze), where the §3 spike is the ready template.

## 6. The honest wall (the brief's "spike proof or wall")

The requested study_tutor spike — "one task, one recipe, two runs: diverged + real evidence +
deterministic" — cannot be run with a RECIPE, because no recipe anchors (§1). That is the honest
wall, and it is not moved by a forced match. What CAN be shown, and is (§3), is that the SUBSTRATE
clears all three gates on a real source break over a service-free scope — so the wall is precisely a
recipe-authoring gap, not an evidence-surfacing or service-dependency wall. The divergence guard
remains the arbiter; divergence stays EARNED.

## 7. Files (adf-side; path-limited; no push; contracts.py frozen)

- `src/qav/scrub.py` — `CANONICALIZE_LIST_KEYS` + `_canonicalize` (the `findings`-order fix).
- `tests/test_qav_scrub.py` — +5 hermetic canonicalization tests.
- Corpus repos read-only (study-tutor `f843cb5`, guardkit `b68c9e9d` — HEADs unchanged, scratch
  worktrees cleaned). Keepalive: no generation/fleet run in this lane (bundle regen is CPU/pytest
  only), so no keepalive exposure; timer never touched.
