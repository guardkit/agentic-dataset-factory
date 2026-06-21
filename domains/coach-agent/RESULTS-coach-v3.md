# RESULTS — Coach v3 fine-tune: bundle-format LoRA WINS the rubber-stamp gate

**Date:** 2026-06-21 · **Status:** v3 FT COMPLETE + EVAL'D — **WIN, decisively.** Both rates beat base on
the production-bundle holdout; the single disagreement is a known eval-quality defect, not a model error.
**Read-first companions:** `RESULTS-coach-v3-step0.md` (base+bundle baseline), `RESULTS-coach-v3-smoke.md`
(seq-6144 memory probe), `HANDOFF-coach-v3-lora-launch.md` (the staged run), `LAUNCH-coach-v3-lora.md`
(the runbook), memory `project_coach_v2_synthetic`.

---

## TL;DR

A LoRA trained on the **production evidence-bundle prompt** (train==serve, byte-faithful via the real
`AgentInvoker._build_coach_prompt(synthesis=True)`) scores **false-approval 0.0% / false-feedback 6.7% /
96.7% correct** on the 30-case bundle-format holdout — beating the base (`gemma4-coach` + bundle: FA 13.3%
/ FF 13.3% / 86.7%) on **both** axes with no over-rejection. On the teacher-validated 28 (excluding the
two Step-0-flagged generation defects) it is **FA 0.0% / FF 0.0% / 100%** — flawless. **Win condition
(FA AND FF both < ~20% AND beat base 13.3/13.3): MET.**

The arc, end to end: **94% rubber-stamp → 0% false-approval.**

---

## The eval

**Command (operator-run, GB10 docker, fleet STOPPED):** `eval_coach.py --model-path
.../coach-gemma4-26b-moe-v3/merged-16bit --holdout-file holdout_synth_v3.jsonl --max-tokens 96`
(transformers backend, bf16, sdpa; **no GBNF grammar** — the FT emits parseable decision-lead JSON on its
own). Report: `~/fine-tuning/output/v3-eval.json`, log `v3-eval.log`.

```
[holdout — TRUE held-out, the generalisation metric]
  n=30  parse=100%  correct=96.7%  false-approval=0.0% (of 15 feedback)
  confusion: {'approve->approve': 14, 'approve->feedback': 1, 'feedback->feedback': 15}
```

| metric | v3 FT | base + bundle (Step 0) |
|---|---|---|
| correct | **96.7%** (29/30) | 86.7% |
| false-approval (gold=feedback wrongly approved) | **0.0%** (0/15) | 13.3% (2/15) |
| false-feedback (gold=approve wrongly rejected) | **6.7%** (1/15) | 13.3% (2/15) |
| parse rate | 100% | 100% (via GBNF) |

## The single disagreement is a known defect, not a model error

The one miss — `approve->feedback` — is **idx27 = SYN-028 / `trap_scary_stderr`**, one of the **two cases
the Step-0 Opus blind-verify already flagged as a generation defect** (`RESULTS-coach-v3-step0.md` §5): its
bundle is self-contradictory — `independent_tests.tests_passed=true` while the `test_output_summary` text
literally says "FAILED". The FT's raw output shows it caught exactly that contradiction
("the independent trust-but-verify run … FAILED: 'FAILED…'") and rejected — a **defensible** verdict on a
case whose gold label is itself suspect.

**Excluding the two flagged defects (SYN-019, SYN-028 — both approve-side), the teacher-validated 28:
FA 0/15 = 0.0%, FF 0/13 = 0.0%, correct 28/28 = 100%.**

## What the FT actually fixed (vs base's 4 residual misses)

Base+bundle's 4 misses split into the two known-hard directions; the FT closed all the genuine ones:

- base FA #1 `g1_zero_bdd` (approved despite `bdd.scenarios_attempted=0`) → **FT caught it.**
- base FA #2 `independent_failed` (trusted Player's "tests pass" over `independent_tests.tests_passed=false`)
  → **FT caught it.**
- base FF #1 `trap_g4_path` (over-rejected a Layer-1-resolved path discrepancy it should demote)
  → **FT correctly approved.**
- base FF #2 `trap_scary_stderr` = SYN-028 → the **defective** case above (gold suspect; FT's reject is
  reasonable). Not a real regression.

So the bundle-format LoRA closed the absence-of-failure leniency (FA → 0) **and** the path-demotion
over-rejection (the one *valid* approve-trap), without introducing new over-rejection.

## Training recap (the run that produced this)

