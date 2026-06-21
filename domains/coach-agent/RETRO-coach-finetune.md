# Retro: Coach LoRA fine-tune (Gemma-4-26B-A4B MoE)

**Period:** 2026-06-19 → 2026-06-20 · **Outcome:** ⚠️ trained & serving cleanly, **but eval = rubber-stamp → NOT deployable** · **Machine:** DGX Spark GB10 (`promaxgb10-41b1`, 121 GB unified)

> **Headline:** the pipeline, recipe, schema-alignment and serving all work — but the resulting
> model **approves ~81–96% of should-be-feedback cases** (false-approval). It learned the *format*
> and the *majority class*, not *judgment*. **This is a data problem, not a training problem**, and
> the 2-GB10 seq-8192 retrain will NOT fix it. See §3.5.

A judgment-quality Coach LoRA for the autobuild Player-Coach loop, fine-tuned from the curated
447-row verdict corpus. This retro captures what we set out to do, the decisions, the surprises
(mostly a GB10 memory wall), and what changes when the **second GB10 arrives**.

---

## 1. Goal & outcome

Turn the prepped `~/coach-dataset/` corpus into a fine-tuned Coach that emits the COACHSPLIT
structured-JSON verdict reliably — closing the base 26B-A4B's "reasons forever, no verdict" gap
(F17). Secondary trigger: Google's Gemma 4 **QAT** release ("should we use it?").

**Result:** `~/fine-tuning/output/coach-gemma4-26b-moe/` — LoRA adapter (1.9 G), merged-16bit
(49 G), q4_k_m GGUF (17 G). 1 epoch / 179 steps, **train_loss 0.162** (1.09 → ~0.11), all
smoke-guards green. Serves clean fenced-JSON verdicts with `--reasoning off` (no token leaks).

## 1.5 Eval result — the rubber-stamp (the real outcome)

Held-out eval (`eval_coach.py`, 76 holdout, decision-focused), 2026-06-20:

| metric | value |
|---|---|
| parse rate (valid JSON) | **100%** ✅ |
| correct-verdict | 80.3% *(illusory — 79% of holdout is gold-approve)* |
| **false-approval (of 16 gold-feedback)** | **87.5% (14/16) — approved cases that should be feedback** ❌ |
| approve rate overall | **73/76 = 96%** |
| in-train hard-case probes correct | **11.8%** (approves 9/17 cases it was trained to catch) |

Fairness-checked: re-running the 16 feedback cases **with** the training-matched coachsplit
identity suffix gave 81% false-approval (13/16) — marginally better, **still a rubber-stamp**. Not
a prompt/eval artifact.

**Verdict: the model is unusable as a Coach.** A Coach that approves ~81–96% of the work it should
push back on provides negative safety. The serving stuff (clean JSON, schema, no leaks) all works —
but the *judgment* didn't transfer.

### Root cause: class imbalance + weak corrective signal
- The corpus is **362 approve / 85 feedback (81/19)** — harvested Claude trajectories where Claude
  approved most Player turns. Oversampling lifted feedback only **19% → 24%** — nowhere near enough.
- The 9 relabelled + 8 authored hard-cases (the anti-rubber-stamp "corrective layer") were a
  rounding error against 362 approves.
- **train_loss 0.162 was a false comfort** — it measures format + majority-class fit, not judgment.
  Classic imbalanced-classification failure: the cheapest way to low loss is "always approve."

---

## 2. Key decisions (the cheap wins, all evidence-backed)

| Decision | Verdict | Why |
|---|---|---|
| **QAT base swap** (`gemma-4-...-qat-q4_0-unquantized`) | ❌ **Rejected** | Adversarial research refuted it: that repo is "for research/compilation," and Q4_0-from-QAT collapses 26B-A4B to **70.2%** top-1 (vs 85.6% UD-Q4_K_XL). Kept the proven bf16 base. The real QAT lever is `qat_scheme="int4"` during LoRA — untested on this MoE, exports w4a16 not GGUF → research only. |
| **Chat template** | `gemma-4` (non-thinking) | Coach emits JSON, not `<think>`. Adversarially supported; #7 confirmed clean serve. |
| **Serve quant** | UD-Q4_K_XL / q4_k_m, **never q4_0** | Unsloth's own number; q4_k_m is the interim stand-in. |
| **Verdict schema** | Reshape to `{task_id, turn, decision, …}` | The corpus **predated the live COACHSPLIT grammar** — it led with `decision` and had no task_id/turn, so an as-harvested Coach would be **rejected by the parser**. `prepare_coach_sft.py --coachsplit-schema` (default ON) fixed it. |
| **Weighting** | Oversample by `round(weight)` | TRL has no per-sample loss weighting; lifts feedback 19%→24% (anti-rubber-stamp). |

