---
id: TASK-TRF-011
title: Restore langchain-skills from backup
status: completed
created: 2026-03-26T00:00:00Z
updated: 2026-03-27T00:00:00Z
completed: 2026-03-27T00:00:00Z
completed_location: tasks/completed/TASK-TRF-011/
priority: critical
tags: [devtools, skills, P0, prerequisite]
complexity: 1
task_type: implementation
parent_review: TASK-REV-TRF5
feature_id: FEAT-TRF5
wave: 0
implementation_mode: direct
depends_on: []
test_results:
  status: pass
  coverage: null
  last_run: 2026-03-27T00:00:00Z
---

# Task: Restore langchain-skills from Backup

## Description

langchain-skills were installed before the exemplar build (2026-03-16) but lost on 2026-03-17 when `~/.claude/` was restructured. A complete backup exists at `~/.claude.backup.20260317_101318/skills/` with all 11 skills.

The AutoBuild that created this repo ran without skills loaded, contributing to incorrect fix decisions (TASK-TRF-003).

## Implementation

```bash
cp -r ~/.claude.backup.20260317_101318/skills ~/.claude/skills
```

Verify installation:
```bash
ls ~/.claude/skills/
# Expected: 11 directories including deep-agents-core, deep-agents-memory, deep-agents-orchestration
```

## Acceptance Criteria

- [x] `~/.claude/skills/` directory exists with all 11 skill directories
- [x] Each skill directory contains a SKILL.md file
- [x] Claude Code can access skills during subsequent task-work sessions

## Context

This is a **prerequisite** for all other Wave 1 tasks. The skills provide Claude Code with expert DeepAgents SDK knowledge needed to correctly implement the Coach factory fix (TASK-TRF-012) and reasoning extraction (TASK-TRF-013).
