# HANDOFF — Coach v3: Step 0/1 done, v3 LoRA staged, awaiting GB10 launch

**Date:** 2026-06-21 · **For:** the next session (fresh context) / the operator · **Supersedes:**
`HANDOFF-coach-v3.md` (the pre-Step-0 plan). **Read-first companions:** `RESULTS-coach-v3-step0.md`
(the headline finding), `RESULTS-coach-v3-smoke.md` (Step B PASS — seq-6144 fits at 63.2 GB),
`LAUNCH-coach-v3-lora.md` (how to run the training — **the immediate next action**),
memory `project_coach_v2_synthetic`.

---

## TL;DR

- **Step 0 (done):** the Coach rubber-stamp is a **train≠serve / input-completeness artifact, NOT a
  base-model capability gap.** Given the *production* prompt (`player_report + <evidence_bundle> + 7
  absence-of-failure guards`, toolless synthesis), the **base `gemma4-coach`** scores **false-approval
  13.3% / false-feedback 13.3%** (vs **94% FA** on the old player-report-only prompt). Win condition met.
- **Step 1 (done, committed):** the input `CoachEvidenceBundle` is now persisted per turn
  (`coach_evidence_turn_N.json`) so future runs yield production-faithful training pairs. guardkit commit
  **`24b7f324`** on `main` (not pushed).
- **Step 2 (done, staged):** built a 174-row v3 training corpus **in the production bundle format** and
  staged a GB10 LoRA package. **Awaiting your manual launch** (Claude must not drive GB10 docker — freeze risk).
- **NEXT ACTION:** run `LAUNCH-coach-v3-lora.md` (seq 6144, behind the watchdog). Paste `v3-smoke.log`
  then `v3-eval.log` back to a new session.

---

## The immediate next step (you, manual)

Follow **`domains/coach-agent/LAUNCH-coach-v3-lora.md`** exactly. Sequence:
1. **Stop the fleet** (Step A) — frees the 121 GB pool; `nvidia-smi` compute-apps must be EMPTY.
2. **Smoke** (Step B, ~10 min) behind `mem_watchdog.sh coach-ft-v3 11` + `watch nvidia-smi`. **The
   GO/NO-GO is the step-40 memory peak < ~110 GB** (NOT step 1 — the allocator climbs over the epoch).
3. **Full run** (Step C, ~40–60 min, watchdog on).
4. **Eval** (Step D) on `holdout_synth_v3.jsonl`; read the `[holdout …]` block only.
5. **Restore the fleet** (Step E).

**Gate:** false-approval AND false-feedback both **< ~20% AND beating base 13.3% / 13.3%**.
**If seq 6144 OOM-climbs:** relaunch with `-e SEQ=4096` (decision-preserved; tests the FA/FF gate, terser
verdicts) **or** defer to the 2nd GB10 (cable ~2026-06-23 → seq 8192, 0% truncation).

---

## Why seq 6144 (operator chose) — the real-token finding

Measured with the actual gemma4 tokenizer (**chars/token = 3.50**):
- bundle prompt: **p50 3980, max 4488** tok (the production bundle+guards+decision-format boilerplate is
  irreducible — shrinking it would break train==serve).
- completion (verdict): p50 660 tok. full example: p50 4677, **max 5784**.
- **ALL exceed seq 4096** (completion truncates: decision survives, issues/rationale clip). **0% exceed 6144.**

So seq 6144 → **0% truncation** (full verdicts trained). Risk: v1 saw seq-6144 OOM-climb to ~112 GB on one
GB10 — but v3's data is shorter (max 5784 vs v1's 7215), so the peak may land under the 121 GB ceiling.
The smoke is the probe. The 2nd GB10 unlocks a clean seq-8192 run if 6144 doesn't fit.

---

## Staged artifacts (verified present)

**Data (`~/fine-tuning/data/`):**
- `train-coach-v3.jsonl` — **174 rows, 94 approve / 80 feedback**, ShareGPT, `source=synthetic_v3`,
  COACHSPLIT-reshaped (task_id+turn+decision lead), 0 holdout leakage.
- `holdout_synth_v3.jsonl` — **30 bundle-format cases** (15 fb / 15 ap). **Base baseline: FA 13.3% (2/15),
  FF 13.3% (2/15)** (excluding the 2 blind-verify-flagged cases SYN-019/028: FA 13.3% / FF 7.7%).

**Scripts (`~/fine-tuning/scripts/`):** `run_coach_v3_smoke.sh`, `run_coach_v3_full.sh` (default `SEQ=6144`,
override `-e SEQ=4096`), `mem_watchdog.sh`, `train_coach_moe.py`, `eval_coach.py`.

**Output (after the run):** `~/fine-tuning/output/coach-gemma4-26b-moe-v3/` (lora-adapter / merged-16bit /
gguf), `~/fine-tuning/output/v3-{smoke,full,eval}.log`.

**guardkit commit:** `24b7f324` on `main` — `_invoke_coach_primary` persists the bundle; +2 tests in
`tests/orchestrator/test_llm_coach_primary.py::TestPrimaryFlowEvidenceBundlePersistence` (19 pass). Not pushed.

---

## How the v3 corpus was built (reproducible; all in `domains/coach-agent/`)

