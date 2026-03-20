---
id: TASK-AF-011
title: "Update pyproject.toml for agent factories"
task_type: scaffolding
parent_review: TASK-REV-DAA1
feature_id: FEAT-AF
wave: 1
implementation_mode: direct
complexity: 1
dependencies: []
status: pending
tags: [pyproject, dependencies, packaging]
---

# Task: Update pyproject.toml for agent factories

## Description

Update `pyproject.toml` to include the new `agents`, `prompts`, and `config` packages and ensure `deepagents>=0.4.11` is listed as a dependency.

## Acceptance Criteria

- [ ] `deepagents>=0.4.11` is in project dependencies (if not already)
- [ ] Package includes updated for `agents*`, `prompts*`, `config*` (if using packages discovery)
- [ ] Test paths include new test locations
- [ ] `pip install -e .` succeeds with the updated pyproject.toml
