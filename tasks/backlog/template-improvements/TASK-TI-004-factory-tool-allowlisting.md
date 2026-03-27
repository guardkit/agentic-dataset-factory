---
id: TASK-TI-004
title: Factory tool allowlisting with assertions
status: backlog
created: 2026-03-27T22:00:00Z
updated: 2026-03-27T22:00:00Z
priority: p1
tags: [template, factory, security, base-template]
complexity: 4
parent_review: TASK-REV-TRF12
feature_id: FEAT-TI
wave: 2
implementation_mode: task-work
depends_on: []
test_results:
  status: pending
  coverage: null
  last_run: null
---

# Task: Factory Tool Allowlisting with Assertions

## Description

Create factory guard utilities for the `langchain-deepagents` base template that enforce tool allowlisting and prevent the tool leakage bugs that dominated runs 1-6.

## What to Build

### 1. `assert_tool_inventory(agent, expected_tools: set[str])`
- Post-factory assertion: `assert set(t.name for t in agent.tools) == expected_tools`
- Raises `ToolLeakageError` with diff showing unexpected/missing tools
- Called at factory exit, not just in tests

### 2. `create_restricted_agent()` wrapper
- Bypasses `create_deep_agent()` for agents that must NOT have filesystem tools
- Uses `create_agent()` directly with explicit middleware stack
- Inline docstring warning:
  ```
  # WARNING: create_deep_agent() unconditionally injects FilesystemMiddleware
  # (8 tools: ls, read_file, write_file, edit_file, glob, grep, execute, write_todos)
  # Use create_restricted_agent() for agents that must have curated tool access.
  ```

### 3. Factory template (`agent_factory.py.j2`)
- Jinja2 template generating factory functions with tool allowlists baked in
- Each agent role gets explicit `allowed_tools` parameter
- Generated code includes the assertion at factory exit

## Fixes Prevented

TRF-003, TRF-012, TRF-016, TRF-017

## Target Location

`lib/factory_guards.py` + `scaffold/agent_factory.py.j2` (in the template output)

## Acceptance Criteria

- [ ] `assert_tool_inventory()` raises on unexpected tools
- [ ] `create_restricted_agent()` bypasses FilesystemMiddleware
- [ ] Inline SDK warning in docstring where developers hit it
- [ ] Factory template generates allowlisted factories
- [ ] Unit tests for leakage detection
- [ ] Regression test: create_deep_agent + backend=None still leaks (documents the SDK behaviour)

## Effort Estimate

1 day
