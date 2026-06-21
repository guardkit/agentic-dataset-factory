# HANDOFF — Coach v3: train==serve on the evidence-bundle prompt

**Date:** 2026-06-20 · **For:** the next session · **Read first:** `RESULTS-coach-v2.md` (the finding),
`RETRO-coach-finetune.md` (v1), `project_coach_v2_synthetic` memory. **Fleet:** leave **STOPPED** (v3
re-harvest is CPU; training needs it down anyway).

---

## TL;DR

v2 proved the synthetic pipeline works and surfaced the real root cause: **a train≠serve format mismatch.**
The **production** autobuild Coach is served `task + player_report + <evidence_bundle> + absence-of-failure
guards` and decides in **toolless synthesis** mode (verdict entirely from the bundle). But the **harvest**
(`curate_coach_dataset.py:render_prompt`) trained on `player_report` ONLY — dropping the bundle. So v1/v2
were trained on an input the production Coach never sees (ill-posed AND off-distribution), which is very
likely the dominant cause of the rubber-stamp — deeper than v1's "class imbalance."

**v3 = make training match production.** No serving change. First do the cheap experiment that may moot the
whole fine-tune (Step 0). The catch: the **input evidence bundle is not persisted** per turn, so real-data
re-harvest needs reconstruction — which is why **synthetic-first (we control the bundle) is the v3 spine.**

**Win condition (unchanged):** false-approval AND false-feedback both < ~20% on a balanced holdout **whose
prompts are in the production evidence-bundle format.**

---

## The grounding (verified 2026-06-20, read-only investigation)

**Production Coach prompt** — `guardkit/guardkit/orchestrator/agent_invoker.py`:
- `_build_coach_prompt(...)` assembles: `Task + Requirements + Player's Report (JSON) + {evidence_section} +
  {honesty_section} + {guards_section} + responsibilities + Decision Format`.
- `_render_evidence_bundle_section()` emits the bundle as JSON inside `<evidence_bundle>...</evidence_bundle>`.
- `_render_absence_of_failure_guards()` emits 7 guards (zero-cardinality BDD/test, sophisticated-lie,
  Layer-1 path demotion, gathering-status, independent-test-absent, wiring advisory).
- Toolless synthesis: `allowed_tools=[]`, "base your verdict ENTIRELY on the evidence bundle."
- Bundle is produced by `CoachValidator.gather_evidence()` (`orchestrator/autobuild.py` ~L6051) →
  `CoachEvidenceBundle` (`orchestrator/quality_gates/coach_evidence.py`), passed via `invoke_coach(evidence_bundle=...)`.

