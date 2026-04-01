# Review Report: TASK-REV-TPF1

## Executive Summary

The post-params-fix run completed all **77 targets** with **zero pipeline errors** and **zero Coach parse failures** — a transformative improvement over Long Run 1 (245 parse failures, 83.4% acceptance) and test-fixes-run-1 (immediate crash on `guided_json`). The **90.9% acceptance rate** (70/77) validates that the TASK-LR1-012 structured outputs fix via `extra_body` + xgrammar backend has eliminated the dominant failure mode from Long Run 1.

The **new dominant failure mode is Player JSON compliance** — the Player agent (which lacks structured output constraints) produced 44 extraction failures across 33 targets, directly causing 6 of the 7 rejections. This is the highest-priority issue for the next production run.

**Overall assessment: 85/100** — major improvement over Long Run 1 (72/100). Pipeline infrastructure is production-ready; Player JSON compliance is the remaining bottleneck.

---

## Review Details

- **Task**: TASK-REV-TPF1 — Analyse test-run-after-params-fixes output
- **Mode**: Comprehensive analysis (code-quality + pipeline validation)
- **Parent Review**: TASK-REV-TFR1 (test-fixes-run-1, crash analysis)
- **Model under review**: Qwen/Qwen3.5-35B-A3B-FP8 via vLLM on promaxgb10-41b1:8002
- **Data reviewed**: 6,326 lines of logs, 70 accepted examples, 7 rejected examples

---

## 1. Run Metrics

| Metric | This Run | Long Run 1 | Delta |
|--------|----------|------------|-------|
| Targets | 77 | 1,000 | — |
| Accepted | 70 (90.9%) | 834 (83.4%) | +7.5pp |
| Rejected | 7 (9.1%) | 166 (16.6%) | -7.5pp |
| Total turns | 145 | 1,689 | — |
| Elapsed | 96.7 min | 27.5 hrs | — |
| Coach parse failures | **0** | **245** | **-100%** |
| Pipeline errors | **0** | 0 | — |
| Prompt tokens | 1,309,353 | 14,977,380 | — |
| Completion tokens | 207,002 | 3,614,891 | — |
| Total tokens | 1,516,355 | 18,592,271 | — |

### Acceptance by Turn

| Turns to accept | Count | % of accepted |
|-----------------|-------|---------------|
| 1 (first attempt) | 29 | 41.4% |
| 2 (one revision) | 28 | 40.0% |
| 3 (two revisions) | 13 | 18.6% |

58.6% of accepted examples required at least one revision — the adversarial cooperation loop is actively improving quality.

### Throughput

| Metric | Value |
|--------|-------|
| Avg time per target | 75.4s |
| Fastest target | 25s (index 27, Poetry analysis) |
| Slowest target | 160s (index 38, Essay feedback multi-turn) |
| Throughput | ~47.7 targets/hour |

---

## 2. Fix Validation

### 2.1 TASK-LR1-012: Structured Outputs via extra_body — VALIDATED

**Status: Complete success.**

- Log line 13 confirms: `"Coach structured_outputs schema enabled for local provider"`
- All 145 Coach responses used `coach_content_source: content (standard path)` — xgrammar constrained decoding delivered valid JSON through the standard content field every time
- Zero Coach parse failures (was 245 in Long Run 1)
- Zero prose preamble before Coach JSON (xgrammar enforcement working)
- The `extra_json` field contains the full `CoachVerdict` schema with all required fields (`decision`, `score`, `layer_correct`, `type_correct`, `criteria_met`, `issues`, `quality_assessment`)

### 2.2 TASK-LR1-002: Post-Generation Validation Gate — VALIDATED

**Status: Working as designed.**

The validation gate caught exactly 2 defects that the Coach missed:

| Index | Issue | Coach Verdict | Validation Result | Outcome |
|-------|-------|---------------|-------------------|---------|
| 41 | Unclosed think block (opens=1, closes=0) | accept/5 | REJECTED | Re-generated on next turn, accepted clean |
| 42 | Unclosed think block (opens=1, closes=0) | accept/5 | REJECTED | Re-generated on next turn, accepted clean |

Without this gate, 2 training examples with malformed think blocks would have entered the output file. The gate prevented data corruption.

### 2.3 TASK-LR1-003/004: Think-Block Prompt Changes — VALIDATED

**Status: Effective.**

Only 2 unclosed think-block warnings out of 145 turns (1.4%). Both were caught by the validation gate and corrected on the next turn. Think-block formatting compliance is overwhelmingly correct.

