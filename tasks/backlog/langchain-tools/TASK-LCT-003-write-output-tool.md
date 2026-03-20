---
id: TASK-LCT-003
title: "Implement create_write_output_tool factory and write_output tool with layer routing"
task_type: feature
parent_review: TASK-REV-723B
feature_id: FEAT-LCT
wave: 2
implementation_mode: task-work
complexity: 6
dependencies:
  - TASK-LCT-001
status: pending
priority: high
tags: [langchain-tools, write-output, layer-routing, validation]
consumer_context:
  - task: TASK-LCT-001
    consumes: METADATA_SCHEMA
    framework: "Pydantic v2 (BaseModel + field_validator)"
    driver: "pydantic"
    format_note: "list[MetadataField] where each MetadataField has field, type, required, valid_values attributes"
---

# Task: Implement create_write_output_tool factory and write_output tool with layer routing

## Description

Implement the `create_write_output_tool(output_dir: Path, metadata_schema: list[MetadataField])` factory function that returns a LangChain `@tool`-decorated `write_output` function. The tool validates training examples against the schema and routes them to the correct output file based on `metadata.layer`.

## Deliverables

1. `src/tools/write_output.py` — Factory + tool implementation
   - `create_write_output_tool(output_dir: Path, metadata_schema: list[MetadataField]) -> Callable`
   - Inner `write_output(example_json: str) -> str`

## Acceptance Criteria

- [ ] Factory returns a LangChain `@tool`-decorated callable
- [ ] Output directory and metadata schema are bound at factory time
- [ ] Validation checks executed in order per API contract (10 checks):
  1. Parse JSON → reject if invalid
  2. Check `messages` exists and is non-empty array
  3. Check `messages[0].role == "system"`
  4. Check `metadata` exists and is object
  5. Check `metadata.layer` ∈ {"behaviour", "knowledge"}
  6. Check `metadata.type` ∈ {"reasoning", "direct"}
  7. If reasoning: verify last assistant message contains `<think>` block
  8. If direct: verify last assistant message does NOT contain `<think>` block
  9. Validate all metadata fields against GOAL.md Metadata Schema valid values
  10. Append validated JSON line to correct output file
- [ ] Layer routing: behaviour → `{output_dir}/train.jsonl`, knowledge → `{output_dir}/rag_index/knowledge.jsonl`
- [ ] Append mode — each example appended as single JSON line
- [ ] Atomic writes — each line flushed immediately (no buffering)
- [ ] Success message format: `"Written to {path} (example #{N})"`
- [ ] Error messages match API contract exactly (e.g., `"Error: Invalid JSON"`)
- [ ] JSON content with embedded newlines/escapes written as single valid JSON line
- [ ] Large content (>100KB) written without truncation
- [ ] Partial write failure leaves file in consistent state
- [ ] All errors returned as descriptive strings, never raised as exceptions (D7)
- [ ] All modified files pass project-configured lint/format checks with zero errors

## Seam Tests

The following seam test validates the integration contract with the metadata schema from TASK-LCT-001.

```python
"""Seam test: verify METADATA_SCHEMA contract from TASK-LCT-001."""
import pytest


@pytest.mark.seam
@pytest.mark.integration_contract("METADATA_SCHEMA")
def test_metadata_schema_format():
    """Verify METADATA_SCHEMA matches the expected format.

    Contract: list[MetadataField] where each MetadataField has field, type, required, valid_values attributes
    Producer: TASK-LCT-001
    """
    # Producer side: get the schema
    schema = []  # e.g., from GoalConfig.metadata_schema

    # Consumer side: verify format matches contract
    assert isinstance(schema, list), "METADATA_SCHEMA must be a list"
    # Each entry must have field, type, required, valid_values attributes
    # for field_def in schema:
    #     assert hasattr(field_def, 'field'), f"MetadataField missing 'field' attribute"
    #     assert hasattr(field_def, 'valid_values'), f"MetadataField missing 'valid_values'"
```

## Reference

- API contract: `docs/design/contracts/API-tools.md` (Tool 2: write_output)
- Data model: `docs/design/models/DM-training-example.md`
- Output contract: `docs/design/contracts/API-output.md`
- BDD scenarios: `features/langchain-tools/langchain-tools.feature` (Groups A-D write_output scenarios)

## Implementation Notes

- Use `json.dumps(example, ensure_ascii=False)` for JSONL serialisation
- Flush after each write: `f.write(line + "\n"); f.flush()`
- For atomic writes consider: write to temp file, then `os.replace()` is overkill for append — use `open(path, "a")` with immediate flush per ADR-ARCH-006 (single writer)
- Create `rag_index/` subdirectory on first knowledge-layer write if not exists
- Track example count per file (closure state) for success message numbering
