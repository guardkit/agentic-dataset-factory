---
id: TASK-EP-004
title: "Domain resolution and ChromaDB readiness check"
task_type: feature
parent_review: TASK-REV-9EDC
feature_id: FEAT-2CF1
wave: 2
implementation_mode: task-work
complexity: 3
dependencies:
  - TASK-EP-002
status: pending
---

# Task: Domain Resolution and ChromaDB Readiness Check

## Description

Implement startup steps 4-6 from the API-entrypoint contract: resolve the domain directory path, validate GOAL.md exists within it, and verify the ChromaDB collection contains indexed chunks.

## Requirements

- Resolve domain path: `domains/{config.domain}/`
- Raise `DomainNotFoundError` if domain directory doesn't exist
- Raise error if `GOAL.md` missing from domain directory
- Connect to ChromaDB embedded PersistentClient
- Get collection by domain name (DDR-003 naming: domain directory name)
- Raise error with actionable message if collection has zero chunks:
  `"No chunks found for '{domain}'. Run: python -m ingestion.ingest --domain {domain}"`
- Set `LANGSMITH_PROJECT` env var to `"adf-{config.domain}"` (step 3)
- Warn (don't block) if `LANGSMITH_TRACING=true` but no `LANGSMITH_API_KEY` (ASSUM-004)

## Acceptance Criteria

- [ ] Domain path resolved to `domains/{domain}/`
- [ ] `DomainNotFoundError` raised for non-existent domain (BDD: "Startup with non-existent domain directory")
- [ ] Error raised for missing GOAL.md (BDD: "Startup with missing GOAL.md in domain directory")
- [ ] ChromaDB collection verified to contain chunks (BDD: "ChromaDB collection is verified to contain chunks")
- [ ] Error raised for empty collection with ingestion suggestion (BDD: "Startup with empty ChromaDB collection")
- [ ] Error raised when ChromaDB service unavailable (BDD: "ChromaDB service is unavailable at startup")
- [ ] `LANGSMITH_PROJECT` set to `"adf-{domain}"` (BDD: "LangSmith project environment variable is set")
- [ ] Warning logged if tracing enabled without API key (BDD: "LangSmith tracing enabled but API key is missing")
- [ ] All modified files pass project-configured lint/format checks with zero errors

## Reference

- API contract: `docs/design/contracts/API-entrypoint.md` (Startup Sequence steps 3-6)
- BDD scenarios: `features/entrypoint/entrypoint.feature` (key examples + negative cases)
- ASSUM-004: LangSmith tracing non-blocking

## Implementation Notes

Place in `entrypoint/startup.py`. Define `DomainNotFoundError` in `config/exceptions.py`.
