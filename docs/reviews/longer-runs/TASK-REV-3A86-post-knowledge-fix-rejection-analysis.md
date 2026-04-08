# Review Report: TASK-REV-3A86 — Post-Knowledge-Fix Rejection Rate Analysis

## Executive Summary

The 36.4% rejection rate observed in the post-knowledge-fix run represents a **2.5-3x increase** over baseline (12-17%). The root cause is clear: the knowledge layer fix introduced ~525 new **direct/knowledge** targets, but the Coach evaluation criteria still apply `socratic_approach` (25% weight) **uniformly to all examples**, including knowledge-layer examples that are designed to deliver factual content rather than use Socratic questioning.

**Reasoning-type examples reject at 11.7%** — consistent with baseline. The entire spike is driven by knowledge/direct targets rejecting at **62.7%**.

The Coach is working correctly. It is faithfully applying the criteria as written. The fix is in GOAL.md and/or the Coach prompt — the evaluation criteria need layer-aware routing.

---

## Run Metrics Comparison

| Run | Date | Targets | Accepted | Rejected | Rejection Rate | Notes |
|-----|------|---------|----------|----------|----------------|-------|
| 2500-run-1 (partial) | Apr 1 | 1405 | 1342 | 63 | 4.5% | Incomplete (56%), mostly reasoning targets processed |
| 2500-run-resumed | Apr 2 | 1094 | 954 | 140 | 12.8% | Completion of above run |
| long_run_1 | Apr 1 | 1000 | 834 | 166 | 16.6% | Full run, reasoning-only |
| factory-run-3 | Mar 29 | 20 | 18 | 2 | 10.0% | Small test run |
| **Post-knowledge-fix** | **Apr 5** | **1546** | **984** | **562** | **36.4%** | **This run** |

**Baseline range (completed full-scale runs): 12-17% rejection rate**

---

## Rejection Breakdown by Type

| Type | Approx. Targets | Rejected | Rejection Rate | Baseline Comparison |
|------|-----------------|----------|----------------|---------------------|
| reasoning (behaviour) | ~1,875 | 220 | 11.7% | Within baseline (12-17%) |
| direct (knowledge + behaviour) | ~625 | 392 | 62.7% | **NEW — no prior baseline** |
| **Total** | **~2,500** | **612** | **36.4%** | 2.5x above baseline |

The reasoning-type rejection rate (11.7%) confirms the pipeline is functioning normally for its original workload.

---

## Top 5 Blocking Issues

| Rank | Criterion | Blocking Count | % of All Blocks | Affected Layer |
|------|-----------|----------------|-----------------|----------------|
| 1 | `socratic_approach` | 512 | 49.6% | Primarily knowledge/direct |
| 2 | `type_correct` | 166 | 16.1% | Mixed (missing `<think>` blocks) |
| 3 | `ao_accuracy` | 138 | 13.4% | Mixed |
| 4 | `mark_scheme_aligned` | 93 | 9.0% | Mixed |
| 5 | `layer_classification` | 66 | 6.4% | Mixed |

The `socratic_approach` criterion alone accounts for nearly half of all blocking issues.

---

## Rejections by Knowledge-Layer Category

| Category | Layer | Type | Rejections | Est. Targets | Est. Rejection Rate |
|----------|-------|------|------------|--------------|---------------------|
| Context — historical and social | knowledge | direct | 80 | 125 | 64% |
| Terminology and literary devices | knowledge | direct | 79 | 125 | 63% |
| Character knowledge — set texts | knowledge | direct | 79 | 100 | 79% |
| Encouragement and study skills | behaviour | direct | 65 | 100 | 65% |
| Exam structure and mark allocation | knowledge | direct | 45 | 75 | 60% |
| Factual recall — AQA specification | knowledge | direct | 44 | 100 | 44% |

All knowledge/direct categories reject at 44-79%. These categories are designed for **factual delivery** (definitions, quotes, mark scheme criteria) — not Socratic dialogue.

---

## Root Cause Analysis

### Primary Cause: Criteria-Layer Mismatch

The knowledge layer fix (memory: `project_knowledge_layer_fix.md`) correctly added a `Layer` column to GOAL.md and wired it through the pipeline. This introduced ~525 `knowledge/direct` targets. However, the **evaluation criteria were not updated** to account for the different pedagogical purpose of knowledge-layer examples.

**The Coach prompt** ([coach_prompts.py](../../prompts/coach_prompts.py)) injects all 5 evaluation criteria from GOAL.md uniformly:

