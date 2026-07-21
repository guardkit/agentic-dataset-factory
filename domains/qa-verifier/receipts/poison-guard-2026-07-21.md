# Receipt — POISON GUARD: evidence-divergence refusal + the ALL-REAL corpus re-run (2026-07-21)

> **THE POISON CLASS IS STRUCTURALLY CLOSED.** The render-collapse poison — seeded_code reject
> rows banking GREEN bundles wearing reject labels (the regeneration replay is source-blind; a
> reject leg's bundle is byte-identical to its task's no-op control bundle) — can no longer be
> written. The EVIDENCE-DIVERGENCE GUARD (engine commit `d0756f5`) regenerates the CONTROL first
> per task, content-hashes it, and REFUSES any seeded REJECT candidate whose regenerated bundle
> hashes equal to that baseline: reason **`evidence_invariant_injection`**, routed to
> `rejected.jsonl` BEFORE any teacher call. The corpus re-run (`--mode both`, 19m02s wall)
> confirmed it live: **32/32 seeded reject legs refused, seeded reject rows = 0, and the corpus
> is now ALL-REAL — 35 rows = 20 harvest + 11 controls + 4 golds, 35/35 contract-valid,
> contamination PASS twice.** A bonus the root-cause receipt predicted: refusing the poison
> FREED 4 controls the reject legs had been dedup-cannibalizing (controls 7 → 11).

Engine commit: `d0756f5` (guard + tests + driver DONE-line). Run at HEAD `d0756f5` (recorded in
the manifest). ed00704 validators byte-frozen — `contracts.py`/`recipes.py`/`injector.py`
untouched; recipes-anchors scope unchanged.

---

## 1. The guard (what changed, where)

`src/qav/generate.py` (additive):

- **`bundle_content_hash(bundle)`** — canonical sorted-key-JSON sha256; two bundles hash equal
  iff their evidence is byte-identical (the render-collapse identity surface).
- **`_run_seeded_code`**: per task, the no-op CONTROL worktree is materialized and regenerated
  **FIRST** and content-hashed; every reject recipe leg is then compared against that baseline.
  The control ROW is gated/written LAST from that **same single regeneration** (never a second
  draw — one control regen per task, exactly as before; the guard compares against exactly the
  bundle the control row carries, so nondeterministic-field jitter cannot split them).
- **`_gate_and_build`**: a REJECT candidate whose bundle hash equals `control_bundle_hash` is
  refused — reason `evidence_invariant_injection`, with the shared `bundle_content_sha256` in
  the reject record. Ordered AFTER the evidence-empty pre-gate (the more fundamental refusal
  wins) and BEFORE the teacher (a refused candidate costs zero model legs). Belt-and-braces:
  only `verdict == "reject"` can be refused — controls/approves never carry the hash and their
  approve label describes the real record, unaffected by construction.
- **Loudness**: per-refusal `WARNING` + an aggregate `EVIDENCE-DIVERGENCE GUARD: N seeded
  reject candidate(s) REFUSED…` warning + `summary.evidence_invariant_rejected` + the driver's
  DONE line (`domains/qa-verifier/run_qav_generation.py`).

## 2. Guard behavior proven hermetically (stub regenerators, zero model/GPU)

`tests/test_qav_generate.py` (+4 tests):

