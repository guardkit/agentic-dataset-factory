# Study Tutor Factory — Training Pipeline Plan

> Prepared: March 2026  
> Project: `agentic-dataset-factory` → `study-tutor-factory`  
> Author: Rich Woollcott  
> Status: Planning

---

## Overview

This document captures the two-phase plan for producing, fine-tuning, and evaluating a
GCSE English AI tutor model (Nemotron 3 Nano 30B-A3B via QLoRA/Unsloth on the GB10).

The two phases are intentionally designed as a **controlled ablation study**: both produce
training data in the same format, use the same base model, and are evaluated against the
same golden set. The only variable is how the training data was generated. This means
Phase 1 and Phase 2 results are directly comparable, and the comparison measures the
concrete value added by the Player-Coach adversarial loop.

---

## Background: why this approach, not RLVR

The NVIDIA NeMo workflow (NeMo Data Designer + RLVR/GRPO) is designed for domains where
quality can be verified by code — e.g. CLI command syntax is either valid or it isn't.
A deterministic reward function exists, so reinforcement learning is appropriate.

GCSE tutoring quality is a **semantic** problem. There is no regex for "did the tutor use
Socratic questioning correctly while aligning to AO2 for a Grade 7 target?" This requires
pedagogical judgment. LLM-as-judge (the Coach agent) is the correct quality gate for this
problem class.

The key architectural principle (from Daniel Bourke, March 2026):

> **Fine-tuning teaches behaviour, not facts.**

This is why the dataset has two independently routed layers:
- `behaviour` layer → `train.jsonl` → Unsloth fine-tuning (teaches *how* the model tutors)
- `knowledge` layer → `rag_index/knowledge.jsonl` → ChromaDB seeding (provides *what* it draws from)

---

## Repository structure

Both phases live in the **same repository**. This is a deliberate decision, not a default.

The strongest reason is what the phases share, not how they differ. Both phases:
- Read from the same `domains/gcse-english-tutor/` config and `GOAL.md`
- Produce output in the same JSONL schema to the same `output/` paths
- Are evaluated against the same `golden_set.jsonl`
- Feed the same downstream `study-tutor-factory` fine-tuning pipeline

Splitting into separate repos would require either duplicating domain config or introducing
a cross-repo dependency, and would make the Phase 1 vs Phase 2 ablation comparison an
inter-repo coordination problem.

The architectural difference between phases (Phase 1: plain Python script, Phase 2:
LangGraph agents + ChromaDB) is handled by **directory isolation**, not repo separation.

### Target structure

```
agentic-dataset-factory/
│
├── domains/
│   └── gcse-english-tutor/
│       ├── GOAL.md
│       ├── generation-plan.yaml     ← ordered generation targets (shared by both phases)
│       ├── golden_set.jsonl         ← hand-curated eval set (committed)
│       └── sources/                 ← gitignored (copyrighted source PDFs)
│
├── synthesis/                       ← Phase 1 lives entirely here
│   ├── README.md                    ← "Phase 1 manual synthesis — see training-pipeline-plan.md"
│   ├── synthesise.py                ← main generation script
│   ├── templates.py                 ← synthesis prompts from gcse-tutor-training-data-format.md
│   ├── validator.py                 ← schema + 75/25 split + layer routing validation
│   └── tests/
│       ├── test_synthesise.py
│       ├── test_templates.py
│       └── test_validator.py
│
├── agents/                          ← Phase 2 (not yet built)
├── tools/                           ← Phase 2
├── ingestion/                       ← Phase 2
├── prompts/                         ← Phase 2
│
├── output/                          ← shared by both phases (gitignored)
│   ├── train.jsonl
│   ├── rag_index/
│   │   └── knowledge.jsonl
│   └── rejected.jsonl
│
├── checkpoints/                     ← gitignored (large model files)
│   ├── phase1/
│   └── phase2/
│
└── evals/
    ├── phase1/
    │   └── results.json             ← generated, gitignored
    └── phase2/
        └── results.json             ← generated, gitignored
```

