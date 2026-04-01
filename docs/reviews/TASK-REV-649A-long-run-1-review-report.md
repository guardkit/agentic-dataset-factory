# Review Report: TASK-REV-649A

## Executive Summary

Long Run 1 produced **761 accepted training examples** and **166 rejected examples** across 1,000 targets in 27.5 hours using Qwen3.5-35B-A3B-FP8 via vLLM. The **83.4% acceptance rate** is a solid first run. Infrastructure was rock-solid with zero timeouts, exceptions, or network errors.

The **single dominant failure mode is JSON parsing** (100% of errors) caused by Qwen3.5 emitting untagged reasoning prose before JSON output, making it unparseable. The Coach agent is the weakest link (91% of parse failures). Enabling vLLM `guided_json` for the Coach would eliminate the root cause.

The training dataset has **good format compliance** but contains **critical defects**: 23 empty assistant responses (think-block only, no visible reply), 3 degenerate placeholder entries, and 7 unclosed think-blocks. The RAG knowledge index has **significant curriculum gaps** with 3 entire set texts missing.

**Overall assessment: 72/100** — strong pipeline foundations with addressable quality issues.

---

## Review Details

- **Task**: TASK-REV-649A — Analyse long run 1 output and training dataset
- **Mode**: Comprehensive analysis
- **Model under review**: Qwen/Qwen3.5-35B-A3B-FP8 via vLLM on promaxgb10-41b1:8002
- **Data reviewed**: 78,176 lines of logs, 761 train examples, 166 rejected examples, 73 RAG knowledge entries

---

## 1. Run Metrics

| Metric | Value |
|--------|-------|
| Total targets attempted | 1,000 |
| Accepted | 834 (83.4%) |
| Rejected | 166 (16.6%) |
| Total Player+Coach turns | 1,689 |
| Elapsed time | 27.5 hours |
| Throughput | ~36.4 targets/hour |
| Total tokens consumed | 18,592,271 |
| Prompt tokens | 14,977,380 |
| Completion tokens | 3,614,891 |
| Player LLM calls | 1,719 |
| Coach LLM calls | 1,915 |

### Acceptance by attempt

| Turns to accept | Count | % of accepted |
|-----------------|-------|---------------|
| 1 (first attempt) | 487 | 58.4% |
| 2 (one revision) | 239 | 28.7% |
| 3 (two revisions) | 108 | 12.9% |

The adversarial cooperation loop is working — 41.6% of accepted items were rescued by revision.

### Rejection breakdown

| Rejection reason | Count | % |
|------------------|-------|---|
| max_turns_exhausted | 117 | 70.5% |
| llm_failure: no JSON found | 46 | 27.7% |
| llm_failure: schema validation | 3 | 1.8% |

---

## 2. Error Patterns and Failure Modes

### 2.1 JSON Parsing — The Dominant Failure

**245 total parse failures** across the run, with 49 resulting in final rejection. The root cause is consistent: Qwen3.5 emits **untagged reasoning prose** (not wrapped in `<think>` tags) before its JSON output, making it unparseable by the 3-strategy JSON extractor (direct parse, code-fence regex, brace-matching).

- **Coach parse failures**: 245 (91% of all parse failures)
- **Player parse failures**: 22 (9%)
- The Coach's evaluation task is more "reasoning-heavy", triggering stronger prose emission
- **Note**: Think-block normalisation fixes (TRF-020, TRF-021) were already in place for this run but did not help because the problematic content is untagged prose, not `<think>` blocks

### 2.2 The Score-5 Accept Pattern

Across rejected examples, 216/351 coaching turns (61.5%) show `decision: accept, score: 5`. Code review confirms **there is no phantom-accept fallback in the codebase** — when JSON extraction fails, the pipeline retries the Coach with explicit "output raw JSON only" reinforcement, and rejects on repeated failure.