**CoachEvidenceBundle fields** (what to surface): `honesty` (discrepancies, Layer-1 resolved_paths, Layer-2),
`gathering_status`, `quality_gates` (tests/coverage/arch/plan aggregate), `coverage_details`, `plan_audit`,
`bdd` (scenarios_attempted/failed, discoveries, errors), `arch_review`, `tests`, `wiring`, `mocked_seam`,
`spec_gap`, `independent_tests` (Coach's own pytest), `runtime_parity`, `evidence_repo_tests`,
`severity_recommendations`, `advisory_issues`, `task_type`, `profile_name`.

**Harvest gap** — `guardkit/scripts/{harvest_coach_dataset.py, curate_coach_dataset.py}`:
`render_prompt()` builds the prompt from `task + player_report` only; the Coach artifact is used ONLY for the
`render_completion()` label and outcome-join. **The bundle is dropped.**

**Persistence gap (key constraint)** — turn dirs (`<repo>/.guardkit/autobuild/<TASK>/`) contain
`player_turn_N.json`, `coach_turn_N.json` (OUTPUT only: `decision, issues, criteria_verification, rationale`),
`task_work_results.json`, `phase_4_summary.json`, `specialist_results.json`, `state_transitions.json`,
`turn_context.json`. **The input `CoachEvidenceBundle` is NOT persisted.** Partial signals are reconstructable
from `phase_4_summary.json` (tests/coverage/bdd) + the coach_turn's `criteria_verification[].evidence` /
`issues` (which quote the verification), but that is approximate and partly entangled with the label.

---

## v3 plan

### Step 0 — Re-measure the BASE with the evidence bundle (cheap; may moot the fine-tune)
The base `gemma4-coach`'s "94% false-approval" was on the impoverished prompt. The production design intent is
base + bundle + guards. **Build ~30 evidence-format eval prompts and eval the base** (zero-shot, fleet up OR
transformers). Two ways to get bundles:
- reuse the production `_build_coach_prompt` + a reconstructed bundle (from `phase_4_summary` + coach_turn
  evidence) for a handful of real held-out turns, OR
- hand-construct/synthesize a few evidence-format cases.
**If base + bundle + guards already lands both rates < ~20% → the rubber-stamp was a harvest artifact; the
"fix" is just configuration (ensure production serves the bundle — it does) + maybe no FT at all.** This is
the highest-value, lowest-cost first experiment. Do it before any training.

### Step 1 — Persist the input bundle going forward (1-line enabler)
In `autobuild.py` right after `gather_evidence()`, write `evidence_bundle.to_dict()` to
`<TASK>/coach_evidence_turn_N.json`. Costless, and every future autobuild run then yields clean,
production-faithful `(prompt-with-bundle → verdict)` training pairs. Start accumulating immediately.

### Step 2 — Build v3 training data (synthetic-first)
Because real input bundles aren't persisted historically, **synthetic is the spine** (we control the bundle):
- **2a Synthetic in production format.** Extend the v2 generator (proven, cue-gated) so each case emits a
  `CoachEvidenceBundle`-shaped object where the **flaw lives in the evidence** (e.g.
  `independent_tests.tests_passed=false`; `bdd.scenarios_failed=1`; `coverage` below threshold; `honesty`
  discrepancy; `plan_audit.missing_files`) for feedback, and clean bundles for approve. Render via the
  **production `_build_coach_prompt`** so train==serve byte-for-byte. Matched pairs + traps + the cue gate carry over.
- **2b Reconstructed real (for realism).** From persisted artifacts, assemble approximate bundles
  (`phase_4_summary` + extracted coach_turn evidence) for a subset; tag `source: reconstructed` and keep
  filterable. Lower priority than 2a; or skip until Step 1 accumulates clean runs.
- **Design care:** the prompt carries the **evidence (raw signals)**; the completion carries the **judgment
  (decision/criteria/rationale)**. Do NOT put the Coach's output `criteria_verification.result`/`decision`
  into the prompt — that leaks the label. Surface `independent_tests`, `tests`, `bdd`, `coverage`, `honesty`,
  `plan_audit`, etc. (the inputs), not the verdict.

### Step 3 — Prompt format: reuse production builder
Import/replicate `_build_coach_prompt` + `_render_evidence_bundle_section` + `_render_absence_of_failure_guards`
so the training prompt is identical to serving. Re-point `curate_coach_dataset.py` (or a new v3 renderer) at it.
This is the single most important fidelity lever.

### Step 4 — Sequence length / GB10 memory (watch this)
The evidence bundle is large; production uses ctx 65536. Evidence-format prompts will be **much longer** than
v2's ~2k tokens — likely > 4096 → the **GB10 seq-4096 memory ceiling returns** (seq≥6144 OOM-climbs on one
GB10; see RETRO). Mitigations: (a) measure real token lengths first; (b) compress the bundle to the
decision-relevant fields; (c) the **2nd GB10** (cable ~2026-06-23) unlocks seq 8192 via multi-node sharding —
this is exactly where it pays off. Don't assume 4096 fits.

### Step 5 — Retrain + eval
Same recipe (`train_coach_moe.py`, seq per Step 4, base unchanged, watchdog, fleet stopped, manual launch per
`LAUNCH-coach-v2-lora.md`). Eval on the **evidence-format** balanced holdout. Gate: both rates < ~20%.

---

## Open questions / risks
- **Step 0 outcome decides scope:** if base+bundle is already good, v3 is mostly a data/serving-config
  confirmation, not a fine-tune. Run it first.
- **Bundle reconstruction fidelity** (2b) vs synthetic-only (2a): start synthetic; add real once Step 1 persists bundles.
- **Prompt length → seq/memory** (Step 4) is the main feasibility risk; may gate on the 2nd GB10.
- **Leakage discipline:** evidence-in, judgment-out; keep the Coach's output fields out of the prompt.
- **Holdout integrity:** the evidence-format holdout must be disjoint from train and use real-or-realistic bundles.

## Reusable assets (carry over from v2, `domains/coach-agent/`)
`build_lora_corpus_v2.py`, `prepare_coach_sft.py`, `assemble_synthetic_v2.py`, `audit_cue_leakage.py`,
`finalize_v2_corpus.py`, `extract_workflow_rows.py`, `fewshot_eval_coach.py`, `eval_coach.py`
(`--holdout-file`, sdpa), `train_coach_moe.py`, `mem_watchdog.sh`, the 3 generator workflows. The v2
balanced/holdout JSONLs and the trained `coach-gemma4-26b-moe-v2` adapter remain for reference/ablation.
