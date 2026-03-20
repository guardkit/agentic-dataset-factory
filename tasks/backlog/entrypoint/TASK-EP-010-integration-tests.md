---
id: TASK-EP-010
title: "Integration tests — BDD smoke scenarios"
task_type: testing
parent_review: TASK-REV-9EDC
feature_id: FEAT-2CF1
wave: 4
implementation_mode: task-work
complexity: 4
dependencies:
  - TASK-EP-009
status: pending
---

# Task: Integration Tests — BDD Smoke Scenarios

## Description

Implement integration tests covering the 8 smoke-tagged BDD scenarios from `features/entrypoint/entrypoint.feature`. These tests verify the end-to-end startup and generation flow with mocked external dependencies (LLM, ChromaDB).

## Requirements

### Smoke Scenarios to Cover
1. Loading a valid agent-config.yaml → AgentConfig returned with all sections
2. Structured logging is configured from the config file
3. LangSmith project environment variable is set from the domain
4. Domain directory is resolved and validated
5. GOAL.md is parsed and validated during startup
6. ChromaDB collection is verified to contain chunks
7. Full startup sequence completes and generation loop is invoked
8. Generation loop processes a target through Player-Coach cycle

### Test Approach
- Mock LLM calls (Player and Coach) with predetermined responses
- Mock ChromaDB with in-memory collection containing test chunks
- Use temporary directories for domain and output paths
- Use `pytest` with fixtures for config, domain, and agent setup
- Mark tests with `@pytest.mark.smoke` and `@pytest.mark.integration`

### Key Negative Cases to Include
- Missing agent-config.yaml → FileNotFoundError
- Non-existent domain directory → DomainNotFoundError
- Missing GOAL.md → error with actionable message
- Empty ChromaDB collection → error suggesting ingestion

## Acceptance Criteria

- [ ] All 8 smoke BDD scenarios covered by integration tests
- [ ] Key negative cases tested (missing config, domain, GOAL.md, empty ChromaDB)
- [ ] Tests run with mocked external dependencies (no real LLM/ChromaDB needed)
- [ ] All tests pass with `pytest tests/ -v -m smoke`
- [ ] Test fixtures provide reusable config, domain, and agent setup

## Reference

- BDD scenarios: `features/entrypoint/entrypoint.feature` (all @smoke tagged)
- API contract: `docs/design/contracts/API-entrypoint.md`

## Implementation Notes

Place in `tests/test_entrypoint.py` and `tests/test_generation_loop.py`. Use `pytest-asyncio` if generation loop is async. Create shared fixtures in `tests/conftest.py` for config and domain setup.
