# QAV pilot tune — S3 TRAINING receipt

**Date:** 2026-07-23 · **Seat:** S3 TRAINING · **Factory sha at run:** `3da25b3` ·
**Machine:** DGX Spark GB10 (121 GB unified) · **Container:** `nvcr.io/nvidia/pytorch:25.11-py3`
(deps: transformers 5.5.4 / trl 0.26.1 / accelerate 1.10.0 / datasets 4.3.0 / unsloth **2026.7.4**
— post-PR-4913) · **Base:** `unsloth/gemma-4-26B-A4B-it` (HF-cache training weights, no download).

**Scope stop-line honored: NO GGUF exported** (Phase 5.3 = S4's job). The run ends at
merged-16bit + the mandatory Phase-5.2 merged-gen gate.

GPU posture: keepalive flock-hold verified alive (PID 1185504); `qav-coach` evicted from
llama-swap before launch; the two s2s audio models (`parakeet-tdt-0.6b-v3`, `qwen3-tts-0.6b`)
were transiently unloaded by llama-swap's `/unload` (it ignores the per-model param — operator
catch, noted below) and **restored to ready within ~2 min** via their upstream health probes.
`/running` was minimal (2 small audio models) for the whole training window.

---

## 1. Phase 0 staging — ALL GATES GREEN (exit 0)

`prepare_qav_sft.py --date 2026-07-23` on the banked 108-corpus:

| gate | result |
|---|---|
| row verification | **PASS 108/108** |
| template-token leak | **PASS** 0 hits / 8 markers |
| contamination (train∩eval) | **PASS** 0 |
| frozen-exam cross-check | **PASS** 0 hits (86 rows × 562 shingles × 2 exams) |
| class-balance tripwire | **PASS** byte-match manifest ({approve:41, reject:45}; DC-03:27 DC-05:3 DC-08:8 DC-14:7) |
| target transform | strip_think=True strip_fence=True → bare verdict JSON |

Sources (raw sha256): train `8bb5bce0e236eb2a…` (86) · eval `c26c9bc5a6a5b514…` (22).
Staged (`~/fine-tuning/data/`, DF-008 — never committed): `train-qav.jsonl`
`376183983033049e…` (86) · `eval-qav.jsonl` `d0829a9a3869309e…` (22) + staging manifest.

## 2. THE SEQ-LENGTH GATE — real-tokenizer audit → **16384**, exclude-never-truncate

Real gemma-4 tokenizer (FastModel + `get_chat_template("gemma-4")`), full render per row,
in-container. **Ground truth vs the 3.5-ch/tok estimate — the estimate was materially wrong at
the tail** (real train max 66,327 tok vs est 61,180; real 8192-exceed 23.3% vs est 25%; real
12288-exceed 10.47% vs est 10.19%):

| candidate | train exceed | train kept | ≥90% rule |
|---|---|---|---|
| 8192 | 20/86 | 76.74% | FAIL |
| 12288 | 9/86 | **89.53%** | **FAIL (just under)** |
| **16384** | **4/86** | **95.35%** | **PASS ← chosen** |
| 24576 | 3/86 | 96.51% | (larger, not needed) |

(train p50 5,236 · p95 16,249 · p99/max 66,327 · eval p50 3,994 · max 51,978.)

**Decision: `--max-seq-length 16384`** — the smallest candidate keeping ≥90% of train rows
un-truncated that also survived the 1-step memory smoke (§3). Full per-row audit:
`~/fine-tuning/output/qav-gemma4-26b-moe/seq-audit-real-tokenizer.json`.

**EXCLUDED BY NAME (5 rows — never silently truncated; the verdict sits at the END):**

| split | row_id | real tokens | label |
|---|---|---|---|
| train | qav-5a7c0da775c6938c | 66,327 | reject DC-03 |
| train | qav-6394acf8aa44a442 | 57,231 | reject DC-05 |
| train | qav-e39d68e1ee550702 | 52,748 | reject DC-08 |
| train | qav-a1b64a41566b1fc9 | 16,607 | reject DC-03 |
| eval | qav-0327647b6abc2d6a | 51,978 | approve |

Post-exclusion training corpus: **82 train** (41 approve / 41 reject — share 0.50, still inside
the 0.50±0.10 band; DC-03:25 DC-05:2 DC-08:7 DC-14:7) + **21 eval** (4 approve / 17 reject).
Filtered files: `train-qav-seq16384.jsonl` `39bfe2b08a55e68c…` ·
`eval-qav-seq16384.jsonl` `920f2991ed063b18…`. Honest note: all 4 excluded train rows are
rejects — the 4 longest bundles in the corpus carry defect evidence the tune never saw; DC-05
train support drops from 3 to 2. Recorded, not hidden.

