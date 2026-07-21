# Receipt — REJECT-SIDE RE-SPIKE (2026-07-21)

> **THE GATE — MET.** The rewritten anchor set (HEAD `9c212db`, round-4 0/33 cure) now produces
> **REAL SEEDED REJECT ROWS.** A live `seeded_defect` run over the first 3 discovered tasks
> emitted **2 seeded_code reject rows** (teacher-authored `<think>`, coach-gate passed, 6/6
> contract-valid) plus the **4 gold negatives** — 6 reject rows banked, every one `verdict:reject`,
> every one VALID. Anchor hit-rate went **0/33 → 18/33** (the 15 skips are exactly the recorded
> EXPECTED-MISS recipes). No teacher refusals, no coach rejections, no schema/cue/evidence-empty
> rejects, **no coach 500s and no eviction** — the `qav-coach` unique-alias co-residency held.

---

## The one-minute version

Round-4 measured anchor hit-rate **0/33** — all 11 reject recipes anchor-skipped, zero reject
rows. HEAD `9c212db` rewrote the anchor strings against the real corpus shapes (recipe ids /
families / dc_classes / the mutation machinery byte-frozen). This re-spike ran the **real driver**
in `seeded_defect` mode with `--limit 3` to answer one question: does the rewrite actually plant
and emit reject rows in a live run, not just in unit fixtures? **It does.** Two distinct
seeded_code reject rows survived the full pipeline (inject → real bundle regen via guardkit
`gather_evidence` → teacher rationale → coach gate → content-addressed write), both DC-08 /
`R-ABSENT-junit`, alongside the 4 always-eval gold negatives. The approve side is empty at this
limit (control greens deduped to zero) — the manifest records that honestly as an advisory
balance FAIL. The reject side is **real and non-zero for the first time.**

## Run parameters

| | |
|---|---|
| driver | `domains/qa-verifier/run_qav_generation.py` |
| invocation | `PYTHONPATH=src .venv/bin/python … --mode seeded_defect --limit 3` |
| factory sha | `9c212db` (anchor-rewrite HEAD; round-4 0/33 cure) |
| launched | 2026-07-21 13:25:50 BST · nohup, active short-polls (~80–90s), not harness-tracked |
| finished | 2026-07-21 13:41:01 BST · **~15m11s wall** (inside the 60-min wall; exited clean) |
| log | `run_logs/reject-side-respike-2026-07-21.log` |
| fleet | `:9000` up throughout; teacher `gpt-oss-120b`, coach `qav-coach` (co-resident `qav` set) |
| keepalive | verified **inactive** at start; **not re-armed** (per instruction) |
| s2s app | untouched; no eviction observed |

## The headline — reject rows produced

**6 reject rows banked, all `verdict:reject`, all 6/6 contract-valid:**

| split | mode | recipe | dc_class | repo / task | sha | row_id |
|---|---|---|---|---|---|---|
| train | seeded_code | R-ABSENT-junit | DC-08 | guardkit / TASK-QAWE-002 | 799cefd0 | qav-af89e9bb3d485499 |
| eval_qav | seeded_code | R-ABSENT-junit | DC-08 | guardkit / TASK-QAWE-001 | 799cefd0 | qav-a73b879e7e74bd93 |
| eval_qav | gold_negative | — | DC-08 | study-tutor / TASK-SMP2-07 | 54ab79fd | qav-43c8de8edc8d812b |
| eval_qav | gold_negative | — | DC-03 | study-tutor / TASK-SMP3-06 | 99bf79d5 | qav-f9f7f8f886c64b03 |
| eval_qav | gold_negative | — | DC-03 | guardkit / TASK-QAV-005 | 888906f2 | qav-0201caff2db7a8cd |
| eval_qav | gold_negative | — | DC-03 | forge / FEAT-DD4F | 1ad98c0 | qav-13f964bbaead7fd1 |

**vs the harvest run (2026-07-21): 0 train / 0 eval / 0 rejected. This run: reject side is REAL.**

