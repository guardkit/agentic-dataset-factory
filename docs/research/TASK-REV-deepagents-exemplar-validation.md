# TASK-REV: DeepAgents Exemplar Repo Validation
## Before running /template-create for study-tutor-factory

**Task Type:** review  
**Complexity:** medium  
**Domain tags:** `deepagents, langchain, template, python, agentic-loop`  
**Prerequisite for:** `/template-create` → `deepagents-agentic-loop` GuardKit template  
**Date:** March 2026

---

## Context

Before running `/template-create` on the combined DeepAgents exemplar repo,
this review verifies the exemplar is structurally sound, runs correctly, and
represents genuine best-practice patterns — not noise that would corrupt the
template.

The GuardKit template philosophy is explicit: templates are created FROM proven
working code. If the exemplar has broken imports, missing dependencies, or
anti-patterns, `/template-create` will encode those flaws permanently.

The exemplar is assembled from two LangChain official examples:
- `langchain-ai/deepagents/examples/deep_research` — structural backbone,
  multi-agent coordination, LangSmith integration
- `langchain-ai/deepagents/examples/content-builder-agent` — config-driven
  pattern (`AGENTS.md`, `subagents.yaml`, `skills/` directory)

These are merged into a single exemplar repo that reflects the
`study-tutor-factory` Player-Coach data generation pattern.

---

## Target Exemplar Structure

The reviewer should verify this exact structure exists and is correct:

```
deepagents-tutor-exemplar/
├── pyproject.toml                  # uv-managed, pins deepagents + dependencies
├── .env.example                    # documents required env vars, no secrets
├── AGENTS.md                       # agent roles, behaviour boundaries
├── coach-config.yaml               # configurable coach: local or API
├── langgraph.json                  # LangGraph deployment config
├── README.md                       # setup + usage instructions
│
├── subjects/                       # subject-agnostic config (one dir per subject)
│   └── gcse-english/
│       └── SUBJECT.md              # synthesis prompts, AO framework, exam board
│
├── agents/
│   ├── __init__.py
│   ├── player.py                   # data generation agent
│   └── coach.py                    # validation agent
│
├── tools/
│   ├── __init__.py
│   ├── rag_retrieval.py            # ChromaDB retrieval tool
│   └── jsonl_writer.py             # accepts/routes examples to correct output
│
├── prompts/
│   ├── __init__.py
│   ├── player_prompts.py           # Player system prompt + generation instructions
│   └── coach_prompts.py            # Coach rubric + rejection schema
│
└── agent.py                        # main entrypoint — wires everything together
```

---

## Review Checklist

Work through each section in order. Mark each item ✅ pass or ❌ fail with notes.

---

### Section 1: Environment and Dependencies

- [ ] `pyproject.toml` exists and is valid TOML
- [ ] `deepagents` is listed as a dependency with a pinned or minimum version
- [ ] `langchain`, `langgraph`, `langchain-community` are present
- [ ] `chromadb` is present (for RAG retrieval tool)
- [ ] `langsmith` is present (for tracing)
- [ ] `python-dotenv` or equivalent is present
- [ ] `uv sync` completes without errors from a clean environment
- [ ] `uv run python -c "from deepagents import create_deep_agent; print('OK')"` passes
- [ ] `uv run python -c "import chromadb; print('OK')"` passes
- [ ] `.env.example` documents: `LANGSMITH_API_KEY`, `LANGSMITH_TRACING`,
  `LANGSMITH_PROJECT`, `LOCAL_MODEL_ENDPOINT`, `ANTHROPIC_API_KEY` (optional)
- [ ] No API keys or secrets present in any tracked file

---

### Section 2: Agent entrypoint (`agent.py`)

- [ ] File imports `create_deep_agent` from `deepagents`
- [ ] File imports `init_chat_model` from `langchain.chat_models`
- [ ] Model is loaded from config, not hardcoded — reads `coach-config.yaml`
  and selects local endpoint or API based on `provider` field
- [ ] Player agent is created with `create_deep_agent(model=..., tools=[...],
  system_prompt=...)`
- [ ] Coach agent is created separately with different `system_prompt`
- [ ] `uv run python agent.py --help` runs without error (or equivalent smoke test)
- [ ] No `openai:` model strings hardcoded — model provider is configurable

**Anti-patterns to reject:**
- [ ] ❌ Model hardcoded as `"openai:gpt-4o"` or any specific provider string
- [ ] ❌ API keys read directly from hardcoded strings
- [ ] ❌ Both agents sharing the same system prompt

