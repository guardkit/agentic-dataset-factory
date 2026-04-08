# Review Report: TASK-REV-CC01 — Coach Non-Compliance with Layer-Aware Criteria Routing

## Executive Summary

The Coach's 0% compliance with layer-specific criteria routing has a single, definitive root cause: **the routing instruction in GOAL.md is discarded during parsing and never reaches the Coach prompt**. The parser (`parse_table()`) extracts only table rows from the Evaluation Criteria section — the "### Layer-Specific Criteria Routing" prose is silently dropped. Additionally, two explicit instructions in the constructed prompt directly contradict routing:

1. **Base prompt** (line 72-73): "You MUST include ALL criteria from the Evaluation Criteria section"
2. **`_format_evaluation_criteria()`** appends: "You MUST include the following keys in your `criteria_met` response: `socratic_approach`, `ao_accuracy`, ..."

The Coach obeys these instructions faithfully, evaluating all 6 criteria for every example regardless of layer.

The Coach refusal issue (120 refusals, 51% of direct rejections) is a separate LLM-level problem — the vLLM model returns `content=''` with an `additional_kwargs['refusal']` key, indicating content policy or capability triggers.

---

## Review Details

- **Mode**: Architectural / Decision (hybrid)
- **Depth**: Standard
- **Task**: TASK-REV-CC01
- **Files Examined**: 6 source files + 2 output files + 1 prior review

---

## Root Cause Analysis

### Finding 1: Routing Instruction is Discarded During Parsing (CRITICAL)

**Evidence chain:**

1. **GOAL.md** (lines 81-88) contains:
   ```
   ### Layer-Specific Criteria Routing
   - **Behaviour layer**: Evaluate socratic_approach, ao_accuracy, ...
   - **Knowledge layer**: Evaluate ONLY factual_accuracy, completeness, ...
     Do NOT evaluate socratic_approach or ao_accuracy
   ```

