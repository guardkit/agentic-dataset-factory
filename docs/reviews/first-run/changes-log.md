# First Run Changes Log

All code changes made during the PRF-006 first run debugging session, from initial `python agent.py` through to the successful Qwen2.5-14B run on GB10.

## Runtime & Initialization

### 1. agent.py — dotenv loading + sys.path fix

**Problem**: `.env` file not loaded (ANTHROPIC_API_KEY missing); `from src.tools.tool_factory` failed at runtime because `src/` not on Python path (only configured for pytest via `pyproject.toml`).

**Changes**:
- Added `from dotenv import load_dotenv` and `load_dotenv()` before any SDK imports
- Added `sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))` to match pytest's `pythonpath = ["src"]`
- Changed `from src.tools.tool_factory import create_player_tools` → `from tools.tool_factory import create_player_tools`

### 2. agent-config.yaml — created and iterated

**Created** with initial config for `gcse-english-tutor` domain. Went through several iterations:
1. Initial: `provider: local`, Qwen3-Coder-Next on port 8002 (not running)
2. Changed to: `provider: anthropic`, claude-sonnet-4-6 / claude-opus-4-6 (billing insufficient)
3. Changed to: `provider: local`, Qwen2.5-14B on port 8000 (missing `langchain-openai` package, then missing `--enable-auto-tool-choice`)
4. Final: `provider: local`, Qwen2.5-14B on port 8002 (dedicated vLLM instance with tool-calling)

### 3. .env — created

Contains `ANTHROPIC_API_KEY` (for when Anthropic models are used).

## Parser Fix

### 4. domain_config/parser.py — table header detection

**Problem**: `parse_table()` assumed line 0 of a section was always the table header. When sections had introductory text before the table (e.g., Evaluation Criteria), the prose was parsed as a data row, producing empty `EvaluationCriterion` objects.

**Changes** to `parse_table()`:
- Scans for the actual header row (first pipe-delimited line matching known column headers) instead of assuming line 0
- Skips non-table lines (no `|` character) in data rows
- All processing starts from `header_line_idx + 1` instead of `lines[1:]`

## GOAL.md Changes

### 5. domains/gcse-english-tutor/GOAL.md — reduced targets for testing

**Changes**:
- Source Documents: Changed patterns from `mr-bruff-*.pdf` / `aqa-mark-schemes/*.pdf` to `*.pdf` (matching actual filenames)
- Generation Targets: Reduced from 7 categories / 1,000 total to 1 category / 1 target
- Removed `Total:` and `Reasoning/direct split:` summary lines (parser treated them as table rows)
- Removed `(can be empty)` from `ao` field valid values

## Player Model Fix (TASK-PRF-001)

### 6. agents/player.py — use shared model_factory

**Problem**: Player had a local `create_model()` returning `"provider:model"` string. For `provider: local`, this produced `"local:Qwen/..."` which is not a valid `init_chat_model` provider.

**Changes**:
- Removed local `create_model()` function (lines 25-39)
- Added `from agents.model_factory import create_model` (same as coach.py)

## Tool Fixes (from second run session)

### 7. src/tools/rag_retrieval.py — ChromaDB persistence path

**Problem**: `PersistentClient()` called without path argument, so ChromaDB couldn't find the `./chroma_data` directory populated during ingestion.

**Changes**:
- Added `persist_directory: str = "./chroma_data"` parameter to `create_rag_retrieval_tool()`
- Changed to `chromadb.PersistentClient(path=persist_directory)`

### 8. src/tools/tool_factory.py — pass persist_directory through

**Changes**:
- Added `persist_directory` parameter to `create_player_tools()`
- Passes it through to `create_rag_retrieval_tool()`

### 9. src/tools/write_output.py — array field validation

**Problem**: `metadata.ao` field (e.g. `["AO1", "AO2"]`) failed validation because the validator checked the whole array against valid values instead of each element.

**Changes**:
- Array fields: validate each element individually, collect invalid ones
- Scalar fields: unchanged
- Skip `None` values
- Enhanced error messages listing all invalid values

## Ingestion Pipeline Fixes (from TASK-PRF-005)

### 10. ingestion/docling_processor.py — Docling v2 API

**Problem**: Docling v2's `PageItem` objects don't have a `.text` attribute.

**Changes**:
- Switched from `doc.pages` dictionary to `doc.iterate_items()` which returns content items with provenance
- Extracts page numbers from `prov_list[0].page_no`

### 11. ingestion/chromadb_indexer.py — unique chunk IDs

**Problem**: Chunk IDs collided across pages.

**Changes**:
- ID format changed from `{domain}_{source_file}_{chunk_index}` to `{domain}_{source_file}_p{page_number}_c{chunk_index}`

## New Files Created

### 12. AGENTS.md — agent boundaries

Created at repo root with ALWAYS/NEVER/ASK sections for Player and Coach agents. Required by both factories: `memory=["./AGENTS.md"]`.

### 13. vllm-agentic-factory.sh — dedicated vLLM script

Created at `guardkit/scripts/vllm-agentic-factory.sh`. Key differences from `vllm-graphiti.sh`:
- Adds `--enable-auto-tool-choice --tool-call-parser hermes`
- Uses port 8002 (doesn't touch Graphiti on 8000)
- GPU util 0.35 (fits alongside Graphiti's 0.40)
- Context 16384

## Dependencies Installed

- `langchain-openai` — required by `init_chat_model` for the `openai` provider (which `local` maps to)
- `python-dotenv` — already installed, used for `.env` loading

## Test Updates

Updated mocks/assertions in:
- `src/tools/tests/test_tool_factory.py` — persist_directory parameter
- `src/tools/tests/test_rag_retrieval.py` — ChromaDB path tests
- `src/tools/tests/test_write_output.py` — array validation tests
- `ingestion/tests/test_chromadb_indexer.py` — new chunk ID format
- `ingestion/tests/test_docling_processor.py` — Docling v2 iterate_items API

## First Run Result

After all fixes, the pipeline ran successfully against Qwen2.5-14B on GB10 port 8002:
- 8 successful API round trips (200 OK)
- RAG retrieval errors (ChromaDB connection issue — fixed in subsequent session)
- `metadata.ao` validation errors (fixed in subsequent session)
- Timed out at 600s after looping on failed tool calls
- Result: 0 accepted, 1 rejected (timeout)

See `docs/reviews/first-run/vllm-qwen-25-1.md` for full execution log.