The `synthesis/` directory is fully self-contained — it does not import from `agents/`,
`tools/`, or any Phase 2 module. It reads from `domains/` and writes to `output/`.

### The generation plan

A key design decision for Phase 1 reproducibility: the synthesis script is driven by
`domains/gcse-english-tutor/generation-plan.yaml` — a structured, committed list of
`(text, topic, grade_target, layer, type)` tuples ordered to hit the composition targets
in `gcse-tutor-training-data-format.md`.

This is preferable to random sampling from distribution targets because:
- The Phase 1 baseline checkpoint is **reproducible** — same plan, same distribution
- The Phase 1 vs Phase 2 comparison is cleaner (same targets, different generation method)
- Phase 2 Player agent reads the same file as its generation target list

```yaml
# domains/gcse-english-tutor/generation-plan.yaml (excerpt)
generation_targets:
  - text: macbeth
    topic: character_analysis
    grade_target: 7
    layer: behaviour
    type: reasoning
  - text: a_christmas_carol
    topic: essay_feedback
    grade_target: 6
    layer: behaviour
    type: reasoning
  - text: an_inspector_calls
    topic: factual_recall
    grade_target: null
    layer: knowledge
    type: direct
  # ... 200-300 total entries
```

---

## Tooling: Claude Code and GuardKit commands

Phase 1 is well-suited to Claude Code. It is a contained Python scripting task —
no agents, no LangGraph, no ChromaDB — approximately 200–300 lines across three modules.
The `.claude/rules/guidance/` specialists already configured in this repo
(`pytest-factory-test-specialist.md`, `system-prompt-engineer.md`) apply directly.

### GuardKit slash command evaluation

| Command | Phase 1 applicability | Verdict |
|---------|----------------------|---------|
| `/feature-spec` | Generates Gherkin acceptance criteria for the synthesis script using the Propose-Review methodology. Pass `gcse-tutor-training-data-format.md` and this document as `--context`. Produces the spec that drives `task-work`. | **Use** |
| `/task-create` | Creates the implementation task file that `/task-work` reads. Documentation only — no code. | **Use** |
| `/task-work` | Implements the synthesis script against the feature spec acceptance criteria. Use `--autobuild-mode` for autonomous execution on GB10. | **Use** |
| `/system-plan` | Not needed — Phase 1 is too small and focused. Architecture is already documented. | **Skip** |
| `task-complete`, `task-status` | Standard workflow hygiene. | **Use as normal** |

### Recommended Claude Code workflow for Phase 1

**Step 1 — Feature spec**

```bash
/feature-spec "Generate GCSE English training examples via Claude API synthesis" \
  --context docs/research/gcse-tutor-training-data-format.md \
  --context docs/research/training-pipeline-plan.md
```

Curate the Gherkin scenarios in the Propose-Review loop. Key acceptance criteria to
ensure are covered:

- Correct JSONL output format (ShareGPT schema with metadata)
- 75/25 reasoning/direct split enforced as generation proceeds
- Metadata schema validation (all required fields present and valid)
- Text and topic distribution matches `generation-plan.yaml` targets
- Layer routing: `behaviour` → `train.jsonl`, `knowledge` → `rag_index/knowledge.jsonl`
- Malformed / invalid API responses written to `rejected.jsonl` with reason
- Progress logged as structured JSON (count, distribution, rejection rate)

**Step 2 — Task creation**

```bash
/task-create "Phase 1 synthesis script: generate GCSE training examples" \
  priority:high
```

**Step 3 — Implementation**

```bash
/task-work TASK-XXX
```

The synthesis script responsibilities:
- Load generation targets from `domains/gcse-english-tutor/generation-plan.yaml`
- Call `claude-sonnet-4-5` via Anthropic API using the appropriate prompt template
  (reasoning vs direct, single-turn vs multi-turn essay feedback)
- Track running 75/25 split and adjust template selection to maintain it
- Validate output schema before writing
- Route to `train.jsonl` or `rag_index/knowledge.jsonl` based on `layer` field
- Write invalid outputs to `rejected.jsonl` with reason code
- Log progress periodically (structured JSON: count, accepted, rejected, split ratio)

