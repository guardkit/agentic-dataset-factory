---
id: TASK-LR1-008
title: Generate RAG entries for missing set texts
status: backlog
created: 2026-03-30T00:00:00Z
updated: 2026-03-30T00:00:00Z
priority: medium
tags: [coverage, rag, curriculum]
complexity: 4
parent_review: TASK-REV-649A
feature_id: FEAT-LR1
wave: 2
implementation_mode: task-work
dependencies: []
---

# Task: Generate RAG entries for missing set texts

## Description

The RAG knowledge index has critical curriculum gaps:
- **A Christmas Carol**: 0 entries (MISSING)
- **Power & Conflict poetry**: 0 entries (MISSING)
- **Unseen poetry**: 0 entries (MISSING)
- **An Inspector Calls**: 1 entry (CRITICAL GAP)
- **Language Paper 2**: 2 entries (VERY THIN)

Macbeth is over-represented at 48% (35/73 entries).

## Scope

- [ ] Generate ~15-20 knowledge entries for A Christmas Carol (characters, themes, context, key quotes)
- [ ] Generate ~15-20 knowledge entries for Power & Conflict poetry (key poems, themes, techniques, comparison points)
- [ ] Generate ~10-15 knowledge entries for unseen poetry (approach, techniques, mark scheme, common pitfalls)
- [ ] Expand An Inspector Calls from 1 to ~15-20 entries
- [ ] Expand Language Paper 2 from 2 to ~10-15 entries
- [ ] Ensure entries are factual knowledge (not Socratic teaching) — `layer=knowledge`, `type=direct`
- [ ] Cover underrepresented AOs: AO4 (SPaG), AO5, AO6

## Acceptance Criteria

- [ ] All 5 texts have minimum 10 entries each
- [ ] No text exceeds 30% of total RAG index
- [ ] AO4/5/6 each have minimum 8 entries
- [ ] All entries are factually accurate
- [ ] All entries use `type=direct` (no Socratic questioning in knowledge layer)
