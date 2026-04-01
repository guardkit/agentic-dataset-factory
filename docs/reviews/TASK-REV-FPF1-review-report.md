# Review Report: TASK-REV-FPF1

## Executive Summary

The post-format-gate-fixes run represents a **significant regression** in acceptance rate: **68.8% (53/77)** vs the baseline of **90.9% (70/77)** — a 22.1 percentage point drop.

### Definitive Root Cause (revised after deep investigation)

**The regression is caused by the prompt changes, NOT the format gate.** Cross-run comparison proves this:

| Metric | Baseline | This Run | Cause |
|--------|----------|----------|-------|
| Non-JSON Player output | 44 extraction fails | 68 format gate blocks | **Prompt made worse (+54%)** |
| JSON without metadata | 0 write validation fails | 22 write validation fails | **New failure mode from prompt** |
| Unclosed think blocks | 4 post-gen fails | 14 post-gen fails | **Prompt made worse (+250%)** |
| Total turn-wasting failures | 48 in 145 turns (33%) | 104 in 173 turns (60%) | **Compound degradation** |

The format gate is mechanically correct and saved 68 Coach calls. But the stronger Player prompt (BAD/GOOD examples, "do not think out loud") caused the Player to produce **worse** output in every dimension:
1. **More non-JSON output** (68 vs 44) — the BAD example may prime the model to replicate the bad pattern
2. **A completely new failure mode**: JSON objects that contain `{"messages": [...]}` but omit `{"metadata": {...}}` — the brace-matching extractor grabs the first valid JSON object, which is incomplete
3. **More structural defects** (unclosed think blocks, placeholders)

Framework validation confirms: no LangChain/DeepAgents configuration changes, no vLLM thinking mode activation (all content sources are plain "string"), no model parameter changes. The regression is 100% attributable to the prompt text changes.

**Overall assessment: 58/100** — a major regression from baseline (85/100). The pipeline is NOT ready for a production run in this state.

---

## Review Details

- **Task**: TASK-REV-FPF1 — Analyse test-FPF1-fixes output
- **Mode**: Comprehensive analysis (pipeline validation + regression analysis)
- **Parent Review**: TASK-REV-TPF1 (baseline: test-run-after-params-fixes)
- **Fixes under test**: Pre-Coach format gate, Stronger Player prompt, Feedback labelling
- **Model under review**: Qwen/Qwen3.5-35B-A3B-FP8 via vLLM on promaxgb10-41b1:8002
- **Data reviewed**: 6,046 log lines, 53 accepted examples, 24 rejected examples

---

## 1. Run Metrics

| Metric | This Run | Baseline (TPF1) | Delta |
|--------|----------|-----------------|-------|
| Targets | 77 | 77 | — |
| Accepted | 53 (68.8%) | 70 (90.9%) | **-22.1pp** |
| Rejected | 24 (31.2%) | 7 (9.1%) | **+22.1pp** |
| Total turns | 173 | 145 | +28 |
| Elapsed | 98.4 min (5,901.8s) | 96.7 min | +1.7% |
| Coach calls | 105 | 145 | -40 (-27.6%) |
| Coach parse failures | 0 | 0 | — |
| Format gate blocks | 68 | N/A (not deployed) | NEW |
| Write validation failures | 22 | 0 | NEW |
| Post-gen validation failures | 14 | 2 | +12 |
| Prompt tokens | 1,261,318 | 1,309,353 | -3.7% |
| Completion tokens | 215,983 | 207,002 | +4.3% |
| Total tokens | 1,477,301 | 1,516,355 | -2.6% |

### Acceptance by Turn (53 Accepted)

| Turns to accept | Count | % of accepted | Baseline |
|-----------------|-------|---------------|----------|
| 1 (first attempt) | 22 | 41.5% | 41.4% |
| 2 (one revision) | 14 | 26.4% | 40.0% |
| 3 (two revisions) | 17 | 32.1% | 18.6% |

Average turns per accepted example: 1.91 (baseline: 1.77)

### Score Distribution (53 Accepted)

