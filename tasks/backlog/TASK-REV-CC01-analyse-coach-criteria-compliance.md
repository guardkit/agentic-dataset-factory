---
id: TASK-REV-CC01
title: Analyse Coach non-compliance with layer-aware criteria routing
status: review_complete
created: 2026-04-07T09:00:00Z
updated: 2026-04-07T09:00:00Z
priority: high
tags: [review, coach, criteria-routing, compliance, knowledge-layer, prompt-engineering]
task_type: review
complexity: 6
test_results:
  status: pending
  coverage: null
  last_run: null
---

# Task: Analyse Coach non-compliance with layer-aware criteria routing

## Description

The knowledge-layer criteria fix (TASK-KCF-001) added layer-specific evaluation criteria
routing to GOAL.md, instructing the Coach to evaluate knowledge/direct examples against
`factual_accuracy`, `completeness`, `age_appropriate`, and `mark_scheme_aligned` only —
excluding `socratic_approach` and `ao_accuracy`.

**The Coach completely ignored this instruction.** 0% compliance — all 309 Coach verdicts
for direct examples included `socratic_approach` in `criteria_met`, and 79% marked it as
blocking. The Qwen 3.5-35B model follows the structured output schema faithfully but does
not follow the conditional criteria routing instruction in the evaluation criteria section.

### Key Metrics from Knowledge Run (2026-04-06)

- **Direct targets processed**: 622 (indices 1877-2499)
- **Direct accepted**: 385 (61.9%)
- **Direct rejected**: 237 (38.1%)
- **Coach refusals**: 120 (51% of direct rejections) — separate infrastructure issue
- **max_turns_exhausted**: 103 (43% of direct rejections)
- **socratic_approach blocking in direct verdicts**: 166 instances (should be 0)
- **Coach compliance with layer routing**: 0% — all 309 verdicts include socratic_approach

### Evidence

From `output/rejected.jsonl` analysis:
- 309/309 direct Coach verdicts include `socratic_approach` in `criteria_met` keys
- 0/309 correctly excluded `socratic_approach` for knowledge layer
- Coach evaluates all 6 criteria uniformly regardless of the routing instruction
- The natural-language instruction "Evaluate ONLY factual_accuracy, completeness,
  age_appropriate, mark_scheme_aligned" had zero effect

## Review Objectives

1. **Determine why the Coach ignores the routing instruction** — is it prompt position,
   instruction format, model capability, or structured output schema constraints?
2. **Analyse the Coach prompt as actually constructed** — trace through `build_coach_prompt()`
   to see exactly what the Coach receives, including where the routing instruction appears
   relative to other instructions
3. **Evaluate fix approaches** with feasibility and regression risk:
   - Prompt restructuring (move routing instruction to more prominent position)
   - Two-table format (separate criteria tables per layer, remove inapplicable criteria)
   - Code-level routing (filter criteria before building Coach prompt based on target layer)
   - Post-verdict filtering (orchestrator ignores socratic_approach blocks for direct type)
   - Structured output schema modification (different schema per layer)
4. **Assess the Coach refusal issue** — 120 refusals (51% of rejections) are a separate
   problem; determine if they share a root cause with compliance failure
5. **Recommend the minimal-risk fix** that maximises compliance without requiring model
   changes or extensive code modifications

## Acceptance Criteria

- [ ] Root cause determination with evidence (prompt trace, model behaviour analysis)
- [ ] Coach prompt as-constructed included in review (full text or key sections)
- [ ] At least 3 fix approaches evaluated with effort/risk/impact
- [ ] Recommended approach with implementation plan
- [ ] Assessment of whether fix requires another re-run or can be applied post-hoc
- [ ] Coach refusal analysis (separate from compliance) with mitigation options
- [ ] Review document written to `docs/reviews/`

## Implementation Notes

Key files to examine:
- `prompts/coach_prompts.py` — `build_coach_prompt()` and `_format_evaluation_criteria()`
- `domains/gcse-english-tutor/GOAL.md` — Evaluation Criteria section (lines 74-97)
- `config/coach_verdict.py` — CoachVerdict schema and `is_accepted` property
- `entrypoint/generation_loop.py` — where Coach input is constructed (lines 751-758)
- `output/rejected.jsonl` — rejection data for pattern analysis

Context from prior analysis:
- `CoachVerdict.criteria_met` is `dict[str, bool]` — free-form, any keys accepted
- `is_accepted` checks issues[].severity == "blocking" but does not filter by criterion name
- Coach receives Player content directly — no target metadata injected separately
- The Coach must infer layer/type from the Player's JSON metadata, not from explicit routing
