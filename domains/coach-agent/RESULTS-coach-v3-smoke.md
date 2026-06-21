# RESULTS — Coach v3 Step B SMOKE: the seq-6144 memory probe

**Date:** 2026-06-21 · **Status:** Step B SMOKE **PASS — GO for Step C (full run) at seq 6144, no
fallback needed** · **Headline:** the handoff's #1 open risk ("seq-6144 may OOM-climb past ~110 GB like
v1") is **retired** — v3 peaks at **63.2 GB**, ~58 GB under the 121 GB ceiling.
**Companions:** `LAUNCH-coach-v3-lora.md` (the runbook this evaluates), `HANDOFF-coach-v3-lora-launch.md`
(the plan + open risks), `RESULTS-coach-v3-step0.md` (the base finding the FT targets).

---

## 1. What Step B asked

Step B is a single-purpose probe, not a quality eval: **does seq 6144 fit under the ~110 GB watchdog
threshold on one 121 GB GB10?** v1 OOM-climbed at 6144 (→ ~112 GB, watchdog-killed), so 8192 was deferred
to the 2nd GB10. v3's data is shorter (max example 5784 tok vs v1's 7215), so the peak *should* land
lower — the smoke finds out. The GO/NO-GO is the **step-40** memory peak (the allocator high-water climbs
over the epoch, so step 1 is not representative).

## 2. The five gates — all PASS

40-step smoke on the full 174-row corpus (0.92 epoch), `run_coach_v3_smoke.sh`, default SEQ=6144.

| Gate | Criterion | Observed | Verdict |
|---|---|---|---|
| **[G5] memory** ⭐ | step-40 peak < ~110 GB | **63.2 GB** (torch in-proc peak) | ✅ ~47 GB margin |
| [G1] trainable | ≥ ~1.0% (expect ~1.88%) | 494,376,960 / 26,300,310,832 = **1.88%** | ✅ exact |
| [G3] attn impl | sdpa | **sdpa** (FA2 unsupported: gemma4 head-dim 512 > 256 limit) | ✅ |
| [G4] masking | not 0% / not 100% | **85.2%** masked (3796 prompt / 661 verdict, 4457 tot) | ✅ see §3 |
| loss | decreasing | **0.45 → 0.23** (clean downtrend, train_loss 0.2334) | ✅ |
| exit | 0 | exit 0; MoE LoRA merge 60/60 per-expert tensors | ✅ |

**The headline:** [G5] = 63.2 GB at step 40. The whole purpose of the smoke. v1's failure mode does not
recur on v3's shorter data. (Note: [G5] is the torch `max_memory_allocated` in-process peak; the
Terminal-3 `nvidia-smi` reading was not captured but runs modestly higher — CUDA context +
fragmentation, typically +3–10 GB → ~70 GB — still far under the 110 GB gate.)

## 3. Two readings that look off but aren't

**[G4] 85.2% masked is EXPECTED for v3 — the runbook's note is stale.** The log note predicts "~29%
masked, the Coach verdict is the LARGER trained part" — that was the **v2** shape (short player-report
prompt, long verdict). v3 **inverts** it: the prompt is now the full **production evidence bundle**
(~3796 tok, masked) and the verdict is the short completion (661 tok, trained). 661/4457 = 14.8% trained
/ 85.2% masked is internally consistent and matches the planned token budget (bundle p50 3980, verdict
p50 660). The markers are working — 661 tok of verdict signal per example is the correct completion-only
SFT setup. The STOP condition (~0% or ~100% → markers wrong) is **not** tripped.

**Throughput → the full run will take longer than the runbook's "40–60 min."** Observed **~43.5 s/step**
(0.023 steps/s; smoke train_runtime 1739 s for 40 steps + ~6 min merge). The full run (3 epochs × 174
rows ≈ **~130 steps**) projects to **~90–100 min** + merge. Don't read the longer duration as a hang.

## 4. Why NOT go higher than seq 6144 (the data settles it)

Re-measured the staged corpus directly (`train-coach-v3.jsonl`, chars/3.50 ≈ tokens cross-check; precise
tokenizer figures from the handoff):

```
rows=174   est tokens:  p50≈4707  p95≈5329  MAX≈5784 (handoff, tokenizer-precise) / ~5874 (char-estimate)
rows > 6144 tok: 0      headroom of seq6144 over the longest example: ~270–360 tok
```

