# QAV Batch Review — CARD #2 (the deeper hunt) — one tap 2026-07-21

**The one-minute version.** Card #1 mined the easy seam (merge summaries + one post-merge review).
Card #2 went **deeper** into the residual pool — the 79-bundle curation pack minus card #1's 20 —
hunting **second-order evidence**: later fix commits that name the exact task and state the coach
verdict, a live on-device gate blocker, a discriminating retro, and the forge merge-review. Below are
**10 curator labels** the harvest derived and then adversarially attacked; each survived. Each rests
on a **committed record OTHER than the bundle** (a fix commit, a review, a live-gate, a retro) — never
on the bundle's own say-so — and is tagged with the **rule** that earned it. Approving banks all 10 as
QAV *data* (private, DF-008 — **banking is not training**).

**The headline: 6 of the 10 are REJECTS, and all 6 sit on the TRAIN split.** The census and the
round-4 spike named one binding constraint over and over — *train reject side = 0* (the only rejects
were the eval-holdout gold negatives, which the contamination law keeps out of train). **These six are
the first harvested, non-gold, train-side rejects the program has ever had** — materialised from
committed evidence alone, with no seeded lane and without touching the evidence-divergence guard.

**Why the guard is untouched:** every reject below is a **real committed coach bundle** (verbatim on
disk, all-gates-green, honesty 1.0) whose reject label is earned by an **external** record. That is
harvest mode — the sanctioned reject path. The seeded evidence-divergence tripwire polices only
seeded_code control-identical bundles; nothing here is seeded.

**To strike any row:** name its task id in your reply. Struck rows drop; the rest bank.

**Honesty counts.** Two rows are flagged **strike-me-first** (QAV-006 approve; KCA3-003 reject). A
whole basket of candidates was **excluded on the law** (see HONEST RESIDUAL below) — including the 4
QAV Phase-0 neighbours, whose only record is a review-summary I could prove unreliable.
**Split: 4 approve / 6 reject.**

---

## APPROVE (4) — coach was right

**Rule A1-J** — *jarvis has no merge_summary.json; approve when the feature tracker records
final_decision=approved, merge is clean + on main, an independent live-gate ran, and no post-approval
**product** fix names the task.* (FEAT-28FF, merge 736399b, live-gate JNB-009 @9200266 "ALL GREEN").
The same rule + tracker + merge + live-gate card #1 used for JNB-001; the two post-merge JNB fixes
(9e2e0b6, eaf9a21) are **test-only** and name JNB-005/006, so they don't disqualify these three.
- `jarvis / TASK-JNB-002` → **approve** — notification-sink seam + queued hook; tracker approved; JNB-009 exercised the wired bridge · `jarvis/.guardkit/features/FEAT-28FF.yaml`
- `jarvis / TASK-JNB-003` → **approve** — lifecycle wiring (construct+bind SlackNotifier); tracker approved; JNB-009 live-exercised exactly this runtime. *(caveat: direct-mode — the live-gate, not the bundle, is the mitigant)*
- `jarvis / TASK-JNB-008` → **approve** — v1 scenario test matrix; 5 turns, terminal green (10/10), ugly-green; no fix names it

**Rule retro-affirmed-fix-held** — *approve when the SAME committed retro that CAUGHT a sibling escape
affirmatively records THIS task closing the gap under an independent adversarial re-run, and no later
fix names it.*
- `guardkit / TASK-QAV-006` → **approve** (ugly-green, **strike-me-first**) — the L4 producer that closed the QAV-005 (GN-3) runner-without-producer escape; the same consolidation retro that caught QAV-005 affirms QAV-006 "4 adversarial turns, 291 tests green, fs-01 verdict-flip now real" · `guardkit/docs/retro/qa-verifier-state-consolidation-2026-07-04.md`. *(caveat: self-authored retro, thin bundle AC 1/7; approve side isn't the constraint — safe to strike)*

---

## REJECT (6) — coach approved, a committed record caught the escape · **ALL split=train**

**Rule OA-R (operator-assist reject)** — *reject when a committed operator-assist FIX COMMIT states
the task was Coach-approved AND corrects a real product defect in its OWN module the coach's scope
missed.* `ground_truth_source = operator_caught`. Source: the specialist-agent FEAT-DF12 operator-assist
commits.
- `specialist-agent / TASK-DFEM-004` → **reject [DC-03]** — validator mis-parsed the authoritative positional table format (rejecting conformant plans) + added an unconditional `corrections` key breaking the pinned 4-key contract shape; pre-fix 4 gate + 1 dispatch failure · `@418c046`
- `specialist-agent / TASK-DFEM-006` → **reject [DC-03]** — approved 8/8 but built a 287-line **self-consistent shadow schema** instead of the real guardkit model (coach missed it *because* the shadow was internally consistent) + head_sha name collision + divergent API · `@03e4914`
- `specialist-agent / TASK-DFEM-007` → **reject [DC-03]** — DF-007 division-of-labour violation: with no target_repo the emitter wrote pass-bars into its **own** repo (CWD-relative fallback) + 5 stray artifacts swept into the commit · `@cf2abe3`

**Rule RC-R (review-catch reject)** — *reject when a committed post-autobuild "coach-of-coaches" / Fable
review fix records a real product defect in the coach-approved task's own surface (outside the smoke-gate
scope).* `ground_truth_source = merge_review_caught`.
- `study-tutor / TASK-KCA2-002` → **reject [DC-03]** — made `HTTPAuthConfig.resolver` a required ctor arg, breaking 5 direct-construction callsites; outside the smoke-gate scope; violated its own "existing tests pass unchanged" AC (the GN-2 signature/callsite class) · `@255e0b54`
- `study-tutor / TASK-KCA3-003` → **reject [DC-03]** (**strike-me-first**) — discarded `whenComplete` future re-raised SignInCancelled/Failed as uncaught zone errors; the returned-future seam was never wired despite a surface-correct try/catch · `@b3960225`. *(flag: fix tags it "(coach critical)" and bundle is 10/11 AC — coach may have partially known; strike if you read it as coach-caught)*

