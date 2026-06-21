# RESULTS — Coach v2 (synthetic balanced data → tiny LoRA) + the input-completeness finding

**Date:** 2026-06-20 · **Status:** v2 LoRA trained + evaluated — **best Coach yet, not deployable** ·
**Headline:** the rubber-stamp is *substantially an ill-posed-task artifact*: ~half the corpus's gold
verdicts depend on the Coach's **independent verification**, which the player-report prompt omits. This is
a deeper root cause than v1's "class-imbalance" diagnosis, and it sets the v3 direction.
**Companions:** `RETRO-coach-finetune.md` (v1), `HANDOFF-coach-v2.md`, `LAUNCH-coach-v2-lora.md`.

---

## 1. What we did (the v2 arc)

1. **Built a taxonomy-driven synthetic generator** (the factory's own Player–Coach loop, Opus as the teacher
   Coach), grounded in the 8 `guardkit/.claude/rules/` failure modes: matched `(flaw→feedback /
   clean→approve / scary-but-fine→approve-trap)` cases, blind-verified by an independent Opus pass.
2. **Three cue-hardening rounds + a standing auto-gate** (`audit_cue_leakage.py`): round 1 fixed class
   balance but leaked lexical cues (`green`→fb, `real`→ap, `ast.parse`→fb); round 2 fixed those but leaked a
   numeric cue (feedback cited more tests in 28/28 matched pairs); round 3 fixed that but needed a
   deterministic finalize (drop the backfired `hard_pair` rows, neutralize intensifiers, backfill the
   collapsed harness rule). Lesson: **spurious cues are whack-a-mole; numeric/structural cues are best fixed
   deterministically, not by more prose rounds — and the real arbiter is a cue-immune holdout.**
3. **Step-3 cheap signal (few-shot, no GB10):** on the cue-immune real holdout, +6 synthetic exemplars
   crushed false-approval **94%→12%** (data is potent) but over-rejected (false-feedback 75–81%) — few-shot
   can't calibrate; balanced fine-tuning can.
4. **Tiny LoRA** on a balanced 196-row corpus (84 real fb + 14 synth fb + 98 approves), seq 4096, 2 epochs,
   on the GB10 (smoke + full all-green: 1.88% trainable, peak 61 GB, train_loss 0.196).

## 2. The numbers (eval on `holdout_balanced_real.jsonl` — 16 fb / 16 ap real rows)

| model | false-approval | false-feedback | correct |
|---|---|---|---|
| base `gemma4-coach` (zero-shot) | **94%** | 12% | 47% |
| base + 6 synthetic exemplars (few-shot) | 12% | 75–81% | 50–53% |
| **v2 LoRA (196 balanced, 2 ep)** | **62.5%** (10/16) | **18.75%** (3/16) | **59.4%** |

The LoRA **halved the base's false-approval** (94→62.5), lifted correct +12 pts, and kept false-feedback
**in-bounds** (<20%). But it is **not** the win condition (both rates < ~20%): it is *under-corrected* —
still approves 10/16 should-be-feedback.

> ⚠️ **CRITICAL CAVEAT (discovered post-eval — see §3/§4): all three rows above were measured on the
> HARVEST prompt (`player_report` only), which is NOT the production Coach's input.** The live autobuild
> Coach is served `player_report` **plus a `<evidence_bundle>`** (independent tests/BDD/lint/coverage/
> honesty) and absence-of-failure guards, in toolless-synthesis mode. So these numbers measure the base/FT
> on an *impoverished, non-production* input; the base's true production false-approval is **unmeasured**.
> v3 redoes this on the production format, starting by re-measuring the base WITH the evidence bundle.

## 3. WHY — the input-completeness finding (the real result)

We classified every holdout case: *is the gold verdict reachable from the player-report prompt ALONE, or
does it require the Coach's independent verification?* (Opus panel, blind to the model's answer.)

**Feedback (16):** `inferable yes=4 · partial=6 · no=6`. Signal types: `in_report_tell=7 ·
requires_independent_verification=6 · thin_evidence_unverified_AC=3`.
**Approve (16):** 11 are justified by independent verification the report does not contain.

The 6 **uninferable** feedback cases are the smoking gun — the player report claims success, and the gold
rejects on the Coach's **own** run, e.g.:
- `TASK-J003-007`, `TASK-GCI-007`: report `tests_passed: True`; gold = *"pytest-bdd: 1 scenario assertion
  failed"* (the Coach's BDD oracle, not in the report).
- `TASK-GR-LOAD`: report `tests_passed: True (12)`; gold = *"8 ACs missing"* (on-disk verification).
- `TASK-MEM-002`: report asserts all 20 tests pass; gold = *"evidence_bundle.independent_tests.tests_passed
  = false"* (independent runner failed).

