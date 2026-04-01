---
id: TASK-LR1-001
title: Enable vLLM guided_json for Coach agent
status: completed
created: 2026-03-30T00:00:00Z
updated: 2026-03-30T00:00:00Z
completed: 2026-03-30T20:30:00Z
completed_location: tasks/completed/TASK-LR1-001/
priority: critical
tags: [pipeline-fix, coach, json-parsing, vllm]
complexity: 5
parent_review: TASK-REV-649A
feature_id: FEAT-LR1
wave: 1
implementation_mode: task-work
dependencies: []
---

# Task: Enable vLLM guided_json for Coach agent

## Description

Enable vLLM's `guided_json` / `response_format` parameter for the Coach agent's LLM calls so that token generation is constrained to valid JSON matching the `CoachVerdict` schema. This eliminates the root cause of all 245 Coach parse failures in Long Run 1 (91% of all parse failures, ~70% of all rejections).

## Context

The Coach agent uses Qwen3.5-35B-A3B-FP8 via vLLM. The model emits untagged reasoning prose before its JSON verdict, causing the 3-strategy JSON extractor to fail. Previous fixes (TRF-020/021 think-block normalisation) did not help because the problematic content is plain prose, not `<think>` blocks.

`guided_json` constrains the model at the token-generation level to produce only valid JSON matching a provided schema. No prose preamble is possible.

## Scope

- [x] Define the `CoachVerdict` JSON schema for `guided_json` (must match the existing `CoachVerdict` dataclass/model)
- [x] Add `response_format` / `guided_json` parameter to the Coach's LLM call via `agents/coach.py` and `agents/model_factory.py`
- [ ] Verify the schema works with vLLM's `--guided-decoding-backend` on promaxgb10-41b1:8002 *(requires live run)*
- [x] **Do NOT apply guided_json to the Player** — Player outputs nested JSON containing free-form conversation content with think blocks, which would be broken by schema constraints
- [ ] Test with a small batch (10-20 targets) to verify Coach parse failure rate drops to ~0 *(requires live run)*

## Acceptance Criteria

- [x] Coach LLM calls use `guided_json` with `CoachVerdict` schema
- [x] Player LLM calls are unchanged
- [ ] Coach parse failures reduced from 245 to near-zero in test batch *(requires live run)*
- [x] Existing tests pass (321/323; 2 pre-existing GOAL.md failures unrelated)
- [ ] No regression in accepted example quality *(requires live run)*

## Risk Assessment

**Risk: Low** — Coach output is evaluation-only, never written to training data. The schema is already well-defined. vLLM's guided decoding is a mature feature.

**Rollback**: Remove the `response_format` parameter to revert to unconstrained generation.
