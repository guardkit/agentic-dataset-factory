# Product-Owner Dataset Generation — Build Plan

**Date:** 2026-07-02
**Companion:** `GOAL.md` (same folder), `../architect-agent/PLAN-architect-internalised-v2.md` (the generative-mode strategy this reuses), `../coach-agent/` (the strong-model + teacher-gate template).
**Shape:** measure the current model cheaply first, then add a no-book "generative" mode to the *existing* factory, lift the harvest into training shape, bulk-generate + Coach-gate across all six modes, assemble, fine-tune, gate on a balanced held-out eval.

---

## 1. Situation — three generation mechanisms, and why PO needs the third

We already have two working ways to manufacture a fine-tune dataset:

1. **The factory's extractive book-RAG loop** (`agentic-dataset-factory`). A Player walks the GOAL.md *Generation Targets* taxonomy; the orchestrator pre-retrieves book chunks from ChromaDB and injects them; a layer-aware Coach grades each example against a GOAL-derived rubric; accepted rows are written to `train.jsonl`/`knowledge.jsonl`. This built the architect and GCSE-tutor datasets.
2. **The coach v3 workflow** (`domains/coach-agent/wf_gen_v3_train.js → wf_teacher_verdict_v3.js → build_v3_sft.py`). A deterministic scaffold fixes the label and flaw placement; a strong model (Opus) writes only the realistic *wrapper*; two independent gates (a mechanical guard-checker **and** teacher-agreement) admit a row to SFT. Result: rubber-stamp **94% → 0% false-approval**.

PO needs a **third** thing that borrows from both: the factory's loop + Coach + output-routing (mechanism 1), driven by a **strong Player with no book grounding** and gated by a **strong, independent Coach** (the transferable idea from mechanism 2), with the **91-record harvest woven in as `extract`-mode seed**.

**Key distinction that shapes everything below:** the coach fine-tune is a **judge** (binary approve/feedback), so its matched-pairs / deterministic-gold machinery teaches a *decision boundary*. **PO is a *generator*** — it produces decompositions. So the coach's deterministic-gold + matched-pair scaffolding **does not transfer**; what transfers is the *discipline* (strong generator → strong independent verifier → gate → weight → SFT → **balanced two-sided** eval). This is why the right home for PO is the factory loop, not a standalone coach-style workflow.

**Grounding note (2026-07-02):** the POHARVEST corpus is now materialized on this GB10 — `~/po-dataset/` (`po_history_records.jsonl` = 91 records, `MANIFEST.md`, `README.md`), harvester at `specialist-agent/scripts/harvest_po_dataset.py`, task in `specialist-agent/tasks/completed/`. DeepSeek V4 Flash, by contrast, is **not** served anywhere (see §4).

---

## 2. The reusable recipe (coach v3 abstracted → PO)

