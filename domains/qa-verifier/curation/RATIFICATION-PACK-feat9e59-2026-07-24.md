# Ratification pack — the stranded api_test batch (Option B) — 2026-07-24

## The one-minute version

You are being asked to ratify **9 task approvals** (plus 2 optional with named caveats), riding
**three real merge commits** that are already ancestors of api_test's main. Signing converts
their stranded run records into training material the factory can legally use. What it buys the
v4 tune, measured: the **pure-shape vacancy cohort** — the exact axis v3 failed on — grows from
**3 tasks / 9 variants / 1 repo** to **~10–12 tasks / ~16–27 variants / 2 repos**, including
**two held-out eval-side spines** (DB-005, DB-006). This is the difference between v4 betting
on its thinnest plank and v4 reinforcing it. **9 of the 20 tasks are deliberately NOT in the
approve list** — three false-green smells, one synthetic record, four tracker contradictions,
one approved-but-never-merged — each named below. Not batch-approving those is the false-green
law working, not caution theatre.

**Your act:** approve Table A as a batch (say "approve batch A", or strike rows); optionally
add Table B's two caveated rows; Table C needs no action (it documents what stays out and why).
Everything after that is my work, listed at the end.

## Table A — recommended approvals (9, rule A1-T)

| task | feature → ratified sha | the evidence you're signing off | vacancy value |
|---|---|---|---|
| TASK-DB-001 | FEAT-947C → `94249c5` | approved + merged; 83/0 tests, cov 85%; caveat: coach's independent run skipped | spine (train) |
| TASK-DB-005 | FEAT-947C → `94249c5` | approved + merged; direct-mode, 6/6 ACs, 1/0 tests, gates green | **spine (EVAL)** — cleanest record in batch |
| TASK-DB-006 | FEAT-947C → `94249c5` | approved + merged; 17/0 tests, cov 93%, 6/6 ACs | **spine (EVAL)** |
| TASK-DB-007 | FEAT-947C → `94249c5` | approved + merged; 13/0 tests green; composite verdict null | spine (train) |
| TASK-DB-008 | FEAT-947C → `94249c5` | approved + merged; 13/0 tests green; composite verdict null | spine (train) |
| TASK-ADOC-002 | FEAT-B2D7 → `98b5930` | approved + merged; 25/0 tests, cov 98% | spine (train) |
| TASK-ADOC-003 | FEAT-B2D7 → `98b5930` | approved + merged; 30/0 tests, cov 98% | record/harvest only (no source files in its lists) |
| TASK-C086 | FEAT-EC3C → `562daf8` | approved + merged; 9/0 tests, cov 94% | record/harvest only |
| TASK-ED5F | FEAT-EC3C → `562daf8` | approved + merged; 12/0 tests, cov 97% | spine (train) |

## Table B — optional, each needs your explicit caveat acceptance (2)

| task | the caveat you'd be accepting |
|---|---|
| TASK-ADOC-001 | gates green + cov 98% but **zero counted tests** — a zero-count green under an approve |
| TASK-70ED | zero-count green AND its source files are empty scaffolding — weakest spine on offer |

## Table C — stays OUT, no action needed (9, rule Q-TRK: queued, never silently labeled)

- **TASK-DB-004 — strongest false-green in the batch**: coach approved while the record says
  0 passed / **1 FAILED**, completed=false, and the skipped independent run was logged as
  passing. The FMDR class exactly.
- **TASK-DB-002, TASK-DB-003** — approved with completed=false, 0/0 tests, null gates.
- **TASK-LOG-001..005 — the whole family**: approvals exist only in record dirs while the
  committed tracker says pending/failed; no merge or decision commit exists (checkpoints
  committed straight to main after a fixes commit — the manual-salvage shape the discovery
  honesty law was written against). **TASK-LOG-004 additionally carries `_synthetic=true` —
  hard-excluded from either split forever.**
- **TASK-VER-001** — the richest record, but approved-and-never-merged (its own tracker commit
  says so), the code at HEAD is a different feature's implementation, and its task id collides
  with a later machine-planned task.

## What happens after you sign (my work, in order, all receipted)

1. 20 rows into `harvest-outcomes.yaml` (A1-T approves with the three merge shas; Q-TRK queue
   rows with named reasons), citing this pack as the ratification artifact.
2. Record-store copies (the durability act — the stranded worktree is one `git worktree prune`
   from vanishing), preferring the git-tracked record dirs at main where they exist.
3. The api_test test-command pin (proposed: `pytest tests/ -q -p no:cacheprovider
   -p no:warnings`) — **spike-gated**: control-green at the ratified shas must be proven ×2
   before anything mints (the estate's own receipt warns of 8 pre-existing reds on a later
   base; if whole-suite green fails, the pin narrows per-recipe, the guardkit pattern).
4. Per-spine regeneration spikes (wiring populates? deterministic ×2? three-distinct-hashes?)
   — each spine that fails its spike is dropped loudly, never fudged.
5. Then the v4 overnight per plateau-card #3 option A's sequence, with the same stop-rule.

## Honest caps

Control-green at the ratified shas is unverified until step 3's spike (collect-only was clean:
238 tests, zero errors). The records' file lists carry hygiene residue (.pyc entries, absolute
paths into sibling worktrees) — harmless for reading, named as a scoping caveat for seeding.
Split sides are computed, not assumed: DB-005/DB-006 hash eval for the vacancy family;
everything else in Table A hashes train. Buckets, shapes, and evidence trails: the 3-counter
inspection of 2026-07-24 (workflow receipts in the session transcript; per-task detail
reproducible read-only from the records themselves).
