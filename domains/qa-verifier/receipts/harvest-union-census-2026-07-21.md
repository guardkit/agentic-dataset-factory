# RECEIPT — QAV Harvest UNION census (GB10 + Mac) + ratified-outcomes DELTA (2026-07-21)

> Companion to `harvest-s1-census-2026-07-21.md` (the GB10 census + the labeling policy).
> This receipt unions the **Mac sweep** (`incoming/`, read-only evidence) into the GB10 82,
> then applies **THE RATIFIED POLICY (census §2, Rich 2026-07-21)** mechanically over the union
> to produce the committed data file `outcomes/harvest-outcomes-2026-07-21.yaml`.
> Nothing here writes to a corpus repo; `incoming/` is read-only and never committed.

## 0. One-minute version

| Question | GB10 census (07-21 AM) | **Union (GB10 + Mac)** |
|---|---|---|
| Harvestable final-turn bundles discovered | 82 | **82** (Mac adds 0) |
| New tasks contributed by the Mac | — | **0** |
| New bundles contributed by the Mac | — | **0** (all 58 Mac finals are byte-duplicates) |
| Same-task divergences (Mac vs GB10) | — | **0** |
| New *outcome records* mined from Mac merge summaries | — | **3** (FEAT-ATR, FEAT-PH1-002, FEAT-PH1-003) — none labelable |
| **Approve-labelable (consumable)** | 9 *(2 certain + 7 probable)* | **2** — the 7 "probable" PRV DISCONFIRMED |
| **Reject-labelable (consumable)** | 4 | **4** (unchanged; the gold negatives) |
| **Total consumable labels** | ~13 projected | **6 confirmed** (2 approve + 4 reject) |
| Queued / undecidable (never guessed) | 69 + escapes | **7 PRV + 7 PO-002 + 3 Mac-new features + A2/U1 + 79 outcome-less** |

**Headline: the Mac widened nothing labelable, and it closed the census's one open question the
wrong way for the count.** The PRV presence-confirm the census owed came back **NEGATIVE**, which
*removes* 7 speculative approves rather than adding rows. Confirmed labelable = **6**, down from the
census's projected ~13.

---

## 1. Union discovery — method + result

Method: the census's own `discover_bundles` semantics (final-turn per `(repo, task)`, key =
immediate-parent-dir-name) applied over the Mac tree, **reusing the census skip filter**
(`! */.claude/worktrees/*`) and the `(repo, task)` merge caveat. Dedup against the GB10 82 by
`(repo, task, content-hash)` (sha256 of the bundle bytes).

- **Mac sweep contents:** 147 `coach_evidence_turn_*.json` + **4** `merge_summary.json` + **0** gate
  histories, across 6 repos (`fleet-memory, forge, guardkit, jarvis, nats-core, study-tutor`).
- **Mac distinct `(repo, task)` finals:** 58.
- **Classification of all 58 vs GB10:**
  - **byte-duplicate: 58 / 58** — every Mac final-turn bundle is byte-identical to its GB10 final.
  - **same-task-divergent: 0** — including the two duplicate-layout traps below, which both resolved
    to byte-identical copies.
  - **NEW task: 0.**
- **Mac is a strict repo-subset of GB10.** The Mac lacks **24** `(repo, task)` the GB10 has:
  `api_test` (3), `guardkit` non-HARV features (10: ABL1×2, BDDW×2, QAV×6), `specialist-agent` (11).

### Duplicate-layout traps checked (both benign)
1. **jarvis `.guardkit/worktrees/FEAT-28FF/`** — the Mac carries a *second* copy of every
   `TASK-JNB-*` bundle inside a live `.guardkit` worktree (this is the Mac analogue of the GB10
   `.claude/worktrees` jarvis duplicate the census warned about; note it is under `.guardkit/`,
   which the `.claude/worktrees` skip does **not** remove). Both copies + the GB10 canonical are
   **byte-identical** → collapses to one byte-dup, no divergence.
2. **guardkit `docs/history/.../autobuild-evidence/` vs `.../autobuild-evidence-full/`** — HARV-002 /
   HARV-004 appear under two sibling dirs on the Mac; both byte-identical to the GB10 final.

---

## 2. Mac merge-summary mining — 3 new outcome records, 0 new labels

The 4 Mac merge summaries were mined for outcome records the GB10 census lacked. **3 are Mac-new**
(FEAT-PO-002 already existed on GB10). **None yields a labelable approve** — each fails A1's join.

| merge_summary (Mac) | New vs GB10? | Kind | Why not A1-approvable |
|---|---|---|---|
| guardkit **FEAT-ATR** | **new** | manual `/task-work`, "direct commits to main, no worktree, **no autobuild artefacts**" | no `decision:"approved"` field; **0** bundles for TASK-ATR-* anywhere |
| study-tutor **FEAT-PH1-002** | **new** | squash-merge; `tasks_merged` list only | no per-task decision; "per-task autobuild artifacts intentionally **not committed**"; **0** TASK-DSP-* bundles |
| study-tutor **FEAT-PH1-003** | **new** | squash-merge; `tasks_merged` list only | same; **0** TASK-DTL-* bundles |
| study-tutor **FEAT-PO-002** | already on GB10 | `autobuild:false`, reviewer-in-loop | **A3** — different approve semantics → QUEUED; **0** TASK-PO02-* bundles |