---

## Phase 1 — Manual synthesis pipeline (baseline)

### Goal

Produce ~200–300 high-quality training examples using the synthesis prompt templates
already specified in `gcse-tutor-training-data-format.md`, calling the Claude API directly.
Fine-tune Nemotron 3 Nano on this data and run against the golden set to establish a
**baseline eval score**.

This phase is not a throwaway prototype. It becomes the reference checkpoint against which
every subsequent improvement is measured.

### Steps

1. **Use existing synthesis prompts** from `gcse-tutor-training-data-format.md`
   - "Generate Reasoning Example (Single Turn)"
   - "Generate Multi-Turn Essay Feedback Example"
   - These are already parameterised for text, AO, and grade target

2. **Drive generation from `generation-plan.yaml`** — iterate through all targets in order,
   calling the synthesis script for each. This ensures reproducible distribution.

3. **Generate ~200–300 examples** via Claude API, distributed across:
   - Literary analysis (single-turn, reasoning mode)
   - Essay feedback (multi-turn, reasoning mode)
   - Exam technique guidance (reasoning mode)
   - Factual recall / terminology (direct mode)
   - Encouragement / session management (direct mode)

4. **Manual quality gate** — spot-check ~10% of examples (20–30) against the rubric:
   - Does the assistant use Socratic questioning (guides rather than gives)?
   - Is the AO classification correct?
   - Is the analysis factually accurate per AQA criteria?
   - Is tone age-appropriate for Year 10?

5. **Enforce 75/25 split** — 75% reasoning mode (with `<think>` blocks), 25% direct.
   This is a hard constraint for Nemotron 3 Nano MoE to preserve reasoning capability
   post-fine-tune.

6. **Fine-tune on GB10** via Unsloth QLoRA on the accepted examples.

7. **Run eval against golden set** — produces the Phase 1 baseline score.

### Output

| File | Purpose |
|------|---------|
| `output/train.jsonl` | Behaviour layer — fine-tuning input |
| `output/rag_index/knowledge.jsonl` | Knowledge layer — RAG seed |
| `output/rejected.jsonl` | Invalid/malformed outputs with reason code |
| `checkpoints/phase1/` | Fine-tuned Nemotron checkpoint |
| `evals/phase1/results.json` | Eval scores against golden set |

### What Phase 1 teaches

- Whether the data format and system prompt are correct
- Whether the 75/25 reasoning split is working as intended
- Whether the golden set is sensitive enough to detect quality differences
- Baseline metric to beat in Phase 2

---

## Phase 2 — Player-Coach adversarial factory

### Goal

Use the `agentic-dataset-factory` pipeline (Player-Coach adversarial agent loop + RAG
retrieval from Docling-indexed source documents) to generate a larger, higher-quality
dataset. Fine-tune and evaluate using identical settings to Phase 1. Compare results.

### Architecture

The pipeline is defined in full in:
- `docs/architecture/ARCHITECTURE.md` — module decomposition, ADRs, deployment topology
- `docs/architecture/system-context.md` — C4 Level 1
- `docs/architecture/container.md` — C4 Level 2
- `docs/architecture/domain-model.md` — entity relationships and layer routing

Key components:

```
Stage 0: Ingest (one-time)
  Docling processes sources/ → chunks → ChromaDB collection

Stage 1: Generate (Player-Coach loop, runs overnight on GB10)
  For each generation target in generation-plan.yaml:
    Player: retrieve chunks via rag_retrieval → generate example → submit to Coach
    Coach: evaluate against GOAL.md criteria → accept or reject with structured JSON
    If rejected (turns < max_turns): Player revises → resubmits
    If accepted: write_output routes to train.jsonl or knowledge.jsonl
    If max turns reached: discard → rejected.jsonl

Stage 2: Fine-tune (study-tutor-factory)
  Unsloth QLoRA on output/train.jsonl → Nemotron 3 Nano checkpoint

Stage 3: Eval (study-tutor-factory)
  Claude-as-judge on golden set → per-checkpoint metrics
```

### Player agent

