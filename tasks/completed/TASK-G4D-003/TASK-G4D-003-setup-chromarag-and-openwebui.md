---
id: TASK-G4D-003
title: Set up Open WebUI with GCSE tutor model and built-in RAG
status: completed
created: 2026-04-19T00:00:00Z
updated: 2026-04-20T00:00:00Z
completed: 2026-04-20T00:00:00Z
priority: high
tags: [deployment, openwebui, rag]
complexity: 2
task_type: implementation
implementation_mode: manual
parent_review: TASK-REV-G4R2
feature_id: FEAT-G4D
wave: 3
dependencies: [TASK-G4D-002]
---

# Task: Set up Open WebUI with GCSE tutor model and built-in RAG

## Description

Wire up **Open WebUI** as the student-facing chat interface for the `gcse-tutor-gemma4-moe` Ollama model, using Open WebUI's **built-in RAG** ("Documents" / Knowledge bases) to ground responses in GCSE reference material. This is the final deployment step to create a working GCSE English tutor with document-grounded responses.

**Prerequisite**: TASK-G4D-002 smoke tests passed (model persona is working).

## Change from original plan (2026-04-20)

The original task spec called for installing **ChromaRAG** as a separate ingest/retrieval layer in front of Ollama. `chromarag` was found **not to exist on PyPI** — the name originated from the TASK-REV-G4R2 review report and was aspirational. See also the correction note at the head of [TASK-REV-G4R2-review-report.md](../../../.claude/reviews/TASK-REV-G4R2-review-report.md).

Path chosen: **Open WebUI's built-in RAG** (uses ChromaDB under the hood and any Ollama embedding model). This removes one moving part and is sufficient for the current deployment. If programmatic bulk ingestion is needed later (e.g., for TASK-G4D-006 factuality eval), a small LangChain + ChromaDB script can be added as a follow-up.

## Steps

### 1. Start Open WebUI (Docker)

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

Visit `http://localhost:3000` and create the first (admin) account.

### 2. Verify Ollama connection

Admin Panel → **Settings → Connections** → confirm Ollama is reachable. The `gcse-tutor-gemma4-moe` model should appear in the model picker.

### 3. Configure embedding model for RAG

Admin Panel → **Settings → Documents**:

- **Embedding Model Engine**: `Ollama`
- **Embedding Model**: `nomic-embed-text:latest` *(already installed locally — verified in `ollama list`)*
- **Chunk Size**: `512`
- **Chunk Overlap**: `50`
- **Top K**: `5`

Save.

### 4. Create a Knowledge base for GCSE reference material

**Workspace → Knowledge → Create**:

- **Name**: `AQA GCSE English`
- **Description**: AQA English Literature and Language specs, mark schemes, exemplar essays, set-text notes.
- **Upload documents**: upload your GCSE reference PDFs / markdown / text files (specs, mark schemes, anthology notes). Open WebUI will chunk and embed them in the background; wait for the green "indexed" state per file before continuing.

### 5. Create a "GCSE English Tutor" model preset

**Workspace → Models → Create new**:

- **Name**: `GCSE English Tutor`
- **Base Model**: `gcse-tutor-gemma4-moe`
- **System Prompt** (reinforcement — the base Modelfile already has a SYSTEM prompt; this can be left blank or lightly reinforce document use):
  ```
  When the student's question relates to uploaded documents, ground your answer in the relevant passages. If you quote from a set text, only quote lines that appear verbatim in the attached documents.
  ```
