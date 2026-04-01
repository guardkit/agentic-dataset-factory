---
id: TASK-LR1-011
title: Review RAG entries for knowledge vs behaviour layer misclassification
status: backlog
created: 2026-03-30T00:00:00Z
updated: 2026-03-30T00:00:00Z
priority: low
tags: [data-cleaning, rag, classification]
complexity: 3
parent_review: TASK-REV-649A
feature_id: FEAT-LR1
wave: 2
implementation_mode: task-work
dependencies: [TASK-LR1-008]
---

# Task: Review RAG entries for knowledge vs behaviour layer misclassification

## Description

46/73 RAG knowledge entries (63%) contain Socratic questioning (asking the student questions). Knowledge-layer entries should provide factual reference material, not teaching dialogues. These may be better classified as behaviour-layer examples.

Additionally, 5 entries have `type=reasoning` with `<think>` blocks, which are atypical for knowledge-layer content.

## Scope

- [ ] Write a script to identify RAG entries containing question marks in assistant content
- [ ] Manually review flagged entries to determine if they are:
  - a) Genuine knowledge (factual info that happens to end with a rhetorical question) — keep in RAG
  - b) Teaching dialogues (Socratic method) — move to behaviour layer or remove from RAG
- [ ] Reclassify or remove misclassified entries
- [ ] Review the 5 `type=reasoning` entries for appropriateness in knowledge layer

## Acceptance Criteria

- [ ] All 46 Socratic entries reviewed
- [ ] Misclassified entries reclassified or removed
- [ ] 5 reasoning-type entries reviewed
- [ ] Knowledge index contains only factual reference material
