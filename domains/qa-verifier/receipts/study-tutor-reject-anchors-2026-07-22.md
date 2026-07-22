# Receipt — STUDY_TUTOR REJECT ANCHORS: the vein opened, one faithful DC-03 recipe SPIKE-GREEN (2026-07-22)

> **THE RECIPE-ANCHOR GAP IS CLOSED FOR DC-03, AND THE SUBSTRATE'S FITNESS IS NOW PROVEN THROUGH A
> REAL RECIPE — NOT A MANUAL BREAK.** The SA finding (study-tutor-evidence-surfacing) established
> that study_tutor's zero rejects were a pure recipe-anchor gap: its service-free substrate
> (`tests/unit/knowledge/test_corpus_models.py`) surfaces a real corpus_models defect deterministically
> under the 4-layer deep-regeneration fix. What was missing was a study_tutor-shaped RECIPE. This lane
> authors one — **R-DC03-callsite's study_tutor anchor variant** — behind a MINIMAL per-repo
> anchor-variant mechanism, and proves it on the real bridge: control + mutated + two runs →
> **DIVERGED, real ValidationError evidence, deterministic** (the evidence-divergence guard passes it).
> The other 10 recipes remain HONEST study_tutor expected-misses (guardkit-verbatim constructs absent,
> or the generic shape non-unique) — recorded per-recipe, at both approved shas, never force-matched.

Factory HEAD at start: `0b76a57`. Corpus repos read-only, HEADs unchanged: study-tutor `f843cb5`
(detached scratch worktrees only, all removed; the pre-existing `FEAT-39E1` autobuild worktree is not
ours). `contracts.py` / recipe ids / families / dc_classes / mutation-SEMANTICS byte-frozen; the
evidence-divergence guard + scrub UNTOUCHED. Labels never model-derived. No push. DF-008.

---

## 1. The per-repo anchor-variant mechanism (the coordinator's minimal-mechanism ruling)

One anchor STRING genuinely cannot match both repos: guardkit's DC-03 call-site drift anchors on
`FullDocParser.__init__(… chunk_threshold …)`; study_tutor has no such `def __init__` — its analog is
a retired pydantic field on `CorpusChunk`. So `src/qav/recipes.py` gains `_first_anchor(files,
*variants)`: a recipe's `plan` may carry an ORDERED list of per-repo anchor variants; the **first whose
shape is present wins** (first-unique-match), and if NONE match it raises `AnchorNotFound` **loudly**,
naming every variant's reason (the FEAT-DD4F never-a-silent-no-op law). The corpus trees are disjoint,
so at most one variant's anchor is ever present.

- **Scope of the change:** only `R-DC03-callsite`'s `plan` was split — into `_plan_dc03_callsite_guardkit`
  (the existing body, byte-preserved) and `_plan_dc03_callsite_study_tutor` (new), combined via
  `_first_anchor`. Every other recipe is untouched. The `Recipe` dataclass, all ids/families/dc_classes,
  `expected_signature` strings, and `injector.py` are byte-frozen. The mechanism lives entirely in the
  sanctioned ANCHOR-STRING territory (ed00704 recipes-anchors exception) plus this one combinator.
- **Why minimal and why needed:** a single shared anchor string cannot express two disjoint verbatim
  constructs; a per-recipe ordered candidate list is the smallest mechanism that keeps semantics/families/ids
  frozen while letting the anchor strings differ per repo. Declared plainly here for the coach.

## 2. The study_tutor DC-03 anchor (semantic fidelity, unique match, genuinely dies)

**Real construct** (`src/study_tutor/knowledge/corpus_models.py` @ `94f3331`, FEAT-70A4/TASK-PRV-001):
the `CorpusChunk` pydantic-v2 model declares a REQUIRED `chunk_index: int` field under
`model_config = ConfigDict(extra="forbid")`, and its call sites — the loader (TASK-PRV-002), the
retrieval / quote-verifier consumers, and the unit payloads in `tests/unit/knowledge/test_corpus_models.py`
— all instantiate `CorpusChunk(…, chunk_index=N)`.

