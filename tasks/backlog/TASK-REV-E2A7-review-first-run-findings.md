---
id: TASK-REV-E2A7
title: Review first run findings and plan GB10 deployment
status: review_complete
created: 2026-03-25T00:00:00Z
updated: 2026-03-25T00:00:00Z
priority: critical
tags: [review, first-run, debugging, gb10, deployment]
complexity: 6
task_type: review
decision_required: true
review_results:
  mode: decision
  depth: comprehensive
  score: 35
  findings_count: 5
  recommendations_count: 5
  decision: implement
  report_path: .claude/reviews/TASK-REV-E2A7-review-report.md
  completed_at: 2026-03-25T00:00:00Z
test_results:
  status: pending
  coverage: null
  last_run: null
---

# Task: Review First Run Findings and Plan GB10 Deployment

## Description

Review the findings from the first end-to-end run of the agentic-dataset-factory pipeline using Qwen2.5-14B-Instruct on the GB10 via Tailscale. The run completed 8 successful API round trips but timed out at 600s with 0 accepted, 1 rejected.

## Source Document

`docs/reviews/first-run/vllm-qwen-25-1.md`

## Key Findings to Analyse

### 1. RAG Retrieval Failing (P0)

- Every `rag_retrieval` tool call returned errors: "error retrieving the relevant curriculum chunks"
- The Player agent could not retrieve source material from ChromaDB
- **Root cause hypothesis**: ChromaDB `chroma_data/` was populated on the MacBook during TASK-PRF-005, but the DeepAgents Player's `rag_retrieval` tool connects to ChromaDB locally — the tool runs on the MacBook where `chroma_data/` exists, so this should work. Need to inspect the actual error returned by the tool.
- **Decision needed**: Is this a connection issue, collection name mismatch, or something else?

### 2. write_output Validation Failing — metadata.ao Field (P1)

- When the model generated examples without RAG context, `write_output` rejected them
- Repeated validation errors on `metadata.ao` field format
- The model couldn't produce `["AO1", "AO2"]` in the format the validator expects
- **Decision needed**: Is this a validator bug (too strict) or model output issue?

### 3. Infinite Retry Loop (P1)

- The model correctly followed its workflow (rag_retrieval → generate → write_output)
- But failed RAG + failed validation = infinite retry loop
- 8 round trips, each growing the context (2 → 16 role entries), until 600s timeout
- **Decision needed**: Should the generation loop have a max-iterations-per-target limit?

### 4. Model Suitability (P2)

- Qwen2.5-14B actually performed well mechanically — correct tool calls, self-correction attempts
- The issues were in tool implementations, not model capability
- However, running on GB10 port 8000 (shared with Graphiti) is not ideal
- A dedicated vLLM instance on port 8002 with `--enable-auto-tool-choice --tool-call-parser hermes` was created (`vllm-agentic-factory.sh`)

### 5. GB10 Deployment Consideration (P1)

- Currently running MacBook → GB10 (Tailscale) for LLM inference
- ChromaDB runs locally on MacBook (populated during TASK-PRF-005)
- The ingestion pipeline (Docling) was also run on MacBook
- **Decision needed**: Should the entire pipeline (ingestion + generation) run on GB10 directly?
  - Pro: Eliminates network latency, ChromaDB and LLM co-located
  - Pro: GB10 has Docling venv already configured
  - Con: Requires cloning repo and setting up environment on GB10
  - Con: ChromaDB data would need to be regenerated on GB10

## Acceptance Criteria

- [ ] RAG retrieval error root cause identified (inspect actual tool error message)
- [ ] metadata.ao validation issue root cause identified
- [ ] Decision made on retry loop bounds
- [ ] Decision made on GB10 vs MacBook deployment strategy
- [ ] Implementation tasks created for each confirmed finding

## Decisions Required

1. **RAG retrieval fix** — What is the actual error from ChromaDB? Connection, collection name, or query issue?
2. **Validation strictness** — Should `write_output` be more lenient on ao field format, or should we fix the model prompt?
3. **Loop bounds** — Add max iterations per DeepAgents agent turn (e.g., 10 tool calls max)?
4. **Deployment strategy** — Run everything on GB10, or keep split MacBook/GB10 architecture?

## Suggested Follow-Up Tasks (if findings accepted)

| Priority | Task | Description |
|----------|------|-------------|
| P0 | TASK-FIX-RAG | Debug and fix rag_retrieval tool ChromaDB connection |
| P0 | TASK-FIX-AO-VALID | Fix metadata.ao validation or model prompt for correct format |
| P1 | TASK-LOOP-BOUNDS | Add max tool-call iterations to prevent timeout loops |
| P1 | TASK-GB10-DEPLOY | Set up full pipeline on GB10 (repo clone, venv, ChromaDB) |
| P2 | TASK-SECOND-RUN | Re-run with fixes applied |

## Implementation Notes

This is a review/analysis task. Use `/task-review TASK-REV-E2A7` to execute the review, then create implementation tasks for accepted findings.

## Test Execution Log

[Automatically populated by /task-work]
