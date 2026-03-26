# Pre-Run Review: agentic-dataset-factory

## Executive Summary

The agentic-dataset-factory Phase 2 codebase (43 tasks across 6 features, all built successfully via `guardkit autobuild`) has been reviewed for runtime readiness. The code quality is excellent — well-structured, properly documented with ADR/DDR references, comprehensive test coverage (40+ test files), and production-grade resilience patterns (retry, timeout, checkpoint/resume). However, **four prerequisites must be satisfied before the first end-to-end run**, and **one confirmed bug** was identified that **will** block the Player agent from instantiating with a `local` provider configuration. The bug was confirmed by cross-referencing the codebase against the DeepAgents SDK documentation (https://docs.langchain.com/oss/python/deepagents/models) and the SDK GitHub repository (https://github.com/langchain-ai/deepagents).

## Review Details

- **Mode**: Pre-Run Readiness Assessment
- **Depth**: Code-level inspection of all modules
- **Scope**: Full repo — `agent.py`, `agents/`, `config/`, `domain_config/`, `entrypoint/`, `ingestion/`, `prompts/`, `src/tools/`, `tests/`
- **Source**: Claude Desktop analysis session (2026-03-22)

---

## 1. CONFIRMED BUG: Player Model Creation Will Fail for Local Provider

**Severity**: HIGH — WILL block first run at Player agent creation step  
**Location**: `agents/player.py` vs `agents/coach.py` vs `agents/model_factory.py`

### Evidence from DeepAgents SDK Documentation

The DeepAgents SDK docs (https://docs.langchain.com/oss/python/deepagents/models) confirm that `create_deep_agent(model=...)` accepts **two forms**:

1. **A string** in `"provider:model"` format — e.g., `model="openai:gpt-5.3-codex"`. Under the hood, this calls `init_chat_model()` with default parameters.
2. **A pre-built `BaseChatModel` object** — e.g., `model=init_chat_model(model="anthropic:claude-sonnet-4-6", thinking=...)`.

Reference code from the docs:
```python
# String form — calls init_chat_model under the hood
agent = create_deep_agent(model="openai:gpt-5.3-codex")

# Object form — pre-configured model
model = init_chat_model(model="anthropic:claude-sonnet-4-6", thinking={"type": "enabled", "budget_tokens": 10000})
agent = create_deep_agent(model=model)
```

### The Problem

**`agents/player.py`** defines a local `create_model()` function that returns a **string**:
```python
def create_model(model_config: ModelConfig) -> str:
    return f"{model_config.provider}:{model_config.model}"
```

For a `local` provider config, this produces: `"local:Qwen/Qwen3-Coder-Next-FP8"`.

When `create_deep_agent()` receives this string, it calls `init_chat_model("local:Qwen/Qwen3-Coder-Next-FP8")` under the hood. **But `"local"` is NOT a valid `init_chat_model` provider.** Valid providers are `"openai"`, `"anthropic"`, `"google_genai"`, etc.

**`agents/coach.py`** correctly imports from `agents.model_factory` which handles the provider mapping:
```python
_PROVIDER_MAP = {
    "local": "openai",       # Local endpoints use OpenAI-compatible API
    "anthropic": "anthropic",
    "openai": "openai",
}
```
The Coach's `model_factory.create_model()` translates `local` → `openai` and passes `base_url=config.endpoint`, returning a properly configured `BaseChatModel`.

### Impact

The **Player agent WILL fail** at instantiation when using `provider: local` in `agent-config.yaml`. The Coach will work correctly. This blocks any end-to-end run with local vLLM inference.

### Root Cause

AutoBuild generated two separate model creation paths — the Player got a local string-based shortcut (`player.py:create_model`), while the Coach correctly uses the shared `model_factory.py`. This is a classic integration gap where two tasks (TASK-AF-003 for Player, TASK-AF-004 for Coach) produced inconsistent implementations.

### Fix

Replace the Player's local `create_model()` with the shared `model_factory.create_model()`:

**`agents/player.py`** — change:
```python
# REMOVE this local function:
def create_model(model_config: ModelConfig) -> str:
    return f"{model_config.provider}:{model_config.model}"

# ADD this import instead:
from agents.model_factory import create_model
```

No other changes needed — `create_player()` already passes `model` to `create_deep_agent()`, and the shared factory returns a `BaseChatModel` which the SDK accepts.

### Reference Documentation

- DeepAgents SDK Models: https://docs.langchain.com/oss/python/deepagents/models
- DeepAgents SDK Overview: https://docs.langchain.com/oss/python/deepagents/overview
- DeepAgents GitHub: https://github.com/langchain-ai/deepagents
- `init_chat_model` uses `provider:model` string format where provider must be a recognised LangChain provider name (openai, anthropic, etc.) — NOT a custom alias like "local"

### Verification

After applying the fix:
```bash
# Verify both factories return the same type
python -c "
from agents.model_factory import create_model
from config.models import ModelConfig

config = ModelConfig(provider='local', model='test-model', endpoint='http://localhost:8002/v1')
model = create_model(config)
print(f'Type: {type(model).__name__}')
print(f'Model works: {hasattr(model, \"invoke\")}')
"
```

---

## 2. Missing Files — Must Create Before Running

### 2.1 `agent-config.yaml` (REQUIRED — does not exist)

**Impact**: Pipeline fails immediately at Step 1 (`load_config()` raises `FileNotFoundError`)

The config loader (`config/loader.py`) expects this file at the repo root. Based on the Pydantic models in `config/models.py`, create:

```yaml
# agent-config.yaml — agentic-dataset-factory configuration
# Reference: docs/design/models/DM-agent-config.md

domain: gcse-english-tutor

player:
  provider: local
  model: Qwen/Qwen3-Coder-Next-FP8
  endpoint: http://localhost:8002/v1
  temperature: 0.7

coach:
  provider: local
  model: Qwen/Qwen3-Coder-Next-FP8
  endpoint: http://localhost:8002/v1
  temperature: 0.3

generation:
  max_turns: 3
  llm_retry_attempts: 3
  llm_retry_backoff: 2.0
  llm_timeout: 300
  target_timeout: 600

chunking:
  chunk_size: 512
  overlap: 64

logging:
  level: INFO
  format: json
```

**Notes**:
- The endpoint URL assumes vLLM is serving on the GB10 on port 8002 (the AutoBuild LLM port from `scripts/vllm-serve.sh`)
- If running from the GB10 directly, use `http://localhost:8002/v1`
- If running from the Mac, use `http://promaxgb10-41b1:8002/v1` (or whatever the GB10 hostname resolves to)
- Consider whether Player and Coach should use the same model or different ones — the architecture originally specified Nemotron 3 Super for the Coach

### 2.2 `AGENTS.md` (REQUIRED — does not exist)

**Impact**: Both `create_player()` and `create_coach()` pass `memory=["./AGENTS.md"]` to `create_deep_agent()`. Missing file may cause runtime error depending on how DeepAgents SDK handles missing memory files.

Create at repo root:

```markdown
# Agent Boundaries — agentic-dataset-factory

## Player Agent

### ALWAYS
- Use `rag_retrieval` tool to find relevant curriculum content before generating any training example
- Use `write_output` tool to persist every accepted training example
- Include `<think>` blocks in all reasoning-type examples (75% of dataset)
- Follow the ShareGPT conversation format: system → user → assistant
- Include all required metadata fields as defined in GOAL.md Metadata Schema
- Ground training examples in AQA specification content and mark scheme criteria

### NEVER
- Generate training examples without first consulting source material via RAG
- Skip metadata fields or use values outside the defined valid values
- Include `<think>` blocks in direct-type examples
- Generate content that is factually incorrect about literary texts or AQA criteria
- Produce content inappropriate for Year 10 students (age 14-15)

### ASK
- If unsure about the correct AO (Assessment Objective) for a given question type
- If the RAG retrieval returns insufficient context for the target category

## Coach Agent

### ALWAYS
- Return structured JSON verdict matching the CoachVerdict schema exactly
- Evaluate against ALL criteria from GOAL.md Evaluation Criteria section
- Check layer routing correctness (behaviour vs knowledge)
- Check type correctness (reasoning vs direct) matches think block presence
- Provide actionable feedback in the quality_assessment field when rejecting

### NEVER
- Write files or call any tools (Coach has no tools by design — D5 invariant)
- Accept examples with missing or invalid metadata fields
- Accept examples where metadata.type does not match think block presence
- Return unstructured text instead of JSON verdict

### ASK
- N/A — Coach operates autonomously within its evaluation rubric
```

### 2.3 ChromaDB Collection (REQUIRED — not populated)

**Impact**: Pipeline fails at Step 5 (`verify_chromadb_collection()` raises `ConnectionError` or `RuntimeError`)

The startup sequence checks for a ChromaDB `PersistentClient` at `./chroma_data` with a collection named `gcse-english-tutor` containing at least one chunk.

**Prerequisites**:
1. Source PDFs must be placed in `domains/gcse-english-tutor/sources/` (currently empty — just `.gitkeep`)
2. Ingestion pipeline must be run to populate ChromaDB

**Steps**:
```bash
# 1. Copy source PDFs (Mr Bruff guides, AQA mark schemes)
cp /path/to/mr-bruff-*.pdf domains/gcse-english-tutor/sources/
cp /path/to/aqa-mark-schemes/*.pdf domains/gcse-english-tutor/sources/

# 2. Run ingestion (requires Docling — use the GB10 venv)
python -m ingestion --domain gcse-english-tutor

# 3. Verify
python -c "
import chromadb
client = chromadb.PersistentClient(path='./chroma_data')
coll = client.get_collection('gcse-english-tutor')
print(f'Collection: {coll.name}, Chunks: {coll.count()}')
"
```

**Note**: The ingestion pipeline uses Docling. The GOAL.md specifies `standard` mode for all source documents (digital PDFs). The Docling venv on the GB10 is at `~/.venv/docling/`. VLM mode (for scanned paperbacks) is not needed for the initial run.

### 2.4 `.env` file (OPTIONAL — does not exist)

Not strictly required, but the startup sequence checks for `LANGSMITH_TRACING` and `LANGSMITH_API_KEY` environment variables. Without them, LangSmith tracing is disabled (non-blocking — ASSUM-004). If you want tracing:

```bash
# .env
LANGSMITH_TRACING=true
LANGSMITH_API_KEY=your-key-here
```

---

## 3. Startup Dependency Chain

The `agent.py` entrypoint executes a 12-step startup sequence. Each step depends on the previous ones succeeding:

| Step | Function | Dependency | Status |
|------|----------|------------|--------|
| 1 | `load_config()` | `agent-config.yaml` exists | ✗ Must create |
| 2 | `configure_logging()` | Config loaded | ✓ Should work |
| 3 | `configure_langsmith()` | Config loaded | ✓ Should work (warns without API key) |
| 4 | `resolve_domain()` | `domains/gcse-english-tutor/` exists | ✓ Exists |
| 5 | `verify_chromadb_collection()` | ChromaDB populated | ✗ Must run ingestion |
| 6 | `parse_goal_md()` | `GOAL.md` exists and valid | ✓ Exists, looks complete |
| 7 | `prepare_output_directory()` | None | ✓ Creates `output/` fresh |
| 8 | `build_player_prompt()` / `build_coach_prompt()` | GOAL.md parsed | ✓ Should work |
| 9 | `create_player_tools()` | ChromaDB collection name | ✓ Depends on step 5 |
| 10 | `create_player()` / `create_coach()` | `AGENTS.md` exists, model endpoint accessible | ✗ Must create AGENTS.md, needs vLLM running. **Player has confirmed bug** — `create_model()` returns invalid provider string for `local` |
| 11 | `CheckpointManager` | Output dir ready | ✓ Should work |
| 12 | `run_generation_loop()` | All above + LLM responding | Depends on all above |

**The pipeline will fail at Step 1 without `agent-config.yaml`, and at Step 5 without a populated ChromaDB collection.**

---

## 4. Test Suite Assessment

### Coverage

40+ test files across all modules:

| Module | Test Files | Scope |
|--------|-----------|-------|
| `config/tests/` | 4 | Config loading, validation, coach verdict, logging |
| `domain_config/tests/` | 4 | GOAL.md parsing, models, validators |
| `agents/tests/` | 3 | Player factory, coach factory, model factory |
| `entrypoint/tests/` | 6 | Generation loop, startup, checkpoint, output, graph |
| `ingestion/tests/` | 7 + 1 integration | Chunker, indexer, Docling processor, errors, models |
| `prompts/tests/` | 1 | Prompt builders |
| `src/tools/tests/` | 4 | RAG retrieval, write output, tool factory, models |
| `synthesis/tests/` | 4 | Synthesise, templates, validation, validator |
| `tests/` (root) | 9 | Integration smoke, GOAL.md structure, domain structure |

### Test Markers

From `pyproject.toml`:
- `@seam` — integration contract verification between tasks
- `@integration_contract` — specific contract being verified
- `@integration` — full pipeline end-to-end
- `@smoke` — fast CI tests mapping to BDD scenarios

### Recommended Test Execution Order

```bash
# Phase 1: Unit tests only (Mac, no external deps)
pip install -e ".[dev]"
pytest --tb=short -q

# Phase 2: Smoke tests (Mac, all mocked)
pytest -m smoke --tb=short -v

# Phase 3: Seam tests (Mac, verifies inter-module contracts)
pytest -m seam --tb=short -v

# Phase 4: Integration (GB10, needs vLLM + ChromaDB)
pytest -m integration --tb=long -v
```

---

## 5. Architecture Observations

### What AutoBuild Got Right

1. **Clean separation of concerns**: Each module has a clear responsibility — `config/` for loading, `domain_config/` for GOAL.md parsing, `agents/` for factory functions, `entrypoint/` for orchestration, `tools/` for RAG and output, `ingestion/` for PDF processing
2. **Resilience patterns**: LLM retry with exponential backoff, per-target timeouts, atomic checkpoint writes, lock file concurrency guard — all from ADR-ARCH-010
3. **Validation chain**: The `write_output` tool has a 10-step validation pipeline that checks JSON structure, messages format, metadata fields, layer routing, and think-block consistency
4. **Error handling**: Every external interaction (ChromaDB, LLM calls, file I/O) is wrapped in try/except with descriptive error messages
5. **Testability**: Factory functions, dependency injection (ChromaDB client parameter), and clean interfaces make the code highly testable

### What Needs Attention

1. **Player `create_model` is BROKEN for local provider** (see Section 1) — the Player has a local string-returning function that produces `"local:model-name"`, but `"local"` is not a valid `init_chat_model` provider. Confirmed by SDK docs. Must be replaced with the shared `model_factory.create_model()` which correctly maps `local` → `openai` with `base_url`
2. **No `agent-config.yaml` example or template** — AutoBuild didn't create one, even though `config/models.py` fully specifies the schema
3. **No `AGENTS.md`** — referenced by both agent factories but not created
4. **Ingestion pipeline not wired into main entrypoint** — `ingestion/` is a separate CLI (`python -m ingestion`), not part of `agent.py`. This is by design (Stage 0 is separate from Stage 1) but means the user must run it manually first

---

## 6. Recommended Implementation Tasks

### TASK-FIX-MODEL: Fix Player Model Creation — CONFIRMED BUG (P0)

**Description**: The Player agent's local `create_model()` in `agents/player.py` returns a string `"local:model-name"` which `create_deep_agent()` passes to `init_chat_model()` under the hood. The `"local"` provider is NOT recognised by `init_chat_model` — it only accepts standard LangChain provider names (`openai`, `anthropic`, etc.). The Coach correctly uses `agents/model_factory.py` which maps `local` → `openai` with `base_url`. **This bug is confirmed by the DeepAgents SDK documentation at https://docs.langchain.com/oss/python/deepagents/models.**

**Files to modify**: `agents/player.py`

**Changes**:
1. Remove the local `create_model()` function (the one returning `f"{model_config.provider}:{model_config.model}"`)
2. Add `from agents.model_factory import create_model` import (same as `coach.py` already does)
3. No changes needed to `create_player()` body — it already passes `model` to `create_deep_agent()`

**Acceptance criteria**:
- `create_player()` uses `model_factory.create_model()` which returns `BaseChatModel`
- Both Player and Coach pass `BaseChatModel` to `create_deep_agent(model=...)`
- Player with `provider: local` and `endpoint: http://localhost:8002/v1` creates a valid model
- Existing tests in `agents/tests/test_player.py` still pass (may need mock updates for return type)

**Reference**: https://docs.langchain.com/oss/python/deepagents/models — confirms `create_deep_agent` accepts both strings and `BaseChatModel`, but strings must use valid `init_chat_model` provider names (not `"local"`)

### TASK-CREATE-CONFIG: Create agent-config.yaml (P0)

**Description**: Create the `agent-config.yaml` file at the repo root with configuration for the `gcse-english-tutor` domain using local vLLM inference.

**Files to create**: `agent-config.yaml`

**Acceptance criteria**:
- File validates successfully via `load_config()` 
- Domain is `gcse-english-tutor`
- Both Player and Coach point to accessible vLLM endpoints
- All defaults from `config/models.py` are respected

**Verification**:
```bash
python -c "from config.loader import load_config; c = load_config(); print(f'OK: {c.domain}')"
```

### TASK-CREATE-AGENTS-MD: Create AGENTS.md (P0)

**Description**: Create the `AGENTS.md` file at the repo root with ALWAYS/NEVER/ASK boundaries for Player and Coach agents, following the DeepAgents exemplar pattern.

**Files to create**: `AGENTS.md`

**Acceptance criteria**:
- File exists at `./AGENTS.md` (relative to repo root)
- Contains boundaries for both Player and Coach agents
- Player boundaries reference tool usage (`rag_retrieval`, `write_output`)
- Coach boundaries enforce D5 evaluation-only invariant (no tools, no files)

### TASK-VERIFY-TESTS: Run Full Test Suite (P1)

**Description**: Install dev dependencies and run the complete test suite to verify AutoBuild-generated code passes its own tests.

**Commands**:
```bash
pip install -e ".[dev]"
pytest --tb=short -q
pytest -m smoke --tb=short -v
```

**Acceptance criteria**:
- All unit tests pass
- All smoke tests pass
- Any failures are documented with root cause analysis

### TASK-INGEST: Run Ingestion Pipeline (P1)

**Description**: Copy source PDFs into the domain sources directory and run the ingestion pipeline to populate ChromaDB.

**Prerequisites**: Docling venv active, source PDFs available

**Acceptance criteria**:
- ChromaDB collection `gcse-english-tutor` exists at `./chroma_data`
- Collection contains > 0 chunks
- Verification script confirms population

### TASK-FIRST-RUN: Execute First End-to-End Run (P2)

**Description**: With all prerequisites satisfied, execute `python agent.py` and observe the first generation cycle.

**Recommendation**: Start with a minimal run — temporarily reduce generation targets in GOAL.md to a single category with `count: 1` to validate the loop works before running the full 1,000-target overnight run.

**Acceptance criteria**:
- Pipeline starts and progresses through all 12 startup steps
- At least one Player-Coach cycle completes
- Output appears in `output/train.jsonl` or `output/rejected.jsonl`
- Output conforms to the ShareGPT format with correct metadata

---

## 7. Risk Matrix

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Player model creation fails for `local` provider | **Certain** | **Blocks run** | TASK-FIX-MODEL — confirmed bug: `"local"` not valid `init_chat_model` provider |
| Missing `agent-config.yaml` | Certain | Blocks run | TASK-CREATE-CONFIG — create from schema |
| Missing `AGENTS.md` | Certain | Blocks run | TASK-CREATE-AGENTS-MD — create from exemplar pattern |
| Empty ChromaDB | Certain | Blocks run | TASK-INGEST — run ingestion pipeline |
| `deepagents` SDK API mismatch (other) | Low | May block run | Check SDK version matches `pyproject.toml` constraint (`>=0.4.11`) |
| Import path issues (`src/tools/` vs `tools/`) | Low | Blocks import | `pyproject.toml` `pythonpath = ["src"]` should handle this |
| Generation loop logic bugs | Low | Corrupts output | Well-tested by smoke tests; verify with single-target run |
| vLLM endpoint unreachable | Low | Blocks generation | Verify with `curl http://localhost:8002/v1/models` before running |

---

## 8. Port Allocation Reference (GB10)

For the generation loop to work, the correct vLLM services must be running:

| Port | Service | Script | Model | Required For |
|------|---------|--------|-------|-------------|
| 8000 | Graphiti LLM | `vllm-graphiti.sh` | Qwen2.5-14B-Instruct FP8 | Not needed for generation |
| 8001 | Embedding | `vllm-embed.sh` | nomic-embed-text-v1.5 | Not needed for generation |
| 8002 | AutoBuild LLM | `vllm-serve.sh` | Qwen3-Coder-Next FP8 | **Player + Coach inference** |
| 8003 | Nemotron Nano | `vllm-nemotron3-nano.sh` | Nemotron 3 Nano 30B-A3B | Optional alternative |

Only port 8002 is required for the first run (assuming both Player and Coach use the same model). If using different models for Player and Coach, additional ports may be needed.

---

## Appendix: Key File Inventory

| File | Status | Purpose |
|------|--------|---------|
| `agent.py` | ✓ Complete | Main entrypoint — LangGraph thin wrapper |
| `agents/player.py` | ✗ CONFIRMED BUG — local `create_model` returns invalid provider string | Player factory — fix before running |
| `agents/coach.py` | ✓ Complete | Coach factory (uses shared `model_factory`) |
| `agents/model_factory.py` | ✓ Complete | Shared model creation via `init_chat_model` |
| `config/loader.py` | ✓ Complete | YAML → Pydantic config loader |
| `config/models.py` | ✓ Complete | All config Pydantic models |
| `config/coach_verdict.py` | ✓ Complete | Coach JSON verdict schema |
| `domain_config/parser.py` | ✓ Complete | GOAL.md markdown parser |
| `domain_config/models.py` | ✓ Complete | Domain config Pydantic models |
| `domain_config/validators.py` | ✓ Complete | Cross-section validation |
| `entrypoint/generation_loop.py` | ✓ Complete | Core Player-Coach adversarial loop |
| `entrypoint/startup.py` | ✓ Complete | Domain resolution, ChromaDB check |
| `entrypoint/checkpoint.py` | ✓ Complete | Atomic checkpoint, lock file, output prep |
| `entrypoint/output.py` | ✓ Complete | Append-mode JSONL file management |
| `src/tools/rag_retrieval.py` | ✓ Complete | ChromaDB RAG tool |
| `src/tools/write_output.py` | ✓ Complete | Layer-aware JSONL writer with 10-step validation |
| `src/tools/tool_factory.py` | ✓ Complete | Player/Coach tool list assembly |
| `ingestion/ingest.py` | ✓ Complete | CLI orchestrator for PDF → ChromaDB |
| `prompts/player_prompts.py` | ✓ Complete | Player prompt builder |
| `prompts/coach_prompts.py` | ✓ Complete | Coach prompt builder |
| `domains/gcse-english-tutor/GOAL.md` | ✓ Complete | Domain config (1,000 targets, 9 sections) |
| `domains/gcse-english-tutor/sources/` | ✗ Empty | Needs Mr Bruff PDFs + AQA mark schemes |
| `agent-config.yaml` | ✗ Missing | Must create |
| `AGENTS.md` | ✗ Missing | Must create |
| `chroma_data/` | ✗ Missing | Must run ingestion |
| `.env` | ✗ Missing | Optional (LangSmith tracing) |
