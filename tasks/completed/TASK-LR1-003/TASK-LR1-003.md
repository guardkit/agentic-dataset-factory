---
id: TASK-LR1-003
title: Strengthen Coach prompt to reduce shallow score-5 accepts
status: completed
created: 2026-03-30T00:00:00Z
updated: 2026-03-30T00:00:00Z
completed: 2026-03-30T00:00:00Z
priority: high
tags: [prompt-tuning, coach, quality]
complexity: 3
parent_review: TASK-REV-649A
feature_id: FEAT-LR1
wave: 1
implementation_mode: task-work
dependencies: []
---

# Task: Strengthen Coach prompt to reduce shallow score-5 accepts

## Description

In Long Run 1, 216/351 coaching turns in rejected examples showed `decision: accept, score: 5` — shallow, uncritical acceptances. Code review confirmed there is no phantom-accept fallback; these are genuine Coach verdicts where the model did not critically evaluate the Player's output.

Strengthen the Coach system prompt to require explicit justification for high scores and critical evaluation of every criterion.

## Scope

- [ ] Update Coach system prompt in `prompts/coach_prompts.py` to add:
  - "You MUST critically evaluate every criterion listed below. Do not accept by default."
  - "A score of 4 or 5 requires explicit justification stating what was done well for EACH criterion."
  - "If you cannot verify a criterion (e.g., metadata is missing), you MUST score 1-2 and request revision."
- [ ] Add a negative example to the prompt showing what a shallow accept looks like and why it's wrong
- [ ] Test with a small batch (10-20 targets) comparing old vs new prompt acceptance patterns
- [ ] Verify that the strengthened prompt doesn't cause excessive rejections (target: accept rate stays above 75%)

## Acceptance Criteria

- [ ] Coach prompt updated with explicit critical evaluation instructions
- [ ] Test batch shows reduced score-5 rate (target: <50% of accepts are score=5, down from 85.8%)
- [ ] Accept rate remains above 75%
- [ ] Existing tests pass

## Risk Assessment

**Risk: Low** — prompt-only change. If too aggressive, can be softened. Monitor accept rate in test batch.