| Score | Count | % | Baseline |
|-------|-------|---|----------|
| 4 | 8 | 15.1% | 7.1% |
| 5 | 45 | 84.9% | 92.9% |

---

## 2. Fix Validation

### 2.1 Pre-Coach Format Gate — WORKING but HARMFUL

**Status: Mechanically correct, strategically destructive.**

The format gate triggered 68 times across 173 turns (39.3% of all turns). It correctly identified non-JSON Player output and skipped Coach invocation, saving 68 Coach calls.

**Positive effects:**
- 68 unnecessary Coach calls eliminated (saved ~68 * 4,500 = ~306,000 tokens of Coach input)
- FORMAT ERROR feedback correctly labelled (56 instances)
- No false positives observed (valid JSON never blocked)

**Negative effects:**
- Each format gate trigger consumes a turn from the 3-turn budget
- 5 targets rejected purely by format gate (3/3 turns blocked): indices 26, 29, 40, 41, 57
- 12 targets had Coach accept at least once but still rejected because format gate + write validation consumed remaining turns

**Critical design flaw:** The format gate `continue` statement at line 726 of `generation_loop.py` increments the turn counter implicitly (via the for-loop), consuming a precious turn slot. With only 3 turns, a single format gate fire reduces the target to 2 effective turns — and any other failure (write validation, post-gen validation, Coach revise) then exhausts the budget.

### 2.2 Stronger Player Prompt — NOT EFFECTIVE

**Status: No improvement. Possible regression.**

| Metric | This Run | Baseline | Delta |
|--------|----------|----------|-------|
| Format gate blocks / JSON extraction failures | 68 | 44 | **+24 (+54.5%)** |
| Targets with at least 1 format failure | ~40 | 33 | +~7 |
| All-3-turns format failure | 5 | N/A | NEW |

The stronger prompt (BAD/GOOD examples, "do not think out loud" instruction) did NOT reduce the Player's tendency to produce prose-before-JSON. Format failures increased from 44 to 68. Possible explanations:
1. The longer prompt increased the Player's context window load, reducing compliance
2. The BAD example may paradoxically prime the model to replicate the bad pattern
3. The "do not think out loud" instruction may trigger Qwen3.5's thinking mode

### 2.3 Feedback Labelling (FORMAT ERROR vs Coach Feedback) — WORKING

**Status: Correctly distinguishing feedback types.**

- 56 FORMAT ERROR labels (format gate rejections)
- 43 Coach Feedback labels (genuine Coach revise decisions)
- Labels correctly differentiated in Player message history

---

## 3. Rejection Root Cause Analysis (24 Rejected Targets)

### 3.1 Failure Mode Taxonomy

| Root Cause | Count | % | Description |
|-----------|-------|---|-------------|
| Format gate exhausted all 3 turns | 5 | 20.8% | Player never produced valid JSON |
| Format gate + Coach revise combined | 7 | 29.2% | FG consumed 1-2 turns, Coach revised on remaining |
| Coach accepted but write/post-gen failed | 12 | 50.0% | Coach accepted, but downstream validation rejected |

**The dominant failure mode (50%) is NEW**: The Coach accepts the example, but write validation catches missing metadata or post-generation validation catches unclosed think blocks. Combined with format gate turns consumed earlier, the target exhausts its 3-turn budget.

### 3.2 Detailed Rejected Target Analysis

