---
id: TASK-G4D-003
title: Set up ChromaRAG and Open WebUI with GCSE tutor model
status: backlog
created: 2026-04-19T00:00:00Z
priority: high
tags: [deployment, chromarag, openwebui, rag]
complexity: 3
task_type: implementation
implementation_mode: manual
parent_review: TASK-REV-G4R2
feature_id: FEAT-G4D
wave: 3
dependencies: [TASK-G4D-002]
---

# Task: Set up ChromaRAG and Open WebUI with GCSE tutor model

## Description

Configure ChromaRAG for retrieval-augmented generation with GCSE reference documents, and wire up Open WebUI as the student-facing chat interface. This is the final deployment step to create a working GCSE English tutor with document-grounded responses.

**Prerequisite**: TASK-G4D-002 smoke tests passed (model persona is working).

## Part A: ChromaRAG Setup

1. **Install ChromaRAG** (if not already installed):
   ```bash
   pip install chromarag
   ```

2. **Ingest GCSE reference documents**:
   ```bash
   chromarag ingest \
     --collection gcse-english \
     --input-dir ~/Documents/GCSE-English-Resources/ \
     --chunk-size 512 \
     --chunk-overlap 50
   ```

3. **Configure ChromaRAG** to use the Ollama model:
   ```yaml
   # chromarag-config.yaml
   llm:
     provider: ollama
     model: gcse-tutor-gemma4-moe
     base_url: http://localhost:11434
   vectorstore:
     provider: chromadb
     collection: gcse-english
     persist_directory: ~/.chromarag/gcse-english
   retrieval:
     top_k: 5
     score_threshold: 0.7
   ```

4. **Test RAG retrieval**:
   ```bash
   chromarag query \
     --collection gcse-english \
     "What are the assessment objectives for AQA English Literature Paper 1?"
   ```

## Part B: Open WebUI Setup

1. **Start Open WebUI** (Docker method):
   ```bash
   docker run -d \
     --name open-webui \
     -p 3000:8080 \
     -v open-webui:/app/backend/data \
     -e OLLAMA_BASE_URL=http://host.docker.internal:11434 \
     --add-host=host.docker.internal:host-gateway \
     --restart always \
     ghcr.io/open-webui/open-webui:main
   ```

2. **Access at** `http://localhost:3000` and create account

3. **Create "GCSE English Tutor" model preset**:
   - Workspace > Models > Create new
   - Base model: `gcse-tutor-gemma4-moe`
   - System prompt (reinforcement):
     ```
     You are an expert GCSE English tutor supporting students studying the AQA specification.
     Use Socratic questioning to guide students to discover answers.
     Reference the uploaded documents for accurate specification details.
     ```
   - Enable RAG/document context
   - Attach GCSE document collections

4. **Upload reference documents** via Documents section (or connect to ChromaDB)

5. **Configure embedding model**: Settings > Documents > set to `nomic-embed-text` via Ollama

## End-to-End Test

Select "GCSE English Tutor" in Open WebUI, attach a relevant document (e.g., AQA mark scheme), and ask:

> "How should I structure a Grade 9 response to an extract question on Macbeth?"

Verify the response:
- Uses Socratic questioning
- References the attached document context
- Includes AQA-specific guidance (AO1-AO4)
- Is appropriate for a GCSE student

## Acceptance Criteria

- [ ] ChromaRAG collection populated with GCSE reference documents
- [ ] RAG retrieval returns relevant chunks for test queries
- [ ] Open WebUI running and connected to Ollama
- [ ] "GCSE English Tutor" preset created with RAG enabled
- [ ] End-to-end test: student question -> RAG retrieval -> tutor response
- [ ] Response quality acceptable for student-facing use
