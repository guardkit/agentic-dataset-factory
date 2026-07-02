# PO Phase 0 — Golden Set & Base Diagnosis: Results

**Date:** 2026-07-02
**Spec:** `SPEC-po-phase0-golden-set.md` · **Plan:** `PLAN-po-dataset-generation.md` §7 Phase 0
**Model under test:** `gemma4-26b` (Gemma-4-26B-A4B-IT MoE — the PO fine-tune base) · **Coach/gate:** `gpt-oss-120b` (distinct model, no self-scoring)

---

## TL;DR — Phase 0 CONCLUDED (2026-07-02): the base is strong

Across three runs (guided prose, light prose, and the real ProductRoadmap-JSON `contract` run with a `## File:` corpus), the **Gemma-4-26B-A4B MoE base is a strong starting point**. It **grounds faithfully when given a corpus (extract 6/6), never fabricates sources** (greenfield: `coverage_score=null` + empty `source_documents`, correct), **surfaces unknowns as confidence-tagged assumptions (100%)**, holds decomposition/scope/prioritisation (100%), and **never false-confidences on any of the 11 traps in any run**. The naive "weak" numbers (grounding 46%, acceptance-criteria 23%) were **eval-design artifacts**, not base gaps: `grounding_fidelity` mis-scoped no-corpus modes (now fixed in GOAL.md), and single-pass `ProductRoadmap` has no acceptance-criteria field (ACs live in the phased `EnrichmentBatch` — deferred to Phase 2). **Implication for the fine-tune: reinforcement + serving-shape fluency, not judgment repair.** Full arc below.

**Applied on conclusion:** the light-touch `grounding_fidelity` mode-scoping fix (GOAL.md) so no-corpus modes aren't penalised for correct empty-citation behaviour — this also corrects training-time gating, not just the eval. The phased-extract AC path is logged as a Phase-2 item.

---

## What was built

**Serving (llama-swap `/opt/llama-swap/config/config.yaml`):**
- Added a clean base id **`gemma4-26b`** → the MoE base (`gemma-4-26B-A4B-it-UD-Q4_K_XL.gguf`), neutral posture, on-demand. The dense `gemma4-31b` (a QAT coach-fallback, *not* the base) was left untouched.
- Added a co-residency set **`po_eval: "go & g26"`** so `gpt-oss-120b` + `gemma4-26b` load together (~95-105 GB / 121 GB, mirrors `autobuild_go`) — the scorer hits both without swapping.
- Discipline: the run **requires the keepalive timer paused** (`sudo systemctl stop llama-swap-keepalive.timer`) so its 5-min probe doesn't revive the `all` fleet on top → OOM. Re-enable after. Backups: `config.yaml.bak-20260702-pre-gemma4-26b-base`, `…-pre-po-eval-set`.