> **Why QAT was rejected — and why it's NOT a precision story** (common misconception): both the
> plain base and the `qat-q4_0-unquantized` checkpoint are **bf16 / full precision** — we fine-tune
> at full precision either way, so there is no "bf16 has more precision than QAT" *training*
> trade-off. QAT means the weights were *calibrated to survive int4 quantization* (near-bf16 quality
> when **served** at int4), not that they're lower precision. We rejected the QAT base because that
> benefit **didn't apply to our path**: (1) it isn't a supported fine-tune entry point (card says
> "research/compilation"); (2) QAT's payoff needs the matched **Q4_0** export, which Unsloth measured
> at **70.2%** top-1 for *this* 26B-A4B MoE — the matched format degraded it badly; (3) we already
> get good int4 serving via **UD-Q4_K_XL on the ordinary bf16 fine-tune**, so the swap buys nothing;
> (4) LoRA-merge + re-quantize would likely disturb the QAT calibration anyway. *Aside (opposite to
> intuition): QAT slightly perturbs the bf16 weights for int4-robustness, so the pristine base is the
> marginally cleaner full-precision start.*

**Data bugs caught by the serving-contract verification** (both in the 8 authored hard_cases,
now fixed in `hard_cases.jsonl` + `train_final.jsonl`): a mislabelled `path-string-mismatch`
verdict (metadata `feedback`, really `approve`) and a malformed-JSON verdict (`TASK-BDDW-009`,
trailing `}`).

---

## 3. The surprise: a GB10 memory wall (the main lesson)

The corpus is **completion-heavy** — real gemma4-tokenizer p99 ≈ 6,447 tokens, max ≈ 7,215.
To avoid truncating verdicts you want seq ≥ 6144. **But seq ≥ 6144 does not complete on a single
121 GB GB10**, and the failure mode is sneaky:

| seq | step 1 | step 40 | step 80 | result |
|---|---|---|---|---|
| **4096** | ~66 G | 80 G | (stable) | ✅ **completes** ([G5] peak 61 G) |
| 6144 | 66 G | 106 G | 112 G ↑ | ❌ watchdog-killed (~step 110) |
| 6144 + `expandable_segments` | 66 G | 101 G | 107 G ↑ | ❌ still climbing |
| 8192 | 66 G | — | 114 G @45 | ❌ watchdog-killed |

**The trap:** the CUDA allocator high-water **climbs over the epoch** (~6 GB / 40 steps at 6144),
because the peak is set by the *longest example seen so far*, and the longest 6–7k-token examples
appear partway through the shuffled epoch. **The step-1 reading badly understates the peak** — we
nearly trusted a comfortable 66 GB early reading. `PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True`
shifted the whole curve down only ~5 GB — not enough to change the verdict.

**Settled config:** seq 4096 + `--max-completion-tokens 2800` compression + expandable_segments
→ stable 61 GB, completes in ~82 min. **Cost:** ~18.7% of verdicts truncate their *rationale
tail* (decision + criteria + issues are at the front, preserved; and the serve-time GBNF grammar
forces complete JSON regardless). The residual 4096 truncation is **prompt-driven** (long ACs +
player reports), so completion-compression alone can't remove it.

### What made this survivable
- A **memory watchdog** (`docker kill` if available RAM < ~8–11 GB) ran behind every attempt, so
  each over-ambitious seq **aborted cleanly instead of freezing the box** (a freeze needs a
  power-cycle). This is non-negotiable on the GB10's unified memory.
- **Step-40 / step-80 probes** read the *plateau/trajectory*, not step 1 — that's what exposed the
  climb and let us bail early instead of wasting 2 h per failed run.
- Baking the guards ([G1] expert-attach 1.88%, [G2] template, [G3] sdpa, [G4] masking, [G5] peak)
  into the trainer meant every run self-validated in the first 60 s.

---

## 4. ⇒ The second GB10 (cable arriving ~2026-06-23) changes this

