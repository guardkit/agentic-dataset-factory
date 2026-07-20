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
