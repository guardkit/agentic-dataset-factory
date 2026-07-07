# QAV Phase 1 — Dataset Generation Plan (seeded-defect mode design)

**Status:** WS2-B11 spec half, 2026-07-07 (Fable 5). This document is the design the Opus code
half implements — the **one dataset-factory code change** is §2's seeded-defect generation
mode. No generation runs before the GB10 calendar clears (HSBC demo 07-09 quiet window + the
82h Phase-3 PO run; `factory-program-plan-2026-07-07.md` §2.2 owns the box — hard guardrail).
**Companions:** `GOAL.md` (judgment criteria, targets), `OUTPUT-CONTRACT.md` (row/label/manifest
contracts), `SPEC-qav-gold-negatives.md` (the 4 real escaped-seam reconstructions).

## 1. Situation — why a third generation shape

The factory has three proven mechanisms: grounded book generation (tutor/architect/PO Phase 3),
generative no-book mode (PO Phase 1), and the coach-v3 synthetic recipe (deterministic spec →
teacher rationale → SFT row). QAV needs a **fourth, closest to coach-v3**: the truth of every
row is a *real or deliberately-planted code defect*, not model imagination. Rows are transforms
of real evidence artifacts; models only author rationale text against labels fixed by
construction. This is what keeps a judgment dataset honest — the coach-v2 saga proved both that
synthetic bundles work (train≠serve fears refuted) and that class balance, not sequence length
or base swaps, is what kills or saves the judge.

Volume reality (scope §5): real historical bundles = low hundreds at best across the 29
documented runs. The seeded-defect mode is what makes the dataset trainable.

## 2. The seeded-defect generation mode (the code change, for the Opus half)

**Pipeline (per seeded row):**

```
known-green task (corpus §2.1)
  → worktree checkout at the task's approved sha
  → INJECTOR applies one DC-class recipe (§3) as a patch          [deterministic]
  → guardkit CoachValidator.gather_evidence re-runs over the
    defective tree → regenerated CoachEvidenceBundle               [real gather, real bundle]
  → label fixed by construction: reject + {class, locus=injection site}, source=seeded
  → teacher model authors <think> rationale against the fixed label [only model step]
  → factory Coach gate: schema-valid, rationale-consistent-with-label, cue-audit clean
  → row + metadata → output/qa-verifier/
```

Two injection strategies, explicitly tiered:

- **`seeded_code` (primary).** Inject the defect into the working tree and *regenerate the
  bundle honestly* via guardkit's own `gather_evidence` (B-min path). The bundle is real; only
  the code is sabotaged. Highest fidelity — the evidence shows exactly what the Coach would
  have seen. Requires: guardkit importable against the target repo's worktree, the repo's test
  substrate runnable (venv per repo — the SIBTESTENV01 lesson), and GPU only for the teacher
  step. Mechanics note for the code half: drive `CoachValidator.gather_evidence` directly
  (library call), not a full autobuild turn — no Player, no llama-swap dependency for the
  gather step.
- **`seeded_bundle` (augmentation only, capped ≤25% of seeded rows).** Mutate a real serialized
  bundle's fields to a documented defect signature without re-running anything. Cheap, no
  worktree/test substrate needed — but risks teaching surface cues. Every `seeded_bundle` row
  passes the **cue-leakage audit** (extend `domains/coach-agent/audit_cue_leakage.py`
  conventions: field-distribution comparison vs real bundles, sentinel/ordering artefact scan);
  audit failure kills the row. Tagged distinctly in metadata so WS4 can ablate it.

**Harvest transform (same session of code, second entry point):** walk committed run artifacts
(§2.1) → collect real `coach_turn_N.json` bundles + the run's eventual outcome → assign
post-hoc `ground_truth_source`: `coach_correct` (approved, and no later layer found a defect),
`operator_caught` / `merge_review_caught` (retro/review names the miss), `live_gate_caught`
(none yet — enum slot reserved). Ugly-green harvesting is deliberate: approved bundles carrying
advisory_issues / demoted should_fix / infra-classified failures are the anti-over-reject rows.

**Seeded-control greens:** run the §2 pipeline with a no-op injection (empty patch) to produce
regenerated true-green bundles through the identical machinery — controls for any regeneration
artefact separating seeded rejects from harvested approves (else "was regenerated" itself
becomes the cue).

### 2.1 Known-green corpus inventory (code half verifies counts on disk)

| Source | What | Where |
|---|---|---|
| guardkit final-week completions | FEAT-E2CB (2/2), FEAT-10AC (5/5), FEAT-0E6D (1/1), SMP/APP waves | `guardkit/.guardkit/` run records, `docs/retro/evidence/` |
| study-tutor FEAT-SMP-001..003, APP-001 | 7-task features w/ coach_turn records | study-tutor `.guardkit/`, retros |
| forge FEAT-3ED2 (11/11, BDD 33/33) | largest single clean feature | forge run records |
| 29-run documented corpus (Mar–Jul) | earlier runs where records survive | per-repo `.guardkit/` + retros |

