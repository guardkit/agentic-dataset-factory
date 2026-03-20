# Implementation Guide: GCSE English Tutor GOAL.md — First Domain Configuration

> Feature: FEAT-GG | Review: TASK-REV-843F
> Approach: Authoring-Only (write GOAL.md + validation tests)

## Architecture Overview

This feature creates the first concrete domain configuration — a pure markdown file at `domains/gcse-english-tutor/GOAL.md` consumed by 6 downstream modules. No Python code is produced for the GOAL.md itself; the validation tests ensure content consistency with the existing Pydantic models in `synthesis/validator.py`.

```
domains/gcse-english-tutor/
├── GOAL.md              ← 9 required sections (this feature)
├── golden_set.jsonl     ← optional, future work
└── sources/
    ├── .gitkeep
    └── (PDFs added separately, gitignored)
```

## Data Flow: Read/Write Paths

```mermaid
flowchart LR
    subgraph Writes["Write Paths"]
        W1["TASK-GG-001\nCreate directory"]
        W2["TASK-GG-002\nSections 1-5"]
        W3["TASK-GG-003\nSections 6-9"]
    end

    subgraph Storage["Storage"]
        S1[("domains/gcse-english-tutor/\nGOAL.md")]
        S2[("synthesis/validator.py\nPydantic models")]
    end

    subgraph Reads["Read Paths"]
        R1["TASK-GG-004\nMetadata consistency tests"]
        R2["TASK-GG-005\nStructural smoke tests"]
        R3["parse_goal_md()\n(FEAT-5606, future)"]
        R4["agent.py entrypoint\n(future)"]
        R5["prompts/ module\n(future)"]
        R6["ingestion/ module\n(future)"]
    end

    W1 -->|"mkdir + skeleton"| S1
    W2 -->|"populate sections 1-5"| S1
    W3 -->|"populate sections 6-9"| S1

    S1 -->|"read + parse tables"| R1
    S2 -->|"import TEXT_VALUES,\nTOPIC_VALUES"| R1
    S1 -->|"read + regex"| R2
    S1 -->|"Path.read_text()"| R3
    S1 -.->|"NOT WIRED"| R4
    S1 -.->|"NOT WIRED"| R5
    S1 -.->|"NOT WIRED"| R6

    style W1 fill:#cfc,stroke:#090
    style W2 fill:#cfc,stroke:#090
    style W3 fill:#cfc,stroke:#090
    style R1 fill:#cfc,stroke:#090
    style R2 fill:#cfc,stroke:#090
    style R3 fill:#ffc,stroke:#cc0
    style R4 fill:#fcc,stroke:#c00
    style R5 fill:#fcc,stroke:#c00
    style R6 fill:#fcc,stroke:#c00
```

_Green = this feature. Yellow = planned (FEAT-5606). Red = future features (not yet planned)._

**Disconnection Alert**: 3 read paths (R4, R5, R6) have no caller yet. These are expected — they will be wired when the entrypoint, prompts, and ingestion modules are implemented in future features. This GOAL.md is the foundation they will consume.

## Integration Contracts

```mermaid
sequenceDiagram
    participant GG002 as TASK-GG-002<br/>Sections 1-5
    participant GG003 as TASK-GG-003<br/>Sections 6-9
    participant GOALMD as GOAL.md<br/>(on disk)
    participant GG004 as TASK-GG-004<br/>Consistency Tests
    participant Validator as synthesis/validator.py

    GG002->>GOALMD: Write sections 1-5
    GG003->>GOALMD: Write sections 6-9

    GG004->>GOALMD: Parse metadata table
    GG004->>Validator: Import TEXT_VALUES, TOPIC_VALUES
    GG004->>GG004: Compare valid values

    Note over GG004,Validator: Values must match:<br/>GOAL.md text ⊇ TEXT_VALUES<br/>GOAL.md topic ⊇ TOPIC_VALUES
```

_Shows the cross-validation contract between GOAL.md content and existing Pydantic models._

## Task Dependencies

```mermaid
graph TD
    T1["TASK-GG-001<br/>Directory Structure"]
    T2["TASK-GG-002<br/>Sections 1-5"]
    T3["TASK-GG-003<br/>Sections 6-9"]
    T4["TASK-GG-004<br/>Metadata Consistency Tests"]
    T5["TASK-GG-005<br/>Structural Smoke Tests"]

    T1 --> T2
    T1 --> T3
    T2 --> T4
    T3 --> T4
    T2 --> T5
    T3 --> T5

    style T2 fill:#cfc,stroke:#090
    style T3 fill:#cfc,stroke:#090
    style T4 fill:#cfc,stroke:#090
    style T5 fill:#cfc,stroke:#090
```

_Tasks with green background can run in parallel within their wave._

## §4: Integration Contracts

