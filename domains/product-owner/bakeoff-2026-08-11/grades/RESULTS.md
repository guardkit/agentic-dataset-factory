# Bake-off results — the teacher decision (2026-08-11)

## The decision

**The generation teacher is T2 — the current production PO seat (`product-owner-agent`,
an alias of `qwen36-workhorse`).** By the pre-declared primary metric, gate-clean
count: T2 5/9, T1 3/9. No tie; tie-breakers not engaged. T3 was pre-declared
ineligible (frontier reference only).

**Operational consequence: corpus generation needs NO DeepSeek windows.** The winning
teacher serves on the GB10's own `:9000` — no drain, no fleet moves.

| Candidate | Gate-clean | Mean blocking findings | Clean artifacts |
|---|---|---|---|
| **T2 production seat (winner)** | **5/9** | **2.67** | EX-1, EX-2, EX-3, FS-2, GF-2 |
| T1 DeepSeek V4 Flash 0731 | 3/9 | 5.89 | GF-1, GF-2, GF-3 |
| T3 Claude reference (ineligible) | 0/9 | 45.78 | — |

## What the numbers say beyond the decision (observations, not re-litigation)

- **Perfect complementarity**: T1 swept greenfield 3/3 (with thinking enabled it was
  the only candidate to hold the full roadmap contract on every brief); T2 swept
  extract 3/3. Each failed where the other passed.
- **T1's failure classes are format discipline**: malformed JSON on two extract
  artifacts (temperature 1.0 per its own seat guidance), one fabricated-reference set
  (citing paths mentioned inside the source doc rather than the corpus), and the
  proposal format's one-Feature-block rule broken on all three spec artifacts.
- **T2's failure classes**: one degenerate 67-char response (GF-3), banned
  implementation language in spec steps (FS-1/FS-3), an assumptions floor miss
  (GF-1). These are exactly the per-row defects the generation loop's Coach gate and
  the PO-shaped distributional gates must catch in job 5.
- **T3's 0/9 is shape non-compliance** (no think blocks, no proposal banner), not
  content quality — recorded for calibration honesty: frontier quality does not
  excuse contract drift, which is the whole reason the serving contract is graded.

## Amendments history (both same-day, both uniform across candidates)

1. Harness corrections: GF inputs gained the production system prompt (captures bank
   only the user message); FS grader re-aimed at the proposal surface the inputs
   demand; T1 requests enabled thinking against the seat's `{"thinking":false}`
   default; reasoning field-name belt-and-braces. Round-1 artifacts preserved in
   `responses-r1/` + `grades-r1/`.
2. Greenfield grounding gate aligned to the prompt's own contract (`request:`
   references are required, not forbidden; fragments must quote the problem statement
   verbatim; filenames remain fabrications).

**Flagged for Rich:** the frozen exam task `po-held-004` hard-asserts empty
`source_documents` while the live prompt the exam assembles at run time demands
`request:` references — an exam-vs-prompt bind predating this lane (prompt convention
~07-11, exam gold 07-03). Reconciliation is Rich's ruling; the freeze law is
raise-only and this lane changed nothing in fleet-evals.

## The window record (two windows, both closed clean)

- Ritual: snapshot → drain both nodes → **thermal caps 2200 MHz (Rich's instruction)**
  → launch → gates → generate → teardown → revive proven against snapshots →
  functional probes non-empty → clocks reset.
- Window 1: 19/19 config greps PASS; served id pinned; B12X active; zero dropped
  shared-experts both nodes; KV pool 1.62M tokens; acceptance healthy; decode
  **80.2 tok/s at capped clocks** (above the 55–67 uncapped band); prefill 1787 tok/s.
- Thermals under sustained generation: Node A max **71°C**, Node B max **69°C** —
  versus the 85°C+/shutdown regime reported at stock clocks. The cap cost nothing
  measurable. (Candidate for permanence via a systemd unit — Rich's call.)
- Tool gates (5.6) skipped, recorded: zero tool traffic in this workload.
- Both fleets verified revived against their pre-drain snapshots; workhorse and
  tutor probes returned non-empty content; clocks reset to default.

## Disposal

No bake-off output enters the training corpus. fleet-evals received nothing.
