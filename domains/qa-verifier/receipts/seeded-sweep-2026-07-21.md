# Receipt — SEEDED SWEEP: the full seeded_defect run over all 13 record-complete tasks (2026-07-21)

> **COMPLETE — 19m14s wall, 15 rows banked (10 train / 5 eval), 15/15 contract-valid,
> contamination PASS twice (embedded + standalone), zero evictions, zero coach 500s.** The
> manifest's balance now has **BOTH sides for the first time**: approve 7 / reject 8 across the
> corpus (train-side approve_share **0.70** — an honest ADVISORY FAIL against 0.50±0.10). The
> breadth thesis half-confirmed: **distinct task records did land distinct rows** (7 study_tutor
> controls banked, one per task, even though all seven sit at ONE sha), but the reject side is
> still **anchor-limited, not breadth-limited** — study_tutor anchored **0/11** reject recipes,
> so every seeded reject remains guardkit-sourced R-ABSENT-junit/DC-08.

---

## Preflight (and the one deviation, cured + receipted)

| check | expected | found |
|---|---|---|
| keepalive timer | inactive | **ACTIVE** (re-armed since the re-spike; 5-min fires; allowlist = gemma4-tutor / tutor-coach / embed) |
| venue baseline | 60325b2 clean | ✓ `60325b2`, only untracked `domains/qa-verifier/manifests/` + `run_logs/`; corpus HEADs guardkit `b68c9e9d` · study-tutor `f843cb5` · forge `686439c`; all 4 interpreter paths present; `limit:` commented |
| `/running` before | s2s stack | ✓ embed, gemma4-tutor, parakeet-tdt-0.6b-v3, qwen3-tts-0.6b, tutor-coach (all ready); teacher/coach NOT loaded (cold first leg expected) |

**The keepalive deviation and its cure.** The config's own law: *"Keepalive MUST stay paused
while this set runs (the autobuild_go/coach31 OOM law)"* — but the timer was live and sudo is
passworded, so `systemctl stop` was not available to this seat. Cure: held the keepalive script's
**own concurrency guard** — an exclusive `flock` on `/var/lock/llama-swap-keepalive.lock`
(user-owned) — for the run's duration. Every fire then exits 0 immediately by the script's design.
**Journal-proven:** all four fires in the window (14:51:00, 14:56:02, 15:01:04, 15:06:13) logged
`"Another keep-alive run is in progress; exiting."` — no revive attempted, no OOM exposure. The
timer itself was **never touched** (not stopped, not re-armed — left exactly as found, per
instruction). Lock released at 15:07/15:11 post-run; keepalive's own next fire (**15:11:20**)
revived `embed gemma4-tutor tutor-coach` — the venue restored its s2s posture by itself.

- s2s app: its LLM seats were evicted at the qav set-switch (~14:47) and re-warmed at 15:11:20 —
  the tolerated-evictions posture; the audio pair (parakeet + qwen3-tts) stayed resident
  **throughout** (pk & qt ride every set). No s2s transport errors observed from this side.
- Pre-run bank (1 train + 5 eval re-spike rows) snapshotted to the session scratchpad **and**
  preserved by the driver's own `*.bak` swap; post-run corpus additionally snapshotted to
  `output_backup_qav-seededsweep_20260721-151136/`.

## Run parameters

| | |
|---|---|
| driver | `domains/qa-verifier/run_qav_generation.py` |
| invocation | `PYTHONPATH=src OPENAI_API_KEY=local .venv/bin/python … --config domains/qa-verifier/agent-config.yaml --mode seeded_defect` (**NO --limit** — the whole included set) |
| factory sha | `60325b2` |
| launched | 2026-07-21 **14:46:57** BST · nohup pid 976348 · active short-polls ~170s (not harness-tracked) |
| finished | 2026-07-21 **15:06:11** BST · **19m14s wall** (well inside the 4h wall) |
| log | `run_logs/seeded-sweep-2026-07-21.log` |
| fleet | `:9000` up throughout; teacher `gpt-oss-120b`, coach `qav-coach` (co-resident `qav` set) |

## Discovery — 13 included / 71 excluded (exclusion law loud on every one)

Included: **guardkit** TASK-QAWE-001..004 @`799cefd0`, TASK-BDDW-001 @`917bcef7`, TASK-BDDW-002 ·
**study_tutor** TASK-PRV-001..007 @`94f3331`. Excluded 71 with logged reasons (spec-only features,
no approved-sha key — e.g. all seven study_tutor TASK-PO02-* fell to
`no approved-sha key in merge_summary` — gold sources, unresolvable shas). Forge contributed no
included task (its only banked presence is the FEAT-DD4F gold negative, eval-held as designed).

## Rows banked by side

| split | approve | reject | total |
|---|---|---|---|
| train | **7** (all seeded-control greens) | **3** (all seeded_code) | 10 |
| eval_qav | 0 | **5** (1 seeded_code + 4 gold negatives) | 5 |
| rejected.jsonl | — | — | 1 (`coach_rejected`) |

Full banked map:

| split | verdict | mode | recipe | dc | source | row_id |
|---|---|---|---|---|---|---|
| train | reject | seeded_code | R-ABSENT-junit | DC-08 | guardkit/TASK-QAWE-002@799cefd0 | qav-af89e9bb3d485499 |
| train | reject | seeded_code | R-ABSENT-junit | DC-08 | guardkit/TASK-QAWE-004@799cefd0 | qav-b974a4c8fa52b674 |
| train | reject | seeded_code | R-ABSENT-junit | DC-08 | guardkit/TASK-BDDW-001@917bcef7 | qav-f948d9acd2ad27bf |
| train | approve | seeded_code | R-CONTROL-noop | — | study_tutor/TASK-PRV-001@94f3331 | qav-131b59625f16c301 |
| train | approve | seeded_code | R-CONTROL-noop | — | study_tutor/TASK-PRV-002@94f3331 | qav-b910c6d09ffe4239 |
| train | approve | seeded_code | R-CONTROL-noop | — | study_tutor/TASK-PRV-003@94f3331 | qav-5f0e03aae7746945 |
| train | approve | seeded_code | R-CONTROL-noop | — | study_tutor/TASK-PRV-004@94f3331 | qav-8fe8c6733d65b099 |
| train | approve | seeded_code | R-CONTROL-noop | — | study_tutor/TASK-PRV-005@94f3331 | qav-e790462d9f0c3087 |
| train | approve | seeded_code | R-CONTROL-noop | — | study_tutor/TASK-PRV-006@94f3331 | qav-dda51ae892430427 |
| train | approve | seeded_code | R-CONTROL-noop | — | study_tutor/TASK-PRV-007@94f3331 | qav-6c8f9c395dc7501f |
| eval | reject | seeded_code | R-ABSENT-junit | DC-08 | guardkit/TASK-QAWE-001@799cefd0 | qav-a73b879e7e74bd93 |
| eval | reject | gold_negative | — | DC-08 | study-tutor/TASK-SMP2-07@54ab79fd | qav-43c8de8edc8d812b |
| eval | reject | gold_negative | — | DC-03 | study-tutor/TASK-SMP3-06@99bf79d5 | qav-f9f7f8f886c64b03 |
| eval | reject | gold_negative | — | DC-03 | guardkit/TASK-QAV-005@888906f2 | qav-0201caff2db7a8cd |
| eval | reject | gold_negative | — | DC-03 | forge/FEAT-DD4F@1ad98c0 | qav-13f964bbaead7fd1 |

The one rejected row: guardkit/TASK-QAWE-002 `R-CONTROL-noop`, reason `coach_rejected`
(`coach: keyword-sniffed revise`) — a control green the coach's keyword-sniff turned away.
Honest gate turn-away, not a crash; the quality gates saw one bad row, not zero rows.

## Per-recipe / per-task hit map (45 planted legs)

| recipe | legs planted | where anchored | unique rows banked |
|---|---|---|---|
| R-ABSENT-junit | 6 | QAWE×4, BDDW×2 | **4** (QAWE-001/-002/-004, BDDW-001; -003 + BDDW-002 deduped) |
| R-DC03-callsite | 6 | QAWE×4, BDDW×2 | 0 (all deduped) |
| R-DC03-mockseam | 4 | QAWE×4 | 0 (all deduped) |
| R-DC03-producer | 4 | QAWE×4 | 0 (all deduped) |
| R-DC05-skipguard | 6 | QAWE×4, BDDW×2 | 0 (all deduped) |
| R-DC05-sysmod | 6 | QAWE×4, BDDW×2 | 0 (all deduped) |
| R-CONTROL-noop | 13 | every task | **7** (PRV-001..007; the 6 guardkit controls: 5 deduped + 1 coach-rejected) |

- **anchor_skipped = 111** = study_tutor 7×11 (all 77 — the anchors do not match study_tutor tree
  shapes at all) + QAWE 4×5 + BDDW 2×7 (BDDW additionally misses mockseam/producer). The recorded
  EXPECTED-MISS recipes (R-DC03-kwargs, R-DC08-undefstep, R-DC08-pendmask, R-DC12-planvisible,
  R-DC14-narrative) anchored **nowhere**, as recorded.
- **Dedup: 33 real write-time collisions** (every DC-03/DC-05 plant regenerated a bundle that
  rendered identical to an already-banked bundle; sibling-task copies of ABSENT-junit and the
  guardkit controls likewise). Driver-summary `deduped=66` **double-counts** these 33: the
  seeded-row path bumps the counter on `write_row()==False` (src/qav/generate.py:983) and then
  finalize re-adds `writer.duplicates_skipped` for the same events (:852). The re-spike's
  `deduped=38` fits the same ×2 (19 real). Cosmetic counters-only bug — no row effect; worth a
  one-line fix some session.

Driver summary (verbatim): `seeded_code_written=4 seeded_control_written=0+7 [control=7]
seeded_bundle_written=0 gold_negatives_written=4 harvest_written=0 teacher_refused=0
coach_rejected=1 cue_rejected=0 evidence_empty_rejected=0 schema_rejected=0 anchor_skipped=111
deduped=66 train=10 eval_qav=5 manifest_finalized=True balance_ok=False approve_share=0.7`.

