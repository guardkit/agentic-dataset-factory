# RECEIPT — Growth cycle 4 (2026-07-22; `--mode both`, factory_sha `ca40863`)

The first cycle to run **on top of** the two levers cycle 3 named: the per-repo `test_command`
pins (`ca40863` — jarvis spiked green, forge+nats_core honest expected-miss) and the study_tutor
DC-03 reject anchor + per-repo anchor-variant mechanism (`8ff7eb6`). Both worked exactly as
projected: they turned prior guard refusals into **real surfaced rejects** and, in doing so,
**recovered the balance band**.

## Corpus before → after (by side)

| Side | Cycle 3 | Cycle 4 | Δ |
|---|---|---|---|
| train | 61 | **77** | +16 |
| eval_qav | 15 | **17** | +2 |
| **TOTAL** | **76** | **94** | **+18 (+23.7%)** |

`_scratch`/`*.bak` bank the prior 76-row corpus; a full snapshot is
`output_backup_qav-growth-cycle4_20260722-155358`.

## Per-lane attribution (rows written, incl. eval routing)

| Lane | Cycle 3 | Cycle 4 | Δ | Note |
|---|---|---|---|---|
| **seeded_code** | 9 | **26** | **+17** | the growth engine — jarvis (`-k publishes` pin) + study_tutor (DC-03 `test_corpus_models.py` anchor) planted defects now SURFACE in the regenerated bundle instead of being refused |
| control (seeded-green) | 27 | 27 | 0 | steady |
| seeded_bundle | 6 | 7 | +1 | pool-gated (`seeded_bundle_no_provenance=52`, unchanged cap) |
| harvest | 30 | 30 | 0 | same consumables, 4 honestly skipped (queued/reviewer-in-loop) |
| gold negatives | 4 | 4 | 0 | all 4 in eval_qav (holdout intact) |

eval_qav (17) = seeded_code 5 · harvest 8 · gold_negative 4.
train (77) by generation_mode = seeded_code 48 · harvest 22 · seeded_bundle 7.

## Guard-refusal delta (vs cycle 3's 28)

**24 evidence_invariant_injection refusals — down 4 from 28.** The refusals are now concentrated
almost entirely in **guardkit**: its pin (`tests/orchestrator/test_wiring_seam_real_factory.py`) is
a single narrow seam that most planted DC-03/05 defects never reach, so those recipes regenerate a
bundle byte-identical to the no-op control and the guard honestly turns them away (no reject label
may ride evidence the defect never reached). jarvis, study_tutor and forge produced **zero** new
guard refusals — their pins surface cleanly. The guard is working as designed; the 24 are the
honest ceiling of guardkit's current pin, not a regression.

Full rejected.jsonl: `evidence_invariant_injection` 24 · `cue_leakage` 1 = 25.
teacher_refused=0 · coach_rejected=0 · schema_rejected=0 · deduped=6 · anchor_skipped=256 (was 268).

## Manifest verdict — HONEST, all laws PASS

- **contamination_check.status = `pass`** — row_id intersection 0, sibling-variant violations 0,
  gold-negative source-task violations 0.
- **balance RECOVERED → PASS.** `approve_share` **0.6721 (advisory FAIL, cycle 3) → 0.5325 (PASS)**,
  inside 0.50±0.10; `ugly_green_share_of_approves` 0.9512 (≥0.45). This is the predicted mechanism:
  the +17 seeded_code **rejects** pulled the approve share back into band — balance recovered by
  reject surfacing, not by massaging. train by_verdict: approve 41 / reject 36.
- by_dc_class: DC-03 23 · DC-08 6 · DC-14 7 (DC-05/DC-12 0). by_ground_truth_source: seeded 55 ·
  coach_correct 15 · merge_review_caught 4 · operator_caught 2 · live_gate_caught 1.
- visibility `private (DF-008)`; factory_sha `ca40863`; bundle_schema_sha `41a0ebe457`.
- **Self-verify (run this cycle): 94/94 rows re-validate against OUTPUT-CONTRACT (0 failures);
  standalone contamination gate VERDICT: PASS.**

## FLOOR CHECK (Option A: total ≥ 250 AND all laws passing)

**NOT ARMED — 94 < 250.** All laws pass (contamination, balance, contract), but the count floor is
not met. The tune does **not** start.

## Plateau verdict — NO PLATEAU (growth is real, decelerating)

+23.7% is down from cycle 3's +52%, but this is **not** a plateau: the **seeded_code lane nearly
tripled (9 → 26)** — the two new levers converted refusals into rows and healed the balance band in
the same move. The remaining, quantified ceiling to 250:

1. **guardkit's 24 refusals** — its wiring-seam pin is too narrow; needs a broader/per-recipe
   `test_command` (or DC-shaped anchors like study_tutor got) so its planted defects surface. This
   is the single largest recoverable block.
2. **seeded_bundle pool cap** (`no_provenance=52`) — grows only with future consumable ratifications.
3. **anchor_skipped=256** — recipe/anchor coverage still leaves most study_tutor+guardkit
   task×recipe cells unseeded; each new per-repo anchor variant (the `8ff7eb6` mechanism) converts a
   slice of these into candidates, as the study_tutor DC-03 anchor just demonstrated.

The loop continues toward 250; the next highest-yield lever is a guardkit pin/anchor pass mirroring
what just worked for jarvis and study_tutor.

## Ops

- `--mode both`, launched detached (nohup, PID 844387). Wall **14:21:58 → 15:51:23 = 1h29m25s**.
- Discovery: 28 source tasks included, 785 excluded (approved-sha honesty law, unchanged).
- **Serving posture = the round-3 thrash regime** (confirmed live): teacher `gpt-oss-120b` ↔ coach
  `qav-coach` mutually evict, so each model-touching row pays both cold loads (~30-100s load +
  generation). This is the run-time floor and a serving-posture artefact, not an engine cost — the
  batched-legs / co-residency fork remains the standing optimization if row-time ever gates.
- **Keepalive timer NEVER touched** (flock-guard unconditional posture; the keepalive script's flock
  guard makes co-residency safe) — `active` before, during, and after. No OOM. Services healthy.
- Self-verify + contamination gate run post-finish; both green.
