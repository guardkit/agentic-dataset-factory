# QAV Batch Review — one tap 2026-07-21

**The one-minute version.** Below are **18 curator labels** the harvest derived and then
adversarially attacked. Each one survived. Approving banks all 18 as QAV *data* (private,
DF-008 — **banking is not training**, no model learns from this here). Each label rests on a
**committed record** (a merge, a retro, a post-merge review, a feature tracker, a deploy-smoke)
— never on the bundle's own say-so. Each is tagged with the **rule** that earned it; approving
the batch ratifies the rules and the labels together.

**To strike any row:** name its task id in your reply. Struck rows drop; the rest bank.

**Honesty counts:** **2 candidates were REFUTED** and are NOT below (TASK-STAT-001, TASK-HARV-004).
Also excluded by law: A2 manual-fix approves, and gold-source tasks (never re-labeled).
**Split:** 13 approve / 5 reject.

---

## APPROVE (13) — coach was right

**Rule A1-LIVE** — *approve only when a committed behavioural re-verification ran on the merged/deployed tree, not just a clean merge.*
- `api_test / TASK-UPT-001` → **approve** — merge e5ff1c8 + staged deploy-smoke re-ran /uptime (3 fields, counter rose, POST 405) · `ai-transition/docs/factory-1-first-pass-2026-07-12.md`

**Rule independent-guard-held** — *approve only when a committed record OTHER than the bundle re-exercises the task's exact contract and holds.*
- `nats-core / TASK-MEP-002` → **approve** — merged guard green; sole guard-hit was innocent prose, not a topic leak · `nats-core/tests/test_topics.py` (@bd9bc49)

**Rule A1'-review-summary-approve** — *approve when committed review-summary.md + events.jsonl both record approve at the merge, merge is on main, and no later fix touches the surface.* (FEAT-VOICE-001, merge 5d57b022)
- `study-tutor / TASK-VOX-002` → **approve** — review-summary approved + events.jsonl approve; no later fix · `.guardkit/autobuild/FEAT-VOICE-001/review-summary.md`
- `study-tutor / TASK-VOX-003` → **approve** — same record, row approved; 6d54ea8e is feat not fix · *(same path)*
- `study-tutor / TASK-VOX-004` → **approve** — same record, row approved; no fix · *(same path)*
- `study-tutor / TASK-VOX-005` → **approve** — same record, row approved; no fix · *(same path)*
- `study-tutor / TASK-VOX-007` → **approve** — took 5 turns; terminal verdict approve, never reopened · *(same path)*

**Rule MP-A** — *approve when the adversarial post-merge review (proven to catch escapes) affirmatively passed THIS task and no fix touched its core.* (FEAT-SPL-002 review @4e47d47, merge 34b17d0)
- `forge / TASK-MP-001` → **approve** — review PASS on fallbacks-audit + approval-routing; audit.py never fixed · `forge/docs/reviews/feat-spl-002-post-merge-review-2026-07-06.md`
- `forge / TASK-MP-002` → **approve** (ugly-green) — durable-store PASS; only LOW audit-only blemishes · *(same review)*
- `forge / TASK-MP-003` → **approve** (ugly-green) — pure-function planner PASS; planner.py never touched · *(same review)*
- `forge / TASK-MP-004A` → **approve** — gate-adapter PASS; MP-012 change is cosmetic reflow only · *(same review)*
- `forge / TASK-MP-007` → **approve** — frontier PASS in full, zero negative findings · *(same review)*

**Rule A1-J** — *jarvis has no merge_summary.json; approve when the committed feature tracker records final_decision=approved, merge is clean + on main, an independent live-gate ran, and no fix names the task.*
- `jarvis / TASK-JNB-001` → **approve** — tracker final_decision=approved; merge 736399b (2390 pass/0 fail); live-gate held; no fix · `jarvis/.guardkit/features/FEAT-28FF.yaml`

---

## REJECT (5) — coach escaped, the merge review caught it

**Rule MP-R** — *reject when the committed post-merge review recorded a MEDIUM+ CONFIRMED defect in the coach-approved task's OWN module and a later commit substantively rewrote it to fix it.* All DC-03 (composition-seam), all in FEAT-SPL-002, all fixed by MP-012 @4aac654. Source: `forge/docs/reviews/feat-spl-002-post-merge-review-2026-07-06.md`
- `forge / TASK-MP-009` → **reject [DC-03]** — CRITICAL: Mode P chain had zero production execution path; masked by *args/**kwargs fakes
- `forge / TASK-MP-004B` → **reject [DC-03]** — HIGH: checkpoint sends invalid approval payloads, jarvis drops them; masked by a permissive fake publisher
- `forge / TASK-MP-006` → **reject [DC-03]** — HIGH: terminal handoff unreachable — GitRunner a Protocol only, zero call sites, no row written
- `forge / TASK-MP-005` → **reject [DC-03]** — MEDIUM: escalation/defer had no driver; new request_id never persisted; CAS guard skipped
- `forge / TASK-MP-008` → **reject [DC-03]** — MEDIUM: consumer acks on write-failure (drops on SQLITE_BUSY); dotted cid fragments the approval subject

---

**Reply `approve the batch`** (optionally `except <task ids>`).
