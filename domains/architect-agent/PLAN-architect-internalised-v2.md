# Architect v2 — Internalised Architect: Phased Plan

**Date:** 2026-06-23 (restored after an untracked-file wipe; commit this version)
**Decision record:** `CONVERSATION-architect-v2-clean-dataset.md` (same folder).
**Shape:** a near-free serving experiment first (may short-circuit most of the build), then measure, then regenerate-and-retrain only if the experiment says it's needed.

---

## Guiding constraints

- **No books at inference** — the point of the internalised architect.
- **No retraining to stop fabrication** — fabrication is serving-side; the trained prompt and training data are already citation-free. Disabling the injection removes it.
- **Measure before regenerating** — no generation/training cycle until the current model's internalised baseline is known.
- **Player held constant across the A/B** — DeepSeek V4 Flash on both arms, so any books-vs-ungrounded difference attributes to grounding, not Player strength.
- **Single-layer dataset for v2** — behaviour only; the knowledge/RAG layer is dropped.
- **Citation-free, tool-free generation** — v2 completions carry knowledge internalised into reasoning, no `[book_id]`, no tool-call protocol; this is what prevents re-teaching the fabrication.

---

## Phase 0 — Serving experiment on the *current* model (no GPU, hours)

Find out whether the existing fine-tune is already an adequate internalised architect once the citation-demanding injection is removed. Cheapest, highest-information step; gates everything below.

> **Build step (specified & grounded):** `specialist-agent/tasks/backlog/TASK-AIV2-019-disable-rag-injection-internalised-architect.md` — the precise `session.py` guard + `role.yaml` flag, smoke contract, rollback, and observation protocol.

- Gate off the unconditional pre-retrieval on the local path — `specialist-agent/.../orchestrator/session.py:647` (`run_greenfield` → `_pre_retrieve_architecture_knowledge`). Gate the helper on `self._role_config.knowledge_index.enabled` (closes the AIV2-017 gating mismatch); set `knowledge_index.enabled: false` in `roles/architect/role.yaml`. When the helper returns `""`, the injection block in `_build_initial_input` (2384–2402) — extracts *and* the citation mandate — disappears entirely.
- Confirm the local/trained path serves `player_trained.md` (it does, on `--player-model local`) — no prompt change.
- Run greenfield on 2–3 representative scopes. Observe: **(a)** fabrication gone? (expected yes); **(b)** reasoning quality; **(c) structured deliverable intact?** — full Conversation Starter (C4, DDD map, ADR Preferred Directions, assumptions JSON) without `player.md`'s scaffolding?

**Decision gate:**
- Reasoning + structure hold → shippable internalised architect now; books removed entirely; v2 regeneration becomes optional quality work. Skip toward Phase 4.
- Reasoning holds, structure degrades → structure was coming from `player.md`; bake it into the model via v2 (the frozen `player_trained.md` can't supply it). Proceed to Phase 2–3.
- Reasoning weak → v2 quality regeneration needed. Proceed to Phase 2–3.

---

## Phase 1 — Internalised baseline eval (book-free golden set)

Turn the Phase 0 observation into a measured baseline the v2 A/B must beat.

- Build/confirm a **book-free** architect golden set — scopes + rubric scoring quality, **structural completeness**, and **fabrication rate**.
- Score the current model: **with-injection** (current live) vs **no-injection** (internalised). Record the baseline.

> The earlier "three-config always-on RAG" framing is retired — the mechanism is one-shot injection, and the chosen architecture has no inference RAG. Eval is injected-vs-internalised now, v2 candidates later.

---

## Phase 2 — Generative mode in the factory  *(pre-flight: read the code first)*

A second factory mode that generates citation-free, knowledge-dense, single-layer behaviour examples from a taxonomy, no book grounding, DeepSeek V4 Flash as Player.

**Pre-flight (ground the diff — not yet read):** `agentic-dataset-factory/agent.py`, `agent-config.yaml`, `prompts/`, the mode / `rag_retrieval` handling, the architect `GOAL.md` output spec. Detailed build steps written against these. *(Deliberately deferred — its shape depends on Phase 0's structured-output result.)*

- **New mode:** taxonomy walk (the existing `GOAL.md` *Generation Targets* table is the enumeration) instead of `rag_retrieval` over books; Player generates from internalised knowledge.
- **Single-layer output:** behaviour only.
- **Citation-free + tool-free:** no `[book_id]`, no tool-call protocol — matches the trained-prompt regime; prevents re-teaching fabrication.
- **If Phase 0 showed structure degrades:** examples must now produce the full Conversation Starter structure (likely updating the `GOAL.md` output spec **and** re-snapshotting the trained prompt).
- **DeepSeek V4 Flash** served locally across the two GB10s (QSFP) as Player.

---

## Phase 3 — Generation A/B + v2 fine-tunes

Measure books-vs-ungrounded; pick the clean winner.

- Two generation runs, **Player held constant** (DeepSeek V4 Flash): **Option 1** books-grounded (existing extractive mode, new Player); **Option 2** ungrounded (new generative mode). Writing the new mode + re-running extractive yields both arms cheaply.
- Coach-score; fine-tune two single-layer models (Gemma 4 26B-A4B MoE).
- Eval both against the Phase 1 golden set: quality + structural completeness + fabrication rate.
- **Decision:** ungrounded holds up → clean internalised architect, ship it (no books anywhere). Books-grounded wins → measures the gap the later clean-corpus phase must close; ship Option 1 knowingly as interim (synthetic-from-books in the weights — the accepted middle ground), or iterate.
- Hardware: one arm per GB10, or DeepSeek sharded across both.

---

## Phase 4 — Ship the internalised architect

- Deploy the winning fine-tune with the injection disabled and the clean serving prompt. No inference RAG, no books.
- Reconcile serving: greenfield no longer pre-retrieves; `player.md`'s citation/tool regime retired (or `player.md` reframed/removed) for the local path; `knowledge_index.enabled: false`.
- Close TASK-AIV2-017 / AIV2-018 — the injection MVP is **superseded**, not hardened (TASK-AIV2-019 supersedes them).

---

## Phase 5 *(later)* — Grounded architect + capture flywheel

- When a clean corpus + captured own-data exist: build the grounded architect (real tool-use, **execution-grounded** training — not SFT-on-traces) over the clean corpus, with honest citations.
- Stand up capture of **validated-and-edited** `/system-arch` / ADR / C4 outputs (the human-edit delta is the gold) → the flywheel that internalises more competence into each successive fine-tune.

---

## What falls out (deferred, not lost)

- **Clean external corpus + own-outputs** → a *training-time* input (grounding v2 generation, and the Phase 5 flywheel), **not** an inference RAG.
- **Inference RAG, grounded tool-use, citations** → Phase 5.

---

*Restored 2026-06-23 from conversation after a `git clean` removed the uncommitted original. Commit this file. Evidence: `specialist-agent/docs/evidence/architect-rag-wireup-2026-06-23.md`, `chroma-corpus-provenance-2026-06-23.md`.*
