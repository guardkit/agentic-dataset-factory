---
id: TASK-TRF-031
title: Add CRITICAL response format instruction to Player prompt
status: complete
created: 2026-03-27T20:00:00Z
updated: 2026-03-27T20:00:00Z
priority: high
tags: [fix, player-prompt, json-extraction, throughput]
complexity: 2
parent_review: TASK-REV-TRF10
depends_on: []
---

# Task: Add CRITICAL Response Format Instruction to Player Prompt

## Problem

The Player produces conversational prose instead of JSON on Turn 1 (after processing RAG tool results). The output format instruction in `PLAYER_BASE_PROMPT` is too weak for Qwen3.5-35B-A3B — the model prioritises conversational continuation over structured output when processing tool results.

## Root Cause

`prompts/player_prompts.py:72-77` says "Return the training example as a single JSON object" but this instruction is buried mid-prompt, uses polite language, and competes with RAG context the model is actively processing.

## Fix

Append a `## CRITICAL — Response Format` section to the END of `PLAYER_BASE_PROMPT` (after `## Quality Standards`) with explicit JSON-only output instructions leveraging recency bias and imperative language.

## Files to Change

- `prompts/player_prompts.py` — append to `PLAYER_BASE_PROMPT`

## Acceptance Criteria

- [ ] PLAYER_BASE_PROMPT ends with CRITICAL response format section
- [ ] Existing tests pass
- [ ] New test verifies the prompt contains the format instruction
