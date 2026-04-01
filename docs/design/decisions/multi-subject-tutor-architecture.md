# ADR: Multi-Subject Tutor Architecture

**Date:** March 2026
**Author:** Rich
**Status:** Decided
**Context:** Expanding the GCSE AI Tutor to cover all of Lilymay's GCSE subjects

---

## Background

Lilymay studies the following subjects at Robert Blake School (United Learning
curriculum, AQA examining board across all subjects — to be verified per subject):

- English Language & Literature
- History
- Maths
- French
- Spanish
- Triple Science (Biology, Chemistry, Physics)

The question raised was whether to create **separate fine-tuned models per
subject**, with a LangChain DeepAgents routing layer selecting the correct
LLM/SLM per session.

**Decision: No. One fine-tuned model, multiple RAG collections.**

---

## Key Principle: The Two-Layer Architecture Already Solves This

The agentic-dataset-factory is built on a deliberate two-layer separation:

| Layer | Purpose | Mechanism |
|---|---|---|
| **Fine-tuning** | Teaches HOW the model responds | `train.jsonl` → Unsloth QLoRA |
| **RAG** | Provides WHAT the model draws from | ChromaDB / Open WebUI Knowledge Collections |

These two layers are **independently updatable**. This is load-bearing.

Tutoring *behaviour* — Socratic questioning, scaffolded feedback, encouragement,
age-appropriate language, AO-aligned assessment — is **subject-agnostic**. A
student struggling with essay structure in History needs identical pedagogical
scaffolding to one struggling with AO2 in English. Fine-tuning teaches the tutor
*how to be a good tutor*, not what the curriculum contains. RAG handles the
curriculum.

Running 6 fine-tuned models would be solving a problem that doesn't exist.

---

## GB10 Hardware Constraint Reinforces This

The GB10 runs a sequential GPU queue. Loading and unloading a 30B model in Ollama
has real latency. One model loaded and resident in VRAM is strictly better for
Lilymay's session experience than subject-based model switching.

---

## The Correct Routing Seam

Routing happens at the **RAG collection layer**, not the model layer.

```
┌────────────────────────────────────────────────────┐
│         One fine-tuned Nemotron tutoring model     │
│                  (Ollama on GB10)                  │
└────────────────────┬───────────────────────────────┘
                     │
          Subject RAG collection selected
                     │
     ┌───────────────┼───────────────────────┐
     │       │       │       │       │       │
 English   Maths  History French Spanish Science
  (done)                              (planned)
```

### Stage 2 — Open WebUI (available as soon as fine-tune completes)

Lilymay opens a chat, picks the subject Knowledge Collection from the dropdown.
The fine-tuned model underneath stays the same. Zero additional infrastructure
required beyond Docling ingestion of subject PDFs.

### Stage 3 — DeepAgents Orchestrator (future)

Intent detection routes to the correct RAG collection automatically:

```
Student message → intent detected → select subject RAG collection
    → inject into context → fine-tuned tutoring model responds
```

Not:

```
Student message → intent detected → load different fine-tuned model  ✗
```

---

## The One Genuine Exception: Maths

Maths has a meaningfully different pedagogy:

- Worked examples and step-by-step arithmetic
- Checking calculations, not analysing language
- "Show me how you'd factorise this" ≠ "What do you notice about this passage?"

**Resolution:** Add a Maths-specific behaviour section to the *same* training
dataset — approximately 500–600 examples demonstrating worked-example tutoring
patterns — rather than creating a separate model. The `metadata.text` field (or
a new `metadata.subject` field) cleanly separates these during generation.

Same model, richer behavioural repertoire.

---

## Deployment Stages

Defined fully in `docs/deployment-and-rag-plan.md`. Summary:

| Stage | What Lilymay gets | Multi-subject status |
|---|---|---|
| **1. Chat** | Fine-tuned model + Open WebUI | English only |
| **2. RAG** | Subject Knowledge Collections in Open WebUI | All subjects — ingest PDFs per subject |
| **3. Agent** | DeepAgents orchestration, automatic subject routing | Requires `domains/` per subject |

Stage 2 is the immediate target. It requires no additional fine-tuning — only:

1. Source PDFs per subject (AQA specs, mark schemes, revision guides)
2. Docling ingestion per subject on the GB10
3. One Knowledge Collection per subject in Open WebUI

---

## Source Material Status

| Subject | Source PDFs | Exam board confirmed | Notes |
|---|---|---|---|
| English | Mr Bruff guides ✅ | AQA ✅ | Fine-tune in progress |
| History | ❌ needed | To verify | AQA likely |
| Maths | ❌ needed | To verify | Foundation vs Higher tier to confirm |
| French | ❌ needed | To verify | AQA likely |
| Spanish | ❌ needed | To verify | AQA likely |
| Triple Science | ❌ needed | To verify | Triple vs Combined Science to confirm — content diverges enough to matter |

**Action:** Confirm exam board and tier/spec per subject from Robert Blake School
website or Lilymay's curriculum materials before ingesting any sources.

---

## Future: Dataset Factory Domains per Subject

When Stage 3 is reached, each subject gets its own `domains/` directory with a
`GOAL.md` and `sources/`. The factory runs per domain sequentially (GB10 GPU
constraint). Generated training data is **merged into a single `train.jsonl`**
before fine-tuning — one model trained on all subjects' behavioural examples.

```
domains/
├── gcse-english-tutor/       ← in progress
├── gcse-maths-tutor/         ← add Maths behaviour examples here first
├── gcse-history-tutor/
├── gcse-french-tutor/
├── gcse-spanish-tutor/
└── gcse-science-tutor/
```

Target accepted examples per subject for comparable quality: **3,000–5,000**.

---

## Run Strategy — Accumulation Warning

> ⚠️ **Critical:** By default `python agent.py` wipes `output/train.jsonl` on
> each run. Runs do NOT automatically accumulate.

Archive before each new long run:

```bash
mkdir -p output_archive/run_N
cp output/train.jsonl output_archive/run_N/
cp output/rag_index/knowledge.jsonl output_archive/run_N/
```

Merge all runs before fine-tuning:

```bash
cat output_archive/run_1/train.jsonl \
    output_archive/run_2/train.jsonl \
    output/train.jsonl > combined/train.jsonl
```

The `--resume` flag resumes a *crashed run only* — it does not append across
independent runs.

---

## Current English Domain Run Parameters

| Parameter | Value |
|---|---|
| Targets per run | 2,500 |
| Expected acceptance rate | ~93% (post TASK-REV-TPF1 fix) |
| Expected accepted examples | ~2,325 |
| Estimated runtime | 65–70 hours |
| Model | Qwen3.5-35B-A3B-FP8 via vLLM on GB10 |
| Token usage | ~18,600 tokens per target |
| "Genuinely useful" threshold | 5,000 accepted examples |

Categories removed due to insufficient RAG source material:

- `Language analysis — unseen poetry` (no Mr Bruff unseen poetry guide available)
- `AO-specific guidance (AO1-AO6)`

Restore in `GOAL.prod.md` when dedicated source documents are added to
`domains/gcse-english-tutor/sources/`.