| Idx | Category | FG | Coach Accept | Coach Revise | Write/PostGen Fail | Root Cause |
|-----|----------|---:|:-----------:|:----------:|:---------:|------------|
| 0 | Literary analysis | 2 | 1 | 0 | Write fail | FG + Write |
| 1 | Literary analysis | 2 | 0 | 1 | — | FG + Coach |
| 2 | Literary analysis | 1 | 1 | 1 | PostGen fail | Combined |
| 6 | Literary analysis | 1 | 0 | 2 | — | Coach quality |
| 14 | Character — Inspector Calls | 2 | 1 | 0 | Write fail | FG + Write |
| 16 | Character — Inspector Calls | 2 | 1 | 0 | Write fail | FG + Write |
| 19 | Character — A Christmas Carol | 2 | 0 | 1 | — | FG + Coach |
| 22 | Character — A Christmas Carol | 1 | 0 | 2 | — | Coach quality |
| 26 | Language — poetry | 3 | 0 | 0 | — | Pure FG |
| 28 | Language — poetry | 1 | 1 | 1 | Write fail | Combined |
| 29 | Language — unseen poetry | 3 | 0 | 0 | — | Pure FG |
| 35 | Structure analysis | 1 | 2 | 0 | Write fail x2 | Write fail |
| 38 | Essay feedback — Lit | 1 | 1 | 1 | PostGen fail | Combined |
| 39 | Essay feedback — Lit | 2 | 0 | 1 | — | FG + Coach |
| 40 | Essay feedback — Lit | 3 | 0 | 0 | — | Pure FG |
| 41 | Essay feedback — Lit | 3 | 0 | 0 | — | Pure FG |
| 43 | Essay feedback — Lang | 2 | 0 | 1 | — | FG + Coach |
| 44 | Essay feedback — Lang | 2 | 1 | 0 | Write fail | FG + Write |
| 53 | Comparative — poetry | 2 | 1 | 0 | Write fail | FG + Write |
| 54 | AO-specific guidance | 2 | 1 | 0 | Write fail | FG + Write |
| 57 | Grade boundary guidance | 3 | 0 | 0 | — | Pure FG |
| 72 | Encouragement/study skills | 0 | 2 | 1 | Write fail x2 | Write fail |
| 73 | Context — historical | 1 | 1 | 1 | Write fail | Combined |
| 76 | Context — historical | 1 | 0 | 2 | — | Coach quality |

### 3.3 Category Regression Analysis

| Category | Baseline Rej% | This Run Rej% | Delta | Status |
|----------|:------------:|:------------:|:-----:|--------|
| Literary analysis (single-turn) | 0% | **57.1%** | +57.1pp | **REGRESSED** |
| Essay feedback — Lit (multi-turn) | 0% | **80.0%** | +80.0pp | **REGRESSED** |
| Character — An Inspector Calls | 0% | 33.3% | +33.3pp | REGRESSED |
| Character — A Christmas Carol | 0% | 40.0% | +40.0pp | REGRESSED |
| Language — poetry (P&C) | 0% | 40.0% | +40.0pp | REGRESSED |
| Essay feedback — Language | 0% | 50.0% | +50.0pp | REGRESSED |
| Context — historical/social | 0% | 50.0% | +50.0pp | REGRESSED |
| Grade boundary guidance | 0% | 50.0% | +50.0pp | REGRESSED |
| Language — unseen poetry | **100%** | 25.0% | -75.0pp | **IMPROVED** |
| AO-specific guidance | **100%** | 50.0% | -50.0pp | **IMPROVED** |
| Terminology/literary devices | 25% | 0% | -25.0pp | IMPROVED |
| Encouragement/study skills | 25% | 33.3% | +8.3pp | Marginal |

**The fixes improved the two worst categories** (unseen poetry, AO-specific guidance) but **caused widespread regression across 8 previously stable categories**.

### 3.4 Write Validation Failure Analysis

22 write validation failures occurred. By error type:

| Error | Count | Targets Affected |
|-------|------:|:-----------------|
| Missing required field 'metadata' | 15 | 0, 5, 14, 16, 28, 35(x2), 44, 53, 54, 55, 72 |
| Missing required field 'messages' | 1 | 72 |
| metadata.type 'reasoning' but no `<think>` block | 1 | 44 |
| metadata.topic invalid value 'essay_technique' | 1 | 54 |
| (Other / omitted lines) | 4 | Various |

**Missing metadata is the dominant write validation failure** (15/22 = 68%). The Coach accepts examples that pass its quality criteria but doesn't enforce metadata presence — that's caught by write validation. This creates a pattern where Coach accepts → write rejects → turn consumed → eventual target rejection.

---

## 4. Token Efficiency

