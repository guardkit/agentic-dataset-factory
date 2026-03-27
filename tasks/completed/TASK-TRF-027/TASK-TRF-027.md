---
id: TASK-TRF-027
title: Coach prompt — verify think block presence before accepting
status: completed
created: 2026-03-27T16:00:00Z
updated: 2026-03-27T18:00:00Z
completed: 2026-03-27T18:00:00Z
priority: low
tags: [coach, prompt-engineering, quality, eighth-run]
complexity: 2
parent_review: TASK-REV-TRF8
feature_id: FEAT-TRF8
depends_on: [TASK-TRF-024]
wave: 2
implementation_mode: direct
completed_location: tasks/completed/TASK-TRF-027/
test_results:
  status: not-applicable
  coverage: null
  last_run: null
---

# Task: Coach Prompt — Verify Think Block Presence Before Accepting

## Problem

In Run 8, the Coach scored 5/5 and accepted training examples that lacked required `<think>` blocks. For reasoning-type examples, the Generation Guidelines require:

> All reasoning-type examples (75% of the dataset) must include a `<think>` block in the assistant turn.

The Coach's AGENTS.md already says:

> Check type correctness (reasoning vs direct) matches think block presence

But the Coach is not enforcing this — it accepted examples without think blocks twice.

## Fix

Add an explicit instruction to the Coach system prompt (or AGENTS.md Coach section) that makes think block verification a hard requirement for acceptance:

```markdown
### CRITICAL EVALUATION RULE
For reasoning-type examples: if the assistant message does NOT contain a `<think>...</think>` block,
you MUST set decision to "revise" and score to 1, regardless of other quality.
The think block is a mandatory structural requirement for all reasoning examples.
```

## Files Modified

- `AGENTS.md` — Coach ALWAYS section: added CRITICAL rule for automatic rejection; Coach NEVER section: added explicit prohibition
- `domains/gcse-english-tutor/GOAL.md` — Evaluation Criteria section: added CRITICAL PRE-CHECK subsection

## Acceptance Criteria

- [x] Coach prompt explicitly states think block is mandatory for reasoning type
- [x] Coach prompt specifies automatic rejection (score 1) for missing think blocks
- [ ] Next run: Coach rejects reasoning examples without think blocks (to be verified)

## Risk

**Low**. This is a prompt-only change. No code modifications needed.

## Note

This is a quality improvement. TASK-TRF-024 (removing `--reasoning-parser`) should fix the root cause, but this ensures the Coach acts as a safety net even if think blocks are missing for other reasons.
