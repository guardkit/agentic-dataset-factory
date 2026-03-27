---
id: TASK-TRF-015
title: Investigate Player example truncation before Coach evaluation
status: completed
created: 2026-03-26T00:00:00Z
updated: 2026-03-27T00:00:00Z
completed: 2026-03-27T00:00:00Z
completed_location: tasks/completed/TASK-TRF-015/
priority: medium
tags: [investigation, orchestrator, quality, P2]
complexity: 3
task_type: implementation
parent_review: TASK-REV-TRF5
feature_id: FEAT-TRF5
wave: 2
implementation_mode: task-work
depends_on: [TASK-TRF-012, TASK-TRF-013]
test_results:
  status: pass
  coverage: null
  last_run: 2026-03-27T00:00:00Z
---

# Task: Investigate Player Example Truncation

## Description

In Run 5, the Coach's input contained only the tail end of the Player's generated training example (~951 chars): the assistant response text and metadata, but missing the system message and user message from the JSON `messages` array.

### Possible Causes

1. Player generated incomplete JSON (model truncation)
2. Orchestrator's `_extract_example_json()` truncated the JSON during extraction
3. Context window message truncation within DeepAgents SDK
4. The Player's full response was split across multiple content blocks

### Investigation Steps

1. Add debug logging to capture the raw Player response before extraction
2. Add debug logging to capture the extracted JSON before passing to Coach
3. Compare lengths to identify where truncation occurs
4. Run a single target and examine the full log

## Acceptance Criteria

- [x] Root cause of truncation identified
- [x] Fix implemented if cause is in our code
- [x] Debug logging added for Player response extraction (can be gated behind log level)
- [x] Coach receives complete training example JSON

## Context

This is a P2 quality concern from TASK-REV-TRF5. May only be observable once TASK-TRF-012 and TASK-TRF-013 are fixed and the pipeline reaches the Coach evaluation stage successfully.

## Implementation Notes (TASK-TRF-015)

### Root Cause

The truncation occurred because `player_response["messages"][-1].content` was accessed
directly (line 519). When the Player model returns content as a **list of typed content
blocks** (e.g. `[{"type": "text", "text": "..."}]`) rather than a plain string — which
happens with some model providers — the raw list was passed downstream, causing
serialisation artefacts and data loss.

This is **Possible Cause #4**: the Player's response was split across multiple content
blocks, and only the string representation of the last block survived.

### Fix

Added `_extract_player_content()` function mirroring the existing `_extract_coach_content()`
— it handles both plain string and content-block-list formats, concatenating text blocks
into a single string. The generation loop now calls this function instead of raw `.content`
access.

### Debug Logging Added

Three debug log points added (gated behind `logger.debug`):
1. **After Player response**: content source type and length
2. **After extraction**: input vs output length comparison
3. **Before Coach**: content length passed to Coach

All use structured format consistent with existing logging patterns.
