# QAV v2 — ATTRIBUTION-CORPUS RETRAIN receipt (train + gate + S4 + the hang)

**Date:** 2026-07-23 · **Lane:** QAV ATTRIBUTION CORPUS + v2 RE-EXAM (ai-transition §7, claim
13b213d) · **Corpus receipt:** `attribution-corpus-2026-07-23.md` (adf `18b9084`; manifest
committed `a39f24c`) · **Seq receipt:** `tune-v2-seq-2026-07-23.md` (`4ac6c82`) ·
**Machine:** DGX Spark GB10 (121 GB unified) · **Container:** `qav-ft-20260723`
(nvcr.io/nvidia/pytorch:25.11-py3, same deps as v1: transformers 5.5.4 / trl 0.26.1 /
accelerate 1.10.0 / datasets 4.3.0 / unsloth 2026.7.4) · **Base:** `unsloth/gemma-4-26B-A4B-it`.

**PROVENANCE NOTE — this receipt was written by the post-hang recovery session.** The train,
merge, and Phase-5.2 gate all completed and wrote their artifacts BEFORE the GB10's 18:15
OOM thrash-wedge (§6); every number below is read from the on-disk logs
(`~/fine-tuning/output/qav-gemma4-26b-moe-v2/{train.log,merged-gen-gate.{log,json}}`), not from
memory of a live session. The receipting step itself was what the hang interrupted.

---

## 1. Staging — the 302-row attribution corpus: ALL GATES GREEN

`prepare_qav_sft.py` on the grown corpus (108→302; the seeded_record family landed DC-12 0→69,
DC-14 7→56):

| gate | result |
|---|---|
| rows staged | train **279** (114 approve / 165 reject) · eval **23** (6 approve / 17 reject) |
| train∩eval contamination | **PASS** intersection 0 |
| frozen-exam cross-check | **PASS** 0 hits (279 rows × 562 shingles × 2 exams, 8-gram normalized) |
| template-token leak | **PASS** 0 hits / 8 markers |
| class-balance tripwire | **PASS** byte-match vs manifest ({approve:114, reject:165}; DC-03:27 DC-05:4 DC-08:9 DC-12:69 DC-14:56) |
| target transform | strip_think=True strip_fence=True → bare verdict JSON |

Sources (raw sha256): train `7c607b33f624f566…` (279) · eval `f756e4f9567a557a…` (23) ·
factory manifest `5456cbed3b36d663…`. Staged (`~/fine-tuning/data/`, DF-008 — never committed):
`train-qav.jsonl` `76e256f3d3af7f1a…` · `eval-qav.jsonl` `65c375909a2461b7…` + staging manifest.

## 2. Seq gate — 20480 (the long-context recovery, receipted at `4ac6c82`)

24576 OOMs in training on this 26B; **20480 fits** (1-step worst-case smoke peak 81.0 GB).
Real-tokenizer audit over the 302 corpus → **EXCLUDED BY NAME at 20480 (never truncated):**

| split | row_id | real tokens | label |
|---|---|---|---|
| train | qav-e39d68e1ee550702 | 52,748 | reject DC-08 |
| train | qav-6394acf8aa44a442 | 57,231 | reject DC-05 |
| train | qav-5a7c0da775c6938c | 66,327 | reject DC-03 |
| eval | qav-0327647b6abc2d6a | 51,978 | approve |
| eval | qav-cfc846435168e121 | 52,065 | approve |
| eval | qav-40daa1d2adf38029 | 52,304 | reject DC-14 |

vs v1's five exclusions, `qav-a1b64a41566b1fc9` (16,607 tok, reject DC-03) is **RECOVERED into
train** — the seq-20480 point of the lane. Post-exclusion: **276 train**
(114 approve / 162 reject; DC-03:26 DC-05:3 DC-08:8 **DC-12:69 DC-14:56**) + **20 eval**.
Honest notes, recorded not hidden: (1) the 3 longest reject exemplars (52–66k tok) remain
unseen by any tune; (2) DC-05 train support is 3; (3) the eval split lost its ONLY DC-14 row to
the seq gate and has never had a DC-12 row (corpus fact) — the Phase-5.2 gate therefore probed
DC-12 with a train-member row (§4), and the frozen exam remains the only honest attribution grade.