## Anchor hit-rate delta (0/33 → 18/33)

`--limit 3` took the first 3 discovered tasks — **guardkit TASK-QAWE-001 / -002 / -003** (all @
`799cefd0`). Discovery: **13 included, 71 excluded** (exclusion law loud on every spec-only /
no-approved-sha feature).

- **11 reject recipes × 3 tasks = 33 recipe-task combos.**
- **`anchor_skipped = 15`** — exactly the recorded EXPECTED-MISS set (`R-DC03-kwargs`,
  `R-DC08-undefstep`, `R-DC08-pendmask`, `R-DC12-planvisible`, `R-DC14-narrative`) × 3 tasks.
  Honest misses, not force-matched; `AnchorNotFound` stayed loud (a `continue`, never a silent
  no-op).
- **Anchored (hit) = 18/33** — the 6 HIT recipes (`R-ABSENT-junit`, `R-DC03-callsite`,
  `R-DC03-mockseam`, `R-DC03-producer`, `R-DC05-skipguard`, `R-DC05-sysmod`) planted on all 3
  tasks and each drove a **real** guardkit `gather_evidence` regen leg.

**Delta: 0/33 anchored (round-4) → 18/33 anchored (this run). The cure holds on a live run, and it
holds on TASK-QAWE-003 — a task that was NOT in the anchor-study set (only -001/-002 were), so this
is anchor generalization, not just a fit to the two studied trees.**

## Rows train / eval / rejected + why 18 plants → 2 unique reject rows

Driver summary (`summary.__dict__`, verbatim):

```
seeded_code_written=2  seeded_control_written=0  seeded_bundle_written=0
gold_negatives_written=4  harvest_written=0
teacher_refused=0  coach_rejected=0  cue_rejected=0  evidence_empty_rejected=0  schema_rejected=0
anchor_skipped=15  gold_source_skipped=0  deduped=38
train=1  eval_qav=5  rejected=0
manifest_finalized=True  balance_ok=False  approve_share=0.0
```

- **train = 1** (one seeded_code reject) · **eval_qav = 5** (one seeded_code reject + 4 golds) ·
  **rejected = 0** (nothing discarded by the coach/cue/schema gates — quality gates saw zero bad
  rows, not zero rows).
- **`deduped = 38`** is the story behind 18 anchored plants collapsing to 2 unique reject rows.
  `row_id` is **content-addressed on the rendered user-message bundle** (`contracts.row_id`). The
  3 QAWE tasks @ the same sha render near-identical evidence bundles, so different mutations on
  the same task — and even the *same* recipe across the 3 sibling tasks — collide to the same
  `row_id` and dedup. Only `R-ABSENT-junit` on -001 and on -002 rendered distinct surviving
  bundles; QAWE-003's copy deduped. This is correct, honest de-duplication (it is exactly what
  keeps train/eval clean), **not** a plant failure — every one of the 18 legs planted and
  regenerated for real.
- **control = 0 → the balance FAIL.** The 3 no-op control greens deduped to zero the same way
  (identical rendered green bundle across the sibling tasks), so **no approve-side row banked**.

## Manifest verdict — honest, balance now has ONE side only

`domains/qa-verifier/manifests/qav-phase1-train.manifest.json` (finalized, `factory_sha 9c212db`):

- `by_verdict`: **approve 0, reject 1** · `by_dc_class`: DC-08 = 1 · `by_generation_mode`:
  seeded_code = 1 · `by_ground_truth_source`: seeded = 1.
- **`balance_report.approve_share = 0.0`** → **`MANIFEST BALANCE ADVISORY FAIL`** logged loudly:
  *"approve_share 0.00 outside 0.50±0.10; ugly_green share 0.00 < 0.45"* — **rows banked +
  manifest written honestly** (advisory, non-fatal, by design).
- **`contamination_check`: PASS** — row_id intersection 0, no sibling-variant split-straddle, no
  gold-source violations.