### 2.4 TASK-LR1-010: Other Wave 1 Fixes — VALIDATED

The structured output schema for the Coach works flawlessly across all 145 turns. The `coach_content_source` was consistently `content (standard path)`, confirming xgrammar-constrained output delivery is stable.

---

## 3. Rejection Analysis (7 Rejected Targets)

### 3.1 Rejection Summary

| Index | Category | Type | Failure Mode | Root Cause |
|-------|----------|------|-------------|------------|
| 29 | Language analysis — unseen poetry | reasoning | JSON extraction failed all 3 turns | Player prose preamble |
| 30 | Language analysis — unseen poetry | reasoning | JSON extraction failed all 3 turns | Player prose preamble |
| 31 | Language analysis — unseen poetry | reasoning | JSON extraction failed turns 2-3 | Player prose preamble |
| 54 | AO-specific guidance (AO1-AO6) | reasoning | JSON extraction failed turns 1, 3 | Player prose preamble |
| 55 | AO-specific guidance (AO1-AO6) | reasoning | JSON extraction failed turns 2-3 | Player prose preamble |
| 59 | Terminology and literary devices | direct | Coach revise on final turn | Genuine quality rejection |
| 70 | Encouragement and study skills | direct | JSON extraction failed turn 3 | Player prose preamble |

### 3.2 Failure Mode Breakdown

| Failure Mode | Count | % |
|-------------|-------|---|
| Player JSON extraction failure | 6 | 85.7% |
| Genuine quality rejection (Coach revise) | 1 | 14.3% |

### 3.3 Category Clustering

Strong clustering detected:

| Category | Targets | Rejected | Rejection Rate |
|----------|---------|----------|---------------|
| Language analysis — unseen poetry | 3 | 3 | **100%** |
| AO-specific guidance (AO1-AO6) | 2 | 2 | **100%** |
| Terminology and literary devices | 4 | 1 | 25% |
| Encouragement and study skills | 4 | 1 | 25% |
| All other categories (16) | 64 | 0 | 0% |

The "unseen poetry" category has the lowest RAG context (`result_len=1167` — least curriculum context of any category), suggesting insufficient grounding material contributes to Player formatting failures.

### 3.4 Player JSON Extraction Failures (Pipeline-Wide)

44 extraction failures occurred across 33 unique targets during the run:

- 26 targets recovered on retry (Player produced valid JSON on a subsequent turn)
- 7 targets failed all 3 turns and were rejected
- The Player frequently outputs reasoning prose (e.g., "The user wants me to generate...") before or instead of JSON
- This is a **Player-side compliance issue** — xgrammar only constrains the Coach

---

## 4. Quality Analysis

### 4.1 Score Distribution (70 Accepted)

| Score | Count | % |
|-------|-------|---|
| 4 | 5 | 7.1% |
| 5 | 65 | 92.9% |

### 4.2 All-Turn Score Distribution (145 Turns)

| Score | Count | % |
|-------|-------|---|
| 1 | 9 | 6.2% |
| 2 | 18 | 12.4% |
| 3 | 0 | 0% |
| 4 | 6 | 4.1% |
| 5 | 112 | 77.2% |

**Bimodal scoring pattern**: The Coach never gives score=3. It either hard-rejects (1-2) or fully accepts (4-5). This suggests the scoring rubric may benefit from calibration, but functionally the binary accept/revise behaviour is working correctly.

### 4.3 Comparison with Long Run 1

| Metric | This Run | Long Run 1 |
|--------|----------|------------|
| Acceptance rate | 90.9% | 83.4% |
| First-turn accept | 41.4% | 58.4% |
| Coach parse failures | 0 | 245 |
| Validation gate catches | 2 | N/A (not deployed) |

The lower first-turn accept rate (41.4% vs 58.4%) is likely due to the Player's JSON extraction failures forcing retries — the Coach is actually accepting on its first evaluation more consistently, but the Player needs formatting corrections.

---

## 5. Performance Analysis

### 5.1 Timing Distribution

| Metric | Value |
|--------|-------|
| Average per target | 75.4s |
| Median (estimated) | ~65s |
| Min | 25s |
| Max | 160s |
| Std dev (estimated) | ~35s |

### 5.2 Slowest Targets

