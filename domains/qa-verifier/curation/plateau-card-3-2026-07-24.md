# Plateau card #3 — the QAV v4 go/no-go (2026-07-24)

## The one-minute version

Three tunes in a row now judge perfectly — right reject/approve call every single time — and
fail the exam only on **naming the defect kind**. The v3 exam localized that failure to two
missing kinds of training example. Before spending another GPU night, we counted exactly how
many of each we can honestly manufacture from what the estate owns:

1. **Blank-section examples** ("an evidence section is empty while all tests are green ⇒
   composition seam, DC-03") — the main gap. Today: **3 rows**. Honestly mintable: **~25
   banked** (30 variants across 14 tasks, at the measured 84% pair-banking rate), of which
   **6 land in the held-out eval side**. Caveat, stated plainly: only **9 variants reproduce
   the exam's *pure* shape** (blank section AND no plan-audit block); the other 21 are
   near-shapes. One recovery spike (api_test UPT-001, below) likely adds ~4–7 more and breaks
   the single-repo monoculture.
2. **"Blank ≠ tampering" examples** (the new DC-05 confusion) — decisively curable: **~35–43
   banked** across five constructions, all inside already-proven machinery, growing DC-05
   support from 3 train rows to ~20–25 with explicit tamper-vs-clean contrasts on the same
   spines. This gap can be retired outright.
3. **The MacBook adds zero.** The 07-21 sweep tree contains no run records at all — every
   artifact in it is a byte-duplicate strict-subset of what the GB10 holds. (A fresh Mac
   sweep is a 2-minute optional check; the tree's profile says the Mac never stored the
   record type we need.)

**The honest read:** the arithmetic supports one more overnight cycle — this is not a
"we can only make a dozen" situation. But the pure-shape count (9, maybe 13) is the thinnest
plank; if v4 fails, it fails there, and that failure would mean the source estate itself must
grow before any further tuning.

## The menu — pick a letter

**A — Run v4 now (RECOMMENDED), with a stop-rule.** Sequence: the two cheap pre-gates first —
(i) the UPT-001 recovery spike (copy its stranded run record into the record-store, regenerate
its control ×2, prove the wiring section really populates; ~an hour, CPU) and (ii) the PRV-007
diagnostic (its record should give a populated spine but replayed all-null — one hour to
diagnose, possibly a free 7th study_tutor spine). Then the overnight: vacancy cohort + DC-05
boundary axes → corpus run → retrain → sealed re-exam. Same protocol as last night, receipts
throughout. **The stop-rule rides the claim: if the exam still fails on the pure-vacancy shape,
the tuning loop parks until the source estate grows — no v5 on this corpus.**

**B — Ratify first, then a bigger v4.** Your one Rich-moment lever: api_test FEAT-9E59 holds
**20 complete run records on disk** whose tasks have tracker approvals but no committed merge
evidence — the false-green law (forge FEAT-FMDR precedent) rightly refuses them without your
explicit ratification. If you hand-ratify that batch (or a slice), the vacancy cohort's
task-bound rises well past 14 before the retrain. Cost: your judgment over ~20 tasks, then the
same overnight as A.

**C — Park the tuning loop.** Three probes have fully proven the serving contract and verdict
behavior, and have localized the attribution gap to training material the estate cannot yet
manufacture at scale. Bank the findings, let organic factory growth (new features → new
records) raise the ceiling, and revisit with a richer estate. Nothing is lost — all three
candidates stay parked on llama-swap, and the corpus keeps growing regardless.

## Why A is the recommendation

The DC-05 half of the failure is curable beyond reasonable doubt (~40 targeted contrast rows
through proven seams). The vacancy half grows 3 → ~25–30 rows (8–10×) with repo diversity
1 → 2, and — new since v3 — the eval split now carries every class, so the cheap merged-gen
gate will show whether the mapping landed *before* the exam is spent. One more overnight is a
bounded bet with an honest stop-rule; B is the better bet only if you want to spend a
ratification sitting first; C costs nothing and stays available after an A failure.

---
*Arithmetic provenance: 4-counter census 2026-07-24 (populated-spine census over the 64 banked
control rows · record-store/recovery audit · DC-05 construction survey · Mac sweep-tree record
mine). Full numbers in the census outputs; per-task field matrix and split-side assignments
verified against `assign_split` and the banked corpus. DF-008: counts and field names only.*
