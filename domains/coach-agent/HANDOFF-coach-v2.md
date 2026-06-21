# HANDOFF — Coach fine-tune: v1 (rubber-stamp) → v2 (rebalanced synthetic data)

**Date:** 2026-06-20 · **For:** the next session (fresh context) · **Companion docs (read first):**
`RETRO-coach-finetune.md` (full story + lessons), `RUNBOOK-coach-fine-tune.md` (how to train),
`SERVING-coach-ft.md` (how to serve/eval), `RESEARCH-gemma4-qat-decision.md` (QAT decision).

---

## TL;DR

v1 Coach LoRA **trained and serves cleanly but is a RUBBER-STAMP** (87.5% false-approval) — **do not
deploy it.** Root cause = corpus class-imbalance (81% approve / 19% feedback), not the recipe. **v2 =
generate balanced *failure* data synthetically with this factory's Player–Coach loop**, grounded in
the `guardkit/.claude/rules/` failure taxonomy, then retrain and gate on a *balanced* holdout.
**Next concrete step: build a small taxonomy-driven prototype generator (option a) and validate it on
~40–60 examples before scaling.** Keep base `gemma4-coach` as the production Coach meanwhile.

---

## Current state

| Thing | State |
|---|---|
| Production Coach | **base `gemma4-coach`** (UD-Q4_K_XL) in llama-swap — unchanged, keep it |
| v1 fine-tune | trained, **NOT deployed** (rubber-stamp). Artifacts root-owned, kept for reference |
| Fleet | restored & healthy (llama-swap + forge-prod + sidecars) |
| Pipeline/scripts | working & validated end-to-end (the reusable asset) |

### Artifact map
- **Scripts/docs** (this repo): `domains/coach-agent/` — `prepare_coach_sft.py`, `train_coach_moe.py`,
  `eval_coach.py`, `RUNBOOK-…`, `SERVING-…`, `RESEARCH-…`, `RETRO-…`, this handoff.
- **v1 model** (root-owned): `~/fine-tuning/output/coach-gemma4-26b-moe/` — `lora-adapter/` (1.9 G),
  `merged-16bit/` (49 G), `gguf_gguf/gemma-4-26b-a4b-it.Q4_K_M.gguf` (17 G). Eval reports:
  `~/coach-dataset/curated/eval_coach_ft.json`.
- **Dataset**: `~/coach-dataset/curated/` — `train_final.jsonl` (447: 363 approve / 84 feedback after
  the 2026-06-20 fixes), `holdout_eval.jsonl` (76), `hard_cases.jsonl` (8, fixed),
  `hard_case_seeds.jsonl` (the 8 **authoring_templates** — the v2 scaffold).
- **Failure taxonomy** (the v2 grounding): `guardkit/.claude/rules/` — `absence-of-failure-is-not-success.md`,
  `per-task-green-is-not-feature-green.md`, `path-string-mismatch-is-not-dishonesty.md` (approve-trap),
  `evidence-boundary-narrower-than-write-surface.md`, `smoke-gate-is-feedback-not-terminator.md`,
  `namespace-hygiene.md`, `harness-cancellation-contract.md`, `stack-plugin-architecture.md`.
- **Factory pipeline**: `agents/{player,coach}.py`, `prompts/{player,coach}_prompts.py`,
  `entrypoint/generation_loop.py`, `domain_config/` (GOAL.md mechanism), `config/coach_verdict.py`,
  `docs/design/models/DM-coach-rejection.md`. Existing harvest/curate: `guardkit/scripts/*coach*.py`.

### Cleanup (root-owned → needs sudo)
The coach **smoke dir was already removed** (verified gone 2026-06-20). Only the v1 intermediate
checkpoints remain from this work:
```bash
sudo rm -rf ~/fine-tuning/output/coach-gemma4-26b-moe/checkpoint-*   # ~5.8 G (checkpoint-100/179)
```
Unrelated bonus reclaim: a stale `~/fine-tuning/output/architect-agent-gemma4-26b-moe-smoke` (~52 G,
from the May architect run) is also safe to `sudo rm -rf` if you want the space.