`RESULTS-coach-v3-smoke.md` + `v3-full.log`: 3 epochs × 174 rows (94 approve / 80 feedback), seq **6144**,
base `unsloth/gemma-4-26b-a4b-it`, **[G1]** 1.88% trainable (494M/26.3B), **[G3]** sdpa (Gemma-4 head-dim
512 > FA2's 256), **[G4]** 85.2% masked (correct for bundle format — the prompt is the large part, the
verdict is the trained ~15%), **train_loss 0.456 → 0.1473**, **[G5] peak 63.2 GB** (58 GB under the 121 GB
ceiling — v1's seq-6144 OOM-climb did **not** recur on v3's shorter data). exit 0. Artifacts in
`~/fine-tuning/output/coach-gemma4-26b-moe-v3/` (lora-adapter / merged-16bit / gguf q4_k_m stand-in).

## Honest caveats

- **Synthetic holdout.** The 30-case holdout is synthetic (deterministic flaw placement), scenario-disjoint
  from train (0 leakage) but from the **same generator family** — so this proves the FT learned the
  bundle-format judgment and generalises across held-out scenarios *within that distribution*, not yet that
  it generalises to **real, messier production bundles**. Step 1 (guardkit `24b7f324`) now persists real
  `coach_evidence_turn_N.json` per turn → a future re-harvest can confirm this on real bundles.
- **Decode-path difference.** Base was measured via llama-swap + strict GBNF grammar; the FT via
  transformers `--model-path` with **no** grammar. parse=100% on both, so the comparison is fair, but note
  the FT's *production serve* path will be GBNF-constrained — see the round-trip gate below.
- **Marginal value over Step 0.** base+bundle already passed the <20 gate (13.3/13.3); the FT's value is
  closing the residual ~13% on each axis (→ 0% false-approval, the critical anti-rubber-stamp metric) and
  giving margin. Worth shipping — after the round-trip check.

## Serve verification (2026-06-21 — RUNBOOK smoke-test #7 + served-quant eval, BOTH PASS)

The bf16 eval above used transformers (`--model-path`), which does **not** exercise the production
llama.cpp + GBNF serve path. Two follow-up checks closed that gap, with the v3 `q4_k_m` GGUF served
standalone (`llama-server --reasoning off --jinja`, port 8123, mirroring the production `gemma4-coach`
posture; production fleet left untouched on :9000):

**(1) [G2] thought-block round-trip — PASS.** RUNBOOK #7's three checks, on SYN-001 (feedback,
`g1_zero_bdd` — a base false-approval) and SYN-016 (approve, clean), each run **without** grammar
(natural emission) and **with** `coach-verdict.gbnf`:
- (a) valid JSON — fenced ` ```json ` verdict in all 4 runs.
- (b) **NO leaked `<|channel>thought` / `<|turn>` / `<eos>` tokens**; `reasoning_content` empty (the model
  goes straight to the verdict — the trained non-thinking posture under `--reasoning off`). **The [G2]
  empty-thought-block concern does not materialise at serve** (confirms v2's earlier finding for v3).
- (c) COACHSPLIT schema — `task_id`→`turn`→`decision` first, echoing the right task_id/turn from the
  prompt identity. Both decisions correct (SYN-001→feedback, citing "the BDD oracle ran zero scenarios";
  SYN-016→approve).

**(2) Served-quant eval — PASS, identical to bf16.** `eval_coach.py --endpoint :8123 --grammar
coach-verdict.gbnf` over the full 30-case holdout (production toolless+grammar posture):

```
[holdout]  n=30  parse=100%  correct=96.7%  false-approval=0.0% (of 15 feedback)
  confusion: {'approve->approve': 14, 'approve->feedback': 1, 'feedback->feedback': 15}