## Manifest verdict — honest, and balance now has BOTH sides

`domains/qa-verifier/manifests/qav-phase1-train.manifest.json` (finalized, `factory_sha 60325b2`,
dataset `qav-phase1-train-v1`, private DF-008):

- `by_verdict` (train side): **approve 7 / reject 3** — the headline: after the harvest run's 0/0
  and the re-spike's 0/1, the balance report finally has both sides.
- **`approve_share = 0.70`** → `MANIFEST BALANCE ADVISORY FAIL` (outside 0.50±0.10) — logged
  loudly, rows banked + manifest written honestly (advisory by design, not massaged).
- **`ugly_green_share_of_approves = 0.8571`** — the ≥0.45 bar **PASSES**.
- `by_dc_class`: DC-08 = 3 (train reject diversity is one class deep — see readiness).
- **`contamination_check: PASS`** (intersection 0, sibling-variant 0, gold-source 0) — and the
  standalone `scripts/qav_contamination_check.py` re-ran clean: `VERDICT: PASS`, rc=0.
- File-hash note: the manifest's `files[0].sha256` (`acb84767…`) hashes the **canonical
  re-serialization** of the train rows, not raw file bytes — reproduced exactly from the on-disk
  rows via `qav.manifest._jsonl_bytes` (raw-byte sha of `train.jsonl` is `37781a4a…` below). Honest,
  just a different canonical form.

## Validation — every banked row

`qav.contracts.validate_row` over all 15 banked rows (train + eval_qav): **15/15 VALID — CORPUS
OK, FAILURES 0.**

## Per-leg times + co-residency

45 regen legs (32 anchored plants + 13 controls): **min 17s · median 23s · mean 25s · max 100s**.
The single 100s outlier is the FIRST leg (QAWE-001/R-ABSENT-junit) — it paid the one-time
cold-load of both seats; everything after ran warm ≤33s. That is a further ~40% improvement on the
re-spike's warm mean (~43s), because the co-resident set never thrashed.

**Co-residency held run-long: zero** `evict` / `500` / `retry` / `unload` / `connection` lines in
the log; `teacher_refused=0`; every coach call answered. `/running` at finish = exactly the `qav`
set: gpt-oss-120b + qav-coach + parakeet + qwen3-tts. No OOM, no keepalive interference (see
preflight).

## Corpus-assembly readiness (the honest assessment)

**The engine is proven at full breadth; the corpus is not yet trainable at this volume.** 10 train
rows (7 approve / 3 reject, reject side one recipe × one dc_class deep) against a 500–800-row
ambition. What this sweep settled, and what it newly quantified:

1. **Proven:** end-to-end full-set run, both sides banked, all gates honest, dedup correct,
   co-residency stable, 19-minute full-sweep cost — re-runs are CHEAP now. The sweep itself is no
   longer the bottleneck.
2. **Breadth lever, refined:** distinct **task records** land distinct rows even at one sha (7/7
   PRV controls banked @`94f3331`) — record-distinctness, not sha-distinctness, is what beats
   dedup. But near-clone records (QAWE siblings) still collide.
3. **Bottleneck #1 — anchor coverage on study_tutor: 0/11.** Seven of the 13 tasks contribute
   zero reject plants. Extending the anchor vocabulary to study_tutor tree shapes is the single
   highest-yield move for reject-side volume (it would roughly double plantable surface).
4. **Bottleneck #2 — DC-03/DC-05 render-collapse: 26 legs → 0 unique rows.** These mutations
   regenerate bundles whose rendered user-message is identical to an already-banked bundle, so
   they can never yield under content-addressed row_ids. Either the mutations must perturb
   bundle-visible fields, or these recipes will stay yield-zero on this corpus.
5. **Untapped volume levers:** `harvest` mode (ratified labels wired, inert in this mode-scoped
   run), `seeded_bundle` augmentation (cap 25%, currently 0), and the 5 EXPECTED-MISS recipes
   (anchored nowhere).
6. **Balance:** approve-share 0.70 will swing as reject volume grows; judge it only on the next
   full-volume corpus, per the standing note.

## Artifacts + provenance

- `output/qa-verifier/train.jsonl` — 10 rows · raw sha256 `37781a4a017ac3665f8c5937e44551f4d09ca5b531df7e81de72e250834fb05c`
- `output/qa-verifier/eval_qav.jsonl` — 5 rows · raw sha256 `58ee7c8bb7a25561cd7df6d276ccfa912dd186dbfc1a7734acdb481365b621c9`
- `output/qa-verifier/rejected.jsonl` — 1 row · raw sha256 `9423f690f58b3a903448711d7e901f8a3ec0036c25c98ee5f6a0045c791669bf`
- `domains/qa-verifier/manifests/qav-phase1-train.manifest.json` — finalized, factory_sha `60325b2`
- `run_logs/seeded-sweep-2026-07-21.log` — full driver log
- `output_backup_qav-seededsweep_20260721-151136/` — post-run snapshot; prior corpus in `*.bak` + scratchpad
- Datasets private (DF-008). Corpus repos untouched (scratch worktrees only, cleaned per row).
