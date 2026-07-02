# Phase 0 — PO Golden Set & Base-Model Diagnosis (Spec)

**Date:** 2026-07-02
**Parent:** `PLAN-po-dataset-generation.md` §7 Phase 0.
**Output:** a reusable book-free PO eval asset + a per-dimension weakness diagnosis that edge-weights Phase 3 generation.

---

## 0. Why Phase 0 is different for PO than for the architect

The architect's Phase 0 was a **short-circuit**: an architect fine-tune already existed and was deployed, so Phase 0 asked "is the model we already have good enough once the injection is removed?" — and could make the whole build unnecessary.

**PO has no fine-tune to short-circuit.** So Phase 0 here is not a go/no-go on building; it produces two assets the build *needs regardless*:

1. **The golden set** — the book-free eval you gate the Phase-4 fine-tune on. Skipping it is how you fool yourself (coach v1's "80% correct" on a 79%-approve holdout). It is unavoidable, so front-load it.
2. **A base-model dimension diagnosis** — score the current model with the factory Coach to find its weakest rubric dimensions, then over-sample those in generation (the coach "edge-dense toward measured misses" lever; softer for a generator than a judge, but still worth its low cost).

Phase 0 deliberately does **not** touch the think+fenced-JSON serving-contract risk — that's covered by the Phase-1 mode smoke-test, which should follow immediately.

---

## 1. Golden-set composition

**Target ~30 items (min 24), balanced across all six modes** — because five of the six modes have zero in-distribution training seed, the eval must measure all six or you're blind on 5/6 of the surface.

| Mode | Items | Seed source |
|---|---|---|
| `extract` | 6 | Real harvest triples (§2) — real briefs, real reference outputs |
| `greenfield` | 4 | Authored: a blank-slate product brief (problem statement in) |
| `idea` | 3 | Authored: a hypothesis to validate |
| `evolve` | 4 | Authored: an existing roadmap + a build-plan change |
| `impact` | 4 | Authored: an existing roadmap + new info to fold in |
| `scope` | 3 | Authored: a roadmap + a timebox/constraint cut |
| **+ assumption-posture traps** | 6 | Authored — see §3 (may reuse a mode framing) |

**Dimension coverage constraint:** across the set, each of the 7 behaviour dimensions (`outcome_framing`, `feature_decomposition`, `acceptance_criteria`, `assumption_surfacing`, `scope_discipline`, `prioritisation`, `cross_framework_synthesis`) is the *primary stress* of **≥3 items**. `terminology_correct` + `no_verbatim_reproduction` are cross-cutting (scored on every item). Optionally add 2–4 knowledge-layer items (`pm_concepts`, `discovery_framing`) for the deferred RAG layer.

**Multi-turn:** ≥5 items (≥15%) are 2–3 round (brief → partial decomposition + clarifying question → refine).

---

## 2. Seeding from the harvest (22 real triples, on-host)

All 22 paired `/feature-spec` records resolve on **this** host (the harvest recorded Mac paths; translate `/Users/richardwoollcott/…` → `/home/richardwoollcott/…`). Each gives a real `extract`-mode set:

- **Brief (user message):** the source spec the session decomposed (from `command_invocation` + the feature context).
- **Reference decomposition (NOT sole gold):** `features/<slug>/<slug>.feature` (the acceptance criteria as Gherkin) + `<slug>_assumptions.yaml` (assumptions with confidence + basis) + `<slug>_summary.md` (the decomposition).

> These outputs were **rubber-stamped AI proposals**, so treat them as a strong **reference**, not perfect gold. In scoring, the model-under-test *generates fresh* from the brief; the reference calibrates the rubric, it is not the answer key. Pick the ~6 richest triples (e.g. `FEAT-FORGE-008`, `Graphiti-Student-Model`, `FEAT-JARVIS-005`, `primary-text-rag`) — high scenario + assumption counts.

**Upper-bound baseline:** score the frontier **GPT-5.5** PO sessions (held-out per the harvest README) with the *same* harness to calibrate what a rubric-"good" decomposition looks like — the fine-tune's target is to approach it.

---

## 3. Assumption-posture traps (the PO analog of coach approve-traps)

The primary PO failure is **inventing a confident requirement where the honest answer is "unknown."** So the eval must include briefs that contain a **genuine unknown** the model *should* surface as an explicit assumption (confidence + basis), not silently resolve.

Each trap records the expected loud/conservative behaviour, e.g.:

> *Brief:* "Add notifications so users know about events." *Hidden unknown:* channel (email/push/in-app) and delivery guarantee (best-effort vs guaranteed) are unspecified and materially change the acceptance criteria.
> *Pass:* surfaces both as assumptions with confidence + basis; scopes MVP conditionally.
> *Fail:* invents "send push notifications with guaranteed delivery" as a firm requirement.

Traps make the metric **two-sided** (§5).

---

## 4. Item schema

```json
{
  "id": "GOLD-extract-003",
  "mode": "extract",
  "primary_dimension": "assumption_surfacing",
  "turns": 1,
  "is_assumption_trap": false,
  "user": "<the brief / doc corpus / roadmap+constraint — per mode>",
  "reference": {                     // optional; harvest triples or GPT-5.5 output
    "feature_path": "…/x.feature",
    "assumptions_path": "…/x_assumptions.yaml",
    "summary_path": "…/x_summary.md"
  },
  "trap_expectation": null           // for traps: the unknown that must become an assumption
}
```

System message is always the verbatim PO system prompt from `GOAL.md §System Prompt`.

---

## 5. The scoring harness (`score_golden_set.py`)

> **Model under test:** `gemma4-26b` on `:9000` — the base **Gemma-4-26B-A4B-IT MoE**
> the PO fine-tune trains from (added to the llama-swap config 2026-07-02 as a
> clean base id; same weights as `gemma4-coach`, neutral posture, on-demand). This
> is the indicative base, not the dense `gemma4-31b` QAT coach-fallback. Coach
> (gate) = `gpt-oss-120b` — a different model (SPEC AC-5, no self-scoring).


No standalone scorer exists — the Coach only runs inside `run_generation_loop`. Build a ~60-line harness that **reuses the factory pieces verbatim** (this also validates the harness you'll gate training with):

**Reused factory API:**
- `config.loader.load_config()` — Player = model-under-test; Coach = the gate model (a *different* model per Decision B).
- `domain_config.parser.parse_goal_md(domains/product-owner/GOAL.md)` → `GoalConfig`.
- `prompts.coach_prompts.build_coach_prompt(goal, target_layer="behaviour")` (`coach_prompts.py:255`).
- `agents.coach.create_coach(config.coach, coach_prompt, memory=["./AGENTS.md"])` (`agents/coach.py`).
- `entrypoint.generation_loop._parse_coach_verdict` (`generation_loop.py:348`) → `config.coach_verdict.CoachVerdict` = `{decision, score(1-5), layer_correct, type_correct, criteria_met: dict[str,bool], issues:[{criterion,severity,description,suggestion}], quality_assessment, is_accepted}`.
- Invoke the coach graph with the example as the user turn exactly as `_process_single_target` does (`generation_loop.py:~796-810`).

**Two steps per item:**
1. **Generate** — run the model-under-test on `{system: PO system prompt, user: item.user}` → its `<think>` + fenced ProductRoadmap JSON output.
2. **Score** — feed `{system, user, assistant=output}` to the Coach; parse `CoachVerdict`.

**Aggregate outputs:**
- **Per-dimension pass rate** = fraction of items where `criteria_met[dim] == True`. → the weakness ranking.
- **Per-mode pass rate** = mean `is_accepted` by mode. → which of the 6 modes the base is worst at (expect the 5 unseeded ones lower).
- **Assumption-posture score** = on trap items, fraction that surfaced the unknown vs invented a requirement.

---

## 6. Two-sided metric (don't over-correct into a hedger)

Track both failure directions, mirroring coach FA/FF:

- **False confidence** (primary): invented a requirement where the honest answer was unknown → low `assumption_explicitness`, trap fail.
- **Over-conservative**: hedged everything into assumptions / refused to commit to an MVP → low `scope_discipline`/`decomposition_coherence` despite high assumption counts.

The Phase-4 fine-tune must **lower false-confidence without raising over-conservative** — a single aggregate score would hide the trade, exactly the coach v1 lesson.

---

## 7. What Phase 0 feeds forward

- **Edge-density weight vector** → Phase 3: over-sample the taxonomy dimensions with the lowest base pass rates (e.g. if `assumption_surfacing` fails 60% but `feature_decomposition` passes 90%, shift generation volume toward assumption-surfacing).
- **The golden set itself** → Phase 4 gate (balanced, two-sided).
- **A validated Coach harness** → reused as the training-time gate + the final eval.

---

## 8. Acceptance criteria

- [ ] **AC-1** ~30 golden items (min 24) spanning all six modes; each behaviour dimension the primary stress of ≥3 items; ≥5 multi-turn; ≥6 assumption-posture traps.
- [ ] **AC-2** ≥6 `extract` items seeded from on-host harvest triples; GPT-5.5 upper-bound baseline scored by the same harness.
- [ ] **AC-3** `score_golden_set.py` reuses `load_config` / `parse_goal_md` / `build_coach_prompt` / `create_coach` / `_parse_coach_verdict` (no re-implementation of the rubric).
- [ ] **AC-4** Report: per-dimension pass rate, per-mode pass rate, two-sided (false-confidence vs over-conservative) counts, and the derived edge-density weight vector.
- [ ] **AC-5** Player (model-under-test) ≠ Coach (gate) model — no self-scoring.

---

## 9. Effort

~½–1 day: harness ~60 lines reusing factory internals; the cost is authoring/curating ~24 briefs (the 6 `extract` come nearly free from the harvest triples; the 18 authored + 6 traps are the real work). Front-loads the unavoidable Phase-4 eval asset.

---

*Grounded 2026-07-02 against agents/coach.py, prompts/coach_prompts.py:255, entrypoint/generation_loop.py:348, config/coach_verdict.py, and the 22 on-host harvest triples.*
