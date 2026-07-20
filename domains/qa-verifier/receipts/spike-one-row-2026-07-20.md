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