| Coach v3 stage | What it was | PO equivalent |
|---|---|---|
| ① Deterministic case plan (label + flaw placement, edge-dense toward base misses, disjoint from holdout) | `wf_gen_v3_train.js` | **Taxonomy walk** over GOAL.md *Generation Targets* (9 dimensions × 6 modes) + a **Phase-0 base-error weighting** (over-sample the dimensions the current model is weakest on). No labels — PO is generative. |
| ② Strong model writes only the wrapper (never the label) | Opus, schema-constrained | **Strong Player** writes the full example (`<think>` + decomposition) from internalised PM knowledge. |
| ③ Deterministic matched-pair assembly, rendered through the **production prompt builder** (train==serve) | `assemble_step0_synthetic.py` | **N/A for a generator** (no clean/flaw pairs). The train==serve lever survives as: system prompt = the verbatim PO system prompt; assistant shape = the real serving contract (§5). |
| ④ Mechanical gold-consistency gate | `guards_tripped()` | **N/A** (no deterministic gold). Replaced by the structural validators (ProductRoadmap invariants, think-block presence). |
| ⑤ Strong-model teacher gate — keep row only if teacher agrees | `build_v3_sft.py:96-98` | **Factory Coach** accept/revise on the GOAL rubric. **Collusion fix:** Coach must be a *different model* from the Player (today both are `qwen36-workhorse` — that's a rubber-stamp risk). |
| ⑥ Balance by construction + mild up-weight | `WEIGHT`, `round(weight)` oversample | Balance **mode + dimension** coverage by construction; up-weight the 22 paired harvest triples, down-weight unpaired rubber-stamp + late-May drift. |
| ⑦ SFT staging gates (template-token leak, holdout overlap, seq-len, schema) | `prepare_coach_sft.py` | Reuse the same class of gates on the PO corpus. |
| ⑧ Gate on a **balanced two-sided** holdout | RESULTS-coach-v3.md | PO Phase-1 golden set: never gate on aggregate score alone; require the loud/conservative failure posture (assumption-surfacing) to hold. |

**Load-bearing lessons that DO transfer:** (a) *fix the input, not the model* — render training prompts the way production actually serves them; (b) the verifier must be **independent of the generator** or you get a rubber-stamp; (c) **edge-dense toward measured misses** is what made a small corpus move the needle — so a Phase-0 baseline measurement is worth its cost; (d) evaluate with a **balanced, two-sided** metric.

---

## 3. Recommended build: add a "generative" mode to the *existing* factory (Option A)

**Recommendation: Option A — a no-book generative branch inside `agentic-dataset-factory`, not a standalone workflow (Option B).** The factory *already* has everything the coach workflow had to build by hand: the taxonomy walk, a GOAL-derived layer-aware Coach, layer routing, orchestrator-gated writes, checkpoint/resume, and — crucially — `domains/product-owner/GOAL.md` is **already authored for it**. The book grounding is a bolt-on, not the spine.

### Why it's low-effort (verified against the code)

- **The taxonomy walk already exists.** `agent.py:234` drives `run_generation_loop(targets=goal.generation_targets, …)` straight off the *Generation Targets* table (parsed by `domain_config/parser.py:427`, expanded per `count` at `generation_loop.py:1264`). No new enumerator.
- **The loop already tolerates no grounding.** `generation_loop.py:673` guards `if rag_tool is not None:` and `:1182` guards `if rag_context:` — pass `rag_tool=None` and the "Curriculum Context" injection block simply vanishes. `agent.py:156` already computes `rag_tool = tools[0] if tools else None`.
- **Player and Coach are independent config blocks.** `agent-config.yaml` has separate `player:` / `coach:` blocks; `model_factory.py` maps `provider: local` → OpenAI `base_url=endpoint`. A strong Player on a different endpoint while the Coach stays on `:9000` is a **config edit**, no code change.
- **The whole second half is RAG-agnostic and stays byte-for-byte identical:** format gate, Coach evaluate, verdict parse, layer routing to `train.jsonl`/`rag_index/knowledge.jsonl`, orchestrator-gated write, checkpoint/lock (`generation_loop.py:706-1139`, `write_output.py:35-38`).

### The only new code (the seams)

1. **`src/tools/tool_factory.py::create_player_tools`** — today hard-codes the Player's tool list to exactly `[rag_retrieval]`. Add a `grounded: bool` param; return `[]` when `grounded=False`.
2. **`agent.py`** — Step 5 `verify_chromadb_collection(config.domain)` hard-fails for a domain with no collection; **skip it when ungrounded**. Step 9 call becomes `create_player_tools(collection_name=config.domain, grounded=grounded)`.
3. **`config/models.py` + `agent-config.yaml`** — add one flag, `generation.grounded: bool` (default `true` so architect/tutor are unchanged); set `false` for PO.
4. **`prompts/player_prompts.py`** — when ungrounded, omit the rag_retrieval/citation usage guidance so the Player isn't told to use a tool it doesn't have (this is the same "citation-free, tool-free" discipline the architect-v2 plan mandates, which prevents teaching fabrication).

That is the entire mode. Everything else is `domain: product-owner` + the `player`/`coach` model choices.

> **Option B (standalone coach-style workflow) is rejected:** it would re-implement the taxonomy walk, the Coach rubric, layer routing, output writing, and resume that the factory already provides — and PO, being a generator, doesn't need the deterministic-evidence machinery that justified a standalone workflow for the coach.

---

## 4. Two decisions to lock before bulk generation

### Decision A — the drop-in output shape ✅ DECIDED (2026-07-02): `<think>` + fenced ProductRoadmap JSON

GOAL.md §Output Schema shows the assistant content as `<think>` + **markdown prose**. But the real serving slot — `specialist-agent/roles/product-owner` `ProductOwnerOutputHandler.parse()` — validates a **ProductRoadmap JSON** object (≥1 epic; each epic ≥1 feature; `feature_spec_inputs` flattened-match by `feature_id`; description ≥2 sentences; strict `priority/moscow/value/complexity` Literals; `greenfield` ⇒ `coverage_score=null`). A think-prefixed *bare* JSON will not parse.

**Decided: `<think>…</think>` + a ```json-fenced ProductRoadmap object.** This satisfies the mandatory think-block **and** the handler's fenced-JSON extraction path (`handler._extract_json` strategy 2), and keeps `gemma-4` (not `gemma-4-thinking`) so the think block stays in content. **Consequent work:** tighten GOAL.md's §Output Schema to emit fenced ProductRoadmap JSON (not free prose); pin the exact `feature_spec_inputs/<id>.md` legacy-vs-enriched layout (`handler.py:339-529`) at authoring time; make sure the factory's format gate accepts think + fenced-JSON.

### Decision B — the strong Player identity ✅ DECIDED (2026-07-02): `gpt-oss-120b` one-box; Coach on a different model

DeepSeek V4 Flash (named in the architect-v2 plan) is **not served**: absent from the live `:9000` model list, and the two-Spark TP=2 bring-up is an **unexecuted draft** that would take the *entire* `:9000` fleet down on both boxes for the run (including the Coach) under the DF-004 memory rule.

**Decided: `gpt-oss-120b` one-box as the Player** (operator-recommended default teacher), **with the Coach on a *different* model** (e.g. `qwen36-workhorse` or a coach-class model) to break Player==Coach collusion. It's served on-demand today, Player+Coach co-reside under the one-box ceiling, and it honors DF-001 (a bounded, attended, one-time manufacturing run — the Player is disposable; only the distilled Gemma-4 SLM ships). *Fallback:* `qwen36-workhorse` (served now, but do **not** also use it as the Coach). *Upgrade path (deferred):* DeepSeek V4 Flash only if a Phase-0/1 measurement proves teacher quality is the bottleneck — and only after the two-Spark bring-up is actually executed.

---

## 5. PO generation plan (what the strong Player produces)

- **Volume/coverage:** the GOAL.md *Generation Targets* — 1,050 book-grounded examples across 9 dimension categories, 100% `<think>` (reasoning), behaviour-heavy (~76/24). **Deliberately span all six modes** (`idea/extract/greenfield/evolve/impact/scope`) — the harvest seeds only `extract`, so the other five have **zero** in-distribution seed and depend entirely on generation. Vary the *user* message framing per mode (idea=hypothesis; greenfield=problem statement; extract=doc corpus; evolve=docs+build-plan; impact=docs+roadmap+new-info; scope=roadmap+constraint) and set `metadata.mode` to match.
- **Envelope:** `messages` (system = verbatim PO system prompt) + fixed `metadata` enums (`layer/type/dimension/mode/source_books/topic/source/turns`).
- **Mandatory think block:** every assistant message opens with `<think>` that *reasons* (outcome pursued, unknowns→assumptions, in/out scope, sequencing) — missing/empty ⇒ the factory Coach's `type_correct` gate auto-revises (score 1). This is the exact mechanism `prompts/coach_prompts.py:70` enforces.
- **Serving-contract shape:** per Decision A.
- **Multi-turn ≥15%:** brief → partial decomposition + a clarifying question / assumption challenge → refine → deepen (`turns≥2`).
- **No verbatim:** never >15 consecutive words from a source PDF (established terms exempt).
- **The Coach gate:** the factory Coach uses the **GOAL rubric** (`outcome_over_output`, `decomposition_coherence`, `acceptance_criteria_testability`, `assumption_explicitness`, `scope_discipline`, `prioritisation_rationale`, `terminology_correct`, `no_verbatim_reproduction`) with the think-block pre-check. Accept ⇔ `decision==accept ∧ score≥3 ∧ layer_correct ∧ type_correct ∧ no blocking issues`. **This is a different rubric from the runtime serving Coach** (`criteria/definitions.yaml`: coverage/grounding/feature_spec_readiness/dependency/scope, pass 0.6) — the factory rubric decides which *training rows* survive; the runtime rubric decides live output. Both matter; don't conflate them.

---

## 6. Weaving in the harvest (the moat: harvest-don't-author)

The 91 records are **raw** and carry **no think block** and **no curation-judgment signal** (0/31 `considered`; every session rubber-stamped). Use them as **`extract`-mode SFT seed**, not preference data (no DPO).

**Transformation (RAW record → training row) — reuse the strong Player as a "reasoning-reconstructor," analogous to coach's "LLM writes only the wrapper":**
- **User message:** the extract-mode input the session decomposed (feature brief / source spec from `command_invocation` + context).
- **Assistant message:** the **real** decomposition — reconstructed from `proposal_groups` + `why_rationales` + `assumptions[{text,confidence,basis,human_response}]` + the paired `features/<slug>/{.feature,_assumptions.yaml,_summary.md}` triple — with a **`<think>` block synthesised by the strong Player conditioned on those real artifacts** (grounded reconstruction, not free invention — low fabrication risk because the *answer* is real; only the reasoning is reconstructed). Coach-gate exactly like a generated row.
- **Metadata/weighting:** `mode=extract`, `layer=behaviour`. **Add a `source` enum value `harvest`** (GOAL.md currently allows only `synthetic`) so the trainer can weight the seed. **Weights:** the **22 paired triples** = higher (real, in-distribution, real outputs); **unpaired rubber-stamp** = lower (weak positive, self-distillation risk); **down-weight late-May** drift via `curation_richness` + `date`; `partial` (12) = reference only, exclude from training.
- **Volume framing:** bulk still comes from the books; the harvest is the in-distribution `extract` reinforcement + the real-domain output-shape anchor (forge/jarvis/study-tutor/specialist-agent).

---

## 7. Phased sequence (cheapest-highest-information first)

**Phase 0 — Golden set + base diagnosis (no GPU beyond serving, ~½–1 day).** *Full spec: `SPEC-po-phase0-golden-set.md`.* Unlike the architect's Phase 0, this is **not** a short-circuit (there is no PO fine-tune to measure) — its value is the two assets the build needs regardless: (1) the **book-free PO golden set** — the Phase-4 eval asset you can't ship without; (2) a **base-model dimension diagnosis** that edge-weights Phase 3. Key efficiency: **you don't need the generative Player mode to run Phase 0** — the factory **Coach already runs and is RAG-agnostic**, so a ~60-line `score_golden_set.py` reuses `load_config`/`parse_goal_md`/`build_coach_prompt`/`create_coach`/`_parse_coach_verdict` to score the base model with the *same* rubric harness you'll gate training with. **Seed the golden set** from the **22 on-host harvest triples** (real `extract` briefs+outputs) + authored briefs for the 5 unseeded modes + **assumption-posture traps** (the loud/conservative test), with the **GPT-5.5** sessions as the upper-bound baseline. Track a **two-sided** metric (false-confidence vs over-conservative), not an aggregate score.

> **✅ Phase 0 CONCLUDED (2026-07-02) — see `RESULTS-po-phase0.md`.** Verdict: the base is **strong** — grounds faithfully with a corpus (extract 6/6), never fabricates sources, surfaces assumptions (100%), holds scope/decomposition/prioritisation (100%), and never false-confidences on any of the 11 traps across three runs (guided prose, light prose, contract JSON). The "weak" grounding/AC numbers were **eval artifacts**: `grounding_fidelity` mis-scoped no-corpus modes (**now fixed in GOAL.md**), and single-pass `ProductRoadmap` has no acceptance-criteria field (see Phase 2). **This flips the fine-tune emphasis from teaching judgment to reinforcement + serving-shape fluency.** Corrected Phase-3 edge-density: `outcome_over_output` under JSON + `prioritisation_rationale` + serving-shape, **not** the (already-strong) judgment criteria.

**Phase 1 — Wire the factory generative mode + smoke-test the contract.** Implement the four seams (§3); set `domain: product-owner`, `generation.grounded: false`, `player`=`gpt-oss-120b` (Decision B), `coach`=different model. Smoke-test 5–10 examples across 2–3 modes; **this is where the think + fenced-ProductRoadmap-JSON contract (Decision A) gets de-risked** — confirm the no-RAG path, the think-block `type_correct` gate, and handler-parseable JSON all work end-to-end. Runs right after Phase 0 because Phase 0 by design doesn't touch this serving-contract risk.

**Phase 2 — Lift the harvest.** Run the reconstruction transformation (§6) over the 31 `extract` records (22 paired first); Coach-gate; write to `train.jsonl` tagged `source=harvest`. **Also here (Phase-0 finding):** cover the **phased `extract` flow** — `EpicPlan` Phase A (stubs + `cited_docs` + `source_citations`) → `EnrichmentBatch` Phase B (`acceptance_criteria`, enum Literals, `field_citations`) — since acceptance criteria live in Phase B, not the single-pass `ProductRoadmap`. This is what makes `acceptance_criteria_testability` measurable/trainable under the real contract.

**Phase 3 — Bulk generate + gate.** Walk the full taxonomy (1,050, six modes), **edge-dense per the Phase-0 verdict — toward `outcome_over_output` under JSON, `prioritisation_rationale`, and serving-shape fluency (correct ProductRoadmap/EnrichmentBatch JSON, phased ACs), NOT the already-strong judgment criteria** (assumptions/scope/decomposition/no-fabrication). Because a big/cross-node Player is time-shared with the fleet, **batch it**: bulk-generate → (swap models once if needed) → bulk-Coach-gate, not per-item swaps. Assemble with the SFT staging gates (§2⑦) + the harvest weighting (§6).

**Phase 4 — Fine-tune + gate.** Unsloth QLoRA on Gemma-4-26B-A4B MoE (`gemma-4` template). **Gate on the Phase-1 golden set with a balanced, two-sided metric** — the fine-tune must hold the loud/conservative assumption posture, not just score well on average.

**Phase 5 (later) — Capture flywheel.** Stand up capture of *validated-and-edited* PO outputs (the human-edit delta is the gold the harvest lacked) → future `considered`-quality preference data (then DPO becomes possible).

---

## 8. Risks & open questions

- **Player==Coach collusion.** The single biggest quality trap (it's what rubber-stamped coach v1/v2). Enforce Player ≠ Coach model. *(Decided in §4B.)*
- **Harvest think-block self-distillation.** Reconstructing reasoning over AI-authored, rubber-stamped proposals. Mitigated by grounding the reconstruction in the *real* paired outputs + Coach-gating + low weight, but it is not human-judgment signal — don't overweight it.
- **The JSON/markdown mismatch (Decision A)** must be resolved before generation or every row is mis-shaped.
- **Runtime-Coach grounding behaviours can't be exercised at train time** — book-generated examples have no `## Actual Product Docs` manifest, so citation/coverage discipline the serving Coach enforces is under-trained. Track it; the harvest's real paired outputs partially cover it.
- **`extract` has phased sub-shapes** (EpicPlan / EnrichmentBatch / ProductNFRs) with their own schemas — GOAL targets only the full ProductRoadmap; decide whether the phased shapes need coverage.
- **DeepSeek serving is a paper prerequisite** (unexecuted two-Spark draft, drains the fleet). Don't block the dataset on it — ship with `gpt-oss-120b`/`qwen36-workhorse` and treat DeepSeek as a gated upgrade.
- **Metadata `source` enum** needs a `harvest` value; behaviour criterion weights in GOAL sum >100% but are advisory (the Coach gates on boolean `criteria_met` + score, not the weighted composite) — don't assume weighted-composite gating.

---

*Grounded 2026-07-02 against the factory code (agent.py, generation_loop.py, tool_factory.py, domain_config/parser.py), the coach v3 pipeline, the product-owner role in specialist-agent, and the two-Spark serving docs. Evidence: workflow `wf_e7d4db73-789` subsystem maps.*