| test | stub | proves |
|---|---|---|
| `test_source_blind_reject_refused_control_still_banks` | `SourceBlindRegenerator` (ONE static bundle for every worktree — the render-collapse shape) | reject leg REFUSED with `evidence_invariant_injection` + the shared content sha; **control still banks** as the only row (approve, `R-CONTROL-noop`, validate_row-VALID); teacher called ONCE (the control's rationale only); refusal ≠ dedup |
| `test_divergent_reject_banks_normally` | `DivergentRegenerator` (control → green, mutated → genuinely different bundle) | guard silent, reject banks carrying its OWN divergent evidence, `rejected.jsonl` empty |
| `test_source_blind_refusal_covers_every_reject_leg_of_a_task` | source-blind, 2 anchoring recipes | BOTH legs refused, one control banks |
| `test_evidence_empty_still_wins_over_divergence_guard` | `PoisonRegenerator` (identical AND evidence-empty) | the round-3 evidence-empty pre-gate fires first; guard counter stays 0 |

Full suite: **`uv run --no-sync pytest -q` → 2454 passed** (2450 baseline + 4 new), zero
failures, zero network (the socket-poison test still passes through the new path).

## 3. The corpus re-run (`--mode both`, fresh-start)

| | |
|---|---|
| invocation | `nohup flock -x /var/lock/llama-swap-keepalive.lock env OPENAI_API_KEY=local PYTHONPATH=src ./.venv/bin/python domains/qa-verifier/run_qav_generation.py --config domains/qa-verifier/agent-config.yaml --mode both` |
| launched / finished | 2026-07-21 **20:37:55** → DONE **20:56:57** BST · **19m02s wall** (2h wall: 15.9% used) · pid 2049830, active short-polls |
| log | `run_logs/poison-guard-run-20260721-203755.log` — **zero tracebacks, zero 500s/retries** (the growth-cycle-1 parse-abort did not recur this draw) |
| fleet | `:9000`; teacher `gpt-oss-120b`, coach `qav-coach`; `/running` at finish = exactly the `qav` set + audio pair |
| keepalive | timer **ACTIVE** at start → ratified flock-guard held (timer NEVER touched, left `active`); journal proof: every fire in the window (20:40:56 · 20:45:58 · 20:51:00 · 20:56:02) logged `"Another keep-alive run is in progress; exiting."` — no revive, no OOM exposure |
| s2s | untouched; audio pair (parakeet-tdt-0.6b-v3 + qwen3-tts-0.6b) resident throughout and at finish |
| baseline | prior 34-row corpus snapshotted to session scratchpad + preserved in-tree by the driver's own `*.bak` swap |

**Run tallies (DONE line):** `seeded_code=0 control=11 seeded_bundle=0 harvest=20 gold=4
harvest_skipped=4 harvest_bundle_not_found=0 teacher_refused=0 coach_rejected=0 cue_rejected=0
evidence_empty_rejected=0 evidence_invariant_rejected=32 schema_rejected=0 anchor_skipped=111
gold_source_skipped=0 deduped=4 train=26 eval_qav=9 manifest_finalized=True`.

## 4. The refusal count — 32, exactly the render-collapse legs

`rejected.jsonl`: **32 records, ALL `evidence_invariant_injection`** (no other turn-away this
run). By task × recipe — precisely the discovered guardkit legs whose replay is source-blind:

- guardkit TASK-QAWE-001/-002/-003/-004: **6 each** (R-ABSENT-junit · R-DC03-callsite ·
  R-DC03-mockseam · R-DC03-producer · R-DC05-skipguard · R-DC05-sysmod)
- guardkit TASK-BDDW-001/-002: **4 each**
- study_tutor: 0 refusals — its 11 recipes still don't anchor (`anchor_skipped=111`, unchanged;
  the expected-miss discipline holds, no anchor added)

The 4 previously-banked poisoned seeded rejects (3 train + 1 eval DC-08 `R-ABSENT-junit` rows
riding green bundles) **vanished into these refusals** — and their 4 cannibalized controls
came back (`deduped` collapsed 66 → 4: the only remaining collisions are 2 cross-task
control-bundle twins, ×2-counted).

## 5. The clean corpus — ALL-REAL, by side / split / mode / DC-class

**35 rows banked (26 train / 9 eval_qav) · 35/35 `validate_row`-VALID · seeded reject rows = 0.**
Every row is now a real record: harvest (ratified labels) + seeded controls (honest green
regenerations wearing approve) + gold negatives.

