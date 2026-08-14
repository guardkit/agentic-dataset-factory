# The PO training corpus of record — manifest
## Assembled 2026-08-14 evening · all components quality-gated · training remains behind Rich's word

## The corpus: 323 rows, three components (all under `corpora/`, DF-008 private)

| Component | File | Rows | Provenance |
|---|---|---:|---|
| Harvest (real, Feb–May sessions) | `harvest/train_harvest.jsonl` | 13 | Deterministic answers from real artifacts; teacher (`product-owner-agent`) wrote only reasoning; 5 gates + leakage discard |
| Trace export (real, July production) | `trace-export/po_player_filtered.jsonl` | 93 | Mechanical M-22-redacted export of Coach-accepted iterations; 7-stage filter |
| Synthetic (gpt-oss-120b, 08-13/14 run) | `synthetic/train_synthetic.jsonl` | 217 | Factory generative loop, independent `gemma4-coach` gate, 300-target curriculum |

Never-train sidecars: `harvest/quarantine_golden_overlap.jsonl` (12), rejection/review
files per component, `synthetic-mirror/` (the run-time safety mirror).

## Combined coverage by shape

| Shape | Real | Synthetic | Total |
|---|---:|---:|---:|
| feature-spec | 39 | — | 39 |
| feature-plan | 34 | — | 34 |
| greenfield | 11 | 42 | 53 |
| idea | 4 | 44 | 48 |
| scope | 2 | 42 | 44 |
| evolve | 1 | 46 | 47 |
| impact | 0 | 43 | 43 |
| extract | 13 | — | 13 |
| other | 2 | — | 2 |
| **total** | **106** | **217** | **323** |

Real:synthetic ≈ 33:67. Every row base-model-neutral, stamped with source +
generator + provenance. The phased-extract shapes (extract:a/b) remain unbuilt —
extract coverage is the harvest's 13 real rows; the §5 seams are the named gap if
extraction depth ever proves thin at exam time.

## The two-Player datum (the identical 300-target curriculum, identical Coach)

| Player | Targets | Accepted | Rate | Notes |
|---|---:|---:|---:|---|
| gpt-oss-120b | 300 | 258 | **86%** | 694 turns, 36.6h; 42 rejects = 22 max-turns + 9 timeouts + 11 (reboot-lost run's tail) |
| qwen36 (production seat alias) | 270 | 129 | **48%** | The reboot-lost overnight run; datum banked, rows lost to the wipe |

The bake-off verdict (teacher-on-real-inputs) stands; this measures Coach-gated
synthetic authorship, where gpt-oss-120b is decisively stronger. Both live in the
record for any future teacher question.

## Gate results on the synthetic component (2026-08-14)

Exam-leakage NONE · duplicate assistant contents 0 · credential hits 0 ·
envelope/think defects 0 · mode balance idea 44 / greenfield 42 / evolve 46 /
impact 43 / scope 42 · top project-name share 6% (anti-monoculture bar 40%).

## Ledgered defect (adf loop, fix owed)

`write_output` validation drops Coach-ACCEPTED rows after 3 retries when the
Player invents a `metadata.topic` outside the GOAL enum — 41 accepted rows lost
this run (258 accepted, 217 written), banked NOWHERE. Fix sketch: fall back to
the nearest valid topic or bank to a sidecar; an accepted row must never vanish
on a metadata label.

## Status

The corpus is COMPLETE for the training word as ruled: real rows anchor the
covered shapes, synthetic fills the thin ones, the exam is frozen (with the
Option-A greenfield repair), and the student-candidate list amends to
"Gemma 4 AND Qwen 3.8" at the training sitting (plan item 6, 2026-08-13).
