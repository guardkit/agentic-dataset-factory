# PO Phase 1 — Factory Generative Mode: Results

**Date:** 2026-07-03
**Handoff:** `HANDOFF-po-phase1-generative-mode.md` · **Plan:** `PLAN-po-dataset-generation.md` §3/§7
**Player:** `gpt-oss-120b` (generative, no corpus) · **Coach/gate:** `gemma4-coach` (Gemma-4-26B-A4B-IT base, distinct model — no self-scoring)

---

## TL;DR — Phase 1 CONCLUDED (2026-07-03): generative mode works end-to-end

Added a no-book **generative** mode to `agentic-dataset-factory` so a strong Player (`gpt-oss-120b`) generates PO training examples from the GOAL taxonomy with **no ChromaDB, no RAG tool, and no pre-fetched curriculum context** — reusing the factory's Coach gate, layer routing, output writing, and checkpoint/resume **unchanged**. The smoke-test bar (from the handoff) was serving-shape correctness, and it is met:

- **gpt-oss-120b + gemma4-coach quality run = 6/6 accepted, 0 rejected.** Every accepted row is a ShareGPT example whose assistant content is `<think>…</think>` + a ```json-fenced **ProductRoadmap** that parses, tagged `layer=behaviour` → routed to `output/train.jsonl`.
- **Clean greenfield grounding:** every row has `coverage_score=null` and **zero `source_documents`** at every level — no fabricated citations, exactly the mode-aware discipline. No numeric-priority inflation.
- **gemma4-coach discriminates**, it does not rubber-stamp: 5/6 targets went `revise (score 2) → accept (score 5)`, exercising the propose→feedback→revise loop.

One real, general bug was found and fixed along the way (Coach empty-structured-output refusals were mis-handled as unrecoverable failures — see below).

---

## What was built

### The four seams (the taxonomy walk, Coach gate, layer routing, output writing, checkpoint/resume stayed unchanged)

1. **`src/tools/tool_factory.py`** — `create_player_tools(..., grounded=True)`; `grounded=False` returns `[]` (no `rag_retrieval`, no ChromaDB dependency, `collection_name` unused/unvalidated).
2. **`agent.py`** — `verify_chromadb_collection` is skipped when `config.generation.grounded` is false (a no-book domain has no collection → would hard-fail `ConnectionError`); `grounded` threaded into `create_player_tools` and `build_player_prompt`. The loop's `rag_tool=None` guards already omit pre-fetch + curriculum injection cleanly — **no loop change** for the RAG path.
3. **`config/models.py`** — `GenerationConfig.grounded: bool = True` (default keeps architect/tutor grounded) + `limit: int | None = None` (caps expanded targets for smoke runs without editing GOAL's count table).
4. **`prompts/player_prompts.py`** — new `PLAYER_BASE_PROMPT_UNGROUNDED` (omits the tool/curriculum blocks; adds a generative-mode note + anti-fabrication grounding: "never fabricate a source… leave source/citation fields empty when no corpus is supplied"); `build_player_prompt(goal, *, grounded=True)` selects the base. `PLAYER_BASE_PROMPT` is untouched.

### Output-shape (the load-bearing correctness item)

The GOAL Output Schema previously carried only a **prose** placeholder for the assistant content, and the ProductRoadmap field list lived only in the external `OUTPUT-CONTRACT.md` (which the Player never sees). Fixed by **inlining the `_CONTRACT_INSTRUCTION` ProductRoadmap schema + mode-aware grounding discipline into `GOAL.md` → Generation Guidelines** (injected verbatim into the Player prompt), and pointing the Output Schema example's assistant `content` at a ```json-fenced ProductRoadmap object. Pure domain-file change, no code coupling; reaches the Player in both grounded and ungrounded modes.

### Coach robustness fix (general, not PO-specific)

