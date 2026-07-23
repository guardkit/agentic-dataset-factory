# Cycle-2 coverage — the two trust-page catches, cured

Cycle 1 shipped a recruiter corpus and a tuned model that passed the guided exam. The 2026-07-23
trust page then caught **two drafting failures** on banked cycle-1 drafts that the soft judge had
waved through. This cycle is a **focused four-class supplement** (`briefs-cycle2.yaml`) that teaches
the model the right answer to each, plus the closed-set exemplars a corpus census showed were missing.

Nothing here changes the generation engine or the acceptance path: every block reuses an existing
`expected_class`, so pointing `agent-config-cycle2.yaml` at `briefs-cycle2.yaml` and running is the
whole operation. The office's own checkers stay the boss.

---

## The two caught failures

1. **Invented source + stages under a webhook-flavoured ask.** A leads-chase draft reached for
   `read: webhook` (a source kind that does not exist — the legal set is
   `mailbox-sweep | tray | ledger | pending | drop-folder`), and added unregistered stages
   `gather`/`classify` with fabricated `with:` params. A webhook-flavoured clause stampeded the model
   straight past the closed vocabulary — the exact 2026-07-21 leads-chase failure, recurring.

2. **Invented `send_as: one-page`.** A friday-week-in-review draft wrote `send_as: one-page`. The
   closed set is `one-bundle | each-record` only. The model reached for a plain-English word instead
   of the vocabulary when the ask was flavoured with "one page".

## The census gaps behind them

- **No `each-record` exemplar anywhere.** All **188** drafted destinations in the cycle-1 corpus are
  `send_as: one-bundle` + `deliver: email`. `each-record` appears in **zero** drafted file bodies. With
  no in-corpus example of the legal per-record shape, the model improvises (`one-page`) under any
  bundling-flavoured ask.
- **No tight servable-vs-wall contrast.** Zero valid drafts pair a webhook / Google Calendar / Slack
  flavoured ask with a **clean closed-set-source draft**. Honest-wall exemplars exist, but none is a
  minimal contrast sibling of a fully-servable leads-chase — so the model never learned that a single
  added integration clause is the ONLY thing separating "draft it" from "draft the doable part and
  name the wall".

---

## The four class blocks

| Block id (`briefs-cycle2.yaml`) | Sorting label | Target rows | Seed briefs | Intent — the cure |
|---|---|---:|---:|---|
| `leads-chase-valid-source` | `pipeline` | 40 | 11 | Fully-servable chase/follow-up asks in closed vocabulary only — tray/pending/ledger + member + window, weekly/weekday schedules, one-bundle email to the operator. No integration clause, so a webhook is never reached for. Cures failure (1). |
| `integration-wall-with-draft` | `honest-wall` | 40 | 10 | Servable core PLUS one unservable integration clause (Google Calendar, Slack, SMS, external dashboard, CRM API, webhook, phone, Notion, Dropbox). Correct answer: draft the doable part with closed-set sources AND name the missing integration as a wall **in prose** — never a fake token in a draft file. Cures failures (1) and (2) at the boundary. |
| `send-as-explicit` | `pipeline` | 40 | 10 | Weekly/periodic review + report asks (friday-class analogues, paraphrased) whose correct draft is `deliver: email` + `send_as: one-bundle` to the operator — the legal answer to a bundling ask. Several briefs make the bundling explicit ("as one email", "a single bundle", "not one message per item"). Cures failure (2). |
| `send-as-each-record` | `pipeline` | 30 | 8 | Per-record delivery to a NAMED pinned gateway destination — `deliver: gateway` + `send_as: each-record`, single `to: {destination}`, no route. Gives the corpus its **first `each-record` exemplars**. Cures the census gap behind failure (2). |

Totals: **150 target rows across 39 seed briefs.** Blocks reuse `pipeline` (×3) and `honest-wall`
(×1) — no new class, no engine change.

## The contrast-sibling pairs

Six `integration-wall-with-draft` briefs are minimal contrast siblings of a `leads-chase-valid-source`
brief: identical ask shape, exactly one added unservable clause. The model sees the same core drafted
clean in one row and drafted-plus-walled in its sibling — the sharpest possible signal that the
integration clause, and only it, is the difference.

| Servable brief (block 1) | Wall sibling (block 2) | The one added clause |
|---|---|---|
| Monday 9am, sales-clerk leads, last-7-days, still waiting | same | check my **Google Calendar** so it skips weeks I'm away |
| Weekday 8am, sales-clerk tray, yesterday, unanswered | same | drop a copy into our team **Slack** channel |
| Day 5:30pm, sales-clerk pending queue, need a reply | same | **text** the count to my mobile (SMS) |
| Wednesday 10am, research-clerk tray, last-7-days, not circled back | same | sync them into our **CRM** through its API |
| Weekday 6pm, leads-clerk tray, day's unanswered | same | fire a **webhook** to our reporting tool |
| Friday 4pm, finance-clerk ledger, awaiting response | same | push the totals to our external **dashboard** |

The remaining four wall briefs are standalone (calendar-write reminders, a phone call, Notion,
Dropbox) so the wall class is not narrowed to only the sibling shapes.

## The combo law

Executable destinations only (runner.py:266-275): **`deliver: email` + `send_as: one-bundle`**, and
**`deliver: gateway` + `send_as: each-record`** (a single `to: {destination}`, no route). The other
two pairings — `email` + `each-record` and `gateway` + `one-bundle` — validate but are
execution-refused, so no brief here elicits them. Block 3 targets the email/one-bundle combo; block 4
targets the gateway/each-record combo. Every block-4 brief names a single pinned gateway destination
(invented names such as `intake-desk`, `case-tracker`, `fulfilment-queue`, `review-board`,
`ops-inbox`, `dispatch-gateway`, `partner-portal`, `records-desk`; the stub estate context accepts any
because `gateway_destinations` is left empty, short-circuiting the pinned-allowlist check).

## Denylist-paraphrase discipline

Every brief is paraphrase-clean of the 21 held distinctive phrases (`denylist.py`) and carries no
banked-session verbatim text. The four eval-held sessions are Rich's frozen re-sit exam, never
training data. Scenario NAMES (leads-chase, friday-review) are deliberately lawful; the distinctive
PHRASING is what the denylist floor catches — so, for example, "chase list of the leads waiting on a
reply" is rephrased freshly here as "leads still waiting to hear back", "follow-ups I still owe",
"contacts I haven't circled back to", "unanswered enquiries", and "still needing a nudge". The
`gate-papers-2026-07-23-readable.md` exam was read for ask-SHAPE only; no held phrasing is reused, and
the acceptance path's contamination gate enforces this on every generated row before it is written.

## Self-check performed

- Both new YAML files parse (`yaml.safe_load`).
- Every one of the 21 denylist phrases greps to **zero hits** across the briefs.
- Every `send-as-each-record` brief names a single pinned **gateway** destination and per-record
  delivery; every `send-as-explicit` brief implies **email + one-bundle** (single/combined/bundle).
- `agent-config-cycle2.yaml` differs from `agent-config.yaml` by exactly the one `briefs:` path line.
