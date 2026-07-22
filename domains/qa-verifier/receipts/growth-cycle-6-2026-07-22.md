# RECEIPT — Growth cycle 6 (2026-07-22; `--mode both`, factory_sha `8138f44`)

> Take 1 (launched 19:01) CRASHED at 20:01 on a fence-bearing teacher `<think>` —
> `json.JSONDecodeError: Extra data` escaping `parse_assistant_content` inside `build_row`, an
> uncaught mid-run kill (full traceback in `run_logs/qav-growth-cycle6-20260722-190106.log`).
> Root-caused and fixed as `8138f44` (ValueError incl. JSONDecodeError at both `build_row` sites
> is now a loud `schema_invalid` RESULT, both poison shapes regression-tested). This receipt is
> **RUN take 2** on that fix.

# RUN take 2

The first cycle to run on top of the two cycle-6 levers — the **recovered guardkit
source-package pins** (`guardkit-shadow-claim-recovery-2026-07-22.md`: R-DC03-producer +
R-DC03-callsite, the falsified editable-install shadow claim) and the **jarvis DC-05 anchor**
(`anchor-diversity-dc05-jarvis-2026-07-22.md`: jarvis's 2nd DC-class) — plus the `8138f44`
totality fix. The run COMPLETED clean where take 1 died: same levers, same corpus walk, no crash.
Both levers minted real rows and the refusal well kept draining (evidence-invariant 12 → 6, the
residual now being ONLY the proven-inert R-DC05-sysmod) — but the NET gain was **+8 (+8.0%)**,
below the 10% plateau bar. **PLATEAU is called** (arithmetic in §Plateau).

## Ops — take 2 launch hygiene (the traps, named)

- **Stale self-matching monitor from take 1 killed before anything else** (PID 1600055 — a
  `while pgrep -f "run_qav_generation"` loop whose own cmdline matched its own pattern; it had
  spun 3.5 h and would have polluted every bracketed process check).
- **The `.bak` bank was about to be destroyed and was saved first.** Take 1's launch banked the
  100-row cycle-5 corpus to `*.bak`, then crashed leaving PARTIAL live files (train 32 / eval 6 /
  rejected 6, no manifest). `OutputWriter._backup` REPLACES `.bak` unconditionally, so a naive
  relaunch would have overwritten the 100-row bank with the partial garbage. Fix: take-1 partials
  stashed (scratchpad), `.bak` → live restored (verified 82/18/15 + manifest = the exact cycle-5
  state), THEN launched — so launch re-banked the true 100-row corpus. Verified post-launch:
  `train.jsonl.bak` 82 · `eval_qav.jsonl.bak` 18 · `rejected.jsonl.bak` 15 · `manifest.json.bak`.
- Launched detached (nohup, driver PID 2094594) **22:40:34**; DONE **00:16:08.657** →
  **wall 1h35m34s** (vs cycle 5's 1h19m14s; the recovered guardkit source-package legs + jarvis
  DC-05 legs are the growth). Actively polled in-turn every few minutes (bracketed pgrep via
  pidfile + log-advance + traceback scan); zero tracebacks.
- Keepalive PAUSED throughout via Rich's standing flock hold (PID 1185504, verified alive before
  launch and at close-out). s2s (parakeet + qwen3-tts) alive throughout. Corpus repos read-only.
  Full snapshot: `output_backup_qav-growth-cycle6-take2-20260723-002149`.

## Corpus before → after (by side)

| Side | Cycle 5 | Cycle 6 | Δ |
|---|---|---|---|
| train | 82 | **86** | +4 |
| eval_qav | 18 | **22** | +4 |
| **TOTAL** | **100** | **108** | **+8 (+8.0%)** |

train by mode: seeded_code 54 → **57** · harvest 22 (0) · seeded_bundle 6 → **7**.
eval_qav by mode: seeded_code 7 → **10** · harvest 7 → **8** · gold_negative 4 (holdout intact).
Pipeline writes this run (DONE line): seeded_code=40 · control=27 · seeded_bundle=7 · harvest=30 ·
gold=4; **deduped=14** (unchanged) · anchor_skipped=**252** (was 256) · teacher_refused=0 ·
coach_rejected=**4** (was 2) · cue_rejected=1 · evidence_invariant=**6** (was 12) ·
**schema_rejected=0**.

## Attribution — what each cycle-6 lever contributed

1. **Recovered guardkit source-package pins (shadow-claim lane): +7 rows.**
   R-DC03-producer **3 train** + R-DC03-callsite (guardkit) **4 train** — all previously refused
   as evidence-invariant no-ops under the false shadow claim. One further producer candidate was
   coach_rejected. **Guard refusals halved again, 12 → 6, and the residual 6 are ALL
   R-DC05-sysmod** — the proven-inert stub (guardkitfactory genuinely installed), the honest
   structural cap the lane predicted. The evidence-invariant well is now EMPTY of recoverables.
2. **jarvis R-DC05-skipguard (anchor-diversity lane): +3 eval_qav rows** (one further candidate
   coach_rejected). jarvis DC-class count 1 → 2 is live in the corpus (DC-08 + DC-05);
   anchor_skipped 256 → 252. The lane projected +1 distinct row; sampling minted 3 (all eval side).