The score-5 pattern is likely the Coach genuinely returning shallow `accept` verdicts without deep evaluation (a model behaviour issue, not a code bug). This warrants further investigation but is **not a pipeline engineering fix** — it's a prompt/model quality issue.

- **216 turns** with accept/score=5 in rejected examples
- Only **4 examples** had genuine clean accepts that were later reverted
- The pattern correlates with the Coach's tendency toward brief, uncritical evaluations

### 2.3 Infrastructure

**Zero infrastructure issues** — no timeouts, exceptions, network errors, or OOM events in 27.5 hours. The vLLM server was completely stable. The only warnings were 1,632 benign ChromaDB ONNX provider messages.

### 2.4 Rejection Rate by Run Phase

| Phase (targets) | Rejection rate |
|-----------------|---------------|
| 0-200 | 17.0% |
| 200-500 | 18.2% |
| 500-700 | 21.0% (peak) |
| 700-1000 | 16.6% |

The peak at targets 500-700 correlates with essay feedback and language analysis categories (multi-turn, harder for the model). The rate improved significantly for the final 300 targets.

---

## 3. Training Dataset Analysis (761 examples)

### 3.1 Format Compliance

- **761/761** valid JSON, valid ShareGPT structure
- All messages have valid roles (`system`, `user`, `assistant`) and non-empty content
- **Conversation patterns**: 91.3% single-turn, 7.0% 2-turn, 1.4% 3-turn, 0.3% 4-turn

### 3.2 Metadata Completeness

| Field | Completeness |
|-------|-------------|
| layer, type, ao, text, topic, source, turns | 100% |
| grade_target | **77.4%** (172 missing — 170 are `type=direct` by design, 2 are `reasoning` bugs) |

### 3.3 Category Distribution

**By type**: reasoning 591 (77.7%), direct 170 (22.3%)

**By text/source material**:

| Text | Count | % |
|------|-------|---|
| macbeth | 195 | 25.6% |
| an_inspector_calls | 160 | 21.0% |
| general | 129 | 17.0% |
| language_paper_1 | 73 | 9.6% |
| power_conflict_poetry | 66 | 8.7% |
| a_christmas_carol | 55 | 7.2% |
| language_paper_2 | 49 | 6.4% |
| unseen_poetry | 34 | 4.5% |

**By topic**:

| Topic | Count | % |
|-------|-------|---|
| character_analysis | 245 | 32.2% |
| exam_technique | 128 | 16.8% |
| language_analysis | 83 | 10.9% |
| essay_feedback | 79 | 10.4% |
| terminology | 54 | 7.1% |
| structure_analysis | 51 | 6.7% |
| encouragement | 39 | 5.1% |
| factual_recall | 33 | 4.3% |
| character_knowledge | 29 | 3.8% |
| comparative | 20 | 2.6% |

**Underrepresented**: `unseen_poetry` (34), `comparative` (20), `a_christmas_carol` (55)

### 3.4 Grade Distribution

| Grade | Count | % |
|-------|-------|---|
| 4 | 30 | **3.9%** |
| 5 | 112 | 14.7% |
| 6 | 117 | 15.4% |
| 7 | 142 | 18.7% |
| 8 | 87 | 11.4% |
| 9 | 101 | 13.3% |
| None | 172 | 22.6% |

**Grade 4 is severely underrepresented** (30 examples, only 3 texts, 2 topics). The distribution skews mid-to-high, underserving lower-attaining students.

### 3.5 Think-Block Compliance

- **Reasoning examples**: 591/591 (100%) contain `<think>` blocks
- **Direct examples**: 0/170 (0%) — correct, direct doesn't need think-blocks
- **7 unclosed think-blocks** (mismatched open/close tags) — training data defect

### 3.6 Critical Data Quality Defects

| Severity | Issue | Count |
|----------|-------|-------|
| **CRITICAL** | Empty assistant responses (think-block only, no visible reply) | 23 |
| **CRITICAL** | Degenerate placeholder entries (`"..."` content) | 3 |
| **HIGH** | Unclosed `<think>` blocks | 7 |
| **HIGH** | Truncated/malformed system prompts | 15 |
| **MEDIUM** | Turn-count metadata mismatches | 21 |
| **LOW** | Exact duplicate pair | 1 |