Pipeline (the Step-0 machinery, scaled + extended to emit gold completions):
1. `wf_gen_v3_train.js` (Workflow) — 80 matched clean/flaw bundle pairs + 16 approve-traps. **Gold label +
   flaw placement are DETERMINISTIC** (set per absence-of-failure guard in `makeBundleSpec`); the LLM writes
   only the realistic wrapper (task + player_report claiming success + flaw strings). Edge-dense on the
   base's Step-0 misses. → SPEC_JSONL lines in the run output.
2. `extract_specs.py` (from the run `.output` `logs[]`) → `v3_train_specs.jsonl` (176 specs).
3. `assemble_step0_synthetic.py` — builds REAL `CoachEvidenceBundle` from each spec, renders via the
   production `AgentInvoker._build_coach_prompt(synthesis=True)` (byte-faithful train==serve), and a
   **deterministic guard-checker validates every gold** (feedback ⇒ ≥1 blocking guard; approve ⇒ none).
   → `v3_train_eval.jsonl`.
4. `prep_teacher_args.py` → per-scenario prompt files (`v3_prompts/`) + compact args.
5. `wf_teacher_verdict_v3.js` (Workflow) — Opus teacher-Coach reads each prompt, writes a full COACHSPLIT
   verdict; **kept only where decision == deterministic gold** (172/176 first pass). Evidence-in-prompt,
   judgment-in-completion (no leakage).
6. `build_v3_sft.py` — joins prompts↔verdicts (merges multiple verdict sources), fenced completions,
   gate. → `v3_sft_raw.jsonl` (174 rows).
7. `prepare_coach_sft.py --weight-mode none --rationale-cap 300 --note-cap 120 --holdout step0_synth_eval.jsonl`
   → `~/fine-tuning/data/train-coach-v3.jsonl`.

**Data-quality lesson (carry forward):** the `scary_stderr` trap initially reused the agent's *failure*
summary string → malformed bundle (tests_passed=true but summary says "FAILED …"); the teacher gate
correctly dropped them. Fixed in `wf_gen_v3_train.js makeBundleSpec` (benign-by-construction) + patched
+ re-verdicted → recovered. 2 path-demotion traps stayed dropped (teacher found genuine logic bugs in
those wrappers). **The teacher-agreement gate is doing real work — keep it.**

---

## Open risks / what to watch

- **seq-6144 memory (primary): RESOLVED 2026-06-21 — smoke PASS, peak 63.2 GB at step 40** (~58 GB under
  the 121 GB ceiling). v1's OOM-climb does not recur on v3's shorter data. GO for the full run at 6144, no
  `-e SEQ=4096` fallback needed. See `RESULTS-coach-v3-smoke.md`. (Spin-off: the single GB10 can now do the
  seq-8192 run that was scheduled for the 2nd box — relevant only to a future longer real-bundle corpus;
  the current 174 rows are 0% over 6144, so 8192 buys nothing here.)
- **Trap thinness:** scary_stderr recovered but path-demotion traps are only ~4. If the FT eval shows
  **FF up (over-rejection)**, scale traps in `wf_gen_v3_train.js` and retrain.
- **Synthetic-only realism:** the corpus is synthetic (clean flaw placement). Real production bundles are
  messier — Step 1 now accumulates them; a future re-harvest can mix real bundles in.
- **Eval inference path:** base FA/FF (13.3/13.3) was measured via the llama-swap endpoint + strict GBNF
  grammar; the FT is eval'd via transformers `--model-path` (the runbook's Step D, v2 methodology). Same
  holdout, slightly different decode path — note it when comparing.

---

## After the eval (next session, depending on result)

- **WIN (both < base, traps held):** build UD-Q4_K_XL serve quant, add a `coach-ft-v3` llama-swap route,
  and (when the 2nd GB10 lands) a clean seq-8192 retrain for full verdicts.
- **FA down / FF up:** scale approve-traps + retrain.
- **No improvement over base:** base+bundle is near this model's ceiling — the real win was Step 0 (serve
  the bundle, which production already does); FT is optional. Consider scaling the corpus.
- **Regardless:** Step 1 keeps accumulating real `coach_evidence_turn_N.json` — periodically re-harvest to
  confirm Step 0 on real bundles and to enrich the corpus.

---

## Environment / housekeeping

- **Fleet: STOPPED** (Claude brought llama-swap up only for the Step-0 base eval, then stopped it). The
  GB10 needs the fleet down for training anyway.
- Throwaway tokenizer venv at `/tmp/toktest` (transformers, no torch) — used to measure real token lengths;
  delete anytime.
- Host: GB10 `promaxgb10-41b1`, 121 GB unified. Container `nvcr.io/nvidia/pytorch:25.11-py3` (pulled).
- **Claude must NOT launch GB10 docker training** — the Claude→tmux→docker chain froze the box twice; a
  freeze needs a power-cycle. Claude prepares + validates; the operator runs the docker steps.

---

## One-line status for the next session

> Step 0 proved base+bundle is not a rubber-stamp (FA/FF 13%); Step 1 persists the bundle (committed
> 24b7f324); Step 2 staged a 174-row bundle-format v3 LoRA at seq 6144 — **operator runs
> `LAUNCH-coach-v3-lora.md`, then paste `v3-smoke.log` / `v3-eval.log` back.**
