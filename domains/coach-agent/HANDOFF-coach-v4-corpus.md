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
- **DONE 2026-07-25 evening — THE CORPUS IS REGENERATED + VERIFIED (`build_v4_sft.py` →
  `v4_sft_raw.jsonl`, 174 rows, 94 approve / 80 reject).** Grounding choice = the strongest
  option: locus DERIVED deterministically from the labelled `bundle_spec` anchors in
  `v3_train_specs.jsonl` (no teacher, no hallucination, no GPU generation run). Build-time hard
  gates all pass: every completion parses raw/unfenced with exactly {verdict, findings:[{locus}]};
  every cited token verified verbatim-present in its own prompt; all 80 loci unique; verdict
  counts match the audited v3 base. Prompt transform: the `## Decision Format` block replaced
  with the v4 raw-JSON contract; old-grammar vocabulary above the seam rewritten
  (criteria_verification imperative, "Surface as feedback", '"feedback" decision', "in the
  rationale") — **these same rewrites must be mirrored in guardkit's coach prompt assembly at
  reseat (train==serve prompt parity)**.
- **Verification receipts:** deterministic cue-leakage gate PASS on the player-report surface
  (max DF-diff 0.05, cue coverage 0.0%; NOTE: `audit_cue_leakage.py`'s `## Player report` marker
  does not match these prompts' `## Player's Report` header — feed it the report field, or it
  silently audits the whole prompt and false-FAILs on bundle determinism). Adversarial
  multi-agent audit run `wf_6c936265-877` (23 agents, 125 rows): 14 blocking → all triaged; the
  two v4-side defects FIXED (instruction imperative; g6 locus now cites BOTH
  `tests_passed=false` AND `signal_absent=true`, never recasting present failure as absent);
  phrasing rotation added for monoculture connectives. The v2-bar conformance agent EXECUTED 20
  targets through the real frozen `verdict_schema_findings_v2`: zero findings. Post-fix
  cold-read: CLEAN.
- **Residue ledger (inherited bundle-authoring, NOT re-opened in this lane — a future
  bundle-generator fix list):** (1) all 5 g6 bundles pair `signal_absent=true` with a decisive
  completed failure summary + `duration_seconds=120` contradicting the in-summary time; (2) 4
  g7_wiring bundles assert physically impossible states (wiring says a file doesn't exist while
  BDD passes 3/3 on it); (3) bdd_failed bundles report scenarios_failed=2 but itemize 1 failure;
  (4) the 4 trap_g4_path discrepancies are labelled `file_existence` but describe real
  functional defects — golds kept (in-bundle `severity_recommendations` instruct the demotion;
  coach-ft-v3 trained on the same golds and still rejected all exam escape-kin); the disjoint v2
  exam is the arbiter; (5) numeric monoculture (coverage=71 ×4, "2 of 3" ×10) is bundle-side;
  (6) guard-prose polish for reseat: guards 1/2 suggest message-shaped locus text, guard 4's
  "should_fix" has no output channel, guard 7's command-then-advisory contradiction.
- **Staged on the GB10:** `~/fine-tuning/data/train-coach-v4.jsonl` (174 ShareGPT rows,
  `--weight-mode none --no-fence --no-coachsplit-schema`; leakage 0/174; the staging script's
  "malformed verdict" warning = its old-grammar validator not knowing v4 — expected).
  `run_coach_v4_smoke.sh` + `run_coach_v4_full.sh` deployed (deltas: gemma-4-thinking template,
  GGUF q8_0, unsloth ≥ 2026.4.4 gate, in-container REAL-tokenizer seq audit as the 4096-vs-6144
  decision gate; est p99=4161/max=4163 @3.5 chars/tok — 3 rows straddle 4096, ground truth
  decides). Base cache verified: `refs/main` = `60941ad6` == HF latest (the updated "Gemma 4
  Fixes" release, lastModified 2026-07-17). Pinned llama.cpp built clean at `720d7fa4`
  (2026-07-25 master, all July Gemma-4 fixes) in `~/llama.cpp-gemma4-jul25` — the live
  `llama.cpp-new` (2026-05-30) predates the fixes and stays untouched for serving.
- NEXT (GPU): smoke (60 steps, [G2] framing = THE CATCH check) → full train → merged-gen gate →
  GGUF q8_0 via the pinned build → **serve gate (unfenced parse)** → grade vs the v2 bar →
  reseat on a clear pass. The train confirms against the GPU protocol (fleet-idle-first, flock
  keepalive at `/var/lock/llama-swap-keepalive.lock`, `/unload`, headroom, mem watchdog,
  release by exact fd-holder PID) before firing.
