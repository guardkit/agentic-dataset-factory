---
id: TASK-D0A8-005
title: Write learnings document for 2500-run stall analysis
status: completed
created: 2026-04-01T20:00:00Z
updated: 2026-04-01T20:00:00Z
priority: medium
tags: [documentation, learnings, post-mortem]
task_type: implementation
complexity: 2
parent_review: TASK-REV-D0A8
feature_id: FEAT-D0A8
wave: 1
implementation_mode: direct
dependencies: []
test_results:
  status: pending
  coverage: null
  last_run: null
---

# Task: Write learnings document for 2500-run stall analysis

## Description

Create a learnings document at `docs/learnings/2500-run-stall-analysis.md` that captures the problem, root cause analysis, historical context, and decisions from the TASK-REV-D0A8 review. This document serves as a reference for future generation runs so the same mistakes are not repeated.

## Content Requirements

The document should cover:

1. **Incident summary**: What happened, when, impact
2. **Root causes**: Mac sleep, timeout chain failure, format gate rate
3. **Cross-boundary execution flow**: The validated invocation chain from generation loop through LangChain/OpenAI/httpx to vLLM
4. **The LangChain timeout sentinel bug**: How `timeout=None` defeats OpenAI's 600s default
5. **Format gate history**: The evolution of format gate fixes (TRF-025/030/031, FPF1-001/002/003) and why prompt engineering backfired
6. **Why structured output cannot be used for Player**: Tool calling conflict, variable messages, prose quality, explicit architectural decision
7. **Binding decisions**: Table of architectural constraints from prior reviews that must not be violated
8. **Checklist for future overnight/long runs**: Operational checklist to avoid repeating these issues

## Acceptance Criteria

- [ ] Document exists at `docs/learnings/2500-run-stall-analysis.md`
- [ ] Covers all 8 content sections above
- [ ] References specific task IDs, review reports, and code locations
- [ ] Includes the binding decisions table
- [ ] Includes operational checklist for future runs

## Files to Create

- `docs/learnings/2500-run-stall-analysis.md`