---

### Section 3: Coach configuration (`coach-config.yaml`)

- [ ] File parses as valid YAML
- [ ] Contains `provider` field: value is `local` or `anthropic`
- [ ] Contains `local` section with `model` and `endpoint` fields
- [ ] Contains `api` section with `model` field
- [ ] `agent.py` reads this file and selects the correct provider at startup
- [ ] Switching `provider: local` → `provider: anthropic` changes model without
  code changes (config only)

**Expected structure:**
```yaml
coach:
  provider: local
  local:
    model: nemotron-3-super-120b-a12b
    endpoint: http://localhost:8000/v1
  api:
    model: claude-opus-4-6
```

---

### Section 4: Subject configuration (`subjects/gcse-english/SUBJECT.md`)

- [ ] File exists and is valid Markdown
- [ ] Contains `exam_board` field (AQA)
- [ ] Contains `specifications` list (8700, 8702)
- [ ] Contains `ao_framework` section defining AO1–AO6
- [ ] Contains synthesis prompt templates for the Player agent — these are
  the prompts used to generate training examples, not generic instructions
- [ ] Contains subject-specific Coach rubric additions (what makes a good
  GCSE English tutoring example specifically)
- [ ] A second subject directory (`subjects/gcse-maths/`) does NOT need to
  exist — verify the pattern is documented but not required

---

### Section 5: Agent definitions (`agents/player.py`, `agents/coach.py`)

**player.py:**
- [ ] Imports `create_deep_agent`
- [ ] Defines `create_player(model, tools, subject_config) -> agent` function
- [ ] Passes `system_prompt` from `prompts/player_prompts.py` — not inline string
- [ ] Tools list includes `rag_retrieval` and `jsonl_writer`
- [ ] Function is callable without side effects (no top-level agent instantiation)

**coach.py:**
- [ ] Imports `create_deep_agent`
- [ ] Defines `create_coach(model, subject_config) -> agent` function
- [ ] Passes `system_prompt` from `prompts/coach_prompts.py`
- [ ] Coach has NO `jsonl_writer` tool — it only accepts or rejects, it does
  not write output directly
- [ ] Function is callable without side effects

**Anti-patterns to reject:**
- [ ] ❌ Agent instantiated at module level (breaks testability)
- [ ] ❌ System prompts written as inline multi-line strings in agent files
- [ ] ❌ Coach given write access to output files

---

### Section 6: Tools (`tools/`)

**rag_retrieval.py:**
- [ ] Decorated with `@tool` from `langchain_core.tools`
- [ ] Accepts `query: str` and `subject: str` parameters
- [ ] Returns retrieved chunks as a string (not raw ChromaDB objects)
- [ ] ChromaDB client is initialised lazily (not at import time)
- [ ] Handles the case where ChromaDB collection doesn't exist yet (returns
  empty result, not exception)
- [ ] Tool docstring is clear — DeepAgents uses docstrings for tool selection

**jsonl_writer.py:**
- [ ] Decorated with `@tool`
- [ ] Accepts `example: str` (JSON string) and `layer: str` parameters
- [ ] Routes `layer="behaviour"` → `train.jsonl`
- [ ] Routes `layer="knowledge"` → `rag_index/`
- [ ] Validates that `example` is valid JSON before writing
- [ ] Validates that `layer` is one of `behaviour | knowledge`
- [ ] Returns confirmation string on success, error string on failure
- [ ] Does NOT raise exceptions — returns error as string (agents handle errors
  via return value, not exceptions)

---

### Section 7: Prompts (`prompts/`)

**player_prompts.py:**
- [ ] Defines `PLAYER_SYSTEM_PROMPT` as a module-level string constant
- [ ] Prompt instructs the Player to retrieve relevant chunks BEFORE generating
- [ ] Prompt specifies the training data format (ShareGPT JSONL)
- [ ] Prompt specifies the 75/25 reasoning/direct split requirement
- [ ] Prompt instructs the Player to set the `layer` field correctly
- [ ] Prompt instructs the Player to pass output to `jsonl_writer` tool

**coach_prompts.py:**
- [ ] Defines `COACH_SYSTEM_PROMPT` as a module-level string constant
- [ ] Prompt defines the rejection schema (structured, not free text):
  ```json
  {
    "decision": "accept | reject",
    "score": 1-5,
    "issues": ["list of specific problems"],
    "ao_correct": true | false,
    "socratic_quality": "guides | gives_answer | mixed",
    "layer_correct": true | false
  }
  ```
