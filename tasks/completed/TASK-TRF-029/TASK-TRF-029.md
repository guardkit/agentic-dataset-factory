---
id: TASK-TRF-029
title: Add explicit <think> block instruction to Player prompt
status: completed
created: 2026-03-27T18:00:00Z
updated: 2026-03-27T21:00:00Z
completed: 2026-03-27T21:00:00Z
completed_location: tasks/completed/TASK-TRF-029/
priority: critical
tags: [prompt-engineering, think-blocks, player, ninth-run]
complexity: 2
parent_review: TASK-REV-TRF9
feature_id: FEAT-TRF9
depends_on: []
wave: 1
implementation_mode: direct
test_results:
  status: pending
  coverage: null
  last_run: null
---

# Task: Add Explicit <think> Block Instruction to Player Prompt

## Problem

Without vLLM's `--reasoning-parser qwen3` (removed in TRF-024), Qwen3.5 outputs its own reasoning as plain untagged text before the JSON. The model does NOT use `<think>` tags natively — those are a vLLM-level feature.

More critically, the training examples the model generates lack `<think>` blocks in the assistant's content field. The `write_output` validator requires reasoning-type examples to have `<think>...</think>` in the assistant content:

```python
if example_type == "reasoning" and not has_think:
    return "Error: metadata.type is 'reasoning' but assistant content has no <think> block"
```

## Root Cause

The existing Player prompt (in GOAL.md Generation Guidelines) says:

> All reasoning-type examples (75% of the dataset) must include a `<think>` block in the assistant turn.

But the model interprets this loosely. Without a concrete format example, the model either:
1. Omits think blocks entirely (Run 9)
2. Generates think blocks as part of its own reasoning (which vLLM then strips — Run 8)

The model needs an explicit, concrete example of the expected JSON structure with `<think>` blocks embedded in the content field.

## Fix

Add a concrete format example to the Generation Guidelines section of `domains/gcse-english-tutor/GOAL.md`, immediately after the existing think block instruction:

```markdown
**Think block format for reasoning examples**: All reasoning-type examples (75% of the dataset) must include a `<think>` block in the assistant turn. The think block contains internal reasoning about: which AOs apply, the student's likely knowledge level, common misconceptions to watch for, and what Socratic question will guide them forward. The visible response after the think block must NOT reveal the internal reasoning.

**IMPORTANT — Format example for reasoning-type assistant content**:
```
"content": "<think>The student is asking about Lady Macbeth's soliloquy in Act 1 Scene 5. This relates to AO2 (language analysis) and AO3 (context). At Grade 7, they should be able to identify language techniques and link them to context. I should guide them to notice the imperative verbs and how they connect to gender expectations.</think>\n\nThat's a really interesting passage to look at! Before I share my thoughts, what do you notice about the types of words Lady Macbeth uses when she's speaking to the spirits? Are they soft and gentle, or something else entirely?"
```
The `<think>` block MUST appear at the very start of the assistant content, followed by the visible response. Do NOT omit the `<think>` block for reasoning-type examples.
```

## Files to Modify

- `domains/gcse-english-tutor/GOAL.md` (Generation Guidelines section)

## Acceptance Criteria

- [ ] GOAL.md Generation Guidelines includes concrete format example with `<think>` block
- [ ] Example shows `<think>` at start of content field, followed by visible response
- [ ] Instruction emphasises MUST and NOT omit
- [ ] Next run: Player generates `<think>` blocks in assistant content for reasoning-type examples
- [ ] Next run: `write_output` think block validation passes

## Risk

**Low**. Prompt-only change. No code modifications. If the model still doesn't follow the instruction, we may need to add a post-processing step that injects think blocks.