Runbook 3.3a catch (operator fix, receipted): the runbook's audit snippet calls
`tok.apply_chat_template` on plain-string content, but FastModel returns a **multimodal
Processor** for gemma-4 — it requires typed-parts content
(`[{"type":"text","text":…}]`). The audit renders via typed parts and counts with the inner
tokenizer; the trainer itself is unaffected (`standardize_data_formats` handles the shape).

## 3. Smoke — 1 step at the chosen config on the WORST case: PASS

Stress set = the 4 longest **kept** rows (16,249 / 16,162 / 15,097 / 13,582 tok) so the single
eff-batch-4 step is the true memory worst case. seq 16384, 16-bit LoRA, unsloth grad
checkpointing:

- **[G1]** trainable 494,376,960 / 26,300,310,832 = **1.88%** (exact expected — experts attached)
- **[GT]** gemma-4 non-thinking applied, hybrid-swap guard passed · **[G2]** both turn markers
- **[G6]** think=0/4 fenced=0/4 · **[G4]** masked 99.2% (high-expected band, below the 99.9 abort)
- **[G3]** sdpa · loss **0.7959** (finite) · **[G5] peak 64.2 GB**; host steady ~78–84 GB during
  the step (transient ~108 GB at load) · exit **0**

## 4. Full run — 3 epochs on 82 rows: training COMPLETE

```
train_qav.py --data-path train-qav-seq16384.jsonl --eval-path eval-qav-seq16384.jsonl
             --max-seq-length 16384        (all other knobs = runbook defaults:
             r=16/alpha=16/dropout=0, lr 2e-4 cosine, warmup 0.03, eff-batch 4,
             3 epochs, adamw_8bit, seed 3407)
```

- Guards at step 0: identical greens to §3 ([G6] 0/82 0/82; [G4] 99.2%).
- **63/63 steps** (21/epoch) · **train_runtime 2,475 s (41 min 15 s)**; wall launch→adapter
  saved ≈ 47 min (08:13:54→09:01) · **final train_loss 0.2539** (run average; last-step 0.1352)
- eval_loss by epoch: **1.512 → 1.325 → 1.322** (loss-only tracking, 21 rows)
- **[G5] peak GPU 79.0 GB**; host high-water ~98 GB during epoch evals, transient 104 GB at the
  epoch-2 boundary — held, no OOM during training.

**HONEST CATCH — the in-process merge OOMed (EXIT=137, SIGKILL at ~119 GB):** after the adapter
saved, `save_pretrained_merged` inside the still-loaded training process (model + optimizer
remnants + a second weight copy) blew the 121 GB pool. The training artefacts were intact.
**Recovery (no retrain):** a fresh merge-only process (`merge_qav.py`: FastModel loads
lora-adapter → `save_pretrained_merged`) — completed in ~10 min, exit 0, transient peak ~112 GB.
Two sub-catches receipted: (1) the fresh process needs train_qav.py's **torchao version-gate
patch** (`is_torchao_available → False`) or PEFT adapter injection dies on the container's
torchao 0.14; (2) transformers 5.x `apply_chat_template` returns a BatchEncoding — `generate`
needs `**enc`, not the object.

## 5. Phase-5.2 MERGED-GEN GATE (mandatory, pre-GGUF): **PASS**

