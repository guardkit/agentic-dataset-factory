# Review Report: TASK-REV-E2A7

## Executive Summary

The first end-to-end run of the agentic-dataset-factory pipeline (Qwen2.5-14B-Instruct via vLLM on GB10) completed 8 API round trips but produced 0 accepted and 1 rejected example before hitting the 600s timeout. Root cause analysis identifies **two confirmed bugs** and **one design gap**. The model performed well mechanically — all failures trace to tool/validation implementation issues, not model capability.

## Review Details

- **Mode**: Decision Analysis + Root Cause Investigation
- **Depth**: Comprehensive (revised from standard — deep code trace with diagrams)
- **Source**: `docs/reviews/first-run/vllm-qwen-25-1.md` (raw pipeline logs)
- **Scope**: RAG retrieval, write_output validation, generation loop, deployment
- **Diagrams**: 3 Excalidraw sequence diagrams (C4 Container, Finding 1 trace, Finding 2 trace)

## Confidence Level

**HIGH** — Both root causes confirmed by:
1. Reading every file in the call chain end-to-end
2. Matching log evidence to specific lines of code
3. Verifying ChromaDB default path via Python signature inspection
4. Confirming collection exists in `chroma_data/chroma.sqlite3`
5. Tracing the exact Python semantics of `list not in list` evaluation

---

## Finding 1: RAG Retrieval — ChromaDB Path Mismatch (P0)

**Root Cause: CONFIRMED BUG**

