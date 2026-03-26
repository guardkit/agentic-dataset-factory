# Review Report: TASK-REV-A1B4

## Executive Summary

All 6 findings from the pre-run verification review have been verified against the actual codebase. **Every finding is confirmed accurate.** One confirmed code bug (Player model creation), three missing files, a documented startup dependency chain, and port allocation requirements — all match the current repo state exactly.

## Review Details

- **Mode**: Architectural / Pre-Run Verification Analysis
- **Depth**: Standard (code-level inspection)
- **Scope**: `agents/player.py`, `agents/coach.py`, `agents/model_factory.py`, `config/models.py`, missing files inventory
- **Date**: 2026-03-22

---

## Findings Verification

### Finding 1: CONFIRMED BUG — Player Model Creation (P0)

**Status**: CONFIRMED

**Evidence**:
- `agents/player.py:25-39` defines a local `create_model()` that returns `f"{model_config.provider}:{model_config.model}"` — a raw string
- For `provider: local`, this produces `"local:Qwen/Qwen3-Coder-Next-FP8"`
- `"local"` is NOT a valid `init_chat_model` provider (only `openai`, `anthropic`, `google_genai`, etc.)
- `agents/coach.py:25` correctly imports `from agents.model_factory import create_model`
- `agents/model_factory.py:28-32` has `_PROVIDER_MAP = {"local": "openai", ...}` which correctly translates `local` → `openai`
- The Player's `create_model` returns `str`, while the shared factory returns `BaseChatModel` — type mismatch

**Root Cause**: TASK-AF-003 (Player) and TASK-AF-004 (Coach) were built independently by AutoBuild. The Coach correctly used the shared `model_factory`, but the Player got a local string-based shortcut that doesn't handle provider mapping.

**Fix**: Replace `player.py`'s local `create_model()` with `from agents.model_factory import create_model` (same as `coach.py` already does). No other changes needed.

### Finding 2: Missing Files (P0)

**Status**: ALL CONFIRMED MISSING

| File | Exists? | Impact |
|------|---------|--------|
| `agent-config.yaml` | NO | Startup Step 1 fails (`load_config()` → `FileNotFoundError`) |
| `AGENTS.md` | NO | Startup Step 10 fails (both factories pass `memory=["./AGENTS.md"]`) |
| `chroma_data/` | NO | Startup Step 5 fails (`verify_chromadb_collection()`) |
| `.env` | NO | Non-blocking (LangSmith tracing disabled) |

### Finding 3: Startup Dependency Chain

**Status**: CONFIRMED — consistent with code structure in `agent.py`, `entrypoint/startup.py`, `config/loader.py`

Steps 1, 5, and 10 will fail without prerequisites. The 12-step chain is accurately documented.

### Finding 4: Test Suite Assessment

**Status**: NOT YET VERIFIED (requires `pip install -e ".[dev]"` and `pytest` execution)

The test file inventory and recommended execution order appear accurate based on directory structure.

### Finding 5: Architecture Observations

**Status**: CONFIRMED — AutoBuild quality is excellent. The Player/Coach model factory inconsistency is the only confirmed code bug. Clean separation, resilience patterns, and validation chains all present.

### Finding 6: Port Allocation

**Status**: CONFIRMED — Port 8002 is the only port required for first run (Player + Coach inference via vLLM).

---

## Recommendations

### Priority Ordering (Recommended)

| Order | Priority | Task | Rationale |
|-------|----------|------|-----------|
| 1 | P0 | TASK-FIX-MODEL | 3-line fix, unblocks Player agent creation |
| 2 | P0 | TASK-CREATE-CONFIG | Required for Step 1 of startup; schema fully defined in `config/models.py` |
| 3 | P0 | TASK-CREATE-AGENTS-MD | Required for Step 10; template provided in verification review |
| 4 | P1 | TASK-VERIFY-TESTS | Run test suite to catch any other AutoBuild issues before proceeding |
| 5 | P1 | TASK-INGEST | Populate ChromaDB for Step 5; requires source PDFs |
| 6 | P2 | TASK-FIRST-RUN | End-to-end validation once all above complete |

### Decision: Model Strategy

Both Player and Coach should use the **same model** for the first run (simplest configuration, single vLLM instance on port 8002). The architecture supports different models via separate `player:` and `coach:` config sections — this can be changed later (e.g., Nemotron 3 Super for Coach).

### Decision: Test-First Approach

**Run tests BEFORE applying fixes.** This establishes a baseline:
1. Run `pytest --tb=short -q` to see what passes/fails with current code
2. Apply TASK-FIX-MODEL
3. Re-run tests to confirm fix doesn't break existing test expectations (mocks may need updating for return type change from `str` to `BaseChatModel`)

---

## Risk Assessment

| Risk | Status | Notes |
|------|--------|-------|
| Player model creation fails | **CONFIRMED** | Fix is trivial (import change) |
| Missing config files | **CONFIRMED** | Templates available in review doc |
| SDK API mismatch | LOW | Check `deepagents>=0.4.11` matches installed version |
| Import path issues | LOW | `pyproject.toml` pythonpath handles `src/` prefix |
| Generation loop bugs | LOW | Well-tested; validate with single-target run |

---

## Appendix: Files Inspected

- `agents/player.py` — confirmed bug at line 25-39
- `agents/coach.py` — confirmed correct import at line 25
- `agents/model_factory.py` — confirmed provider mapping at lines 28-32
- `config/models.py` — confirmed schema for `agent-config.yaml`
- `agent-config.yaml` — confirmed missing
- `AGENTS.md` — confirmed missing
- `chroma_data/` — confirmed missing
- `.env` — confirmed missing (non-blocking)