**The mutation** (one edit, one file): retire `chunk_index: int` from the model's contract. This is the
SMP-003 retired-member call-site drift expressed in study_tutor's construct vocabulary — the dropped
`chunk_index` field is the analog of guardkit's dropped `chunk_threshold` kwarg. Because the contract is
`extra="forbid"`, every surviving caller's instantiation now raises `ValidationError`: **the dead call
site genuinely dies, and the service-free unit scope catches it as real failing tests** (the 9c212db
discipline). The NOTHING-else self-check holds (only `corpus_models.py` changes).

- **Anchor uniqueness:** the probe `citation_anchor: CitationAnchor | None = None` selects `corpus_models.py`
  uniquely across the scoped map — the markdown design docs write the field WITHOUT the `= None` default,
  and `.guardkit` records (the one other hit) are excluded from the map by `EXCLUDE_DIR_PARTS`. Verified
  stable at BOTH approved shas (corpus_models.py is byte-identical across `94f3331` and `5d57b022`).
- **test_command pinned** in `agent-config.yaml → regeneration.test_commands`:
  `study_tutor: "pytest tests/unit/knowledge/test_corpus_models.py -q -p no:cacheprovider"` — the
  SA-proven service-free scope; the mutated file's tests are IN scope.

## 3. Per-recipe study_tutor verdict (real scoped map, BOTH approved shas)

Ran all 11 recipes' `inject()` over the real scoped file map at `94f3331` (340 files) and `5d57b022`
(871 files). Identical verdict at both shas:

| recipe | study_tutor verdict | reason |
|---|---|---|
| **R-DC03-callsite** | **ANCHORED** → `src/study_tutor/knowledge/corpus_models.py` (unique) | the new study_tutor variant; SPIKE-GREEN (§4) |
| R-DC03-producer | anchor_skipped | guardkit `analyze_wiring(...)` producer call absent |
| R-DC03-kwargs | anchor_skipped | guardkit `run_bdd_for_task(` composition call absent |
| R-DC03-mockseam | anchor_skipped | `pytest.importorskip("guardkitfactory.wiring")` seam absent |
| R-DC05-sysmod | anchor_skipped | `guardkit/orchestrator/quality_gates/__init__.py` absent |
| R-DC05-skipguard | anchor_skipped | study_tutor's skipif (planner/test_protocols.py) carries a DIFFERENT reason string — guardkit-verbatim anchor absent |
| R-DC08-undefstep | anchor_skipped | `@given/@when/@then` step modules EXIST (4, in `features/`) but are non-unique → `_find` declines; also outside the service-free scope (need the deepagents/graphiti substrate) |
| R-DC08-pendmask | anchor_skipped | same 4-module ambiguity |
| R-DC12-planvisible | anchor_skipped | broad plan-doc anchor non-unique across `.claude/` + `docs/` |
| R-DC14-narrative | anchor_skipped | the one unique plan-doc match is prose (`files_created` mentioned, never an injectable `files_created = [ … ]` list) — edit matches 0<1; the narrative signal is the excluded `.guardkit` record |
| R-ABSENT-junit | anchor_skipped | guardkit `TASK-BDD-E8954` junit module absent |

**These are honest expected-misses, matching the existing 5 guardkit expected-misses (semantic fidelity
over hit-rate).** DC-08 is the one live future candidate: study_tutor DOES ship pytest-bdd step modules
(unlike guardkit), but anchoring them needs (a) a unique-module per-repo variant AND (b) broadening the
pin into the service-DEPENDENT feature substrate — out of this minimal, service-free lane. Recorded, not
forced.

## 4. THE LIVE MICRO-SPIKE — one task, one recipe, real bridge, run twice

Task **study_tutor/TASK-PRV-001 @ 94f3331**; recipe **R-DC03-callsite** (study_tutor variant); real
guardkit `gather_evidence` via `SubprocessBridgeRegenerator`; `task_type=integration` (layer 1),
`study_tutor` test_command pinned (layer 2), record materialized from the factory record-store
(`domains/qa-verifier/record-store/study_tutor/TASK-PRV-001/`); every bundle scrubbed before hashing.
**Zero model / GPU / fleet** (bundle regen is CPU/pytest only). Flock-guard `-x
/var/lock/llama-swap-keepalive.lock` held UNCONDITIONALLY over the run; keepalive timer never touched.