All four land in the `queued` section of the outcomes file as documented records, not labels.

---

## 3. The ratified policy applied over the union

Rules per **census §2, ratified by Rich 2026-07-21**. Labels come ONLY from committed records.

### A1 approves — **2** (was projected 9)
- **guardkit FEAT-E2CB `TASK-BDDW-001`, `TASK-BDDW-002`** — merge_summary `decision:"approved"`,
  no manual-fix, both bundles in the discovered 82 (and byte-present in the union). Provenance sha =
  the **FF merge sha `917bcef7`** (RATIFIED: merge-sha is the approve provenance sha; no per-task
  approved-sha source of record exists). Both are `ugly_green` → clear the ≥45% ugly-green floor.
- **PRV presence-confirm (the census owed this) = NEGATIVE.** FEAT-70A4's merge_summary lists
  `TASK-PRV-001..007` all `decision:"approved"`, but **zero** `coach_evidence_turn_*.json` exist for
  any `TASK-PRV` task — not on the GB10 corpus, not in the Mac sweep (only `tasks/completed/TASK-PRV-008/`
  as a doc dir). A1 requires the discovered final-turn bundle; the join **fails** → the 7 "probable"
  approves are **disconfirmed → QUEUED**, never guessed.

### R1 rejects — **4** (unchanged; the FEAT-EVAL-QAV holdout, `split: eval_qav`)
GN-1 SMP2-07 (DC-08, operator_caught, retro `54ab79fd`, reconstructed) · GN-2 SMP3-06 (DC-03,
operator_caught, retro `99bf79d5`, reconstructed) · GN-3 QAV-005 (DC-03, merge_review_caught,
sha `888906f2`, **verbatim** bundle on disk) · GN-4 DD4F (DC-03, merge_review_caught, fix sha
`1ad98c0`, reconstructed) — **U2: DD4F task-id stays FLAGGED-BLANK** (never synthesised).

### The other calls
- **A2** approved-plus-manual-fix (FEAT-C332 QAWE-002/004) → **EXCLUDED** (not `coach_correct`; also
  not in the discovered set). Queued.
- **A3** FEAT-PO-002 → **QUEUED** (autobuild:false; now on disk from both trees).
- **U1** FEAT-FMDR-004 → **QUEUED** (recipe-seed only, no committed retro to join).
- **U4** the outcome-less discovered bundles → **UNLABELED**; `harvest()` skips them; Rich curates.

---

## 4. Updated achievable-set arithmetic (frozen balance laws)

Consumable labels after the union: **2 approve + 4 reject**. Frozen manifest laws:
`approve_share ≤ 0.60` (approves ≤ 1.5× rejects); ugly-green ≥ 45% of approves; gold-negative source
tasks excluded from `train` (contamination law).

- **Whole-corpus achievable set: 6 rows** (4 reject + 2 approve). `approve_share = 2/6 = 0.33 ≤ 0.60`
  ✓; ugly-green floor met (2/2). **This is now APPROVE-bound, not reject-bound** — the 0.60 law would
  permit 6 approves against 4 rejects, but only **2 approves exist**. (Census had it at a 10-row
  reject-bound ceiling; the PRV disconfirm flips the binding side and lowers the ceiling to 6.)
- **Balanced 50/50 whole-corpus: 4 rows** (2 reject + 2 approve) — down from the census's 8.
- **Balanced *train* manifest: still NOT achievable.** All 4 rejects are gold-negative `eval_qav`
  holdout; the contamination law keeps their source tasks out of `train`. Train side = **2 approve,
  0 reject** → a balanced train split would be approve-only (`approve_share = 1.0`), which the band
  correctly refuses. The union does not change this — it removes approves, it adds no rejects.

**Net delta from the Mac:** +0 bundles, +0 tasks, +0 labels, +3 documented-but-unlabelable outcome
records; and it resolves the census's PRV question to **−7 speculative approves**. The reject side —
the true binding constraint for a trainable balanced set — is **unchanged and still zero on the
train split**. The corpus-blocked reality (round-4 spike) stands: only the S3 seeded lanes or a
hand-curation pass on the 79 outcome-less finals can materialise train-side rejects.

---

## 5. Provenance / footguns carried forward
- `incoming/` is READ-ONLY evidence, **never committed** (one-line `.gitignore` entry added as the
  single permitted ignore edit this lane).
- The GB10 82 source of record — `run_logs/qav-harvest-census-2026-07-21.jsonl` — stays **untracked**
  (`run_logs/*.jsonl` is not gitignored; do not commit it).
- Any harvest run over the union must reuse the census's `.claude/worktrees` skip **and** be aware
  the Mac's jarvis duplicate lives under `.guardkit/worktrees/` (the skip does not remove it; the
  `(repo,task)` final-turn dedup does — but the rglob tie-break is undefined between byte-identical
  copies, which here is harmless).
