# RECEIPT — QAV one-row spike, 2026-07-20 (GPU re-arm day)

> **VERDICT: HONEST WALL — the spike did not produce a row.** The real driver refuses at
> source-task discovery: `_discover_source_tasks` is the loud stub the d9ce33a commit itself
> names as "the concrete wiring left for the first attended run." No teacher call, no GPU
> load, no output mutation, no scratch worktrees. This is the RUNBOOK's own troubleshooting
> row ("source-task discovery is a generation run"), hit live. **Not pilot-ready.** The
> coordinator's next move is the wiring lane, not a re-run.

- Operator: SPIKE operator (Fable), authorized seat use ("The demo is done so you are free
  to use the GPU's" — Rich, 2026-07-20).
- Repo HEAD at spike: `d9ce33a` (fresh engine + driver, coach-verified).
- Log: `run_logs/qav_spike_20260720-170038.log` (uncommitted, run_logs convention).

---

## 1. What ran

Exactly the RUNBOOK's SPIKE command (attempt 1 omitted `PYTHONPATH=src` by operator error,
failed on import in <1 s, discarded; attempt 2 verbatim):

```
cd ~/Projects/appmilla_github/agentic-dataset-factory
export OPENAI_API_KEY=local
PYTHONPATH=src python domains/qa-verifier/run_qav_generation.py \
    --config domains/qa-verifier/agent-config.yaml --limit 1
```

Driver banner confirmed the real wiring engaged: `mode=seeded_defect limit=1
out=output/qa-verifier teacher=gpt-oss-120b corpus=['forge', 'guardkit', 'study_tutor']`.

## 2. Measured wall-times — HONEST FAILURE RECORD

| Leg | Measured |
|---|---|
| Total wall | **<1 s** (start `2026-07-20T17:00:38+01:00` epoch 1784563238 → end same second, rc=1) |
| regenerate leg (gather_evidence) | **never reached** |
| teacher leg (gpt-oss-120b) | **never reached** |
| coach leg (coach-ft-v3) | **never reached** |

Failure point (full traceback in the log):

```
File ".../src/qav/generate.py", line 555, in run_generation
    source_tasks = _discover_source_tasks(config)
File ".../src/qav/generate.py", line 810, in _discover_source_tasks
RuntimeError: source-task discovery is a generation run — inject source_tasks in tests,
and wire the git-worktree provider (approved-sha resolution + per-repo interpreter,
config.interpreters) for the attended GB10 run
```

`src/qav/generate.py:800-814` is a documented loud stub: its docstring records the two open
points — (a) approved-sha resolution per task, (b) file-map scoping (whole-worktree vs
recipe-relevant subtree). The refusal is by design (no unchecked rows), not a regression.

### The second wall queued directly behind the first (found by preflight, not hit)

Even with discovery wired, `GatherEvidenceRegenerator.regenerate`
(`src/qav/injector.py:154-166`) imports guardkit **in the driver's own process**, and:

- guardkit is **NOT importable from the factory `.venv`** (verified: `ModuleNotFoundError`);
- the driver never threads `config.interpreters` into the regenerator — it is constructed
  as `GatherEvidenceRegenerator(task_id="qav-seeded", profile_name=None)`
  (`run_qav_generation.py:170`); the per-repo interpreter seam exists only in config;
