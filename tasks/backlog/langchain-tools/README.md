# Feature: LangChain Tools — RAG Retrieval and Write Output

## Problem

The Player agent in the adversarial generation pipeline needs two tools: one to retrieve curriculum chunks from ChromaDB for grounding, and one to validate and persist accepted training examples to the correct output files based on layer routing. The Coach agent must have no tools (D5 invariant).

## Solution

Closure-based factory pattern producing LangChain `@tool`-decorated functions:

- `create_rag_retrieval_tool(collection_name)` → `rag_retrieval(query, n_results=5) -> str`
- `create_write_output_tool(output_dir, metadata_schema)` → `write_output(example_json) -> str`
- `create_player_tools(...)` → `[rag_retrieval, write_output]`
- `create_coach_tools()` → `[]`

All tools return error strings, never raise exceptions (D7 contract).

## Tasks

| ID | Task | Complexity | Wave | Mode |
|----|------|-----------|------|------|
| TASK-LCT-001 | Tools package + Pydantic models | 3 | 1 | direct |
| TASK-LCT-002 | rag_retrieval factory + tool | 5 | 2 | task-work |
| TASK-LCT-003 | write_output factory + tool + layer routing | 6 | 2 | task-work |
| TASK-LCT-004 | Tool assignment + factory wiring | 3 | 3 | direct |
| TASK-LCT-005 | Unit + integration tests (41 BDD scenarios) | 5 | 3 | task-work |

## Dependencies

- **FEAT-5606** (Goal MD Parser) — provides `MetadataField` for write_output validation
- **FEAT-F59D** (Ingestion Pipeline) — populates ChromaDB collections for rag_retrieval

## Review

Original review: TASK-REV-723B