## 3. Full run — 3 epochs on 276 rows: training COMPLETE (EXIT=0)

`train_qav.py --data-path train-qav-seq20480-v2.jsonl --eval-path eval-qav-seq20480-v2.jsonl
--max-seq-length 20480` (all other knobs = runbook defaults: r=16/alpha=16/dropout=0, lr 2e-4
cosine, warmup 0.03, eff-batch 4, 3 epochs, adamw_8bit, seed 3407).

- Guards: **[G1]** 494,376,960 / 26,300,310,832 = **1.88%** · **[GT]** gemma-4 non-thinking ·
  **[G2]** both turn markers · **[G6]** think=0/276 fenced=0/276 · **[G4]** masked **95.6%**
  (high-expected band) · **[G3]** sdpa
- **207/207 steps** (69/epoch) · train_runtime **5,439 s (90 min 39 s)** ·
  final **train_loss 0.08727**
- **eval_loss by epoch: 1.253 → 1.100 → 1.064** — still falling at epoch 3
  (v1 on 82 rows: 1.512 → 1.325 → 1.322, plateaued) — the corpus, not epochs, moved it.
- **[G5] peak GPU 79.0 GB** — the seq-20480 run held under the ~100 GB freeze-watch line
  for the whole training window.
- The in-process merge **succeeded this time** (v1's OOMed at ~119 GB and needed a fresh
  process): MoE LoRA merge applied 60/60 per-expert tensors, merged-16bit saved in-run.
  Difference vs v1: the llama-swap fleet was already unloaded for the v2 window.

## 4. Phase-5.2 MERGED-GEN GATE (mandatory, pre-GGUF): **PASS** — 17:55

Merged-16bit under plain transformers; greedy generation on serving-shaped prompts; outputs
judged under the verbatim exam-extractor replica. **4 rows: 3 held-out eval + 1 train-member
DC-12 probe** (no DC-12 exists in eval — corpus fact, §2):

| row | provenance | label | model verdict | parse |
|---|---|---|---|---|
| qav-5facf8bbef2aed96 | held-out eval | approve | approve ✓ | bare JSON, balanced |
| qav-13f964bbaead7fd1 | held-out eval | reject DC-03 | approve ✗ | bare JSON, balanced |
| qav-43c8de8edc8d812b | held-out eval | reject DC-08 | approve ✗ | bare JSON, balanced |
| qav-6d610939b5caa18e | train-member probe | reject DC-12 | reject ✓ | bare JSON, balanced |

- **Format (the gate): 4/4 bare verdict JSON** — no think, no fences, no template tokens, zero
  contaminants. `gate_pass_over_ran=true`. The serving contract held.
- **Verdicts (informational, NOT a grade): 2/4.** The two misses are the SAME two rows v1's
  gate missed, and both carry conspicuously tiny serving prompts (471 / 478 tok vs 3,944 for
  the approve row) — thin-bundle rejects. v1's identical gate-lean did NOT materialize on the
  frozen exam (12/12 gold negatives rejected), so this is carried loudly to S5, not resolved here.

## 5. Artefacts (all outside the repo, DF-008)

```
~/fine-tuning/output/qav-gemma4-26b-moe-v2/
├── checkpoint-{69,138,207}/  (207 = epoch 3.0, full optimizer state — resumable)
├── lora-adapter/            (adapter + tokenizer/template)      @17:42
├── merged-16bit/            (Phase-5.2 PASSED)                  @17:43–17:49
├── gguf/qav-gemma4-26b-moe-v2.BF16.gguf  50,505,120,480 B       @20:07 (recovery session)
├── train.log (EXIT=0 @17:50) · merged-gen-gate.{log,json} @17:55
~/fine-tuning/data/{train,eval}-qav-seq20480-v2.jsonl · smoke-stress-qav-v2-longseq.jsonl
```

## 6. THE HANG — what interrupted the lane (honest record)