- Retrieves relevant curriculum chunks from ChromaDB (`rag_retrieval` tool)
- Generates training examples using base prompt + GOAL.md `Generation Guidelines` section
- Submits to Coach; revises on rejection

### Coach agent

- `tools=[]` always — evaluates only, never writes
- Evaluates against GOAL.md `Evaluation Criteria` section
- Returns structured JSON:
  ```json
  {
    "decision": "accept | reject",
    "score": 0.0–1.0,
    "issues": ["list of specific problems"],
    "criteria_met": {"socratic_approach": true, "ao_alignment": true, ...},
    "quality_assessment": "brief explanation"
  }
  ```

### Model configuration

Both Player and Coach are configurable via `agent-config.yaml`:

```yaml
player:
  provider: local          # vLLM on GB10
  model: qwen3-coder-next
  endpoint: http://localhost:8000
  temperature: 0.7

coach:
  provider: anthropic      # Claude API for higher evaluation quality
  model: claude-sonnet-4-5
  temperature: 0.3
```

Using Claude API as Coach (rather than local model) gives higher evaluation quality
during the adversarial loop at modest cost, since Coach calls are fewer and shorter
than Player generation calls.

### Target dataset

| Category | Type | Target count |
|----------|------|-------------|
| Literary analysis (single-turn) | reasoning | 200 |
| Essay feedback (multi-turn) | reasoning | 250 |
| Exam technique guidance | reasoning | 150 |
| Poetry comparative | reasoning | 150 |
| Factual recall / character / plot | direct | 100 |
| Terminology definitions | direct | 75 |
| Encouragement / session management | direct | 75 |
| **Total** | | **1,000** |

Reasoning examples: ~750 (75%) | Direct examples: ~250 (25%)

### Output

Same file paths as Phase 1, different checkpoint and results directories:

| File | Purpose |
|------|---------|
| `output/train.jsonl` | Behaviour layer — fine-tuning input |
| `output/rag_index/knowledge.jsonl` | Knowledge layer — RAG seed |
| `output/rejected.jsonl` | Rejected examples with Coach JSON + turn count |
| `checkpoints/phase2/` | Fine-tuned Nemotron checkpoint |
| `evals/phase2/results.json` | Eval scores against golden set |

---

## Evaluation strategy

### Golden set

A hand-curated set of 75–100 examples in `domains/gcse-english-tutor/golden_set.jsonl`.
Format:

```json
{
  "messages": [...],
  "expected_behaviours": [
    "asks a Socratic question rather than giving the answer directly",
    "correctly identifies the AO2 focus",
    "references connotations of specific word choice"
  ],
  "red_flags": [
    "gives the complete essay answer to the student",
    "states factually incorrect information about the text",
    "uses condescending or discouraging language"
  ],
  "metadata": { "text": "macbeth", "topic": "character_analysis", "grade_target": 7 }
}
```

### Eval harness

Claude-as-judge scores each model response against the `expected_behaviours` and
`red_flags` for its golden example. Produces per-checkpoint metrics:

- **Socratic rate** — % of responses that guide rather than give the answer
- **AO accuracy** — % with correctly identified and applied assessment objectives
- **Red flag rate** — % triggering any red flag (lower is better)
- **Overall quality score** — composite 0–1

### The ablation comparison

| Metric | Phase 1 baseline | Phase 2 | Delta |
|--------|-----------------|---------|-------|
| Socratic rate | TBD | TBD | TBD |
| AO accuracy | TBD | TBD | TBD |
| Red flag rate | TBD | TBD | TBD |
| Overall quality | TBD | TBD | TBD |

**Interpreting the delta:**

- **Phase 2 clearly beats Phase 1** — the Coach is adding real value; the adversarial
  rejection loop produces measurably better training data. Architecture validated.

- **Phase 2 marginally beats Phase 1** — the synthesis prompts were already good; focus
  on tightening the Coach rubric or increasing the rejection turn limit before scaling.