- **0 of 174 rows exceed 6144.** seq 6144 already trains **100% of every verdict with 0% truncation.**
  The token band 6144 → 8192 is **empty** for v3 — there is nothing up there to capture.
- Raising to 8192 buys **zero** training signal and costs memory + step time. On Unsloth's variable-length
  path it likely wouldn't even raise the 63 GB peak (the peak is driven by the real 5784-tok longest
  batch, not the cap) — but it definitely adds no quality, and forces a re-smoke.
- The byte-faithful **train==serve** rendering is the foundation of the v3 effort; there is no reason to
  perturb a config that already fits the data losslessly.

**What the 63 GB peak actually unlocks (the real value):** 8192 was deferred to the 2nd GB10 because of
*memory risk* — and that risk is now disproven. So a **future re-harvest that mixes in real production
bundles** (Step 1 is accumulating `coach_evidence_turn_N.json`; real bundles are messier/longer than
synthetic) **can train at seq 8192 on this single GB10** — no need to wait for the 2nd box. The slim
~270-tok margin over the current longest example is the cue: the day a longer real bundle enters the
corpus, *that's* when you go to 8192, and the probe says the box will take it.

**If you want to spend the ~58 GB of spare headroom on THIS run** the lever that helps is **effective
batch size** (throughput + smoother gradients) or **LoRA rank** — not seq. For a 174-row calibration
LoRA, neither is worth a config change + re-smoke; the current setup is well-matched.

## 5. Carry-forward (for the WIN path, not a Step B/C/D concern)

The [G2] render note flags a possible **train≠serve mismatch at SERVE time**: no `<|channel>thought`
block in the trained assistant turn, but the 26B-A4B non-thinking path injects an empty thought block at
serve via `add_generation_prompt`. Irrelevant to the memory gate, the full run, and the eval — but **if
the eval wins**, verify with the export + grammar-serve round-trip (RUNBOOK smoke-test #7) **before**
building the `coach-ft-v3` serve quant. The JSON verdict position could differ between train and serve.

## 6. Conclusion + next action

**GO. Run Step C unchanged** (`run_coach_v3_full.sh`, default SEQ=6144). Keep `mem_watchdog.sh
coach-ft-v3 11` + `watch nvidia-smi` running and glance past step 40/80 per the runbook — but at a 63.2
GB smoke peak, an allocator climb of ~47 GB over the full run is very unlikely, and the watchdog
backstops a freeze. **The `-e SEQ=4096` fallback is not needed.** Then Step D eval on
`holdout_synth_v3.jsonl` (gate: FA AND FF both < ~20% and beating base 13.3% / 13.3%). Paste
`v3-full.log` then `v3-eval.log` back.

## 7. Artifacts
- `~/fine-tuning/output/v3-smoke.log` — the smoke run (gates [G1]–[G5], loss curve, merge).
- `~/fine-tuning/scripts/run_coach_v3_smoke.sh`, `train_coach_moe.py`, `mem_watchdog.sh`.
- `~/fine-tuning/data/train-coach-v3.jsonl` — 174 rows, 0 > 6144 tok (verified).
- Output: `~/fine-tuning/output/coach-gemma4-26b-moe-v3-smoke/{lora-adapter,merged-16bit}` (throwaway).

## 8. Talk / video takeaways
1. **The memory probe is the GO gate, not the loss.** A fine-tune smoke's job on a constrained box is to
   answer one question — *does it fit?* — at the step that matters (step 40, after the allocator climbs),
   behind a watchdog that backstops a freeze. v1 OOM-climbed at this exact setting; v3's shorter data
   peaked at 63 GB. Same model, same seq, different data → 50 GB difference.
2. **"Go higher" only helps if your data is up there.** seq 8192 sounds strictly better, but 0 of 174
   examples exceed 6144 — the extra context window would train on emptiness at higher cost. Pick the
   sequence length from the *measured* token distribution, not from the hardware's max.
3. **A passing probe retires a roadmap assumption.** The 63 GB peak didn't just greenlight this run — it
   proved the single GB10 can do the seq-8192 run that was scheduled for the 2nd box, changing what the
   2nd GB10 is actually *for*.
