# Receipt — GROWTH CYCLE 2: `--mode both` over the coach-passed levers (2026-07-21)

> **COMPLETE — 61m54s wall, 50 rows banked (41 train / 9 eval_qav), 50/50 contract-valid,
> contamination PASS (×2), ZERO evictions of the qav set, timer never touched.** This cycle
> **grew the corpus 35 → 50 (net +15 rows, +42.9%)** and — for the first time — **flipped the
> frozen balance law from FAIL → PASS** (approve_share 0.76 → 0.5854, inside 0.50±0.10). The
> reject-side levers finally moved volume: seeded_code rejects **0 → 10** (deep-regeneration fix +
> card #2), seeded_bundle **0 → 4** (provenance completion). **FLOOR (Option A, total ≥ 250):
> NOT MET → NOT auto-GO-armed** — 50 is 20% of the 250 floor. But the **<10% plateau clause is
> NOT triggered** (+42.9% ≫ 10%): this is real growth, not a replateau. The tune is **not**
> dispatched (coordinator's call; and the count floor is unmet regardless).

Factory HEAD: `0ceaa9e` (recorded in the manifest). No engine code touched (RUN operator).

---

## Floor verdict — the go/no-go card (Option A)

| gate | required | measured | pass? |
|---|---|---|---|
| **total rows** | ≥ 250 | **50** (train 41 / eval 9) | ✗ (20% of floor) |
| balance: approve_share | 0.50 ± 0.10 | **0.5854** | ✓ (flipped from 0.76 FAIL in cycle-1) |
| ugly-green share of approves | ≥ 0.45 | 0.9583 | ✓ |
| contamination | PASS | PASS (×2) | ✓ |

**VERDICT: NOT AUTO-GO-ARMED.** All three frozen laws now PASS, but the corpus is below the
count floor by 5×. Returned to the coordinator as a **below-floor, growing, laws-clean** result.
The tune is **not** started.

**Plateau clause (<10%): NOT triggered.** Growth this cycle = **+42.9%** (35 → 50). The
currently-landed levers are *not* plateaued — the reject-side fixes (deep-regeneration + seeded_bundle
provenance) that yielded zero in cycle-1 yielded **+14 reject rows** this cycle. Recommend
**continuing cycles / feeding the volume levers**, not a stall card.

## Corpus size — before / after, by side

| | train | eval_qav | total |
|---|---|---|---|
| **before** (baseline banked to `*.bak`) | 26 (approve 23 / reject 3) | 9 (approve 3 / reject 6) | **35** |
| **after** (this cycle, `0ceaa9e`) | 41 (approve 24 / reject 17) | 9 (approve 3 / reject 6) | **50** |
| **cycle-2 delta** | **+15** (reject +14, approve +1) | 0 (frozen holdout) | **+15 (+42.9%)** |

Overall approve_share 26/35 = 0.743 → 27/50 = 0.54. Manifest (train-only) approve_share 0.76 → **0.5854**.

**The `.bak` banks the 35-row baseline (noted):** the driver's fresh-start swap wrote
`train.jsonl.bak` = 26 rows sha `d810c01dba6c…` and `eval_qav.jsonl.bak` = 9 rows sha `96d98365445d…`
— byte-identical to the pre-run output (independently snapshotted to session scratchpad first).
Fresh-start is not resumable; the baseline is safe as `*.bak`.

## Full census — by side / split / mode / DC-class

**train (41) — verdict approve 24 / reject 17:**

| verdict | mode | dc_class | recipe | n |
|---|---|---|---|---|
| approve | harvest | — | — | 13 |
| approve | seeded_code | — | R-CONTROL-noop | 11 |
| reject | harvest | DC-03 | — | 3 |
| reject | seeded_code | DC-03 | R-DC03-mockseam | 3 |
| reject | seeded_code | DC-03 | R-DC03-producer | 3 |
| reject | seeded_code | DC-03 | R-DC03-callsite | 1 |
| reject | seeded_code | DC-05 | R-DC05-skipguard | 1 |
| reject | seeded_code | DC-05 | R-DC05-sysmod | 1 |
| reject | seeded_code | DC-08 | R-ABSENT-junit | 1 |
| reject | seeded_bundle | DC-14 | R-BUNDLE-DC14-honesty | 4 |

**eval_qav (9) — verdict approve 3 / reject 6 (frozen holdout, split membership unchanged):**

| verdict | mode | dc_class | n |
|---|---|---|---|
| approve | harvest | — | 2 |
| approve | seeded_code | — | 1 |
| reject | harvest | DC-03 | 2 |
| reject | gold_negative | DC-03 | 3 |
| reject | gold_negative | DC-08 | 1 |

**Manifest counts (train file):** by_verdict approve 24 / reject 17 · by_dc_class DC-03=10, DC-05=2,
DC-08=1, DC-12=0, DC-14=4 · by_ground_truth_source coach_correct 13 / merge_review_caught 3 /
seeded 25 · by_generation_mode harvest 16, seeded_code 21, seeded_bundle 4, gold_negative 0.

**Run tallies (DONE line):** `seeded_code=10 control=12 seeded_bundle=4 seeded_bundle_capped=0
seeded_bundle_no_provenance=62 harvest=20 gold=4 harvest_skipped=4 harvest_bundle_not_found=0
teacher_refused=0 coach_rejected=0 cue_rejected=1 evidence_empty_rejected=0
evidence_invariant_rejected=20 train=41 eval_qav=9 manifest_finalized=True balance_ok=True
approve_share=0.5854`. (`anchor_skipped=111` unchanged; `deduped=6` — the ×2 write-time
double-count → ~3 real collisions, down from cycle-1's 66.)

**Per-recipe hits (seeded reject rows that survived, by repo):** guardkit — R-DC03-mockseam 3,
R-DC03-producer 3, R-DC03-callsite 1, R-DC05-skipguard 1, R-DC05-sysmod 1, R-ABSENT-junit(DC-08) 1
(= 10); seeded_bundle R-BUNDLE-DC14-honesty — forge 2, nats_core 1, study_tutor 1 (= 4).

**Harvest rows (20, train+eval):** forge approve 5 / reject 5, study_tutor approve 5, guardkit
approve 2, api_test approve 1, jarvis approve 1, nats_core approve 1. 4 harvest_skipped (queued
dispositions: guardkit QAWE-002/004, study-tutor PO02-001/TASK-PRV-001), 0 bundle_not_found.

**Gold negatives (4, eval):** study-tutor DC-08, study-tutor DC-03, guardkit DC-03, forge DC-03.

## `evidence_invariant` refusals — the render-collapse guard (honest)

`evidence_invariant_rejected = 20`, **all guardkit**, all byte-identical to their no-op control
bundle (5× R-ABSENT-, 5× R-DC03-, 10× R-DC05-). These are the recipe legs whose planted defect never
surfaces in the rendered evidence on guardkit's older QAWE-001..004 tasks — refused exactly as the
EVIDENCE-DIVERGENCE guard + render-collapse root-cause receipt require ("no reject label may ride
evidence the defect never reached"). The deep-regeneration 4-layer fix (`0ceaa9e`) DID surface
divergent bundles on the divergent tasks (that is where the 10 accepted guardkit seeded rejects came
from) — but it does **not** cure the structurally-collapsing guardkit recipe/task combinations, which
remain honestly zero-yield. Poison guard: `cue_rejected=1`, `evidence_empty_rejected=0`,
`teacher_refused=0`, `coach_rejected=0`.

## Per-lane yield attribution — what each landed lever bought THIS corpus

- **Deep-regeneration 4-layer fix (`0ceaa9e`) + card #2 curation (`6e19492`): +10 reject rows.**
  seeded_code rejects **0 → 10** (all guardkit; DC-03 ×7, DC-05 ×2, DC-08 ×1). Card #2's new
  divergent task (e.g. `TASK-BDDW-001`) plus the 4-layer render fix let real perturbations reach the
  evidence, so the reject label rides genuine defect signal. The 20 byte-identical legs still refuse
  honestly. **Bought: the reject side finally has volume — this is the largest single lever gain.**

- **seeded_bundle PROVENANCE COMPLETION (`65066b5`): +4 rows.** `seeded_bundle_written = 4`
  (R-BUNDLE-DC14-honesty; forge 2, nats_core 1, study_tutor 1) — up from **0** in cycle-1. Wiring the
  input from the union committed-provenance pool gave G3q a record-resolved path. `seeded_bundle_no_provenance=62`
  candidates still skipped (never a guessed sha). **Bought: the seeded_bundle lever is no longer inert.**

- **Harvest: 20 rows (+1 over cycle-1's 19).** Steady at the ratified-outcomes ceiling; 4 skipped for
  queued dispositions. **Bought: no new harvest volume — the union outcomes pool is exhausted at ~20
  until more curation batches ratify.**

- **Net: +15 rows AND the balance-law flip.** The +14 reject rows (10 seeded_code + 4 seeded_bundle)
  drove approve_share 0.76 → 0.5854 — the frozen balance law is now a genuine PASS, not an advisory
  bank.

## Manifest verdict — honest

`domains/qa-verifier/manifests/qav-phase1-train.manifest.json` (factory_sha `0ceaa9e`, dataset
`qav-phase1-train-v1`, private DF-008):

- `approve_share = 0.5854` → **BALANCE PASS** (inside 0.50±0.10; `balance_ok=true`,
  `manifest_balance_violations=[]`). First cycle to clear this law.
- `ugly_green_share_of_approves = 0.9583` → PASSES the ≥0.45 floor.
- `contamination_check.status = "pass"` (intersection 0, sibling-variant 0, gold-source 0); the
  standalone `scripts/qav_contamination_check.py` re-ran clean: **VERDICT: PASS**.
- `visibility = "private (DF-008)"`.
- Validation: **50/50 rows `validate_row`-VALID**.
- **sha note (benign):** the manifest's recorded train sha256 `176136c0821f8c…` is
  `sha256(_jsonl_bytes(train_rows))` — the canonical *re-serialization* of the in-memory rows, which
  matches exactly (verified). The raw file bytes hash differently (`sha256sum train.jsonl` =
  `2d3a7bda4925…`) purely from serialization formatting; row content is intact.

## Frozen holdout — membership unchanged, content regenerated (expected)

Fresh-start regenerates rationales, so `eval_qav.jsonl` is byte-different from `*.bak`. But the
holdout **membership** by (repo, task, mode, recipe) is **identical** to baseline (the seed-frozen
split held); 8/9 row_ids stable, 1 row_id shifted only because its `<think>` regenerated (row_id is a
content hash), 4/9 rows carry regenerated content. No holdout leakage — contamination PASS confirms.

## Serving posture — ZERO evictions of the qav set; timer NEVER touched

- **Evictions of the qav working set: ZERO.** Teacher `gpt-oss-120b` + coach `qav-coach` co-resident
  (the `qav` llama-swap set). `teacher_refused=0`, `coach_rejected=0`, **no HTTP 500s** in the run
  (the 7 log lines matching "timeout/500/refused" are all benign — 4 DISCOVERY-EXCLUDE feature-tracker
  `final_decision` strings + the divergence-guard summary). Steady progress throughout 62 min.
- **Keepalive FINDING (flag for the coordinator):** the keepalive timer read `inactive` at run start
  (lock free, no keepalive process), so per the ratified rule the flock-guard was **not** applied. Yet
  the keepalive script **fired 12× during the run window** (via some trigger other than the `.timer`,
  which stayed `inactive` before and after). Every fire revived **only** `embed gemma4-tutor
  tutor-coach` — it **never touched** `gpt-oss-120b`/`qav-coach`, and **no OOM occurred** (the qav
  co-resident set design absorbed it). The risk in `agent-config.yaml` (gpt-oss evicts the always-on
  fleet → keepalive revives on top → OOM) did **not** materialize this run, but the timer's `inactive`
  reading is **not** a reliable "keepalive is dormant" signal. **Recommendation: apply the exclusive
  flock-guard unconditionally on future runs, regardless of the timer's active-state.** The timer was
  **never touched** by this operator (honored) and is left `inactive`.

## Times

| | |
|---|---|
| launch attempt 1 | 22:04:46 — failed instantly (`env: 'python': No such file or directory`); no work done, no state touched |
| **run (completed)** | **launched 22:05:07 → DONE 23:07:01 · 61m54s wall** (relaunched with `.venv/bin/python`, `PYTHONPATH=src`) |
| log | `run_logs/growth_cycle2_20260721-220446.log` |

Pace note: guardkit seeded legs are slow (~3–7 min each — they re-run the real `test_wiring_seam_real_factory.py`
integration suite per recipe); study_tutor legs (`test_command=None`) run ~1 min; the rationale/harvest
teacher+coach phase ran ~14 min silent (per-row HTTP calls to :9000, not logged per row).

## Venue — corpus repos untouched

Harvest read committed bundles in place; seeded scratch worktrees under
`output/qa-verifier/_scratch/<repo>/<task>/<recipe>` cleaned per row. No corpus repo written.

## Artifacts + provenance

- `output/qa-verifier/train.jsonl` — 41 rows · file sha256 `2d3a7bda4925d132f34eba8aa82dd58e65535e7b9b5bbc1cde623c9bf7f941fe` · manifest (re-serialized) sha256 `176136c0821f8c2356eea4ceb1b751fbcb359f32d791ea6e48d57916b97ce743`
- `output/qa-verifier/eval_qav.jsonl` — 9 rows · sha256 `3b30fd48b45690346bc73ba17eebb8d64155ee5cbbf5dff11daf3413c67233c3`
- `output/qa-verifier/rejected.jsonl` — 21 rows (refused candidates, not corpus)
- `domains/qa-verifier/manifests/qav-phase1-train.manifest.json` — factory_sha `0ceaa9e`
- baseline banked: `output/qa-verifier/train.jsonl.bak` (26, `d810c01dba6c…`) · `eval_qav.jsonl.bak` (9, `96d98365445d…`)
- log: `run_logs/growth_cycle2_20260721-220446.log`
- Datasets private (DF-008). No push.

## What the coordinator needs to decide

The corpus is **growing and laws-clean** but at **50/250** (20% of the Option-A floor). The levers
that moved this cycle are the reject-side fixes; the approve/harvest side is at its outcomes-pool
ceiling (~20). To reach 250:

1. **More ratified curation batches** — still the only lever that adds harvest volume; the union
   outcomes pool is exhausted at ~20 harvest rows until a new batch ratifies.
2. **Cure guardkit render-collapse** — 20 guardkit reject legs (R-ABSENT/R-DC03/R-DC05) still refuse
   byte-identical; curing them unlocks that reject volume (the deep-regen fix cured the *divergent*
   tasks, not the structurally-collapsing recipe/task combos).
3. **Broaden seeded_bundle provenance** — 62 candidates still skipped no-provenance; each record-resolved
   sha added is a new DC-14 reject row.
4. **Apply the flock-guard unconditionally** (serving finding above) before the next, longer run.

Recommend a fresh lever decision to Rich (more curation batches are the largest reservoir), then
re-cycle — the plateau is broken, but 250 needs the harvest/curation reservoir opened.
