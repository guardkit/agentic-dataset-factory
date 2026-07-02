# Phase 1 Handoff — Wire the Factory Generative Mode (PO)

**Date:** 2026-07-02
**Prereqs:** Phase 0 CONCLUDED (`RESULTS-po-phase0.md`). Plan §3/§7 in `PLAN-po-dataset-generation.md`.
**Goal of Phase 1:** add a no-book **generative** mode to `agentic-dataset-factory` so a strong Player (gpt-oss-120b) generates PO training examples from the GOAL taxonomy — reusing the factory's Coach gate, layer routing, and output writing unchanged — then smoke-test that it emits **contract-valid ProductRoadmap JSON** the Coach accepts.

> **Latest commits (origin/main):** `bd886f3` (Phase 0 conclusion + grounding fix), `d8040d8` (contract probe + corpus items), `f892d76` (contract-run verdict). Working tree clean at handoff.

---

## What Phase 0 changed about Phase 1 (read first)

- **The base is strong** (grounds faithfully, never fabricates, assumptions/scope/decomposition/prioritisation 100%, 0/11 false-confidence across 3 runs). gpt-oss-120b (the generative Player) is stronger still. **So the Phase-1 risk is NOT judgment quality — it is serving-shape correctness.** The smoke-test bar is: *does the generative mode emit a ShareGPT example whose assistant content is `<think>` + a contract-valid ProductRoadmap JSON, and does the Coach accept it?*
- The `contract` output instruction in `score_golden_set.py` (`_CONTRACT_INSTRUCTION`) is the **prototype for the generative Player's output shape** — reuse its ProductRoadmap schema + grounding discipline when updating the Player prompt / GOAL Output Schema.
- `grounding_fidelity` is now mode-aware in `GOAL.md` (no-corpus modes: no-fabrication + brief-trace; empty `source_documents` OK). The Coach reads criteria from GOAL dynamically, so this is already live for training-time gating.
- **Deferred to Phase 2:** the phased `extract` flow (EpicPlan → EnrichmentBatch) where acceptance criteria live — single-pass ProductRoadmap has no AC field. Phase 1 targets single-pass ProductRoadmap only.

---

## The four seams (verified file:line, 2026-07-02)

The taxonomy walk, Coach gate, layer routing, output writing, checkpoint/resume are **already mode-agnostic** and stay unchanged. Only these change:

### Seam 1 — `src/tools/tool_factory.py:100` `create_player_tools`
Hardcodes `return [rag_tool]` (line 130). Add a `grounded: bool = True` param; when `False`, return `[]` (skip building the rag tool → no ChromaDB dependency).
```python
def create_player_tools(collection_name, persist_directory=..., grounded=True):
    if not grounded:
        return []
    rag_tool = create_rag_retrieval_tool(collection_name, persist_directory)
    return [rag_tool]
```

### Seam 2 — `agent.py` (startup wiring)
- `agent.py:133` `verify_chromadb_collection(config.domain)` — **skip when ungrounded** (a no-book domain has no collection; it would hard-fail). Guard on `config.generation.grounded`.
- `agent.py:147` `create_player_tools(collection_name=config.domain)` → pass `grounded=config.generation.grounded`.
- `agent.py:156` `rag_tool = tools[0] if tools else None` — already yields `None` for empty tools. **No change.**
- `run_generation_loop(..., rag_tool=rag_tool)` — the loop already guards `if rag_tool is not None:` (`generation_loop.py:673`) and `if rag_context:` (`:1182`), so `rag_tool=None` cleanly omits the pre-fetch + the "Curriculum Context" injection. **No loop change.**

### Seam 3 — `config/models.py:102` `GenerationConfig` + `agent-config.yaml`
Add one field to `GenerationConfig`: `grounded: bool = True` (default true keeps architect/tutor unchanged). Set `generation.grounded: false` in `agent-config.yaml` for the PO run, plus `domain: product-owner`, `player.model: gpt-oss-120b` (endpoint `http://localhost:9000/v1`), and `coach.model` = a **different** model (e.g. `qwen36-workhorse` or `coach-ft-v3` — must differ from the Player to avoid self-grading collusion; Coach must follow the CoachVerdict JSON, so a general instruct model, not a task-specialised FT — prefer `qwen36-workhorse`).

