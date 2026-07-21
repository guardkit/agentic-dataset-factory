# Receipt — GROWTH CYCLE 1: `--mode both` fresh-start over the coach-passed growth lanes (2026-07-21)

> **COMPLETE (2nd attempt) — 31m19s wall, 34 rows banked (25 train / 9 eval_qav), 34/34
> contract-valid, contamination PASS twice, zero evictions, timer never touched.** But the
> headline is the honest one: **this cycle grew the corpus 35 → 34 (net −1 row, −2.9%).** All
> three landed growth lanes (G1 feature-tracker reader · G2 reject-side respike / render-collapse
> · G3q seeded_bundle activation) are **provenance/honesty-gated to ZERO net corpus yield** — they
> bought precision and wiring, not volume. **FLOOR: NOT MET → NOT auto-GO-armed.** At 34 total /
> 25 train we are at ~3.4% of the `total ≥ 1000` floor, and the balance law is failing
> (approve_share 0.76). Per the stall-safe clause this is a **PLATEAU report + fresh decision
> card** for Rich: the measured ceiling of the current levers is ~34–35 rows.

Factory HEAD: `91d6bf6` (recorded in the manifest). No engine code touched (RUN operator).

---

## Floor verdict — the go/no-go card

| gate | required | measured | pass? |
|---|---|---|---|
| **total rows** | ≥ 1000 (≈ train ≥ 850) | **34** (train 25) | ✗ (3.4% of floor) |
| contamination | PASS | PASS (×2) | ✓ |
| ugly-green share of approves | ≥ 0.45 | 0.9474 | ✓ |
| balance: approve_share | 0.50 ± 0.10 | **0.76** | ✗ (ADVISORY FAIL, banked honestly) |

**VERDICT: NOT AUTO-GO-ARMED.** Below the count floor by ~29×, and the frozen balance law is
failing. The tune is **not** dispatched. Returned to the coordinator as a below-floor + plateau
result, not an armed one.

## Corpus size — before / after, by side

| | train | eval_qav | total |
|---|---|---|---|
| **before** (corpus-run `35e6dff`, unchanged baseline) | 26 (approve 20 / reject 6) | 9 (approve 2 / reject 7) | **35** |
| **after** (this cycle, `91d6bf6`) | 25 (approve 19 / reject 6) | 9 (approve 2 / reject 7) | **34** |
| **cycle-1 delta** | −1 (one approve) | 0 | **−1 (−2.9%)** |

Baseline preserved before the run: 35-row corpus copied to session scratchpad AND banked by the
driver's own fresh-start `*.bak` swap (train.jsonl.bak = 26 rows, sha `3bd82c548267`; eval.bak = 9,
sha `8e2e27d72e42` — the corpus-run shas exactly). Fresh-start is not resumable; the baseline is
safe as `*.bak`.

The −1 is a stochastic teacher/coach artefact, not a lane effect: `harvest_written=19` (one of the
20 consumable labels' rationale drew `coach_rejected` this run; `coach_rejected=2` total vs 0 last
run). No new rows were added by any growth lane.

## Full census — by side / split / mode / DC-class

**train (25):**

| verdict | mode | dc_class | n |
|---|---|---|---|
| approve | harvest | — | 12 |
| approve | seeded_code (controls) | — | 7 |
| reject | harvest | DC-03 | 3 |
| reject | seeded_code | DC-08 | 3 |

**eval_qav (9):**

| verdict | mode | dc_class | n |
|---|---|---|---|
| approve | harvest | — | 2 |
| reject | harvest | DC-03 | 2 |
| reject | gold_negative | DC-03 | 3 |
| reject | gold_negative | DC-08 | 1 |
| reject | seeded_code | DC-08 | 1 |

**Manifest counts (train file):** by_verdict approve 19 / reject 6 · by_dc_class DC-03=3, DC-08=3,
DC-05/12/14=0 · by_ground_truth_source coach_correct 12 / merge_review_caught 3 / seeded 10 ·
by_generation_mode harvest 15, seeded_code 10, seeded_bundle 0, gold_negative 0.

**Run tallies (DONE line):** `seeded_code=4 control=7 seeded_bundle=0 harvest=19 gold=4
harvest_skipped=4 harvest_bundle_not_found=0 teacher_refused=0 coach_rejected=2 cue_rejected=0
evidence_empty_rejected=0 schema_rejected=0 anchor_skipped=111 gold_source_skipped=0 deduped=66`.

