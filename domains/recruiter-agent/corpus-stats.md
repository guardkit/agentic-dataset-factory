# Recruiter corpus — generation STATS

- Teacher seat(s): workhorse · author_reps: 12 · source run dir(s): run-full
- Attempted: **912** · accepted: **773** · rejected: **139** · deduped: **0** · contaminated: **3**
- Frozen corpus: **773 rows** (train 696 / val 77); dedup across runs 0
- Overall accept rate: **85%** (773/912 attempts)
- Checker pass rate (accepted vs checker-refused): **89%** — 91 draft(s) refused by the office's own validators (config-check / pipeline-validate)
- Admitted first-pass: **636** · after one bounded repair: **137** (82% first-pass clean)

## Rows per class vs the coverage plan

| Class | Sorting | Target | Frozen (train/val) | Attempts acc/rej | vs target |
|---|---|---:|---:|---:|:--|
| `clerk-from-examples` | clerk | 120 | 191 (172/19) | 191/25 | ✓ met |
| `pipeline-from-sentence` | pipeline | 90 | 113 (102/11) | 113/31 | ✓ met |
| `parameter-not-clerk` | parameter | 50 | 120 (108/12) | 120/0 | ✓ met |
| `missing-capability-wall` | missing-capability | 45 | 120 (108/12) | 120/0 | ✓ met |
| `honest-wall-not-faked` | honest-wall | 55 | 93 (84/9) | 93/27 | ✓ met |
| `placeholder-goldens` | placeholder-goldens | 40 | 96 (86/10) | 96/0 | ✓ met |
| `injection-probe` | injection-probe | 50 | 40 (36/4) | 40/56 | ⚠ 80% of target |
| **TOTAL** | | **450** | **773** | | **172% of plan** |

## Rejection-reason histogram (all run dirs)

| Reason bucket | Count |
|---|---:|
| checker: config-check failed | 51 |
| checker: pipeline-validate failed | 40 |
| sorting-rule mismatch | 14 |
| anchor cross-check mismatch | 12 |
| injection: granted egress/scope | 11 |
| other | 8 |
| contamination (eval-held) | 3 |

## Honest shortfalls (findings, not fudged)

- **`injection-probe`**: 40/50 (80% of target). Dominant reject reasons: checker: config-check failed (30), injection: granted egress/scope (11). From 8 seed briefs.

_val is a loss-only monitoring split (per-class-stratified, deterministic by row_id, disjoint), NOT the pass exam — the four banked sessions are the exam, never in this corpus (denylist enforced)._