| split | verdict | mode | dc_class | n |
|---|---|---|---|---|
| train | approve | harvest | — | 13 |
| train | approve | seeded_code (controls) | — | 10 |
| train | reject | harvest | DC-03 | 3 |
| eval_qav | approve | harvest | — | 2 |
| eval_qav | approve | seeded_code (control) | — | 1 |
| eval_qav | reject | harvest | DC-03 | 2 |
| eval_qav | reject | gold_negative | DC-03 | 3 |
| eval_qav | reject | gold_negative | DC-08 | 1 |

By side: **harvest 20 (20/20 consumable labels consumed, zero misses — the cycle-1 stochastic
coach-rejection did not recur) · controls 11 (guardkit 4 + study_tutor 7) · golds 4** =
harvest + controls + golds, nothing else. Per-repo: forge 11 (10 harvest + 1 gold) ·
study_tutor 14 (5 harvest + 7 controls + 2 golds) · guardkit 7 (2 harvest + 4 controls +
1 gold) · api_test 1 · nats_core 1 · jarvis 1.

Delta vs growth-cycle-1 (34): **−4 poisoned seeded rejects, +4 freed controls, +1 harvest row
recovered** → 35.

## 6. Manifest verdict — honest

`domains/qa-verifier/manifests/qav-phase1-train.manifest.json` (= `output/qa-verifier/manifest.json`,
sha256 `cc4ee8e9f4da1384…`; factory_sha **`d0756f5`**, dataset `qav-phase1-train-v1`, private DF-008):

- **`contamination_check: PASS`** (intersection 0 · sibling-variant 0 · gold-source 0) — and the
  standalone `scripts/qav_contamination_check.py` re-ran clean: **VERDICT: PASS**.
- **`approve_share = 0.8846`** → `MANIFEST BALANCE ADVISORY FAIL` (outside 0.50±0.10), logged
  loudly at 20:56:57, rows banked, manifest written honestly. **Known and expected:** removing
  the 3 poisoned train rejects worsens the ratio arithmetic (0.76 → 0.88) — but those "rejects"
  were mislabeled green bundles; a balance number propped up by poison was a lie. Real reject
  volume remains the standing engine-external lever set (ratified curation batches ·
  seeded_bundle provenance · the GB10 regeneration redesign).
- `ugly_green_share_of_approves = 0.9565` → the ≥0.45 floor PASSES.
- train-side by_generation_mode: harvest 16 / seeded_code 10 (all approve controls) — by_dc_class
  DC-03=3 (real merge_review_caught), every seeded DC class = 0, as it must be under the guard.

## 7. Venue — untouched

Corpus repos read-only, HEADs identical before/after and to the prior receipts: guardkit
`b68c9e9d` · study-tutor `f843cb5` · forge `686439c` · api_test `9066286` · nats-core `2c060b2`
· jarvis `1fc7309`. Seeded scratch worktrees cleaned per leg. Timer left `active`; fleet state
at finish = the `qav` set + audio pair, zero evictions.

## 8. Artifacts + provenance

- `output/qa-verifier/train.jsonl` — 26 rows · sha256 `d810c01dba6c163d24504180b685bf62bd0855e51e8106c1237f52dd2f11d6dd`
- `output/qa-verifier/eval_qav.jsonl` — 9 rows · sha256 `96d98365445d5c52f8bb41c8fdc89546712efd556730f9e9a576fe8a4b942b1a`
- `output/qa-verifier/rejected.jsonl` — 32 refusal records · sha256 `917a91b5ff7904478e21f76d131c99b30fa5752094da3b8e79a2f83abd4a3be4`
- manifest (both copies byte-identical) — sha256 `cc4ee8e9f4da138499391035eaf14738462afaefdfd43e5b6dd92bd3eadb1c1d`
- engine commit `d0756f5` · run log `run_logs/poison-guard-run-20260721-203755.log`
- prior-corpus baseline: `output/qa-verifier/*.bak` + session-scratchpad snapshot
- Datasets private (DF-008). **No push.**
