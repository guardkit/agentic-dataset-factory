# Implementation Guide: GCSE Training Example Synthesis

**Feature ID:** FEAT-GTS
**Approach:** Sequential Module Build
**Testing:** Full TDD
**Execution:** Auto-detect parallelism

---

## Data Flow: Read/Write Paths

```mermaid
flowchart LR
    subgraph Writes["Write Paths"]
        W1["synthesise.py\nmain_loop()"]
        W2["synthesise.py\nwrite_checkpoint()"]
        W3["synthesise.py\nwrite_rejected()"]
    end

    subgraph Storage["Storage"]
        S1[("generation-plan.yaml\n(YAML, read-only)")]
        S2[("output/train.jsonl\n(JSONL)")]
        S3[("output/rag_index/\nknowledge.jsonl\n(JSONL)")]
        S4[("output/rejected.jsonl\n(JSONL)")]
        S5[("output/.checkpoint.json\n(JSON)")]
    end

    subgraph Reads["Read Paths"]
        R1["synthesise.py\nload_plan()"]
        R2["synthesise.py\nresume_from_checkpoint()"]
        R3["Unsloth fine-tuning\n(Phase 1 downstream)"]
        R4["ChromaDB seeding\n(Phase 2 downstream)"]
        R5["Manual QA\n(spot-check 10%)"]
    end

    S1 -->|"PyYAML load"| R1
    W1 -->|"append + flush"| S2
    W1 -->|"append + flush"| S3
    W3 -->|"append + flush"| S4
    W2 -->|"overwrite"| S5
    S5 -->|"JSON load"| R2
    S2 -->|"SFTTrainer input"| R3
    S3 -->|"collection.add()"| R4
    S2 -->|"human review"| R5
    S4 -->|"human review"| R5
```

_All write paths have corresponding read paths. No disconnections detected._

---

## Integration Contracts

```mermaid
sequenceDiagram
    participant CLI as synthesise.py CLI
    participant Plan as generation-plan.yaml
    participant Tmpl as templates.py
    participant API as Claude API
    participant Val as validator.py
    participant Out as Output Files

    CLI->>Plan: load_plan()
    Plan-->>CLI: GenerationPlan

    loop For each GenerationTarget
        CLI->>Tmpl: select_template(target)
        Tmpl-->>CLI: PromptPair

        CLI->>API: messages.create(model, system, user)
        API-->>CLI: Message (text)

        CLI->>CLI: parse_json(response.text)

        CLI->>Val: validate_example(example, tracker, detector)
        Val-->>CLI: ValidationResult

        alt is_valid
            CLI->>Out: append to route path
        else invalid
            CLI->>Out: append to rejected.jsonl
        end

        CLI->>Out: write .checkpoint.json
    end

    CLI->>CLI: log final summary
```

_Data flows through the complete pipeline: Plan → Template → API → Validation → Output. No "fetch then discard" points._

---

## Task Dependencies

```mermaid
graph TD
    T1[TASK-GTS-001: Project scaffolding] --> T2[TASK-GTS-002: Pydantic models]
    T2 --> T3[TASK-GTS-003: Validation logic]
    T2 --> T4[TASK-GTS-004: Prompt templates]
    T3 --> T5[TASK-GTS-005: Synthesis orchestrator]
    T4 --> T5

    style T3 fill:#cfc,stroke:#090
    style T4 fill:#cfc,stroke:#090
```

_Tasks with green background (TASK-GTS-003 and TASK-GTS-004) can run in parallel._

---

## §4: Integration Contracts

### Contract: VALIDATION_API
- **Producer task:** TASK-GTS-003
- **Consumer task(s):** TASK-GTS-005
- **Artifact type:** Python module API (function + classes)
- **Format constraint:** `validate_example(example, split_tracker, duplicate_detector)` returns `ValidationResult` with fields `is_valid: bool`, `reason: str | None`, `route: str | None`. `SplitTracker` and `DuplicateDetector` are instantiated by the consumer and passed in.
- **Validation method:** Coach verifies that TASK-GTS-005 imports and calls `validate_example` with correct argument types, and handles both `is_valid=True` and `is_valid=False` return values.

### Contract: TEMPLATE_API
- **Producer task:** TASK-GTS-004
- **Consumer task(s):** TASK-GTS-005
- **Artifact type:** Python module API (function + dataclass)
- **Format constraint:** `select_template(target: GenerationTarget)` returns a callable `(GenerationTarget) -> PromptPair`. `PromptPair` has fields `system_prompt: str` and `user_prompt: str`.
- **Validation method:** Coach verifies that TASK-GTS-005 calls `select_template()` for each target, then calls the returned function, and uses both `system_prompt` and `user_prompt` from the PromptPair in the API call.

---

## Execution Strategy

### Wave 1: Foundation (sequential)
| Task | Mode | Est. Time |
|------|------|-----------|
| TASK-GTS-001: Project scaffolding | direct | 15 min |

### Wave 2: Data Models (sequential)
| Task | Mode | Est. Time |
|------|------|-----------|
| TASK-GTS-002: Pydantic models | task-work (TDD) | 45 min |

### Wave 3: Core Modules (parallel)
| Task | Mode | Est. Time |
|------|------|-----------|
| TASK-GTS-003: Validation logic | task-work (TDD) | 60 min |
| TASK-GTS-004: Prompt templates | task-work (TDD) | 45 min |

### Wave 4: Integration (sequential)
| Task | Mode | Est. Time |
|------|------|-----------|
| TASK-GTS-005: Synthesis orchestrator | task-work (TDD) | 90 min |

**Estimated total:** ~4 hours (with Wave 3 parallelism)

---

## Architecture Notes

### Module isolation
`synthesis/` MUST NOT import from `agents/`, `tools/`, or any Phase 2 module. If a shared utility is needed, it goes in a `common/` module.

### Key design decisions
1. **Sync Anthropic client** — matches ADR-ARCH-006 (sequential generation)
2. **Append-per-line writes** with `flush()` — crash-safe JSONL for overnight GB10 runs
3. **Checkpoint file** — enables resumption without duplication
4. **SHA-256 content hashing** — duplicate detection across retries
5. **Structured JSON logging** — matches ADR-ARCH-007

### Confirmed assumptions
- ASSUM-001: ±5% split tolerance (confirmed)
- ASSUM-002: claude-sonnet-4-5 for synthesis (confirmed)
- ASSUM-003: Max 3 retries with exponential backoff 1s/2s/4s (confirmed)
- ASSUM-004: Progress logged every 10 targets (confirmed)
- ASSUM-005: Multi-turn = 4+ messages after system (confirmed)

### Testing approach
Full TDD — tests written before implementation for each module. Mock the Anthropic client in tests (never call the real API). 28 Gherkin scenarios from the feature spec map to unit tests across the 3 test files.
