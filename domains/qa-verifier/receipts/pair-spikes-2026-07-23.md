# QAV v3 contrast-pair boundary spikes — NO-GO → v1.2 → GO (2026-07-23 night)

**Design:** `DESIGN-qav-v3-contrast-pairs-2026-07-23.md` (v1.1 → v1.2 in-flight) · **Harness:**
the record-family spike pattern (8369265 / guardkit-per-recipe-test-scope §4): real
`SubprocessBridgeRegenerator.from_config` on the shipped agent-config, records via
`load_task_work_record` (record-store + corpus autobuild), engine-exact
inject_control→materialize→regenerate→validate→scrub→hash order, both passes under
`flock -x /var/lock/llama-swap-keepalive.lock`, CPU only, zero model/GPU/fleet calls, corpus
repos read-only (detached /tmp worktrees, removed; zero leftovers), no frozen file touched.

## Round 1 — NO-GO (the spike's find, exactly what §7.2 exists for)

Regenerated control bundles **never carry `runtime_parity`**, and carry `wiring`/`bdd` only on
study_tutor record spines (record-replayed, not gathered, under the integration profile) — so
the three sever-a-populated-field recipes were ANCHOR-ABSENT corpus-wide on guardkit/jarvis
spines: `A-dc03` (⇒ the pair-atomic law banks ZERO attractor-cut pairs), `C-dc08` (⇒ zero
DC-08 rows), `CTRL-comp`. Everything that fired passed all laws: 14/14 distinct hashes,
×2 byte-identical, evidence_empty=None, validate_bundle PASS, cue_audit clean, shingle max
6 ≤ 7, split buckets exact, eval-row seq ~8% of the 20480 gate.

**The label-honesty rule underneath (now design §2 v1.2):** on a spine whose approve control
already has a field null, nulling cannot be a reject signal — the reject side must ADD
defect-bearing evidence. → `A-dc03` populates `wiring` with call-site defect evidence;
`C-dc08` populates a defect-bearing `bdd_authoring_sweep`; `CTRL-comp`/`CTRL-bdd` are their
healthy approve mates. Fix + independent re-coach: suite 2691 passed exit 0, frozen files
byte-untouched, label-honesty by construction (reject/approve sides always differ in
discriminating keys; 0 collisions across 5 spines).

## Round 2 — GO (all rebuilt surfaces + regression)

| Spike | Control | Sides (sha16, all ×2 byte-identical) | Verdict |
|---|---|---|---|
| Axis A · guardkit/QAWE-003 (None-wiring spine) | 8ab23738a5bbb25f | A-dc12 8702c8a42899abba · A-dc03 **9de2f9e089b96551 NEW-MINT** | PASS |
| Axis A+B reg · study_tutor/PRV-005 (dict-wiring) | 23baf88c333fdefd | A-dc12 a83e8f8e06f4657c · A-dc03 **b33aba5808689326** · B-dc14 5428f75c16aa3338 · B-dc12 a63e75d4a1d8f57b | PASS (B byte-stable vs round 1) |
| Axis C · guardkit/BDDW-002 | b4ccc18e30f70374 | C-dc08 **a66f5b51ecb3843e** (sweep authored=False, 4/5 undefined) · CTRL-bdd **1209c7b391e47ee6** (7/7 defined, approve) | PASS |
| C-dc03 reg · study_tutor/PRV-002 | 0680030945f01037 | C-dc03 8488ed1be2203553 | PASS (byte-stable) |
| **Eval cohort e2e · jarvis/JNB-001 (bucket 486 ⇒ eval)** | f7c0f9a6524c415d | A-dc12 3a58af2062be5380 · A-dc03 **d341bba7142b455b** · B-dc14 1d89934acdc39fd9 · B-dc12 eace62036cb56b2c · CTRL-audit eb4051825db3ecc4 · CTRL-comp **d134a7f0a0297384** · CTRL-tests 7a104fbafdbebbdd — 8 distinct | PASS |

Row gates 16/16 minted sides: evidence_empty_reason=None · validate_bundle PASS · cue_audit
clean. Shingle: max shared 8-gram run **6 ≤ 7** vs both frozen exam bodies incl. all new
populated-field prose (the 6-run is pre-existing schema-key adjacency, present in unmutated
controls). Split buckets ×10 unchanged (eval cohort 239/486/942/1323; BDDW-001 misses at
1538; both C cohorts wholly train). Seq budget: eval-side sides 7.8–8.6% of 20480.

**Honest caps standing:** no BDD-owning task hashes eval ⇒ no axis-C DC-08 eval rows this
cycle; the GN-1 pure bdd-null and GN-3 pure oracle-null shapes have no same-task pair
construction (design v1.2 names both). The pair-census sibling-parity check is a loud
receipt counter (`pair_census_orphans` + WARNING), not a crash — pair-atomic banking is the
real guarantee.

**GO issued for the corpus run** on the committed engine (this receipt's commit).