- [ ] Prompt instructs Coach to return structured JSON, not prose
- [ ] Prompt references AO1–AO6 explicitly
- [ ] Prompt defines what constitutes a Socratic response vs giving the answer

---

### Section 8: AGENTS.md

- [ ] File exists and describes the two agent roles clearly
- [ ] Defines Player's responsibilities and boundaries
- [ ] Defines Coach's responsibilities and boundaries
- [ ] Includes ALWAYS/NEVER/ASK sections per GuardKit boundary pattern:

  ```
  ## Player Agent
  ALWAYS: retrieve chunks before generating, set layer field, use think blocks
         for 75% of examples
  NEVER: write output directly without Coach approval, generate more than one
         example per turn
  ASK: when retrieved context is ambiguous about grade level

  ## Coach Agent
  ALWAYS: return structured JSON rejection schema, check layer field routing
  NEVER: write to output files, modify the example directly
  ASK: when example is borderline (score 3) — escalate for human review
  ```

- [ ] AGENTS.md is referenced in `agent.py` or passed as context to agents

---

### Section 9: LangSmith integration

- [ ] `LANGSMITH_TRACING=true` is documented in `.env.example`
- [ ] `LANGSMITH_PROJECT` is set to `"study-tutor-factory"` in `.env.example`
- [ ] No explicit LangSmith callback setup needed — DeepAgents traces
  automatically when env vars are set
- [ ] Verify: `uv run python -c "import langsmith; print(langsmith.__version__)"` passes

---

### Section 10: Smoke test

Run the full agent loop with a minimal test input before declaring the
exemplar ready:

```bash
# Requires: LANGSMITH_API_KEY set, LangSmith tracing active
# Requires: either local vLLM endpoint OR ANTHROPIC_API_KEY for coach
# ChromaDB does not need to be populated — rag_retrieval returns empty gracefully

uv run python agent.py \
  --subject gcse-english \
  --mode smoke \
  --max-examples 2 \
  --max-coach-turns 2
```

Expected outcome:
- [ ] Player generates 2 draft examples without error
- [ ] Coach validates each and returns structured JSON decision
- [ ] At least 1 example is accepted and written to `train.jsonl`
- [ ] LangSmith trace appears at smith.langchain.com
- [ ] No unhandled exceptions in the trace

If no `--mode smoke` flag exists yet, a minimal `python -c` import test is
the minimum acceptable:

```bash
uv run python -c "
from agents.player import create_player
from agents.coach import create_coach
from tools.rag_retrieval import rag_retrieval
from tools.jsonl_writer import jsonl_writer
from prompts.player_prompts import PLAYER_SYSTEM_PROMPT
from prompts.coach_prompts import COACH_SYSTEM_PROMPT
print('All imports OK')
"
```

- [ ] All imports resolve without error

---

## Review Decision

### PASS criteria (all must be true)
- All Section 1 dependency checks pass
- Sections 2–8 have zero ❌ failures on anti-pattern items
- Section 10 smoke test passes (at minimum: all imports OK)
- No API keys in tracked files

### CONDITIONAL PASS criteria
If any non-critical items fail (e.g. AGENTS.md missing ALWAYS/NEVER sections,
coach prompt is prose not structured JSON), document the gaps and fix before
running `/template-create`. These gaps will be encoded into the template if
not fixed.

### FAIL criteria (any one blocks /template-create)
- `uv sync` fails
- Any import in Section 10 fails
- Coach and Player use identical system prompts
- Model is hardcoded (not configurable via `coach-config.yaml`)
- Any API key present in tracked files

---

## What to do with failures

For each ❌ failure: fix it in the exemplar repo first. Do not run
`/template-create` on a broken exemplar. The template is only as good as
what you feed it.

Common fixes:
- Missing `@tool` decorator → add it, ensure docstring is clear
- Agent instantiated at module level → wrap in `create_*()` function
- Inline system prompt → move to `prompts/` module
- Hardcoded model → read from `coach-config.yaml`
- Exception raised in tool → return error string instead

---

## After this review passes

```bash
# From the exemplar repo root
cd deepagents-tutor-exemplar

# Run template-create (GuardKit command in Claude Code)
/template-create

# This produces a local GuardKit template at:
# ~/.guardkit/templates/local/deepagents-agentic-loop/

# Verify the template was created
guardkit template list --local

# Initialise study-tutor-factory from it
cd ../study-tutor-factory
guardkit init deepagents-agentic-loop
```

---

*TASK-REV prepared March 2026 | study-tutor-factory pre-work*
