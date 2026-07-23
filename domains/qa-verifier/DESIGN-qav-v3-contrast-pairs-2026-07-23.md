# DESIGN — QAV v3: class-boundary contrast pairs + eval-side coverage

**Date:** 2026-07-23 evening · **Lane claim:** ai-transition exec-plan §7 (`7c5d798`) on Rich's
"proceed with the recommendations from the results" · **Evidence base:**
`RESULTS-qav-ft-v2-2026-07-23.md` (fleet-evals `0fbee7e`) + a 4-reader recon over the engine,
class semantics, corpus census, and exam boundaries (file:line cites throughout).
**Design doctrine carried:** the seeded_record precedent — engine-side only, ed00704 byte-frozen
set untouched, labels fixed by construction, anti-shortcut controls in proportion, micro-spikes
per boundary mandatory.

## 0. The one-minute version

v2 judges perfectly and attributes wrongly: DC-12 (69 rows, the biggest reject class) became an
attractor; DC-14 never fires; GN-1↔GN-2 swap deterministically. Root cause, now precise: **class
correlates with bundle SHAPE in the training corpus** (record-mutation shapes → DC-12/DC-14,
source-injection shapes → DC-03/DC-05/DC-08), so the model learned shape→class, not
signal→class. And the ONE fact that decides the exam's hard cases — *DC-12's owning signature
is a `plan_audit` violation block; a bundle whose `plan_audit` is null/clean cannot be DC-12* —
appears in no training contrast. The cure is **same-spine minimal pairs whose single differing
signal flips the owning class**, minted through the existing `R-BUNDLE-*` direct-bundle seam,
with matched approve controls, plus **eval-side coverage for free** via the four tasks whose
`seeded_bundle` family already hashes to eval. NOT more volume: ~60–80 surgical rows.

**A binding negative finding shapes this design: the trained target is the BARE verdict JSON**
(staging strips `<think>` and the fence — `prepare_qav_sft.py:438-462`, receipt
tune-train-v2 §1). Rationale prose teaches the tune NOTHING. The boundary must live in the
exemplar distribution (bundle, label, locus) — contrastive `<think>` was considered and
REJECTED as a lever on this ground.

## 1. What the exam demands vs what the corpus teaches (the three boundary cuts)

| Boundary | Exam ground truth | v2's answer | Why the corpus taught the error |
|---|---|---|---|
| **DC-12 ↔ DC-03** (GN-3, GN-4) | composition vacancy: `behavioural_oracle`/`wiring`/`runtime_parity`/`stub_scan` **null** under green suites, `plan_audit` **null**, `gathering_status=complete` → DC-03 | DC-12 ×6 reps | every DC-12 exemplar carries `plan_audit.status=violation` + `partial_gate_abort`; no exemplar shows the same green-suite spine with plan_audit null → DC-03. The negative rule (plan_audit-null ⇒ not-DC-12) is untaught |
| **DC-14 ↔ DC-12** (RC-01) | confident claim + **zero executed tests** (`tests_run=0`, `collected 0`, `signal_absent=true`), `gathering_status=complete`, NO plan_audit → DC-14 | DC-12 ×3 reps | trained DC-14 = honesty file-existence discrepancies + `partial_honesty_abort` — a signature RC-01's bundle does not carry; the vacuous-green semantics nearest-neighbor in training is DC-12's "unverifiable at gate time" prose |
| **DC-08 ↔ DC-03** (GN-1↔GN-2) | the load-bearing null is the one **the task owns**: authoring task + `bdd_authoring_sweep:null` → DC-08; wiring task + `wiring/runtime_parity:null` (with `bdd:null` as distractor) → DC-03 | swapped, deterministically | training DC-08/DC-03 rows never co-present both null families on one spine, so "any bdd-null token → DC-08-ish" survives |

