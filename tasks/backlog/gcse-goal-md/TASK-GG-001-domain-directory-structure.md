---
id: TASK-GG-001
title: "Create domain directory structure and source documents inventory"
task_type: scaffolding
parent_review: TASK-REV-843F
feature_id: FEAT-GG
wave: 1
implementation_mode: direct
complexity: 3
dependencies: []
status: pending
estimated_minutes: 30
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
