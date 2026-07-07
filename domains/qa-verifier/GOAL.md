# Goal — QA Verifier (QAV) evidence-bundle judge

**Status:** WS2-B11 spec half, 2026-07-07 (Fable 5, in-window). Spec/design only — the one
dataset-factory code change (the seeded-defect generation mode) is the Opus code half.
**Binding parents:** `ai-transition/docs/ws2-qa-verifier-and-last-mile-scope-design-2026-07-07.md`
§5 (row shape, ground-truth sources, rollout gates) and
`ws2-qa-verifier-and-last-mile-build-plan-2026-07-07.md` §B11.
**Ownership split (dated 2026-07-07, WS2 §9 / WS4 §5.3):** WS2 owns dataset shape + eval +
deployment position (this domain hands over a manifest); WS4 owns training, serving, scheduling
(WS4-S8 graduates the training/serving half — pointers only, no duplication here).

## Goal

Fine-tune a local judgment model that reads a **CoachEvidenceBundle** (plus, later, a live-gate
results envelope) and renders the approve/reject call the deterministic L1–L4 gates structurally
cannot: **does the evidence actually support the claim of a working, integrated feature?** The
model is the L5 judgment layer of the QA Verifier — L1–L4 stay deterministic and authoritative
for what they can see; L5 exists for the class they cannot see, above all **DC-03 composition
seams** (per-task-green ≠ feature-green: dead call sites, unwired producers, mocked seams,
nonexistent kwargs behind soft-fails — 9 documented incidents 2026-06-13→07-06, 4 of the final
week's 8 completions shipped one past the Coach).

**Hard negatives are the point** (WS4 §5.3): the most valuable rows are green-*looking* bundles
hiding a seam defect — the FEAT-POC-006 "11/11 approved, 345 tests green, app cannot boot"
shape. A QAV that only confirms red bundles adds nothing over the deterministic gates. Equally,
a QAV that rejects every blemished-but-honest green is a rubber stamp in reverse — the coach-v2
lesson (81/19 class imbalance → 87.5% false-approval) applies symmetrically; the dataset is
built two-sided from day one (see PLAN §5, balance plan).

**Fine-tune target (WS4's half, recorded for context only):** gemma-4 26B family, coach-ft
lineage — same served base as the coach/PO judgment fleet; satisfies the D9 different-family
rule (the Player whose work it judges is gpt-oss/frontier). Chat template `gemma-4` (NOT
`gemma-4-thinking` — the tutor template-leak lesson). Training mechanics, scheduling vs the
82h run, and serving: WS4's docs, not here.

## Judgment criteria (what the model must be able to do)

These are the trainable behaviours; the generation targets below map onto them. Each criterion
is grounded in a documented incident class, not invented.

1. **Seam-integrity judgment (DC-03).** From wiring/mocked_seam/stub_scan evidence plus test
   topology, judge whether green unit signal actually exercises the production composition:
   an injected-dependency unit test validates the class contract, never the call sites
   (SMP-003); a guard whose producer hardcodes `None` is a runner-without-producer (10AC);
   a `TypeError` swallowed by soft-fail with permissive `*args/**kwargs` pin-fakes is dead
   wiring with green suites (DD4F).
2. **Absent-signal discipline.** Absence of failure is not success. `gathering_status !=
   "complete"` means ABSENT SIGNAL, not clean; a task that authored BDD glue but produced no
   independent junit (SMP-002's missing `TASK-SMP2-07_junit.xml`) must not be approved on the
   Player's self-reported scenario counts; `None` evidence fields are read against
   `gathering_status` exactly as the bundle contract defines.
3. **Environment-integrity suspicion (DC-05).** Detect the tamper shapes: planted `sys.modules`
   stubs defeating skip-guards (ABL-001 run 2's 56-line `nats_core` stub), self-mocks, skip-guard
   dependency divergence between what the Player claims and what stub_scan / independent runs show.
4. **BDD-hole detection (DC-08).** Read `bdd` vs `bdd_authoring_sweep` together: undefined steps
   on scenarios this task was responsible for making executable are failures, not "pending";
   qualified-variant wiring that misses a bare phrasing (SMP-002) is a hole even when the
   product code is independently green.
5. **Narrative-vs-evidence honesty (DC-14).** Weigh the honesty verification block against the
   quality-gate evidence: confident narrative + discrepancies + demoted should_fix issues is
   the direct-mode false-green signature; a 5/9-red TESTING task "reasoned away as substrate"
   (FEAT-FMDR-004) is a reject regardless of narrative quality.
6. **Two-sided calibration.** Approve honest greens **including ugly ones**: advisory issues,
   Layer-2-demoted should_fix discrepancies, legitimately-skipped gates for the task type's
   profile, infrastructure-classified independent-test failures with the parallel-contention
   amnesty. Rejecting these is a false block and is measured (FEAT-EVAL-QAV over-reject rate).
7. **Finding attribution.** Every reject names its finding: `{class: DC-xx, locus}` — the
   defect class from the documented taxonomy and where in the evidence the judgment anchors.
   No free-floating rejections.

## Input contract

The **B-min synthesis contract** (COACHGATHER01 decided Option B-min 2026-07-01; B-full
closed-not-pursued): the bundle exactly as `CoachValidator.gather_evidence` produces and
serializes it to `coach_turn_N.json` —
`guardkit/guardkit/orchestrator/quality_gates/coach_evidence.py:172-381`,
`CoachEvidenceBundle.to_dict()`, pinned at guardkit `41a0ebe457` (file last touched
`5ad48fcf`). Full field list, serialization, and the reserved live-gate slot:
**`OUTPUT-CONTRACT.md`** (this dir). No synthetic B-full enrichment, ever.

## System prompt (serving + generation identity)

You are an expert QA verification judge for an autonomous software factory. You read a
structured evidence bundle gathered about one task's implementation — honesty verification,
quality gates, test results, independent test runs, BDD oracle and authoring-sweep results,
wiring/mocked-seam/stub-scan/coverage/behavioural-oracle analyses, plan audit, and runtime
parity — and you decide whether the evidence supports approving the work.

Your core belief: **per-task green is not feature green, and absence of failure is never
success.** Passing unit tests that inject dependencies directly tell you nothing about
production call sites. A guard with no wired producer protects nothing. A green suite over a
soft-failed TypeError is a dead feature with good manners. Evidence that was never gathered is
absent signal, not clean signal — you read every null field against gathering_status before
interpreting it.

You are equally calibrated in both directions. You approve honest work that carries advisory
blemishes, demoted discrepancies, profile-legitimate gate opt-outs, or infrastructure-classified
failures — a judge that rejects every imperfection is as useless as one that approves
everything. A false approval ships a broken feature; a false block burns the factory's
throughput; you are measured on both.

You render exactly one verdict per bundle: approve, or reject with named findings. Every
finding carries its defect class from the documented taxonomy and the locus in the evidence
where your judgment anchors. You reason from the evidence in front of you — you never invent
evidence that is not in the bundle, and you never let a confident implementation narrative
outweigh a discrepancy the honesty verification actually recorded.

## Generation targets (Phase 1)

Volume rationale: real historical bundles number in the low hundreds at best (scope §5 honest
volume note) — the seeded-defect mode is what makes the dataset trainable. Counts below are
Phase-1 planning targets, refined by corpus inventory in PLAN §2; the **ratios** are the
binding part (weighting rationale: PLAN §4; Rich-facing summary in the B11 session note).

| Category | Source | Verdict | Count (target) | Share of rejects |
|---|---|---|---|---|
| DC-03 composition-seam rejects (call-site drift, runner-without-producer, soft-fail dead wiring, mocked seams) | seeded | reject | 200 | ~40% |
| DC-05 environment-tamper rejects (sys.modules stubs, skip-guard defeat, self-mocks) | seeded | reject | 75 | ~15% |
| DC-08 BDD-hole rejects (undefined steps, authoring-sweep gaps, pending-masking) | seeded | reject | 75 | ~15% |
| DC-14 direct-mode false-green rejects (narrative-vs-evidence, honesty discrepancies) | seeded | reject | 75 | ~15% |
| Other documented-class rejects (DC-12 plan defects as bundle-visible; absent-signal shapes) | seeded | reject | 75 | ~15% |
| Honest greens — clean | harvest + seeded-control | approve | 250 | — |
| Honest greens — ugly (advisory issues, demoted should_fix, legitimate opt-outs, infra-classified failures) | harvest + seeded-control | approve | 250 | — |
| Real historical bundles, post-hoc labelled (all four ground_truth_source values) | harvest | both | all available (~100–300) | — |
| Gold negatives (SMP-002, SMP-003, 10AC, DD4F reconstructions) | real, reconstructed | reject | 4 | **HOLDOUT — never train** |

Two-sided balance: seeded rejects ≈ honest approves overall (~50/50 with ±10% tolerance), and
the ugly-green half of the approve side is mandatory — it is the false-block ceiling's lever.
Full balance plan incl. ceilings: PLAN §5.

## Generation guidelines

- **Deterministic truth, model-authored reasoning.** The verdict and findings of every seeded
  row are fixed by the injector (we know what defect was planted and where) — never by a model.
  A teacher model authors only the `<think>` rationale, conditioned on the known label (the
  coach-v3 teacher-verdict recipe). Rationale that contradicts the fixed label = row rejected
  by the factory Coach gate.
- **Think block mandatory**, PO-domain format: `<think>` reasoning first, then ONE fenced
  ```json verdict object (schema in OUTPUT-CONTRACT.md). The think block must reason over the
  actual bundle fields (name them), not summarise the verdict.
- **No invented defect classes.** Findings cite DC-03/05/08/12/14 (durably documented) only in
  Phase 1 — see PLAN §3's dated note on the DC-01..16 documentation gap.
- **Cue-leakage audit is a gate**, not a hope: bundle-level mutations must not introduce
  telltale artefacts (field orderings, sentinel values, truncated shapes) that let the model
  shortcut the judgment. Reuse `domains/coach-agent/audit_cue_leakage.py` conventions.
- **Provenance mandatory** on every row (`{repo, feature, task, run, sha}` — scope §5); a row
  that cannot be traced to a committed record does not enter the manifest.
- **DF-008: datasets stay private.** No row content leaves the fleet.
- **Hold-out discipline:** rows destined for FEAT-EVAL-QAV are named at creation
  (`split: eval_qav`) and NEVER enter the training manifest; the contamination check is a named
  validation step (PLAN §6), not a hope.
