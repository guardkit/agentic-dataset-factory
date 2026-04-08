---
id: TASK-CR-004
title: Update COACH_BASE_PROMPT to remove "ALL criteria" contradiction
status: completed
created: 2026-04-07T12:00:00Z
updated: 2026-04-07T12:00:00Z
completed: 2026-04-07T00:00:00Z
priority: medium
complexity: 1
tags: [criteria-routing, coach, prompt]
parent_review: TASK-REV-CC01
feature_id: FEAT-CR
wave: 1
implementation_mode: direct
dependencies: []
test_results:
  status: passed
  coverage: null
  last_run: 2026-04-07T00:00:00Z
---

# Task: Update COACH_BASE_PROMPT to remove "ALL criteria" contradiction

## Description

The COACH_BASE_PROMPT contains two references to "ALL criteria" that would contradict layer-aware filtering:

1. **Line 72-73**: "You MUST include ALL criteria from the Evaluation Criteria section in this dict."
2. **Line 147**: "Evaluate EACH criterion individually from the Evaluation Criteria section."

After TASK-CR-002, the Evaluation Criteria section will only contain applicable criteria — but the word "ALL" could still confuse if the model retains knowledge of criteria from other contexts.

## Changes

In `prompts/coach_prompts.py`, update COACH_BASE_PROMPT:

**Line 72-73** — Change:
```
You MUST include ALL criteria from the Evaluation Criteria section in this dict.
```
To:
```
You MUST include every criterion listed in the Evaluation Criteria section below in this dict. Do NOT add criteria that are not listed.
```

**Line 147** — Change:
```
Evaluate EACH criterion individually from the Evaluation Criteria section.
```
To:
```
Evaluate each criterion listed in the Evaluation Criteria section below.
```

## Files to Modify

- `prompts/coach_prompts.py` — COACH_BASE_PROMPT constant (2 line changes)

## Acceptance Criteria

- [x] No reference to "ALL criteria" remains in COACH_BASE_PROMPT
- [x] New wording explicitly says "listed below" to anchor to the filtered list
- [x] New wording includes "Do NOT add criteria that are not listed" as a guardrail
- [x] Existing tests pass