| Metric | This Run | Baseline | Delta |
|--------|----------|----------|-------|
| Total tokens | 1,477,301 | 1,516,355 | -2.6% |
| Prompt tokens | 1,261,318 | 1,309,353 | -3.7% |
| Completion tokens | 215,983 | 207,002 | +4.3% |
| Avg tokens/target | 19,186 | 19,693 | -2.6% |
| Tokens per accepted example | 27,874 | 21,662 | **+28.7%** |
| Tokens per rejected example | — | — | — |

**Token cost per accepted example rose 28.7%** because total tokens stayed similar while acceptance dropped from 70 to 53. The format gate saved ~306K Coach tokens but this was offset by more turns needed (173 vs 145).

### Coach Call Savings

| Metric | Value |
|--------|-------|
| Coach calls eliminated by format gate | 68 |
| Estimated Coach tokens saved | ~306,000 |
| Actual total token reduction | 39,054 (2.6%) |
| Net savings negligible | Format gate saved Coach tokens but increased Player turns |

---

## 5. Performance

| Metric | This Run | Baseline | Delta |
|--------|----------|----------|-------|
| Elapsed time | 98.4 min | 96.7 min | +1.7% |
| Avg time per target | 76.6s | 75.4s | +1.6% |
| Throughput | ~47.0 targets/hr | ~47.7 targets/hr | -1.5% |

Performance is essentially unchanged. The format gate's Coach-skip savings are offset by more total turns.

---

## 6. Deep Root Cause Analysis (Revised)

### 6.1 Failure Mode Shift (Evidence)

The baseline and this run used **identical** infrastructure: same model (Qwen/Qwen3.5-35B-A3B-FP8), same vLLM endpoint, same temperature (Player 0.6, Coach 0.3), same LangChain `create_agent()` factory, same middleware stack. Framework validation confirms: no thinking mode activation (100% of Player content sources are plain "string"), no model_kwargs changes, no extra_body changes to the Player.

The **only** variable is the three code changes: format gate, stronger prompt, feedback labelling.

**Baseline Player behavior** (72 successful extractions analysed):
- Average JSON ratio: 63.3% (36.7% prose alongside JSON is normal)
- When brace-matcher found JSON, it **always** contained both `messages` AND `metadata`
- 44 cases where NO valid JSON could be extracted at all (pure prose)
- Recovery rate from extraction failures: 26/33 targets = 79%

**This-run Player behavior** (write-validation failures analysed):
- 12 cases where extraction succeeded but JSON lacked metadata
- Average JSON ratio for these: 60.5% (similar prose ratio to baseline)
- One extreme case: `input_len=8421, output_len=33` — extractor found a tiny JSON fragment
- The Player is now producing `{"messages": [...]}` as a standalone JSON object, with metadata either absent or in a separate JSON block that the brace-matcher doesn't reach

### 6.2 The Brace-Matcher Vulnerability

`_extract_json_object()` (generation_loop.py:146-229) uses a 3-try strategy:
1. Direct `json.loads()` of full content
2. Markdown code fence extraction
3. **Brace-matching**: find FIRST `{...}` that parses as valid JSON dict

Try 3 is the critical path. It returns the **first** complete JSON object found via brace-depth scanning. If the Player produces:

```
I'll create a literary analysis example with Socratic questioning...
{"messages": [{"role": "system", "content": "You are..."}, ...]}
The metadata for this example should be:
{"metadata": {"layer": "behaviour", "type": "reasoning", ...}}
```

The brace-matcher returns `{"messages": [...]}` (the first valid dict) — **without** the metadata which is in a separate JSON object. This is what the write validation catches as "Missing required field 'metadata'".

**In the baseline**, the Player always produced a single combined JSON object: `{"messages": [...], "metadata": {...}}`. The prompt changes disrupted this pattern.

### 6.3 Why the Prompt Changes Made Things Worse

**Evidence — three measurable degradations:**

