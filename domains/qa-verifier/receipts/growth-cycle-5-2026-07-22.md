# RECEIPT — Growth cycle 5 (2026-07-22; `--mode both`, factory_sha `3ffb481`)

The first cycle to run **on top of the coach-passed scopes** — the per-recipe `test_command`
override (`3ffb481`: guardkit `R-DC05-skipguard` / `R-ABSENT-junit` pinned to their own mutated
files, each with a scope-matched control). Cycle 4 named guardkit's 24 refusals as "the single
largest recoverable block"; this cycle those scopes **halved the guard refusals (24 → 12)** and
surfaced the previously-refused classes as real rows — **but the NET corpus gain was small (+6)**
because dedup absorbed most of the new candidates. The growth curve has bent hard toward a plateau.

## Corpus before → after (by side)

| Side | Cycle 4 | Cycle 5 | Δ |
|---|---|---|---|
| train | 77 | **82** | +5 |
| eval_qav | 17 | **18** | +1 |
| **TOTAL** | **94** | **100** | **+6 (+6.4%)** |

`*.bak` banks the prior **94-row** corpus (verified: `train.jsonl.bak` 77 · `eval_qav.jsonl.bak` 17
· `rejected.jsonl.bak` 25). Full snapshot: `output_backup_qav-growth-cycle5_<ts>` (see Ops).

## Per-mode attribution

**train (82)** by `generation_mode`: seeded_code **54** (was 48, +6) · harvest 22 (0) ·
seeded_bundle 6 (was 7, −1). **eval_qav (18)**: seeded_code 7 · harvest 7 · gold_negative 4
(holdout intact). Pipeline writes this run (DONE line): seeded_code=34 · control=27 ·
seeded_bundle=6 · harvest=29 · gold=4; **deduped=14** · anchor_skipped=256 · teacher_refused=0 ·
coach_rejected=2 · cue_rejected=1.

The entire train delta is the **seeded_code lane (+6)** — the coach-passed guardkit scopes plus the
study_tutor DC-03 anchor. Harvest is flat (same 29 consumables, 4 honestly skipped). seeded_bundle
is pool-gated (`seeded_bundle_no_provenance=52`, unchanged cap).

## Guard-refusal delta (vs cycle 4's 24) — HALVED

**12 `evidence_invariant_injection` refusals — down 12 from 24.** The coach-passed guardkit
per-recipe scopes did exactly what cycle 4 projected: `R-DC05-skipguard` and `R-ABSENT-junit` now
regenerate a bundle that DIVERGES from the no-op control, so their planted defects surface as real
rows instead of being honestly refused. The residual 12 are the guardkit **source-package**
mutations (`R-DC03-producer`, `R-DC03-callsite`, `R-DC05-sysmod`) whose `import guardkit.*` resolves
to the editable install, not the mutated worktree copy — byte-identical to control, genuinely
**not** recoverable by a test scope (the honest structural cap, documented in `agent-config.yaml`).

Full `rejected.jsonl` (15, was 25): `evidence_invariant_injection` 12 · `coach_rejected` 2 ·
`cue_leakage` 1.

## Manifest verdict — HONEST, all laws PASS

- **contamination_check.status = `pass`** — row_id intersection 0, sibling-variant violations 0,
  gold-negative source-task violations 0.
- **balance PERFECT.** `approve_share` **0.5325 (cycle 4) → 0.5000 (dead-centre)**, inside 0.50±0.10;
  `ugly_green_share_of_approves` 0.9512 (≥0.45). train `by_verdict`: **approve 41 / reject 41** (was
  41/36) — the +5 seeded rows were all **rejects**, pulling the share to exactly 0.5.
- `by_dc_class`: **DC-05 0 → 3** and **DC-08 6 → 9** are the coach-passed-scope wins; DC-03 23 (steady)
  · DC-14 6 · DC-12 0. `by_ground_truth_source`: seeded 55 → **60** · coach_correct 15 ·
  merge_review_caught 4 · operator_caught 2 · live_gate_caught 1.
- visibility `private (DF-008)`; factory_sha `3ffb481`; bundle_schema_sha `41a0ebe457`;
  train sha256 `8fcdc050ed33a21ea467ba6f758a36479a73d42b4b908fa2b7111f83b0ff8bd2`.