The seq-8192 wall is a **single-node memory limit**, not a model or data limit. With two GB10s
connected (ConnectX / the unified-memory interconnect), the path to **seq 8192, 0% truncation**:

- **~242 GB aggregate unified memory** across the pair — the 8192 peak (~114 GB on one node)
  comfortably fits when sharded, with headroom for the climb.
- **Options to use it** (in rough order of effort):
  1. **FSDP / sharded data-parallel** across the 2 nodes (Accelerate/torchrun) — shards optimizer +
     gradients + (optionally) params, roughly halving per-node memory → seq 8192 fits per node.
     Unsloth's multi-GPU story is the gating question to confirm.
  2. **Pipeline/tensor split** of the 49 GB frozen base across both nodes — frees per-node room for
     the long-seq activations.
  3. Simplest interim: keep single-node seq 4096 for *this* model; use the pair for the **next**
     full-fidelity retrain at 8192.
- **Re-run plan at 8192:** regenerate data with `--no-...` compression (full verdicts),
  `--max-seq-length 8192` (0% truncation), same guards + watchdog, and re-run the "beats base"
  eval to measure whether the full rationale tail actually improved judgment vs this 4096 model.
- **To confirm before the cable lands:** does the Unsloth + TRL stack we use support multi-node
  FSDP on GB10/Blackwell (sm_121) in container 25.11? (It needed `accelerate==1.10.0` single-node;
  multi-node device_map/FSDP interplay is the unknown.)

> **Decision (revised after the eval):** do NOT ship the seq-4096 Coach — it's a rubber-stamp.
> The second GB10 unlocks **seq 8192 / 0% truncation**, which is worth having, **but it does not
> fix the rubber-stamp** — that's a *data-balance* failure (§1.5), independent of sequence length.
> **Order of operations for v2:** (1) fix the corpus balance FIRST, (2) then retrain — at seq 8192
> on the 2-node rig if available, else seq 4096. Don't burn the 2-node run on the same imbalanced data.

### Fixing the rubber-stamp (the actual v2 priority — data, not hardware)
- **Rebalance toward feedback:** the 81/19 split + 24% oversample wasn't enough. Target ~40–50%
  feedback. Sources: harvest more *rejected*/feedback Claude turns; mine real autobuild logs for
  genuine false-greens; author many more hard negatives (the 8 hard-cases → dozens).
- **Stronger anti-majority levers:** much higher feedback oversampling (or class-weighted/focal loss
  if we move off plain TRL SFT), and verify on a *balanced* held-out set so "always approve" can't
  score 80%.
- **Re-eval gate:** require false-approval **< ~20%** on a balanced holdout before declaring success —
  correct-verdict alone is the metric that lied here.

---

## 5. What worked / what to change

**Worked**
- Adversarial research workflow up front — killed the QAT-base detour before it cost a run.
- Serving-contract verification *before* training — caught the task_id/turn schema mismatch that
  would have produced a parser-rejected model, plus 2 data bugs.
- Guards + watchdog + memory probes — turned a scary unified-memory box into a safe, debuggable
  loop. Zero freezes across 4 full-run attempts.

**Change next time**
- **Measure the step-40 memory plateau on a short probe BEFORE committing a seq length** — don't
  trust step 1. (Now in the runbook.)
- The trainer's `--max-seq-length` default is now **4096** (was optimistically 6144).
- Resolve the **grammar-application mechanism** for serving (the `grammar` field was ignored on
  `/v1/chat/completions`; COACHSPLIT applies it on the toolless synthesis call — confirm the exact
  path so the served Coach is schema-forced in production).
- Consider **prompt-side trimming** (player-report length) to cut the prompt-driven 4096 truncation
  if we stay single-node.

---

## 6. Open items (post-train)

**Eval done — result is the blocker.** The serving/deploy items below are **on hold until the
rubber-stamp is fixed** (§1.5, §4): a clean-serving rubber-stamp Coach must not go to production.

- [x] Held-out eval — **DONE: rubber-stamp, 87.5% false-approval, not deployable.**
- [ ] **P0 — fix the corpus balance** (target ~40–50% feedback; more rejected harvests + hard
      negatives) and retrain; gate on **false-approval < ~20% on a balanced holdout**.