And the FT's three **false-feedbacks** (`TASK-MEM-007`, `J004-019`, `J004-002`) are the mirror image: the
report *looks* bad (`files: []`, `tests_run: False`) so the model says feedback, but gold **approves** on an
independent evidence bundle the report doesn't show.

**Implications:**
- **A prompt-only Coach has a hard false-approval floor of ~6/16 ≈ 38%** on this holdout — those verdicts are
  not a function of the input. The v2 LoRA (62.5%) closed **~half** the base→floor gap (94 → 62.5, floor 38).
- The remaining ~4 inferable/partial feedback misses (e.g. `TASK-MCP-005`/`TASK-GR-LOAD`: *"Files actual: 0"
  while claiming completion*) **are** improvable — the model is still too lenient on in-report honesty/thin
  evidence tells. Our synthetic absence/honesty data targets exactly these; more of it should help.
- **Both error directions are dominated by input-incompleteness**, not model capacity. This is very likely a
  deeper driver of the v1 rubber-stamp than class imbalance alone: when the gold OUTPUT depends on signal
  absent from the INPUT, the cheapest fit is "always approve."

## 4. v3 direction (precise, two-pronged)

**(A) Fix the INPUT — the big lever. CONFIRMED: this is a train≠serve mismatch, not a serving gap.** The
live autobuild Coach (`guardkit/orchestrator/agent_invoker.py:_build_coach_prompt`) ALREADY serves the Coach
`task + player_report + <evidence_bundle>{independent_tests, tests, coverage, bdd, plan_audit, arch_review,
honesty, wiring/mocked_seam/spec_gap, runtime_parity} + 7 absence-of-failure guards`, in **toolless
synthesis** mode (decide entirely from the bundle). But the harvest (`curate_coach_dataset.py:render_prompt`)
built the training prompt from `player_report` ONLY — **dropping the evidence bundle**. So v3 needs **NO
serving change**; it must **re-harvest training data to MATCH the production prompt** (ideally by reusing the
production `_build_coach_prompt` so train==serve byte-for-byte). With the evidence present, the 6
"uninferable" feedback cases become inferable (bundle says independent BDD failed → feedback).
> Re-interpret v2: because the harvest dropped the bundle, v1/v2 trained the Coach on an input distribution
> the production Coach never sees — ill-posed AND off-distribution. The first v3 experiment is cheap and may
> moot the fine-tune: **eval the base `gemma4-coach` WITH the evidence bundle (production format)** — if the
> base + bundle + guards already lands both rates < ~20%, the rubber-stamp was purely a harvest artifact.

**(B) More pressure on in-report honesty/thin-evidence tells.** Scale the synthetic `absence-of-failure` /
honesty / unverified-AC cases (the generator is proven + cue-gated) and/or a modest feedback-lean, to close
the ~4 improvable misses. (Pure ratio-tuning only slides the FA/FF tradeoff; more diverse data moves the
frontier.)

**Re-eval gate (unchanged):** false-approval AND false-feedback both < ~20% on a balanced holdout **whose
prompts include the verification section** (so the task is well-posed).

## 5. Status of artifacts
- **Best Coach so far:** `~/fine-tuning/output/coach-gemma4-26b-moe-v2/` (lora-adapter / merged-16bit /
  gguf_gguf q4_k_m). FA 62.5% on balanced real — **better than base (94%) but NOT deployable.** Keep base
  `gemma4-coach` as production.
- **Reusable pipeline** (`domains/coach-agent/`): `build_lora_corpus_v2.py`, `prepare_coach_sft.py`,
  `assemble_synthetic_v2.py`, `audit_cue_leakage.py`, `finalize_v2_corpus.py`, `extract_workflow_rows.py`,
  `fewshot_eval_coach.py`, `eval_coach.py` (now `--holdout-file` + sdpa fix), `train_coach_moe.py`.
- **Eval sets:** `holdout_balanced_real.jsonl` (the honest balanced gate), `synthetic_v2final_holdout.jsonl`.

## 6. Talk / video takeaways
1. **The loss function lied (v1); the holdout balance lied (v1); and in v2 — the *prompt* lied.** Three
   layers of "the metric/setup is hiding the real task." The deepest one: the Coach was being trained to
   predict a label that depended on evidence it was never shown.
2. **A dataset factory auditing its own data** caught lexical *and* numeric shortcuts across three rounds via
   an automated gate — then the cue-immune real holdout caught the thing the gate couldn't: an ill-posed
   input. Adversarial verification at every layer.
3. **The fix is recursive and unglamorous:** give the Coach the same evidence the judge had. Most "model
   can't do X" is "we never put X in the input."
