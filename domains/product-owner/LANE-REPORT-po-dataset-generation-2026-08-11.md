# The product-owner dataset-generation lane — report of record
## 2026-08-11 · run on Rich's word (handoff: ai-transition docs/ways-of-working/po-dataset-generation-handoff-2026-08-11.md) · the lane ENDS at a corpus, this report, and a STOP — training stays parked behind Rich's separate word

## The one-minute version

The lane ran all seven handoff jobs in one day. The exam bar is **frozen** (Rich's
word). The teacher bake-off ran honestly through two clean DeepSeek windows and
**the production seat won** — so the corpus needs no Spark windows at all. The
first real corpus is banked: **15 accepted, quality-gated training rows**
reconstructed from real February–May specification sessions (every answer real,
only the reasoning teacher-written), plus 12 quarantined rows guarding the exam
and 7 honest rejections for review. The synthetic half (the thin shapes) is
designed, costed, and **waiting for Rich's sizing word**. Nothing trained.

## Job outcomes

| Job | Outcome |
|---|---|
| 1 Stock-take | 213 clean traces (07-11→07-31; none since — no August spec-chain runs). Coverage AMENDED during the bake-off: feature-spec 39 distinct (the real diverse stock), feature-plan 35, greenfield 43 records = only **6 distinct briefs**, idea-mode = **all probe-grade** ("x"/"Test"), extraction runs 0 (but the 91-record POHARVEST seed exists), scope 0 true-shape |
| 2 adf fix-list sweep | Zero of the six ledgered residues inherited (traced by imports); four adopted as design lessons; full suite 2,796 green pre-build |
| 3 Exam freeze | **FROZEN, Rich's word 2026-08-11** — digest at `EXAM-FREEZE-DIGEST-2026-08-11.md`; raise-only forever |
| 4 Teacher bake-off | **T2 the production seat WINS 5/9 vs DeepSeek 3/9** (pre-declared rule, two same-day amendments all uniform + documented; frontier reference 0/9, ineligible). Record: `bakeoff-2026-08-11/grades/RESULTS.md` |
| 5 Generation (real half) | Harvest lift BUILT per `SPEC-po-phase2-harvest-lift.md` (WS4-S2) and RUN: 19 records → 18 accepted → **15 after the leakage gate**, 12 quarantined, 7 rejected/stubs. Teacher = the bake-off winner (`product-owner-agent`), Coach = `gemma4-coach`, no self-scoring |
| 6 Quality gates | **Exam-leakage gate FIRED and enforced**: 3 rows discarded (FinProxy-domain briefs — identifying strings of frozen tasks 1–3; "a hit is a discard", no re-litigation). Dedup clean, credential scan clean, envelopes/stamps complete, 3-row spot-check exact (ACs == scenario names 32/32 and 29/29), brief skim clean |
| 7 Stop | This report; corpus bytes stay private under `output/harvest/` per DF-008 (never committed); training NOT started |

## The corpus, precisely

`output/harvest/train_harvest.jsonl` — 15 rows. Every row: `[system, user,
assistant]`, base-model-neutral (no chat template baked; the trainer applies it),
assistant = one think block + one fenced serving-contract JSON whose every factual
field is deterministically assembled from the real session artifacts; the teacher
wrote ONLY the reasoning and two glue fields. Stamps on every row: teacher model,
tier, weight (§4 table incl. the DDD-drift discount), triple SHAs, lift version,
`source: harvest`. Sidecars: `quarantine_golden_overlap.jsonl` (12 — golden-set
overlap, weight 0.0, never merges), `rejected_rows.jsonl` (7 — Coach rejections +
FORGE-006's `triple_missing` estate-drift stubs), `discarded_exam_leakage.jsonl`
(3), `MANIFEST-harvest-lift.md` (all 31 records dispositioned, rendered briefs
included, no silent drops).

## Decisions taken inside the lane (each recorded where it happened)

- **Teacher = the bake-off winner**, superseding the 07-07 spec's Decision-B
  `gpt-oss-120b` default via the script's own `--think-model` arg (recorded in the
  script docstring + commit). Coach distinct; no self-scoring.
