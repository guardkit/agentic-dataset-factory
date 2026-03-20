---
complexity: 5
dependencies:
- TASK-LCT-002
- TASK-LCT-003
- TASK-LCT-004
feature_id: FEAT-LCT
id: TASK-LCT-005
implementation_mode: task-work
parent_review: TASK-REV-723B
priority: high
status: design_approved
tags:
- langchain-tools
- testing
- bdd
- pytest
task_type: testing
title: Unit and integration tests for LangChain tools (41 BDD scenarios)
wave: 3
---

# Task: Unit and integration tests for LangChain tools

## Description

Create comprehensive test coverage for the tools module, mapping to the 41 BDD scenarios in `features/langchain-tools/langchain-tools.feature`. Tests should cover all key examples, boundary conditions, negative cases, and edge cases.

## Deliverables

1. `synthesis/tests/tools/test_rag_retrieval.py` — rag_retrieval tool tests
2. `synthesis/tests/tools/test_write_output.py` — write_output tool tests
3. `synthesis/tests/tools/test_factory.py` — Tool assignment and factory tests
4. `synthesis/tests/tools/conftest.py` — Shared fixtures (mock ChromaDB, temp output dirs, sample metadata schema)

## Test Coverage Mapping

### rag_retrieval (16 scenarios)

**Key examples (@smoke):**
- Valid query returns formatted chunks with source metadata
- Default n_results returns exactly 5 chunks
- Tool bound to correct collection name
- Tool errors returned as strings, not exceptions

**Boundary:**
- n_results=20 (max) returns exactly 20
- n_results=21 returns error string
- n_results=1 returns exactly 1
- n_results=0 returns error string
- Collection has fewer chunks than requested

**Negative:**
- Collection not found → error string
- ChromaDB unavailable → error string
- Collection name with path traversal → rejected at factory

**Edge cases:**
- Lazy ChromaDB init on first call, reuse on subsequent
- Low-relevance query returns top chunks (no error)
- Chunks with missing metadata returned with available info

### write_output (22 scenarios)

**Key examples (@smoke):**
- Valid behaviour-layer example → train.jsonl
- Valid knowledge-layer example → rag_index/knowledge.jsonl
- Reasoning type with think block → success
- Direct type without think block → success
- Invalid JSON → error string (D7)

**Boundary:**
- Empty messages array → error
- Minimal 3-message example → success
- Multi-turn 5-message example → success

**Negative:**
- Invalid JSON → "Error: Invalid JSON"
- Missing messages → "Error: Missing required field 'messages'"
- Missing metadata → "Error: Missing required field 'metadata'"
- messages[0].role != "system" → error
- Invalid layer value → error with valid values listed
- Invalid type value → error
- Reasoning without think block → error
- Direct with think block → error
- Invalid metadata text value → error with valid values

**Edge cases:**
- Multiple writes accumulate (append mode)
- Each write flushed immediately
- Mixed layer routing in one session
- Tool bound to configured output directory
- Tool validates against injected metadata schema
- JSON with embedded newlines written as single line
- Large content (>100KB) written without truncation
- Partial write failure leaves consistent state
- Single-writer assumption (sequential, no interleaving)

### Factory (3 scenarios)

- Player gets [rag_retrieval, write_output]
- Coach gets [] (empty)
- Coach has no access to either tool

## Acceptance Criteria

- [ ] All 41 BDD scenarios have corresponding pytest tests
- [ ] Smoke tests (@smoke) marked with `@pytest.mark.smoke` for fast CI runs
- [ ] ChromaDB mocked in unit tests (no real database dependency)
- [ ] Output file tests use `tmp_path` fixture (clean isolation)
- [ ] Tests validate exact error message strings per API contract
- [ ] No test depends on execution order (fully isolated)
- [ ] All tests pass with `pytest synthesis/tests/tools/ -v`

## Reference

- BDD spec: `features/langchain-tools/langchain-tools.feature`
- Assumptions: `features/langchain-tools/langchain-tools_assumptions.yaml`
- pytest config: `pyproject.toml` ([tool.pytest.ini_options])

## Implementation Notes

- Use `unittest.mock.patch` for ChromaDB client mocking
- Use `pytest.mark.parametrize` for boundary value tests (n_results edge cases)
- Test fixtures should create fresh tool instances per test (factory pattern)
- Use `tmp_path` for all file-writing tests
- Mark seam tests with `@pytest.mark.seam` per pyproject.toml config