### Seam 4 — `prompts/player_prompts.py:178` `build_player_prompt`
Lines 46-70 carry the `rag_retrieval` + "Curriculum Context is pre-fetched" usage block. When ungrounded, **omit** that block (the Player has no rag tool and no injected context) — otherwise the prompt tells the model to use a tool it doesn't have and reference context that isn't there (re-teaching the fabrication the architect-v2 plan warns against). Simplest: thread a `grounded` flag into `build_player_prompt(goal, grounded=True)` and conditionally include the RAG block. (Called at `agent.py:142`.)

---

## Output-shape pre-check (the load-bearing correctness item)

The generative Player emits a **ShareGPT training example**: `{"messages": [system, user, {role:assistant, content}], "metadata": {...}}`. Per Decision A + OUTPUT-CONTRACT.md §124, the **assistant `content` must be `<think>…</think>` + a ```json-fenced ProductRoadmap object`** (not prose).

**Verify before generating:** does `GOAL.md §Output Schema` already specify this nested shape (think + fenced ProductRoadmap JSON as the assistant content), and does `build_player_prompt` convey the ProductRoadmap field list + the mode-aware grounding discipline? If not, update the GOAL Output Schema (reuse `_CONTRACT_INSTRUCTION`'s schema block from `score_golden_set.py`). This is the single thing most likely to make the smoke-test fail.

---

## Smoke-test — definition of done

1. `agent-config.yaml`: `domain: product-owner`, `generation.grounded: false`, `player=gpt-oss-120b`, `coach=qwen36-workhorse` (≠ player).
2. Run the factory over 5–10 targets across 2–3 modes (a small `GOAL.md` target slice, or cap the run).
3. **Pass criteria:**
   - No ChromaDB / rag errors (Seam 1+2 working; no "Curriculum Context" in the Player message).
   - Player output parses as `{messages, metadata}` (format gate passes).
   - Assistant content has a `<think>` block (`type_correct`) + a fenced ProductRoadmap JSON that `ProductOwnerOutputHandler.parse()` would accept (≥1 epic, feature_spec_inputs flatten-match, description ≥2 sentences, enum Literals, greenfield `coverage_score=null`).
   - Coach accepts a reasonable fraction; rejects trace to real quality issues, not shape confusion.
   - Accepted rows land in `output/train.jsonl` (behaviour) via the unchanged layer routing.

## Operational notes (for the smoke-test run)
- gpt-oss-120b as Player needs co-residency with the Coach. If Coach = `qwen36-workhorse` (always-on), gpt-oss-120b loading **evicts the fleet** — pause keepalive first: `sudo systemctl stop llama-swap-keepalive.timer` (Rich's sudo; re-enable after). The `po_eval` matrix set (gpt-oss-120b + gemma4-26b) exists; for a Player+Coach run you may want a `po_gen` set (`go & qw`) or just let the solver swap. Alternatively run the smoke with a smaller Player first (qwen36-workhorse) purely to de-risk the *plumbing*, then switch to gpt-oss-120b for quality.
- The `.env` dummy `OPENAI_API_KEY` is needed (agent.py loads it via `load_dotenv`).

---

## Open decisions for Phase 1
1. **Coach model for generation.** `qwen36-workhorse` (general, always-on, follows CoachVerdict) vs a PO-specialised coach (none exists yet). Recommend `qwen36-workhorse` for the smoke; revisit for the bulk run.
2. **Does GOAL Output Schema already emit think+ProductRoadmap JSON?** Verify/patch (above).
3. **Target slicing for the smoke** — how to run a small subset without editing GOAL's 1,050-count table (e.g. a `--limit` or a scratch GOAL). Check `generation_loop` target expansion (`:1264` `for _ in range(target.count)`).

---

## Gotchas / do-not-repeat
- Don't remove/repoint `gemma4-31b` or `gemma4-coach` in llama-swap (fallback + base). New model handles are additive.
- Harness `--concurrency` must be ≤ the model's llama-swap `concurrencyLimit` (2) or you get HTTP 429 (retry is in place, but keep it ≤2).
- Generated run outputs under `golden_set/` (`phase0_*.json/.log`) are gitignored — reproducible; the committed record is `RESULTS-po-phase0.md`.

---

*State at handoff: Phase 0 done + committed; harness, golden set (13–19 items), and all findings pushed to origin/main. Phase 1 = the four seams + output-shape pre-check + smoke-test above.*
