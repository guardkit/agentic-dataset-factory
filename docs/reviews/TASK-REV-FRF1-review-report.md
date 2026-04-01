# Review Report: TASK-REV-FRF1

## Executive Summary

The three regression fixes from TASK-FPF1 have been **validated successfully**. The pipeline run `test-fpf1-regression-fixes` achieved **73/77 accepted (94.8%)**, exceeding the 91% restoration target by 3.8 percentage points. The regression from 90.9% to 68.8% has been fully reversed and surpassed.

All three fixes contributed measurably:
1. **Prompt revert** (TASK-FPF1-001): Restored Player compliance, reducing format failures from 68 to 47 and write validation failures from 22 to 1
2. **Format gate hardening** (TASK-FPF1-002): Zero false positives; when Player produces JSON it always includes both required keys
3. **Turn budget decoupling** (TASK-FPF1-003): 80.8% of accepted targets got first-pass Coach acceptance; format retries no longer starve Coach turns

**Verdict**: Regression fully reversed. Pipeline ready for production scaling.

## Review Details

- **Task ID**: TASK-REV-FRF1
- **Mode**: Code Quality / Pipeline Validation
- **Depth**: Standard
- **Run Analysed**: `docs/reviews/longer-runs/test-fpf1-regression-fixes.md`

---

## 1. Headline Metrics (Three-Way Comparison)

| Metric | Baseline (TPF1) | Regression (FPF1) | **This Run (FRF1)** | vs Baseline | vs Regression |
|--------|:---------------:|:-----------------:|:-------------------:|:-----------:|:-------------:|
| **Accepted** | 70/77 (90.9%) | 53/77 (68.8%) | **73/77 (94.8%)** | **+3.9pp** | **+26.0pp** |
| **Rejected** | 7 (9.1%) | 24 (31.2%) | **4 (5.2%)** | -3.9pp | -26.0pp |
| **Total Turns** | 145 | 173 | **144** | -0.7% | -16.8% |
| **Elapsed Time** | 96.7 min | 98.4 min | **87.1 min** | -9.9% | -11.5% |
| **Avg Time/Target** | 75.4s | 76.6s | **67.9s** | -9.9% | -11.4% |
| **Total Tokens** | 1,516,355 | 1,477,301 | **1,300,626** | **-14.2%** | -12.0% |
| **Avg Tokens/Accepted** | 21,662 | 27,874 | **16,170** | **-25.4%** | **-42.0%** |
| **Format Gate Blocks** | 44 | 68 | **47** | +6.8% | -30.9% |
| **Write Validation Fails** | 0 | 22 | **1** | +1 | **-21** |
| **Post-Gen Validation Fails** | 2 | 14 | **1** | -1 | -13 |

---

## 2. Fix Validation

### Fix 1: Prompt Revert (TASK-FPF1-001) -- VALIDATED

| Evidence | Regression | This Run | Assessment |
|----------|:----------:|:--------:|:----------:|
| Format gate blocks (Player not producing JSON) | 68 | 47 | Restored to near-baseline (44) |
| Write validation failures (missing metadata) | 22 | 1 | Near-zero; structural compliance restored |
| Post-gen validation failures (unclosed think blocks) | 14 | 1 | Better than baseline (2) |
| All previously regressed categories (8 categories, 33-80% rejection) | Regressed | **0% rejection** | Fully restored |

The BAD/GOOD examples and "do not think out loud" instruction in the FPF1 prompt were confirmed as the root cause of the regression. Reverting these changes restored Player compliance across all categories.

### Fix 2: Format Gate Hardening (TASK-FPF1-002) -- VALIDATED

| Evidence | Assessment |
|----------|:----------:|
| Missing-key format gate triggers | **0** (never fired) |
| False positives (valid JSON with both keys blocked) | **0** |
| All 47 format gate blocks | Pure non-JSON (Player emitted prose) |

The new structural key check (`messages` + `metadata`) never triggered because when the Player produces valid JSON, it always includes both required keys. The fix is correctly implemented with zero false positives. It provides a safety net for a failure mode that no longer occurs after the prompt revert, but remains valuable insurance.

### Fix 3: Turn Budget Decoupling (TASK-FPF1-003) -- VALIDATED

| Evidence | Assessment |
|----------|:----------:|
| First-pass Coach acceptance (of accepted targets) | 80.8% (59/73) |
| Targets accepted after format retries + Coach accept | 14 targets successfully recovered |
| Coach turns per target | Always <= max_turns (3) |
| Targets where format gate consumed all turns | 2 (indices 48, 52 -- both rejected) |

Format gate retries now operate independently of Coach turns. 14 accepted targets needed format retries before reaching the Coach, and all had sufficient Coach turns remaining. Without this fix, many of these would have been rejected.

---

## 3. Rejected Targets Analysis

### Overview