Anchor vocabulary the new loci must speak (exam-verified, single tokens — safe under the
shingle gate): DC-03 → `call site`, `runtime_parity`, `producer`, `vacuous`, `kwargs`,
`soft-fail`, `pin test`, `production construction` · DC-08 → `bdd_authoring_sweep`,
`bdd … null`, `step definition`, `absent signal`, `authoring task` · DC-14 → `tests_run`,
`collected 0`, `signal_absent`, `no test signal`, `narrative` · DC-12 (corpus-native, not
exam) → `plan_audit.status=violation`, `plan_audit_passed=False`, `missing_files`,
`partial_gate_abort`.

## 2. The mechanism: R-BUNDLE pair recipes (the only seam that can mint these shapes)

**Why bundle-side:** the DC-03 exam shapes are null-field composition vacancies and the DC-14
shape is zero-executed tests — `wiring`/`stub_scan`/`runtime_parity`/`tests`/`quality_gates`
are RECOMPUTED by the live gather machinery (the proven R-RECORD-DC05-skipmask inertness,
`record_recipes.py:449-486`), so record mutations cannot produce them. The direct-bundle seam
already exists and is namespace-ready: `_BUNDLE_MUTATION_RECIPES` + `build_bundle_mutations`
(`generate.py:832-890`), `R-BUNDLE-*` ids fall through `_family_of` to family `seeded_bundle`
(`generate.py:369-374`) — pair split-atomicity per task is structural.

**DESIGN v1.1 (post adversarial-coach FAIL, four blocking findings honored): the existing
`_BUNDLE_MUTATION_RECIPES` seam is NOT sufficient** — its label is hardcoded reject
(`generate.py:225-227`), it reads disk-discovered bundles (`generate.py:717-745, 939-955`)
which do not exist for guardkit/TASK-QAWE-004 or study_tutor/TASK-PRV-004, its recipes cannot
be task-scoped, and the seeded_bundle cap base (`generate.py:1633`: `seeded_code_written +
seeded_control_written` = 68, EXCLUDING the 193 record rows) admits only ~22 rows. **THE
ENGINE WORK-PACKAGE (all engine-side, no frozen file):**

- **New module `src/qav/bundle_pairs.py`**: a `PairRecipe` registry mirroring
  `record_recipes.py` discipline (frozen dataclasses, import-time self-checks, pure
  dict→(mutated_bundle, locus)|None transforms, `_stable_*` determinism) with THREE deltas:
  (1) **verdict-carrying** — reject sides carry `dc_class`; approve controls carry
  `dc_class=None` and label `{verdict: approve, findings: [], ground_truth_source: seeded}`;
  (2) **task-scoped** — each recipe declares a task predicate/allowlist (axis C's ownership
  cut, the eval-cohort-first ordering, the budget discipline); (3) ids in the
  `R-BUNDLE-PAIR-*` namespace (falls through `_family_of` to `generation_mode` — rows emit
  the frozen-allowlisted mode `seeded_bundle`, so the §4 eval buckets hold unchanged).
- **New engine path `_run_contrast_pairs`** (sibling of `_run_seeded_record`,
  `generate.py:1539-1612` pattern): operates on each source task's **in-run regenerated,
  scrubbed CONTROL bundle** (all 28 source tasks reachable — including QAWE-004/PRV-004,
  whose records regenerate fine; this is the coach-named cure for the missing eval tasks);
  banks **pair-atomically** (both sides gate-accepted or both routed loudly to
  rejected.jsonl — teacher/coach dropping one side can never bank a lone sibling);
  enforces the three-distinct-hashes law IN-ENGINE (scrubbed control vs side-a vs side-b —
  any collision = loud `pair_hash_collision` refusal; NOTE the divergence guard does NOT run
  for bundle rows (`generate.py:1151-1155` vs `1652-1657`) and silent row_id dedup
  first-writer-wins (`generate.py:574-586`) is the real failure mode this law preempts).
