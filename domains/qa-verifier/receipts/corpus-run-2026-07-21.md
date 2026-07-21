# Receipt — THE CORPUS RUN: `--mode both` over the ratified 20-label outcomes (2026-07-21)

> **COMPLETE — 30m37s wall, 35 rows banked (26 train / 9 eval_qav), 35/35 contract-valid,
> contamination PASS twice (embedded + standalone), ZERO evictions, zero coach/teacher
> failures.** The headline: **ALL 20 ratified consumable labels were CONSUMED —
> `harvest_written=20`, `harvest_bundle_not_found=0`.** Every one of Rich's 18 batch-ratified
> labels (plus the 2 original A1 approves) landed as a banked harvest row; not one miss. The
> corpus now carries REAL both-sided data at 2.3× the seeded sweep's volume: real approves
> across six repos (api_test / nats_core / study_tutor / forge / jarvis / guardkit) and the
> first REAL train-side rejects (3 MP-R merge_review_caught escapes).

---

## The merge that fed it (STEP 1, commit `35e6dff`)

- Rich ratified the batch verbatim 2026-07-21 ("approve the batch", zero strikes, against
  `curation/batch-review-card-2026-07-21.md`). All 18 labels from
  `curation/derived-outcomes-2026-07-21.yaml` folded into
  **`domains/qa-verifier/harvest-outcomes.yaml`** — the file the config's
  `generation.harvest_outcomes` key actually reads (NOT
  `outcomes/harvest-outcomes-2026-07-21.yaml`, which is the S2 record file in a different,
  non-loader schema; it stays untouched as the dated record). Each entry:
  `disposition: consumable`, stamped
  `ratified: "Rich 2026-07-21 'approve the batch' (batch-review-card-2026-07-21.md)"`,
  provenance (record_path / sha / rule / note) verbatim. Data only — no engine code touched.
- **THE REPO-KEY LAW held:** entries use the corpus key spellings (`study_tutor`,
  `nats_core`, `api_test`, `jarvis`, `forge`). `agent-config.yaml` gained the three new
  corpus roots + interpreter insurance entries (all venvs verified). None of the three new
  repos carries a `.guardkit/archive/*/merge_summary.json`, so they add HARVEST discovery
  only — the run confirmed: seeded discovery stayed exactly 13 included (97 excluded, the
  +26 all spec-only loud exclusions from the new roots).
- **Preset `split:` fields DROPPED** from the derived entries — split assignment belongs to
  the engine's own law (`assign_split`, seed `qav-phase1`, holdout 0.15) at row creation.
  Consequence, recorded honestly: 3 of the 5 MP-R rejects (MP-005/006/008) landed **train**;
  MP-009/MP-004B landed eval_qav. The derived yaml's blanket eval-preset intent is
  superseded by the ratified split-law ruling; the train side gains its first REAL rejects.
- Pre-run sanity: `load_harvest_outcomes` → **CONSUMABLE = 20** (2 original A1 + 18
  ratified), 4 queued skipped loudly, zero gold-source clashes; census-safe discovery found
  **70 final-turn bundles** across the six roots and **all 20 keys joined** — every winner
  byte-matched the derived yaml's `bundle_path` (turn included).

## Preflight + the keepalive flock-guard (timer never touched)