### Contract: METADATA_VALID_VALUES
- **Producer task:** TASK-GG-003 (Sections 6-9, specifically the Metadata Schema table)
- **Consumer task(s):** TASK-GG-004 (Metadata consistency tests)
- **Artifact type:** Markdown table rows in GOAL.md
- **Format constraint:** Text and topic valid values in the GOAL.md Metadata Schema table must be a superset of the `Literal` values defined in `synthesis/validator.py`'s `Metadata` model. Specifically: every value in `TEXT_VALUES` must appear in the GOAL.md `text` field's Valid Values column, and every value in `TOPIC_VALUES` must appear in the `topic` field's Valid Values column.
- **Validation method:** TASK-GG-004 pytest tests parse the GOAL.md table and assert `set(TEXT_VALUES).issubset(goal_md_text_values)` and `set(TOPIC_VALUES).issubset(goal_md_topic_values)`.

### Contract: GOAL_MD_STRUCTURE
- **Producer task:** TASK-GG-002 and TASK-GG-003 (complete GOAL.md content)
- **Consumer task(s):** TASK-GG-005 (Structural smoke tests)
- **Artifact type:** Markdown file on disk
- **Format constraint:** Must contain exactly 9 `## Section` headings matching the names defined in `docs/design/contracts/API-domain-config.md`. Generation Targets table must sum to 1,000. Reasoning split must be >= 70%.
- **Validation method:** TASK-GG-005 pytest tests use regex to find section headings and parse table rows to sum counts.

## Execution Strategy

### Wave 1: Content Authoring (3 tasks)

| Task | Description | Complexity | Mode | Parallel |
|------|-------------|-----------|------|----------|
| TASK-GG-001 | Create directory structure + skeleton | 3 | direct | Foundation |
| TASK-GG-002 | Sections 1-5 content | 5 | task-work | After GG-001 |
| TASK-GG-003 | Sections 6-9 content | 5 | task-work | After GG-001 |

**Execution:** TASK-GG-001 runs first (direct mode, ~15 min). Then TASK-GG-002 and TASK-GG-003 can run in parallel — they write to different sections of the same file, but since TASK-GG-001 creates the skeleton with all 9 headings, each task fills in its own sections without conflict.

### Wave 2: Validation Tests (2 tasks — parallel)

| Task | Description | Complexity | Mode | Parallel |
|------|-------------|-----------|------|----------|
| TASK-GG-004 | Metadata consistency tests | 4 | task-work | ✅ |
| TASK-GG-005 | Structural smoke tests | 4 | task-work | ✅ |

**Execution:** Both test tasks can run in parallel. They read the GOAL.md but write to separate test files (`tests/test_goal_md_consistency.py` and `tests/test_goal_md_structure.py`).

## Key Design Decisions

1. **Authoring-only, not parser-coupled**: The GOAL.md is pure markdown. Writing it is independent of the parser (FEAT-5606). This allows both features to progress in parallel.

2. **Cross-validation against existing code**: Rather than waiting for the parser, we test GOAL.md metadata values against the already-implemented Pydantic models in `synthesis/validator.py`. This catches drift immediately.

3. **Content from research doc**: The system prompt, generation targets, and metadata values are drawn verbatim from `docs/research/gcse-tutor-training-data-format.md` — minimising creative decisions and ensuring consistency with the research specification.

4. **Skeleton-then-fill pattern**: TASK-GG-001 creates all 9 section headings as a skeleton, allowing TASK-GG-002 and TASK-GG-003 to fill sections independently without merge conflicts.

## BDD Scenario Coverage Map

| Task | BDD Scenarios Covered (from gcse-goal-md.feature) |
|------|--------------------------------------------------|
| TASK-GG-001 | Directory existence (Background preconditions) |
| TASK-GG-002 | Lines 22-28 (Goal), 30-36 (Source Docs), 39-46 (System Prompt), 50-55 (Gen Targets), 59-63 (Gen Guidelines) |
| TASK-GG-003 | Lines 68-73 (Eval Criteria), 77-81 (Output Schema), 85-93 (Metadata Schema), 97-100 (Layer Routing), 104-108 (Complete GoalConfig) |
| TASK-GG-004 | Lines 234-237 (text coverage), 275-276 (language paper text IDs), 324-328 (topic consistency) |
| TASK-GG-005 | Lines 114-118 (total=1000), 122-125 (75/25 split), 129-132 (70% min), 144-148 (weights=100%), 157-162 (grade_target range) |

## Risk Mitigations

| Risk | Likelihood | Mitigation |
|------|-----------|-----------|
| Metadata values drift from validator.py | Medium | TASK-GG-004 explicitly cross-validates |
| Gen targets don't sum to 1,000 | Low | TASK-GG-005 asserts exact sum |
| Eval criteria weights don't sum to 100% | Low | TASK-GG-005 asserts within ±1% |
| System prompt doesn't match research doc | Low | Copy verbatim; TASK-GG-005 checks length |
| TASK-GG-002 and GG-003 conflict on same file | Medium | Skeleton pattern: each fills its own sections |
| Source doc patterns attempt path traversal | Low | TASK-GG-005 checks for ".." in patterns |