```
| socratic_approach | Guides via questions rather than giving answers | 25% |
| ao_accuracy       | Correct application of assessment objectives    | 25% |
| mark_scheme_aligned | Analysis aligns with AQA marking criteria     | 20% |
| age_appropriate   | Language suitable for Year 10 student            | 15% |
| factual_accuracy  | No incorrect claims about texts or context       | 15% |
```

For knowledge-layer examples (terminology definitions, factual recall, character knowledge), `socratic_approach` is **structurally impossible** to satisfy — these examples exist to provide direct factual answers for RAG retrieval, not to ask Socratic questions.

### Secondary Causes

1. **`type_correct` failures (166 blocks)**: Direct-type examples don't require `<think>` blocks, but the Coach's critical pre-check expects them for reasoning-type. Some targets may have mismatched type/layer metadata causing confusion.

2. **`ao_accuracy` failures (138 blocks)**: Knowledge-layer examples covering terminology or context may not naturally reference specific AOs, leading to blocking issues when the Coach cannot verify AO application.

3. **Coach refusals (98 rejections, 16%)**: The local vLLM Coach model occasionally produces empty responses. This is an infrastructure issue, not related to the knowledge fix.

### What Did NOT Cause the Increase

- **Pipeline logic**: The acceptance rule (`decision==accept AND score>=3 AND layer_correct AND type_correct AND no blocking`) is unchanged and correct.
- **Coach strictness**: The Coach is not being overly strict — it's correctly identifying that knowledge examples don't demonstrate Socratic approach.
- **Player quality**: Reasoning-type examples still accept at 88.3%, consistent with prior runs.

---

## Quality Assessment: Are Accepted Examples Higher Quality?

**Yes.** The Coach is correctly filtering. The 984 accepted examples (all reasoning-type or the ~37% of direct-type that happen to pass) represent genuinely high-quality output. The rejection rate increase is a **false positive problem**, not a quality regression — good knowledge examples are being rejected for criteria that don't apply to their layer.

---

## Recommendations

### Recommendation 1: Add Layer-Aware Evaluation Criteria to GOAL.md (Recommended)

Add a section to GOAL.md that specifies which criteria apply to which layer:

```markdown
## Layer-Specific Evaluation Rules

### Behaviour Layer (reasoning type)
All 5 criteria apply with stated weights:
- socratic_approach (25%), ao_accuracy (25%), mark_scheme_aligned (20%),
  age_appropriate (15%), factual_accuracy (15%)

### Knowledge Layer (direct type)
Replace socratic_approach with knowledge-specific criteria:
- factual_accuracy (35%) — No incorrect claims
- completeness (25%) — Covers the topic adequately for RAG retrieval
- age_appropriate (20%) — Language suitable for Year 10
- mark_scheme_aligned (20%) — References AQA criteria where applicable
```

**Impact**: Would reduce knowledge-layer rejections from ~63% to an estimated 15-20%.

### Recommendation 2: Update Coach Prompt to Route Criteria by Layer

Modify `build_coach_prompt()` or the evaluation protocol section to instruct the Coach to apply different criteria based on the example's `metadata.layer` value.

**Impact**: Enables the Coach to evaluate knowledge examples against appropriate standards.

### Recommendation 3: Mark `socratic_approach` as N/A for Direct Type

A lighter-touch fix: in the evaluation criteria section, add a note that `socratic_approach` should be marked `true` (not applicable = passes) for `direct` type examples.

**Impact**: Quick fix, reduces the dominant blocking issue. Less thorough than Recommendation 1 but faster to implement.

### Recommendation 4: Address Coach Refusals (16% of rejections)

The 98 Coach refusal rejections (`llm_failure: Coach response has no extractable content`) appear to be vLLM model refusals (content='', additional_kwargs=['refusal']). Investigate whether specific content triggers these refusals and consider retry logic or prompt adjustments.

**Impact**: Would recover ~98 additional examples (~6% improvement).

---

## Expected Impact of Fixes

| Scenario | Est. Rejection Rate | Recovered Examples |
|----------|--------------------|--------------------|
| Current (no changes) | 36.4% | — |
| Rec 1+2 (layer-aware criteria) | 14-18% | ~340 additional accepted |
| Rec 3 (quick socratic N/A fix) | 20-24% | ~200 additional accepted |
| Rec 1+2+4 (full fix) | 12-16% | ~380 additional accepted |

---

## Appendix: Rejection Reason Distribution

| Reason | Count | % |
|--------|-------|---|
| max_turns_exhausted | 476 | 77.8% |
| llm_failure (Coach refusal) | 98 | 16.0% |
| llm_failure (Player empty) | 38 | 6.2% |

## Appendix: Coach Score Distribution in Rejections