Merged-16bit loaded under plain transformers; greedy generation (max_new_tokens 2048) on 3
held-out eval bundles' own serving-shaped prompts; outputs judged under a verbatim replica of
the exam extractor (```json fence → first balanced `{…}`):

| row | label | model output | parse | contaminants |
|---|---|---|---|---|
| qav-5facf8bbef2aed96 | approve | `{"verdict":"approve","findings":[],"ground_truth_source":"seeded"}` | **bare JSON, balanced path** | none |
| qav-43c8de8edc8d812b | reject DC-08 | `{"verdict":"approve","findings":[],"findings_class":"N/A","findings_locus":"N/A"}` | **bare JSON, balanced path** | none |
| qav-13f964bbaead7fd1 | reject DC-03 | `{"verdict":"approve","findings":[],"ground_truth_source":"seeded"}` | **bare JSON, balanced path** | none |

- **Format (the gate): 3/3 parse as bare verdict JSON** — no `<think>`, no ``` fence, no
  template tokens, every output starts `{` ends `}`. The serve-time failure mode the DCL
  merged-gen lesson exists for is **absent** — the model emits exactly the serving contract.
- **Verdicts vs labels (informational, NOT a grade): 1/3 match.** The approve matched; both
  reject rows were **approved with empty findings** (one with junk `"N/A"` extra keys). On this
  3-row peek the tune leans approve-biased — precisely what FEAT-EVAL-QAV's 4/4 gold-negative
  must-catch exists to grade. Recorded loudly for the S4/A-B operator; no deploy claim made.
- Full outputs: `~/fine-tuning/output/qav-gemma4-26b-moe/merged-gen-gate.json`.

## 6. Artefacts (all outside the repo, DF-008)

```
~/fine-tuning/output/qav-gemma4-26b-moe/
├── lora-adapter/            1.9 GB  (adapter + tokenizer/template)
├── merged-16bit/            49 GB + 1.7 GB shards (+ config/tokenizer)   ← Phase-5.2 PASSED
├── (gguf/  NOT WRITTEN — S4's job, per the stop-line)
├── train.log · merge.log · merged-gen-gate.{log,json}
├── seq-audit-real-tokenizer.json · checkpoint-{21,42,63}/
~/fine-tuning/data/{train,eval}-qav-seq16384.jsonl · smoke-stress-qav.jsonl · qav-staging-manifest.json
~/fine-tuning/scripts/{train_qav.py (copy), audit_seq_qav.py, merge_qav.py, merged_gen_gate_qav.py}
```

**Next (not this seat):** S4 = GGUF q4_k_m export (never q4_0) → llama-swap staged entry →
Phase-6 A/B on the frozen exam (qav-held-001 must-catch 4/4 + qav-held-002 over-reject
ceiling). The 3-row approve-lean above is the first thing that A/B should interrogate.

*Container `qav-ft-20260723` left up for S4; corpus bytes untouched; shas + counts + row_ids
only, no row content (DF-008).*

---

## 7. S4 SERVE + S5 THE FROZEN EXAM (appended 2026-07-23, the S4/S5 operator)

**S4 — GGUF + serving (the coach-ft-v3 pipeline mirrored):** merged-16bit (the exact
Phase-5.2-gated artifact) → `convert_hf_to_gguf.py --outtype bf16` in-container (llama.cpp-new's
Gemma4 conversion tree, 50.5 GB, exit 0) → host `llama-quantize` **Q4_K_M** (never q4_0) →
`/opt/llama-swap/models/qav-ft/qav-gemma4-26b-moe.Q4_K_M.gguf`, **16,796,000,992 bytes** (the
coach-ft-v3 precedent is 16,796,001,088 — same pipeline, same size class), sha256
`c5c9daaf51b51a85…`. llama-swap: dated backup
`config.yaml.bak-20260723-095724-pre-qav-ft`, added the `qav-ft` block (coach-ft-v3 mirror,
ctx 98304, q8 KV, `--reasoning off`) + var `qft` + exam set `qav_exam: "qft & g26 & pk & qt"`;
restarted via systemd; `/v1/models` lists both aliases; 1-token smokes HTTP 200 each;
co-residency verified (matrix solve `set=qav_exam`, both `ready` in `/running`, no mid-exam
swapping). Keepalive stayed flock-held (PID 1185504); s2s audio pair untouched.

**S5 — the frozen exam (fleet-evals, freeze `2165802`): VERDICT NO-DEPLOY — but the A/B is
decisive on the axis the tune was built for.** 2 candidates × 2 tasks × 3 reps, 12/12 rep-runs
valid (exit 0, zero aborts/re-runs); graded per rep with separate unmasked pytest exits.

| axis | qav-ft (tuned) | gemma4-26b (stock) |
|---|---|---|
| G-Q1 contract | **6/6 reps PASS** (24/24 bundles bare JSON, 0 truncations) | 3/6 — all held-001 reps FAIL (7/12 gold-neg generations truncated-unparseable) |
| G-Q2 must-catch | FAIL — but **12/12 gold negatives REJECTED at verdict level**; misses are owning-class/locus only | FAIL — 7/12 outright escapes (truncation ⇒ no verdict) |
| G-Q3 catch floor | FAIL — RC-01 rejected 3/3 but class DC-03, never DC-14 | FAIL — RC-01 rejected 3/3, class DC-05/DC-12 |
| G-Q4 false-block | **PASS 3/3** (9/9 honest/ugly greens approved) | **PASS 3/3** |
| latency/bundle | 0.45–1.41 s (med 52 completion tok) | 9–47 s (med 1132 tok, 7 at the 2048 ceiling) |

**§5's approve-lean flag is RESOLVED as a non-event:** on the frozen exam the tune rejected every
gold negative in every rep. The residual (and gating) gap is **defect-class attribution** — DC-03
composition-seam evidence read as DC-05/DC-12, RC-01's DC-14 never named — consistent with the §2
honest note (the 4 longest reject exemplars, 2 of them DC-03, sat above the seq gate; DC-05
support = 2; DC-14 reject support thin). More epochs on 82 rows is not the cure; reject-side
class diversity (the plateau card's new-mechanism-class ask) is.

Full doc + artifacts: fleet-evals `RESULTS-qav-ft-v1-2026-07-23.md` + `runs/qav-heldout/*`
(commit `e66a8be`). Probe-not-adoption per R3-02: `qav-ft` stays a probe-set entry; no deploy
claim. Rollback = the dated .bak above; the `qav_exam` set + entry left in place for follow-up
probes. Container `qav-ft-20260723` still up.