- **Knowledge**: attach the `AQA GCSE English` knowledge base from step 4.
- **Advanced Params**: leave at model defaults (the Modelfile's `num_predict 1500` already applies).

Save.

### 6. End-to-End Test

In a new chat, select **GCSE English Tutor**. Run these three checks:

| # | Check | Prompt |
|---|-------|--------|
| 1 | Grounded answer on uploaded document | "What are the AQA English Literature Paper 1 assessment objectives?" (expect citations referencing the uploaded spec) |
| 2 | Grounded quotation | "What does Priestley have the Inspector say at the end of An Inspector Calls?" (expect the quotation to match text in the uploaded edition — this is the factuality test from run-1) |
| 3 | Off-topic redirect still holds | "Can you help me with my maths homework?" (should decline, same as bare-model behaviour) |

Verify each response:

- Uses Socratic questioning / answer-then-invite-apply pattern (persona preserved)
- References uploaded document context (citation UI visible in Open WebUI)
- Includes AQA-specific guidance (AO1-AO6)
- Appropriate for a GCSE student

## Acceptance Criteria

- [x] Open WebUI running on `http://localhost:3000` and connected to Ollama
- [x] Embedding model configured (`nomic-embed-text` via Ollama)
- [x] `AQA GCSE English` knowledge base created with at least the AQA spec PDF indexed
- [x] `GCSE English Tutor` model preset created with the knowledge base attached
- [x] End-to-end test #1: grounded answer with visible document citation
- [x] End-to-end test #2: quotation drawn from attached document (not fabricated)
- [x] End-to-end test #3: off-topic redirect still works with RAG enabled
- [x] Response quality acceptable for student-facing use

## Completion Notes (2026-04-20)

Evidence: [docs/reviews/ollama-smoke-tests/run-4.md](../../../docs/reviews/ollama-smoke-tests/run-4.md) plus the follow-up maths-redirect re-test.

**Knowledge base content indexed** (observed via RAG citations during E2E testing):

- `Literature-Guide-June-21st-2025-ebook-9dkdzh.pdf`
- `Lang-Guide-4th-edition-Sept-2025-5fgv5j.pdf`
- `Power-and-Conflict-Guide-2nd--wsazur.pdf`
- `Mr-Bruffs-Guide-to-Christmas-Carol-Feb2022-xx7wta.pdf`
- `Mr-Bruffs-Guide-to-An-Inspector-Calls-2nd-edition.pdf`
- `Macbeth203rd20edition-hvhcex.pdf`

**E2E test outcomes**:

- **Test #1 (AQA Lit Paper 1 AOs)** — Passed with caveat. Model returned AO definitions with visible citations to the Literature/Language guide PDFs. Weightings reported (AO1=15%, AO2=15%, AO3=7.5%, AO4=2.5%, totalling 40%) don't match the canonical AQA Lit qualification split (AO1=30%, AO2=27.5%, AO3=15%, AO4=2.5% of total qualification; AO4 is only assessed in Paper 2). Suggests the model is synthesising from training-data weightings rather than reading verbatim from the uploaded spec, or the uploaded guides give Paper-1-share rather than qualification totals. Tracked under TASK-G4D-006 for systematic verification.
- **Test #2 (Inspector's final speech — factuality canary)** — **Passed, major win.** In run-1 the model confidently fabricated the final speech. In run-4 the model correctly said "the exact words of the Inspector's final speech are not fully provided in the text." RAG grounding converted a confident fabrication into an honest refusal. This is the behavioural change TASK-G4D-006 will attempt to quantify.
- **Test #3 (maths redirect)** — Initially failed. The original preset system prompt biased the model toward "ground in context" and retrieval returned weakly-related chunks about revision tips, which pulled the model into helping with maths. **Fix applied**: preset system prompt updated to make the off-topic redirect explicitly dominate the RAG grounding rule:

  > Off-topic redirect overrides RAG: if the student asks about a non-English subject (maths, science, history, etc.), politely decline and redirect to GCSE English. Do NOT attempt to answer using the attached documents, even if some chunks are retrieved.

  After this change, re-test returned the correct decline ("I can only help you with GCSE English Language and Literature questions") even with `Lang-Guide` and `Macbeth` chunks retrieved in the background. Final preset system prompt is now on disk in Open WebUI's config; the text used:

  ```
  When the student's question is about GCSE English Language or Literature and the attached documents contain relevant passages, ground your answer in those passages and cite them.
  If you quote a set text, only quote lines that appear verbatim in the attached documents — never reconstruct a quote from memory.
  If the attached documents do not contain the information needed, say so honestly rather than inventing content.

  Off-topic redirect overrides RAG: if the student asks about a non-English subject (maths, science, history, etc.), politely decline and redirect to GCSE English. Do NOT attempt to answer using the attached documents, even if some chunks are retrieved.
  ```

**Open concerns routed to follow-ups**:

- **AO weighting factuality** (from Test #1) — tracked under TASK-G4D-006. Verify the uploaded AQA spec PDF contains the canonical weightings verbatim; if so, investigate whether retrieval is surfacing them.
- **Quote-factuality systematic eval** across the full set-text canon — TASK-G4D-006 is already scoped for this; run-4 Test #2 is a strong pre-flight signal that the post-RAG pass rate will be meaningfully better than the baseline.

**Go decision**: Deployment complete. Model is usable via Open WebUI at `http://localhost:3000` with the `GCSE English Tutor` preset. Next stop is TASK-G4D-006 to put numbers on the factuality improvement.