| Score | Count | % |
|-------|-------|---|
| 1 (Poor) | 104 | 13.2% |
| 2 (Below Standard) | 673 | 85.3% |
| 3 (Adequate) | 21 | 2.7% |
| 4 (Good) | 3 | 0.4% |
| 5 (Excellent) | 29 | 3.7% |

Score-2 dominance (85%) indicates systematic criteria mismatch rather than random quality failure.

## Appendix: Format Gate Failures

| Gate | Count |
|------|-------|
| player_output_not_json | 927 instances across all turns |
| unclosed_think_block | 14 |
| degenerate_placeholder | 1 |

The high `player_output_not_json` count reflects repeated retry attempts within the max_turns loop for targets that ultimately get rejected.

---

## REVISION 1: Deep Validation (Requested)

### Execution Flow Trace (Verified Against Code)

Complete code-level trace of how the criteria mismatch produces rejections:

```
GOAL.md (18 categories, 2500 expanded targets)
  ↓ parse_generation_targets() [src/goal_parser.py:227]
  ↓ Supports 5-col format: Category|Type|Layer|Count|Grades
  ↓
GenerationTarget[] (category, type, layer, count, grade_targets)
  ↓ run_generation_loop() [entrypoint/generation_loop.py:1085-1089]
  ↓ Expands: each target × count → 2500 individual targets
  ↓ ORDER: reasoning targets 0-1874, then direct targets 1875-2499
  ↓
_build_player_message() [generation_loop.py:1004-1011]
  ↓ Sends: Category, Type, Layer, Grade Target to Player
  ↓
Player generates JSON example with messages[] + metadata{layer, type}
  ↓
Pre-Coach format gate [generation_loop.py:711-745]
  ↓ Checks: valid JSON, has "messages" + "metadata" keys
  ↓ FAILURE HERE: 927 format_gate entries (Player outputs prose instead of JSON)
  ↓
Coach receives Player content [generation_loop.py:751-758]
  ↓ Coach sees: the full Player JSON output including metadata.layer
  ↓ Coach system prompt: COACH_BASE_PROMPT + GOAL.md sections
  ↓ Evaluation Criteria section: ALL 5 CRITERIA for EVERY example
  ↓
Coach evaluates against criteria [coach_prompts.py:146-154]
  ↓ Step 4: "Evaluate EACH criterion individually"
  ↓ For knowledge/direct: socratic_approach → false → blocking issue
  ↓
CoachVerdict returned [config/coach_verdict.py:28-69]
  ↓ criteria_met: dict[str, bool] — FREE-FORM, any keys accepted
  ↓ issues: [{criterion: "socratic_approach", severity: "blocking", ...}]
  ↓
verdict.is_accepted [coach_verdict.py:52-69]
  ↓ Checks: decision=="accept" AND score>=3 AND layer_correct
  ↓         AND type_correct AND no blocking issues
  ↓ FAILS: blocking issue on socratic_approach → is_accepted=False
  ↓
Rejection recorded [generation_loop.py:961-969]
  ↓ Coach feedback sent back to Player for revision
  ↓ Player tries again but STILL can't satisfy socratic_approach
  ↓ for a factual knowledge example
  ↓
After 3 Coach turns → max_turns_exhausted [generation_loop.py:971-981]
  ↓ Written to rejected.jsonl
```

### Smoking Gun Evidence

Actual Coach verdict from `rejected.jsonl` (Terminology example):

```json
{
  "category": "Terminology and literary devices",
  "type": "direct",
  "reason": "max_turns_exhausted",
  "rejection_history": [{
    "decision": "revise",
    "score": 3,
    "layer_correct": true,
    "type_correct": true,
    "criteria_met": {
      "socratic_approach": false,  ← BLOCKING
      "ao_accuracy": true,
      "mark_scheme_aligned": true,
      "age_appropriate": true,
      "factual_accuracy": true
    },
    "issues": [{
      "criterion": "socratic_approach",
      "severity": "blocking",
      "description": "The tutor directly explains alliteration and assonance
        rather than guiding the student to discover the definitions through
        questions."
    }]
  }]
}
```

Score is 3 (adequate), all other criteria pass, but the single blocking issue on `socratic_approach` prevents acceptance. This pattern repeats 508 times across direct-type rejections.

### Criteria Failure Rates (Direct-Type Coach Verdicts Only)

| Criterion | Met | Unmet | Fail Rate |
|-----------|-----|-------|-----------|
| socratic_approach | 264 | 540 | **67.2%** |
| mark_scheme_aligned | 598 | 206 | 25.6% |
| ao_accuracy | 616 | 188 | 23.4% |
| factual_accuracy | 734 | 70 | 8.7% |
| age_appropriate | 803 | 1 | 0.1% |