| Index | Duration | Category | Cause |
|-------|----------|----------|-------|
| 38 | 160s | Essay feedback — Literature (multi-turn) | Multi-turn generation |
| 71 | 154s | Encouragement and study skills | 3-turn retry |
| 41 | 150s | Essay feedback — Literature (multi-turn) | Validation gate re-gen |
| 69 | 141s | Exam structure and mark allocation | 3-turn retry |
| 37 | 136s | Essay feedback — Literature (multi-turn) | Multi-turn generation |

No targets approached the 600s timeout. The pipeline is comfortably within time limits.

### 5.3 Token Efficiency

| Metric | Accepted (70) | Rejected (7) |
|--------|--------------|--------------|
| Avg tokens/target | 18,603 | 30,590 |
| Min | 9,915 | 28,892 |
| Max | 34,823 | 31,956 |

Rejected targets consume 64.4% more tokens on average because they exhaust all 3 turns. The 7 rejections consumed 214,130 tokens (16.4% overhead relative to accepted token budget).

### 5.4 Scaling Projection (77 → 1,000 Targets)

| Metric | 77 targets | 1,000 targets (projected) |
|--------|-----------|--------------------------|
| Duration | 96.7 min | ~20.9 hours |
| Tokens | 1.52M | ~19.7M |
| Accepted (at 90.9%) | 70 | ~909 |
| Rejected (at 9.1%) | 7 | ~91 |

The projected duration of ~21 hours fits within an overnight window. Token consumption is comparable to Long Run 1 (18.6M actual).

---

## 6. Recommendations

### Priority 1: Player JSON Compliance (Critical for Scale)

The Player produced 44 JSON extraction failures across the run. At 1,000 targets, this projects to ~570 extraction failures, wasting tokens and causing ~90 rejections.

**Options**:
1. **Enable structured outputs for Player** — Apply the same `extra_body` + xgrammar approach used for the Coach. This would eliminate the failure mode entirely but may constrain the Player's creative output.
2. **Stronger JSON-only prompting** — Reinforce the "output only JSON" instruction in the Player prompt with explicit examples and penalties.
3. **Improved JSON extraction** — Enhance the 3-strategy extractor to better find embedded JSON within prose output.

**Recommended**: Option 2 (stronger prompting) as first step, with Option 3 as fallback. Option 1 risks constraining multi-turn conversation generation.

### Priority 2: RAG Enrichment for Weak Categories

"Language analysis — unseen poetry" (100% rejection, `result_len=1167`) and "AO-specific guidance" (100% rejection) need more curriculum context in the RAG index.

**Action**: Add unseen poetry analysis techniques and AO-specific guidance content to the ChromaDB knowledge base before the production run.

### Priority 3: Coach Score Calibration (Low Priority)

The bimodal scoring (never score=3) is functional but limits diagnostic granularity. Consider adjusting the Coach prompt to encourage use of the full 1-5 range. This is cosmetic — the accept/revise decisions are correct.

---

## 7. Readiness Assessment: Overnight Production Run (77 → 1,000)

| Criterion | Status | Notes |
|-----------|--------|-------|
| Pipeline stability | **READY** | Zero errors, zero crashes across 77 targets |
| Coach structured outputs | **READY** | 145/145 valid JSON, zero parse failures |
| Validation gate | **READY** | Caught 2 defects Coach missed |
| Think-block compliance | **READY** | 1.4% failure rate, all caught by gate |
| Player JSON compliance | **AT RISK** | 44 extraction failures; 6/7 rejections caused by this |
| RAG coverage | **AT RISK** | 2 categories at 100% rejection due to thin context |
| Time budget | **READY** | Projected 21 hours fits overnight window |
| Token budget | **READY** | Projected 19.7M tokens is manageable |

**Verdict**: The pipeline is structurally ready for a 1,000-target overnight run. The two "AT RISK" items (Player JSON compliance, RAG coverage) are quality issues that will increase rejection count but will not cause pipeline failures. Fixing them before the run would improve the acceptance rate from ~90.9% to an estimated ~95%.

---

## Appendix: Wave 1 Fix Effectiveness Summary

| Fix | Task ID | Status | Evidence |
|-----|---------|--------|----------|
| Structured outputs via extra_body | TASK-LR1-012 | **COMPLETE SUCCESS** | 0 Coach parse failures (was 245) |
| Post-generation validation gate | TASK-LR1-002 | **WORKING** | Caught 2 unclosed think blocks |
| Think-block prompt changes | TASK-LR1-003/004 | **EFFECTIVE** | 1.4% failure rate (all caught by gate) |
| xgrammar backend | TASK-LR1-012 | **WORKING** | All Coach output constrained, no prose leakage |
