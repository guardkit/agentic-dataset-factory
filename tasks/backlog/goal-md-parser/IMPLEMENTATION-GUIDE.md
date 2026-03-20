# Implementation Guide: GOAL.md Parser and Strict Validation

> Feature: FEAT-5606 | Review: TASK-REV-DC5D
> Approach: Pydantic v2 Models + Regex Section Splitter

## Architecture Overview

The `domain_config` module is a **leaf module** with no dependencies on other project modules. It reads GOAL.md files from disk and produces a validated `GoalConfig` object consumed by 6 downstream modules.

```
domain_config/
├── __init__.py      ← public API: parse_goal_md, GoalConfig, GoalValidationError
├── models.py        ← Pydantic v2 models for all data structures
├── parser.py        ← Section splitting, table parsing, JSON extraction, parse_goal_md()
└── validators.py    ← Cross-section validation rules, error aggregation
```

## Data Flow: Read/Write Paths

```mermaid
flowchart LR
    subgraph Writes["Write Paths"]
        W1["GOAL.md\n(authored by user)"]
    end

    subgraph Storage["Storage"]
        S1[("GOAL.md file\n(markdown on disk)")]
    end

    subgraph Reads["Read Paths"]
        R1["parse_goal_md()\n→ GoalConfig"]
        R2["agent.py entrypoint"]
        R3["prompts/player_prompts.py"]
        R4["prompts/coach_prompts.py"]
        R5["ingestion/ingest.py"]
        R6["tools/write_output.py"]
    end

    W1 -->|"user creates/edits"| S1

    S1 -->|"Path.read_text()"| R1
    R1 -->|"GoalConfig"| R2
    R1 -->|"generation_guidelines,\nsystem_prompt"| R3
    R1 -->|"evaluation_criteria"| R4
    R1 -->|"source_documents"| R5
    R1 -->|"output_schema,\nmetadata_schema,\nlayer_routing"| R6

    style W1 fill:#cfc,stroke:#090
    style R1 fill:#cfc,stroke:#090
    style R2 fill:#ffc,stroke:#cc0
    style R3 fill:#ffc,stroke:#cc0
    style R4 fill:#ffc,stroke:#cc0
    style R5 fill:#ffc,stroke:#cc0
    style R6 fill:#ffc,stroke:#cc0
```

_Green = implemented by this feature. Yellow = downstream consumers (not yet implemented, will be wired by future features)._

**No disconnections**: All read paths have a clear caller chain. The downstream consumers (R2-R6) will be wired when their respective modules are implemented. This is expected — `domain_config` is the foundation module built first.

## Integration Contracts

```mermaid
sequenceDiagram
    participant User as User/Operator
    participant Entry as agent.py
    participant Parser as parse_goal_md()
    participant Split as split_sections()
    participant Table as parse_table()
    participant JSON as extract_json()
    participant Valid as validate_goal_config()

    User->>Entry: run pipeline(domain_name)
    Entry->>Parser: parse_goal_md(Path)
    Parser->>Parser: read file from disk

    Parser->>Split: split_sections(content)
    Split-->>Parser: dict[str, str] (9 sections)

    loop For each table section
        Parser->>Table: parse_table(body, Model, col_map)
        Table-->>Parser: list[Model]
    end

    Parser->>JSON: extract_json(output_schema_body)
    JSON-->>Parser: dict

    Parser->>Valid: validate_goal_config(sections, config)
    Note over Valid: Checks all 10 rules
    Note over Valid: Aggregates ALL errors
    Valid-->>Parser: None (or raises GoalValidationError)

    Parser-->>Entry: GoalConfig
    Entry->>Entry: Use GoalConfig for pipeline orchestration
```

_Shows the internal call sequence. validate_goal_config receives all parsed data and checks cross-section rules._

## Task Dependencies

```mermaid
graph TD
    T1["TASK-DC-001\nPydantic Models"]
    T2["TASK-DC-002\nSection Splitter"]
    T3["TASK-DC-003\nTable + JSON Parsers"]
    T4["TASK-DC-004\nCross-Section Validation"]
    T5["TASK-DC-005\nPublic API + Integration Tests"]

    T1 --> T2
    T1 --> T3
    T2 --> T4
    T3 --> T4
    T4 --> T5

    style T2 fill:#cfc,stroke:#090
    style T3 fill:#cfc,stroke:#090
```