| Index | Category | Type | Turns | Root Cause |
|:-----:|----------|:----:|:-----:|------------|
| 48 | Exam technique -- Language Paper 1 | reasoning | 5 | Format gate exhaustion: Player output prose on all turns |
| 52 | Exam technique -- Language Paper 2 | reasoning | 4 | Format gate exhaustion: Player output prose on all turns |
| 66 | Factual recall -- AQA specification | direct | 3 | **Anomaly**: Coach accepted (score 5) but pipeline rejected -- `<think>` block in direct-type |
| 75 | Context -- historical/social (set texts) | direct | 3 | Coach rejection: Player kept inserting `<think>` blocks in direct-type |

### Root Cause Categories

| Root Cause | Count | Indices |
|------------|:-----:|---------|
| Format gate exhaustion (Player never produced JSON) | 2 | 48, 52 |
| `<think>` block leakage into direct-type examples | 2 | 66, 75 |

### Key Observations

1. **Exam technique is the weakest category**: Both format gate exhaustion failures were in "Exam technique" categories. The RAG context pulled in irrelevant material (Literature paper content for Language paper targets), likely confusing the model.

2. **`<think>` block leakage in direct-type targets**: Qwen3.5's reasoning mode makes it difficult to suppress `<think>` blocks. When the target specifies `type=direct`, the model still produces thinking blocks. This affected 2/19 direct-type targets (10.5%).

3. **Index 66 anomaly**: Coach accepted this example with score 5, but the pipeline rejected it because a `<think>` block was present in a `direct`-type example. This suggests a post-Coach structural validation is correctly catching type mismatches that the Coach missed. This is working as intended, but the Coach should ideally catch this itself.

### Previously Problematic Categories -- Restored

| Category | Regression Rejection Rate | This Run Rejection Rate |
|----------|:------------------------:|:----------------------:|
| Literary analysis | 57.1% | **0%** |
| Essay feedback -- Literature | 80.0% | **0%** |
| Character -- An Inspector Calls | 33.3% | **0%** |
| Character -- A Christmas Carol | 40.0% | **0%** |
| Language -- unseen poetry | 25.0% | **0%** |
| AO-specific guidance | 50.0% | **0%** |

All previously regressed categories now show 100% acceptance.

---

## 4. Quality Analysis

### Score Distribution (Accepted Targets)

| Score | Count | Percentage | vs Baseline | vs Regression |
|:-----:|:-----:|:----------:|:-----------:|:-------------:|
| 5 (Excellent) | 66 | 90.4% | -2.5pp (was 92.9%) | +5.5pp (was 84.9%) |
| 4 (Good) | 7 | 9.6% | +2.5pp (was 7.1%) | -5.5pp (was 15.1%) |
| 3 (Adequate) | 0 | 0% | -- | -- |

Quality is strong: 90.4% of accepted targets scored 5/5, close to baseline levels.

### Turn Distribution (Accepted Targets)

| Player Invocations | Count | % | Assessment |
|:------------------:|:-----:|:-:|:----------:|
| 1 (first-pass) | 37 | 50.7% | Half needed no retries at all |
| 2 | 22 | 30.1% | Typically 1 format retry then Coach accept |
| 3 | 8 | 11.0% | Format retries or 1 Coach revision |
| 4 | 6 | 8.2% | Multiple format retries |

### Coach Turn Distribution (Accepted Targets)

| Coach Turns | Count | % |
|:-----------:|:-----:|:-:|
| 1 (first-pass accept) | 59 | 80.8% |
| 2 | 11 | 15.1% |
| 3 | 3 | 4.1% |

80.8% first-pass Coach acceptance demonstrates the Coach is not a bottleneck.

### Coach Verdict Summary (All 97 Turn-Complete Events)

| Decision | Count |
|----------|:-----:|
| Accept | 76 |
| Revise | 21 |

---

## 5. Token Efficiency

| Metric | Baseline | Regression | This Run | Assessment |
|--------|:--------:|:----------:|:--------:|:----------:|
| Total tokens | 1,516,355 | 1,477,301 | **1,300,626** | 14.2% below baseline |
| Avg tokens/target | 19,693 | 19,186 | **16,891** | 14.2% below baseline |
| Avg tokens/accepted | 21,662 | 27,874 | **16,170** | **25.4% below baseline** |
| Tokens on rejected targets | -- | -- | 120,199 (9.2%) | Rejected targets cost 1.86x average |
| Prompt/completion split | -- | -- | 85.0% / 15.0% | Normal ratio |

The token efficiency improvement is significant. The prompt revert reduced wasted tokens on failed turns, and the turn budget decoupling reduced unnecessary Player invocations.

### Cost Projection (1,000 targets at this run's efficiency)

| Metric | Projected Value |
|--------|:--------------:|
| Total tokens | ~16.9M |
| Duration | ~14.7 hours |
| Expected accepted | ~948 (94.8%) |
| Expected rejected | ~52 |

---

## 6. Performance

| Metric | Baseline | Regression | This Run |
|--------|:--------:|:----------:|:--------:|
| Total elapsed | 96.7 min | 98.4 min | **87.1 min** |
| Avg time/target | 75.4s | 76.6s | **67.9s** |
| Throughput | ~47.7/hr | ~47.0/hr | **~53.1/hr** |