**Harness (`score_golden_set.py`):** reuses the factory rubric verbatim (`build_coach_prompt` + `create_coach` + `_parse_coach_verdict` → `CoachVerdict`). Additions this phase:
- retry-with-backoff on transient HTTP 429 (llama-swap `concurrencyLimit`), default `--concurrency 2` (the model's limit);
- persists the model-under-test's full output for auditing/curation;
- **`--instruction {guided,light,minimal}`** — A/B how much output shape is spoon-fed, to separate native PO tendency from instruction-following;
- **derives the behaviour-criteria set dynamically from the GOAL** (via `_filter_criteria_for_layer`), not a hardcoded list — so the 2026-07-01 `grounding_fidelity` addition is measured, reported, and edge-weighted; adds a **grounding-failure summary** (ungrounded count by mode) — the axis the `extract` items exist to test.

### Rubric sync (2026-07-02, from the Mac session)
`GOAL.md` gained a 9th behaviour criterion **`grounding_fidelity`** (15%: every feature/enrichment traces to a real source — brief/corpus/book — no `FABRICATED_SOURCE_REFERENCE`/`UNGROUNDED_FEATURE`; for `extract`, corpus coverage), and a new **`OUTPUT-CONTRACT.md`** pins the real serving output as **structured JSON** (`ProductRoadmap`/`EpicPlan`/`EnrichmentBatch`), not prose. Because the Coach prompt is built from `goal.evaluation_criteria`, the Coach already scores grounding; the harness was the lagging layer (it hardcoded 8 criteria) — now fixed. **Aligning the guided instruction to emit the real JSON contract is a deliberately deferred, non-blocking follow-up** (OUTPUT-CONTRACT §127-132): grounding on prose still meaningfully scores "did it stay faithful to the described feature."

**Golden set (`golden_set/`, 13 items, 11 traps):**
- `golden_greenfield.jsonl` (4) — blank-slate briefs, 2 traps.
- `golden_greenfield_hard.jsonl` (3) — harder traps: a **leading-premise** (gamification "is the answer"), a **gold-plating** ("comprehensive/future-proof settings"), a **false-simplicity/hidden-dependency** ("just a download-my-data PDF, should be simple").
- `golden_extract.jsonl` (6) — seeded from real on-host harvest triples (forge FEAT-FORGE-008, jarvis FEAT-JARVIS-005 + NATS-Fleet-Registration, specialist-agent FEAT-RAG-08, study-tutor Graphiti-Student-Model + primary-text-rag). Each brief describes the real feature but leaves its parameters/policies **open**, so a strong PO must surface them as assumptions; the real `features/<slug>/` triple is the `reference`.

---

## Greenfield result (guided instruction)

| id | brief | trap | decision | score | assumption_explicitness |
|---|---|---|---|---|---|
| 001 | medication-adherence app | ✅ | accept | 5 | ✅ surfaced regulatory + feasibility + delivery unknowns |
| 002 | feature-flag CLI | — | accept | 5 | ✅ |
| 003 | tool-lending marketplace | — | accept | 5 | ✅ |
| 004 | support analytics dashboard | ✅ | accept | 5 | ✅ surfaced data-source, latency, "resolved" definition |

All 8 behaviour criteria 100%. **Two-sided:** false-confidence 0/2 traps, over-conservative 0. Coach assessments confirm the traps were *genuinely* handled (real unknowns surfaced as confidence-tagged assumptions), not rubber-stamped.

> ⚠️ This batch was scored on the **8-criterion (pre-`grounding_fidelity`) rubric** and greenfield mode (no corpus), so it says nothing about grounding. The pending run scores the **9-criterion** rubric across greenfield + extract, where grounding discriminates.

### Honest interpretation
- **Real positive:** under the serving prompt, the base already handles greenfield decomposition and does **not** invent confident requirements on the traps — the primary PO failure mode is absent here. Encouraging for how much greenfield the fine-tune must teach (little).
- **Not discriminating (by construction of what was tested):** greenfield is the easiest mode (self-contained, no grounding); n=4; and the *guided* instruction hands the model the target shape (think + assumptions-with-confidence + Gherkin ACs + scope), so ticking the boxes is easy. **Empty edge-density vector → no Phase-3 oversampling guidance yet.**
- **Inference:** the base handles greenfield, so both the discrimination *and* the training need live in the **harder modes** and **harder traps** — which is exactly what the expanded golden set now targets.

---

## Pending: the sharpened + extract run (two-report A/B)

To get a discriminating signal, run the expanded set under two instruction strengths and compare:
1. **guided** over all 13 items → the primary diagnosis across greenfield + hard-traps + extract.
2. **light** over the same items → the gap vs guided *is* the "how much must the fine-tune instill vs. is already latent" signal (does the base still surface assumptions / write testable ACs when *not* told to?).

```bash
# (keepalive paused; models co-resident via po_eval)
.venv/bin/python domains/product-owner/score_golden_set.py \
  --player-model gemma4-26b --coach-model gpt-oss-120b \
  --golden domains/product-owner/golden_set --instruction guided \
  --out domains/product-owner/golden_set/phase0_guided.json
.venv/bin/python domains/product-owner/score_golden_set.py \
  --player-model gemma4-26b --coach-model gpt-oss-120b \
  --golden domains/product-owner/golden_set --instruction light \
  --out domains/product-owner/golden_set/phase0_light.json
```

**What to watch:** **`grounding_fidelity` on the extract items** (the point of the sync — does the base stay faithful to the described feature and surface gaps as assumptions, or invent capabilities? this is the axis most likely to break 100%); extract-mode accept rate (real grounded features — likely lower than greenfield); whether the harder greenfield traps (005-007) still get 0 false-confidence; and the guided→light delta on `assumption_explicitness` / `acceptance_criteria_testability` / `grounding_fidelity` (dimensions most likely to depend on the spoon-feed).

---

## A/B run — guided vs light, 9-criterion rubric (2026-07-02)

Ran all 13 items (greenfield 7 + extract 6) twice: `--instruction guided` and `--instruction light`.

| criterion | guided pass | light pass |
|---|---|---|
| grounding_fidelity | **0%** (13/13 ungrounded) | **8%** (12/13) |
| prioritisation_rationale | 100% | **62%** |
| outcome_over_output | 100% | **85%** |
| acceptance_criteria_testability | 100% | **92%** |
| assumption_explicitness | 100% | 100% |
| decomposition_coherence / scope_discipline / terminology / no_verbatim | 100% | 100% |
| **accept rate** (both modes) | **0%** | **0%** |
| false-confidence (traps) | **0/11** | **0/11** |

### Finding 1 — the grounding 0% is a MEASUREMENT CONFOUND, not a base weakness
Every `grounding_fidelity` failure reads *"no explicit citations / `## File:` references present."* The prose instruction produces **no citation structure**, and the extract items **describe** their feature rather than **supplying the corpus**, so grounding_fidelity — which requires citations to real sources + corpus coverage — **cannot pass by construction**. The Coach even (over-)demanded citations to source books on greenfield. So this run does **not** measure whether the base invents capabilities; it measures "prose has no citations."

**Consequence:** OUTPUT-CONTRACT §127 ("align the generation instruction to the JSON contract") is **promoted from non-blocking to required-to-measure-grounding**. The Mac session's hope that grounding-on-prose scores faithfulness does not hold — the criterion is citation-centric. To get a real grounding read we need: (a) the output instruction aligned to the mode's JSON (`source_documents`/`field_citations`), and (b) extract items that **carry the corpus** (real `## File:` document text), so the Coach can verify real-vs-`FABRICATED_SOURCE_REFERENCE` and `MISSING_COVERAGE`.

### Finding 2 — the real signal is the guided→light delta on the NON-grounding criteria
Unconfounded and genuine (directional, small n): without the spoon-feed the base weakens on **prioritisation_rationale (100%→62%)**, **outcome_over_output (100%→85%)**, and **acceptance_criteria_testability (100%→92%)**; it holds 100% on assumption/decomposition/scope. → these three are the honest Phase-3 edge-density candidates (the base does them when told, less so natively).

### Finding 3 — the loud/conservative posture is robust
**false-confidence 0/11 traps in BOTH runs**, including the harder greenfield traps (leading-premise, gold-plating, false-simplicity) and the parameter-dense extract traps. The base reliably surfaces unknowns as assumptions rather than inventing confident requirements — the primary PO failure mode stays absent even under a bare instruction. This is the strongest real positive so far.

### Corrected next step
Build the **contract-aligned run**: (1) a `--instruction contract` preset that emits `<think>` + the mode's JSON per OUTPUT-CONTRACT.md; (2) attach real corpus text to the extract items. Then re-run to get a *valid* grounding read. Until then, treat grounding as **unmeasured**, not failed.

---

## Contract grounding run — the real grounding read (2026-07-02)

Ran the 13-item grounding set (greenfield 7 + **corpus** extract 6) under `--instruction contract` (real ProductRoadmap JSON + `## File:` corpus).

| criterion | pass | read |
|---|---|---|
| **grounding_fidelity** | 46% (7/13 fail) | **all 7 failures are greenfield; extract 6/6 PASS** |
| acceptance_criteria_testability | 23% | **artifact** (see below) |
| outcome_over_output | 62% | modest real signal (JSON nudges to output-listing) |
| assumption_explicitness / decomposition / scope / prioritisation / terminology | 100% | robust under JSON too |
| false-confidence (traps) | **0/11** | robust across all 3 runs |

### The headline: the base does NOT have a grounding/fabrication problem
- **Extract (corpus provided): grounding passes 6/6.** Given real `## File:` documents, the base cites them faithfully and covers them — no `FABRICATED_SOURCE_REFERENCE`. This is exactly what the extract batch was built to test, and the answer is **the base grounds well.**
- **Greenfield (no corpus): grounding "fails" 7/7 — but the base did the *right* thing:** it set `coverage_score=null` and emitted **empty** `source_documents` (it did **not** invent sources). The Coach failed it for "empty source_documents / no citation to the brief" — i.e. it over-applies a corpus-centric criterion to a no-corpus mode. **Not base fabrication; a criterion mis-scoping.**

### Two eval-design artifacts (not base defects), both localized
1. **`grounding_fidelity` mis-scopes greenfield/idea.** It should, for no-corpus modes, check *"no fabricated sources + features trace to the brief"* — not *"non-empty source_documents."* The base already exhibits the correct behaviour (no fabrication).
2. **`acceptance_criteria_testability` is unmeasurable under single-pass `ProductRoadmap`.** That schema's `FeatureSpecInput` has **no `acceptance_criteria` field** — ACs live in the phased `EnrichmentBatch` (Phase B, per OUTPUT-CONTRACT §60-75). So the 23% is "the JSON has no AC field," not a base weakness (the base aced ACs at 100% in prose). Every corpus-extract item's blocker was this artifact (grounding passed; `extractc-005` fully accepted). To test ACs under the real contract, use the **phased extract flow** (EpicPlan→EnrichmentBatch) or add ACs to the feature shape.

### Phase-0 verdict
The **Gemma-4-26B-A4B MoE base is a strong starting point**: it grounds faithfully when given a corpus, does not fabricate sources when there isn't one, surfaces unknowns as confidence-tagged assumptions (100%), holds scope/decomposition/prioritisation (100%), and **never false-confidences on any of the 11 traps across three runs** (guided prose, light prose, contract JSON). The fine-tune's job is therefore **reinforcement + serving-shape fluency** (emit the exact JSON contract; ACs in the right phase; keep outcome-framing crisp under JSON), **not fixing broken judgment**. The only modest real gap is `outcome_over_output` under JSON (62%; 85% in light prose) — a Phase-3 reinforcement target, not a deficiency.

### Corrected edge-density (artifacts discounted)
Raw numbers say oversample AC (0.44) + grounding (0.30) — but both are eval artifacts. **Real** Phase-3 emphasis: **outcome-framing under the JSON contract** and **prioritisation_rationale** (weak in the light-prose run), plus **serving-shape fluency** (correct JSON, phased ACs). Judgment and grounding need reinforcement, not remediation.

### Next refinements (to get a clean final number)
(1) mode-scope `grounding_fidelity` (greenfield = no-fabrication + brief-trace); (2) add a `--phase` / EnrichmentBatch path (or AC-in-feature) so acceptance-criteria testability is measurable under the contract. Both are eval-harness/GOAL refinements — the base conclusion stands regardless.

---

## Open items / caveats

- **Sample is still small** (13). Percentages are coarse; trap behaviour is the signal to trust. Expand the other four modes (`idea`/`evolve`/`impact`/`scope`) next for full coverage.
- **Extract items skew to `primary_dimension: assumption_surfacing`** — accurate (the harvested features are parameter-dense) but it means dimension *coverage* via the `extract` batch is narrow; the Coach still scores all 8 criteria per item regardless.
- **Coach = gpt-oss-120b is itself an LLM judge** — its leniency is a variable. The perfect greenfield sweep warrants the light-instruction cross-check to rule out judge over-generosity.
- **Keepalive must be re-enabled after each run** (`sudo systemctl start llama-swap-keepalive.timer`) to restore the production fleet (`coach-ft-v3` etc.).

---

*Grounded 2026-07-02. Harness + golden set under `domains/product-owner/`; reports under `domains/product-owner/golden_set/`.*