_Tasks with green background can run in parallel._

## §4: Integration Contracts

### Contract: SECTION_DICT
- **Producer task:** TASK-DC-002 (Section splitter)
- **Consumer task(s):** TASK-DC-004 (Cross-section validation), TASK-DC-005 (Public API)
- **Artifact type:** Python dict return value
- **Format constraint:** `dict[str, str]` with exactly 9 keys matching the required section names. Values are stripped body text.
- **Validation method:** Coach verifies `split_sections()` returns dict with all 9 keys; consumer calls it directly.

### Contract: PARSED_MODELS
- **Producer task:** TASK-DC-003 (Table + JSON parsers)
- **Consumer task(s):** TASK-DC-004 (Cross-section validation), TASK-DC-005 (Public API)
- **Artifact type:** Python lists of Pydantic model instances
- **Format constraint:** `list[SourceDocument]`, `list[GenerationTarget]`, `list[EvaluationCriterion]`, `list[MetadataField]`, `dict` (output schema), `dict[str, str]` (layer routing). All instances are validated Pydantic models.
- **Validation method:** Coach verifies return types match model classes; Pydantic validation ensures field constraints.

## Execution Strategy

### Wave 1: Foundation (1 task — direct mode)

| Task | Description | Complexity | Mode |
|------|-------------|-----------|------|
| TASK-DC-001 | Create domain_config package + Pydantic models | 3 | direct |

**Rationale**: Simple declarative task. No architectural decisions — models are fully specified by the API contract.

### Wave 2: Parsing (2 tasks — parallel, task-work mode)

| Task | Description | Complexity | Mode |
|------|-------------|-----------|------|
| TASK-DC-002 | Markdown section splitter | 4 | task-work |
| TASK-DC-003 | Table parser + JSON extractor | 5 | task-work |

**Rationale**: These tasks operate on independent concerns (section splitting vs table/JSON parsing) and share no files. Safe to run in parallel.

### Wave 3: Validation + API (2 tasks — sequential, task-work mode)

| Task | Description | Complexity | Mode |
|------|-------------|-----------|------|
| TASK-DC-004 | Cross-section validation + error aggregation | 5 | task-work |
| TASK-DC-005 | Public API + integration tests | 4 | task-work |

**Rationale**: TASK-DC-004 depends on both Wave 2 tasks. TASK-DC-005 depends on TASK-DC-004 (needs validation to compose the full API). These must run sequentially within Wave 3.

## Key Design Decisions

1. **Pydantic v2 over dataclasses**: Consistent with existing `synthesis/validator.py`. Gives us `field_validator`, `Literal` types, and rich error messages for free.

2. **Whitelist regex splitter**: Only split on the 9 known section headings. This handles the edge case where content contains `## Example Approach` without creating a false section boundary.

3. **Error aggregation pattern**: Collect all failures in a `list[tuple[str, str]]` then raise a single `GoalValidationError`. This matches assumption ASSUM-002 (report all errors at once).

4. **Counts authoritative, percentages advisory**: Per assumption ASSUM-003, the reasoning split is calculated from counts, not percentages.

## BDD Scenario Coverage Map

| Task | BDD Scenarios Covered |
|------|----------------------|
| TASK-DC-001 | Model construction, field types |
| TASK-DC-002 | Lines 21-25 (valid), 146-162 (missing sections), 220-224 (empty), 229-234 (whitespace), 272-277 (embedded headings) |
| TASK-DC-003 | Lines 36-40 (Source Docs), 50-56 (Gen Targets), 57-63 (Eval Criteria), 66-71 (Output Schema), 75-79 (Layer Routing), 237-241 (table formatting), 309-314 (nested fences), 317-322 (empty Valid Values) |
| TASK-DC-004 | Lines 84-140 (all boundary), 172-217 (all negative validation), 253-260 (multiple failures), 280-286 (keyword), 298-304 (percentages) |
| TASK-DC-005 | Full integration: all 36 scenarios end-to-end |

## Risk Mitigations

| Risk | Mitigation |
|------|-----------|
| Embedded `##` headings | Whitelist approach — only 9 known names trigger splits |
| Table formatting variations | Strip/trim all cells, handle missing trailing pipes |
| JSON code fence edge cases | Extract between first `` ```json `` and next `` ``` `` only |
| Unicode content | Python 3.11 handles UTF-8 natively; no special handling needed |