---

## What v1 proved (reusable) vs what failed

**Proved (keep):** QAT decision (reject base swap; keep bf16 `unsloth/gemma-4-26b-a4b-it`; serve
UD-Q4_K_XL, never q4_0); non-thinking `gemma-4` template; COACHSPLIT schema reshape
(`--coachsplit-schema`); the 5 baked-in trainer guards; the memory watchdog + step-probe pattern;
clean serving with `--reasoning off` (no token leaks); schema training transfers (emits
`{task_id,turn,decision,…}` with the identity prompt).

**Failed:** judgment. **false-approval 87.5%** (holdout), 11.8% correct on in-train hard-cases,
96% approve rate. `train_loss 0.162` was format + majority-class fit, not judgment.

---

## Carry-forward gotchas (hard-won — don't relearn these)

1. **GB10 memory ceiling = seq 4096.** seq ≥6144 OOM-*climbs* over the epoch (alloc high-water grows
   ~6 GB/40 steps; 8192→114 G, 6144→112 G); `PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True` only
   shifts ~5 G. Judge by the **step-40/80 plateau, not step 1**. seq 4096 peaks a stable ~61 G.
   *(The 2nd GB10 unlocks seq 8192 via multi-node sharding — but that does NOT fix the rubber-stamp.)*
2. **Always run training behind the memory watchdog** (`docker kill` if avail RAM < ~8–11 GB) — a
   freeze needs a power-cycle. Pattern is in the runbook.
3. **Fleet stop/restore is mandatory before any GB10 training** (freeze prevention):
   stop → `systemctl --user stop forge-autobuild-runner forge-langgraph-sidecar llama-swap; docker stop forge-prod`;
   restore → reverse order, `systemctl --user start llama-swap` first, `reset-failed` the runner if needed.
4. **Eval must be on a BALANCED holdout**, and report **false-approval + false-feedback** — not just
   correct-verdict (which is gameable by the majority class). Use `max_tokens ~48` (decision is first)
   to keep eval fast & light; the slow stall in v1 was 1536-token generations under fleet contention.
5. **`pkill -f <pattern>` self-matches the shell** (the pattern text is in the cmdline) → exit 144.
   Kill by PID instead.
6. **Grammar IS applied** by llama-server (`grammar` field on `/v1/chat/completions` works — verified).
   The coach-verdict grammar's free `prefix` lets the model emit a natural block first, then the
   forced verdict; the base needs the **strict** grammar to emit early, and its verdict lands in
   `reasoning_content` (not `content`) under `--reasoning auto`. `eval_coach.py` now reads both.