Per-repo provenance (train+eval): harvest — forge 9, study_tutor 5, guardkit 2, api_test 1,
nats_core 1, jarvis 1; seeded_code — study_tutor 7, guardkit 4; gold_negative — study-tutor 2,
forge 1, guardkit 1. `deduped=66` = the known ×2 double-count (~33 real write-time collisions, the
same seeded-sibling classes as prior runs).

## Per-lane yield attribution — what G1 / G2 / G3q each bought THIS corpus

- **G1 — feature-tracker record-shape reader (`91d6bf6`): 0 new corpus rows.** Seeded INCLUDED held
  at **13 → 13** by the approved-sha honesty law; DISCOVERY line this run = **13 included / 772
  excluded** (up from 97 — the ~730 tracker turn-aways are now *precise recorded exclusions*, seen
  live in the log as `DISCOVERY EXCLUDE …/FEAT-VOICE-… — tracker evidence never seeds a
  seeded-source approve …`). **Bought: discovery precision + 2 new repos walked, not volume.** Its
  own receipt predicted exactly this.

- **G2 — reject-side respike + render-collapse root cause (`60325b2`/`9c212db`/`4921ab9`): 0 net new
  reject rows.** `anchor_skipped=111` — the DC-03/DC-05 recipe anchors that render-collapse to
  byte-identical bundles are skipped exactly as the render-collapse receipt diagnosed ("recipe class
  structurally unfit"). The seeded reject side therefore stayed at the **DC-08 recipes only** (3
  train + 1 eval = 4 `seeded_code` rejects); DC-03/DC-05/DC-12/DC-14 seeded = 0. study_tutor reject
  anchors were **deliberately not added** (would cannibalize the 7 approve controls). **Bought:
  honest anchor set + a root-caused, evidenced blocker — not volume.**

- **G3q — seeded_bundle activation (`c0d749e`): 0 rows.** `seeded_bundle_written=0`,
  `seeded_bundle_capped=0`. Every candidate was skipped `SEEDED_BUNDLE skip …/TASK-… — no
  record-resolved provenance (never a guessed sha)`. The lever is **wired and honest** but yields
  zero under the current provenance rule (the final-turn bundles it would mutate carry no
  record-resolved approved sha). **Bought: a proven-inert, provenance-safe augmentation path — not
  volume.**

**Net: the three growth lanes contributed ZERO rows to this corpus.** They are correctness /
precision / wiring lanes whose own honesty gates hold them at zero yield. Growth was "expected" for
cycle 1, but the levers that actually landed do not move volume — the honest measured result is a
plateau at the prior ceiling.

## Manifest verdict — honest

`domains/qa-verifier/manifests/qav-phase1-train.manifest.json` (factory_sha `91d6bf6`, dataset
`qav-phase1-train-v1`, private DF-008):

- `approve_share = 0.76` → **MANIFEST BALANCE ADVISORY FAIL** (outside 0.50±0.10) — logged loudly at
  20:23:27, rows banked, manifest written honestly.
- `ugly_green_share_of_approves = 0.9474` → PASSES the ≥0.45 floor.
- `contamination_check.status = "pass"` (intersection 0, sibling-variant 0, gold-source 0); the
  standalone `scripts/qav_contamination_check.py` re-ran clean: **VERDICT: PASS**.
- `visibility = "private (DF-008)"`.
- Validation: **34/34 rows `validate_row`-VALID**.

## The blocking finding — a stochastic teacher-output crash aborts the whole run (attempt 1)

The **first** `--mode both` launch (19:39:11) **crashed** ~11 min in at guardkit
`TASK-QAWE-004 / R-DC03-callsite` with an **uncaught** `json.decoder.JSONDecodeError: Extra data:
line 1 column 17`. Root cause, traced:

- `src/qav/contracts.py::parse_assistant_content` uses `_FENCE_RE = ```json\s*(.*?)\s*``` ` and takes
  the **first** ```json fence via `.search`. When the teacher (`gpt-oss-120b`, temp 0.4)
  stochastically emits a fenced `json` block **inside its `<think>` rationale**, the parser grabs
  *that* fence instead of the real verdict object and `json.loads` raises "Extra data".
- This fires inside `build_row → validate_row` on the **injector-fixed** row, so it is **uncaught**
  and **aborts the entire run** — losing seeded + harvest + manifest — rather than rejecting the one
  row. It is a latent robustness gap in the byte-frozen validator (`ed00704`), not a growth-lane
  regression: the prior `35e6dff` run simply drew clean teacher output on the same 13 tasks.

**Operator action taken:** per the RUNBOOK's interrupted-run remedy (no resume — re-run), the
35-row baseline was restored into `output/` from `*.bak` and `--mode both` re-launched at 19:52:09;
the second draw completed clean (0 tracebacks). **Not fixed here** — the fix touches `src/qav/**`
(frozen validators; the RUNBOOK's "do NOT edit" list), so it is escalated to the coordinator/owner,
not patched under the RUN-operator hat. Suggested minimal fix for their sign-off: anchor the fence
search to *after* `</think>` (or make `validate_row`'s parse failure a row-reject, not a raise). It
will recur, and a **larger** corpus (more teacher calls) makes it **more** likely — worth fixing
before the next cycle.

## Serving posture — the flock-guard held, timer NEVER touched

Keepalive timer was **ACTIVE** at start (the corpus-run pattern), so the ratified flock-guard was
used instead of stopping it: an exclusive `flock -x /var/lock/llama-swap-keepalive.lock` wrapped the
whole run. Journal proof for the run window: every fire (19:54, 19:59, 20:04, 20:10, 20:15, 20:20)
logged **"Another keep-alive run is in progress; exiting."** — no revive, no OOM exposure. Timer
left `active`, exactly as found. s2s / audio pair untouched.

- **Evictions: ZERO.** teacher `gpt-oss-120b` + coach `qav-coach` co-resident (the `qav`
  llama-swap set); `teacher_refused=0`, driver reported no 500s/retries.
- **Seeded: 45 regen legs** across the 13 record-complete tasks (guardkit ×6, study_tutor ×7),
  ~19–104 s/leg — byte-for-byte the corpus-run rate.
- **Harvest: 19 rows** at the warm co-resident rate.

## Times

| | |
|---|---|
| attempt 1 (crashed) | launched 19:39:11 → crashed ~19:50 at QAWE-004/R-DC03-callsite (parse abort) |
| **attempt 2 (completed)** | **launched 19:52:09 → DONE 20:23:28 · 31m19s wall** |
| log (completed run) | `run_logs/growth_cycle1_20260721-195209.log` |
| log (crashed run) | `run_logs/growth_cycle1_20260721-193911.log` |

## Venue — corpus repos untouched

HEADs identical to the corpus-run receipt: guardkit `b68c9e9d` · study-tutor `f843cb5` · forge
`686439c` · api_test `9066286` · nats-core `2c060b2` · jarvis `1fc7309`. Harvest read committed
bundles in place; seeded scratch worktrees cleaned per row.

## Artifacts + provenance

- `output/qa-verifier/train.jsonl` — 25 rows · sha256 `904a3341552f04e3e275dbdf71be03974ecc53e0acc68182849a891b4e22acf7`
- `output/qa-verifier/eval_qav.jsonl` — 9 rows
- `output/qa-verifier/rejected.jsonl` — 0 rows
- `domains/qa-verifier/manifests/qav-phase1-train.manifest.json` — factory_sha `91d6bf6`
- snapshot: `output_backup_qav-growth-cycle1_20260721-*/`
- Datasets private (DF-008). No push.

## What the coordinator needs to decide (the fresh plateau card)

The measured ceiling of the currently-landed levers is **~34–35 rows**. To move off it, the volume
levers — all engine-external, in priority order:

1. **More ratified curation batches** (the 79-bundle U4 pool in `curation/pack-2026-07-21.md` →
   `answers-2026-07-21.yaml`). Rich-curation-only by law. This is the **only** lever that adds
   harvest rows, and the largest available reservoir.
2. **Fix render-collapse** so DC-03/DC-05 recipes emit bundle-visible perturbations — unlocks ~26
   seeded reject legs into unique rows (and rebalances the 0.76 approve share downward).
3. **Give seeded_bundle a record-resolved-provenance path** so G3q stops skipping to 0.
4. **study_tutor anchor coverage** (0/11 recipes anchor) — the highest-yield seeded lever, currently
   blocked behind render-collapse.
5. **Fix the parse-abort crash** (above) before scaling teacher calls.

Without at least (1), the next cycle will replateau at ~35. Recommend a fresh GO/NO-GO / lever card
to Rich rather than an auto-cycle.
