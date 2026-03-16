# Feature Specification: DeepAgents Exemplar Repo

**Date:** March 2026
**Author:** Rich
**Status:** Ready for Implementation
**Research Method:** Claude Desktop → `/task-review`
**Target Repo:** `appmilla/deepagents-tutor-exemplar` (new repo)
**Target Branch:** `main`
**Feature ID:** FEAT-XXX *(assigned by `/feature-plan`)*

---

## 1. Problem Statement

Before running GuardKit's `/template-create` to produce a reusable
`deepagents-agentic-loop` template, a working exemplar repo must exist.
GuardKit's template philosophy is explicit: templates are created FROM proven
working code, not authored by hand. This feature builds that exemplar by
combining patterns from two official LangChain DeepAgents examples
(`deep_research` and `content-builder-agent`) into a single repo that
reflects the `study-tutor-factory` Player-Coach data generation pattern.

The exemplar must run end-to-end, pass the TASK-REV validation checklist,
and represent genuine best practices — not noise that would corrupt the
template permanently.

---

## 2. Decision Log

| # | Decision | Rationale | Alternatives Rejected | ADR Status |
|---|----------|-----------|----------------------|------------|
| D1 | Use `deep_research` as structural backbone | Has multi-agent coordination, `prompts.py` separation, LangSmith integration, and LangGraph deployment config already working | Authoring from scratch (slower, no proven baseline) | Accepted |
| D2 | Borrow config-driven pattern from `content-builder-agent` | `AGENTS.md` + `subagents.yaml` + `skills/` externalisation maps directly to subject-agnostic design — adding a subject is a config change not a code change | Hardcoding subject logic in Python (breaks generality) | Accepted |
| D3 | `coach-config.yaml` for configurable Coach model | Enables local (Nemotron 3 Super) for overnight volume runs and Claude Opus API for spot-check validation with zero code changes | Env var switching (less explicit), hardcoded model (breaks the pattern) | Accepted |
| D4 | Player and Coach as separate `create_deep_agent()` instances | Each gets different system prompt, tools, and responsibilities. Coach has NO write tools — it only accepts or rejects | Single agent doing both roles (conflates generation and validation) | Accepted |
| D5 | Coach returns structured JSON rejection schema, not prose | Makes rejection reasons parseable for metrics. Schema: `{decision, score, issues, ao_correct, socratic_quality, layer_correct}` | Free-text critique (not machine-parseable, can't gate on confidence) | Accepted |
| D6 | `@tool` decorated functions with docstrings for tool selection | DeepAgents uses docstrings for tool routing — clear docstrings are load-bearing, not documentation | Class-based tools (unnecessary complexity for this use case) | Accepted |
| D7 | Tools return strings, never raise exceptions | Agents handle errors via return value. Exceptions crash the agent loop | Raising exceptions (breaks DeepAgents tool calling loop) | Accepted |
| D8 | `uv` for dependency management | Consistent with GB10 Python toolchain, fast, lockfile reproducibility | pip + requirements.txt (less reproducible), poetry (heavier) | Accepted |
| D9 | `subjects/` directory mirrors `skills/` pattern from content-builder | Subject = config directory with `SUBJECT.md` containing synthesis prompts and AO framework. Adding Maths requires only a new directory | Hardcoded subject logic (breaks generality, forces code changes per subject) | Accepted |

**Warnings & Constraints:**
- DeepAgents traces automatically when `LANGSMITH_TRACING=true` — no explicit callback setup needed
- `create_deep_agent()` subagents must be defined in code not YAML — use `load_subagents()` helper pattern from content-builder-agent
- ChromaDB client must be initialised lazily (not at import time) to avoid failures when DB doesn't exist yet
- Player system prompt must specify 75/25 reasoning/direct split — Nemotron 3 Nano MoE constraint
- Coach must NOT receive `jsonl_writer` tool — only Player writes output

---

## 3. Architecture

### 3.1 Component Design

| Component | File Path | Purpose | Source |
|-----------|-----------|---------|--------|
| Entrypoint | `agent.py` | Wires everything, reads config, runs loop | deep_research pattern |
| Player agent | `agents/player.py` | `create_player()` factory function | new |
| Coach agent | `agents/coach.py` | `create_coach()` factory function | new |
| RAG retrieval tool | `tools/rag_retrieval.py` | ChromaDB chunk retrieval | new |
| JSONL writer tool | `tools/jsonl_writer.py` | Routes examples to correct output | new |
| Player prompts | `prompts/player_prompts.py` | `PLAYER_SYSTEM_PROMPT` constant | deep_research pattern |
| Coach prompts | `prompts/coach_prompts.py` | `COACH_SYSTEM_PROMPT` + rejection schema | deep_research pattern |
| Agent roles | `AGENTS.md` | ALWAYS/NEVER/ASK boundaries per agent | content-builder pattern |
| Coach config | `coach-config.yaml` | local vs API model selection | new |
| Subject config | `subjects/gcse-english/SUBJECT.md` | AO framework + synthesis prompts | content-builder skills/ pattern |
| LangGraph config | `langgraph.json` | Deployment configuration | deep_research pattern |
| Dependencies | `pyproject.toml` | uv-managed package list | new |
| Env template | `.env.example` | Documents required env vars | new |

### 3.2 Data Flow

```
1. agent.py reads coach-config.yaml → selects local or API coach model
2. agent.py reads subjects/gcse-english/SUBJECT.md → loads synthesis prompts
3. Player agent receives task: "generate N training examples for [topic]"
4. Player calls rag_retrieval(query, subject) → gets relevant curriculum chunks
5. Player generates draft training example (with layer + metadata)
6. Player passes draft to Coach agent
7. Coach evaluates against AO rubric, Socratic quality, layer correctness
8. Coach returns structured JSON: {decision, score, issues, ...}
9a. If accepted: Player calls jsonl_writer(example, layer) → routes to correct output
9b. If rejected (turns < max): Player revises using Coach critique → back to step 6
9c. If max turns reached: example discarded, reason logged
10. LangSmith traces entire loop automatically
```

### 3.3 Output Routing

```
layer="behaviour"  →  train.jsonl         (feeds Unsloth fine-tuning)
layer="knowledge"  →  rag_index/          (feeds ChromaDB seeding)
```

---

## 4. API Contracts

### Coach Rejection Schema

Every Coach response must be valid JSON matching this schema:

```json
{
  "decision": "accept | reject",
  "score": 1,
  "issues": ["specific problem descriptions"],
  "ao_correct": true,
  "socratic_quality": "guides | gives_answer | mixed",
  "layer_correct": true
}
```

Score rubric: 5=excellent, 4=good minor issues, 3=borderline (escalate),
2=significant problems, 1=fundamentally wrong.

### jsonl_writer Tool Contract

- Input: `example: str` (valid JSON string), `layer: str` ("behaviour" | "knowledge")
- Output: `"written to train.jsonl"` | `"written to rag_index/"` | `"error: [reason]"`
- Never raises exceptions — always returns string

### rag_retrieval Tool Contract

- Input: `query: str`, `subject: str` (e.g. "gcse-english")
- Output: concatenated chunk strings, or `"no results found"` if collection empty
- Never raises exceptions — returns empty gracefully

---

## 5. Implementation Tasks

### Task 1: Repository scaffold and dependencies

- **Task ID:** TASK-XXX
- **Complexity:** low
- **Type:** configuration
- **Domain tags:** `python, uv, project-setup, deepagents, langchain`
- **Files to create/modify:**
  - `pyproject.toml` (new)
  - `.env.example` (new)
  - `.gitignore` (new)
  - `langgraph.json` (new)
  - `README.md` (new — brief, just setup instructions)
  - `agents/__init__.py` (new — empty)
  - `tools/__init__.py` (new — empty)
  - `prompts/__init__.py` (new — empty)
  - `subjects/gcse-english/` (new — empty dir, placeholder only)
- **Files NOT to touch:** None (greenfield)
- **Dependencies:** None (first task)
- **Inputs:** Nothing — new repo
- **Outputs:** Working Python environment, all imports resolve
- **Relevant decisions:** D8
- **Acceptance criteria (machine-verifiable):**
  - [ ] `pyproject.toml` exists with `[project]` section, `name = "deepagents-tutor-exemplar"`
  - [ ] Dependencies listed: `deepagents`, `langchain`, `langgraph`,
    `langchain-community`, `chromadb`, `langsmith`, `python-dotenv`, `pyyaml`
  - [ ] `uv sync` completes without errors
  - [ ] `uv run python -c "from deepagents import create_deep_agent; print('OK')"` passes
  - [ ] `uv run python -c "import chromadb; print('OK')"` passes
  - [ ] `uv run python -c "import langsmith; print('OK')"` passes
  - [ ] `.env.example` documents: `LANGSMITH_API_KEY`, `LANGSMITH_TRACING=true`,
    `LANGSMITH_PROJECT=study-tutor-factory`, `LOCAL_MODEL_ENDPOINT`,
    `ANTHROPIC_API_KEY` (marked optional)
  - [ ] `.gitignore` excludes: `.env`, `__pycache__`, `.venv`, `train.jsonl`,
    `rag_index/`, `*.pyc`
  - [ ] `langgraph.json` contains `"graphs": {"data_factory": "./agent.py:agent"}`
  - [ ] No secrets present in any tracked file
- **Player constraints:** Do not create `agent.py` yet — that is Task 5
- **Coach validation commands:**
  ```bash
  uv sync
  uv run python -c "from deepagents import create_deep_agent; import chromadb; import langsmith; print('All imports OK')"
  python -c "import tomllib; tomllib.load(open('pyproject.toml','rb'))" 2>/dev/null || python -c "import tomli; tomli.load(open('pyproject.toml','rb'))"
  grep -q "LANGSMITH_API_KEY" .env.example && echo "env template OK"
  grep -q ".env" .gitignore && echo "gitignore OK"
  ```

---

### Task 2: Tools — `rag_retrieval` and `jsonl_writer`

- **Task ID:** TASK-XXX
- **Complexity:** medium
- **Type:** implementation
- **Domain tags:** `deepagents, langchain-tools, chromadb, jsonl, tool-decorator`
- **Files to create/modify:**
  - `tools/rag_retrieval.py` (new)
  - `tools/jsonl_writer.py` (new)
- **Files NOT to touch:** `tools/__init__.py`, any other files
- **Dependencies:** TASK-XXX (Task 1 — uv sync must work)
- **Inputs:** Empty `tools/` package
- **Outputs:** Two `@tool`-decorated functions, importable and callable
- **Relevant decisions:** D6, D7
- **Acceptance criteria (machine-verifiable):**
  - [ ] `rag_retrieval.py` imports `@tool` from `langchain_core.tools`
  - [ ] `rag_retrieval` function signature: `(query: str, subject: str) -> str`
  - [ ] Docstring explains: retrieves relevant curriculum chunks from ChromaDB
    for the given subject and query
  - [ ] ChromaDB client initialised inside the function body (lazy), not at
    module level
  - [ ] Returns concatenated chunk strings on success
  - [ ] Returns `"no results found for subject: {subject}"` when collection
    empty — does NOT raise exception
  - [ ] Returns `"error: {reason}"` on any other failure — does NOT raise
    exception
  - [ ] `jsonl_writer.py` imports `@tool` from `langchain_core.tools`
  - [ ] `jsonl_writer` function signature: `(example: str, layer: str) -> str`
  - [ ] Docstring explains: validates and writes accepted training example to
    correct output file based on layer field
  - [ ] Validates `example` is valid JSON before writing — returns error string
    if not
  - [ ] Validates `layer` is one of `"behaviour"` or `"knowledge"` — returns
    error string if not
  - [ ] Routes `layer="behaviour"` → appends to `train.jsonl`
  - [ ] Routes `layer="knowledge"` → appends to `rag_index/knowledge.jsonl`
    (creates file/dir if not exists)
  - [ ] Returns `"written to train.jsonl"` or `"written to rag_index/"` on success
  - [ ] Never raises exceptions under any circumstance
  - [ ] Import check passes:
    ```bash
    uv run python -c "from tools.rag_retrieval import rag_retrieval; from tools.jsonl_writer import jsonl_writer; print('OK')"
    ```
- **Player constraints:** Do not modify `agents/` or `prompts/` files
- **Coach validation commands:**
  ```bash
  uv run python -c "from tools.rag_retrieval import rag_retrieval; from tools.jsonl_writer import jsonl_writer; print('Tools import OK')"
  uv run python -c "
  from tools.jsonl_writer import jsonl_writer
  import json, os, tempfile, shutil
  tmp = tempfile.mkdtemp()
  os.chdir(tmp)
  result = jsonl_writer.invoke({'example': json.dumps({'messages': []}), 'layer': 'behaviour'})
  assert 'train.jsonl' in result, f'Expected train.jsonl routing, got: {result}'
  result2 = jsonl_writer.invoke({'example': 'not-json', 'layer': 'behaviour'})
  assert 'error' in result2.lower(), f'Expected error for invalid JSON, got: {result2}'
  result3 = jsonl_writer.invoke({'example': json.dumps({}), 'layer': 'invalid'})
  assert 'error' in result3.lower(), f'Expected error for invalid layer, got: {result3}'
  shutil.rmtree(tmp)
  print('jsonl_writer validation OK')
  "
  uv run python -c "
  from tools.rag_retrieval import rag_retrieval
  result = rag_retrieval.invoke({'query': 'test', 'subject': 'nonexistent-subject'})
  assert isinstance(result, str), 'Must return string'
  assert 'error' in result.lower() or 'no results' in result.lower(), f'Expected graceful empty result, got: {result}'
  print('rag_retrieval graceful empty OK')
  "
  ```

---

### Task 3: Prompts — Player and Coach system prompts

- **Task ID:** TASK-XXX
- **Complexity:** high
- **Type:** implementation
- **Domain tags:** `deepagents, prompt-engineering, system-prompt, agentic-loop, gcse`
- **Files to create/modify:**
  - `prompts/player_prompts.py` (new)
  - `prompts/coach_prompts.py` (new)
- **Files NOT to touch:** `prompts/__init__.py`, any other files
- **Dependencies:** TASK-XXX (Task 1)
- **Inputs:** Empty `prompts/` package
- **Outputs:** Two module-level string constants, correctly structured
- **Relevant decisions:** D4, D5
- **Acceptance criteria (machine-verifiable):**

  **player_prompts.py:**
  - [ ] Defines `PLAYER_SYSTEM_PROMPT` as module-level string constant
  - [ ] Prompt instructs Player to call `rag_retrieval` BEFORE generating an example
  - [ ] Prompt specifies ShareGPT JSONL format (messages array with role/content)
  - [ ] Prompt specifies 75% of examples must include `<think>...</think>` block
    in assistant content
  - [ ] Prompt specifies `layer` field must be set: `"behaviour"` for tutoring
    style examples, `"knowledge"` for factual curriculum content
  - [ ] Prompt instructs Player to call `jsonl_writer` only AFTER Coach accepts
  - [ ] Prompt instructs Player to revise using Coach critique JSON, not re-generate
    from scratch
  - [ ] Prompt does NOT include subject-specific content (that comes from
    `SUBJECT.md` at runtime)

  **coach_prompts.py:**
  - [ ] Defines `COACH_SYSTEM_PROMPT` as module-level string constant
  - [ ] Prompt instructs Coach to return ONLY valid JSON — no prose, no preamble
  - [ ] Prompt defines the exact rejection schema:
    ```
    {"decision": "accept|reject", "score": 1-5, "issues": [...],
     "ao_correct": bool, "socratic_quality": "guides|gives_answer|mixed",
     "layer_correct": bool}
    ```
  - [ ] Prompt defines score rubric: 5=excellent, 4=good, 3=borderline
    (flag for human review), 2=significant problems, 1=fundamentally wrong
  - [ ] Prompt defines AO1-AO6 criteria Coach must evaluate against
  - [ ] Prompt defines Socratic quality: `"guides"` = asks questions to help
    student discover answer, `"gives_answer"` = directly answers, `"mixed"` = partial
  - [ ] Prompt instructs Coach it does NOT have write tools — only Player writes
  - [ ] Import check:
    ```bash
    uv run python -c "from prompts.player_prompts import PLAYER_SYSTEM_PROMPT; from prompts.coach_prompts import COACH_SYSTEM_PROMPT; print('Prompts import OK')"
    ```
  - [ ] `PLAYER_SYSTEM_PROMPT` contains the words "rag_retrieval" and "jsonl_writer"
  - [ ] `COACH_SYSTEM_PROMPT` contains the words "decision" and "socratic"
- **Player constraints:** Do not create agent factory functions here — prompts
  module is string constants only. Do not import from `agents/` or `tools/`.
- **Coach validation commands:**
  ```bash
  uv run python -c "
  from prompts.player_prompts import PLAYER_SYSTEM_PROMPT
  from prompts.coach_prompts import COACH_SYSTEM_PROMPT
  assert 'rag_retrieval' in PLAYER_SYSTEM_PROMPT, 'Player prompt must reference rag_retrieval tool'
  assert 'jsonl_writer' in PLAYER_SYSTEM_PROMPT, 'Player prompt must reference jsonl_writer tool'
  assert 'think' in PLAYER_SYSTEM_PROMPT.lower(), 'Player prompt must specify think block requirement'
  assert 'layer' in PLAYER_SYSTEM_PROMPT.lower(), 'Player prompt must specify layer field'
  assert 'decision' in COACH_SYSTEM_PROMPT.lower(), 'Coach prompt must define rejection schema'
  assert 'socratic' in COACH_SYSTEM_PROMPT.lower(), 'Coach prompt must define socratic quality'
  assert 'ao' in COACH_SYSTEM_PROMPT.lower(), 'Coach prompt must reference AOs'
  assert len(PLAYER_SYSTEM_PROMPT) > 500, 'Player prompt too short'
  assert len(COACH_SYSTEM_PROMPT) > 500, 'Coach prompt too short'
  print('Prompt content validation OK')
  "
  ```

---

### Task 4: Agent factories — `player.py` and `coach.py`

- **Task ID:** TASK-XXX
- **Complexity:** medium
- **Type:** implementation
- **Domain tags:** `deepagents, create-deep-agent, agent-factory, langchain`
- **Files to create/modify:**
  - `agents/player.py` (new)
  - `agents/coach.py` (new)
- **Files NOT to touch:** `agents/__init__.py`, prompts, tools, any other files
- **Dependencies:** TASK-XXX (Task 2 — tools), TASK-XXX (Task 3 — prompts)
- **Inputs:** Working tools and prompt constants
- **Outputs:** Two factory functions, each returning a configured DeepAgent
- **Relevant decisions:** D4, D6
- **Acceptance criteria (machine-verifiable):**

  **agents/player.py:**
  - [ ] Imports `create_deep_agent` from `deepagents`
  - [ ] Imports `rag_retrieval`, `jsonl_writer` from `tools`
  - [ ] Imports `PLAYER_SYSTEM_PROMPT` from `prompts.player_prompts`
  - [ ] Defines `create_player(model, subject_prompt: str)` factory function
  - [ ] `create_player` returns `create_deep_agent(model=model,
    tools=[rag_retrieval, jsonl_writer], system_prompt=...)`
  - [ ] System prompt combines `PLAYER_SYSTEM_PROMPT` + `subject_prompt`
    (concatenated, not overwritten)
  - [ ] No agent instantiated at module level

  **agents/coach.py:**
  - [ ] Imports `create_deep_agent` from `deepagents`
  - [ ] Imports `COACH_SYSTEM_PROMPT` from `prompts.coach_prompts`
  - [ ] Defines `create_coach(model, subject_prompt: str)` factory function
  - [ ] `create_coach` returns `create_deep_agent(model=model, tools=[],
    system_prompt=...)` — NO tools, empty list
  - [ ] Coach tools list is explicitly empty (`tools=[]`)
  - [ ] No agent instantiated at module level

  - [ ] Import check:
    ```bash
    uv run python -c "
    from agents.player import create_player
    from agents.coach import create_coach
    print('Agent factories import OK')
    "
    ```
- **Player constraints:** Do not instantiate agents at module level. Do not
  give Coach any tools. Do not import `agent.py` (circular dependency risk).
- **Coach validation commands:**
  ```bash
  uv run python -c "
  from agents.player import create_player
  from agents.coach import create_coach
  import inspect
  player_sig = inspect.signature(create_player)
  coach_sig = inspect.signature(create_coach)
  assert 'model' in player_sig.parameters, 'create_player must accept model param'
  assert 'model' in coach_sig.parameters, 'create_coach must accept model param'
  print('Agent factory signatures OK')
  "
  uv run python -c "
  import ast, pathlib
  coach_src = pathlib.Path('agents/coach.py').read_text()
  tree = ast.parse(coach_src)
  # Check no module-level Call nodes that instantiate agents
  for node in ast.walk(tree):
      if isinstance(node, ast.Assign):
          if isinstance(node.value, ast.Call):
              func = node.value.func
              name = getattr(func, 'id', getattr(func, 'attr', ''))
              assert name != 'create_deep_agent', 'Coach must not instantiate agent at module level'
  print('No module-level agent instantiation OK')
  "
  ```

---

### Task 5: AGENTS.md and subject configuration

- **Task ID:** TASK-XXX
- **Complexity:** medium
- **Type:** implementation
- **Domain tags:** `deepagents, agents-md, config-driven, subject-agnostic, gcse`
- **Files to create/modify:**
  - `AGENTS.md` (new)
  - `coach-config.yaml` (new)
  - `subjects/gcse-english/SUBJECT.md` (new)
- **Files NOT to touch:** Any Python files
- **Dependencies:** TASK-XXX (Task 3 — prompts, to understand what subject
  config supplements)
- **Inputs:** Understanding of Player/Coach roles from prompts
- **Outputs:** Agent boundary documentation, configurable coach model, first
  subject config
- **Relevant decisions:** D2, D3, D9
- **Acceptance criteria (machine-verifiable):**

  **AGENTS.md:**
  - [ ] Contains `## Player Agent` section
  - [ ] Contains `## Coach Agent` section
  - [ ] Each section has `ALWAYS:`, `NEVER:`, `ASK:` subsections
  - [ ] Player ALWAYS includes: call rag_retrieval before generating, set layer
    field, use think blocks for 75% of examples
  - [ ] Player NEVER includes: write output without Coach approval, generate
    more than one example per turn
  - [ ] Coach ALWAYS includes: return structured JSON, check layer routing
  - [ ] Coach NEVER includes: write to output files, modify example directly
  - [ ] Coach ASK includes: when score is 3 (borderline) — escalate for human review

  **coach-config.yaml:**
  - [ ] Parses as valid YAML
  - [ ] Contains `coach.provider` field (value: `local`)
  - [ ] Contains `coach.local.model` and `coach.local.endpoint` fields
  - [ ] Contains `coach.api.model` field
  - [ ] Default `provider` is `local` (not `anthropic`)

  **subjects/gcse-english/SUBJECT.md:**
  - [ ] Contains `exam_board: AQA` field
  - [ ] Contains `specifications` list: `[8700, 8702]`
  - [ ] Contains `## Assessment Objectives` section defining AO1–AO6
  - [ ] Contains `## Synthesis Prompts` section with Player generation
    instructions specific to GCSE English
  - [ ] Contains `## Coach Rubric Additions` section with subject-specific
    validation criteria
  - [ ] Does NOT contain any Python code

  - [ ] YAML parse check:
    ```bash
    uv run python -c "import yaml; yaml.safe_load(open('coach-config.yaml')); print('coach-config.yaml valid YAML')"
    ```
  - [ ] Section check:
    ```bash
    grep -q "ALWAYS" AGENTS.md && grep -q "NEVER" AGENTS.md && grep -q "ASK" AGENTS.md && echo "AGENTS.md boundaries OK"
    grep -q "AO1" subjects/gcse-english/SUBJECT.md && echo "SUBJECT.md AO framework OK"
    grep -q "provider" coach-config.yaml && echo "coach-config.yaml structure OK"
    ```
- **Player constraints:** Do not modify any Python files in this task.
  Configuration and documentation only.
- **Coach validation commands:**
  ```bash
  uv run python -c "import yaml; c = yaml.safe_load(open('coach-config.yaml')); assert 'coach' in c; assert 'provider' in c['coach']; assert 'local' in c['coach']; assert 'api' in c['coach']; print('coach-config structure valid')"
  grep -c "ALWAYS\|NEVER\|ASK" AGENTS.md | xargs -I{} python -c "assert int('{}') >= 6, 'Expected at least 6 boundary markers in AGENTS.md'"
  echo "AGENTS.md boundary count OK"
  ```

---

### Task 6: Main entrypoint `agent.py`

- **Task ID:** TASK-XXX
- **Complexity:** high
- **Type:** implementation
- **Domain tags:** `deepagents, langchain, init-chat-model, config-loading, entrypoint`
- **Files to create/modify:**
  - `agent.py` (new)
- **Files NOT to touch:** All previously created files
- **Dependencies:** TASK-XXX (Task 4 — agent factories), TASK-XXX (Task 5 — config)
- **Inputs:** All agents, tools, prompts, and config files from previous tasks
- **Outputs:** A runnable entrypoint that wires everything together
- **Relevant decisions:** D1, D3, D4
- **Acceptance criteria (machine-verifiable):**
  - [ ] Imports `create_player` from `agents.player`
  - [ ] Imports `create_coach` from `agents.coach`
  - [ ] Imports `init_chat_model` from `langchain.chat_models`
  - [ ] Reads `coach-config.yaml` at startup to select provider
  - [ ] When `provider: local` — initialises model using `LOCAL_MODEL_ENDPOINT`
    env var with OpenAI-compatible interface
  - [ ] When `provider: anthropic` — initialises model using
    `init_chat_model("anthropic:claude-opus-4-6")`
  - [ ] Reads subject config from `subjects/{subject}/SUBJECT.md`
  - [ ] Creates Player and Coach agents using factory functions
  - [ ] Defines `agent` variable at module level (required for `langgraph.json`)
  - [ ] No model strings hardcoded — all from config or env vars
  - [ ] Supports `--subject` CLI argument (defaults to `gcse-english`)
  - [ ] Full import check passes:
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
  - [ ] No hardcoded model strings:
    ```bash
    grep -v "^#" agent.py | grep -v ".env" | python -c "
    import sys
    content = sys.stdin.read()
    bad = ['gpt-4o', 'claude-opus', 'gemini', 'openai:']
    for b in bad:
        assert b not in content, f'Hardcoded model string found: {b}'
    print('No hardcoded model strings OK')
    "
    ```
- **Player constraints:** Do not modify any files from Tasks 1–5. `agent.py`
  only imports from them — no duplication of logic.
- **Coach validation commands:**
  ```bash
  uv run python -c "
  from agents.player import create_player
  from agents.coach import create_coach
  from tools.rag_retrieval import rag_retrieval
  from tools.jsonl_writer import jsonl_writer
  from prompts.player_prompts import PLAYER_SYSTEM_PROMPT
  from prompts.coach_prompts import COACH_SYSTEM_PROMPT
  print('All imports OK — exemplar is wired correctly')
  "
  python -c "
  import ast, pathlib
  src = pathlib.Path('agent.py').read_text()
  assert 'coach-config.yaml' in src or 'coach_config' in src, 'agent.py must read coach-config.yaml'
  assert 'SUBJECT.md' in src or 'subject' in src.lower(), 'agent.py must load subject config'
  print('Config loading patterns present OK')
  "
  ```

---

## 6. Test Strategy

### Smoke test (run after Task 6 completes)

```bash
# Minimum viable smoke test — no real model needed
uv run python -c "
from agents.player import create_player
from agents.coach import create_coach
from tools.rag_retrieval import rag_retrieval
from tools.jsonl_writer import jsonl_writer
from prompts.player_prompts import PLAYER_SYSTEM_PROMPT
from prompts.coach_prompts import COACH_SYSTEM_PROMPT
import yaml, pathlib
config = yaml.safe_load(pathlib.Path('coach-config.yaml').read_text())
subject = pathlib.Path('subjects/gcse-english/SUBJECT.md').read_text()
assert config['coach']['provider'] in ['local', 'anthropic']
assert len(subject) > 100
print('Full smoke test OK — ready for /template-create review')
"
```

### TASK-REV gate

After all 6 tasks complete, pass `TASK-REV-deepagents-exemplar-validation.md`
to `/task-review` or work through it manually. The exemplar must pass all
PASS criteria before running `/template-create`.

---

## 7. Dependencies and Setup

### Python dependencies (in `pyproject.toml`)
```
deepagents>=0.4.8
langchain>=0.3
langgraph>=0.2
langchain-community>=0.3
chromadb>=0.5
langsmith>=0.2
python-dotenv>=1.0
pyyaml>=6.0
```

### System dependencies
None — all Python, no Docker required for the exemplar itself.
ChromaDB runs embedded (no server needed).

### Environment variables (from `.env`)
```
LANGSMITH_API_KEY=<from smith.langchain.com>
LANGSMITH_TRACING=true
LANGSMITH_PROJECT=study-tutor-factory
LOCAL_MODEL_ENDPOINT=http://localhost:8000/v1   # GB10 vLLM
ANTHROPIC_API_KEY=<optional — only needed when coach.provider=anthropic>
```

---

## 8. File Tree (Target State)

```
deepagents-tutor-exemplar/
├── pyproject.toml
├── .env.example
├── .gitignore
├── README.md
├── AGENTS.md
├── coach-config.yaml
├── langgraph.json
├── agent.py
├── agents/
│   ├── __init__.py
│   ├── player.py
│   └── coach.py
├── tools/
│   ├── __init__.py
│   ├── rag_retrieval.py
│   └── jsonl_writer.py
├── prompts/
│   ├── __init__.py
│   ├── player_prompts.py
│   └── coach_prompts.py
└── subjects/
    └── gcse-english/
        └── SUBJECT.md
```

---

## 9. Out of Scope

- ChromaDB population (that is `study-tutor-factory` Docling pipeline concern)
- Full end-to-end run with real models (exemplar proves structure; real runs
  are `study-tutor-factory` concern)
- LangGraph Studio UI setup
- Multi-subject implementation (only `gcse-english` config needed for exemplar)
- Fine-tuning pipeline (separate repo — `study-tutor-factory/fine-tuning/`)
- Error recovery / retry logic beyond max-turns (v1 scope)

---

## 10. Open Questions (Resolved)

| Question | Resolution |
|---|---|
| Should Player and Coach share a model instance? | No — each gets its own `init_chat_model()` call. Allows different models per role in future. |
| Does Coach need any tools at all? | No — `tools=[]`. Coach only evaluates and returns JSON. Write access belongs to Player only. |
| How does subject config reach the agents at runtime? | `agent.py` reads `SUBJECT.md`, passes as `subject_prompt` to factory functions, which append to base system prompt. |
| Should exemplar include actual training data generation loop? | No — wiring only. The loop logic belongs in `study-tutor-factory`. Exemplar proves patterns are correct. |
| What Python version? | 3.11+ (matches GB10 DGX OS Python, compatible with all dependencies) |

---

*FEAT prepared March 2026 | Consumed by `/task-review` → GuardKit AutoBuild*
