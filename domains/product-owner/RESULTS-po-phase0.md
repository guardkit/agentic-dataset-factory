# PO Phase 0 — Golden Set & Base Diagnosis: Results

**Date:** 2026-07-02
**Spec:** `SPEC-po-phase0-golden-set.md` · **Plan:** `PLAN-po-dataset-generation.md` §7 Phase 0
**Model under test:** `gemma4-26b` (Gemma-4-26B-A4B-IT MoE — the PO fine-tune base) · **Coach/gate:** `gpt-oss-120b` (distinct model, no self-scoring)

---

## TL;DR

The Phase-0 harness runs end-to-end against the real MoE base + an independent Coach, co-resident (no per-item model swap). The **first batch (greenfield, 4 items) came back 4/4 accept, score 5, both assumption-traps genuinely handled** — a real positive (the base does greenfield PO decomposition well and holds the loud/conservative posture), **but a perfect sweep is non-discriminating**: greenfield is the easiest mode, the sample is tiny, and the guided prompt spoon-feeds the rubric shape. So the edge-density vector is empty and gives no Phase-3 guidance yet. The response was to **sharpen the probe** (guided-vs-light A/B + 3 harder traps) and **add the harder, higher-value `extract` mode** (6 items seeded from real harvest triples) before drawing conclusions. That expanded run is pending.

---

## What was built

**Serving (llama-swap `/opt/llama-swap/config/config.yaml`):**
- Added a clean base id **`gemma4-26b`** → the MoE base (`gemma-4-26B-A4B-it-UD-Q4_K_XL.gguf`), neutral posture, on-demand. The dense `gemma4-31b` (a QAT coach-fallback, *not* the base) was left untouched.
- Added a co-residency set **`po_eval: "go & g26"`** so `gpt-oss-120b` + `gemma4-26b` load together (~95-105 GB / 121 GB, mirrors `autobuild_go`) — the scorer hits both without swapping.
- Discipline: the run **requires the keepalive timer paused** (`sudo systemctl stop llama-swap-keepalive.timer`) so its 5-min probe doesn't revive the `all` fleet on top → OOM. Re-enable after. Backups: `config.yaml.bak-20260702-pre-gemma4-26b-base`, `…-pre-po-eval-set`.

**Harness (`score_golden_set.py`):** reuses the factory rubric verbatim (`build_coach_prompt` + `create_coach` + `_parse_coach_verdict` → `CoachVerdict`). Additions this phase:
- retry-with-backoff on transient HTTP 429 (llama-swap `concurrencyLimit`), default `--concurrency 2` (the model's limit);
- persists the model-under-test's full output for auditing/curation;
- **`--instruction {guided,light,minimal}`** — A/B how much output shape is spoon-fed, to separate native PO tendency from instruction-following.

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

**What to watch:** extract-mode accept rate (real grounded features — likely lower than greenfield); whether the harder greenfield traps (005-007) still get 0 false-confidence; and the guided→light delta on `assumption_explicitness` / `acceptance_criteria_testability` (the dimensions most likely to depend on the spoon-feed).

---

## Open items / caveats

- **Sample is still small** (13). Percentages are coarse; trap behaviour is the signal to trust. Expand the other four modes (`idea`/`evolve`/`impact`/`scope`) next for full coverage.
- **Extract items skew to `primary_dimension: assumption_surfacing`** — accurate (the harvested features are parameter-dense) but it means dimension *coverage* via the `extract` batch is narrow; the Coach still scores all 8 criteria per item regardless.
- **Coach = gpt-oss-120b is itself an LLM judge** — its leniency is a variable. The perfect greenfield sweep warrants the light-instruction cross-check to rule out judge over-generosity.
- **Keepalive must be re-enabled after each run** (`sudo systemctl start llama-swap-keepalive.timer`) to restore the production fleet (`coach-ft-v3` etc.).

---

*Grounded 2026-07-02. Harness + golden set under `domains/product-owner/`; reports under `domains/product-owner/golden_set/`.*
