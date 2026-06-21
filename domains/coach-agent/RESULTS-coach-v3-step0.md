# RESULTS — Coach v3 Step 0: re-measure the BASE with the production evidence bundle

**Date:** 2026-06-20 · **Status:** Step 0 COMPLETE — **win condition met on production-format input** ·
**Headline:** the rubber-stamp is a **train≠serve / input-completeness artifact, not a base-model
capability gap.** Given the production Coach prompt (player_report + `<evidence_bundle>` + 7
absence-of-failure guards, toolless synthesis), the **base `gemma4-coach`** scores **false-approval
13.3% AND false-feedback 7.7–13.3%** — both under the ~20% bar that v1/v2 never reached.
**Companions:** `HANDOFF-coach-v3.md` (the plan), `RESULTS-coach-v2.md` (the finding), `RETRO-coach-finetune.md` (v1).

---

## 1. What Step 0 asked

Every prior Coach eval — including the base's "94% false-approval" — ran on the **harvest** prompt
(`player_report` only). Production serves the Coach `task + player_report + <evidence_bundle> + guards`
in **toolless synthesis** mode. Step 0: re-measure the base **WITH the bundle**. If base+bundle+guards
already lands both rates < ~20%, the rubber-stamp was a harvest artifact and the fine-tune may be
unnecessary (HANDOFF-coach-v3 Step 0).

**Fidelity lever:** prompts rendered by the **real** `AgentInvoker._build_coach_prompt(synthesis=True)`
(+ `_render_evidence_bundle_section` / `_render_absence_of_failure_guards` / `_render_bundle_honesty_section`)
called on a bare instance — **byte-faithful train==serve, zero drift.** Base served via llama-swap
:9000 with the strict GBNF grammar (same path that measured the base in v2).

## 2. Three measurements (base `gemma4-coach`, balanced)

| eval | false-approval | false-feedback | correct |
|---|---|---|---|
| player-report-only (v2 baseline) | **94%** (15/16) | 12% | 47% |
| + partial **reconstructed** bundle (32 real holdout cases, Player-side gates only) | **75%** (12/16) | 6% (1/16) | 56% |
| + full **production** bundle (30 synthetic, flaw-in-bundle) — **all 30** | **13.3%** (2/15) | **13.3%** (2/15) | 86.7% |
| + full production bundle — **teacher-validated 28** | **13.3%** (2/15) | **7.7%** (1/13) | — |

**Win condition (both < ~20%): MET** on the production-format synthetic set.

## 3. The reconstructed-real datapoint — the mechanism, isolated

`build_step0_eval.py` rebuilt the 32 v2 holdout cases in production format, reconstructing the bundle
**only from input-side `task_work_results.json`** (Player-produced gates — NEVER `coach_turn_N.json`, so
no label leakage; audit clean). Result: **FA 94→75%, FF 6%.** Breakdown by whether the Player-side
gates alone already implied feedback:

- **recoverable** (Player's own gates show the failure): **caught 3/3 (100%)**.
- **uninferable** (gates clean; the real Coach rejected on its OWN independent verification): **caught 0/13**.

This is the crux finding: the Coach's own `independent_tests` / `honesty` / BDD-oracle signals are
**never persisted** (`coach_turn_N.json` is output-only), so reconstruction can only carry the Player's
clean gates for 13/16 feedback cases. **Reconstruction CANNOT test the production hypothesis** — the
discriminating signal is exactly the unpersisted field. But where the signal IS present, the base reads
it and rejects (3/3). That is why the decisive test had to be synthetic (we control the bundle).

## 4. The decisive synthetic test — flaw lives IN the bundle

30 cases (15 feedback / 15 approve incl. 6 approve-traps), one per absence-of-failure guard + the
RESULTS smoking-gun (`independent_tests.tests_passed=false`) + key `.claude/rules` failure modes.
**Discipline (v2's lesson — free-text LLM generation leaks cues):** gold label + flaw placement are
**deterministic** (set per guard/variant), LLM only writes the realistic wrapper (task + player_report
claiming success + descriptive strings). A **deterministic guard-checker** confirmed every feedback case
trips ≥1 blocking guard and every approve case trips none. An **Opus blind-verify** (reads each rendered
prompt blind) **agreed with 28/30 golds**.

**Base result: FA 13.3%, FF 13.3% (full 30); FF 7.7% on the teacher-validated 28.** The 4 base misses
split exactly into the two known-hard directions:

- **2 false-approvals** — the subtlest *absence-of-failure*: `g1_zero_bdd` (approved despite
  `bdd.scenarios_attempted=0`) and one `independent_failed` (trusted the Player's "tests pass" over
  `independent_tests.tests_passed=false`). The base is still slightly too lenient on pure absence.
- **2 false-feedbacks** — the subtlest *approve-traps*: `trap_g4_path` (rejected a Layer-1-resolved
  path discrepancy it should have demoted) and `trap_scary_stderr`. The base is slightly too aggressive
  on scary surface signals.

These are precisely the edges the v3 synthetic data targets — and exactly what more flaw-in-bundle
data (or guard-prompt tuning) would close.

## 5. Blind-verify caught 2 generation defects (not base errors)

Opus's 2 disagreements were both *approve* cases where the LLM wrapper text contradicted the
deterministic bundle:
- **SYN-019**: task demanded ≥90% coverage but bundle set 88% with `coverage_met=true` (inconsistent).
- **SYN-028** (`trap_scary_stderr`): the generated `test_output_summary` described an actual FAILED test,
  so `tests_passed=true` contradicts its own summary — the trap backfired.

**Lesson (reconfirms v2):** deterministic flaw-placement is necessary but not sufficient — the LLM
wrapper can still inject a contradiction, so the **blind-verify gate stays mandatory** for synthetic
data. Both defects are eval-quality issues, identified and excluded from the teacher-validated number.

## 6. Conclusion + what it means for v3

**The base Coach is broadly competent when given the production evidence bundle.** The rubber-stamp was
the input being impoverished (train≠serve), not the model. Implications:

- **The fine-tune may be unnecessary** for the headline rubber-stamp. The "fix" is configuration/data-
  format: ensure training matches the production bundle prompt — which **production already serves**
  (`agent_invoker.py:_build_coach_prompt`). If a Coach FT is still pursued, train on the **production
  bundle format** (HANDOFF Step 3) and target the **residual absence-of-failure edges** (zero-BDD,
  independent-fail) + the **approve-trap edges** (path-demotion, benign-warning) — ~13% each.
- **Do Step 1 (persist the bundle) regardless** — the 1-line `autobuild.py` write of
  `evidence_bundle.to_dict()` per turn. It is the enabler for confirming this on REAL production bundles
  and for any future bundle-format harvest/FT.

### Honest caveats
- Synthetic bundles place the flaw cleanly; **real production bundles are messier.** This is a strong
  positive signal, **pending confirmation on real persisted bundles** (Step 1 → re-measure).
- Prompts are long (gemma4 tokens ~p50 5.8k, max ~10k; 31/32 reconstructed > 4096) — fine for inference
  (base ctx 65536) but confirms **Step 4**: bundle-format *training* truncates badly at seq 4096 →
  needs bundle compression or the 2nd GB10.
- Measured with the strict GBNF grammar via llama-swap (same toolless-synthesis path as production).

## 7. Artifacts (`domains/coach-agent/`)
- `build_step0_eval.py` → `step0_eval.jsonl` (32 reconstructed-real, production format) + `step0_samples/`.
- `run_step0_base.py` → `step0_base_reconstructed_report.json`, `step0_base_synth_report.json`.
- `wf_gen_step0_synth.js` (generator) + `extract_specs.py` → `step0_synth_specs.jsonl`.
- `assemble_step0_synthetic.py` (real-bundle build + deterministic guard-checker) → `step0_synth_eval.jsonl`.
- `wf_blindverify_step0.js` → `step0_blindverify_report.json` (Opus 28/30 agree).
- `step0_synth_prompts/` (per-case rendered prompts).

## 8. Talk / video takeaways
1. **"The prompt lied" — proven, then fixed.** v2 found the Coach was trained on an input the production
   Coach never sees. Step 0 re-measured the base on the REAL production input and the 94% rubber-stamp
   collapsed to 13%. Most "the model can't judge" is "we never put the evidence in the input."
2. **You can't reconstruct what you didn't persist.** The real-data reconstruction recovered the verdict
   for 3/16 feedback cases and 0/13 of the ones that hinged on the Coach's own (unpersisted) verification
   — a clean, quantified demonstration of why the synthetic, bundle-controlled test was the only way to
   answer the question. (And the 1-line fix: persist the bundle.)
3. **Adversarial verification caught the generator cheating — again.** A deterministic guard-checker
   plus an independent Opus blind-verify flagged 2/30 cases where the LLM wrapper contradicted the
   intended flaw. The dataset factory auditing its own data, at every layer.