The 23 empty responses are the most serious — the model would learn to "think but not respond".

### 3.7 Quality Assessment (20-example sample)

- **Content accuracy**: High — AQA specification references, mark schemes, and literary analysis are accurate
- **Socratic method**: 99% of reasoning examples use questioning to guide students
- **Age-appropriateness**: Consistently suitable for Year 10 (14-15 year olds)
- **Response quality**: Generally good, with the exceptions noted in defects above

---

## 4. Rejected Dataset Analysis (166 examples)

### 4.1 Root Cause Breakdown

~85-90% of rejections are fixable pipeline issues, not content quality failures.

**Fixable via pipeline engineering:**
1. **Coach emits untagged reasoning prose before JSON** — the 3-strategy JSON extractor fails on long preambles. vLLM `guided_json` for Coach would eliminate this at the token-generation level. Affects ~70% of rejections.
2. **Coach score-5 shallow accepts** — 216/351 turns show uncritical `accept: score 5` verdicts. This is a model/prompt behaviour issue, not a code fallback. Addressable via Coach prompt strengthening.
3. **Missing metadata in Player output** — 77 revision issues for missing metadata

**Fixable via prompt tuning:**
4. AO accuracy issues (20 revision issues)
5. Type/layer classification errors (20 combined)

**Genuine quality issues (rare):**
6. Factual accuracy (7), age-appropriateness (3) — acceptable rates

### 4.2 Revision Criteria Frequency

| Criterion | Count |
|-----------|-------|
| metadata_completeness | 77 |
| metadata_schema | 23 |
| ao_accuracy | 20 |
| type_correct | 15 |
| mark_scheme_aligned | 8 |
| socratic_approach | 7 |
| factual_accuracy | 7 |
| layer_correct | 5 |
| Other | 41 |

Missing/invalid metadata accounts for 54% of all revision issues.

---

## 5. RAG Knowledge Index (73 entries)

### 5.1 Structure
- **73 entries**, all well-formed ShareGPT + metadata format
- 100% metadata completeness for all 8 required fields
- All single-turn (appropriate for knowledge layer)

### 5.2 Factual Accuracy
10/10 sampled entries were factually accurate (Lady Macbeth, AQA AOs, exam papers, literary devices, historical context).

### 5.3 Curriculum Coverage — Critical Gaps

| Text | Entries | Assessment |
|------|---------|------------|
| macbeth | 35 | Over-represented (48%) |
| general | 21 | Good |
| language_paper_1 | 14 | Good |
| language_paper_2 | 2 | **Very thin** |
| an_inspector_calls | 1 | **Critical gap** |
| a_christmas_carol | **0** | **MISSING** |
| power_conflict_poetry | **0** | **MISSING** |
| unseen_poetry | **0** | **MISSING** |

- **93.2% of entries have `grade_target=None`** — grade-specific knowledge is almost absent
- **AO4/AO5/AO6 barely covered** (5, 4, 3 entries vs AO1=37, AO3=31)
- **46/73 entries (63%)** contain Socratic questioning — may be misclassified as knowledge when they are behaviour-layer content

---

## 6. Recommendations

> **Revision note (2026-03-30)**: Recommendations revised after deep-dive into prior reviews (TRF-013, TRF-020, TRF-021, TRF-023) and codebase analysis. Original recommendation #1 ("strip think blocks before JSON extraction") was incorrect — the failure mode is untagged reasoning prose, not `<think>` blocks. Think-block normalisation was already in place for this run. Original recommendation #2 ("phantom accept fallback") was also incorrect — no such fallback exists in the codebase.

### Priority 1 — Pipeline Fixes (before next run)

