# QAV v3 contrast-pair corpus cycle — receipt (2026-07-23 23:49 → 2026-07-24 03:18)

**Engine:** `3348c63` (the pair engine, spikes GO — `pair-spikes-2026-07-23.md`) · **Posture:**
qav set (gpt-oss-120b teacher + qav-coach gate) warmed co-resident pre-launch, keepalive
flock-held (fresh holder), standing set freed first (memory pre-flight per the §8 wedge
lessons; swap peaked benign) · **Driver:** `run_qav_generation.py --config agent-config.yaml`,
log `run_logs/qav_gen_20260723-234913.log`, wall 3h29m, exit 0.

## The pair family's first production cycle

- **21 atomic pairs banked (42 sides), `pair_census_orphans=0`** — the sibling-parity receipt
  clean; **0 `pair_hash_collision`**; **8 sides dropped pair-atomically** (their sibling failed
  the gate — no lone side banked, the law working); `contrast_pair_capped=0` (budget 96 never
  bound).
- **84 pair rows banked** (47 reject + 37 approve controls = 44% controls, above the ≥40%
  proportion law): train 56 (A-dc12 6 · A-dc03 6 · B-dc14 7 · B-dc12 7 · C-dc08 2 · C-dc03 3 ·
  CTRL-audit 7 · CTRL-comp 8 · CTRL-tests 8 · CTRL-bdd 2) · **eval 28 — ALL FOUR eval-hash
  tasks (QAWE-004 / JNB-001 / JNB-008 / PRV-004) fired the full A+B+CTRL set** (4 × 7 recipes).
- Other gates this run: coach_rejected 5 · cue_rejected 1 · evidence_invariant 9 (incl. the
  weight-0 DC-05 protections firing as designed) · teacher_refused 0 · schema_rejected 0.

## HONEST CATCH — the harvest-mode miss, and the cure

The shipped `agent-config.yaml` has `mode: seeded_defect`; cycle 7 evidently ran with
`--mode both` on the CLI. This run was launched config-default, so **harvest never ran and the
fresh-start writer dropped cycle 7's 30 harvest rows** (22 train + 8 eval — real-world
coach_correct/merge_review labels, incl. eval's 4 organic DC-03 rejects). Cure, receipted here:
the 30 rows were merged back **byte-preserved from the run's own `.bak` files** (0 row_id
collisions verified) and the manifest rebuilt through the engine's `build_manifest` +
`validate_manifest` (the embedded contamination check re-ran: **pass**; dataset_id/created/
factory_sha kept as the run stamped them). No row content was authored or edited by hand.
Follow-up hygiene for the next cycle: run with `--mode both` (or set the yaml mode) — noted for
the runbook.

## The corpus of record (post-merge)

| | train | eval |
|---|---|---|
| rows | **335** | **52** |
| by mode | seeded_code 250 · seeded_bundle 63 · harvest 22 | seeded_bundle 28 · seeded_code 12 · harvest 8 · gold 4 |
| by class (train) | DC-12 82 · DC-14 64 · DC-03 36 · DC-08 10 · DC-05 4 · approve 139 | |
| **by class (eval)** | | **DC-12 8 (was 0) · DC-14 5 (was 1) · DC-03 13 · DC-08 4 · DC-05 4 · approve 18** |
| balance | approve_share **0.4149 IN-BAND** · ugly-green 0.9568 of approves | |

**C2 delivered:** the eval split now holds every attribution class the exam probes — the next
merged-gen gate and any held-out audit can finally see DC-12/DC-14 without train-member probes.
Class-boundary contrast now exists on BOTH sides of the split, same-spine, label-by-construction.

Artifacts: `output/qa-verifier/{train.jsonl,eval_qav.jsonl,manifest.json}` (DF-008 private,
never committed; `.bak` set = cycle 7 preserved) · tracked manifest copy updated in
`manifests/qav-phase1-train.manifest.json`. Next: staging (incl. the widened eval-split exam
crosscheck) → seq-20480 audit/filter → train v3 → gate → GGUF `qav-ft-v3` → the sealed-gate
re-exam (`RESULTS-qav-ft-v3`).
