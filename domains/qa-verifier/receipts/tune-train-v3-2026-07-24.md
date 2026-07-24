# QAV v3 — CONTRAST-PAIR RETRAIN receipt (staging → train → gate → S4 → S5)

**Date:** 2026-07-24 (overnight) · **Lane:** QAV v3 CONTRAST-PAIR CORPUS + RE-EXAM
(ai-transition §7 claim `7c5d798`) · **Corpus:** `contrast-pair-corpus-2026-07-24.md`
(`f48a921`, engine `3348c63`, spikes GO `pair-spikes-2026-07-23.md`) · **Machine:** GB10 ·
**Container:** `qav-ft-20260723` (same deps as v1/v2) · **Base:** `unsloth/gemma-4-26B-A4B-it`.

## 1. Staging — ALL GATES GREEN (after the widened gate's first live catch)

`prepare_qav_sft.py --date 2026-07-24` on the 387-corpus: 387/387 row verification · leak 0/8 ·
train∩eval 0 · class-balance byte-match ({approve:139, reject:196}; DC-12:82 DC-14:64 DC-03:36
DC-08:10 DC-05:4) · **frozen-exam cross-check: the NEW eval-side widening FIRED on first use**,
flagging the 4 gold_negative eval rows — deliberate exam TWINS (same-defect reconstructions,
never trained, gold-source law enforced in frozen contamination.py). Cured with a BY-MODE gold
exemption, count recorded (`eval_gold_negative_exempted=4`), every other eval row incl. all 28
pair rows still hard-gated → **PASS hits=0 (383 checked)**. Fix `33edfe1`, tests 13/13.

## 2. Seq-20480 re-stage — only FOUR exclusions, eval keeps every class

Real-tokenizer audit (`audit_stage_qav_387_v3.py`, in-container): EXCLUDED BY NAME —
train qav-410c1850089bc578 (51,714 tok, approve) · eval qav-0327647b6abc2d6a /
qav-cfc846435168e121 (approves) · qav-40daa1d2adf38029 (52,304, reject DC-14, the same BDDW-001
row every cycle loses). **Staged: train 331** (138a/193r; DC-12:82 DC-14:64 DC-03:35 DC-08:9
DC-05:3, sha `91e9ee7a…`) · **eval 49** (16a/33r; **DC-03:13 DC-08:4 DC-05:4 DC-12:8 DC-14:4 —
every class survives the gate for the first time**, sha `b75b8b0e…`; the pair rows are ~1.6k tok,
structurally seq-safe).

## 3. Train — guarded smoke → full run, COMPLETE (EXIT=0)

1-step worst-case smoke (4 longest kept rows): all guards green ([G1] 1.88% · [GT] gemma-4
non-thinking · [G2] · [G6] 0/4 · [G4] 99.2% · [G3] sdpa), **[G5] 79.0 GB < the 90 GB launch
gate** → auto-launched the full run. **249/249 steps** (83/epoch × 3) · train_runtime 6,952 s
(1 h 56 m) · train_loss **0.07893** · **eval_loss 0.5746 → 0.4526 → 0.4557** on the
class-complete eval (not comparable to v2's eval — different split composition; the signal is
convergence with a slight epoch-3 uptick) · [G5] peak **79.0 GB** steady · in-run merge OK
(60/60 MoE tensors). Memory posture the whole window: llama-swap EMPTY, keepalive flock-held,
~110 GB headroom at launch — the §8 wedge lessons applied end-to-end.

## 4. Phase-5.2 MERGED-GEN GATE: **PASS** — and the first ALL-HELD-OUT class-diverse sitting

`merged_gen_gate_qav_v3.py`: 6 eval rows, one approve + one reject per class. **6/6 bare JSON,
balanced path, zero contaminants** (the mandatory axis). Verdict-informational 3/6:
**the held-out DC-14 pair row (RC-01 shape) REJECTED ✓ and the held-out DC-12 pair row
REJECTED ✓** — the classes v2 could only probe train-member; approve control approved ✓.
Misses: the two historic thin-prompt rows (`43c8de…` DC-08, `13f964…` DC-03 — three tunes, three
gate-misses, exam-proven non-carrying) + one DC-05 (train support 3, the chronic gap).

## 5. S4 — GGUF + serving

merged-16bit → BF16 (50,505,120,480 B, exit 0) → **Q4_K_M 16,796,000,992 B** (byte-identical
size to v1/v2, same 60/658 fallback), sha256
`6db1f801b4054af35efb22befc7fefaa027b615d32f3ed9e3c4f60429afebf47` →
`/opt/llama-swap/models/qav-ft/qav-gemma4-26b-moe-v3.Q4_K_M.gguf`. Config: backup
`config.yaml.bak-20260724-060941-pre-qav-ft-v3`, `qav-ft-v3` block (exact mirror) + `qft3` +
`qav_exam` gains v3; restart; warm-smoke 200/19.5 s; candidate verified `ready` before the
runner (the v2 single-slot lesson — zero refusals this sitting).

## 6. S5 — the sealed-gate re-exam

fleet-evals **`RESULTS-qav-ft-v3-2026-07-24.md`** (`153e3c0`): **NO-DEPLOY** on the frozen bar —
verdict layer perfect again (12/12 gold-neg rejects · 9/9 greens · 24/24 bare JSON) and the
attribution axis MOVED: **the DC-12 attractor broke (9→3 legs) · first-ever correct GN-1 leg ·
GN-3's anchor 0→3 · determinism→wobble (the shape→class shortcut destabilized)**. Residual =
the null-vacancy shape (right analysis, wrong class name), the design v1.2's own named cap;
plus a new DC-05 null-wiring mini-attractor. v4 levers named in the RESULTS: vacancy cohort at
scale + DC-05 boundary controls. Probe-not-adoption stands.

*The keepalive flock is released at lane close; the standing set restores. All three tuned
candidates parked on llama-swap. Container left up.*
