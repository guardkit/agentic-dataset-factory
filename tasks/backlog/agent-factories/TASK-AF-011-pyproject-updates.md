---
id: TASK-AF-011
title: Update pyproject.toml for agent factories
task_type: scaffolding
parent_review: TASK-REV-DAA1
feature_id: FEAT-AF
wave: 1
implementation_mode: direct
complexity: 1
dependencies: []
status: in_review
tags:
- pyproject
- dependencies
- packaging
autobuild_state:
  current_turn: 1
  max_turns: 35
  worktree_path: /Users/richardwoollcott/Projects/appmilla_github/agentic-dataset-factory/.guardkit/worktrees/FEAT-5AC9
  base_branch: main
  started_at: '2026-03-20T22:47:21.311315'
  last_updated: '2026-03-20T22:54:38.223814'
  turns:
  - turn: 1
    decision: approve
    feedback: null
    timestamp: '2026-03-20T22:47:21.311315'
    player_summary: Updated pyproject.toml to add deepagents>=0.4.11, langchain>=0.3,
      langchain-core>=0.3, langchain-community>=0.3, and langgraph>=0.2 to project
      dependencies. Added agents*, prompts*, config* to setuptools package discovery
      includes. Added config/tests, agents/tests, prompts/tests to pytest testpaths.
      Created agents/ and prompts/ package stubs with __init__.py and tests/ subdirectories.
      Verified pip install -e . succeeds with the updated configuration.
    player_success: true
    coach_success: true
---

# Task: Update pyproject.toml for agent factories

## Description

Update `pyproject.toml` to include the new `agents`, `prompts`, and `config` packages and ensure `deepagents>=0.4.11` is listed as a dependency.

## Acceptance Criteria

- [ ] `deepagents>=0.4.11` is in project dependencies (if not already)
- [ ] Package includes updated for `agents*`, `prompts*`, `config*` (if using packages discovery)
- [ ] Test paths include new test locations
- [ ] `pip install -e .` succeeds with the updated pyproject.toml