- [ ] (Optional, low value now) base-vs-ft beats-base number — moot until the ft model meets the bar.
- [ ] Deferred until v2 passes the gate: UD-Q4_K_XL build · permanent `coach-ft` llama-swap block ·
      grammar-application path · keep base `gemma4-coach` as the production Coach meanwhile.
- [ ] `sudo rm -rf` the throwaway `coach-gemma4-26b-moe-smoke` (~54 G) + `checkpoint-*` dirs (~6 G).
- [ ] **v2:** rebalanced data → retrain (seq 8192 on the 2-node rig if available).

## 7. The fix: use the factory's own adversarial loop to mint the missing failure data

The rubber-stamp is a **data-balance** problem (§1.5), and the cure is the thing this repo exists
for. The **agentic-dataset-factory IS a Player–Coach training-data generator** — so we point it at
its own blind spot: generate the *judgment* (failure) data the Coach never saw enough of.

**The grounding already exists:**
- A real, documented **failure-mode taxonomy** in `guardkit/.claude/rules/` — 8 rules, each citing
  actual incidents (dates, Graphiti UUIDs, fixes): `absence-of-failure-is-not-success`,
  `per-task-green-is-not-feature-green`, `path-string-mismatch-is-not-dishonesty` (an *approve*-trap),
  `evidence-boundary-narrower-than-write-surface`, `smoke-gate-is-feedback-not-terminator`,
  `namespace-hygiene`, `harness-cancellation-contract`, `stack-plugin-architecture`.
- The hard-case **seeds already carry an `authoring_template` per rule** (`hard_case_seeds.jsonl`) —
  the scaffold to scale the 8 hand-authored cases to hundreds.

**Two complementary generation modes:**
1. **Taxonomy-driven (systematic):** per rule × documented manifestation × varied task domain,
   instantiate `(synthetic Task + flawed Player report exhibiting the failure + ideal `feedback`
   verdict that catches it)`.
2. **Adversarial emergent (realism):** the factory's native loop, weaponised — an *adversarial
   Player* sneaks a flaw past; a strong teacher Coach (Claude) catches it → `feedback`. Teacher
   *misses* → a high-value hard case to relabel.

**The trap to avoid — don't trade a rubber-stamp for an over-rejector.** Generate **matched pairs**
`(clean→approve, same-task-flaw-injected→feedback)` and keep the **approve-traps** (scary-but-fine →
approve), target **~50/50**, and **gate on a *balanced* holdout** (false-approval AND false-feedback
both < ~20%). The v1 eval's 80% "correct" lied only because the holdout was 79% approve.

## 8. Talk / video takeaways

The arc is a gift for content: a dataset factory, fine-tuning its own quality Coach, and what broke.

1. **Research before you burn compute.** An adversarial-verification pass refuted the "use the new
   QAT model" instinct *before* a multi-hour run — Q4_0-from-QAT collapses 26B-A4B to 70.2%, and the
   "QAT base" repo isn't even a fine-tuning entry point. Cheap research killed an expensive mistake.
2. **Verify train==serve *before* training.** Reading the live serving grammar first caught that the
   corpus predated the contract (no `task_id`/`turn`) — an as-harvested model would've been *rejected
   by the parser*. It also surfaced two authored-data bugs. None of that is visible in a loss curve.
3. **The hardware has opinions.** The GB10's unified memory *climbs* over an epoch at long sequence
   (8192→114 GB, 6144→112 GB); the early-step reading lies. A `docker kill` watchdog + step-40/80
   memory probes turned a freeze-prone box into a safe, debuggable loop — zero freezes in 4 attempts.
4. **The loss function lied** *(the headline).* train_loss **0.162** looked great; the model was a
   **rubber-stamp (87.5% false-approval)**. Imbalanced data (81% approve) → the cheapest path to low
   loss is "always approve." **Eval on a *balanced* set or your headline metric lies too.**
5. **The fix is recursive.** A dataset factory generating the *judgment* data its own Coach lacked —
   an adversarial Player planting real, documented failure modes, a teacher Coach catching them.

> The most valuable artifact of v1 isn't the model — it's a **correct, instrumented pipeline** and a
> precise diagnosis of *why* it failed. That's the part that makes v2 a known quantity.

---
*Artifacts: `domains/coach-agent/` — prepare_coach_sft.py · train_coach_moe.py · eval_coach.py ·
RUNBOOK · SERVING · RESEARCH-gemma4-qat-decision · HANDOFF-coach-v2 · this retro.*