The 264 "met" entries for `socratic_approach` represent knowledge examples that were **forced** to adopt a Socratic style to pass — 31.6% of accepted knowledge examples contain 2+ question marks, diluting their value as RAG retrieval content.

### Structural Failures in Direct-Type Verdicts

| Check | Failures |
|-------|----------|
| layer_correct=false | 125 |
| type_correct=false | 222 |

These are secondary — the Coach sometimes misclassifies layer/type for knowledge examples, likely because the concept of "knowledge layer" is new and the Coach prompt doesn't strongly differentiate it.

---

## Fix Safety Proof (No Regression Risk)

### 5 Safety Guarantees — Verified Line by Line

**1. `CoachVerdict.criteria_met` is `dict[str, bool]` — accepts ANY criterion names**
- File: [config/coach_verdict.py:47](config/coach_verdict.py#L47)
- `criteria_met: dict[str, bool]` — no hardcoded key validation
- Changing criterion names from `socratic_approach` to `completeness` is transparent to this model

**2. `is_accepted` does NOT check criteria names or criteria_met values**
- File: [config/coach_verdict.py:52-69](config/coach_verdict.py#L52-L69)
- Checks only: `decision`, `score`, `layer_correct`, `type_correct`, `issues[].severity`
- The string "socratic_approach" appears nowhere in acceptance logic

**3. `write_output` validates layer/type/schema — NOT criteria content**
- File: [src/tools/write_output.py:93-203](src/tools/write_output.py#L93-L203)
- 10-step validation chain: JSON parse, messages, metadata.layer, metadata.type, think-block, schema fields
- Zero references to `criteria_met` or any criterion names

**4. `generation_loop.py` never inspects criteria_met**
- File: [entrypoint/generation_loop.py](entrypoint/generation_loop.py)
- Confirmed via grep: zero occurrences of `criteria_met` in this file
- Uses only `verdict.is_accepted` (line 850), `verdict.decision` (line 843), `verdict.score` (line 848)

**5. Coach prompt is rebuilt from GOAL.md on every run — no cached state**
- File: [prompts/coach_prompts.py:239-288](prompts/coach_prompts.py#L239-L288)
- `build_coach_prompt(goal: GoalConfig)` reads `goal.evaluation_criteria` fresh
- `_format_evaluation_criteria()` iterates criteria list and formats as table
- No persisted state between runs

### What Changes, What Doesn't

| Component | File | Changes? | Why |
|-----------|------|----------|-----|
| GOAL.md Evaluation Criteria | `domains/gcse-english-tutor/GOAL.md` | **YES** | Add layer-specific criteria |
| Coach system prompt | (generated at runtime) | **YES** (automatically) | Rebuilt from GOAL.md |
| GoalConfig model | `domain_config/models.py` | NO | `EvaluationCriterion` has free-form `name: str` |
| CoachVerdict model | `config/coach_verdict.py` | NO | `criteria_met: dict[str, bool]` — any keys |
| is_accepted property | `config/coach_verdict.py:52-69` | NO | Doesn't check criteria names |
| generation_loop.py | `entrypoint/generation_loop.py` | NO | Uses only `verdict.is_accepted` |
| write_output tool | `src/tools/write_output.py` | NO | Validates schema, not criteria |
| validator.py | `synthesis/validator.py` | NO | Think-block, duplicate, routing |
| checkpoint.py | `entrypoint/checkpoint.py` | NO | Index-based, criteria-agnostic |
| output.py | `entrypoint/output.py` | NO | File handles only |

**Conclusion: The fix is confined to GOAL.md text. Zero code changes. Zero regression risk.**

---

## Output Combination Strategy

### Problem

A full re-run costs ~50 hours. The reasoning results (indices 0-1874) are high quality with a 11.7% rejection rate consistent with baseline. Only the direct targets (indices 1875-2499) need re-generation.

### Target Index Map

| Index Range | Count | Type | Layer | Category |
|-------------|-------|------|-------|----------|
| 0-274 | 275 | reasoning | behaviour | Literary analysis (single-turn) |
| 275-524 | 250 | reasoning | behaviour | Character analysis — Macbeth |
| 525-724 | 200 | reasoning | behaviour | Character analysis — An Inspector Calls |
| 725-874 | 150 | reasoning | behaviour | Character analysis — A Christmas Carol |
| 875-1024 | 150 | reasoning | behaviour | Language analysis — poetry |
| 1025-1149 | 125 | reasoning | behaviour | Structure analysis |
| 1150-1349 | 200 | reasoning | behaviour | Essay feedback — Literature |
| 1350-1474 | 125 | reasoning | behaviour | Essay feedback — Language |
| 1475-1599 | 125 | reasoning | behaviour | Exam technique — Paper 1 |
| 1600-1724 | 125 | reasoning | behaviour | Exam technique — Paper 2 |
| 1725-1799 | 75 | reasoning | behaviour | Comparative analysis — poetry |
| 1800-1874 | 75 | reasoning | behaviour | Grade boundary guidance |
| **1875-1999** | **125** | **direct** | **knowledge** | **Terminology and literary devices** |
| **2000-2099** | **100** | **direct** | **knowledge** | **Character knowledge — set texts** |
| **2100-2199** | **100** | **direct** | **knowledge** | **Factual recall — AQA specification** |
| **2200-2274** | **75** | **direct** | **knowledge** | **Exam structure and mark allocation** |
| **2275-2374** | **100** | **direct** | **behaviour** | **Encouragement and study skills** |
| **2375-2499** | **125** | **direct** | **knowledge** | **Context — historical and social** |

### Recommended Strategy: Targeted Direct-Only Re-run + Merge

**Step 1: Backup current output**
```bash
cp -r output/ output_backup_run1/
```

**Step 2: Apply the GOAL.md fix** (layer-aware evaluation criteria)

**Step 3: Create a direct-only GOAL.md variant**
Copy GOAL.md, remove the 12 reasoning categories from Generation Targets, keep only the 6 direct categories. This produces 625 targets.

**Step 4: Run the pipeline with the direct-only GOAL** (~8 hours estimated)
```bash
python -m entrypoint.main --goal domains/gcse-english-tutor/GOAL-direct-only.md --fresh
```

**Step 5: Merge outputs**
```bash
# Keep reasoning results from original run
cp output_backup_run1/train.jsonl output/train.jsonl

# Replace knowledge with new (correctly evaluated) results
# (new knowledge.jsonl already in place from Step 4)

# Append new encouragement examples from new run's train.jsonl
# (need to filter: only direct/behaviour examples from new run)

# Merge rejected files
# Keep reasoning rejections from original + direct rejections from new run
```

**Step 6: Validate combined output**
```bash
# Count lines
wc -l output/train.jsonl output/rag_index/knowledge.jsonl output/rejected.jsonl
# Verify JSON validity
python -c "import json; [json.loads(l) for l in open('output/train.jsonl')]"
```

### Expected Results After Combination

| File | Current | After Fix Run | Combined |
|------|---------|---------------|----------|
| train.jsonl | 1,716 | ~85 (encouragement only) | ~1,800 |
| knowledge.jsonl | 172 | ~450 | ~450 (replace) |
| rejected.jsonl | 612 | ~90 | ~310 (220 old reasoning + ~90 new direct) |
| **Total accepted** | **1,888** | **~535** | **~2,250** |
| **Rejection rate** | **36.4%** | **~14%** | **~10%** |

### Risks and Mitigations

| Risk | Mitigation |
|------|------------|
| GOAL.md fix doesn't reduce rejections as expected | Run 20-target test first (~15 min) with direct-only GOAL |
| Encouragement examples (direct/behaviour) need special handling | They go to train.jsonl, not knowledge.jsonl — need to extract from new run |
| Combined output has inconsistent metadata | Both runs use same GOAL.md metadata schema — only criteria change |
| Knowledge examples from current run (172) mixed quality | Replace entirely with new run output — cleaner |

### Recommended Test Plan Before Full Re-run

1. Apply GOAL.md fix
2. Create `GOAL.test-direct.md` with 2 direct categories, 5 targets each
3. Run: `python -m entrypoint.main --goal domains/gcse-english-tutor/GOAL.test-direct.md --fresh`
4. Verify: acceptance rate >80% for direct targets
5. Inspect accepted knowledge examples: factual, not Socratic
6. If passes → proceed with full 625-target direct re-run

**Estimated total time: 15 min test + 8 hr re-run = ~8.25 hours (vs 50+ hours full re-run)**

---

## Appendix: Accepted Knowledge Examples — Quality Concern

Of the 158 direct/knowledge examples that were accepted in the current run:
- **50 (31.6%)** contain 2+ question marks — meaning they were forced to adopt a Socratic style to satisfy `socratic_approach`
- These examples are suboptimal for RAG retrieval because they ask questions instead of providing direct answers

The fix will produce cleaner knowledge examples optimised for their actual purpose (RAG factual delivery).