| leg | scrubbed bundle sha256[:16] |
|---|---|
| CONTROL (no-op) | `637a4ebb69e66e0c` |
| MUTATED run 1 | `fc6ec70f7e0187da` |
| MUTATED run 2 | `fc6ec70f7e0187da` |

- **(A) DIVERGED** — control `637a4ebb…` ≠ mutated `fc6ec70f…`. The mutated bundle EARNS its divergence
  with real evidence, so the standing evidence-divergence guard **passes** it (no refusal).
- **(B) REAL EVIDENCE** — mutated `independent_test_classification.failure_class = "code"`; the planted
  defect surfaces as real FAILED tests carrying
  `pydantic_core._pydantic_core.ValidationError: 1 validation error for CorpusChunk / chunk_index /
  Extra inputs are not permitted [type=extra_forbidden, input_value=12, input_type=int]` across
  `test_corpus_chunk_accepts_primary_with_anchor`, `…_accepts_secondary_without_anchor`,
  `…_citation_anchor_defaults_to_none`, `…_round_trips_through_model_dump_and_validate`. The CONTROL over
  the same scope is clean-green (`failure_class=null`, no ValidationError) — its approve label is honest.
- **(C) DETERMINISTIC** — run 1 == run 2, byte-for-byte (after the `findings`-order scrub already banked).

**Verdict: all three gates GREEN.** study_tutor's substrate is fit for a study_tutor-shaped source
defect the moment a faithful recipe exists — and now one does. Note study_tutor's `pyproject.toml`
pins `pythonpath = ["src", "."]`, so the worktree's mutated `src/study_tutor` wins over the editable
install — a source-PACKAGE mutation surfaces here (unlike guardkit, where the render-collapse appendix
noted source-package mutations may be shadowed by the editable install; study_tutor sidesteps that).

## 5. Fixture tests + the AnchorNotFound law (hermetic)

`tests/test_qav_injector.py` (+3 tests, 17→20; full file green):
- `test_dc03_callsite_study_tutor_variant_retires_the_field_and_nothing_else` — a VERBATIM `CorpusChunk`
  construct + the `_primary_chunk_payload` call site (both lifted from the 94f3331 tree); asserts the
  variant retires `chunk_index` in the model file ONLY, leaves the payload's `chunk_index=12` intact
  (the dead call site), and names the locus.
- `test_dc03_callsite_variants_are_mutually_exclusive_across_disjoint_trees` — guardkit fixture → guardkit
  variant, study_tutor fixture → study_tutor variant; disjoint change sets.
- `test_dc03_callsite_raises_loudly_when_no_variant_anchors` — neither anchor present → `AnchorNotFound`
  loud, "no per-repo anchor variant matched".

Full suite: `uv run --no-sync pytest -q` → **2497 passed** (baseline 2494 + 3). `ruff` clean on the
changed files.

## 6. Files (adf-side; path-limited commit; no push; frozen surfaces untouched)

- `src/qav/recipes.py` — `_first_anchor` combinator + `R-DC03-callsite` split into guardkit/study_tutor
  anchor variants. Ids/families/dc_classes/`expected_signature`/mutation-semantics byte-frozen.
- `domains/qa-verifier/agent-config.yaml` — `regeneration.test_commands.study_tutor` pin + the now-accurate
  "study_tutor anchors R-DC03-callsite" comment.
- `tests/test_qav_injector.py` — the 3 hermetic tests above (verbatim corpus constructs).
- Corpus repos read-only (study-tutor `f843cb5` HEAD unchanged; scratch worktrees removed). `contracts.py`,
  `injector.py`, the divergence guard, and `scrub.py` byte-frozen. Keepalive timer never touched
  (flock-guard held over the CPU/pytest spike). ed00704 validators byte-frozen. No push. DF-008.
