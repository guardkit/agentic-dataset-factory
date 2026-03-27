---
id: TASK-TI-006
title: Observability logging scaffold
status: backlog
created: 2026-03-27T22:00:00Z
updated: 2026-03-27T22:00:00Z
priority: p1
tags: [template, observability, logging, base-template]
complexity: 3
parent_review: TASK-REV-TRF12
feature_id: FEAT-TI
wave: 2
implementation_mode: direct
depends_on: []
test_results:
  status: pending
  coverage: null
  last_run: null
---

# Task: Observability Logging Scaffold

## Description

Create a standard logging module for the `langchain-deepagents` base template that ensures token usage, pipeline stage timing, and error context are logged from the start — preventing the 4 observability gaps that required reactive fixes.

## What to Build

### 1. Token usage logger
- Log `response.usage` after every LLM API call: prompt_tokens, completion_tokens, total_tokens
- Cumulative totals per target and pipeline-wide summary
- Alert if context utilisation exceeds configurable threshold (default 80%)

### 2. Pipeline stage logger
- Log content length at each stage: raw response -> normalized -> extracted -> validated -> written
- Enables detection of truncation, data loss, or unexpected expansion

### 3. Error context logger
- On extraction/validation failure: log first 200 chars + last 200 chars + total length
- Structured format for easy grep/analysis

### 4. Stage timing
- Wall-clock time per pipeline stage
- Cumulative per target and pipeline summary

## Fixes Prevented

TRF-010, TRF-017, TRF-018, TRF-023

## Target Location

`lib/observability.py` (in the template output)

## Acceptance Criteria

- [ ] Token usage logged per API call with cumulative totals
- [ ] Content length logged at each pipeline stage
- [ ] Error context includes head + tail + length
- [ ] Stage timing with summaries
- [ ] Uses Python `logging` module (not print statements)
- [ ] Configurable log level and format

## Effort Estimate

0.5 days
