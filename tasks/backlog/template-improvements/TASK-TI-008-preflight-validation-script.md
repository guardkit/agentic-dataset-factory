---
id: TASK-TI-008
title: Pre-flight validation script (--validate / guardkit validate)
status: backlog
created: 2026-03-27T22:00:00Z
updated: 2026-03-27T22:00:00Z
priority: p2
tags: [template, automation, validation, base-template]
complexity: 5
parent_review: TASK-REV-TRF12
feature_id: FEAT-TI
wave: 3
implementation_mode: task-work
depends_on: [TASK-TI-004]
test_results:
  status: pending
  coverage: null
  last_run: null
---

# Task: Pre-Flight Validation Script

## Description

Create an automated pre-flight validation script that runs the first-run success checklist programmatically. Catches the top wiring issues before the first pipeline execution. Becomes a `guardkit validate` command.

## What to Build

### Automated Checks (wiring)
- [ ] Player tool inventory matches expected allowlist
- [ ] Coach tool list is empty (or evaluator-only)
- [ ] Player does NOT have write_output
- [ ] Factory uses `create_agent()` for tool-restricted agents
- [ ] `max_tokens` explicitly set for all model configs
- [ ] Domain config parses without errors
- [ ] Metadata field types match validation logic (array vs scalar, range vs enum)
- [ ] JSON extraction pipeline order is correct

### Manual Review Prompts (prompts + model config)
- [ ] "Does your Player prompt end with a CRITICAL Response Format section?" [Y/n]
- [ ] "Does your Coach prompt include explicit accept/reject criteria?" [Y/n]
- [ ] "Have you tested your model/parser combination with tool calling?" [Y/n]
- [ ] "Is your vLLM reasoning-parser configuration compatible with your extraction?" [Y/n]

### Output
```
$ guardkit validate

Automated Checks:
  [PASS] Player tools: {'rag_retrieval'} (expected: {'rag_retrieval'})
  [PASS] Coach tools: set() (expected: set())
  [PASS] Player does not have write_output
  [PASS] max_tokens set: Player=4096, Coach=2048
  [PASS] Domain config parses: 8 targets, 5 metadata fields
  [FAIL] Metadata field 'turns' uses range notation but validator treats as enum

Manual Review:
  ? Does your Player prompt end with a CRITICAL Response Format section?
  ? Does your Coach prompt include explicit accept/reject criteria?

Result: 1 FAIL, 2 manual checks pending
```

## Target Location

`lib/preflight.py` + CLI entry point (in the template output)

## Acceptance Criteria

- [ ] Automated checks for all wiring items
- [ ] Manual review prompts for prompt/model items
- [ ] Clear PASS/FAIL output with details
- [ ] Exit code 1 if any automated check fails
- [ ] Can run as `guardkit validate` or `python -m lib.preflight`
- [ ] Unit tests for each automated check

## Effort Estimate

1 day
