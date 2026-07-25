# Coach v4 corpus — audit findings + the reconciled target contract
## 2026-07-25 · the no-GPU prep for the signed re-fine-tune · sets up the corpus regeneration

## Why v4 (the receipts, not the theory)

The v2 graders (fleet-evals, frozen bar) were run against the banked coach-ft-v3 answer sheets.
Result: coach-ft-v3 **fails v2 too** — not on class (correctly de-scoped to a diagnostic) but on
**LOCUS** (CE-02, CE-04, CK-02: "findings never name the in-bundle signal"). So reseating the old
tune, even under the de-scoped bar, does NOT clear it. Rich's ruling ("grading a model I know
needs redoing") is vindicated with a receipt.

## Root causes, confirmed from the v3 corpus (174 rows, `v3_sft_raw.jsonl`)

1. **The fence bug is a TRAINED behaviour.** Every v3 target is wrapped in ```json … ``` fences.
   coach-ft-v3 emits fences at serve because that is what it was trained to emit. The strict
   parser rejects them → the model was shelved. Cure: v4 targets are RAW UNFENCED JSON.
2. **Locus was never a trained target.** v3 targets use the production COACHSPLIT grammar —
   `{decision, criteria_verification, issues:[{type,severity,description}]}` — which has **no
   `locus` field**. The model never learned to name the specific in-bundle signal, so locus is
   weak (4–5/6). Cure: v4 targets carry an explicit `locus` on every finding, and locus is the
   hard target the corpus must nail.

## The three contracts, reconciled (this is the v4 target contract)

| contract | shape | verdict |
|---|---|---|
| v3 training corpus | `{decision, criteria_verification, issues:[{type,severity,description}]}` FENCED | the mismatch that sank v3 |
| exam / frozen v2 bar (`instruction.md`) | `{verdict:"approve"\|"reject", findings:[{class,locus}]}` RAW | grades verdict + locus; class now de-scoped |
| **Rich's ruling → v4 TARGET** | **`{verdict:"approve"\|"reject", findings:[{locus:"<specific in-bundle signal>"}]}` RAW UNFENCED** | **decision + locus, NO class** |

The v4 target = the exam contract minus `class`, raw/unfenced. The frozen v2 grader reads
exactly `verdict` + `findings[].locus`, so train-target ≡ serve-contract ≡ exam-bar — the
three-way alignment that v3 lacked. `approve` ⇒ `findings: []`; `reject` ⇒ ≥1 finding whose
`locus` names the specific signal (a generic "not safe" fails).

## The corpus regeneration (the next work, a generation lane)

The existing v3 targets cannot be transformed into v4 — they are the wrong contract and lack
locus. The corpus must be **regenerated** so every target is a raw `{verdict, findings:[{locus}]}`
with a **strong, signal-specific locus**. Locus is the hard part (it is where v3 fell short), so
the generation must ground each finding's locus in the actual in-bundle signal, not a generic
field path. Options for the regen (design decision for the run):
- Derive locus from the bundle's known defect signal where the training bundles carry a labelled
  anchor (strongest — no teacher hallucination).
- Teacher-generate locus-bearing verdicts (the `wf_teacher_verdict_v3.js` pattern) with an
  explicit instruction to name the exact bundle field/symbol, then verify locus against the
  bundle before banking.
- Keep the `approve` rows (they need no locus) and the honest-green rows unchanged in shape
  beyond de-fencing.

## What transfers unchanged (proven v3 infrastructure)

`train_coach_moe.py`, `prepare_coach_sft.py`, `RUNBOOK-coach-fine-tune.md`, `SERVING-coach-ft.md`,
the LoRA launch scripts. The recipe changes only per the base-pick card: updated
`unsloth/gemma-4-26B-A4B-it`, Unsloth ≥ 2026.4.4, pinned llama.cpp (7 Gemma-4 PRs),
`train_on_responses_only` on the RAW JSON span, Q8_0 GGUF, `--chat-template-kwargs
enable_thinking:false`, temp 0, and — the catch — a **serve gate asserting clean unfenced parse**
before ship.

## State / next

- DONE (no GPU): v2 graders built + validated; corpus audited; v4 contract reconciled.
- NEXT (generation lane, then GPU): regenerate the corpus in the v4 contract with strong locus →
  train on the signed base → merged-gen gate → GGUF → **serve gate (unfenced parse)** → grade vs
  the v2 bar → reseat on a clear pass. The generation run and the multi-hour train confirm against
  the GPU protocol (fleet-idle-first, flock, headroom) before firing.