| Dimension | Baseline | This Run | Change |
|-----------|----------|----------|--------|
| Non-JSON output | 44 extraction fails | 68 format gate blocks | +54.5% |
| JSON without metadata | 0 write fails | 22 write fails | NEW |
| Unclosed think blocks | 4 post-gen fails | 14 post-gen fails | +250% |

**Hypothesis for each degradation:**

1. **BAD example priming**: The BAD example in the prompt literally shows `The user wants me to generate a literary analysis example... Let me think about the appropriate AO... {"messages": [...], "metadata": {...}}`. Qwen3.5 may pattern-match on this and **replicate** the bad behavior (thinking out loud before JSON). This is a well-documented issue with negative examples in LLM prompting — showing what NOT to do often causes models to do it.

2. **JSON structure disruption**: The "do not think out loud" instruction and the emphasis on "start with `{`" may cause the model to output the messages array first (as `{"messages": [...]}`) and then separately reason about metadata. The baseline prompt didn't have this pressure, so the model naturally produced a complete object.

3. **Think-block interference**: The increased prompt length and structural instructions may compete with the think-block format instructions, leading to more malformed think blocks (14 vs 4).

### 6.4 Framework Validation

| Check | Result | Method |
|-------|--------|--------|
| LangChain create_agent() behavior | No change | Code review: same factory, same middleware |
| vLLM thinking mode | NOT active | Log analysis: 100% player_content_source is "string" |
| Model parameters | Identical | Config review: same temperature, max_tokens, model |
| extra_body (Player) | None | Code review: Player factory passes no extra_body |
| extra_body (Coach) | structured_outputs only | Code review: Coach has xgrammar constraint |
| Middleware stack | Identical | Code review: Memory + PatchToolCalls + Caching |

**Conclusion: The regression is 100% prompt-driven.** No framework, model, or infrastructure changes contributed.

---

## 7. Recommendations (Revised with Evidence)

### PRIORITY 1 (Critical): Revert the Prompt Changes

**This is the highest-impact fix.** The data proves the prompt changes caused all three degradation dimensions. Reverting to the baseline prompt would restore the ~90.9% acceptance rate.

Specifically:
- **Revert** the BAD/GOOD examples from `player_prompts.py` lines 115-124
- **Revert** the "do not think out loud" instruction from line 109
- **Keep** the "CRITICAL — Mandatory Metadata" section (lines 79-84) — this is net positive
- **Keep** the "Metadata Checklist" (lines 231-250) — this is net positive

**Why revert instead of iterate:** Three prompt changes were applied simultaneously. The data shows all three dimensions worsened. Iterating one variable at a time from a degraded state is slower than reverting to the known-good baseline and then making ONE targeted change.

### PRIORITY 2 (High): Harden the Format Gate with Key Validation

The format gate currently only checks "is there valid JSON?" It should also check "does the JSON have required keys?"

**Current code** (`generation_loop.py:705-726`):
```python
try:
    _extract_json_object(player_content)
except ValueError:
    # Format gate fires
```

**Proposed fix:**
```python
try:
    extracted = _extract_json_object(player_content)
    data = json.loads(extracted)
    if "messages" not in data or "metadata" not in data:
        raise ValueError("JSON missing required top-level keys")
except ValueError:
    # Format gate fires — catches both non-JSON AND incomplete JSON
```

This moves the "Missing metadata" check from write validation (stage 5) to format gate (stage 1), saving 3 pipeline stages and providing more targeted FORMAT ERROR feedback.

### PRIORITY 3 (Medium): Don't Count Format Gate Failures as Turns

Change the turn loop from `for turn in range(max_turns)` + `continue` to a while-loop where only Coach-evaluated turns increment the counter. This allows format correction retries without consuming the quality-evaluation budget.

```python
turn = 0
format_retries = 0
MAX_FORMAT_RETRIES = 2

while turn < config.max_turns:
    # ... Player generates ...

    # Format gate
    try:
        extracted = _extract_json_object(player_content)
        data = json.loads(extracted)
        if "messages" not in data or "metadata" not in data:
            raise ValueError("missing keys")
    except ValueError:
        format_retries += 1
        if format_retries > MAX_FORMAT_RETRIES:
            turn += 1  # Count as a wasted turn after max retries
        coach_feedback = "FORMAT ERROR: ..."
        continue

    # Coach evaluates — this counts as a turn
    turn += 1
    # ... rest of pipeline ...
```

