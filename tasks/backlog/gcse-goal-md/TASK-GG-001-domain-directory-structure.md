---
id: TASK-GG-001
title: Create domain directory structure and source documents inventory
task_type: scaffolding
parent_review: TASK-REV-843F
feature_id: FEAT-GG
wave: 1
implementation_mode: direct
complexity: 3
dependencies: []
status: in_review
estimated_minutes: 30
autobuild_state:
  current_turn: 1
  max_turns: 35
  worktree_path: /Users/richardwoollcott/Projects/appmilla_github/agentic-dataset-factory/.guardkit/worktrees/FEAT-FBBC
  base_branch: main
  started_at: '2026-03-21T06:59:36.163904'
  last_updated: '2026-03-21T07:02:36.413699'
  turns:
  - turn: 1
    decision: approve
    feedback: null
    timestamp: '2026-03-21T06:59:36.163904'
    player_summary: Created the domain directory structure for gcse-english-tutor
      with sources/ subdirectory, a skeleton GOAL.md with all 9 required section headings
      (Goal, Source Documents, System Prompt, Generation Targets, Generation Guidelines,
      Evaluation Criteria, Output Schema, Metadata Schema, Layer Routing) with TODO
      comments indicating which subsequent tasks will fill the content (TASK-GG-002
      and TASK-GG-003), and added a .gitignore entry to exclude source PDFs. The GOAL.md
      includes empty markdown tables m
    player_success: true
    coach_success: true
---

# Task: Create domain directory structure and source documents inventory

## Description

Create the `domains/gcse-english-tutor/` directory with its required structure: a placeholder `GOAL.md`, a `sources/` subdirectory, and a `.gitkeep` to track the sources directory in git (actual PDFs are gitignored). This establishes the physical layout defined by the API contract in `docs/design/contracts/API-domain-config.md`.

## Acceptance Criteria

- [ ] Directory `domains/gcse-english-tutor/` exists
- [ ] Directory `domains/gcse-english-tutor/sources/` exists with `.gitkeep`
- [ ] A skeleton `GOAL.md` exists with all 9 section headings (content filled by TASK-GG-002 and TASK-GG-003)
- [ ] `.gitignore` entry excludes `domains/*/sources/*.pdf` (source PDFs are large binary files)

## Implementation Notes

Reference: `docs/design/DESIGN.md` target file tree, `docs/design/contracts/API-domain-config.md` directory structure section.

The skeleton GOAL.md should have the 9 headings with TODO placeholders so that subsequent tasks can fill in content independently.