- **Own budget knob `contrast_pair_budget`** on GenerateConfig + agent-config.yaml (target
  ~96 candidates ⇒ ~80 banked): the legacy `seeded_bundle_cap` and its base stay UNTOUCHED
  for the legacy R-BUNDLE recipes; pair rows are counted and receipted separately.
- **Cue-audit widened** (`generate.py:535-537`): scan also for `R-RECORD-*`/`R-BUNDLE-PAIR-*`
  ids leaking into bundle prose (belt-and-braces; minted prose also avoids the sentinel word
  list + `…` hard triggers at `generate.py:394-401, 538-539`).
- **Staging crosscheck widened** (`prepare_qav_sft.py:512` is train-only): the frozen-exam
  8-gram shingle check runs over train AND eval staged rows (engine-side file, not frozen).
- **Run-config hygiene**: the corpus run must clear the `# limit: 4` pilot residue
  (`agent-config.yaml:47`) — `_seeded_limit_hit` would otherwise starve the pair path, which
  runs after seeded_code.

**Recipes (ids; builder adjusts surface details against the pinned 25-field schema —
`validate_bundle` checks key-subset + honesty-present only, all fields nullable,
`contracts.py:119-140`; each side must also pass `evidence_empty_reason`
(`generate.py:424-449`) — `complete` and `partial_gate_abort` both pass, a typo'd
`gathering_status` silently becomes an evidence-empty reject, so the spike asserts it):**

**v1.2 AMENDMENT (post-spike NO-GO, 2026-07-23 late): the populate-with-defect doctrine.**
The boundary spikes proved regenerated control bundles NEVER carry `runtime_parity`, and carry
`wiring`/`bdd` only on study_tutor spines (record-replayed, not gathered, under the integration
profile) — so any recipe guarded on severing a populated field is anchor-absent corpus-wide on
guardkit/jarvis spines and the pair-atomic law banks ZERO axis-A pairs. The label-honesty rule
underneath: **on a spine whose approve control already has a field null, nulling cannot be a
reject signal (the corpus would contradict itself same-task); the reject side must ADD
defect-bearing evidence.** Therefore: `A-dc03` = POPULATE `wiring` with deterministic
defect-bearing call-site evidence (missing-kwargs / production call sites unexercised — the
GN-4 anchor vocabulary), plan_audit untouched-null, suites green → DC-03; `CTRL-comp` =
populate `wiring` HEALTHY (its anti-shortcut mate, fires everywhere); `C-dc08` = POPULATE
`bdd_authoring_sweep` with a defect-bearing sweep (undefined steps on scenarios the task owed
— the SMP-002 populated-sweep DC-08 sub-shape), plus a new `CTRL-bdd` approve mate (healthy
sweep) on the same BDD-owning tasks. The pure null-vacancy DC-03 shape is still taught — via
`C-dc03` on study_tutor wiring-owning spines (controls carry `wiring` populated, so nulling
honestly diverges), and the ownership rule from the approve side via `CTRL-comp`'s
bdd-null-not-owned. HONEST CAP: the GN-1 pure bdd-null shape and GN-3 pure oracle-null shape
have no same-task pair construction (the contradiction above) — named, not hidden. Also
adopted from the build coach: a post-run pair-census sibling-parity assertion (the §3.6
receipt promise) lands in the engine/driver.

Axis A — the attractor cut (DC-12 ↔ DC-03), same task, same spine:
- `R-BUNDLE-PAIR-A-dc12` (reject DC-12): populate `plan_audit` as a violation block
  (status=violation, severity=high, `missing_files` derived cue-clean per the
  `_derive_nonexistent_paths` law) + `gathering_status=partial_gate_abort`; suites stay green.
- `R-BUNDLE-PAIR-A-dc03` (reject DC-03): same spine, `plan_audit` **null**, null out
  `wiring` + `runtime_parity` (+ variant: `behavioural_oracle` — the GN-3 producer shape);
  suites green, `gathering_status=complete`. Locus speaks the DC-03 anchor vocabulary.