- of the three configured `interpreters:`, only guardkit's venv can import guardkit
  (guardkit `.venv` OK · study-tutor `.venv` **no guardkit** · forge `.venv` **no guardkit**,
  and forge's venv is Python 3.14.4). The wiring lane must decide: install guardkit into
  each substrate venv, or run the validator from guardkit's venv against foreign worktrees
  via subprocess. This is a design point for that lane, not for a spike.

## 3. Projection — NOT MEASURABLE this spike

No row completed, so there is **no measured row-time and no honest full-run projection**.
For the coordinator, the arithmetic that a successful spike will feed (GOAL.md "Generation
targets (Phase 1)"): seeded reject targets total **500 rows** (DC-03 200 + DC-05 75 + DC-08
75 + DC-14 75 + other 75), plus the seeded-control share of the ~500 approve side, plus
seeded_bundle capped at 25% of seeded rows, plus harvest (~100–300, no model legs) and the
4 gold negatives (assembled offline — proven cheap). Each seeded_code row costs one
regenerate leg (CPU/pytest-substrate, likely the dominant cost) + one teacher leg + one
coach leg. Projection = measured-row-time × ~500–800 model-touching rows, to be computed
when the re-run spike lands a row.

## 4. PREFLIGHT-CORPUS findings (all paths verified on disk 2026-07-20)

**Exists and matches config/PLAN §2.1:**

- All three corpus repos present as git repos: guardkit `b68c9e9d` · study-tutor `f843cb5`
  · forge `686439c`; all with `.guardkit/` trees; all with `.venv/bin/python`.
- `bundle_schema_sha: "41a0ebe457"` resolves to a commit in guardkit.
- guardkit: FEAT-E2CB (archive, coach_turn_1/2.json under run1-artifacts-TASK-BDDW-001),
  FEAT-10AC (autobuild + archive run3.yaml), FEAT-0E6D (autobuild + archive);
  `docs/retro/evidence/` carries all three named review summaries. Repo-wide:
  598 coach_turn*.json + 102 coach_evidence* files.
- study-tutor: FEAT-APP-001 + TASK-APP1-01..07, FEAT-SMP-002 + TASK-SMP2-02..07,
  FEAT-SMP-003 + TASK-SMP3-01..07; 137 coach_turn + 61 coach_evidence files.
- forge: FEAT-3ED2 present (+ FEAT-DD4F, the GN-4 source); 139 coach_turn +
  19 coach_evidence files.
- Gold-negative verbatim survival (`qav.gold_negatives.probe_survival`, run live):
  **GN-3 VERBATIM** (`guardkit/.guardkit/worktrees/FEAT-10AC/.guardkit/autobuild/TASK-QAV-005/coach_evidence_turn_2.json`);
  GN-1, GN-2, GN-4 → `reconstructed` fallback (allowed by design).

**Does not exist / gaps:**

- **FEAT-SMP-001 has no run record** — only the feature spec
  (`study-tutor/.guardkit/features/FEAT-SMP-001.yaml`); nothing under autobuild/ or
  archive/. PLAN §2.1's "FEAT-SMP-001..003" overstates by one feature.
- TASK-SMP2-01 absent (SMP-002's task records start at TASK-SMP2-02).
- **Approved-sha resolution has no on-disk source of record yet** — the config carries no
  per-task shas; resolving each known-green task's approved sha from run records is
  exactly open point (a) of the discovery stub.
- guardkit importability per `interpreters:` — see §2's second wall.

## 5. PREFLIGHT-SEAT receipts

- llama-swap: user-scope systemd service (`systemctl --user`), live as
  `/usr/local/bin/llama-swap -config /opt/llama-swap/config/config.yaml -listen :9000
  -watch-config`.
- **Both aliases exist in the estate config** `/opt/llama-swap/config/config.yaml`:
  `gpt-oss-120b` (line 477, mxfp4 GGUF) and `coach-ft-v3` (line 380,
  coach-gemma4-26b-moe-v3 Q4_K_M). Both also listed by `GET :9000/v1/models`.
- `GET http://127.0.0.1:9000/running` before spike: `embed`, `parakeet-tdt-0.6b-v3`,
  `qwen3-tts-0.6b` all `ready` (the s2s demo audio stack). **After spike: identical** —
  neither teacher nor coach ever loaded; zero GPU engagement by this spike.

## 6. KEEPALIVE receipts (both toggles)

- **Toggle 1 (pause), before spike:** `systemctl is-active llama-swap-keepalive.timer` →
  **`inactive`** (exit 3) — the RUNBOOK's required pre-run state was ALREADY the live state
  (the RUNBOOK itself says "idempotent — often already inactive, but VERIFY"). `sudo -n`
  is passworded on this box (known GB10 posture), so the literal `sudo systemctl stop` was
  not executable non-interactively — and was a no-op against an already-inactive timer.
  Safety property (timer cannot fire mid-load) held throughout. **No state change made.**
- **Toggle 2 (restore), after spike:** verified again → **`inactive`** (exit 3). Restore =
  returned-to-found-state: the timer was inactive before this spike and is inactive after
  it; this spike changed nothing about serving posture. Whoever deliberately parked the
  timer off (pre-existing estate state) still owns re-arming it; the RUNBOOK's standing
  footnote (re-read the keepalive probe list before re-enabling — coach-ft-v3 allowlist is
  a separate serving-posture item) transfers to that owner.

## 7. Post-spike state verification

- `output/qa-verifier/`: **still absent** — no jsonl, no manifest, no `.bak` churn.
- `output/qa-verifier/_scratch/`: absent — no worktrees created in any corpus repo.
- Corpus repos untouched (read-only venue rule never exercised).

## 8. Recommendation to the coordinator

**WALL — do not schedule the pilot or the full run.** The blocking lane is the discovery
stub's own named wiring: (a) approved-sha resolution per known-green task (needs a source
of record — the run records/archive yamls are the candidates), (b) file-map scoping, and
(c) the regenerator interpreter seam (guardkit unimportable from the factory venv; the
`interpreters:` config is never threaded; 2 of 3 substrate venvs lack guardkit). All three
are named open points in the d9ce33a commit/docstrings — this is scoped build work, not a
fix-forward. Everything else is green: corpus artifacts rich and verified (one PLAN §2.1
overstatement: FEAT-SMP-001 has no run record), both seats configured and reachable,
keepalive posture safe. Re-run THIS spike unchanged once the wiring lane lands; the
projection arithmetic in §3 is ready to receive the measured row-time.

---

# ROUND 2 (post-wiring) — 2026-07-20 (GPU freed by Rich)

> **VERDICT: HONEST WALL AGAIN — the spike still did not produce a row, on a NEW (third) wall.**
> The wiring lane (HEAD `f75a147`) cleared round 1's wall 1: source-task **discovery is now real**
> (13 included / 71 excluded, the approved-sha honesty law firing exactly as designed). But every
> one of the 13 included tasks is then **SKIPPED** with `scoped file map empty … (nothing to
> inject)` → **zero seeded rows, zero teacher leg, zero regenerate leg, zero GPU engagement.**
> Root cause pinned to a **one-line path-resolution bug** in the new file-map provider (below), not
> a missing feature. **Still not pilot-ready.** The coordinator's next move is that one-line fix +
> re-run, after which the regenerator interpreter bridge (round 1's wall 2, still never reached)
> gets its first real exercise.

- Operator: SPIKE operator (Fable), round 2, authorized seat use (Rich freed the GPU).
- Repo HEAD at spike: `f75a147` (the three walls' wiring — record-driven discovery + worktree
  file-map + interpreter-bridged regenerator).
- Log: `run_logs/qav_spike_r2_20260720-172833.log` (uncommitted, run_logs convention).
- Launched via `nohup … ./.venv/bin/python …` into `run_logs/`, polled short.

## R2.1 What ran

Exactly the RUNBOOK's SPIKE command (`--limit 1`, `PYTHONPATH=src`, `OPENAI_API_KEY=local`):

```
PYTHONPATH=src python domains/qa-verifier/run_qav_generation.py \
    --config domains/qa-verifier/agent-config.yaml --limit 1
```

Driver banner: `mode=seeded_defect limit=1 out=output/qa-verifier teacher=gpt-oss-120b
corpus=['forge', 'guardkit', 'study_tutor']`. The run completed (rc=0), wrote a manifest, and
did **not** refuse — but produced **no seeded/model-touching row.**

Discovery (round 1's wall 1) is now wired and correct:
`DISCOVERY: 13 source task(s) included, 71 excluded`. The exclusion law logs every turn-away;
round 1's prediction held — `study_tutor/FEAT-SMP-001` is excluded as spec-only (no
`merge_summary.json`), and `FEAT-PO-002`'s tasks are excluded for *no approved-sha key* in their
merge summary. Then, immediately behind it, the new wall:

```
WARNING DISCOVERY SKIP guardkit/TASK-QAWE-001 — scoped file map empty at 799cefd0 (nothing to inject)
… (all 13 included tasks skipped identically) …
INFO DONE seeded_code=0 control=0 seeded_bundle=0 harvest=0 gold=4 … train=0 eval_qav=4
```

## R2.2 Root cause — a factory-relative worktree path handed to git running in the corpus repo

Pinned by direct reproduction. In `src/qav/discover.py`:

- `discover_source_tasks` (L360–397) calls `checkout_scoped_file_map(corpus_root, sha, worktree)`
  with a **factory-relative** `worktree = scratch_dir/_src/<repo>/<task>`.
- `checkout_scoped_file_map` (L341–354) runs `git worktree add --detach --force <worktree> <sha>`
  via `_run_git`, which executes git with **`cwd = corpus_repo_root`** (L320–328).
- git therefore resolves the *relative* worktree path **against its own cwd (the corpus repo)** —
  it creates the worktree at `<corpus_repo>/output/qa-verifier/_scratch/_src/<repo>/<task>`, NOT
  in the factory tree. `_run_git` sees rc=0 and does not raise. Then `scope_file_map(worktree)`
  reads the factory-relative path, **which does not exist**, and returns `{}` → SKIP.

Proof (this session): `scope_file_map` on a *live absolute-path* checkout of guardkit@`799cefd0`
returns **7920** files; `checkout_scoped_file_map` with the **relative** path returns **0**, and
instrumenting it shows `after add: exists=False` (the worktree landed inside the corpus repo).
**Fix = absolutize `worktree_path` before the git call** (or set git `cwd` independent of the
worktree location). One line. **NOT applied** — `src/qav/**` is do-not-edit per the RUNBOOK; this
is the wiring lane's call.

### Side effect this bug caused — the read-only VENUE RULE was breached

Because the worktree lands *inside* the corpus repo, the spike wrote
`output/qa-verifier/_scratch/…` **into the guardkit and study-tutor working trees** (forge had no
included task reach checkout). `git worktree remove` (also cwd=corpus, so it found them) cleaned
the checked-out files, but left empty dir skeletons behind; `output/` is **not** gitignored in
those repos, so this is real pollution of a read-only venue. **Operator cleaned it** — the
`output/` trees were removed and both repos verified restored as-found; the 7 guardkit + 1
study-tutor pre-existing `autobuild/FEAT-*` worktrees were untouched. The one-line fix also closes
this venue breach.

## R2.3 Measured wall-times

| Leg | Measured |
|---|---|
| Total wall | **~8 s** (start `2026-07-20T17:28:33+01:00` epoch 1784564913 → `DONE` 17:28:41, rc=0) |
| discovery — record scan (refs) | ~2.3 s (17:28:33.79 → 17:28:36.06; 13 included / 71 excluded) |
| discovery — 13 worktree checkouts (all SKIP) | ~5.4 s (17:28:36.06 → 17:28:41.46) |
| regenerate leg (guardkit `gather_evidence`) | **never reached** — no task survived discovery |
| teacher leg (gpt-oss-120b) | **never reached** — no GPU load (seats unchanged: `embed`, `parakeet`, `qwen3-tts` only, before **and** after) |
| coach leg (coach-ft-v3) | **never reached** |

## R2.4 What was produced + validation

- `output/qa-verifier/eval_qav.jsonl` — **4 gold negatives** (assembled offline, no model legs —
  the cheap path proven in round 1). `train.jsonl`, `rejected.jsonl` = empty. Manifest written to
  both `output/qa-verifier/manifest.json` and `domains/qa-verifier/manifests/…`.
- **Row validation (`qav.contracts.validate_row`, run live):** swept 4 rows → **4 valid, 0
  failures** (`CORPUS OK`). All 4 are `generation_mode=gold_negative`.
- **Contamination embed:** `manifest.contamination_check.status = "pass"` — but **trivially**
  (0 train rows, only the 4 eval-side gold negatives; `by_generation_mode.seeded_code = 0`). Not
  evidence the seeded pipe works.

## R2.5 Projection — STILL NOT MEASURABLE

No model-touching row completed, so there is still **no measured row-time and no honest full-run
projection.** The pre-laid arithmetic in §3 (measured-row-time × ~500–800 model-touching rows over
the GOAL.md Phase-1 targets) stands ready and unchanged, awaiting the first real seeded row.

## R2.6 Keepalive receipts (found-state discipline honored)

- **Before:** `systemctl is-active llama-swap-keepalive.timer` → **`inactive`** (exit 3) — the
  parker's pre-existing state, confirmed still live this afternoon. **Not re-armed** — that is the
  parker's call, not this spike's (per the task instruction and the RUNBOOK's standing footnote).
- **After:** re-verified → **`inactive`** (exit 3). This spike changed nothing about serving
  posture; the GPU was never touched (running seats identical before and after).

## R2.7 Recommendation to the coordinator

**WALL — do not schedule the pilot or the full run.** But this is the smallest wall yet: a
**one-line path-resolution fix** in `checkout_scoped_file_map` (absolutize the worktree path so git
— which runs with `cwd=corpus_repo` — places it in the factory scratch, not inside the read-only
corpus repo). That single fix (a) lets all 13 discovered tasks yield a real file map instead of
skipping, and (b) closes the venue-rule breach it currently causes. After it lands, re-run THIS
spike: the **regenerator interpreter bridge** (`SubprocessBridgeRegenerator` → `qav_regenerate_bridge.py`
under `interpreters.guardkit`) gets its first real exercise — it was round 1's wall 2 and has still
never been reached — and only then do the teacher + coach GPU legs light up and the §3 projection
becomes measurable. Everything upstream is green: discovery + the exclusion law are correct and
fast, both seats reachable, keepalive posture safe, the 4 gold negatives validate clean.

---

# ROUND 3 (post path-fix) — 2026-07-20 (GPU freed by Rich)

> **VERDICT: THE FIRST MODEL-ERA ROW LANDED — machinery GREEN end to end, but the row is
> evidentially DEGENERATE.** The path fix (`14a3190`) cleared round 2's wall: a discovered
> task survived to injection, the regenerator interpreter bridge (round 1's wall 2) ran for
> real under guardkit's venv, **both GPU legs fired** (gpt-oss-120b loaded+generated, then
> coach-ft-v3 loaded+accepted), and 1 train row was written, schema-valid, contamination-pass,
> with zero venue debris. Total wall **113.6 s**. BUT the bundle inside that row is nearly
> all-null: `gathering_status="partial_exception"`, `gathering_error="missing_results: Task-work
> results not found at …/R-CONTROL-noop/.guardkit/autobuild/TASK-QAWE-001/task_work_r…"` — the
> approved sha `799cefd0` has **no `.guardkit/archive/` at all** and no QAWE run evidence in-tree
> (verified by `git ls-tree`); the artifact gather_evidence wants exists only at guardkit HEAD
> (`.guardkit/archive/FEAT-C332/run1-artifacts-TASK-QAWE-001/task_work_results.json`). The
> teacher approved and the coach accepted an evidence-empty green bundle. **Machinery proven;
> row not training-grade. Not pilot-ready — one more scoped wiring item (below).**

- Operator: SPIKE operator (Fable), round 3, authorized seat use (Rich freed the GPU).
- Repo HEAD at spike: `14a3190` (the wiring `f75a147` + the coordinator's worktree-path
  absolutization fix; suite 2394 green).
- Log: `run_logs/qav_spike_r3_20260720-173720.log` (uncommitted, run_logs convention).
- Single attempt, verbatim RUNBOOK command (`--limit 1`, `PYTHONPATH=src`,
  `OPENAI_API_KEY=local`, factory `.venv` python), nohup into `run_logs/`, actively polled.

## R3.1 What ran and what it produced

Driver banner: `mode=seeded_defect limit=1 out=output/qa-verifier teacher=gpt-oss-120b
corpus=['forge', 'guardkit', 'study_tutor']`. Clean completion (`DONE` + summary JSON;
process exit observed 17:39:18).

`DONE seeded_code=0 control=1 seeded_bundle=0 harvest=0 gold=4 teacher_refused=0
coach_rejected=0 cue_rejected=0 train=1 eval_qav=4` · `anchor_skipped=11`.

Shape explained: on the first discovered task (guardkit/FEAT-C332/TASK-QAWE-001@`799cefd0`)
**all 11 weighted reject-recipes anchor-skipped** (`AnchorNotFound` against its file map), then
the seeded-control no-op ran the identical machinery — worktree materialize → regen bridge →
teacher → coach — wrote the approve row, and `--limit 1` returned. The emitted row:
`generation_mode=seeded_code`, `injection_recipe=R-CONTROL-noop`, label
`{"verdict": "approve", "findings": [], "ground_truth_source": "seeded"}`.

## R3.2 Measured wall-times — per leg, cross-checked

| Leg | Measured |
|---|---|
| **Total wall** | **113.6 s** (17:37:20.68 → `DONE` 17:39:14.32) |
| discovery (record scan) | 2.2 s (→17:37:22.89; 13 included / 71 excluded) |
| injection sweep (11 anchor-skips) + file-map + control worktree materialize | ~2.4 s (→17:37:25.31) |
| **regenerate leg** (bridge subprocess, guardkit venv) | **~0.9 s** (17:37:25.31 → ~17:37:26.2; corroborated by the scratch-dir cleanup mtime 17:37:26.23) — **degenerate**: missing_results short-circuit, no real pytest work (see R3.3) |
| **teacher leg** (gpt-oss-120b) | **82.30 s** — llama-swap-measured request duration (`POST /v1/chat/completions 200`, 2968 B), **including the cold load** (matrix `evict=[embed]`, health check :5810 passed) |
| **coach leg** (coach-ft-v3) | **22.52 s** — llama-swap-measured (`POST 200`, 1245 B), **including its cold load** (matrix `evict=[gpt-oss-120b]`, health :5801 passed) |
| row write → final writes | train.jsonl 17:39:11.06; gold re-emit + both manifests + `DONE` by 17:39:14.32 (~3.3 s) |

Cross-check: regen-end ~17:37:26.2 + 82.30 + 22.52 = 17:39:11.0 ≈ train.jsonl mtime
17:39:11.06 — the three legs tile the span to ~0.1 s.

**Serving-posture finding (load-bearing for the full run):** the llama-swap matrix sets make
the two seats mutually evicting — the teacher load evicted `embed`, then **the coach load
evicted the teacher**. The driver alternates teacher→coach per row, so at volume every row
pays BOTH cold loads (the measured 82.3/22.5 are this thrash regime, not warm generation).
Post-spike residents: `coach-ft-v3, parakeet, qwen3-tts` (`embed` swapped out; llama-swap
auto-heals it on next request). Batch the legs (all teacher calls, then all coach) or give the
two seats a co-resident matrix set, or the projection below is the floor.

## R3.3 The row — validation PASS, evidence DEGENERATE

- **Contracts (`qav.contracts` validate_row + extract_bundle + extract_label, run live):**
  train.jsonl **1/1 valid** · eval_qav.jsonl **4/4 valid** · rejected.jsonl empty. Layout per
  contract: train/eval/rejected + `.bak` churn (round-2 originals preserved) + manifest at both
  paths (byte-identical, sha `8d283fdb…`); eval_qav.jsonl **byte-identical to round 2**
  (deterministic gold rebuild).
- **Manifest contamination embed:** `status="pass"`, real method recorded (row_id intersection
  + sibling-variant split-straddle + gold-negative source exclusion), intersection 0;
  `factory_sha="14a3190"`; counts correct (`seeded_code=1`, approve share 1.0).
- **BUT the bundle is evidence-empty:** `gathering_status="partial_exception"`,
  `gathering_error="missing_results: …"`; tests/coverage/quality_gates/wiring/stub_scan etc.
  all null; only honesty (score 1.0 over zero resolved paths), profile_name, task_type carry
  values. Root cause verified in guardkit: at `799cefd0` there is **no `.guardkit/archive/`**
  and `.guardkit/autobuild/` holds only unrelated TASK-REV-HMIG files; TASK-QAWE-001 exists at
  that sha only as `tasks/completed/…md`. The run record gather_evidence needs lives at HEAD:
  `.guardkit/archive/FEAT-C332/run1-artifacts-TASK-QAWE-001/task_work_results.json`. A verdict
  model must never learn "missing evidence → approve"; this row is not training-grade.

## R3.4 Projection — first honest numbers, with named caveats

Measured model-touching row time (as-measured regime): regen 0.9 + teacher 82.3 + coach 22.5
+ ~2.5 s row overhead ≈ **108 s ≈ 1.8 min/row**. Against GOAL.md Phase-1 volumes (§3 above,
~500–800 model-touching rows):

- **500 rows × 108 s ≈ 15.0 h** · **800 rows × 108 s ≈ 24.0 h** (harvest + gold excluded — no
  model legs, proven cheap).

Caveats that move this number: (a) it is the **swap-thrash regime** — warm-leg cost is
unknowable from one sample (the 82.3 s bundles load+generation); batching/co-residency cuts it,
re-measure at pilot; (b) regen 0.9 s is the **degenerate short-circuit** — real evidence
regeneration after the archive-materialize fix will cost more (round 1's "pytest-dominant"
prediction may yet return); (c) **anchor hit-rate**: 11/11 recipes skipped on this task — if
that generalizes across the 13 tasks, the seeded reject-side volume (500) is unreachable from
this corpus without recipe/anchor work; the pilot must log the rate per task.

## R3.5 Venue watch + keepalive (found-state discipline held)

- **Corpus repos CLEAN** — round 2's breach class did not recur: no `output/` dir in guardkit,
  study-tutor, or forge; worktree counts at baseline (8/2/1); `git status` unchanged from
  pre-spike (pre-existing unrelated dirt only). The scratch worktrees landed inside the factory
  (`output/qa-verifier/_scratch/…`, gitignored) and were removed after regen; only empty dir
  skeletons remain factory-side.
- **Keepalive:** `systemctl is-active llama-swap-keepalive.timer` → **`inactive`** (exit 3)
  before AND after — found-state preserved, **not re-armed** (the parker's call; RUNBOOK
  footnote transfers unchanged).

## R3.6 Recommendation to the coordinator

**Machinery GREEN, data RED — do not schedule the pilot on this row shape.** The spike's three
original walls are all cleared and the whole chain is proven live (discovery → injection →
bridge → teacher GPU → coach GPU → validated row → contamination-pass manifest → clean venue).
The remaining scoped wiring item: **materialize the archived run record (guardkit-HEAD
`.guardkit/archive/<feature>/…/task_work_results.json` and siblings) into the scratch worktree's
`.guardkit/autobuild/<task>/` before gather_evidence**, and add a loudness law — a bundle with
`gathering_error`/`partial_exception` must be rejected or quarantined, never silently approved
into train (this run proved teacher+coach both wave it through). Decide the serving posture
(batched legs vs co-resident matrix set) before the full run, else ~15–24 h is the floor. Then
re-run THIS spike: expect a real (slower) regen leg and the first training-grade row, and
re-feed §3/R3.4 with the warm numbers.

---

# ROUND 4 (spike + pilot) — 2026-07-20 (GPU freed by Rich)

> **VERDICT: THE FIRST TRAINING-GRADE ROW LANDED (spike) AND THE PILOT RAN THE ENTIRE
> ADDRESSABLE CORPUS — machinery is fully GREEN, but the corpus+recipe state cannot fill the
> Phase-1 targets.** The round-3 poison-path fix (`ee1147e` — materialize the HEAD autobuild
> run-record into each worktree + an evidence-empty pre-gate) cleared round 3's degenerate-row
> wall: the spike's row now carries a **real evidence-bearing bundle** (`gathering_status =
> partial_gate_abort`, `gathering_error = null`, real `tests`/`quality_gates`/`honesty`/
> `coverage_details`/`plan_audit`), the teacher reasons over those real fields, and it is
> contract-valid + contamination-pass. The pilot (`--limit 10`) then exposed the **binding
> constraint, and it is NOT GPU time — it is corpus addressability**: of 13 discovered tasks
> only **3 are processable** (10 SKIP'd — no materializable HEAD run-record), and across those 3
> the **anchor hit-rate is 0/33 (0%)** — every reject recipe anchor-skips, so **zero seeded-reject
> rows are producible from this corpus.** All output is approve-side green controls. **Machinery
> proven training-grade; the full run is NOT recommended until the anchor/recipe + HEAD-record
> lanes land.**

- Operator: SPIKE+PILOT operator (Fable), round 4, authorized seat use (Rich).
- Repo HEAD: `ee1147e` (round-3 poison-path fix: HEAD run-record materialization + evidence-empty
  pre-gate).
- Logs (uncommitted, run_logs convention): spike `run_logs/qav_spike_r4_20260720-180938.log`;
  pilot `run_logs/qav_pilot_r4_20260720-181416.log`. Per-leg GPU durations cross-read from
  `/opt/llama-swap/logs/llama-swap.log`.

## R4.1 SPIKE (`--limit 1`) — training-grade at last

Verbatim RUNBOOK command (`PYTHONPATH=src`, `OPENAI_API_KEY=local`, factory `.venv`, nohup +
active poll). Clean completion rc=0: `DONE seeded_code=0 control=1 … evidence_empty_rejected=0
train=1 eval_qav=4 · anchor_skipped=11`. Same **shape** as round 3 (guardkit/TASK-QAWE-001, all
11 reject recipes anchor-skip, the R-CONTROL-noop green rides through), but the **substance is
now real**:

- **Bundle is EVIDENCE-BEARING, not degenerate.** `gathering_status = "partial_gate_abort"`
  (an evidence-**bearing** early stop per the RUNBOOK — NOT round-3's evidence-empty
  `partial_exception`), `gathering_error = null`. Populated real fields: `tests`
  (tests_failed=0, tests_passed=true), `quality_gates` (9 flags), `honesty` (score 1.0 with
  real `resolved_paths` → `tasks/completed/TASK-QAWE-001-…md`), `coverage_details` (6),
  `plan_audit` (12), `advisory_issues` (2). The HEAD-record materialization fix worked.
- **Teacher rationale reasons over the real bundle** — cites the honesty score, reads the
  `partial_gate_abort` nulls as *absent evidence not failures*, notes the only issues are
  advisory/substrate-level (not the Player's code) → verdict `approve`, findings `[]`. `<think>`
  present, 4595 B response.
- **Contract + contamination:** train 1/1 valid, eval 4/4 valid, `CORPUS OK`; manifest
  `contamination_check.status = pass`; standalone gate `VERDICT: PASS`.

**Spike per-leg (cold-thrash regime, `llama-swap`-measured):** total wall **112.3 s**
(18:09:38.8 → 18:11:31.1) · discovery 2.2 s · regen bridge (real gather_evidence, guardkit venv)
**~1.9 s** · teacher gpt-oss-120b **82.28 s** cold (evict=[coach-ft-v3]) · coach coach-ft-v3
**23.92 s** cold (evict=[gpt-oss-120b]) · ~2 s finalize.

## R4.2 PILOT (`--limit 10`) — ran the WHOLE addressable corpus (cap never binding)

Clean completion rc=0: `DONE seeded_code=0 control=3 … teacher_refused=0 coach_rejected=0
cue_rejected=0 evidence_empty_rejected=0 schema_rejected=0 anchor_skipped=33 train=2
eval_qav=5`. The `--limit 10` cap was **never reached** — the run **exhausted the processable
corpus at 3 tasks**, so this is the full-corpus census for the green side, not a capped sample.

**Task census (13 discovered → 3 processable):**

- **10 SKIP'd** at HEAD-record materialization — no `task_work_results.json` under
  `.guardkit/autobuild` or `.guardkit/archive/<feature>` at the corpus HEAD, so authentic
  evidence cannot be reconstructed (excluded, never fabricated): guardkit TASK-BDDW-002,
  TASK-QAWE-003, TASK-QAWE-004; study_tutor TASK-PRV-001…007.
- **3 processable** (all guardkit): TASK-QAWE-001, TASK-QAWE-002, TASK-BDDW-001.

**Anchor hit-rate = 0/33 (0.0%).** On every one of the 3 processable tasks all 11 reject recipes
anchor-skipped (11×3 = 33). Round 3's 0/11 was **not a one-task fluke — it is systemic**: with
the current recipe/anchor set, **no seeded-reject row is producible from this corpus.** Every
emitted row is an approve-side R-CONTROL-noop green.

**Row census / training-grade (all contract-valid, 7/7):** 3 control rows produced (2→train,
1→eval holdout by the 0.15 split), all **EVIDENCE-BEARING + training-grade** (`partial_gate_abort`,
real fields, teacher `<think>` present); 4 gold negatives → eval. `rejected.jsonl` empty. **0
degenerate, 0 coach-rejected, 0 evidence-empty-rejected.** Manifest: `by_verdict` approve 2 /
reject 0, all `seeded_code`, `approve_share` 1.0, contamination **pass**, `visibility =
private (DF-008)`, `factory_sha = ee1147e`.

**Pilot per-row walls** (REGEN-bridge timestamps): QAWE-001 101 s · QAWE-002 111 s · BDDW-001
105 s → **avg ~105.7 s/model-touching row.** Total pilot wall **~5.5 min** (18:14:16 → 18:19:45).
**Per-leg (all COLD — swap-thrash held every row, no warm legs):** teacher 75.2 / 87.0 / 81.7 s
(avg **81.3 s**) · coach 23.7 / 21.9 / 21.4 s (avg **22.3 s**) · regen ~2 s. The teacher↔coach
mutual eviction (each load evicts the other) fires on every row exactly as round 3 predicted.

## R4.3 REVISED PROJECTION — the corpus, not the clock, is the wall

**Measured row-rate** (cold-thrash regime, unchanged from round 3): ~106 s/model-touching row.
Against the GOAL.md Phase-1 model-touching volume (~500–800 rows) this is the **same 15–24 h
floor** (500×106 s ≈ 14.7 h; 800×106 s ≈ 23.6 h; harvest + gold excluded — no model legs).
*Serving-posture caveat (unchanged, and load-bearing):* ~103 s of each 106 s is the two cold
loads; batching the legs (all teacher, then all coach) or a co-resident matrix set would remove
them, plausibly cutting to a few hours — but warm-leg cost was **never observed** (the driver
still alternates, both seats cold every row). This remains a serving decision, not measured.

**BUT the row-rate projection is moot, because the corpus cannot fill those volumes.** The pilot
ran the entire addressable corpus and the honest full-run yield at today's state is:

- **Seeded-reject rows: ~0.** Anchor hit-rate 0/33 → the 500-row reject target (DC-03 200 +
  DC-05/08/14 75 each + other 75) is **UNREACHABLE** with the current recipes/anchors.
- **Seeded-approve (green control) rows: ~3.** Only 3 of 13 discovered tasks materialize a HEAD
  record; each yields one control green.
- So a **full run today ≈ 3 seeded rows (approve-only) + 4 gold + harvest (if wired)** —
  ~two orders of magnitude below the ~1000-row Phase-1 target. **The binding constraint is corpus
  addressability (anchors miss 100 % + 77 % of tasks lack a HEAD record), not GPU time.**

## R4.4 Venue watch + keepalive (found-state discipline held)

- **Corpus repos CLEAN — no breach.** guardkit 8 worktrees / no `output/` dir / status
  unchanged; study-tutor 2 / none / unchanged; forge 1 / none / unchanged (baselines captured
  pre-spike, re-verified post-pilot). Factory `output/qa-verifier/_scratch` empty (per-row
  cleanup held). Scratch worktrees landed factory-side (gitignored), not inside the corpus repos.
- **Keepalive `inactive` before AND after** (exit 3) — the parker's found-state, preserved,
  **not re-armed** (the parker's call; RUNBOOK footnote — re-read the keepalive probe list and
  the coach-ft-v3 allowlist before re-enabling — transfers unchanged). GPU touched only for the
  spike+pilot legs; post-run residents `coach-ft-v3, parakeet, qwen3-tts` (gpt-oss auto-evicted),
  llama-swap auto-heals `embed` on next request.

## R4.5 Recommendation to the coordinator

**Machinery GREEN + training-grade PROVEN — do NOT launch the full run yet.** The spike produced
the first training-grade row and the pilot cleared every quality gate (contract 7/7, contamination
pass, zero degenerate/rejected, clean venue). But a full run against today's corpus reproduces
only ~3 approve-side green rows — it cannot build the Phase-1 dataset. **Two build lanes gate a
useful full run, and both are corpus/recipe work, not engine work:**

1. **ANCHOR / RECIPE lane (the harder, higher-value one).** All 11 reject recipes anchor-miss
   100 % on the 3 processable guardkit tasks. Either the recipe anchors must be rewritten to match
   the source shapes these repos actually contain, or discovery must reach a much broader,
   anchor-compatible task set. Without reject rows there is **no reject side to the dataset** —
   the whole point of the seeded-defect corpus.
2. **HEAD-RECORD COVERAGE lane.** 10 of 13 discovered tasks (all study_tutor PRV-00x + several
   guardkit) are SKIP'd because no `task_work_results.json` exists at HEAD to reconstruct from.
   Either archive those records into the corpus repos or widen the discovery record search.

Decide the **serving posture** (batched legs vs co-resident matrix) before any eventual full run
so the ~15–24 h cold-thrash floor doesn't bind — but that is downstream of the two corpus lanes.
Re-run THIS spike+pilot after each lane lands to re-measure the anchor hit-rate and the reject/
approve census; the R4.3 arithmetic is ready to receive them.
