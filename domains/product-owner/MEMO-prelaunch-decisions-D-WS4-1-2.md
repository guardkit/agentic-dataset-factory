# Pre-Launch Decision Memo — D-WS4-1 (edge-density) + D-WS4-2 (target count)

**Date:** 2026-07-07 (WS4-S1). **Decider: Rich** — both decisions block the 82h Phase-3 launch (`ws4-learning-flywheel-scope-and-build-plan-2026-07-07.md` §3.2/§8). This memo drafts the options with a recommendation each; it decides nothing. D-WS4-3 (run scheduling: Spark A now + fleet-quiet window vs second Spark) is the third launch blocker and is **not** covered here — see WS4 §3.3 (recommendation there: Spark A now).

**Companion:** `SPEC-po-phase2-harvest-lift.md` (this dir, same session) — referenced for the mode-mix and phased-shape mechanics.

---

## D-WS4-1 — Edge-density: oversampling knob vs consciously-uniform walk

**Ground truth.** Phase-0's corrected verdict (`RESULTS-po-phase0.md:130–137`): the base's judgment criteria (assumptions, scope, decomposition, no-fabrication — 0/11 trap false-confidences across three runs) need *reinforcement, not remediation*. The real Phase-3 emphasis is **outcome-framing under the JSON contract** (62% under contract JSON vs 85–100% in prose), **`prioritisation_rationale`** (100%→62% guided→light), and **serving-shape fluency** (correct JSON, phased ACs). The GOAL Generation Targets predate this verdict and walk the taxonomy uniformly.

**A fact that reframes the "knob".** The factory expands targets directly from the GOAL count table (one target per unit of `Count`). **The count table is already the oversampling knob** — re-weighting is a data edit + dated note, not new code. The third emphasis (serving-shape fluency) is not a count at all: it is already handled structurally by the `require_fenced_json` gate (Phase-1 fix, 100% strict inner-JSON on re-verify) plus the Phase-2 phased-extract shapes and inner-schema validation (SPEC §5). So the decision is narrower than the WS4 doc's framing: *should the two weak criteria's categories get more mass, and where does the mass come from?*

### Option 1 — Rebalance the count table, total preserved (RECOMMENDED)

Boost the two Phase-0-weak categories; fund it entirely from the **knowledge layer**, which feeds a **deferred** RAG index, not the fine-tune (GOAL: "RAG is out day-one… this fine-tune is behaviour-led"). No judgment category is cut — the loud/conservative posture (the Phase-4 two-sided gate) keeps its full training mass.

| Category | Now | Proposed | Δ |
|---|---|---|---|
| Outcome framing (weak under JSON: 62%) | 150 | **210** | +60 |
| Prioritisation (weak unguided: 62%) | 100 | **150** | +50 |
| PM concepts (knowledge, deferred RAG) | 150 | **90** | −60 |
| Discovery & framing (knowledge, deferred RAG) | 100 | **50** | −50 |
| all other behaviour categories | unchanged | | 0 |

Total unchanged (1,100 if D-WS4-2 Option A). Behaviour/knowledge shifts ~76/24 → ~87/13 — a deliberate, documented consequence, not drift; the knowledge layer still gets 140 rows for the future index. Wall-clock ≈ unchanged (same target count; behaviour rows are similar-length to knowledge rows). Cost: a GOAL table edit + dated note under the table. Reversible until the run starts.

- **For:** puts mass exactly where Phase 0 measured softness; zero code; zero schedule impact; preserves the total for D-WS4-2.
- **Against:** knowledge-layer volume drops 44% (acceptable only because RAG is deferred — if a near-term RAG step were planned, fund additively instead); percentages rest on a 13-item Phase-0 sample (directional, not precise — which is why the boost is +40–50%, not a re-architecture).

### Option 2 — Additive oversample (total grows)

Same +110 boost on top of the current table: total → 1,210, knowledge untouched, wall-clock +~8h (~90h run).

- **For:** nothing is cut; more total data.
- **Against:** lengthens the fleet-quiet window (D-WS4-3 pressure); breaks the 1,100 reconciliation (D-WS4-2 would need a third number); more of what the base is already strong at.

### Option 3 — Consciously-uniform walk, decision filed

Keep the table as-is; file this decision so the uniform walk is chosen, not drifted into (the WS4 doc's explicit alternative).

- **For:** zero changes; the weak criteria still get 150+100 uniform rows; the fine-tune's job is reinforcement anyway, and harvest weighting (SPEC §4) + phased shapes already skew the corpus toward serving-shape reality.
- **Against:** Phase-0's only two measured soft spots get no extra mass; if the Phase-4 gate then shows `outcome_over_output`-under-JSON below bar, the remedy is a partial re-run — far more expensive than +60 rows now.

**Recommendation: Option 1.** Mechanism: edit the GOAL Generation Targets table per the Δ column with a dated `<!-- D-WS4-1 -->` comment; WS4-S2 lands the edit once Rich signs.

**Decision (Rich):** ______________  **Date:** ______________

---

## D-WS4-2 — Target count: 1,050 (GOAL comment) vs 1,100 (table / Phase-1 RESULTS)

**Ground truth.** The GOAL Generation Targets **table sums to 1,100** (behaviour 150+150+150+125+100+100+75 = 850; knowledge 150+100 = 250). The "Total book-generation = 1,050" in the GOAL comment block (`GOAL.md:54`) is **stale arithmetic inside the same file** — the factory expands targets from the table, so any full run *is* 1,100; `RESULTS-po-phase1.md:19,90` ("1,100-target run (~82h)") simply reports what the machinery will do. There is no independent source for 1,050.

### Option A — Adopt 1,100 (RECOMMENDED)

Fix the GOAL comment 1,050 → 1,100 with a dated note. Zero machinery change; the ~82h estimate and `agent-config.yaml` readiness (`RESULTS-po-phase1.md:88–90`) already assume it; D-WS4-1 Option 1 preserves it.

### Option B — Enforce 1,050

Cut 50 from the table (no principled donor category exists — the comment never said where its 1,050 came from) and re-derive the wall-clock estimate. Saves ~4h of an 82h run.

- **Against:** invents a rationale to preserve a typo; touches the same table D-WS4-1 edits, twice.

**Recommendation: Option A** — the table is the operative artifact; correct the prose to match it.

**Decision (Rich):** ______________  **Date:** ______________

---

## Run-composition note (informational — config default, not a filed decision)

SPEC §5.6 sets the bulk-run mode list to `[idea, greenfield, extract:a, evolve, impact, scope, extract:b]`: extract's phased shapes get 2/7 of behaviour targets (knowledge-layer targets never receive phased tokens — SPEC §5.2) (they carry the AC/enum/citation disciplines that have zero coverage otherwise and cure the Phase-0 AC-testability artifact); the five no-corpus modes keep 5/7. Two implications for the launch runbook (WS4-S3): extract targets author an in-message synthetic corpus, so Player outputs run longer — watch wall-clock against the 82h estimate in the P2 loop; and the Phase-1 watch items (decomposition depth ~1 epic/1 feature; inner-JSON reject rate, `RESULTS-po-phase1.md:92–96`) apply with extra force to the two new shapes. The mode list is `agent-config.yaml` data — Rich can override it at launch without code.

---

*Both decisions must be filed (dated notes here + WS4 doc §8 markers updated) before `limit` is removed from `generation:` — WS4 §3.2: "do not drift into it."*
