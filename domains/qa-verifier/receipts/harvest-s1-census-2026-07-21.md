# RECEIPT — QAV Harvest S1 census + labeling-policy proposal (2026-07-21)

> **This is a decision document.** Section 2 (the labeling policy) is a **ratification gate**:
> no tune trains on QAV harvest rows until Rich has read and approved these exact rules. Nothing
> below writes to a corpus repo; the whole census was read-only.

Glossary (one pass, plain terms):
- **Bundle** = one serialized `coach_evidence_turn_N.json` file — the frozen record of what the
  automated reviewer ("the coach") saw when it judged a task. This is the *input* a QAV row learns from.
- **Label** = the *answer key* attached to a bundle: **approve** (the coach was right to pass it) or
  **reject** (a real defect slipped past — the coach should have caught it). The whole point of QAV
  is to teach a model to tell these apart.
- **Ugly-green** = an approved bundle that carries blemishes (advisory notes, demoted "should-fix"
  items, or a test failure the coach classified as environment/infra). These are *deliberately*
  wanted — they are the honest greens a lazy "reject-everything" judge would wrongly block.
- **Ground-truth source** = *where the answer key came from*: `coach_correct` (approve held),
  `operator_caught` / `merge_review_caught` / `live_gate_caught` (a human/gate caught the escape).
  A guessed verdict is never a valid source.

---

## 1. One-minute version

| Question | Answer today |
|---|---|
| **Harvestable bundles on disk** (final-turn, schema-valid, read-only discovered) | **82** |
| **…that can carry an evidence-derived label TODAY** | **13** (9 approve + 4 reject) |
| **…approve-labelable** (merge-summary "approved" → discovered bundle) | **9** (2 certain + 7 probable) |
| **…reject-labelable** (the 4 documented gold negatives) | **4** |
| **…undecidable / must be curated, never guessed** | **the other 69 of 82** + the off-corpus escapes |
| **Dataset that yields vs the ~1000-row Phase-1 target** | **~13 rows ≈ 1.3%** of target |
| **Achievable *balanced* set under the frozen laws** | **8 rows** (4 reject + 4 approve @ 50/50); ceiling **10** (4+6 @ the 0.60 tolerance edge) |

**The binding constraint is the reject side, and it is worse than the "8" suggests.** The frozen
manifest laws cap approves at **1.5× the available rejects** (approve_share must stay ≤ 0.60), so 4
rejects allow at most 6 approves — a **10-row** whole-corpus ceiling, **8 at a clean 50/50**. The
ugly-green floor (≥45% of approves) is *not* the limiter — 76 of 82 finals are already ugly-green,
so any approve subset clears it easily.

**The deeper reality (matches the round-4 spike's "machinery GREEN, data RED"):** all 4 rejects are
the **eval-holdout gold negatives**, and the contamination law excludes gold-negative source tasks
from the train split. So the **train side has ZERO rejects today** → a *balanced train manifest* is
**not achievable at all** right now (it would be approve-only, `approve_share = 1.0`, which fails the
band). The "8–10" above is a mixed train+eval object, not a trainable balanced split. A real balanced
train set needs **harvested (non-gold) reject rows that do not exist yet** — that is the S2/S3 job.

---

## 2. THE LABELING POLICY PROPOSAL — **Option B (evidence-only). Rich ratifies before any tune.**

**Option B in one line:** *label a bundle only from a committed post-hoc record; if the record is
missing or ambiguous, the bundle is left UNLABELED and queued for Rich — the verdict is never
inferred from the bundle's own contents.* (This is why the code's `evidence_grounded_draft_think`
is a draft only, and why `harvest()` silently skips any task without a supplied outcome.)

### Approve rules (`verdict = approve`, `ground_truth_source = coach_correct`)