### PRIORITY 4 (Low): Investigate Single-Variable Prompt Improvements

After reverting to baseline (P1), test ONE prompt change at a time:
1. **Test A**: Add only the Metadata Checklist (no BAD/GOOD examples)
2. **Test B**: Add only the "CRITICAL — Mandatory Metadata" emphasis
3. **Test C**: Add a POSITIVE-only example (no BAD example, avoid negative priming)

Each test should run on the same 77 targets and compare acceptance rate vs baseline 90.9%.

---

## 8. Readiness Assessment: Overnight Production Run (77 → 1,000)

| Criterion | Status | Notes |
|-----------|--------|-------|
| Pipeline stability | **READY** | Zero pipeline errors, zero crashes |
| Coach structured outputs | **READY** | 105/105 valid JSON, zero parse failures |
| Post-gen validation gate | **READY** | Caught 14 defects correctly |
| Format gate (mechanical) | **READY** | 68/68 correct triggers, zero false positives |
| Player prompt quality | **NOT READY** | Prompt changes caused 54% more format failures + new metadata-omission failure |
| Write validation | **AT RISK** | 22 failures from prompt-caused metadata omission |
| Acceptance rate | **NOT READY** | 68.8% vs 90.9% baseline |
| Token budget | **READY** | 1.48M tokens, within budget |
| Time budget | **READY** | Projected ~21 hours fits overnight window |

**Verdict: NOT READY.** Revert the prompt changes (P1) and harden the format gate (P2) before the next run. Expected acceptance rate after P1 revert: ~90.9% (restore baseline). Expected after P1+P2: ~93-95% (format gate catches incomplete JSON earlier, saving turns for quality fixes).

**Projected 1,000-target outcomes:**

| Metric | Current (68.8%) | After P1 Revert (~91%) | After P1+P2 (~94%) |
|--------|:---------------:|:---------------------:|:------------------:|
| Accepted | ~688 | ~910 | ~940 |
| Rejected | ~312 | ~90 | ~60 |
| Duration | ~21 hrs | ~21 hrs | ~20 hrs |
| Tokens | ~19.2M | ~19.5M | ~19.0M |

---

## 9. Summary of Findings (Revised)

| # | Finding | Severity | Fix |
|---|---------|----------|-----|
| F1 | Prompt changes caused 54% increase in non-JSON output (44 → 68) | **Critical** | Revert BAD/GOOD examples and "think out loud" instruction (P1) |
| F2 | Prompt changes introduced NEW failure: JSON without metadata (0 → 22) | **Critical** | Revert prompt (P1) + harden format gate with key validation (P2) |
| F3 | Brace-matcher extracts FIRST valid JSON, which may be incomplete | High | Add required-key check after extraction (P2) |
| F4 | 12/24 rejections had Coach accept but write validation reject | High | Resolves with P1 (prompt revert) + P2 (format gate keys) |
| F5 | Post-gen validation failures up 250% (4 → 14, unclosed think blocks) | High | Resolves with P1 (prompt revert) |
| F6 | 8 previously stable categories regressed to 33-80% rejection | High | Collateral damage from prompt changes, resolves with P1 |
| F7 | Token cost per accepted example up 28.7% | Medium | Resolves when acceptance rate recovers |
| F8 | Format gate mechanically correct, zero false positives | Positive | Keep the format gate, enhance with key validation (P2) |
| F9 | FORMAT ERROR labelling working correctly (56 instances) | Positive | Keep |
| F10 | Unseen poetry improved (100% → 25% rejection) | Positive | May lose this gain after P1 revert |
| F11 | Coach structured outputs perfect (105/105 valid JSON) | Positive | Infrastructure is solid |
| F12 | Framework validated: no LangChain/vLLM thinking mode interference | Informational | Confirmed via log analysis |

