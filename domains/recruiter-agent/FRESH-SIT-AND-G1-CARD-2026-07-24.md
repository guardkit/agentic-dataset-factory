# The fresh sit + the G1 walk — Rich's card (2026-07-24)

Two sittings, both browser-only, both yours alone. Nothing here needs a terminal and nothing
freezes without your click. This card assumes the cycle-2 model is on the Spark seat (the
coordinator confirms that before handing you this card; if the merged-gen gate had failed, you
would be reading a failure receipt instead).

## Sitting 1 — the fresh live sit (minutes)

Cycle 2 exists because the trust page caught the two invalid drafts your sign-off rightly refused:
the leads-chase draft that invented a `webhook` source, and the friday draft that invented
`send_as: one-page`. The corpus now carries targeted exemplars for both classes (and the first
`each-record` exemplars the corpus ever had), the checker that caught them is tighter than it was,
and the retrained model passed the same merged-generation gate as cycle 1 before it was packaged.

**None of that earns a signature.** The page decides, then you do.

1. Open `http://127.0.0.1:8477/review` → the recruiter card → **Prepare the review**.
2. Expect **a few minutes of silent spin** — the run has no progress indicator yet (a banked
   residue, not a hang; the judge calls are bounded at ~120s × 3 tries each).
3. This is a LIVE sit: a fresh candidate answers all five items — nothing is replayed.
4. Read each item exactly as before: your ask · your signed standard · the office's read-back ·
   the settled facts. The judge's opinion stays collapsed and gates nothing.
5. If every deterministic fact holds, the sign-off button appears under the last item. If any
   concern shows, **do not sign** — that is the finding, and the floor is the product. Nothing
   freezes on a no.

After a signature: `office hire` seats the recruiter and `/chat` serves it — hiring by
conversation exists from that moment.

## Sitting 2 — G1, your timed walk (~1–2h, DF-028)

The wizard is live on the deployed page and was walked end-to-end synthetically on 07-24
(persisted drafts passed the real `deckhand config-check`; two defects found in that walk are
already fixed and deployed). G1 needs no passing recruiter.

Start the clock when you sit down. The path:

1. `http://127.0.0.1:8477/author` → pick the agent the real new hire is for.
2. Describe the hire through the seven screens — your documents · what matters · what matters
   most · how serious · compare answers · the safety trap · read it back. You will never type a
   number; if a screen asks you for one, stop and write that down (it's a bug, not you).
3. **Author the exam** → three draft files land under `authored-exams/<agent>/`.
4. Your signed act: move each draft to its live name in the agent's folder
   (`config.yaml` / `golden.yaml` / `anchors.yaml`).
5. Rehearse: **Prepare the review** on that agent → read → freeze only if it has earned it,
   or stop honestly.

Stop the clock. Bank: the elapsed time, dated, and **every friction, verbatim** — frictions feed
the next build and never get argued with. Pass bar: *"I'd put James in front of this."*

Known frictions from the synthetic walk (so they don't surprise you — add your own on top):

- The ranking screen defaults everything to "Most important"; clicking straight through submits
  an all-tied ranking with no warning.
- The compare-answers (A/B) screen is the hardest: the two answers respond to two *different*
  asks, and really judging them means opening "show the files" and reading raw YAML.
- The read-back screen labels weights with internal slug ids rather than your question text.
- The done page prints container paths (`/authored-exams/...`); on your machine the drafts are
  in the office folder's `authored-exams/`.

## The three stale cards on the board

Three morning-brief cards from 07-20/21/22 still sit on the coordinator's board (the 07-23 one
was consumed by the approve-click verification — the mail landed in your hotmail at 23:05 UTC
with its receipt banked). Rejecting them cleans the board but resets that edge's streak;
approving them sends three stale summaries to your own mailbox. Your call, no rush.