- **Phases are roughly equal** — either the golden set isn't sensitive enough (eval
  problem), the Coach prompt needs work (Coach problem), or generation quality is
  already at ceiling (scaling won't help). Diagnose before proceeding.

### Integration with Eval Runner

The Eval Runner system (NATS-based, processes YAML eval briefs) already supports the
`guardkit_vs_vanilla` comparison type. The Study Tutor Factory eval uses the same
mechanism with a `phase1_vs_phase2` comparison type:

```yaml
eval_brief:
  id: EVAL-STF-001
  comparison_type: phase1_vs_phase2
  golden_set: domains/gcse-english-tutor/golden_set.jsonl
  checkpoints:
    - id: phase1
      path: checkpoints/phase1/
    - id: phase2
      path: checkpoints/phase2/
  metrics:
    - socratic_rate
    - ao_accuracy
    - red_flag_rate
    - overall_quality
  judge_model: claude-sonnet-4-5
```

---

## Hardware topology

| Machine | Role |
|---------|------|
| MacBook Pro M2 Max | Planning, Claude Desktop, code review |
| Dell Pro Max GB10 (128GB unified) | vLLM inference, Player agent loop, Unsloth fine-tuning, ChromaDB |

The GB10 runs simultaneously:
- **vLLM**: Qwen3-Coder-Next (Player model in local mode)
- **ChromaDB**: embedded, Docling-indexed source documents
- **LangGraph / DeepAgents**: the Player-Coach agent loop
- **Unsloth**: QLoRA fine-tuning post-generation

Coach calls route to the Anthropic API (Claude Sonnet) during generation to maximise
evaluation quality. This is a config change in `agent-config.yaml`, not a code change.

---

## Constraints and warnings

| Constraint | Detail |
|-----------|--------|
| 75/25 reasoning split | Hard constraint for Nemotron 3 Nano MoE — do NOT fine-tune the router layer (Unsloth disables by default). Deviating risks degrading post-fine-tune reasoning capability. |
| `generation-plan.yaml` is the source of truth | Both Phase 1 synthesis script and Phase 2 Player agent read from this file. Changes to distribution targets must be made here, not in code. |
| Copyright (source documents) | `domains/*/sources/` is gitignored. Section 29A CDPA 1988 (TDM exception) covers non-commercial research use for legitimately purchased materials. |
| ChromaDB lazy init | Collection may not exist at startup — `rag_retrieval` must initialise lazily, not at import time. Phase 2 only. |
| Coach isolation | `tools=[]` always for Coach. It evaluates, never writes. Phase 2 only. |
| GOAL.md validation | `agent.py` validates GOAL.md structure at startup — fail fast on missing sections. Phase 2 only. |
| `synthesis/` isolation | Phase 1 code must not import from `agents/`, `tools/`, or any Phase 2 module. If a shared utility is needed, it goes in a `common/` module, not either phase directory. |

---

## Related documents

| Document | Location |
|----------|---------|
| Architecture summary | `docs/architecture/ARCHITECTURE.md` |
| Training data format spec | `docs/research/gcse-tutor-training-data-format.md` |
| GCSE English AI Tutor Proposal | `docs/research/GCSE_English_AI_Tutor_Proposal.docx` |
| Conversation starter | `docs/research/agentic-dataset-factory-conversation-starter.md` |
| Study Tutor Factory starter | `docs/research/study-tutor-factory-conversation-starter.md` |

---

## Open questions

- [ ] What is the right max turn limit for the Player-Coach loop before discarding?
      (Tradeoff: quality vs throughput when running overnight on GB10)
- [ ] Should Phase 1 and Phase 2 datasets be combined for a Phase 2+ fine-tune run,
      or kept strictly separate for clean comparison?
- [ ] What minimum delta on the eval metrics justifies the Phase 2 infrastructure
      investment over just scaling Phase 1 generation?
- [ ] At what point does the knowledge RAG index need to be refreshed as the
      behaviour fine-tune improves? Are they coupled or truly independent?

---

*Document version: 1.1 | March 2026*  
*Changes: Added repository structure decision, generation-plan.yaml design, and GuardKit/Claude Code tooling evaluation*  
*Next review: after Phase 1 eval results available*