- **A1 — Autobuild-approved-and-held.** IF a discovered final-turn bundle's `(repo, task)` appears in
  a committed `merge_summary.json` with `tasks[].decision == "approved"` AND that task carries **no
  manual-fix commit** → approve. **Provenance required:** the on-disk `merge_summary.json`;
  `provenance.sha` = that summary's merge/FF sha (e.g. FEAT-E2CB FF `917bcef7`), `feature` = its
  `feature_id`. *Yields: guardkit FEAT-E2CB `TASK-BDDW-001/002` (2, certain — feature is in the
  discovered set) + study-tutor FEAT-70A4 `TASK-PRV-001..007` (7, pending a one-line presence-confirm
  that each PRV bundle is among study-tutor's 32 discovered finals).* **Total A1 ≈ 9.**
- **A2 — Approved-plus-manual-fix → EXCLUDE.** A task whose approve required a human seam/identity fix
  (guardkit FEAT-C332 `QAWE-002` fix `b0951346`, `QAWE-004` fix `44dbe63d`) is **not** `coach_correct`
  — the approve did not hold unaided. Excluded from approve; queued. (Moot anyway: FEAT-C332 bundles
  are not in the discovered 82 — they live only at HEAD archive.)
- **A3 — Reviewer-in-loop "completed" → QUEUE, do not auto-approve.** study-tutor FEAT-PO-002
  (`PO02-001..007`) is `autobuild:false`, status `completed`, not an autobuild coach `approved`
  decision — a *different* approve semantics. Held for Rich's curation, not labeled by A1.

### Reject rules (`verdict = reject`, requires a `finding` carrying a DC class)

- **R1 — Documented gold negative.** A task named in `SPEC-qav-gold-negatives.md` with a full
  provenance dict `{repo, feature, task, run, sha}` + a **committed retro on disk** + a stated DC class
  + `ground_truth_source ∈ {operator_caught, merge_review_caught}` → reject. **Provenance required:**
  the SPEC row **and** the retro file. *Yields the 4:* GN-1 SMP-002/`SMP2-07` (DC-08, operator_caught),
  GN-2 SMP-003/`SMP3-06` (DC-03, operator_caught), GN-3 10AC/`TASK-QAV-005` (DC-03, merge_review_caught),
  GN-4 DD4F (DC-03, merge_review_caught). These are the **eval holdout** by design.
- **R2 — Prefer the verbatim bundle; else reconstruct (flagged).** Where the approving bundle survives
  verbatim on disk (GN-3: `guardkit/.guardkit/worktrees/FEAT-10AC/…/TASK-QAV-005/coach_evidence_turn_2.json`)
  use it directly; the other three fall back to `reconstructed` (allowed by design, marked as such —
  never fabricated).
- **R3 — Not a clean coach-escape → EXCLUDE from labels.** An escaped defect that either has **no
  CoachEvidenceBundle identity** or was **not a coach-approve-then-escape** is not a QAV reject row:
  lpa-platform-poc **FEAT-POC-006** (canonical mocked-seam case, but its repo carries **zero** bundles
  on disk), **ABL-001** (honesty machinery *stalled* it in-loop — a catch, not an escape), and the
  **B4 defect ledger #1–#21** (factory-plumbing loud-fails caught by the coordinator/deterministic
  gates — the gates *working*, keyed to run-ids/infra commits, not to any bundle). Kept as documented
  cases; excluded from the row set.

### Undecidable → EXCLUDED or QUEUED (never guessed)

- **U1 — FEAT-FMDR-004 (DC-14).** Named only as a recipe seed in `GOAL.md`; no committed retro path →
  cannot join to a run record → **excluded/queued**.
- **U2 — DD4F task-id (the one ambiguous field in the 4 golds).** SPEC leaves it as
  `<wiring-fix task id from forge tracker>`. Keep the gold row but **flag the field for Rich to fill**;
  do not synthesize a task-id.
- **U3 — The 5 unnamed of the "9 documented incidents."** Only ~7 are individually named in committed
  docs; the rest "lived in the session-internal fan-out digest" → **out of scope** until surfaced.
- **U4 — The 69 discovered bundles with no committed outcome** (82 − 9 approve − 4 in-scope). These stay
  **UNLABELED**; `harvest()` skips them by the provenance rule. They are the raw material for Rich's
  curation pass, **never** auto-approved from their contents.

---

## 3. Join-table reality — how a bundle keys to its answer key, and where it frays

| Outcome record | Keys on | Joins to a bundle by | Quality |
|---|---|---|---|
| `merge_summary.json` (approve) | `feature_id` + `tasks[].id` + `decision` | `(repo, task)` → discovered final-turn bundle | **Feature-clean, task-usable.** Caveat: per-task *approved-sha* has **no on-disk source of record** — we use the summary's **merge/FF sha** as `provenance.sha` (defensible: the approve held as of merge), not the exact approving-turn commit. |
| `SPEC-qav-gold-negatives.md` (reject) | explicit `{repo, feature, task, run, sha}` + DC class | named task → committed retro (+ verbatim bundle for GN-3) | **Cleanest join in the estate** for 3 of 4. GN-4 DD4F: every field solid **except the task-id** (U2). |
| live-gate envelopes (`qa/gates/history/*.json`) | `feature-id` + target + UTC timestamp | — | **Feature-level only.** Proves the merged feature runs in production; does **not** reach a task-level coach verdict/bundle. Supporting evidence for A1, not a standalone label. |
| B4 defect ledger #1–#21 | workflow run-ids + infra fix commits | — | **No bundle identity.** Pre-approve loud-fails of plumbing → out of scope (R3). |