3. **Fence-poison rejections (the `8138f44` totality fix): schema_rejected = 0.** The teacher
   emitted zero fence-bearing thinks this run, so the new loud-reject path never fired live. Its
   demonstrated value is (a) take 1 — the identical corpus walk KILLED by exactly this poison at
   20:01 — and (b) the run completing end-to-end on the fix. Honest count: 0 caught this run.

Net arithmetic: +10 lever rows − 2 sampling displacements (train DC-08 9 → 8 among them) +1
seeded_bundle +1 harvest = **+8**. `rejected.jsonl` (11, was 15): evidence_invariant 6 ·
coach_rejected 4 · cue_leakage 1.

## Manifest verdict — HONEST, all laws PASS

- **contamination_check.status = `pass`** — row_id intersection 0, sibling-variant violations 0,
  gold-negative source-task violations 0. **Standalone gate re-run post-finish: VERDICT PASS.**
- **balance PASS.** `approve_share` **0.4767** (41 approve / 45 reject), inside 0.50±0.10;
  `ugly_green_share_of_approves` **0.9512** (≥0.45).
- train `by_dc_class`: DC-03 **27** (was 23) · DC-05 3 · DC-08 8 (was 9) · DC-14 **7** (was 6) ·
  DC-12 0. `by_ground_truth_source`: seeded 60 → **64** · coach_correct 15 · merge_review_caught 4
  · operator_caught 2 · live_gate_caught 1.
- **Self-verify: 108/108 rows re-validate against OUTPUT-CONTRACT (0 failures).**
- visibility `private (DF-008)`; factory_sha **`8138f44`**; bundle_schema_sha `41a0ebe457`;
  train sha256 `5706f19eac0b3e3ec597d20a22b3ee45bfc334cb5db9ee0c197cd2b2ca9d3d7e`.

## FLOOR CHECK (Option A, ratified: total ≥ 250 AND all laws passing)

**NOT AUTO-GO-ARMED — 108 < 250.** All laws pass (contract, contamination, balance), but the
count floor is not met. **The tune does NOT start.**

## PLATEAU — called plainly, with this run's own arithmetic

**+8 on the 100-row baseline = +8.0% < 10%. The plateau clause FIRES.** The measured ceiling:

- **Every candidate this run generated = 133** (108 written + 11 rejected + 14 deduped). Perfect
  conversion of every recoverable reject (+5; the 6 evidence-invariant are proven inert) and every
  deduped candidate (+14, which would require 14 distinct new anchor shapes) still lands at
  **127–133 ≪ 250**. The current mechanism set CANNOT reach the floor even at 100% yield.
- **The only large pool is `anchor_skipped=252`** unseeded task×recipe cells, and this cycle
  measured its real conversion rate: two full SPIKE-validated lanes found **3 viable constructs**
  (producer, guardkit-callsite, jarvis-DC05) out of 5 attempted cells (2 honest ceilings recorded:
  R-DC05-sysmod inert, study_tutor DC-05 control-red) and netted **+8**. Dedup collapses each new
  (sha-group × mutation-shape) to ~1–4 distinct rows — jarvis's 4 tasks at one sha minted 3.
- **Ceiling arithmetic to 250:** need +142 distinct rows ≈ **40+ new viable (sha-group ×
  recipe) constructs** at the measured ~3-per-cycle discovery rate with rising cost — ≈ **18 more
  cycles of equal lever quality**, against a construct supply the tree has already shown to be
  thinning (3 found / 5 attempted this cycle, refusal well now empty of recoverables).
- **Conclusion: 250 is not reachable by iterating the current loop.** The path forward is a NEW
  mechanism class — more corpus repos/shas ratified consumable (grows discovery itself),
  new recipe families (new DC-classes), or a ratified provenance expansion for seeded_bundle
  (`no_provenance=52` cap) — not more cycles of this one.

## Serving

- **Instrument failure, honest:** the take-2 co-residency sampler wrote empty payloads (nested
  bash -c quoting broke its parser; 286 samples, all bare timestamps —
  `run_logs/qav-cycle6-take2-coresidency.log`). The cycle-5-style % is therefore NOT available.
- **Reconstruction from hard process evidence + the llama-swap log:**
  - **qav-coach: resident 100% of the run** — its llama-server (PID 1184036) started 16:36:16,
    before cycle 5 finished, and was still the serving process after take-2's DONE. Zero coach
    evictions; the co-resident `qav` set held.
  - **gpt-oss-120b: one idle-TTL unload/reload** — the serving process at run-end (PID 2196963)
    started **23:17:14**, i.e. the teacher cold-reloaded once mid-run and stayed resident the
    final 59 min. The unload sits in llama-swap's log (`TTL of 600s reached`) and lines up with
    the run's only ≥10-min teacher-idle gap: the CPU-bound guardkit `R-ABSENT-junit` /
    `TASK-BDDW-001` leg (23:02 → 23:16). Same artefact class and count as cycle 5's single
    idle-TTL unload — **no competitive/mutual eviction either direction, no thrash.**

## Times

- Launch 2026-07-22 **22:40:34** → DONE 2026-07-23 **00:16:08.657** = **1h35m34s** wall.
- Take 1 for the record: 19:01:06 → crashed 20:01 (~1h00m in, mid seeded_code).
- Post-finish close-out (census + 108-row self-verify + standalone contamination gate + snapshot)
  all green same session.
