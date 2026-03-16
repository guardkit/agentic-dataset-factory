# agentic-dataset-factory — Conversation Starter
## For: /system-arch + /system-design session · New repo · March 2026

---

## Purpose of this document

This is the context brief for starting a new conversation that will produce
**two architecture documents**:

1. **`/system-arch`** — architecture intent, C4 diagrams, component boundaries,
   ADRs, open questions
2. **`/system-design`** — detailed design: data flows, schemas, agent interaction
   protocol, domain config format, tool contracts, deployment topology

Paste this document at the start of that conversation, then generate the two
documents sequentially.

---

## What is agentic-dataset-factory?

A general-purpose, open-source pipeline for automated training dataset
generation using a Player-Coach adversarial agent loop. Given:

- A **goal** (what behaviour you want a fine-tuned model to exhibit)
- **Source documents** (PDFs, text, structured data)

It produces a validated, structured training dataset ready for fine-tuning.

The pipeline is **domain-agnostic by design**. Adding a new use case is a
config change — a new `domains/` directory containing a `GOAL.md` and
`sources/`. No code changes required.

**First domain:** GCSE English tutor (AQA specification, Year 10, on-device
inference on GB10).

**Future domains (illustrative):** code review assistant, customer support
agent, medical triage classifier, legal document summariser — anything where
you have source documents and a clear behavioural goal.

---

## The foundation: exemplar repo already built

The `deepagents-player-coach-exemplar` repo is built, tested, and a
GuardKit template has been created from it:

```
Template: langchain-deepagents
Location: ~/.agentecflow/templates/langchain-deepagents/
Generated: 14 template files, 7 specialist agents, modular rules structure
```

`agentic-dataset-factory` will be initialised from this template:

```bash
guardkit init langchain-deepagents
```

The exemplar established these patterns — treat them as **fixed, do not
redesign in system-arch**:

