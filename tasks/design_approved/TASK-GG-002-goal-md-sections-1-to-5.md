---
id: TASK-GG-002
title: 'Author GOAL.md sections 1-5: Goal, Source Documents, System Prompt, Generation
  Targets, Generation Guidelines'
task_type: feature
parent_review: TASK-REV-843F
feature_id: FEAT-GG
wave: 1
implementation_mode: task-work
complexity: 5
dependencies:
- TASK-GG-001
status: in_review
estimated_minutes: 90
autobuild_state:
  current_turn: 2
  max_turns: 35
  worktree_path: /Users/richardwoollcott/Projects/appmilla_github/agentic-dataset-factory/.guardkit/worktrees/FEAT-FBBC
  base_branch: main
  started_at: '2026-03-21T07:02:36.438218'
  last_updated: '2026-03-21T07:13:25.463405'
  turns:
  - turn: 1
    decision: feedback
    feedback: '- Coverage threshold not met'
    timestamp: '2026-03-21T07:02:36.438218'
    player_summary: Implementation via task-work delegation
    player_success: true
    coach_success: true
  - turn: 2
    decision: approve
    feedback: null
    timestamp: '2026-03-21T07:08:03.249993'
    player_summary: Implementation via task-work delegation
    player_success: true
    coach_success: true
---

# Task: Author GOAL.md sections 1-5

## Description

Populate the first five sections of `domains/gcse-english-tutor/GOAL.md` with GCSE English curriculum content drawn from the research specification.

### Section 1: Goal
Describe the target model personality — a Socratic GCSE English tutor for AQA specification, Year 10, using guided questioning rather than direct answers.

### Section 2: Source Documents
List the reference PDFs with Docling processing modes. Reference the Mr Bruff guides (standard mode) and AQA mark schemes (standard mode). Use file patterns as specified in the API contract.

### Section 3: System Prompt
Copy verbatim from `docs/research/gcse-tutor-training-data-format.md` lines 35-47. This is the canonical system prompt injected into every training example.

### Section 4: Generation Targets
Create the markdown table with 7 categories totalling exactly 1,000 examples at 75/25 reasoning/direct split. Values from `docs/research/gcse-tutor-training-data-format.md` lines 316-327.

### Section 5: Generation Guidelines
Write Player agent instructions covering: Socratic questioning method, AQA mark scheme alignment, think block format for reasoning examples, multi-turn format for essay feedback, age-appropriate language for Year 10.

## Acceptance Criteria

- [ ] Section 1 (Goal): References Socratic questioning, AQA specification, and GCSE English
- [ ] Section 2 (Source Documents): Markdown table with File Pattern, Mode, Notes columns; mode values are "standard" or "vlm" only
- [ ] Section 2: File patterns do not contain ".." or absolute paths (security constraint)
- [ ] Section 3 (System Prompt): Matches research doc verbatim; minimum 100 characters; references AO1-AO6
- [ ] Section 4 (Generation Targets): Table with Category, Type, Count columns; total = 1,000; reasoning >= 75%
- [ ] Section 4: Type values are only "reasoning" or "direct"
- [ ] Section 5 (Generation Guidelines): Minimum 100 characters; references Socratic questioning, mark scheme, think block format
- [ ] All modified files pass project-configured lint/format checks with zero errors

## Source References

- `docs/research/gcse-tutor-training-data-format.md` — canonical system prompt, generation targets, text distribution
- `docs/design/contracts/API-domain-config.md` — section format specifications
- `features/gcse-goal-md/gcse-goal-md.feature` — BDD scenarios for acceptance validation