7. **Docker run gotcha:** pre-`mkdir -p` the host output dir before `docker run … > host.log` (the
   shell opens the redirect before the container's internal mkdir).

---

## v2 plan (the fix) — synthetic balanced failure data

**Goal:** corpus ~50/50 approve/feedback with realistic, taxonomy-grounded failure cases + matched
approve controls + approve-traps. Then retrain (seq 4096 recipe unchanged) and pass the balanced gate.

**Generation modes (do both):**
- **Taxonomy-driven (start here):** per rule × manifestation × varied synthetic task domain →
  `(Task + flawed Player report + ideal feedback verdict)`. Use `hard_case_seeds.jsonl`
  `authoring_template`s + the rule files (each lists concrete real incidents) as the flaw source.
- **Adversarial emergent (phase 2):** factory's Player–Coach loop — adversarial Player sneaks a flaw
  past, teacher Coach (Claude) catches → feedback; teacher misses → relabel as a hard case.

**Non-negotiable quality controls:**
- **Matched pairs**: `(clean→approve, same-task-flaw-injected→feedback)` so it learns the *boundary*.
- **Keep approve-traps** (path-string-mismatch style: scary but genuinely fine → approve) so the model
  doesn't become an **over-rejector** (the opposite failure).
- Diversity across task domains / failure manifestations / report styles.
- **Provenance-tag** all synthetic (`source: synthetic_*`) so it stays filterable.
- **Balanced eval gate:** ~50/50 holdout; ship only if **false-approval AND false-feedback < ~20%**.

**Rough numbers:** from 363 approve / 84 feedback → generate ~300–500 synthetic (≈⅔ feedback, ⅓ clean
controls/traps) → ~50/50 corpus of ~750–900 rows.

---

## >>> NEXT STEP: the prototype (option a) <<<

**Build a small, controllable taxonomy-driven generator and validate before scaling.** Don't wire the
full factory loop yet — prove the data transfers judgment first.

### Step 0 — orient (10 min)
- Read `entrypoint/generation_loop.py`, `prompts/player_prompts.py`, `prompts/coach_prompts.py`,
  `domain_config/` (the GOAL.md mechanism), `config/coach_verdict.py`. Decide: extend the factory's
  GOAL.md/domain path, or write a focused standalone generator that reuses the same Claude client +
  the COACHSPLIT verdict schema (`prepare_coach_sft.py:to_coachsplit_schema`). **Recommend standalone
  first** for control; fold into the factory once the recipe is proven.
- Read all 8 rule files in `guardkit/.claude/rules/` + `hard_case_seeds.jsonl` (the templates).

### Step 1 — generate a balanced smoke batch (~40–60 rows)
For each of the 8 rules, generate via Claude (strong model, e.g. Opus):
- **N feedback cases**: realistic synthetic Task (ACs) + Player report exhibiting that failure mode +
  ideal `{task_id,turn,decision:"feedback",…}` verdict naming the specific gap (cite the rule).
- **A matched approve control**: same Task, *clean* report → `approve`.
- For `path-string-mismatch` (and 1–2 others), an **approve-trap**: scary symptom that's genuinely
  fine → `approve`.
Output in the **same schema** as `train_final.jsonl` (`prompt`/`completion`/`decision`/`source:
synthetic_v2`/rule tag). Reuse `to_coachsplit_schema` so verdicts are grammar-conformant.

### Step 2 — build a BALANCED holdout (~30 cases, ~50/50)
Hold out a balanced slice (and/or hand-pick from real `holdout_eval.jsonl` feedback + new synthetic).
This is the honest gate — v1's holdout was 79% approve and lied.

### Step 3 — quick judgment check (no full retrain)
Cheapest signal first: **few-shot the base `gemma4-coach`** (or a tiny LoRA on just the smoke batch)
and eval on the balanced holdout with `eval_coach.py` (max_tokens 48). Look for **false-approval AND
false-feedback both trending < ~20%**. If the synthetic data moves the needle on a small scale → scale
to the full ~300–500 and do the real seq-4096 retrain (recipe in the runbook, unchanged). If it
doesn't → the synthetic flaws aren't realistic/diverse enough; iterate on the generator, not the size.

### Guardrails for the prototype
- Validate every generated verdict parses + is grammar-conformant (`prepare_coach_sft.py` already
  gates this) and decision matches the intended label.
- Watch for **mode collapse / surface cues** (e.g. every feedback case mentions "mock") — vary phrasing
  and inject the failure structurally, not lexically.
- Keep it cheap: a 40–60 example batch + a 30-case balanced eval is a few $ of Claude calls and ~15 min.

---

## Open questions for v2
- Wire into the factory's GOAL.md/`generation_loop.py` path, or keep a standalone generator? (recommend
  standalone → fold in later).
- Best teacher model for the adversarial Coach (Claude Opus vs the existing pipeline's model)?
- Multi-node seq-8192 on the 2nd GB10 (cable ~2026-06-23): confirm Unsloth+TRL FSDP on sm_121 /
  container 25.11 — but only *after* the data is fixed.
- Mine real autobuild logs (`guardkit/.guardkit/autobuild/*/coach_*.json`) for genuine false-greens to
  mix real + synthetic feedback.