Timeline (all BST, from the previous boot's journal + file mtimes): 17:50 train EXIT=0 →
17:55 gate PASS → 17:56 last journal write of substance → **18:15:09–18:15:13 OOM-killer storm**
(≈15.6 of 16 GB swap consumed; the killer's victims were near-zero-RSS desktop processes while
the bulk of RAM sat in UVM/GPU-pinned allocations invisible to victim accounting — a livelock,
not a clean kill; journald watchdog-SIGKILLed, "Journal stopped" = the boot's last line) →
userspace limped to ≥18:51 → **power-cycled 19:35**, clean recovery (EFI dirty-bit only).
No Xid, no panic. The box had run memory-saturated all day (NVRM NV_ERR_NO_MEMORY from 08:47;
a 39 GB training python OOM-killed 09:07). **Lost to the hang: only the S4 GGUF export + S5
re-exam + this receipt** — every training artifact predates it. The keepalive flock holder died
with the wedge; the recovery session re-took the pause (fresh holder) and emptied `/running`
(108 GB available) before the S4 leg below.

## 7. S4 — GGUF + serving (the recovery session, same pipeline as v1's §7)

merged-16bit (the exact Phase-5.2-gated artifact) → `convert_hf_to_gguf.py --outtype bf16`
in-container (the mounted `scripts/llama-cpp-convert` Gemma4 tree; 50,505,120,480 bytes —
byte-identical size to v1's BF16, exit 0, log `gguf/convert.log`) → host `llama-quantize`
**Q4_K_M** (never q4_0) → `/opt/llama-swap/models/qav-ft/qav-gemma4-26b-moe-v2.Q4_K_M.gguf`,
**16,796,000,992 bytes — byte-identical size to v1's Q4_K_M** (same pipeline, same size class;
the same 60/658 MoE-expert fallback-quantization warning as v1), sha256
`892fb9a324c693595301433ded21860763a2293851aced89b95a981ec68a89be`
(log `quantize-v2.log` beside it). llama-swap: dated backup
`config.yaml.bak-20260723-200614-pre-qav-ft-v2`, added the `qav-ft-v2` block (exact `qav-ft`
mirror: ctx 98304, q8 KV, `--reasoning off`) + var `qft2` + **the `qav_exam` set gains v2**
(`"qft & qft2 & g26 & pk & qt"` — three 26B candidates + the audio pair co-resident);
restarted via systemd; smokes: `/v1/models` lists all three candidate aliases; 1-token
completions HTTP 200 each (v2 14.5 s / v1 19.4 s / stock 38.8 s cold). Honest note: the smokes
interleaved with the startup preload, so the three 26B candidates were never observed
simultaneously resident — the S5 exam needed only `qav-ft-v2`, and its runner's fresh
single-slot probe REFUSED the first attempt until the candidate was warmed and verified
`ready` (posture at exam time: qav-ft-v2 + the audio pair). The probe doing its job is the
receipt; 3-way simultaneous co-residency was not demonstrated and was not needed.

## 8. S5 — the 3-way re-exam

Run and graded in fleet-evals: **`RESULTS-qav-ft-v2-2026-07-23.md`** (commit `0fbee7e`; v2
fresh × 2 tasks × 3 reps on the sealed gates, freeze `2165802`; v1 + stock columns = their
banked same-day, same-freeze, same-runner runs at `e66a8be`). **VERDICT: NO-DEPLOY** — the
verdict layer stays perfect (12/12 gold-negative rejects, 9/9 greens approved, 24/24 bare-JSON,
byte-identical reps) but owning-class attribution is 0/4: DC-12 became an attractor
(GN-3/GN-4/RC-01), GN-1↔GN-2 classes swapped symmetrically, DC-14 never fires on 56 training
rows; anchors now fire on GN-1/GN-4/RC-01 (evidence-native loci — the corpus's real gain).
Full analysis lives there — this receipt stops at the serving entry, per the seat split.

*Probe-not-adoption per R3-02 stands: `qav-ft-v2` is a probe-set entry; no deploy claim is made
here. Rollback = the dated .bak above.*
