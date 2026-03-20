---
id: TASK-REV-723B
title: "Plan: LangChain Tools — RAG Retrieval and Write Output"
status: review_complete
created: 2026-03-19T00:00:00Z
updated: 2026-03-19T00:00:00Z
priority: high
task_type: review
tags: [langchain-tools, rag-retrieval, write-output, planning]
complexity: 6
test_results:
  status: pending
  coverage: null
  last_run: null
---

# Task: Plan LangChain Tools — RAG Retrieval and Write Output

## Description

Review and plan the implementation of two LangChain `@tool` decorated functions used exclusively by the Player agent:

1. **`rag_retrieval`** — Retrieves curriculum chunks from ChromaDB relevant to the generation target
2. **`write_output`** — Validates and persists training examples with layer-based routing (behaviour → train.jsonl, knowledge → knowledge.jsonl)

Also covers:
- Factory pattern for tool creation (`create_rag_retrieval_tool`, `create_write_output_tool`)
- Tool assignment invariant: Player gets `[rag_retrieval, write_output]`, Coach gets `[]` (D5)
- Error-string-only contract: all tools return error strings, never raise exceptions (D7)

## Context

- Feature spec: `features/langchain-tools/langchain-tools.feature` (41 BDD scenarios)
- API contract: `docs/design/contracts/API-tools.md`
- Data model: `docs/design/models/DM-training-example.md`
- Architecture: `docs/architecture/ARCHITECTURE.md`

## Acceptance Criteria

- [ ] Technical options analysed with pros/cons
- [ ] Implementation approach recommended
- [ ] Task breakdown with complexity scores
- [ ] Risk assessment completed
- [ ] Dependencies identified

## Review Scope

- Focus: All aspects
- Depth: Standard
- Trade-off priority: Balanced
