---
id: TASK-LR1-004
title: Strengthen Player prompt for mandatory metadata
status: completed
created: 2026-03-30T00:00:00Z
updated: 2026-03-30T00:00:00Z
completed: 2026-03-30T00:00:00Z
completed_location: tasks/completed/TASK-LR1-004/
priority: medium
tags: [prompt-tuning, player, metadata]
complexity: 2
parent_review: TASK-REV-649A
feature_id: FEAT-LR1
wave: 1
implementation_mode: direct
dependencies: []
---

# Task: Strengthen Player prompt for mandatory metadata

## Description

In Long Run 1, `metadata_completeness` was the #1 revision criterion (77 issues). The Player frequently generates good pedagogical content but omits the required `metadata` object.

Add explicit emphasis in the Player prompt that metadata is mandatory and its omission causes automatic rejection.

## Scope

- [x] Update Player system prompt in `prompts/player_prompts.py` to add:
  - "CRITICAL: You MUST include the `metadata` object in every response. Omitting metadata will cause automatic rejection."
  - Move the metadata schema description higher in the prompt (before the content generation instructions)
- [x] Add a brief metadata checklist reminder at the end of the prompt

## Acceptance Criteria

- [x] Player prompt updated with mandatory metadata emphasis
- [x] Metadata schema description appears early in prompt
- [x] No change to expected metadata fields or values