**Rule LG-R (live-gate reject)** — *reject when a committed fix records a real product defect in the
coach-approved task's own surface FOUND LIVE (on-device gate blocker).* `ground_truth_source =
live_gate_caught`.
- `study-tutor / TASK-KCA3-001` → **reject [DC-03]** — added a manual VIEW intent-filter duplicating flutter_appauth's redirect receiver → Android twin app-chooser strands the token exchange; caught **live on device** as a KC-G3 blocker (checkpoint C4) · `@8c438eba`

---

## U2 RESOLUTION — one tap, no new row

The GN-4 gold negative carries a blank task-id (`task: null`, "U2 — awaiting Rich"). The forge
FEAT-SPL-002 post-merge review resolves it with certainty: **GN-4 = forge `TASK-MP-011`**, and its
approving bundle **survives verbatim on disk** (`forge/.guardkit/autobuild/TASK-MP-011/coach_evidence_turn_3.json`).
The review names "TASK-MP-011/FEAT-DD4F" as the CRITICAL serve-boot defect; fix sha `1ad98c0` = the
MP-011 merge; GN-4's locus is near-verbatim from it. **Task-id is NOT synthesised — proposed with
committed evidence for your tap.** Confirming fills GN-4's U2 field with `TASK-MP-011` and upgrades it
`reconstructed → verbatim`. **Adds no row; changes no count.**

**To confirm:** say `confirm U2 = MP-011`.

---

## HONEST RESIDUAL — what stays unlabelable, and why

- **guardkit QAV-001..004** (Phase-0 neighbours of the GN-3 reject) — the ONLY per-task record is the
  FEAT-10AC run-3 autobuild review-summary, and it is **impeached**: it stamps QAV-005 "PASSED |
  approved | (no notes)" while QAV-005 is the caught GN-3 gold reject. Silence on QAV-001..004 is not
  affirmation; their bundles are thin (QAV-002 0/8, QAV-004 1/9 AC). → **queued.**
- **specialist DFEM-008 / 009 / 010** — their operator-assist commits are a ratification-driven default
  flip (008), a sibling-test-only update + ruff (009), and ruff-only on an explicitly-clean task (010).
  Not product escapes → not rejects; no policy-grade approve record → **queued.**
- **guardkit ABL1-002** — FAILED after 4 turns (unrecoverable_stall); the honesty machinery caught the
  nats_core stub false-green **in-loop**. Census R3: a catch, not an escape. → **excluded.**
- **study-tutor realm redirect URI (fa49ce58)** — a real KC-G3-blocking defect, but the fix names "A1
  realm-as-code" with no clean join to a discovered coach bundle. → **undecidable / queued.**
- **study-tutor KCA2-001 uv.lock-sync** — real but build-hygiene (lock not regenerated); DC class
  fuzzy; not a product-logic escape. → **queued.**
- **VS2 (8) · VOX-001/006 · MEP-001/003/004/005 · HARV-002 · KC-001..005 · ABL5-001 · KCA2-003..006 ·
  KCA3-002/004/005/006 · VER-001** — clean-merge or thin-turn-1 with **no policy-grade per-task
  record**. Approve side is **not** the binding constraint, and mining them would only worsen
  approve_share. **Deliberately left queued** — they remain Rich's hand-curation pool (pack §U4).

**Net after card #2 (if fully approved):** the whole-corpus consumable labels rise from card #1's
maths by **+4 approve / +6 reject**, and — critically — the **train reject side moves off zero for the
first time** (6 harvested DC-03 train rejects). The balance law finally has real reject volume to work
with instead of gold holdout alone.

---

**Reply `approve the batch`** (optionally `except <task ids>`, and/or `confirm U2 = MP-011`).