Axis B — the RC-01 cut (DC-14 ↔ DC-12), same task, same spine:
- `R-BUNDLE-PAIR-B-dc14` (reject DC-14): zero-test surfaces (`tests.tests_run=0`,
  `collected 0` in the stdout tail, `independent_tests.signal_absent=true`) + a confident
  fresh-prose honesty claim; `gathering_status=complete`, NO plan_audit.
- `R-BUNDLE-PAIR-B-dc12` (reject DC-12): same spine, tests genuinely green (non-zero, varied
  counts), `plan_audit` violation block, `partial_gate_abort`.

Axis C — the ownership cut (DC-08 ↔ DC-03), **cross-task cohorts** (a task owns what it owns —
the two sides ride different tasks with deliberately matched surfaces; both sides co-present
`bdd`-family nulls AND `wiring`-family nulls, and what differs is which null the task owns):
- `R-BUNDLE-PAIR-C-dc08` (reject DC-08): on BDD-owning tasks (guardkit BDDW-002 / QAWE
  family): `bdd:null` + `bdd_authoring_sweep:null` load-bearing; `wiring` populated-healthy.
- `R-BUNDLE-PAIR-C-dc03` (reject DC-03): on wiring-owning tasks: `wiring:null` +
  `runtime_parity:null` load-bearing; `bdd:null` present as the distractor.

Matched approve controls (the anti-shortcut law, in proportion — every surface family both ways):
- `R-BUNDLE-PAIR-CTRL-audit` (approve): `plan_audit` populated + PASSING on the same spine.
- `R-BUNDLE-PAIR-CTRL-comp` (approve): `wiring`/`runtime_parity` populated-healthy, `bdd:null`
  present but NOT owned (teaches the ownership rule from the approve side).
- `R-BUNDLE-PAIR-CTRL-tests` (approve): tests genuinely green with an honest matching claim on
  the axis-B spine.

Labels fixed by construction (never a model call), `ground_truth_source: "seeded"`,
classes within frozen `PHASE1_DC_CLASSES`. Loci are bundle-field=value anchored, FRESH prose.

## 3. The laws every recipe must satisfy (spike-verified before any corpus run)

1. **Three-distinct-hashes law:** per task, scrubbed control vs side-a vs side-b = three
   DISTINCT `bundle_content_hash` values, each side carrying its OWN class signature; ×2 runs
   byte-identical (determinism). Enforcement is IN-ENGINE (`pair_hash_collision` loud refusal
   in `_run_contrast_pairs`) + unit tests + the spike — NOT the divergence guard, which never
   fires for bundle rows (coach advisory 1; the silent alternative is row_id dedup
   first-writer-wins, a label race this law preempts).
2. **Schema law:** every minted bundle passes `validate_bundle` (extra=forbid, pinned 25-field
   set) — null existing fields, never add fields.
3. **Shingle law:** no minted bundle shares an 8-consecutive-normalized-word run with either
   frozen exam bundle body (`prepare_qav_sft.py:344-388` semantics). Practically: fresh
   task-local ids, varied numeric values, fresh claim/notes prose, never copy exam value prose.
   The spike runs a pre-check replica against both exam bodies over BOTH splits' minted rows;
   staging's hard gate re-proves TRAIN rows and (per the v1.1 work-package) is widened to
   cover eval rows too — as-shipped it is train-only (`prepare_qav_sft.py:512`, coach adv. 2).
4. **Split law:** axes A/B are same-task ⇒ atomic by construction. Axis C cohorts: the spike
   reproduces `assign_split` (seed `qav-phase1`, holdout 0.15) for every candidate task under
   family `seeded_bundle` and pins each cohort wholly train-side or wholly eval-side. No
   force-eval knob; the frozen contamination check is satisfied structurally.
5. **Anti-shortcut proportion:** approve controls ≥ ~40% of new rows; both null-distractor
   approves and populated-healthy approves present; derived paths/counts vary deterministically
   (`_stable_*` helpers); no sentinel strings; the per-row cue-audit stays a hard gate.