- **Three reasoning-auto fixes** (each smoke-caught, probe-verified, committed):
  both `:9000` seats serve `--reasoning auto`; clients must read the reasoning
  channel and budget for thinking (6K think / 16K coach). **Estate lesson: any
  new client of these seats inherits this trap.**
- The Coach's grounding objection to verbatim `context_args` rejected 5 rows;
  per the spec's real-fields-never-edited rule they went to review, not repair.

## Flags for Rich (nothing here was changed by this lane)

1. **The exam-vs-prompt bind** (found during the bake-off): frozen `po-held-004`
   hard-asserts empty `source_documents` while the live `player_greenfield.md`
   (assembled at exam run time) REQUIRES `request:` references. Impossible bind,
   predates this lane. Your ruling at the exam's first sitting.
2. **The synthetic half needs your sizing word.** Real coverage after this lane:
   feature-spec/plan rich, extract 12 rows (harvest), greenfield thin (6 distinct
   briefs), idea/scope/evolve ZERO real. The factory's generative mode is built
   and pilot-proven (55/60); the spec's §5 phased-extract seams are designed but
   unbuilt; a full 1,100-target run is days of GB10 wall-clock. Options: full run,
   a thin-shapes-only slice (idea/scope/greenfield first), or hold.
3. **Trace-export option**: specialist-agent's own `export_sft_corpus.py` (with
   M-22 redaction built in) could mechanically yield ~1,000+ player-imitation
   rows from the 213 banked traces (208 rows from 37 traces on its 07-13
   receipt). It writes into specialist-agent's output dir — the lane's read-only
   fence stopped me running it unbidden. Cheap, real, one word.
4. **Ledgered from the Gemma 4 currency check** (in the plan of record):
   `gemma4-coach` (Jun 6 quant) and `gemma4-tutor` (Apr 28) predate the July
   fixes wave; re-pull at a maintenance window.
5. **Thermal caps**: window-proven (71°C max, no measurable cost); a permanent
   systemd unit on both nodes is one word away.

## Mission accounting (§8 discipline)

This lane moved no measurable directly — it is named prerequisite work: the
corpus + frozen exam are the raw material for the PO tune, which targets M1
(better specs → rarer red pen) and deepens M0 (the teacher of the workers is
local; the bake-off proved the estate needs no frontier and now not even a
special seat for it). M0 status during the lane: zero frontier on any critical
path; the frontier reference generation was attended, ineligible, and discarded.

## Fences honoured

No training. Factory seats never drained outside the two Rich-granted windows
(both revived snapshot-proven, probes green, clocks reset). continual-harness-lab
untouched. fleet-evals received zero writes (harness imported read-only).
specialist-agent strictly read-only. No NATS. Corpus private per DF-008.
Path-limited commits throughout, staged-stranger checks before each.

## Addendum — the output-wipe incident and the re-homing (same evening)

Launching the Rich-approved thin-shapes slice, a mangled shell backgrounding left
a first `agent.py` instance alive; with its checkpoint archived it declared a
fresh start and CLEANED `output/` recursively — wiping the day's corpus artifacts
(`output/harvest/`, `output/trace-export/`). Nothing unrecoverable was lost: the
bake-off record was committed under `domains/`, and both pipelines are
deterministic. **Structural lesson, now enforced: the generation loop OWNS
`output/` and cleans it on fresh start — corpus artifacts must never live under
it.** All corpus outputs are re-homed to `corpora/` (gitignored, DF-008): the
trace-export regenerated identically (93 filtered rows, zero leakage), the
harvest lift re-run into `corpora/harvest/` (same deterministic row identities;
the job-6 leakage discard re-applied on completion). The slice relaunches with
exclusive ownership of `output/` after the lift completes.

**Regeneration outcome (2026-08-12, closing the addendum):** the re-run yielded
17 accepted pre-gate (was 18) and the leakage gate discarded 4 (was 3) — **the
final corpus is 13 clean rows** in `corpora/harvest/train_harvest.jsonl`, with
12 quarantined and 8 in review. Deterministic row identities held; WHICH rows
clear the Coach varies at the margin between runs (temperature ~0.1 verdicts) —
the honest cost of the wipe was two marginal rows, both recoverable from
`rejected_rows.jsonl` review if ever wanted. Trace-export: 93 rows, identical.
