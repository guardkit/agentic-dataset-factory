---
id: TASK-CR-008
title: Review model copyright/safety behaviour for Coach alternative
status: backlog
created: 2026-04-08T00:00:00Z
updated: 2026-04-08T00:00:00Z
priority: medium
complexity: 3
tags: [coach, refusal, model-selection, review]
parent_review: TASK-REV-CC01
feature_id: FEAT-CR
wave: null
implementation_mode: manual
dependencies: []
test_results:
  status: n/a
  coverage: null
  last_run: null
---

# Task: Review model copyright/safety behaviour for Coach alternative

## Description

Qwen 3.5-35B-A3B-FP8 refuses to evaluate ~19% of knowledge-layer examples, with refusal rates up to 39% for certain categories (factual recall, literary terminology). The safety layer appears to interpret educational content evaluation as reproducing copyrighted exam/curriculum material.

This is a **review/investigation task** to identify alternative models for the Coach role that:
1. Have less aggressive safety filters for educational content evaluation
2. Can run on the existing vLLM infrastructure (single GPU, FP8/GPTQ quantisation acceptable)
3. Support structured outputs (JSON mode) via the OpenAI-compatible API
4. Produce reliable JSON verdicts at the Coach's low temperature (0.3)

## Investigation Areas

### 1. Why does Qwen 3.5-35B refuse educational content evaluation?

- Is it trained with specific copyright protections for exam content (AQA, GCSE)?
- Does the refusal pattern correlate with specific UK curriculum terms?
- Is it the evaluation framing ("assess this content") or the content itself?
- Does the `structured_outputs` constraint amplify refusal rates?

### 2. Candidate models to evaluate

| Model | Size | Notes |
|-------|------|-------|
| Qwen2.5-32B-Instruct | 32B | Older Qwen, possibly different safety profile |
| Qwen3-32B | 32B | Different architecture, may have different safety |
| Llama 3.1 70B (quantised) | 70B → ~35B FP8 | Meta's safety is content-generation focused, not evaluation |
| Llama 3.3 70B (quantised) | 70B → ~35B FP8 | Newer Llama with improved instruction following |
| Mistral Large 2 (quantised) | Various | Known for lower safety friction |
| Gemma 2 27B | 27B | Google's safety layer may differ |
| DeepSeek-V3 (quantised) | Various | Strong JSON following, different safety profile |

### 3. Evaluation criteria for Coach model

- **Refusal rate** on the same 98 examples that Qwen 3.5-35B refused
- **JSON compliance** — produces valid `CoachVerdict` JSON without structured outputs constraint
- **Evaluation quality** — verdicts are consistent and well-reasoned
- **Latency** — acceptable for the Coach role (not latency-critical but shouldn't bottleneck)
- **VRAM footprint** — must fit alongside the Player model or run on same GPU sequentially

### 4. Testing methodology

- Extract the 98 refused examples from `output_backup_pre_rerun/rejected.jsonl`
- Build a standalone test harness that sends each to the candidate model
- Compare refusal rates, JSON validity, and verdict quality
- Test with and without `structured_outputs` constraint

## Deliverables

- [ ] Summary of why Qwen 3.5-35B refuses educational content evaluation
- [ ] Comparison table of candidate models with refusal rates on the test set
- [ ] Recommendation: which model to use for Coach (or confirm Qwen 3.5-35B with mitigations from TASK-CR-006/007 is sufficient)
- [ ] If recommending a model switch: vLLM serving configuration and VRAM requirements

## This is a research/investigation task, not an implementation task.

Use `/task-review` when ready to investigate.