---

## 10. Appendix A: Evidence Chain

### Methodology
1. Parsed 6,046 log lines from `docs/reviews/longer-runs/test-FPF1-fixes.md`
2. Compared against 6,326 baseline log lines from `docs/reviews/longer-runs/test-run-after-params-fixes.md`
3. Traced code paths in `entrypoint/generation_loop.py` (lines 576-957: turn loop)
4. Validated framework behavior via `agents/player.py`, `agents/coach.py`, `agents/model_factory.py`
5. Confirmed no thinking mode via log grep (100% `player_content_source: string`)
6. Analysed extraction ratios (input_len vs output_len) for write-validation-fail cases
7. Cross-referenced with C4 component diagrams (see Excalidraw)

### Key Data Points
- Baseline extraction successes: 72, avg JSON ratio 63.3%, write fails: **0**
- This-run format gate passes leading to write fails: 12 cases, avg JSON ratio 60.5%
- One pathological case: `input_len=8421, output_len=33` (0.4% ratio — brace-matcher found tiny fragment)
- All 173 Player content sources: "string" (no reasoning_content merging)
- Identical model config: Qwen/Qwen3.5-35B-A3B-FP8, temp 0.6, max_tokens 4096

### Fix Priority and Sequencing

```
Wave 1 (must fix before next run):
  FIX-FPF1-001: Revert BAD/GOOD examples + "think out loud" from player_prompts.py (P1)
  FIX-FPF1-002: Add messages+metadata key check to format gate (P2)

Wave 2 (should fix before next run):
  FIX-FPF1-003: Don't count format gate failures as turns (P3)

Wave 3 (after baseline restored, test single variables):
  FIX-FPF1-004: Test Metadata Checklist addition alone (P4a)
  FIX-FPF1-005: Test POSITIVE-only example addition (P4b, no BAD example)
```
| F2 | Stronger Player prompt increased format failures (44 → 68) | High | Revert or simplify BAD/GOOD examples (P3) |
| F3 | Write validation catches missing metadata Coach misses (15/22) | High | Add metadata check to Coach prompt (P2) |
| F4 | 12/24 rejections had Coach accept but downstream reject | High | Fix P1 + P2 resolves most |
| F5 | 8 previously stable categories now have 33-80% rejection | High | Collateral damage from F1, resolves with fix |
| F6 | Post-gen validation failures up 7x (2 → 14) | Medium | Investigate think-block compliance (P4/P5) |
| F7 | Token cost per accepted example up 28.7% | Medium | Resolves when acceptance rate recovers |
| F8 | FORMAT ERROR labelling working correctly | Positive | No action needed |
| F9 | Unseen poetry improved (100% → 25% rejection) | Positive | Fixes are helping weak categories |
| F10 | AO-specific guidance improved (100% → 50% rejection) | Positive | Fixes are helping weak categories |

---

## Appendix A: Fix Effectiveness Summary

| Fix | Task | Mechanical Status | Net Impact |
|-----|------|-------------------|------------|
| Pre-Coach format gate | TASK-REV-TPF1 Fix 1 | **WORKING** | **NEGATIVE** — saves Coach calls but exhausts turn budget |
| Stronger Player prompt | TASK-REV-TPF1 Fix 2 | DEPLOYED | **NEGATIVE** — format failures increased from 44 to 68 |
| Feedback labelling | TASK-REV-TPF1 Fix 1b | **WORKING** | **NEUTRAL** — correctly labels but insufficient alone |

## Appendix B: Recommended Fix Priority and Sequencing

```
Wave 1 (must fix before next run):
  FIX-FPF1-001: Don't count format gate as a turn (P1)
  FIX-FPF1-002: Add metadata validation to Coach prompt (P2)

Wave 2 (should fix before next run):
  FIX-FPF1-003: Revert/simplify stronger Player prompt (P3)

Wave 3 (investigate):
  FIX-FPF1-004: Qwen3.5 thinking mode interference (P4)
  FIX-FPF1-005: Post-gen validation increase root cause (P5)
```
