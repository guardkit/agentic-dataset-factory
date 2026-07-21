# RECEIPT — QAV harvest run, 2026-07-21 (co-load debut of the `qav` llama-swap set)

> **VERDICT: SERVING-POSTURE WALL — the run crashed on harvest row 1's COACH leg; ZERO rows
> banked, NO manifest written.** The engine is green (harvest mode ingested the ratified
> outcomes correctly, skipped the 4 queued entries loudly, the teacher leg ran and returned a
> real 200), but the **`qav` co-load set was never selected by llama-swap's matrix solver**, so
> the teacher and coach seats mutually evicted exactly as in the round-3/4 cold-thrash regime.
> coach-ft-v3 degraded from clean evict-shutdowns to crash-on-load (`exited prematurely`, :5801
> connection refused → HTTP 500), the driver's 6 coach retries all hit 500, and the run raised
> `RuntimeError: coach call failed after 6 attempts` on the FIRST harvested row. **The co-load
> intervention did NOT engage. Not a data/engine fault — a matrix set-selection defect + a
> non-cleared box.**

- Operator: S3 RUN operator (Fable), authorized seat use (Rich's standing GPU go).
- Repo HEAD: `26e261f` (harvest mode wired — the co-verified harvest execution).
- Driver command (verbatim RUNBOOK full-run shape + `--mode harvest`):
  ```
  OPENAI_API_KEY=local PYTHONPATH=src ./.venv/bin/python \
    domains/qa-verifier/run_qav_generation.py \
    --config domains/qa-verifier/agent-config.yaml --mode harvest
  ```
  nohup, PID 310159, ACTIVE short-polled (not harness-tracked). Log (uncommitted,
  run_logs convention): `run_logs/qav_harvest_20260721-083208.log`.

---

## 1. Preflight (all green before launch)

- **Seats on :9000** — both `gpt-oss-120b` and `coach-ft-v3` present in `GET /v1/models`.
- **Keepalive** — `systemctl is-active llama-swap-keepalive.timer` → **`inactive`** (exit 3),
  before AND after. Found-state preserved; **not re-armed** (the parker's call; RUNBOOK footnote
  transfers unchanged). No `sudo` state change made (already inactive; passworded box).
- **`qav` co-load set present** — `/opt/llama-swap/config/config.yaml:974`
  `qav: "go & cfv3 & pk & qt"` (added 2026-07-20; backup
  `config.yaml.bak-20260720-pre-qavset` present, 48525 B). It is the ONLY set containing both
  `go` and `cfv3`.
- **guardkit imports** under `interpreters.guardkit`
  (`/home/richardwoollcott/.../guardkit/.venv/bin/python -c "import guardkit"` → OK). (Harvest
  reads committed bundles in place and never invoked the regenerator bridge — see §5.)
- **Ratified outcomes** — `load_harvest_outcomes` authoritatively resolves the yaml to **2
  consumable + 4 skipped** (queued): consumable = `(guardkit, TASK-BDDW-001)`,
  `(guardkit, TASK-BDDW-002)`, both `coach_correct` (approve-side), sha `917bcef7`. Census-safe
  discovery FOUND both bundles on disk pre-run.
- **Venue baseline** — guardkit `b68c9e9d` / 8 worktrees / no `output/`; study-tutor `f843cb5`
  / 2 / none; forge `686439c` / 1 / none. No corpus-repo debris.

## 2. What ran — the honest failure record

Driver banner: `mode=harvest limit=None out=output/qa-verifier teacher=gpt-oss-120b
corpus=['forge','guardkit','study_tutor']`. Then, correctly:

```
HARVEST OUTCOME SKIP guardkit/TASK-QAWE-002 — disposition=queued (A2 …)
HARVEST OUTCOME SKIP guardkit/TASK-QAWE-004 — disposition=queued (A2 …)
HARVEST OUTCOME SKIP study-tutor/PO02-001   — disposition=queued (A3 …)
HARVEST OUTCOME SKIP study-tutor/TASK-PRV-001 — disposition=queued (A1-probable …)
```

The 4 queued entries were skipped + counted, never guessed — the labeling policy held. Then on
the first consumable row (`guardkit/TASK-BDDW-001`): teacher leg 200, coach leg failed 6× →
process raised and exited (rc≠0) at the coach `assess` call
(`generate.py:1110` → `run_qav_generation.py:114`).

## 3. Measured per-leg times (llama-swap-authoritative) + the co-residency verdict

| Leg | Set selected | Result | Time |
|---|---|---|---|
| Row-1 **teacher** (`gpt-oss-120b`) | **`autobuild_go`** (`go & gc & pk & qt`) — NOT `qav` | `POST 200`, 4683 B | **87.4 s** (`1m27.383s`), cold (load-inclusive) |
| Row-1 **coach** (`coach-ft-v3`), attempt ×6 | **`all`** (evicts `gpt-oss`) — NOT `qav` | `POST 500` ×6 | 1.4–2.6 s each (all failures) |

**CO-RESIDENCY VERDICT: the `qav` set did NOT hold both models — it was NEVER SELECTED.** The
matrix log is unambiguous and deterministic:

- `matrix: model=gpt-oss-120b set=autobuild_go … evict=[embed]` — the lone teacher request
  resolves to `autobuild_go` (go+**gc**), not `qav`.
- `matrix: model=coach-ft-v3 set=all … evict=[gpt-oss-120b]` — the lone coach request resolves
  to `all`, which **evicts the teacher**. It ping-ponged
  (`go→autobuild_go evict=[coach]` ⇄ `coach→all evict=[gpt-oss]`) ~6 cycles.

**Root cause (config-level, reportable — NOT fixed here):** llama-swap's matrix solver is
per-request and picks the lowest-**evict-cost** set containing the single requested model. For
`coach-ft-v3` while `gpt-oss` is resident, both `all` (evict `[gpt-oss]`, cost 1) and `qav`
(evict `[gc]`, cost 1) tie at cost 1 — and the solver breaks the tie in favour of **`all`**
(which evicts the teacher). `qav` only wins if a single request names BOTH models, which this
driver never does (it strictly alternates teacher→coach, one model per call). **So the set as
authored cannot engage for this driver's call pattern.** Eviction occurred on *every* leg — the
same mutual-eviction thrash rounds 3/4 measured, not the warm regime the set was meant to
deliver.

**Secondary factor — the box was NOT cleared.** The **s2s realtime demo is live** (PID 345542,
`speech-to-speech … --model_name gemma4-tutor … responses_api_base_url :9000`, running since
07-20). Its periodic `gemma4-tutor` requests select the `tutor` set (evicting both big seats),
compounding the thrash. Under the repeated rapid load/evict, coach-ft-v3 went from clean
evict-`shutdown` to **crash-on-load** (`running coach-ft-v3 exited: upstream command exited
prematurely`, `dial tcp 127.0.0.1:5801: connect: connection refused`), which is the HTTP 500 the
driver's 6 retries all hit. The GB10 "program-plan calendar cleared the box" RUNBOOK precondition
was not met.

## 4. Rows banked + manifest verdict

- **Banked: 0 train / 0 eval / 0 rejected.** `output/qa-verifier/{train,eval_qav,rejected}.jsonl`
  are all empty (0 rows). The 4 gold negatives were **NOT** written — they are emitted at
  finalize, which the row-1 crash preempted.
- **Manifest verdict: NONE — no manifest written.** The crash is upstream of finalize, so there
  is no `manifest.json` (and `domains/qa-verifier/manifests/qav-phase1-train.manifest.json` is
  the untouched round-4 pilot file, Jul-20). This is **not** the expected-at-low-N imbalance
  refusal — it is a serving-posture crash on the coach leg, before any manifest stage.
- **Prior corpus safe** — the run's automatic backup moved the round-4 pilot corpus to `*.bak`
  (intact: `train.jsonl.bak` 2 rows, `eval_qav.jsonl.bak` 5 rows, `manifest.json.bak` present).

## 5. Validation

N/A — **zero rows to validate.** (`qav.contracts.validate_row` / the contamination gate have no
input.) The engine's harvest-label ingestion and the queued-skip loudness law both behaved
correctly; the wall is purely serving-side. Contract-validity of harvested rows remains
unproven-this-run.

## 6. Venue + keepalive receipts (found-state discipline held)

- **Corpus repos CLEAN — no breach.** Post-run: guardkit `b68c9e9d` / 8 worktrees / no `output/`;
  study-tutor `f843cb5` / 2 / none; forge `686439c` / 1 / none — identical to baseline. All
  `git status` dirt (guardkit `memory-query-log.jsonl`, forge `uv.lock`, study-tutor research
  docs) is **pre-existing**, none from this run. Harvest read committed bundles in place — no
  scratch worktrees created (the `_scratch/` residue is round-4's, untouched).
- **Keepalive `inactive` before AND after** — not re-armed. Serving posture returned as-found
  (gpt-oss-120b left resident; it TTLs out / the next s2s request evicts it; the s2s demo left
  running — Rich's, not touched).

## 7. Recommendation to the coordinator

**WALL — do not re-run harvest as-is; it will crash identically (the set-selection is
deterministic).** Two serving items gate a warm harvest run, both OUTSIDE this RUN operator's
edit scope (llama-swap config = serving-owner's lane; `src/qav/**` + the driver = do-not-edit):

1. **The `qav` set cannot win the tiebreak.** Either (a) make the driver name both models in a
   single warmup/keepalive request so `qav` is selected and becomes the resident zero-cost set
   for both legs, or (b) reshape the sets so a lone `coach-ft-v3` request prefers a set that
   keeps `gpt-oss` resident (e.g. drop `cfv3` from `all` for the duration, or give `qav` a
   lower tiebreak rank / a unique addressable handle), or (c) adopt the RUNBOOK's **batched-legs**
   posture (all teacher calls, then all coach) so each seat cold-loads once — an engine/driver
   change. Any of these is a serving decision to be recorded, per the RUNBOOK's "Serving
   posture — decide BEFORE the full run" fork.
2. **Clear the box.** The s2s realtime demo (PID 345542) was live throughout and competes for
   the GPU; the RUNBOOK's cleared-calendar precondition must actually hold before the run.

Everything upstream is green: harvest ingestion + the queued-skip loudness law are correct, both
bundles discover on disk, the teacher leg returns a real 200, keepalive posture safe, venue
clean. Re-run this exact command after the serving posture is fixed; expect (at this N) 2
approve-side harvest rows + 4 gold and the **expected low-N imbalance refusal** in the manifest —
which will then be the honest recorded result.

---

## ROUND 2 (the qav-coach cure) — COMPLETED; first ratified rows BANKED

> Written by the coordinator: the operator agent was killed mid-watch by a VS Code crash —
> the detached (nohup) driver finished the run alone, which is exactly what that discipline
> is for. All post-run verification below re-driven by the coordinator's own hand.

- **Run:** `run_logs/qav_harvest_r2_20260721-084747.log`, 08:47:47 → 09:39:09 (**51m22s**),
  rc clean. Config coach = `qav-coach` (the unique-member set cure, commit `b2e89fa`).
- **Banked: 6 rows — the full ratified consumable set.** train = 1 (BDDW approve; its sibling
  approve landed eval by the holdout RNG), eval_qav = 5 (4 gold negatives + 1 approve).
  4 queued outcomes skipped LOUDLY (A3/PRV/flagged — per policy). Zero rejects, zero
  teacher refusals, zero coach rejections, zero schema/evidence-empty rejects.
- **Coordinator validation: 6/6 contract-valid** (`validate_row` + `extract_bundle` +
  `extract_label` per row); labels byte-match the ratified outcomes yaml; manifest
  finalized, contamination **pass**, and the balance advisory **honestly refused**
  (`approve_share 1.00 outside 0.50±0.10`) — the expected verdict at this N, recorded
  not hidden.
- **Co-residency verdict: FUNCTIONAL PASS, measurement inconclusive.** Round-1's kill mode
  is gone — zero coach 500s; every `qav-coach` call forced the qav set as designed. BUT the
  51-minute wall for 2 model rows shows serving contention with LIVE tutor/s2s traffic
  during the run (post-run `/running` = the tutor set resident — the box was not quiet).
  Warm co-resident leg times remain unmeasured; measure on the next quiet-box run.
- **Keepalive:** `inactive` before/after (verified; never re-armed). **Venue:** corpus repos
  carry only their documented pre-existing residue (guardkit memory-query-log · forge
  uv.lock · Rich's untracked study-tutor notes); zero harvest debris.
