---
id: TASK-PRF-005
title: Run ingestion pipeline to populate ChromaDB
status: completed
created: 2026-03-22T00:00:00Z
updated: 2026-03-25T00:00:00Z
completed: 2026-03-25T00:00:00Z
completed_location: tasks/completed/TASK-PRF-005/
priority: high
tags: [ingestion, chromadb, P1]
complexity: 4
parent_review: TASK-REV-A1B4
feature_id: FEAT-PRF
wave: 2
implementation_mode: manual
dependencies: [TASK-PRF-002]
test_results:
  status: pass
  coverage: null
  last_run: 2026-03-25T00:00:00Z
---

# Task: Run Ingestion Pipeline to Populate ChromaDB

## Description

Copy source PDFs into the domain sources directory and run the ingestion pipeline to populate ChromaDB. Startup Step 5 (`verify_chromadb_collection()`) fails without a populated collection.

## Prerequisites

- Source PDFs available (Mr Bruff guides, AQA mark schemes)
- Docling venv active on GB10 (`~/.venv/docling/`)
- TASK-PRF-002 complete (agent-config.yaml exists for domain resolution)

## Steps

1. Copy source PDFs to `domains/gcse-english-tutor/sources/`
2. Run `python -m ingestion --domain gcse-english-tutor`
3. Verify ChromaDB collection exists and is populated

## Acceptance Criteria

- [x] Source PDFs placed in `domains/gcse-english-tutor/sources/`
- [x] ChromaDB collection `gcse-english-tutor` exists at `./chroma_data`
- [x] Collection contains > 0 chunks (3,854 chunks)
- [x] Verification script confirms population

## Verification

```bash
python -c "
import chromadb
client = chromadb.PersistentClient(path='./chroma_data')
coll = client.get_collection('gcse-english-tutor')
print(f'Collection: {coll.name}, Chunks: {coll.count()}')
"
```

## Notes

- GOAL.md specifies `standard` Docling mode (digital PDFs) — no VLM needed
- This is a manual task requiring GB10 hardware access
- Ingestion is Stage 0, separate from the generation pipeline (Stage 1)

## Test Execution Log

[Automatically populated by /task-work]