Selection footgun to carry forward: `discover_bundles` keys final-turn by `(repo, task =
immediate-parent-dir-name)` and **silently merges same-TASK-id bundles across different features /
evidence variants** (guardkit's 100 raw files → 12). And a naive re-run *without* the `.claude/worktrees`
skip records **jarvis worktree paths as the winner** (rglob tie-break). Any S2 harvest must reuse the
census's skip filter, not the bare function.

Source of record for the 82: `run_logs/qav-harvest-census-2026-07-21.jsonl` (untracked by design —
`run_logs/` is **not** actually gitignored for `*.jsonl`; do **not** commit it).

---

## 4. The MacBook one-paste

Rich runs this **on the Mac**. It is read-only, walks the project roots for coach evidence bundles +
merge summaries + live-gate history, skips the `.claude/worktrees` duplicates, and writes **one
tarball** to the home folder. It exists to widen the corpus: the Mac may hold repos/worktrees/records
that never reached the GB10.

```bash
ROOT="$HOME/Projects/appmilla_github"; [ -d "$ROOT" ] || ROOT="$HOME/Projects"; [ -d "$ROOT" ] || ROOT="$HOME"
OUT="$HOME/qav-harvest-mac-$(date +%Y%m%d-%H%M%S).tar.gz"
find "$ROOT" -type f \
  \( -name 'coach_evidence_turn_*.json' -o -name 'merge_summary.json' -o -path '*/qa/gates/history/*.json' \) \
  ! -path '*/.claude/worktrees/*' -print0 2>/dev/null \
| tar --null -c -z -f "$OUT" -T - 2>/dev/null
N=$(tar -tzf "$OUT" 2>/dev/null | wc -l | tr -d ' ')
echo "wrote $OUT — $N files, $(du -h "$OUT" | cut -f1)."
echo "DROP IT BACK: scp to the GB10 into  agentic-dataset-factory/incoming/  (create it),"
echo "or hand it into the QAV channel. Read-only: nothing on the Mac was modified."
```

**Where to drop it:** `scp` (or AirDrop→then copy) into
`~/Projects/appmilla_github/agentic-dataset-factory/incoming/` on the GB10 (make the dir; it is not a
corpus repo, so no venue rule applies), or paste it into the QAV channel. S2 unpacks it read-only and
re-runs discovery over the union.

---

## 5. Honest caps + what S2/S3 need from this census

**Caps (state these plainly to Rich):**
1. **Train reject side = 0 today.** The only rejects are the 4 eval-holdout golds; the contamination law
   keeps gold source-tasks out of train. So there is **no balanced *train* manifest to build right now** —
   the achievable balanced *whole-corpus* set is 8 (50/50) / 10 (0.60 edge), reject-bound, and even that
   is train+eval mixed.
2. **~13 labelable of 82** — the other 69 discovered bundles have **no committed outcome** and must be
   curated by hand; none may be auto-approved from their contents (Option B).
3. **Approve provenance is feature-merge-sha, not exact-turn.** Acceptable, but there is no per-task
   approved-sha source of record — decide whether that is good enough for training provenance.
4. **`schema-compatible` ≠ exact-sha `41a0ebe457`.** Bundles don't self-declare a schema sha; "compatible"
   means the additive-subset validator passes. Exact-sha provenance is unverifiable from disk.
5. **~1000 rows is unreachable from committed evidence alone.** This census tops out near 13 labeled rows.
   The gap is filled only by the seeded-generation path — which round 4 proved is **corpus-blocked**, not
   GPU-blocked (anchor hit-rate 0/33; 10 of 13 discovered tasks lack a HEAD run-record).

**What S2 needs:**
- **Rich's ratification of Section 2** (the gate) — including the A2/A3/U2 calls.
- The **approved-sha source-of-record** decision (cap 3).
- A **curation pass** on: the 69 outcome-less bundles, FEAT-PO-002 semantics (A3), the DD4F task-id (U2),
  and FMDR-004 (U1).
- The **Mac tarball** (Section 4) unpacked, to widen the corpus before re-running discovery.
- The **one-line PRV presence-confirm** (are all 7 PRV bundles among study-tutor's 32 finals?) to firm up
  the "9" approve count to a certain floor.

**What S3 needs (from round 4's spike, unchanged and gating a useful full run):**
- The **anchor/recipe lane** — 11 reject recipes miss 100% on the processable tasks → today's corpus yields
  **zero seeded rejects**, i.e. no reject side to train on.
- The **HEAD-record coverage lane** — 77% of discovered tasks lack a materializable `task_work_results.json`.
- A **serving-posture** decision (batched legs vs co-resident matrix) so the ~15–24 h cold-thrash floor
  doesn't bind once the corpus lanes land.

Until the reject side materializes (harvest curation of the 69, **or** the S3 seeded lanes), QAV training
data is **approve-heavy by force**, and the frozen laws will correctly refuse to certify a balanced manifest.