```

**Byte-identical to the bf16 merged-16bit result** (FA 0.0% / FF 6.7% / 96.7%, same single SYN-028 miss).
→ q4_k_m quantization + grammar serve introduces **zero judgment degradation**. The "pragmatic stand-in"
q4_k_m is already production-grade for this task; **UD-Q4_K_XL is now a fidelity nice-to-have, not a
correctness requirement.**

## Decision: WIN path → next steps

1. **Restore the fleet (LAUNCH Step E)** — ✅ DONE (operator restored; :9000 healthy).
2. **[G2] thought-block round-trip** — ✅ DONE, PASS (see Serve verification above). Pre-serve gate cleared.
3. **Serve quant + route.** ✅ q4_k_m serve **validated** (FA 0%/FF 6.7%, identical to bf16). Remaining:
   add a `coach-ft-v3` llama-swap route (clone the `gemma4-coach` block per `SERVING-coach-ft.md` §2 —
   back up config, restart via systemd) pointing at the v3 GGUF; then repoint the orchestrator's per-role
   Coach override to `coach-ft-v3` (guardkit-side; don't move aliases silently). **UD-Q4_K_XL** (llama.cpp
   `quantize` + Unsloth imatrix; `RESEARCH-gemma4-qat-decision.md` §3) is optional polish — q4_k_m already
   matches bf16.
4. **seq-8192 retrain: NOT needed for this corpus.** 0 of 174 rows exceed 6144 tok (max ≈5784) → the
   6144→8192 band is empty; 8192 buys nothing here. Only relevant to a **future longer real-bundle corpus**
   (Step 1's accumulating evidence), for which the single GB10's 63 GB headroom already suffices.
5. **Confirm on real bundles (ongoing).** Periodically re-harvest the persisted `coach_evidence_turn_N.json`
   to re-measure FA/FF on real production bundles and to enrich the corpus.

## Deployment — LIVE (2026-06-21)

Flipped the production autobuild Coach to `coach-ft-v3`. **Key correction found during deploy:** the
forge production path (`forge-autobuild-runner` → `langgraph dev` → `guardkit autobuild feature <id>
--fresh --verbose`) passes **no `--coach-model`**, so the Coach was falling through to the *Player/default*
model (agent_invoker.py:3745-3753) — it was **never the dedicated base `gemma4-coach`** in the forge path
(that posture only applied to manual `--coach-model gemma4:26b` runs). So this gives the autobuild Coach a
dedicated model for the first time.

**Changes applied (memory-neutral swap of the always-on Coach slot — `coach-ft-v3` ≈ `gemma4-coach`
26B-A4B footprint):**
1. `/opt/llama-swap/models/coach-ft-v3/coach-gemma4-26b-moe-v3.Q4_K_M.gguf` — staged the GGUF (16.8 GB).
2. `/opt/llama-swap/config/config.yaml` — added the `coach-ft-v3` block (ctx 98304, `--reasoning off`,
   q8 KV, alias `autobuild-coach-ft`/`coach_test_ft`); added matrix var `cfv3`; rotated `all` set
   `gc → cfv3`; swapped `hooks.on_startup.preload` `gemma4-coach → coach-ft-v3`. Backed up to
   `config.yaml.bak-20260621-152040-pre-coach-ft-v3`. `gemma4-coach` block kept (now on-demand).
3. `forge/src/forge/subagents/autobuild_runner.py` — added `--coach-model coach-ft-v3` to the autobuild
   argv (~L1376). **Uncommitted working-tree change** on `main`.
4. Restarted `llama-swap` (coach-ft-v3 ready ~21s, total 74 GB — no OOM) and `forge-autobuild-runner`
   (replaced a stale old-code `langgraph dev` survivor holding :8124; fresh process now serves the new code).

**Validated:** `:9000 → coach-ft-v3` (grammar-constrained) returns correct verdicts (SYN-001→feedback,
SYN-016→approve), no `<|channel>thought`/`<|turn>` leaks, COACHSPLIT schema. The full chain is wired:
forge argv → guardkit coach override → `openai:coach-ft-v3` → llama-swap.

**⚠️ Outstanding operator action (needs sudo — root file):** update the keepalive allowlist
`/usr/local/bin/llama-swap-keepalive.sh` `MODEL_PROBE_KIND`: `[gemma4-coach]=chat` → `[coach-ft-v3]=chat`.
The keepalive timer is currently **inactive** (no immediate hazard), but this MUST match `preload` **before
the timer is ever re-enabled**, or it will revive `gemma4-coach` on top of `coach-ft-v3` → OOM/freeze.

**Rollback:** restore `config.yaml.bak-*-pre-coach-ft-v3` (or revert preload + `all` to `gc` and delete the
block/`cfv3` var); delete the two `--coach-model`/`coach-ft-v3` argv items in `autobuild_runner.py`; restart
both services.

**Caveat carried into production:** the win is validated on the synthetic bundle holdout. Step 1
(guardkit `24b7f324`) persists real `coach_evidence_turn_N.json` per turn — re-harvest periodically to
confirm FA/FF on real production bundles now that the FT is the live Coach.

## Talk / video takeaways

1. **94% → 0% false-approval, by fixing the *input*, not the model.** v1/v2 trained the Coach on an input
   production never sends (player-report only). Once trained on the real production bundle (train==serve),
   false-approval collapsed to zero. "The model can't judge" was "we never put the evidence in the input."
2. **The dataset factory caught its own defect — and so did the model.** The single eval disagreement landed
   exactly on a case the Step-0 blind-verify had already flagged as self-contradictory; the FT rejected it
   for the same reason the auditor did. Adversarial verification at generation time and judgment time agreed.
3. **Targeted edge data closes targeted edges.** The synthetic corpus was edge-dense on base's specific
   Step-0 misses (zero-BDD, independent-fail, path-demotion); the FT closed precisely those, with no
   collateral over-rejection.