Fixture repos are **read-only** here (venue rule): checkouts into scratch worktrees only; no
commits to source repos from generation runs.

## 3. Injector recipes — the DC taxonomy mapping

> **Dated note (2026-07-07) — taxonomy documentation status.** The DC-01..DC-16 taxonomy is
> anchored in `factory-gap-analysis-2026-07-07.md` §2 (16 classes: 11 fixed-and-merged =
> DC-01/02/04/06/07/08/09/10/11/13/14; 4 filed-open = DC-05/12/15/16; 1 recurring-unfiled =
> DC-03). The **durable committed record names**: DC-03 composition-seam, DC-05
> environment-tamper, DC-08 BDD holes, DC-12 feature-plan defects, DC-14 direct-mode
> false-green, DC-15 cross-repo evidence architecture, DC-16 tracker corruption (names for
> DC-08/14 per the WS4 doc §5.3 + B11 kickoff). The remaining nine ids are *counted but not
> named* in any committed doc — their names lived in the session-internal fan-out autobuild
> digest. Per the no-invented-classes guardrail, **Phase 1 seeds only the named classes**;
> the nine unnamed ids enter when their names are graduated into a committed taxonomy doc
> (owed alongside WS3's seam work — flagged, not owned here). DC-15/DC-16 are process-layer
> classes with no bundle-visible signature — out of dataset scope, noted for completeness.

Recipes are derived from the real incidents (SPEC-qav-gold-negatives.md carries the four
worked examples); each recipe id is recorded per-row in `metadata.injection_recipe`.

| Recipe | DC | Injection (into a known-green task's tree) | Expected bundle signature |
|---|---|---|---|
| `R-DC03-callsite` | DC-03 | Re-apply a signature change to a class + its direct unit test, revert the production call sites (SMP-003 shape) | unit green; `wiring`/UNWIRED_PATH or runtime_parity red *iff* those analysers cover it — many bundles stay green-looking: that is the point |
| `R-DC03-producer` | DC-03 | Sever a consumer's producer: hardcode the feeding value to `None`/empty while the guard/consumer + its tests remain (10AC shape) | all green; `behavioural_oracle`/field absent or vacuous |
| `R-DC03-kwargs` | DC-03 | Change a callee's kwargs, wrap caller in broad try/except (soft-fail), keep permissive-fake pin tests (DD4F shape) | tests green; stub_scan/wiring may flag; narrative confident |
| `R-DC03-mockseam` | DC-03 | Convert an integration test's real seam to a mock of the service boundary (POC-006 shape) | tests green; `mocked_seam` findings present |
| `R-DC05-sysmod` | DC-05 | Plant a `sys.modules` stub of a required sibling package in an `__init__.py` (ABL-001 run-2 shape, 56-line `nats_core` stub) | tests green via stub; `stub_scan` may flag; independent vs claimed divergence |
| `R-DC05-skipguard` | DC-05 | Alter a skip-guard so dependency-missing tests silently skip instead of fail | green-with-skips; skip counts vs claims diverge |
| `R-DC08-undefstep` | DC-08 | Delete one step-definition variant a scenario needs (SMP-002 bare-phrasing shape) | `bdd_authoring_sweep.scenarios_undefined` > 0, or junit absent when oracle never re-ran |
| `R-DC08-pendmask` | DC-08 | Stub a responsible step as pending on a scenario this task must make executable | `bdd.scenarios_pending` masking a hole |
| `R-DC12-planvisible` | DC-12 | Use a plan_audit block recording a gate sequenced before its test exists / unverifiable AC (bundle-visible slice of the plan-defect class only) | plan_audit findings vs green gates |
| `R-DC14-narrative` | DC-14 | Player report over-claims files/results vs disk (FMDR-004 / ABL-001-run-3 shape) — honesty discrepancies present, narrative confident | `honesty.discrepancies` non-empty; gates partially null |
| `R-ABSENT-junit` | DC-08/DC-14 hybrid | Suppress the independent junit for the authoring task while self-report claims pass (SMP-002 turn-2 shape) | `bdd` null + narrative claims — absent-signal discipline row |

### 4. Weighting rationale (Rich-facing summary)

Weights (GOAL.md targets: DC-03 ~40% of rejects; DC-05/08/14 ~15% each; other documented ~15%):

1. **DC-03 gets the plurality because it is the only class with no structural cure and a
   recurring record**: 9 documented incidents, 3 in the final week, 4 of 8 completions shipped
   one past the Coach. It is *why the L5 seat exists*. Its four sub-shapes (call-site drift,
   runner-without-producer, soft-fail dead wiring, mocked seam) each get dedicated recipes so
   the plurality is spread across mechanisms, not one signature.
2. **DC-05 is filed-open with no landed cure** (ENVTAMPER01 design-first): until WS3's probes
   land, the judge is the only line that can suspect tampering. 15%.
3. **DC-08 and DC-14 are deterministically cured classes — seeded anyway, at 15% each,
   deliberately.** Two reasons: defense in depth (the SMP-002 approval happened *after* the BDD
   oracle machinery existed — cures have bypass paths like partial_honesty_abort), and the
   judge must read those bundle fields correctly to avoid false-blocking greens that merely
   *touch* BDD/honesty machinery. Training only on uncured classes would make cured-class
   fields dead weight in the input.
4. **Nothing above 50% for any single class** — the coach-v2 lesson generalized: any dominant
   class teaches a prior, not a judgment.

### 5. Balance plan (two-sided, pre-registered here)

- **Dataset composition:** approve ≈ reject at 50/50 ±10% (manifest `balance_report` enforces).
  Within approves: ≥45% ugly greens (GOAL.md category). Within rejects: the §4 weights ±5pp.
- **False-approval ceiling (must-catch side):** FEAT-EVAL-QAV (B12) pre-registers must-catch =
  the 4 gold negatives + a held-out seeded slice; the checkpoint bar is 100% on gold-negative
  must-catch rows and a seeded-slice catch rate WS2/Rich set at B12 filing (precedent: coach-v3
  bar). A false PASS is strictly worse than a false FAIL in this seat (WS4 §5.3).
- **False-block ceiling (over-reject side):** held-out honest greens (clean AND ugly) with an
  over-reject ceiling pre-registered at B12 filing — the dataset-factory Phase-4 two-sided gate
  precedent. Rollout gate 3 (scope §5: N consecutive zero-false-block features) consumes the
  same definition.
- **Why both ceilings bind the *dataset*, not just the eval:** coach-v2's 81/19 → 87.5%
  false-approval showed the imbalance does its damage at train time; the manifest refuses to
  finalize outside the composition bands above.

### 6. Hold-out discipline + contamination check (named validation step)

1. `split: eval_qav` is assigned **at row creation**, before any training manifest exists:
   the 4 gold negatives (always), plus a stratified slice (~15%, stratified by
   dc_class × generation_mode × verdict) frozen by seeded RNG recorded in the manifest.
2. Training manifest finalization runs `scripts/qav_contamination_check` (code half):
   asserts `train.row_id ∩ eval.row_id = ∅` **and** zero near-duplicate user messages across
   the split boundary (same source task + same recipe family ⇒ same side of the split —
   sibling-variant leakage is contamination even when hashes differ).
3. The check's output is embedded in the manifest (`contamination_check`); a manifest without
   a passing embedded check is invalid by contract (OUTPUT-CONTRACT §5).
4. B12 copies eval rows into fleet-evals via its own provisioning; the factory never publishes
   eval rows into `output/qa-verifier/train.jsonl` at any intermediate stage.

### 7. Agent-config (draft; code half wires it)

`agent-config.draft.yaml` (this dir) sketches the run config. Deltas vs the PO generative mode:
`generation.mode: seeded_defect` (new); `corpus:` block naming source-repo roots + recipe
weights; teacher model slot (rationale author) instead of a free Player; Coach gate =
schema + label-consistency + cue-audit (not content judgment). GB10 sequencing: bundle
regeneration is CPU-dominant (pytest substrate), teacher rationale is the only GPU stage —
schedule it like a normal factory run under the program-plan calendar; **never tonight**.

### 8. Phased sequence

| Phase | What | Gate |
|---|---|---|
| P0 (this session) | Spec committed (this dir) | B11 spec gate — Rich reads §4 |
| P1 (Opus code half) | Injector + harvest transform + contamination check + manifest writer; recipes `R-DC03-*` first | unit tests; 1 hand-verified row per recipe |
| P2 | Pilot: ~40 rows (interleaved recipes), Rich spot-checks ≥10 (B11 validation bar) | spot-check pass; cue audit clean |
| P3 | Bulk generation to GOAL targets; manifests finalized | balance bands met; contamination pass |
| P4 | Handover: manifest → WS4 (S8 scope doc); eval rows → B12 | B12 files FEAT-EVAL-QAV |

### 9. Risks

- **Regeneration environment fidelity** — bundles regenerated in scratch worktrees can differ
  from live-run bundles (the SMP-003 boot-latency masking shows environment changes evidence).
  Mitigation: seeded-control greens (§2) + per-repo venv pinning; residual risk noted honestly.
- **Cue leakage** in `seeded_bundle` rows — capped, audited, ablatable.
- **Nine unnamed DC ids** — coverage gap until the taxonomy doc lands (§3 note); Phase-1 scope
  is the named classes, which include every final-week escape class.
- **Bundle schema drift** during WS3/WS2 landings — `bundle_schema_sha` + additive-only mixing
  rule (OUTPUT-CONTRACT §2) contains it.