- Reject side is **no longer empty** (round-4 had neither side). The manifest now carries a real
  reject count; the approve side is 0 because control greens deduped out at `--limit 3`. Recorded
  as-is, not massaged.

## Per-leg times + co-residency

21 regen legs (18 anchored plants + 3 control no-ops). Per-leg wall (leg-start → next-leg-start;
the two 116s/143s outliers straddle the teacher-rationale GPU leg + task/finalize boundaries):

```
TASK-QAWE-001  R-ABSENT-junit 116s  R-DC03-callsite  30s  R-DC03-mockseam  61s  R-DC03-producer 92s
               R-DC05-skipguard 26s  R-DC05-sysmod    26s  R-CONTROL-noop   29s
TASK-QAWE-002  R-ABSENT-junit  22s  R-DC03-callsite  29s  R-DC03-mockseam  21s  R-DC03-producer 123s
               R-DC05-skipguard 21s  R-DC05-sysmod    18s  R-CONTROL-noop   20s
TASK-QAWE-003  R-ABSENT-junit  20s  R-DC03-callsite  20s  R-DC03-mockseam  24s  R-DC03-producer 23s
               R-DC05-skipguard 19s  R-DC05-sysmod    22s  R-CONTROL-noop  143s
legs=21  min=18s  max=143s  mean≈43s
```

**Co-residency held.** Zero `evict` / `500` / `connection` / `retry` / `unload` lines in the log.
The `qav-coach` unique-alias set (forces the co-resident `qav` llama-swap set, `gpt-oss-120b`
stays loaded) **cured the per-leg eviction thrash** that walled the 2026-07-21 harvest run (which
took 6× coach-500s → abort). `coach_rejected = 0`, `teacher_refused = 0`: every gate call
succeeded.

## 6/6-style contract validation on every emitted row

Ran `qav.contracts.validate_row` over all 6 banked rows (train + eval_qav): **all VALID-6/6**
(row_id content-addressed on the user message, schema/verdict/findings/provenance/split all
consistent). `rejected.jsonl` empty — nothing was schema/cue/evidence-rejected.

## Findings (honest, for the full run)

1. **Cure confirmed on a live run, and it generalizes** — anchors that were 0/33 now plant
   18/33, including on the unstudied TASK-QAWE-003. The 15 skips are precisely the recorded
   EXPECTED-MISS recipes.
2. **Row VOLUME comes from task BREADTH, not recipe count on sibling tasks.** Content-addressed
   dedup collapses same-task / sibling-task mutations that render identical evidence bundles
   (`deduped=38`; 18 plants → 2 unique). `--limit 3` landing on 3 near-clone QAWE tasks @ one sha
   is close to a worst case for row yield. The **full run over the 13 included tasks** (guardkit +
   study_tutor + forge, distinct trees) is where reject-row diversity will materialize — the
   recipe set is proven to plant; it now needs distinct source bundles to write against.
3. **The approve side needs its own breadth.** Control greens dedup the same way; at this limit
   they collapsed to 0 and the manifest balance advisory FAILed. Full-run breadth (and the
   seeded_bundle augmentation, capped 25%) is what populates the approve/ugly-green side — the
   balance advisory is expected to stay FAIL on any tiny same-sha slice and should be judged only
   on a full run.

## Artifacts + provenance

- `output/qa-verifier/train.jsonl` — 1 row · sha256 `e828960821fe7ac39b03e6a4361d8d99dfa6a23ea8429dfc500bd409bed3a97f`
- `output/qa-verifier/eval_qav.jsonl` — 5 rows (1 seeded_code reject + 4 golds)
- `output/qa-verifier/rejected.jsonl` — 0 rows
- `domains/qa-verifier/manifests/qav-phase1-train.manifest.json` — finalized, factory_sha `9c212db`
- `run_logs/reject-side-respike-2026-07-21.log` — full driver log
- Pre-run banked output (1 train + 5 eval from the harvest bank) snapshotted to the session
  scratchpad before the fresh-start `.bak` swap; also preserved one level in `output/qa-verifier/*.bak`.
- Datasets private (DF-008).