| check | found |
|---|---|
| `:9000 /v1/models` | both `gpt-oss-120b` and `qav-coach` present |
| keepalive timer | **ACTIVE** → flock-guard suppression engaged (the seeded-sweep receipt's method) |
| flock | exclusive lock on `/var/lock/llama-swap-keepalive.lock` HELD 17:11:08 → released post-run ~17:44 |
| journal proof | every fire in the window (17:15, 17:20, 17:25:45, 17:30:57, 17:36:00, 17:41:04) logged `"Another keep-alive run is in progress; exiting."` — no revive, no OOM exposure; timer left `active` exactly as found |
| s2s | not touched; audio pair (parakeet + qwen3-tts) resident throughout |
| prior corpus | seeded-sweep 10/5/1 rows snapshotted to session scratchpad; driver's own `*.bak` swap preserved them in-tree |

## Run parameters

| | |
|---|---|
| driver | `domains/qa-verifier/run_qav_generation.py` |
| invocation | `OPENAI_API_KEY=local PYTHONPATH=src nohup ./.venv/bin/python … --config domains/qa-verifier/agent-config.yaml --mode both` (NO --limit) |
| factory sha | `35e6dff` (recorded in the manifest) |
| launched | 2026-07-21 **17:11:26** BST · nohup pid 1441636 · ACTIVE short-polls ~2.5–3 min (not harness-tracked) |
| finished | 2026-07-21 **17:42:03** BST · **30m37s wall** (4h wall: 12.8% used) |
| log | `run_logs/corpus-run-20260721-171126.log` |
| fleet | `:9000`; teacher `gpt-oss-120b`, coach `qav-coach` (co-resident `qav` set) |

## Rows banked — census by side / split / mode / DC-class

| split | verdict | mode | dc_class | n |
|---|---|---|---|---|
| train | approve | harvest | — | **13** |
| train | approve | seeded_code (controls) | — | 7 |
| train | reject | harvest | DC-03 | **3** |
| train | reject | seeded_code | DC-08 | 3 |
| eval_qav | approve | harvest | — | 2 |
| eval_qav | reject | harvest | DC-03 | 2 |
| eval_qav | reject | gold_negative | DC-03 | 3 |
| eval_qav | reject | gold_negative | DC-08 | 1 |
| eval_qav | reject | seeded_code | DC-08 | 1 |

**By side+split: train 26 (approve 20 / reject 6) · eval_qav 9 (approve 2 / reject 7) ·
total 35.** rejected.jsonl: **0** (zero gate turn-aways this run; the sweep's one
coach-rejection did not recur). Dedup: driver `deduped=68` (the known ×2 double-count;
~34 real write-time collisions, same seeded-sibling classes as the sweep).

## Consumed vs missed ratified labels — 20/20, ZERO misses

`harvest_written=20`, `harvest_bundle_not_found=0`, `harvest_outcomes_skipped=4` (the same
4 queued A2/A3/A1-probable entries, skipped loudly, never guessed). Per-label bank:

- **approve/train (13):** api_test/TASK-UPT-001 · nats_core/TASK-MEP-002 ·
  study_tutor/TASK-VOX-002,-003,-004,-007 · forge/TASK-MP-001,-002,-003,-004A,-007 ·
  jarvis/TASK-JNB-001 · guardkit/TASK-BDDW-002
- **approve/eval_qav (2):** guardkit/TASK-BDDW-001 · study_tutor/TASK-VOX-005
- **reject/train (3):** forge/TASK-MP-005,-006,-008 (merge_review_caught, DC-03)
- **reject/eval_qav (2):** forge/TASK-MP-009,-004B (merge_review_caught, DC-03)

The new repos' bundle locations all worked — including the api_test census-footgun bundle
under `.guardkit/worktrees/FEAT-AE43/` and jarvis's `.claude/worktrees` duplicates correctly
skip-filtered. Splits match the pre-computed engine-law assignment exactly.

## Manifest verdict — honest

`domains/qa-verifier/manifests/qav-phase1-train.manifest.json` (finalized, factory_sha
`35e6dff`, dataset `qav-phase1-train-v1`, private DF-008):

- **`approve_share = 0.7692`** → `MANIFEST BALANCE ADVISORY FAIL` (outside 0.50±0.10) —
  logged loudly, rows banked, manifest written honestly. Better than the sweep's 0.70-on-10
  in absolute reject count (6 train rejects vs 3) but the 13 harvested approves outpaced them.
- **`ugly_green_share_of_approves = 0.95`** — the ≥0.45 floor PASSES with room (the
  deliberately-harvested blemished greens are doing their anti-over-reject job).
- **`contamination_check: PASS`** (intersection 0, sibling-variant 0, gold-source 0) — and
  the standalone `scripts/qav_contamination_check.py` re-ran clean: `VERDICT: PASS`.
- Validation: **35/35 rows `validate_row`-VALID** (envelope, metadata, label, provenance).

## Per-leg times + co-residency — the warm regime held

- **Seeded: 45 regen legs** (32 plants + 13 controls): min 19s · median 24s · mean 27s ·
  max 104s (the one cold first leg) — byte-for-byte the sweep's proven rates.
- **Harvest: ~621s for 20 rows ≈ 31s/row** (teacher <think> + coach gate, both warm,
  co-resident). The 2026-07-21 round-1 wall (51 min for 2 rows under thrash) is CURED at
  scale: 20 rows in ~10 minutes.
- **Evictions: ZERO.** llama-swap journal for the window: 0 evict / exited-prematurely /
  connection-refused lines. Driver log: zero 500s, zero retries, `teacher_refused=0`,
  `coach_rejected=0`, `evidence_empty_rejected=0`, `schema_rejected=0`. `/running` at
  finish = exactly the `qav` set (gpt-oss-120b · qav-coach · parakeet · qwen3-tts).

## Venue

Corpus repos untouched: HEADs and worktree counts identical before/after (guardkit
`b68c9e9d`/8 · study-tutor `f843cb5`/2 · forge `686439c`/1 · api_test `9066286`/4 ·
nats-core `2c060b2`/1 · jarvis `1fc7309`/8). Harvest read committed bundles in place; seeded
scratch worktrees cleaned per row (`output/qa-verifier/_scratch/` holds only the empty
`_src`/repo dirs, factory-side). Known cosmetic, pre-existing: `record_store_roots` leaks
into `corpus_roots` at `GenerateConfig.from_yaml` (only `bundle_schema_sha` is filtered) —
harmless (empty rglob), worth a one-line filter some session.

## Artifacts + provenance

- `output/qa-verifier/train.jsonl` — 26 rows · raw sha256 `3bd82c54826769720695f954b82e8cbaff147d9298d5a087adc27b2be1ee6e76`
- `output/qa-verifier/eval_qav.jsonl` — 9 rows · raw sha256 `8e2e27d72e42f8647fb111000971b1650a978dae272b449d454a333830af7436`
- `output/qa-verifier/rejected.jsonl` — 0 rows (empty-file sha `e3b0c442…`)
- `domains/qa-verifier/manifests/qav-phase1-train.manifest.json` — sha256 `4ae8ffb1bfbf01bb413485b7828fb080d594f79322b2e46c72b82eb6b6852007` (canonical train sha256 inside: `36688f67…`)
- merge commit `35e6dff` (outcomes + config, data only) · run log `run_logs/corpus-run-20260721-171126.log`
- Datasets private (DF-008). No push.

## The honest corpus-size assessment

**35 rows is not a trainable corpus — and this run was never going to make it one.** Against
the two reference points:

1. **The ~1000-row PLAN-level target** (GOAL/PLAN bulk ambition; the sweep receipt phrased
   the same ambition 500–800 train rows): we are at **26 train rows ≈ 3–5% of target**. The
   PLAN itself names the ceiling (§2 "volume reality": real historical bundles = low hundreds
   at best; seeded generation is the volume engine).
2. **The DCL pilot's 507-row deliberate-below-floor precedent:** that lane proved a tune can
   clear its bar from a deliberately-small, quality-first corpus. At 35 rows we are at ~7% of
   even that precedent — this corpus is **not yet at the "small but deliberate" tier**; it is
   at the "every gate proven, every source wired" tier.

What this run DID settle: the full production path — seeded + harvest + golds in ONE pass,
one manifest — is proven end-to-end at proven rates with zero misses on ratified labels and
zero serving incidents. Volume now has exactly four named levers, all engine-external:
(a) **more ratified batches** — the 79-bundle U4 pool is the reservoir, Rich-curation-only
by law; (b) **anchor coverage on study_tutor** (0/11 recipes anchor — still the single
highest-yield seeded lever); (c) the DC-03/DC-05 render-collapse (26 legs → 0 unique rows,
needs bundle-visible perturbation); (d) `seeded_bundle` augmentation (cap 25%, still 0).
Balance (0.77 approve-heavy) self-corrects as reject volume grows via (b)+(c); judge it at
the next volume tier, per the standing note.