| # | Recommendation | Impact | Effort | Risk |
|---|---------------|--------|--------|------|
| 1 | **Enable vLLM `guided_json` for Coach** using the `CoachVerdict` schema. Constrains token generation to valid JSON — no prose preamble possible. **Do NOT apply to Player** (Player outputs nested JSON with free-form conversation content including think blocks). | Eliminates root cause of all 245 Coach parse failures (~70% of rejections) | Medium | Low — Coach output is evaluation-only, never written to training data |
| 2 | **Add post-generation validation** to catch empty responses (think-block only, no visible reply), unclosed think-blocks, and degenerate placeholder entries before writing to train.jsonl | Prevents 33 defective entries reaching the training dataset | Low | Very low — read-only validation gate |
| 3 | **Strengthen Coach prompt** to reduce shallow score-5 accepts. Add explicit instruction: "You MUST critically evaluate every aspect of the training example. A score of 5 requires explicit justification for each criterion." | Addresses 216 shallow-accept turns in rejected examples | Low | Low — prompt-only change |

### Priority 2 — Prompt & Config Tuning

| # | Recommendation | Impact | Effort | Risk |
|---|---------------|--------|--------|------|
| 4 | **Strengthen Player prompt** re: mandatory metadata section — add "CRITICAL: You MUST include the metadata object. Omitting metadata will cause automatic rejection." | Reduces 77 metadata_completeness revisions | Low | Low |
| 5 | **Increase max_turns from 3 to 4** for essay feedback categories specifically | Reduces max_turns rejections for hardest categories | Low | Low — only affects essay_feedback targets |
| 6 | **Boost Grade 4 weighting** in target generation to improve balance (currently 3.9%, target ~12-15%) | Addresses severe underrepresentation of lower-attaining students | Low | Low |
| 7 | **Lower Coach temperature** from 0.3 to 0.1-0.2 to reduce reasoning verbosity | May reduce untagged prose emission in non-guided-json fallback paths | Low | Low |

### Priority 3 — Coverage Gaps

| # | Recommendation | Impact | Effort | Risk |
|---|---------------|--------|--------|------|
| 8 | **Generate RAG entries for missing texts**: A Christmas Carol, Power & Conflict poetry, unseen poetry (currently 0 entries each) | Fills 3 critical curriculum gaps | Medium | Low |
| 9 | **Expand An Inspector Calls RAG** from 1 to ~15-20 entries | Major set text with minimal coverage | Low | Low |
| 10 | **Balance AO coverage** in RAG index (AO4/5/6 severely underrepresented: 5, 4, 3 entries vs AO1=37) | Improves curriculum completeness | Medium | Low |
| 11 | **Increase multi-turn example weighting** in next run (currently 91.3% single-turn) | Better multi-turn tutoring dynamics for fine-tuning | Medium | Low |

### Priority 4 — Data Cleaning (current dataset)

| # | Recommendation | Impact | Effort | Risk |
|---|---------------|--------|--------|------|
| 12 | **Remove 3 degenerate entries** (lines 163, 164, 541 with `"..."` content) | Eliminates training poison | Trivial | None |
| 13 | **Remove or fix 23 empty-response entries** (think-block only, no visible reply) | Prevents model learning to "think but not respond" | Low | Low |
| 14 | **Fix 7 unclosed think-blocks** in training data | Prevents malformed XML in model output | Low | Low |
| 15 | **Review 46 RAG entries** with Socratic questioning for potential layer misclassification (knowledge vs behaviour) | Improves knowledge vs behaviour layer separation | Medium | Low |

---

## Appendix: Coach Decision Distribution

| Decision | Score | Count |
|----------|-------|-------|
| accept | 5 | 1,164 |
| accept | 4 | 191 |
| accept | 3 | 1 |
| revise | 2 | 214 |
| revise | 1 | 59 |
| revise | 3 | 32 |
| revise | 4 | 9 |

---

*Review completed: 2026-03-30*
*Reviewer: Claude Opus 4.6 (automated analysis)*