2. **`parse_table()`** in [parser.py:224-319](domain_config/parser.py#L224-L319) processes only pipe-delimited table rows. All prose — including the routing subsection — is skipped because `"|" not in line`.

3. **`GoalConfig.evaluation_criteria`** is typed as `list[EvaluationCriterion]` — a flat list of criterion objects. There is no field for routing prose, conditional logic, or layer-criterion mappings.

4. **`_format_evaluation_criteria()`** in [coach_prompts.py:194-214](prompts/coach_prompts.py#L194-L214) reconstructs a table from the flat list and appends a "MUST include all keys" instruction listing all 6 criteria.

5. **COACH_BASE_PROMPT** (line 72-73) adds: "You MUST include ALL criteria from the Evaluation Criteria section in this dict."

**Result:** The Coach receives three explicit "include everything" instructions and zero routing instructions. 0% compliance is the expected outcome.

### Finding 2: The Coach Prompt As-Constructed

The Evaluation Criteria section the Coach actually receives:

```
## Evaluation Criteria

| Criterion Name | Description | Weight |
| --- | --- | --- |
| `socratic_approach` | Guides via questions rather than giving answers (behaviour layer only) | 0.25 |
| `ao_accuracy` | Correct application of assessment objectives (behaviour layer only) | 0.25 |
| `mark_scheme_aligned` | Analysis aligns with AQA marking criteria | 0.2 |
| `age_appropriate` | Language suitable for Year 10 student | 0.15 |
| `factual_accuracy` | No incorrect claims about texts, context, or terminology | 0.15 |
| `completeness` | Covers the topic adequately for RAG retrieval use (knowledge layer only) | 0.25 |

You MUST include the following keys in your `criteria_met` response:
`socratic_approach`, `ao_accuracy`, `mark_scheme_aligned`, `age_appropriate`,
`factual_accuracy`, `completeness`.
```

Note: The criterion descriptions contain "(behaviour layer only)" / "(knowledge layer only)" hints in the description text, but these are weak signals overwhelmed by the explicit "MUST include" instruction.

### Finding 3: Coach Refusal Issue (Separate Root Cause)

**120 refusals** (51% of direct rejections, 19.3% of all direct targets) are caused by the vLLM model returning empty content with a refusal signal:

```
llm_failure: Coach response has no extractable content:
content='', additional_kwargs keys=['refusal']
```

This affects direct targets disproportionately (120/125 total refusals = 96%). Probable cause: the Qwen 3.5-35B model's safety layer triggers on certain knowledge content (factual recall, exam structure, character knowledge) more frequently than on reasoning/Socratic content. This is a model-level issue, not a prompt engineering issue.

---

## Fix Approaches Evaluated

### Approach A: Code-Level Criteria Filtering (RECOMMENDED)

**Description:** Filter `goal.evaluation_criteria` by layer before passing to `_format_evaluation_criteria()`. Build two criteria lists — one for behaviour, one for knowledge — and select based on the current target's layer.

**Implementation:**
1. Add a `layer` field to `EvaluationCriterion` model (or parse layer hints from description)
2. Add `get_criteria_for_layer(layer: str) -> list[EvaluationCriterion]` to GoalConfig or coach_prompts
3. Pass the target's layer metadata to `build_coach_prompt()` (or build two prompt variants)
4. Update `_format_evaluation_criteria()` to only list applicable criteria
5. Update the "MUST include" instruction to list only applicable keys

| Attribute | Rating |
|-----------|--------|
| Effort | Medium (3-4 hours) |
| Risk | Low — changes are in prompt construction, not model or schema |
| Impact | High — eliminates the root cause; Coach will only see applicable criteria |
| Regression risk | Low — behaviour-layer prompts unchanged if filtering is correct |

**Trade-off:** Requires passing target layer through to prompt builder, adding a parameter to `build_coach_prompt()`.

### Approach B: Post-Verdict Filtering in Orchestrator

**Description:** After receiving a Coach verdict for a knowledge/direct example, ignore `socratic_approach` and `ao_accuracy` issues when evaluating `is_accepted`. Don't change the Coach prompt at all.

**Implementation:**
1. In `generation_loop.py`, after `_parse_coach_verdict()`, filter out inapplicable blocking issues
2. Recalculate acceptance based on filtered issues

| Attribute | Rating |
|-----------|--------|
| Effort | Low (1-2 hours) |
| Risk | Medium — Coach still wastes tokens evaluating irrelevant criteria; may lower scores unfairly |
| Impact | Medium — prevents false rejections but doesn't fix the evaluation quality |
| Regression risk | Low |

**Trade-off:** The Coach still evaluates `socratic_approach` for knowledge examples, potentially lowering scores and wasting tokens. The quality_assessment text will still mention Socratic deficiencies for direct examples, which is misleading.

### Approach C: Two-Table Format in GOAL.md

**Description:** Split the Evaluation Criteria table into two tables — one for behaviour, one for knowledge — and update the parser to handle both.

**Implementation:**
1. Restructure GOAL.md Evaluation Criteria with two sub-tables
2. Update `parse_table()` / `parse_goal_md()` to extract both tables
3. Add routing logic to coach_prompts.py

| Attribute | Rating |
|-----------|--------|
| Effort | High (6-8 hours) |
| Risk | Medium — parser changes affect all domains; test suite needs updating |
| Impact | High — clean separation at the domain config level |
| Regression risk | Medium — parser changes could break other GOAL.md files |

### Approach D: Prompt Restructuring (Move Routing to Prominent Position)

**Description:** Keep all criteria in the prompt but move the routing instruction to a more authoritative position (inside COACH_BASE_PROMPT or as a separate highlighted section).

| Attribute | Rating |
|-----------|--------|
| Effort | Low (1 hour) |
| Risk | High — Qwen 3.5-35B already ignores the routing instruction; moving it may still fail |
| Impact | Uncertain — depends on model's instruction following with conflicting directives |
| Regression risk | Low |

**Trade-off:** Still has "MUST include all keys" contradicting the routing instruction. Weak approach.

### Approach E: Hybrid (A + B)

**Description:** Implement code-level filtering (A) as the primary fix, with post-verdict filtering (B) as a defence-in-depth fallback.

| Attribute | Rating |
|-----------|--------|
| Effort | Medium (4-5 hours) |
| Risk | Low |
| Impact | Highest — eliminates root cause AND protects against partial compliance |
| Regression risk | Low |

---

## Decision Matrix

| Approach | Impact | Effort | Risk | Regression | Recommendation |
|----------|--------|--------|------|------------|----------------|
| A: Code-level filtering | High | Medium | Low | Low | **RECOMMENDED** |
| B: Post-verdict filtering | Medium | Low | Medium | Low | Good interim fix |
| C: Two-table GOAL.md | High | High | Medium | Medium | Overengineered for now |
| D: Prompt restructuring | Uncertain | Low | High | Low | Not recommended |
| E: Hybrid (A+B) | Highest | Medium | Low | Low | Best if time allows |

---

## Recommended Approach: A (Code-Level Criteria Filtering)

### Implementation Plan

**Step 1:** Add a `layer` tag to `EvaluationCriterion` (or derive it from description text containing "behaviour layer only" / "knowledge layer only").

**Step 2:** Add a `layer` parameter to `build_coach_prompt()`:
```python
def build_coach_prompt(goal: GoalConfig, target_layer: str = "behaviour") -> str:
```

**Step 3:** Filter criteria before formatting:
```python
applicable = [c for c in goal.evaluation_criteria
              if _criterion_applies_to_layer(c, target_layer)]
```

**Step 4:** Update `_format_evaluation_criteria()` output to list only applicable criteria in the "MUST include" instruction.

**Step 5:** Update `generation_loop.py` to pass the target's layer when building/selecting the Coach prompt.

**Step 6:** Update COACH_BASE_PROMPT line 72-73 to say "include all criteria listed below" (not "ALL criteria from the Evaluation Criteria section") since the section now only contains applicable criteria.

### Re-Run Assessment

- **A new run is required** to benefit from this fix — it cannot be applied post-hoc to existing rejected data
- Post-verdict filtering (Approach B) *could* be applied to the existing rejected.jsonl as a recovery script, but this would not improve quality_assessment text
- Estimated impact: direct rejection rate should drop from ~63% to ~20-25% (removing socratic_approach as a blocking criterion)

### Coach Refusal Mitigation

The 120 refusals are a separate issue. Options:
1. **Retry with longer timeout** — may help if refusals are intermittent
2. **Reduce content length** — direct/knowledge examples may exceed context limits
3. **Model configuration** — check vLLM safety/content filtering settings for Qwen 3.5-35B
4. **Fallback model** — use a different model for Coach evaluation of knowledge content

This should be tracked as a separate task.

---

## Acceptance Criteria Verification

- [x] Root cause determination with evidence (prompt trace, model behaviour analysis)
- [x] Coach prompt as-constructed included in review (full text of Evaluation Criteria section)
- [x] At least 3 fix approaches evaluated with effort/risk/impact (5 evaluated)
- [x] Recommended approach with implementation plan
- [x] Assessment of whether fix requires another re-run (yes, re-run required)
- [x] Coach refusal analysis (separate from compliance) with mitigation options
- [x] Review document written to `docs/reviews/`