`gemma4-coach` (via llama.cpp under the structured-output `json_schema` grammar) **intermittently returns `content='' , additional_kwargs={'refusal': None}`** — an *empty* response carrying a null-valued `refusal` key. The old refusal detector only fired on a **truthy** refusal string, so this fell through to a generic `ValueError` → unrecoverable `llm_failure`, and the structured-outputs fallback never triggered. Fix in `entrypoint/generation_loop.py`:
- `CoachRefusalError(reason, empty_structured_output=True)` when the `refusal` key is present with empty content.
- The generation loop routes that case **straight to the non-structured `coach_fallback`** (skipping the reframed-prompt retry, which omits the example and could grade a placeholder), reusing a new `_invoke_coach_fallback` helper. Content-policy refusals keep the reframe→fallback path.

---

## Runs (all `limit=6`, `grounded=false`; targets = first "Outcome framing" slice → all `greenfield` mode)

| Run | Player | Coach | Accepted | Notes |
|---|---|---|---|---|
| Pre-flight (plumbing) | qwen36-workhorse | coach-ft-v3 | **4/6** | Zero infra (both in always-on `all` set). Validated all four seams + output shape. The 2 rejects were **cfv3 fence-wrapping/typo-ing its CoachVerdict** — empirical confirmation of the handoff's "no task-specialised FT as Coach" rule. |
| gpt-oss #1 (pre-fix) | gpt-oss-120b | gemma4-coach | **2/6** | Player output clean; 4 **false** rejects from the gemma4-coach empty-structured-output signature that the fallback didn't catch. Surfaced the bug above. |
| gpt-oss #2 (post-fix) | gpt-oss-120b | gemma4-coach | **6/6** | `fallback_recoveries=1` (index 4 recovered via the non-structured fallback → accept score 5). 0 `llm_failure`. |

**Row validation (gpt-oss #2, all 6):** `layer=behaviour`, `mode=greenfield`, `<think>` present, ProductRoadmap parses, `coverage_score=null`, `source_documents=0` at every level. ProductRoadmap keys exactly match the contract (`project_name, mode, epics, feature_spec_inputs, priority_rationale, constraints_and_dependencies, open_questions, coverage_score, source_documents, assumptions`).

---

## Serving / operational

- **No llama-swap config edit.** gpt-oss-120b + gemma4-coach co-reside via the **existing `autobuild_go` set (`go & gc`)**. Endpoint `:9000`.
- **Keepalive discipline (same as `po_eval`):** requesting gpt-oss-120b evicts the always-on `all` fleet, so the keepalive timer **must be paused first** — `sudo systemctl stop llama-swap-keepalive.timer` (Rich's sudo; no passwordless sudo on GB10) — and re-enabled after, else the 5-min probe revives the fleet on top of gpt-oss → OOM. Note: the timer is **active + enabled** by default (correcting older notes that recorded it inactive).
- `agent-config.yaml` is set to the PO smoke: `domain: product-owner`, `grounded: false`, `limit: 6`, `player: gpt-oss-120b`, `coach: gemma4-coach`.
- `output/` was backed up before each run (`output_backup_pre_po_smoke_*`, `output_backup_po_preflight_qw_*`, `output_backup_po_gptoss_smoke_*`).

## Tests

Full suite **1976 passed** (via `uv run --extra dev pytest`). Added: grounded/ungrounded `create_player_tools` + `build_player_prompt` tests, `GenerationConfig.grounded/limit` tests, and `_extract_coach_content` refusal-classification tests (empty-structured-output vs content-policy vs generic).

## Open items (Phase 2 / bulk run — not Phase-1 gates)

1. **Mode coverage.** The `limit` head-slice draws one category → all `greenfield`. The bulk run must span all six modes (`idea/extract/greenfield/evolve/impact/scope`); the five non-extract modes have no in-distribution seed and depend entirely on book-grounded/generative generation. Drop `limit` (or slice smarter) and rely on the Player mode-coverage guideline.
2. **Decomposition depth.** gpt-oss emitted ~1 epic / 1 feature per example in the smoke — thin for a real roadmap; watch at scale, consider nudging richer decomposition.
3. **Phased `extract` (Phase 2).** `EpicPlan → EnrichmentBatch`, where acceptance criteria and enum-Literal discipline live. Single-pass `ProductRoadmap` (Phase 1) has no AC field.
4. **Knowledge layer.** This smoke produced only behaviour rows (`train.jsonl`); the deferred RAG knowledge layer (`rag_index/knowledge.jsonl`) is generated by knowledge-layer targets in the bulk run.
