# QAV v4 — the Option-B retrain, and the park (2026-07-24 evening)

**Lane:** §7 claim `f678650` (Rich's letter B + "approve batch A"; STOP-RULE in the claim) ·
**Corpus:** `v4-corpus-2026-07-24.md` (@aa2e51e; 463/96, in-band natively; take-1
token-arithmetic catch + ruling v2 `ced9a34`) · **Chain:** staging PASS (555 checked / 4 gold
exempt, hits=0) → seq-20480 re-stage (6 named exclusions; staged **458 train / 93 eval**,
every class both sides; shas `00e56512…`/`38b0311b…`) → guarded smoke (79.0 GB, green) →
**train 345/345** (2h26m, train_loss 0.0667, eval_loss 0.285→0.223→0.236, peak 79.0 GB
steady, merge 60/60 in-run) → **Phase-5.2 gate: 6/6 bare JSON, 5/6 verdicts — the two
historic thin-prompt rows (`43c8de…` DC-08, `13f964…` DC-03) REJECTED for the first time in
four tunes; held-out DC-14 + DC-12 classes CORRECT; the DC-05 source-recipe row the one
verdict miss** → GGUF Q4_K_M `9ce387b7…` (16,796,000,992 B, fourth byte-identical size) →
`qav-ft-v4` seated (backup `bak-20260724-*-pre-qav-ft-v4`; qav_exam = all four candidates +
stock) → the sealed re-exam, 6/6 first-attempt-valid, zero runner refusals.

**S5 VERDICT (fleet-evals `3c3b440`): NO-DEPLOY — and the claim's stop-rule FIRES: the tuning
loop PARKS.** Verdict layer perfect (21/21), anchors **14/15 — evidence-reading essentially
solved**, owning-class **0/15**: the attractor migrated a third time (DC-12 → wobble → DC-05;
GN-1/2/3 all read DC-05, RC-01 flipped to DC-03). Four tunes establish the shape: class-naming
tracks corpus-support gradients, not taxonomy semantics — not a volume problem. Post-park
options named in the RESULTS (organic growth · taxonomy-in-prompt, which needs a fleet-evals
freeze decision · the product question on whether the seat's bar needs the class name) — all
Rich's, none claimed.

*Estate at close: flock released (by fd-holder PID — the pgrep trap avoided), standing set
revived, all four tuned candidates parked on llama-swap as probes, container left up. The v3
corpus remains preserved at `.bak-v3merged`; the v4 corpus is the corpus of record.*