6. **Budget law (v1.1):** pair rows ride their OWN `contrast_pair_budget` (engine knob, target
   ~96 candidates); the legacy `seeded_bundle_cap` and its `seeded_code+control` base
   (`generate.py:1633` — which EXCLUDES record rows and would admit only ~22) stay untouched
   for legacy R-BUNDLE recipes. Eval-cohort tasks are processed FIRST so budget truncation can
   never starve eval (coach blocking 4). Post-run pair census: every banked side has its
   sibling banked (pair-atomic law), receipted.

## 4. Eval-side coverage (C2) — the free seam

The four included tasks whose `(repo, task, "seeded_bundle")` group hashes eval (buckets
coach-reproduced from the code: guardkit QAWE-004 = 239, jarvis JNB-001 = 486, jarvis
JNB-008 = 942, study_tutor PRV-004 = 1323; threshold 1500; no other provenanced task hashes
eval under this family, and BDDW-001 misses at 1538) get the FULL pair set FIRST — eval gains
DC-12, DC-14, DC-03 reject rows plus matched approves, all via the `_run_contrast_pairs`
control-bundle path (which is what makes QAWE-004/PRV-004 reachable at all — they have no
disk-discoverable bundles, coach blocking 3). Everything else lands train by the same hash.
No split-law change. Honest cap: no BDD-owning task hashes eval, so axis-C DC-08 eval rows
are not available this cycle — eval keeps its 4 organic DC-08 rows; named, not hidden.
The seq-gate budget is a named spike check: each minted eval-side bundle's rendered row must
tokenize < 20,480 (the v2 audit machinery re-used).

## 5. Row budget (surgical, not volume — the RESULTS' own instruction)

| Cohort | Tasks × recipes | Rows |
|---|---|---|
| Eval cohort (the 4 eval-hash tasks) | 4 × (A-pair 2 + B-pair 2 + CTRL 2–3) | ~24–28 |
| Train axis A+B pairs | ~8 record-rich tasks × 4 reject sides | ~32 |
| Train axis C cohorts | ~4+4 tasks × 1 side each | ~8 |
| Train controls | in proportion | ~16–20 |
| **Total new R-BUNDLE rows** | | **~80** |

DC-12 reject GROWTH is deliberately ~zero net-of-pairs (it is the attractor; its pair sides
exist for contrast, counts stay lean). Expected corpus: ~302 → ~380, approve_share stays
in-band (manifest advisory + staging tripwire re-prove).

## 6. What is NOT in scope

- No new `<think>` levers (stripped at staging — see §0).
- No record-family growth (28/30 tasks exhausted at 8/8 recipes; the two unexploited tasks
  UPT-001/QAV-006 hash train and cure nothing the pairs don't).
- No frozen-file edits: contracts/injector/contamination/gold_negatives/manifest/harvest byte
  stay; fleet-evals frozen exam surfaces untouched (a NEW held-out attribution exam task is a
  separate future fleet-evals lane, noted not claimed).
- No new metadata keys (pair membership rides the `injection_recipe` id string, recoverable).

## 7. Execution order (after this design is coach-PASSED)

1. Build: pair recipes + wiring + unit tests (engine-side: `generate.py` bundle catalog or a
   sibling module), builder + independent adversarial coach.
2. Spikes: one per axis (A on a record-rich train task; B likewise; C one cohort member each
   side; PLUS one eval-cohort task end-to-end) — the §3 laws are the pass bar; receipted with
   sha[:16] tables before any generation.
3. Corpus run (GPU: the generation set under the flock-held pause; memory pre-flight per the
   §8 wedge lessons) → census receipt with pair counts + class support per split.
4. Staging (all gates incl. shingle + seq-audit) → train v3 → merged-gen gate → GGUF
   `qav-ft-v3` → serving entry → the sealed-gate re-exam → `RESULTS-qav-ft-v3`.
