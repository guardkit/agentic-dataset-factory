# Implementation Guide: Ingestion Pipeline

## Architecture: Thin Orchestrator + Isolated Components

```
ingestion/
├── __init__.py          # Public API exports
├── __main__.py          # CLI entry point (argparse)
├── ingest.py            # ingest_domain() orchestrator
├── goal_reader.py       # Read GOAL.md Source Documents, resolve file patterns
├── docling_processor.py # Docling standard + VLM extraction (lazy import)
├── chunker.py           # chunk_text() via RecursiveCharacterTextSplitter
├── chromadb_indexer.py  # ChromaDB PersistentClient collection CRUD + batch upsert
├── models.py            # Chunk, IngestResult, SourceDocument stub, ExtractedDocument
└── errors.py            # IngestionError hierarchy
```

## Data Flow: Read/Write Paths

```mermaid
flowchart LR
    subgraph Writes["Write Paths"]
        W1["goal_reader.read_source_documents()"]
        W2["docling_processor.process_document()"]
        W3["chunker.chunk_text()"]
        W4["chromadb_indexer.index_chunks()"]
    end

    subgraph Storage["Storage"]
        S1[("GOAL.md\n(file)")]
        S2[("Source PDFs\n(files)")]
        S3[("In-memory chunks\n(list[Chunk])")]
        S4[("ChromaDB collection\n(PersistentClient)")]
    end

    subgraph Reads["Read Paths"]
        R1["ingest.py orchestrator"]
        R2["Generation pipeline\n(Stage 1 - tools/rag_retrieval)"]
    end

    S1 -->|"parse Source Documents table"| W1
    W1 -->|"list[SourceDocument]"| R1

    S2 -->|"PDF bytes"| W2
    W2 -->|"ExtractedDocument"| R1

    R1 -->|"extracted text"| W3
    W3 -->|"list[Chunk]"| S3

    S3 -->|"chunks + metadata"| W4
    W4 -->|"batch upsert"| S4

    S4 -->|"similarity search"| R2

    style R1 fill:#cfc,stroke:#090
    style R2 fill:#cfc,stroke:#090
```

_All write paths have corresponding read paths. No disconnections detected._

## Integration Contracts

```mermaid
sequenceDiagram
    participant CLI as __main__.py
    participant O as ingest.py
    participant GR as goal_reader
    participant DP as docling_processor
    participant CH as chunker
    participant CI as chromadb_indexer

    CLI->>O: ingest_domain(domain_name, chunk_size, overlap, force)
    O->>GR: read_source_documents(domain_path)
    GR-->>O: list[SourceDocument]
    O->>GR: resolve_source_files(domain_path, source_docs)
    GR-->>O: list[(Path, mode)]

    O->>CI: create_or_replace_collection(domain_name, force)
    CI-->>O: Collection

    loop For each (file_path, mode)
        O->>DP: process_document(file_path, mode)
        DP-->>O: ExtractedDocument
        loop For each page in ExtractedDocument
            O->>CH: chunk_text(page.text, chunk_size, overlap, metadata)
            CH-->>O: list[Chunk]
        end
    end

    O->>CI: index_chunks(collection, all_chunks, batch_size=500)
    CI-->>O: chunks_indexed_count

    O-->>CLI: IngestResult
```

_Data flows from CLI through orchestrator to each component and back. No data is fetched and discarded._

## §4: Integration Contracts

### Contract: SourceDocument

- **Producer task:** TASK-DC-001 (Create domain_config package and Pydantic models) — part of FEAT-5606
- **Consumer task(s):** TASK-ING-005 (Implement GOAL.md Source Documents reader)
- **Artifact type:** Python class (Pydantic BaseModel)
- **Format constraint:** `SourceDocument` with fields `file_pattern: str`, `mode: Literal["standard", "vlm"]`, `notes: str = ""`. Until TASK-DC-001 completes, the ingestion pipeline uses a compatible stub in `ingestion/models.py`.
- **Validation method:** Seam test in TASK-ING-005 verifies the SourceDocument contract (field names, types, and mode literal values)

## Task Dependencies

```mermaid
graph TD
    T1[TASK-ING-001: Package + Models<br/>scaffolding, c:3] --> T2[TASK-ING-002: Chunker<br/>feature, c:4]
    T1 --> T3[TASK-ING-003: Docling Processor<br/>feature, c:5]
    T1 --> T4[TASK-ING-004: ChromaDB Indexer<br/>feature, c:5]
    T1 --> T5[TASK-ING-005: GOAL Reader<br/>feature, c:3]
    T2 --> T6[TASK-ING-006: Orchestrator + CLI<br/>feature, c:5]
    T3 --> T6
    T4 --> T6
    T5 --> T6
    T6 --> T7[TASK-ING-007: Integration Tests<br/>testing, c:5]

    DC1[TASK-DC-001: Pydantic Models<br/>FEAT-5606, external] -.->|"SourceDocument model"| T5

    style T2 fill:#cfc,stroke:#090
    style T3 fill:#cfc,stroke:#090
    style T4 fill:#cfc,stroke:#090
    style T5 fill:#cfc,stroke:#090
    style DC1 fill:#ffc,stroke:#cc0
```

_Tasks with green background can run in parallel within their wave. Yellow = external dependency._

## Execution Strategy

### Wave 1: Foundation (parallel)
- **TASK-ING-001:** Create package, models, errors (scaffolding, direct)
- **TASK-ING-002:** Implement chunker (feature, task-work) — can start as soon as `models.py` exists

### Wave 2: Components (parallel)
- **TASK-ING-003:** Docling processor (feature, task-work)
- **TASK-ING-004:** ChromaDB indexer (feature, task-work)
- **TASK-ING-005:** GOAL.md reader (feature, direct)

All three can run in parallel — they depend only on TASK-ING-001 (models/errors), not on each other.

### Wave 3: Orchestration
- **TASK-ING-006:** Orchestrator + CLI (feature, task-work) — depends on all Wave 1-2 tasks

### Wave 4: Verification
- **TASK-ING-007:** Integration tests (testing, task-work) — depends on TASK-ING-006

## Key Design Decisions

1. **Lazy Docling import** — Docling is heavy (~2GB models); import only when `process_document()` is called
2. **Sequential document processing** — per ADR-ARCH-006, no parallel processing in v1
3. **Batch ChromaDB indexing** — configurable batch_size (default 500) to avoid OOM on large collections
4. **SourceDocument stub** — use temporary stub until FEAT-5606 Wave 1 completes; seam test validates contract
5. **Deterministic chunk IDs** — `{domain}_{source_file}_{chunk_index}` for idempotent re-indexing
6. **Force re-ingestion warning** — ASSUM-004 (concurrent access unsafe) logged on `--force`

## Dependencies to Add

```toml
# pyproject.toml additions
dependencies = [
    # ... existing ...
    "docling>=2.0",
    "chromadb>=0.5",
    "langchain-text-splitters>=0.3",
]
```

## Risk Mitigations

| Risk | Mitigation |
|------|------------|
| Docling VLM fails on GB10 | Mock VLM in tests; fallback to standard mode with warning |
| Large PDF OOM | Sequential processing + structured logging of memory milestones |
| GOAL.md parser not ready | SourceDocument stub + seam test ensures safe migration |
| Concurrent re-ingestion | ASSUM-004 warning logged on `--force`; documented in CLI help |