The rag_retrieval tool at [rag_retrieval.py:122](src/tools/rag_retrieval.py#L122) calls:
```python
chromadb.PersistentClient()  # No path argument
```

ChromaDB's default path is `./chroma` (confirmed via signature inspection). However:
- The ingestion pipeline ([chromadb_indexer.py:39](ingestion/chromadb_indexer.py#L39)) writes to `./chroma_data`
- The startup verification ([startup.py:155](entrypoint/startup.py#L155)) checks `./chroma_data`

**Evidence from logs**:
```
Collection 'gcse-english-tutor' not found: Collection [gcse-english-tutor] does not exist
```

The collection exists in `./chroma_data/chroma.sqlite3` (confirmed: `gcse-english-tutor` with 3854 chunks from TASK-PRF-005). But the rag_retrieval tool opens `./chroma` — a different database entirely.

**Fix**: Pass `path="./chroma_data"` to `PersistentClient()` in `rag_retrieval.py:122`. Better: accept `persist_directory` as a factory parameter to `create_rag_retrieval_tool()` for configurability.

**Severity**: P0 — Completely blocks RAG grounding. Every generation attempt runs without source material.

### Deep Trace: Finding 1 — Three ChromaDB Client Instances

The pipeline creates three separate ChromaDB `PersistentClient` instances across its lifecycle. Only two use the correct path:

| Component | File | Line | Path Argument | Correct? |
|-----------|------|------|---------------|----------|
| Ingestion | `ingestion/chromadb_indexer.py` | 39-41 | `path=persist_directory` (default `"./chroma_data"`) | YES |
| Startup verification | `entrypoint/startup.py` | 155 | `path="./chroma_data"` | YES |
| RAG retrieval tool | `src/tools/rag_retrieval.py` | 122 | **(none)** — `PersistentClient()` | **NO** |

ChromaDB `PersistentClient` constructor signature (confirmed):
```python
PersistentClient(path: str | Path = './chroma', ...) -> ClientAPI
```

The default is `./chroma`, not `./chroma_data`. This means the rag_retrieval tool opens an entirely separate, empty database.

**Why startup didn't catch this**: `verify_chromadb_collection()` at [startup.py:125-178](entrypoint/startup.py#L125-L178) creates its own `PersistentClient(path="./chroma_data")` and verifies the collection exists (3854 chunks). But this client instance is discarded — it is not passed to the tool factory. The rag_retrieval tool creates a new client lazily on first invocation ([rag_retrieval.py:114-123](src/tools/rag_retrieval.py#L114-L123)), and this one uses the wrong default.

**Call chain (traced through every file)**:
```
agent.py:133  verify_chromadb_collection(config.domain)     → PersistentClient(path="./chroma_data") → OK ✓
agent.py:146  create_player_tools(collection_name=config.domain, ...)
  → tool_factory.py:128  create_rag_retrieval_tool("gcse-english-tutor")
    → rag_retrieval.py:109  _validate_collection_name("gcse-english-tutor") → OK ✓
    → Returns closure. No ChromaDB connection yet.
...
[Runtime — Player calls rag_retrieval("Macbeth Act 1...")]
  → rag_retrieval.py:116  _get_client()
    → rag_retrieval.py:122  chromadb.PersistentClient()  ← DEFAULTS TO ./chroma
    → rag_retrieval.py:157  client.get_collection("gcse-english-tutor")
    → EXCEPTION: Collection [gcse-english-tutor] does not exist
    → Returns: "Error: ChromaDB collection 'gcse-english-tutor' not found — ..."
```

**Verified on disk**:
```
$ sqlite3 chroma_data/chroma.sqlite3 "SELECT name FROM collections"
→ gcse-english-tutor    (3854 chunks)

$ ls chroma/    # does not exist (default path was never populated)
→ ls: No such file or directory
```

---

## Finding 2: metadata.ao Validation — Array vs Scalar Comparison (P0)

**Root Cause: CONFIRMED BUG**

The write_output validation at [write_output.py:154](src/tools/write_output.py#L154):
```python
if field_value is not None and field_value not in valid_values:
```

For the `ao` field:
- GOAL.md defines `ao` as `array[string]` with valid values `AO1, AO2, AO3, AO4, AO5, AO6`
- The parser ([parser.py:86-94](domain_config/parser.py#L86-L94)) produces `valid_values = ["AO1", "AO2", "AO3", "AO4", "AO5", "AO6"]`
- The model correctly generates `"ao": ["AO2", "AO3"]` (a list)
- The validation checks `["AO2", "AO3"] in ["AO1", "AO2", ...]` — **list-in-list membership, always False**

**Evidence from logs** (repeated 8+ times):
```
Error: metadata.ao value '['AO2', 'AO3']' not in valid values
```

The model even attempted self-correction ("Let me correct this and ensure the AO values are properly formatted") but the fix was impossible — the validator rejects all list values regardless of content.

**Fix**: Step 9 validation must distinguish array fields from scalar fields. For array fields, validate that each element is in `valid_values`:
```python
if isinstance(field_value, list):
    invalid = [v for v in field_value if v not in valid_values]
    if invalid:
        return f"Error: metadata.{field_name} contains invalid values: {invalid}"
else:
    if field_value is not None and field_value not in valid_values:
        return f"Error: metadata.{field_name} value '{field_value}' not in valid values"
```

**Severity**: P0 — Blocks ALL example acceptance for any target that includes `ao` metadata (which is every target in the GCSE English domain).

### Deep Trace: Finding 2 — Data Flow from GOAL.md to Rejection

**Step 1: GOAL.md source** ([GOAL.md:90](domains/gcse-english-tutor/GOAL.md#L90)):
```markdown
| ao | array[string] | yes | AO1, AO2, AO3, AO4, AO5, AO6 (can be empty) |
```

**Step 2: Parser** ([parser.py:86-94](domain_config/parser.py#L86-L94)):
```python
def _coerce_valid_values(raw: str) -> list[str]:
    stripped = raw.strip()  # "AO1, AO2, AO3, AO4, AO5, AO6 (can be empty)"
    return [v.strip() for v in stripped.split(",") if v.strip()]
    # Result: ["AO1", "AO2", "AO3", "AO4", "AO5", "AO6 (can be empty)"]
```

Note: The parser also captures the parenthetical `"AO6 (can be empty)"` as a single value. This is a minor secondary issue — the primary bug is the scalar/array comparison.

**Step 3: MetadataField model** ([models.py:94-100](domain_config/models.py#L94-L100)):
```python
class MetadataField(BaseModel):
    field: str       # "ao"
    type: str        # "array[string]"  ← stored but NEVER used by write_output
    required: bool   # True
    valid_values: list[str]  # ["AO1", "AO2", ..., "AO6 (can be empty)"]
```

**Step 4: Tool factory** ([tool_factory.py:128-129](src/tools/tool_factory.py#L128-L129)):
```python
write_tool = create_write_output_tool(output_dir, metadata_schema)
```

**Step 5: write_output closure** ([write_output.py:64-69](src/tools/write_output.py#L64-L69)):
```python
schema_lookup: dict[str, list[str]] = {}
for field_def in metadata_schema:
    if field_def.valid_values:
        schema_lookup[field_def.field] = field_def.valid_values
# schema_lookup = {"ao": ["AO1",...], "text": [...], "topic": [...], ...}
# Note: field_def.type ("array[string]") is NEVER stored or inspected
```

**Step 6: Model generates** (confirmed from logs):
```json
{"metadata": {"ao": ["AO2", "AO3"], ...}}
```

**Step 7: Validation fails** ([write_output.py:149-158](src/tools/write_output.py#L149-L158)):
```python
for field_name, valid_values in schema_lookup.items():
    if field_name in ("layer", "type"):
        continue
    field_value = metadata.get(field_name)  # ["AO2", "AO3"] (a list)
    if field_value is not None and field_value not in valid_values:
        # Python evaluates: ["AO2", "AO3"] not in ["AO1", "AO2", ..., "AO6 (can be empty)"]
        # list.__contains__ checks: ["AO2","AO3"] == "AO1"? No (list != str)
        #                           ["AO2","AO3"] == "AO2"? No (list != str)
        #                           ... all False
        # Result: not in → True → return error
        return f"Error: metadata.{field_name} value '{field_value}' not in valid values"
```

**The fundamental issue**: `write_output.py` Step 9 treats every metadata field as a scalar string. It has no awareness of `MetadataField.type` — the `type` field is parsed by the parser and stored in the model, but the `schema_lookup` dict at line 66-69 only extracts `field` and `valid_values`, discarding the type information entirely. Without knowing that `ao` is `array[string]`, the validator cannot iterate over the array elements.

**Secondary issue**: `_coerce_valid_values` splits on comma, producing `"AO6 (can be empty)"` as a single value. If the fix includes array-element validation, it should also strip parenthetical notes from valid values, or the GOAL.md should be updated to `AO1, AO2, AO3, AO4, AO5, AO6` without the parenthetical.

---

## Finding 3: Infinite Retry Loop Within DeepAgents Turn (P1)

**Root Cause: Design gap (not a bug)**

The generation loop has proper bounds:
- `max_turns=3` ([models.py:114-118](config/models.py#L114-L118)) — limits Player-Coach cycles
- `target_timeout=600s` ([models.py:134-138](config/models.py#L134-L138)) — hard timeout per target

However, within a single Player turn, the DeepAgents SDK controls tool invocation internally. When both rag_retrieval and write_output fail, the Player:
1. Calls rag_retrieval → error
2. Generates without RAG → calls write_output → validation error
3. Self-corrects → calls write_output again → same validation error
4. Repeats steps 2-3 until the SDK's internal limit or the 600s timeout

The 8 round trips in the logs all occurred within **turn 1** of the Player-Coach cycle. The Coach was never reached because write_output kept rejecting before the Player could submit for evaluation.

**Recommendation**: This is not strictly a bug — the 600s timeout is the backstop. But the loop is wasteful. Options:
- **Option A**: Configure DeepAgents SDK `max_tool_calls` per turn (if supported)
- **Option B**: Track consecutive identical errors in write_output and return a "fatal: stop retrying" message after N identical failures
- **Option C**: Accept the current behavior (600s timeout is the bound) — fixing Findings 1 and 2 eliminates the trigger

**Recommended**: Option C for now. Fixing the two bugs removes the retry trigger entirely. Add Option B as a hardening measure in a future iteration.

---

## Finding 4: Model Suitability — Qwen2.5-14B (P2, Informational)

**Assessment**: The model performed well. It:
- Made correct tool calls (rag_retrieval, write_output) in the right order
- Followed the prescribed workflow
- Attempted self-correction when receiving error feedback
- Generated structurally valid JSON with correct ShareGPT format

The failures were entirely in the tool implementations. No model change is needed.

**Note**: The dedicated vLLM instance on port 8002 (`vllm-agentic-factory.sh` with `--enable-auto-tool-choice --tool-call-parser hermes`) is a good setup. This avoids conflict with the Graphiti vLLM on port 8000.

---

## Finding 5: GB10 Deployment Strategy (P1, Decision)

**Current state**:
- MacBook: ChromaDB (`chroma_data/`), pipeline code, output
- GB10: vLLM inference (Qwen2.5-14B on port 8002)
- Network: Tailscale tunnel between MacBook and GB10

**Decision matrix**:

| Option | Latency | Setup Cost | Maintenance | Risk |
|--------|---------|------------|-------------|------|
| A: Keep split (MacBook + GB10) | ~50ms/call via Tailscale | None (current) | Low | Network dependency |
| B: Full GB10 deployment | <1ms (local) | Medium (clone repo, venv, re-ingest) | Medium | Single point of failure |
| C: Split + ChromaDB on GB10 only | ~50ms for LLM, local for tools | Low (move chroma_data) | Low | Partial coupling |

**Recommendation**: **Option A (keep split)** for now. Rationale:
1. The 50ms Tailscale latency is negligible compared to LLM inference time (~5-10s per call)
2. The two bugs (Findings 1-2) are the actual blockers, not architecture
3. Full GB10 migration introduces setup risk and delays the second run
4. Revisit if overnight runs show network instability

---

## Recommendations Summary

| # | Priority | Action | Effort | Impact |
|---|----------|--------|--------|--------|
| 1 | P0 | Fix rag_retrieval ChromaDB path: pass `path="./chroma_data"` | 1 line change | Unblocks RAG grounding |
| 2 | P0 | Fix write_output Step 9 to handle array metadata fields | ~10 lines | Unblocks example acceptance |
| 3 | P1 | Add max-consecutive-error guard in write_output (hardening) | ~15 lines | Prevents wasteful retries |
| 4 | P2 | Keep split MacBook/GB10 architecture | 0 effort | No change needed |
| 5 | P2 | Re-run pipeline after fixes 1-2 applied | Config only | Validates pipeline end-to-end |

---

## Appendix: Log Timeline Reconstruction

```
T+0s    Pipeline starts, connects to GB10:8002 (vLLM Qwen2.5-14B)
T+~2s   Player Turn 1 begins
T+~3s   rag_retrieval called → "Collection not found" (wrong ChromaDB path)
T+~5s   Player generates without RAG context
T+~7s   write_output called → "metadata.ao value '['AO2', 'AO3']' not in valid values"
T+~10s  Player self-corrects, retries write_output → same error
        ... (6 more retry cycles within DeepAgents SDK) ...
T+600s  target_timeout triggers → "target_rejected: index=0, reason=timeout"
```

## Appendix: Confirmed Collection Data

```
ChromaDB path: ./chroma_data/chroma.sqlite3
Collection: gcse-english-tutor
Chunks indexed: 3854 (from TASK-PRF-005 ingestion run)
Sources: 7 PDF documents
```

## Appendix: C4 Container Boundary Analysis

### System Boundaries (from C4 Container Diagram)

```
┌─────────────────────────────────────────────────┐  ┌──────────────────────┐
│ MacBook (localhost)                              │  │ GB10 (Tailscale)     │
│                                                  │  │                      │
│  agent.py ──→ startup.py ──→ ./chroma_data/ ✓   │  │  vLLM (port 8002)   │
│     │                                            │  │  Qwen2.5-14B-FP8    │
│     ├──→ generation_loop.py                      │  │  --tool-call-parser  │
│     │       ├──→ Player ────────────HTTP──────────│──│──→ /v1/chat/compl.  │
│     │       │     ├──→ rag_retrieval ──→ ./chroma/│  │                      │
│     │       │     │    ^^^^^ BUG 1: wrong path   │  │                      │
│     │       │     └──→ write_output (Step 9 bug) │  │                      │
│     │       │          ^^^^^ BUG 2: array!=scalar│  │                      │
│     │       └──→ Coach ─────────────HTTP──────────│──│──→ /v1/chat/compl.  │
│     │                                            │  │                      │
│  ./chroma_data/ (3854 chunks) ← ingestion        │  │                      │
│  ./output/ ← write_output results                │  │                      │
└─────────────────────────────────────────────────┘  └──────────────────────┘
```

### Cross-Boundary Technology Mapping

| Boundary | Protocol | Latency | Config Source |
|----------|----------|---------|---------------|
| Player → vLLM | HTTP POST via Tailscale | ~50ms + ~5-10s inference | `agent-config.yaml:6` endpoint |
| Coach → vLLM | HTTP POST via Tailscale | ~50ms + ~3-5s inference | `agent-config.yaml:12` endpoint |
| rag_retrieval → ChromaDB | Embedded SQLite (PersistentClient) | <1ms | **MISSING** — defaults to `./chroma` |
| startup → ChromaDB | Embedded SQLite (PersistentClient) | <1ms | Hardcoded `"./chroma_data"` |
| write_output → filesystem | File append | <1ms | `output_dir` param from `agent.py:148` |

### Key Architectural Insight

Both bugs exist entirely within the MacBook boundary. The GB10/Tailscale boundary is clean — HTTP inference works correctly. The bugs are in how local resources (ChromaDB path, metadata type awareness) are wired between components that share the same process.

## Appendix: Complete File Trace

Every file read during this review, in call-chain order:

1. `agent-config.yaml` — domain, model, generation config
2. `agent.py` — LangGraph node orchestrating steps 1-12
3. `entrypoint/startup.py` — verify_chromadb_collection (correct path)
4. `domain_config/parser.py` — GOAL.md parsing, _coerce_valid_values
5. `domain_config/models.py` — MetadataField model (type field stored but unused)
6. `domains/gcse-english-tutor/GOAL.md` — metadata schema source table
7. `src/tools/tool_factory.py` — create_player_tools wiring
8. `src/tools/rag_retrieval.py` — PersistentClient() with no path (BUG 1)
9. `src/tools/write_output.py` — Step 9 scalar validation (BUG 2)
10. `agents/player.py` — Player factory (tools, backend, prompt)
11. `entrypoint/generation_loop.py` — Player-Coach cycle, timeout handling
12. `config/models.py` — GenerationConfig (max_turns=3, target_timeout=600)
13. `ingestion/chromadb_indexer.py` — confirms persist_directory="./chroma_data"
14. `docs/reviews/first-run/vllm-qwen-25-1.md` — raw pipeline logs