- `domains/{domain-name}/GOAL.md` — goal description, quality criteria,
  output schema (replaces exemplar's `domains/example-domain/DOMAIN.md`)
- `domains/{domain-name}/sources/` — input documents for that domain
- `agents/player.py` + `agents/coach.py` — factory functions, no module-level
  instantiation
- `tools/search_data.py` + `tools/write_output.py` — generic tools replaced
  by domain-specific tools (see below)
- `prompts/player_prompts.py` + `prompts/coach_prompts.py` — base prompts +
  domain prompt appended at runtime
- `coach-config.yaml` — configurable Coach model (local or API, no code change)
- `AGENTS.md` — ALWAYS/NEVER/ASK boundaries per agent, loaded via
  `memory=["./AGENTS.md"]`

---

## Key architectural decisions (resolved — do not reopen)

| # | Decision | Resolution |
|---|---|---|
| D1 | Agent framework | LangChain DeepAgents SDK — planning, filesystem, subagents, LangGraph runtime |
| D2 | Adversarial pattern | Player-Coach: Player generates, Coach validates. Separate `create_deep_agent()` instances, different system prompts |
| D3 | Domain abstraction | `domains/{name}/` directory — `GOAL.md` + `sources/`. Config-driven, not code-driven |
| D4 | Coach configurability | `coach-config.yaml` with `provider: local \| api`, local endpoint or Anthropic API |
| D5 | Coach tool isolation | Coach `tools=[]` always — it evaluates only, never writes |
| D6 | Coach output format | Structured JSON rejection schema: `{decision, score, issues, criteria_met, quality_assessment}` |
| D7 | Tool error handling | Tools return error strings, never raise exceptions |
| D8 | Source ingestion | Docling (already working on GB10) — standard mode for digital PDFs, VLM mode for scanned paperbacks |
| D9 | RAG store | ChromaDB local — privacy, no cloud dependency, lazy initialisation |
| D10 | Tracing | LangSmith Developer tier (free, 5K traces/month, native DeepAgents integration) |
| D11 | Dependency management | `uv` — lockfile reproducibility, consistent with GB10 toolchain |
| D12 | Fine-tuning target | Nemotron 3 Nano 30B-A3B — Blackwell-native, Unsloth day-zero support, GB10 optimised |
| D13 | Training data split | 75% reasoning mode (with `<think>` blocks) / 25% direct — Nemotron MoE constraint |
| D14 | Two-layer inference | Fine-tune teaches *behaviour* (how to respond), RAG provides *knowledge* (what to draw from). Independently updatable. |
| D15 | Open-source | Public repo from day one |

**Warnings:**
- Nemotron 3 Nano MoE: do NOT fine-tune the router layer (Unsloth disables by default)
- 75% reasoning examples required to preserve post-fine-tune reasoning capability
- ChromaDB must initialise lazily — collection may not exist at startup
- Coach receives domain prompt appended to base prompt at runtime — not baked in
- LangSmith traces automatically when `LANGSMITH_TRACING=true` — no callback setup needed

---

## Domain config format (GOAL.md)

This is the key abstraction. Each domain directory contains:

```
domains/
└── gcse-english-tutor/
    ├── GOAL.md          ← defines the dataset goal
    └── sources/         ← input PDFs, processed by Docling
        ├── mr-bruff-language.pdf
        ├── mr-bruff-literature.pdf
        └── aqa-mark-schemes/
```

`GOAL.md` sections (to be fully specified in `/system-design`):

```markdown
## Goal
What behaviour the fine-tuned model should exhibit.

## Source Documents
What's in sources/ and how Docling should process each.

## Generation Guidelines
Instructions for the Player agent — what to generate and how.

## Evaluation Criteria
The rubric the Coach uses. Structured scoring per criterion.

## Output Schema
The exact JSON structure each training example must conform to.

## Layer Routing
How to classify examples: `behaviour` (→ train.jsonl) vs
`knowledge` (→ rag_index/).
```

---

## Training data output format

Two output files, both JSONL:

**`output/train.jsonl`** — behaviour layer examples (feeds Unsloth fine-tuning)
- ShareGPT format: `{messages: [{role, content}, ...]}`
- 75% include `<think>...</think>` block in assistant content
- Metadata field: `{layer, type, ao, topic, grade_target, source}`

**`output/rag_index/knowledge.jsonl`** — knowledge layer examples
(seeds ChromaDB at inference time)

The `layer` field in metadata drives routing via `write_output` tool:
- `layer: behaviour` → `output/train.jsonl`
- `layer: knowledge` → `output/rag_index/knowledge.jsonl`

---

## Tool replacements for agentic-dataset-factory

The exemplar's generic tools are replaced with domain-relevant tools:

| Exemplar tool | Replacement | Purpose |
|---|---|---|
| `search_data` (Tavily web search) | `rag_retrieval` (ChromaDB) | Retrieves curriculum chunks from Docling-indexed PDFs |
| `write_output` (generic path) | `write_output` (layer-aware router) | Routes to `train.jsonl` or `rag_index/` based on `layer` field |

The Docling ingestion pipeline (PDF → ChromaDB) is a **pre-run step**, not
part of the agent loop itself. It runs once per domain before the generation
loop starts.

---

## Pipeline stages

```
Stage 0: Ingest (one-time per domain)
  Docling processes sources/ → chunks → ChromaDB collection

Stage 1: Generate (Player-Coach loop, runs overnight)
  For each generation target:
    Player: retrieve chunks → generate example → submit to Coach
    Coach: evaluate against GOAL.md criteria → accept or reject with JSON
    If rejected (turns < max): Player revises → resubmit
    If accepted: write_output routes to correct output file
    If max turns: discard + log

Stage 2: Fine-tune (separate concern, GB10)
  Unsloth QLoRA on output/train.jsonl → Nemotron 3 Nano checkpoint

Stage 3: Eval (separate concern)
  Claude-as-judge on golden set → per-checkpoint metrics
```

Only Stage 1 is in scope for `agentic-dataset-factory`. Stages 2 and 3
belong in the consuming project (e.g. `study-tutor-factory`).

---

## Hardware topology

| Machine | Role |
|---|---|
| MacBook Pro M2 Max | Planning, Claude Desktop, `/system-arch` session |
| Dell Pro Max GB10 (DGX Spark, 128GB unified) | vLLM serving Nemotron 3 Super (Coach local model) + ChromaDB + LangSmith agent runtime + Unsloth fine-tuning |

The GB10 runs:
- **vLLM**: Nemotron 3 Super 120B-A12B — the local Coach model
- **ChromaDB**: embedded, no server required
- **LangGraph / DeepAgents**: the agent loop itself

---

## Repo structure (target)

```
agentic-dataset-factory/
├── pyproject.toml
├── .env.example
├── .gitignore
├── README.md
├── AGENTS.md
├── coach-config.yaml
├── langgraph.json
├── agent.py                        ← main entrypoint (from template)
│
├── domains/                        ← one dir per use case
│   └── gcse-english-tutor/
│       ├── GOAL.md
│       └── sources/
│           ├── mr-bruff-language.pdf
│           └── ...
│
├── agents/
│   ├── player.py                   ← from template
│   └── coach.py                    ← from template
│
├── tools/
│   ├── rag_retrieval.py            ← replaces search_data.py
│   └── write_output.py             ← extended with layer routing
│
├── prompts/
│   ├── player_prompts.py           ← from template, domain-agnostic
│   └── coach_prompts.py            ← from template, domain-agnostic
│
├── ingestion/                      ← NEW: Docling pipeline (Stage 0)
│   ├── ingest.py                   ← CLI: process sources/ → ChromaDB
│   └── chunker.py                  ← chunking strategy
│
└── tests/
    ├── test_agents.py              ← from template
    ├── test_tools.py               ← new
    └── test_ingestion.py           ← new
```

---

## Open questions for /system-arch to resolve

1. **Player turn limit** — how many Coach rejection cycles before an example
   is discarded? What's the right tradeoff between quality and throughput?

2. **Chunking strategy** — what chunk size and overlap for the ingestion
   pipeline? Different from RAG-for-inference chunking needs.

3. **Rejection logging** — where are discarded examples logged, and in what
   format? Useful for dataset quality analysis and Coach prompt improvement.

4. **Concurrency** — can Player and Coach run in parallel across multiple
   generation targets, or strictly sequential? GB10 has headroom but
   LangGraph concurrency model needs consideration.

5. **Domain validation** — should `agent.py` validate `GOAL.md` structure at
   startup, or trust it? What's the failure mode for malformed domain config?

6. **Ingestion CLI** — is `ingestion/ingest.py` a standalone script or a
   `guardkit` command? How does it signal completion to the agent loop?

---

## Open questions for /system-design to resolve

1. **Full `GOAL.md` schema** — complete field specification, required vs
   optional, validation rules.

2. **Coach rejection schema** — extend the exemplar's generic schema with
   domain-aware fields. How does the Coach reference `GOAL.md` criteria
   by name in its `issues` array?

3. **ChromaDB collection naming** — how are collections named per domain?
   How is the collection lifecycle managed (create, update, delete)?

4. **`write_output` layer routing** — exact file paths, append vs overwrite,
   handling of concurrent writes if parallelism is added.

5. **Golden set format** — how does the eval golden set live alongside the
   domain config? Is it part of `domains/{name}/` or separate?

6. **LangSmith project naming** — one project per domain or one shared
   project with tags?

---

## What each command should produce

### /system-arch produces:
- System context (what this is, who uses it, where it fits)
- Pre-resolved decisions treated as constraints
- C4 Level 1 and Level 2 diagrams
- Three-stage pipeline overview (ingest → generate → output)
- Agent interaction model (Player-Coach protocol)
- Domain abstraction design
- Hardware topology
- Resolved open questions from the arch list above
- Out of scope for v1
- ADRs for Graphiti seeding

### /system-design produces:
- Full `GOAL.md` schema specification
- Complete tool contracts (inputs, outputs, error cases)
- Coach rejection schema (extended)
- ChromaDB collection strategy
- Ingestion pipeline design (`ingest.py` → chunker → ChromaDB)
- Training data output format (full field definitions)
- Layer routing logic
- LangSmith integration points
- Resolved open questions from the design list above
- Target file tree with all files specified

---

## Related documents (from planning session)

- `gcse-tutor-training-data-format.md` — training data format spec including
  metadata schema with `layer` field (behaviour vs knowledge split)
- `study-tutor-factory-conversation-starter.md` — the GCSE tutor-specific
  system, which consumes output from `agentic-dataset-factory`
- `TASK-REV-deepagents-exemplar-validation.md` — validation checklist for
  the exemplar (already passing)
- `FEAT-deepagents-exemplar-build.md` — feature spec that was used to build
  the exemplar (reference for patterns used)

---

## Key insight to carry forward

From Daniel Bourke (Queensland AI Meetup, March 2026):
**Fine-tuning teaches behaviour, not facts.**

This is the architectural load-bearing principle. The `layer` field in every
training example routes it to one of two independently updatable outputs:
- `behaviour` layer → fine-tuning (teaches HOW the model responds)
- `knowledge` layer → RAG index (provides WHAT the model draws from)

`agentic-dataset-factory` produces both. The consuming project decides how
to use each.

---

*Prepared: March 2026 | agentic-dataset-factory planning session*
*Use as context for /system-arch and /system-design commands*