- **Self-verify (run this cycle): 100/100 rows re-validate against OUTPUT-CONTRACT (0 failures);
  standalone contamination gate VERDICT: PASS.**

## FLOOR CHECK (Option A: total ≥ 250 AND all laws passing)

**NOT ARMED — 100 < 250.** All laws pass (contamination, balance, contract), but the count floor is
not met. **The tune does NOT start.**

## Plateau verdict — INFLECTING TOWARD PLATEAU (the constraint has shifted)

Growth is real but **sharply decelerating**: **+52% (c3) → +23.7% (c4) → +6.4% (c5)**. The lever
cycle 4 named as the biggest recoverable block — guardkit's refusals — was largely spent this cycle
(24 → 12, surfacing DC-05 0→3 and DC-08 +3), yet the corpus moved only +6. The reason is
**`deduped=14`**: the study_tutor `R-DC03-callsite` anchor, applied across many PRV/VOX tasks,
produces near-identical regenerated bundles (one mutation shape × many tasks) that the dedup
collapses. **The binding constraint has shifted from refusal-recovery to anchor DIVERSITY.**

Quantified remaining ceiling to 250 (need +150), highest-yield first:

1. **`deduped=14` — anchor saturation (the new #1).** study_tutor/jarvis grow by having ONE
   distinct anchor spread over many tasks; those collapse under dedup. The lever is now **multiple
   DISTINCT anchors per corpus repo** (different DC-classes/mutated files per task — the `8ff7eb6`
   per-repo variant mechanism replicated across DC-classes), each SPIKE-validated. More tasks on the
   same anchor no longer pay.
2. **`evidence_invariant` 12 refusals — mostly a genuine cap now.** The residual are guardkit
   source-package mutations shadowed by the editable install; a test scope cannot surface them.
   Only broader/different **anchor targets** (files that live in the worktree, not the installed
   package) would recover any of these.
3. **`anchor_skipped=256` (unchanged)** — most task×recipe cells still unseeded; each new distinct
   per-repo anchor variant converts a slice.
4. **seeded_bundle `no_provenance=52` cap** — grows only with future consumable ratifications.

The refusal-recovery well is drying; the path to 250 is **anchor breadth**, not more scope pins.

## Ops

- `--mode both`, launched detached (nohup, PID 1180229). Wall **16:34:33 → 17:53:47 = 1h19m14s**
  (faster than cycle 4's 1h29m25s — 12 fewer refusals and co-residency avoided most cold loads).
- Discovery: same corpus set (`api_test, fleet_memory, forge, guardkit, jarvis, nats_core,
  specialist_agent, study_tutor`); approved-sha honesty law unchanged (tracker-only repos excluded
  loudly, zero new seeded source tasks).
- **Serving finding — qav pair held CO-RESIDENT; NO mutual thrash (the cycle-4 → cycle-5
  difference).** A 20 s resident-model sampler over the whole run: **212 of 217 samples (97.7%)**
  had **both** `gpt-oss-120b` (teacher, :5810) and `coach-ft-v3` (the GGUF behind the `qav-coach`
  alias, :5816) resident together — the co-resident `qav` llama-swap set working as the config
  intends. **No competitive eviction occurred: the coach never evicted the teacher and the teacher
  never evicted the coach** (that was cycle 4's per-leg mutual-eviction regime). The **only**
  eviction was a single **transient idle-TTL unload of gpt-oss-120b at 16:59:33**, cold-**reloaded
  at 17:01:13** (~1m40s) on the next teacher call — it fell out during the extended guardkit
  `R-DC05-skipguard` / `TASK-BDDW-001` regeneration gap (minutes of CPU-bound pytest with no teacher
  call, so gpt-oss idled past its TTL). This is a new, minor artefact of the coach-passed guardkit
  scopes making some legs long enough to idle the teacher out — one cold reload across the whole run,
  not per-row thrash. If guardkit legs lengthen further, a longer teacher idle-TTL (or a keep-warm
  ping during CPU-bound legs) removes even this.
- **Keepalive timer NEVER touched** (flock-guard unconditional posture — `active` before, during,
  and after). No OOM. Services healthy throughout.
- Self-verify + standalone contamination gate run post-finish; both green.
