---
id: TASK-GTS-004
title: "Implement prompt templates for reasoning, multi-turn, and direct generation"
task_type: feature
parent_review: TASK-REV-6DBC
feature_id: FEAT-GTS
wave: 3
implementation_mode: task-work
complexity: 4
dependencies:
  - TASK-GTS-002
status: completed
completed: 2026-03-17T00:00:00Z
completed_location: tasks/completed/TASK-GTS-004/
priority: high
tags: [synthesis, phase1, prompts, templates]
---

# Task: Implement prompt templates for reasoning, multi-turn, and direct generation

## Description

Create `synthesis/templates.py` with functions that generate Claude API prompts for each example type. The prompts are derived from the synthesis prompt templates in the training data format spec (`docs/research/gcse-tutor-training-data-format.md`).

## Requirements

### System prompt constant
- `TUTOR_SYSTEM_PROMPT: str` — the standard GCSE English tutor system prompt (verbatim from format spec)
- This is injected as the system message in every generated example

### Template functions

Each function returns a dict with `system_prompt: str` and `user_prompt: str` ready for the Claude API call.

#### `build_reasoning_prompt(target: GenerationTarget) -> PromptPair`
- For single-turn reasoning examples
- Parameterised by: text, topic, grade_target, ao
- Instructs Claude to generate a ShareGPT JSON object with `<think>` block in assistant response
- Includes the system prompt to embed in the generated example
- Maps to scenario: "Generating a single-turn reasoning example"

#### `build_multiturn_prompt(target: GenerationTarget) -> PromptPair`
- For multi-turn essay feedback examples (3-turn conversation)
- Parameterised by: text, topic, grade_target, ao
- Instructs Claude to generate 4+ messages after system (user/assistant/user/assistant minimum)
- Each assistant turn must include `<think>` block
- Conversation should show progressive scaffolding
- Maps to scenario: "Generating a multi-turn essay feedback example"

#### `build_direct_prompt(target: GenerationTarget) -> PromptPair`
- For non-reasoning examples (factual recall, terminology, encouragement)
- Parameterised by: text, topic, grade_target
- Instructs Claude to generate ShareGPT JSON with NO think block
- Maps to scenario: "Generating a direct (non-reasoning) example"

### Prompt selection
- `select_template(target: GenerationTarget) -> Callable`
- If `target.type == "reasoning"` and `target.topic == "essay_feedback"` → `build_multiturn_prompt`
- If `target.type == "reasoning"` → `build_reasoning_prompt`
- If `target.type == "direct"` → `build_direct_prompt`

### PromptPair type
- `@dataclass` with `system_prompt: str` and `user_prompt: str`
- `system_prompt` is the meta-prompt (instructions to Claude about what to generate)
- `user_prompt` contains the parameterised generation request

## Acceptance Criteria

- [x] All three template functions produce well-formed prompts
- [x] Prompts include "Return only the JSON object, no preamble" instruction
- [x] Template selection correctly dispatches based on type and topic
- [x] Multi-turn template explicitly requests 4+ messages after system
- [x] Direct template explicitly requests no think block
- [x] Unit tests verify prompt content includes required parameters (text, topic, grade_target)
- [x] Unit tests verify template selection logic for all type/topic combinations
- [x] All modified files pass project-configured lint/format checks with zero errors

## Implementation Notes

Prompts should use f-strings or `.format()` for parameterisation. Keep prompt text as close to the format spec templates as possible — they've already been validated for quality.

The `PromptPair.system_prompt` is the instruction to Claude (the generation model), NOT the tutor system prompt. The tutor system prompt is embedded *within* the user_prompt as part of the JSON the model is asked to produce.