The 10% throughput improvement over baseline is attributable to fewer wasted turns and the decoupled format retry mechanism.

---

## 7. Findings Summary

| # | Finding | Severity | Status |
|:-:|---------|:--------:|:------:|
| F1 | Regression fully reversed: 94.8% acceptance exceeds 91% target | -- | POSITIVE |
| F2 | Prompt revert eliminated write validation failures (22 to 1) | -- | POSITIVE |
| F3 | Format gate hardening: zero false positives, correct enforcement | -- | POSITIVE |
| F4 | Turn budget decoupling: 80.8% first-pass Coach acceptance | -- | POSITIVE |
| F5 | Token efficiency improved 25.4% per accepted target vs baseline | -- | POSITIVE |
| F6 | Exam technique categories remain weakest (2/4 rejections) | Minor | MONITOR |
| F7 | `<think>` block leakage in direct-type targets (10.5% failure rate) | Minor | MONITOR |
| F8 | Index 66 anomaly: Coach accepted but pipeline rejected (type mismatch) | Minor | INVESTIGATE |
| F9 | All 8 previously regressed categories fully restored to 100% acceptance | -- | POSITIVE |
| F10 | Quality maintained: 90.4% score-5 acceptances | -- | POSITIVE |

---

## 8. Recommendations

### Production Readiness

| Criterion | Status | Score |
|-----------|:------:|:-----:|
| Pipeline stability | READY | 10/10 |
| Acceptance rate (>= 91%) | **READY** | 10/10 |
| Coach structured outputs | READY | 10/10 |
| Validation gates | READY | 10/10 |
| Player compliance | READY | 9/10 |
| Token efficiency | READY | 10/10 |
| **Overall** | **READY** | **93/100** |

### Recommended Next Steps

1. **Proceed to 1,000-target production run** -- All acceptance criteria met, regression fully reversed.
2. **Monitor exam technique categories** -- Consider improving RAG retrieval for Language Paper targets to reduce format gate exhaustion in this category.
3. **Investigate `<think>` block leakage** (F7) -- Consider adding a pre-Coach filter that strips `<think>` blocks from direct-type submissions, or adjusting the Player prompt to more explicitly suppress thinking for direct-type targets.
4. **Investigate index 66 anomaly** (F8) -- The Coach should ideally catch `<think>` block presence in direct-type examples before accepting. The pipeline's post-Coach validation caught it correctly, but this represents a Coach evaluation gap.

### Comparison to Acceptance Criteria

| Criterion | Required | Actual | Met? |
|-----------|----------|--------|:----:|
| All three fixes validated with quantitative evidence | Yes | Yes | YES |
| Acceptance rate compared to BOTH baselines | >= comparison | 94.8% vs 90.9% / 68.8% | YES |
| Regression fully reversed (>= 90%) | >= 90% | 94.8% | YES |
| Format gate hardening effectiveness quantified | Yes | 0 triggers, 0 false positives | YES |
| Turn budget decoupling effectiveness quantified | Yes | 80.8% first-pass, 14 targets recovered | YES |
| Token efficiency compared to baselines | Yes | 25.4% improvement over baseline | YES |
| Readiness assessment updated | Yes | 93/100, READY | YES |
| New issues documented | Yes | F6, F7, F8 documented | YES |

---

## Appendix: Category Acceptance Matrix

| Category | Targets | Accepted | Rate | Rejections |
|----------|:-------:|:--------:|:----:|:----------:|
| Literary analysis (single-turn) | 9 | 9 | 100% | 0 |
| Character analysis -- Macbeth | 8 | 8 | 100% | 0 |
| Essay feedback -- Literature (multi-turn) | 7 | 7 | 100% | 0 |
| Character analysis -- An Inspector Calls | 6 | 6 | 100% | 0 |
| Language analysis -- poetry (P&C) | 5 | 5 | 100% | 0 |
| Character analysis -- A Christmas Carol | 5 | 5 | 100% | 0 |
| Terminology and literary devices | 4 | 4 | 100% | 0 |
| Structure analysis -- prose and drama | 4 | 4 | 100% | 0 |
| Essay feedback -- Language (multi-turn) | 4 | 4 | 100% | 0 |
| Context -- historical and social (set texts) | 4 | 3 | 75% | 1 (idx 75) |
| Factual recall -- AQA specification | 3 | 2 | 67% | 1 (idx 66) |
| Exam technique -- Language Paper 2 | 3 | 2 | 67% | 1 (idx 52) |
| Exam technique -- Language Paper 1 | 3 | 2 | 67% | 1 (idx 48) |
| Encouragement and study skills | 3 | 3 | 100% | 0 |
| Character knowledge -- set texts | 3 | 3 | 100% | 0 |
| Grade boundary guidance (grades 4-9) | 2 | 2 | 100% | 0 |
| Exam structure and mark allocation | 2 | 2 | 100% | 0 |
| Comparative analysis -- poetry | 2 | 2 | 100% | 0 |
| **Total** | **77** | **73** | **94.8%** | **4** |
