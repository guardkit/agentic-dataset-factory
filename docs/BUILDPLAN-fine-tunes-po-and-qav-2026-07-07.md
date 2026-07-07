# Buildplan — the two fine-tune lanes: PO Phase-3 run + QAV chain

**Status:** 2026-07-07 late. Written for Rich as the execution checklist; every claim below
re-verified on disk/live today (llama-swap :9000 model list, keepalive timer state, configs,
commits `11db17a`/`6d2fc98`/`77877f7`/`0e3a5d1`).
**Calendar authority:** `ai-transition/docs/factory-program-plan-2026-07-07.md` §2.2 owns the
GB10 box. Fixed points: **07-09 HSBC demo = quiet window**; PO Phase-3 launch **NET weekend
(Rich, 2026-07-07 late — supersedes the older 07-09-eve row; D-WS4-3 filed at launch)**; the
run owns the box ~90h once started.

## Readiness verdict (read this first)

| Lane | State | What "go" needs |
|---|---|---|
| **A — PO Phase-3 dataset generation run** (1,210 targets, ~90h) | ✅ **READY.** Pipeline proven (pilot 60 + re-verify 12, 0 false Coach rejections); D-WS4-1/2 filed (`0e3a5d1`, GOAL = 1,210); config ready | Remove `limit:` line, file D-WS4-3 at launch, launch NET weekend |
| **A′ — PO fine-tune (train)** | ⏳ follows the run | Run output + curation pass → Unsloth QLoRA per runbook lineage; deploy gate = frozen `po-heldout` suite |
| **B — QAV fine-tune** | ❌ **NOT ready to train — the dataset does not exist yet.** Spec complete (`domains/qa-verifier/`, `11db17a`) + training/serving scope complete (`77877f7`), but the **B11 code half (seeded-defect mode) is unbuilt**: no injector, no `output/qa-verifier/`, no manifests, no FEAT-EVAL-QAV | Steps B1–B8 below, in order |

Correcting the premise gently: what is "ready to go" on QAV is the **spec for the code half**,
not the fine-tune. The QAV chain has 5 gates between here and a trained model (code half →
pilot spot-check → bulk manifests → B12 eval suite → train+grade). Realistic earliest train:
**w/c 07-14** (teacher-rationale + train stages need the GPU, which the PO run owns until
~07-13 late if launched Saturday... see calendar at the end).

## Pre-flight state (verified 2026-07-07 late)

- llama-swap up on **:9000**; serves `gpt-oss-120b` (Player) + `gemma4-coach` (Coach fallback)
  + `coach-ft-v3` + `gemma4-26b` — everything both lanes need. `autobuild_go` co-residency set
  already exists (no config edit needed for the PO run).
- `llama-swap-keepalive.timer`: **inactive since 07-03 but ENABLED** — it returns on reboot.
  Treat "stopped" as a per-launch check, never an assumption.
  ⚠️ Standing operator item (pre-dates this plan): the keepalive allowlist
  `/usr/local/bin/llama-swap-keepalive.sh` still probes `gemma4-coach`, not `coach-ft-v3` —
  fix before any re-enable (`domains/coach-agent/RESULTS-coach-v3.md:166-168`).
- adf working tree clean on `main`; `.venv` present; disk 1.5T free (plenty; PO Phase-1 rows
  are small, QAV bundles larger but low thousands of rows).
- `agent-config.yaml` = PO generative mode, currently `limit: 12` (line 36) from the re-verify.

---

## Lane A — PO Phase-3 dataset generation run (~90h, 1,210 targets)

**Owner:** [Operator] launch + light monitoring. **Docs of record:**
`domains/product-owner/RESULTS-po-phase1.md` (readiness + open items),
`MEMO-prelaunch-decisions-D-WS4-1-2.md` (both filed), `PLAN-po-dataset-generation.md`.

### Prerequisites (all met except the two marked ☐)

- ✅ D-WS4-1/2 filed — GOAL targets already edited to 1,210 (`0e3a5d1`); **do not edit GOAL again**.
- ✅ Pipeline robustness: `require_fenced_json` gate + Coach fallback resilience (`cd12f8c`),
  re-verified 10/12 accepted, 100% strictly-valid inner JSON on accepts.
- ✅ Checkpoint/resume per expanded-target index (`--resume`).
- ☐ **D-WS4-3 filed at launch** (Rich, one dated line in WS4 §8 + program plan §2.2:
  Spark A, fleet-quiet window declared, NET weekend).
- ☐ **Calendar clear:** not before the 07-09 demo; NET weekend per Rich. The box is then
  owned ~90h — no autobuild, no evals, no live-gate runs during it.

### Launch steps (commands)

```bash
cd ~/Projects/appmilla_github/agentic-dataset-factory

# 1. Preserve current output (house convention: dated backup dirs)
cp -r output output_backup_pre_po_phase3_$(date +%Y%m%d-%H%M%S)

# 2. Config: remove the pilot cap — delete line 36 (`limit: 12 ...`) from agent-config.yaml.
#    Change NOTHING else (modes round-robin, retries, fenced-JSON gate stay as-is).
#    Commit the one-line change with a dated note referencing D-WS4-3.

# 3. Keepalive OFF (idempotent — currently inactive, but verify; it revives the fleet
#    on top of gpt-oss otherwise -> OOM):
sudo systemctl stop llama-swap-keepalive.timer
systemctl is-active llama-swap-keepalive.timer   # expect: inactive

# 4. Launch inside tmux (90h run must survive the SSH session):
tmux new -s po-phase3
source .venv/bin/activate
python agent.py 2>&1 | tee run_logs/po_phase3_$(date +%Y%m%d-%H%M%S).log
# detach: Ctrl-b d

# 5. Any interruption (power, OOM, crash): resume from the per-target checkpoint
python agent.py --resume
```

### Monitoring (once or twice a day is enough)

- `tmux attach -t po-phase3`; accepted/rejected counters in the log.
- The two at-scale watch items from RESULTS-po-phase1 "Open items":
  **inner-JSON reject rate** (re-verify saw 1/12; if it trends materially higher, raise
  `max_format_retries` for this domain mid-run via a dated config note + resume) and
  **decomposition depth** (~1 epic/1 feature per example is thin — note it for curation,
  don't tune mid-run).
- Progress arithmetic: pilot ≈ 4–5h/60 targets → ~4.5min/target → 1,210 ≈ 90h. If the rate
  drifts far from that, something is wrong (contention, fallback storms) — check before it
  burns days.

### Post-run (same day it completes, ~07-13/14 if launched Saturday)

1. `cp -r output output_po_phase3_final_$(date +%Y%m%d)` + commit RESULTS delta
   (accept rate, reject reasons, mode balance) to `domains/product-owner/`.
2. Restore serving posture: fix the keepalive **allowlist** first
   (`gemma4-coach` → `coach-ft-v3` in `/usr/local/bin/llama-swap-keepalive.sh`), then
   `sudo systemctl start llama-swap-keepalive.timer`; restore the tutor preload
   (program-plan row).
3. Weave in the harvest per Phase-2 when WS4-S2 lands (19 paired records post-quarantine —
   `SPEC-po-phase2-harvest-lift.md`); the book/generative rows do NOT wait on it.

### A′ — the PO fine-tune itself (after the run; separate operator session)

Recipe lineage: `domains/coach-agent/RUNBOOK-coach-fine-tune.md` (Unsloth QLoRA in the NVIDIA
PyTorch container; **manual SSH-paste launch, never Claude→tmux→docker** — two documented
freezes) generalized per `domains/architect-agent/RUNBOOK-architect-fine-tune.md`. Write
`RUNBOOK-po-fine-tune.md` as deltas at train time. Non-negotiables: seq-length audit with the
served tokenizer BEFORE picking `--max-seq-length` (PO rows carry big fenced JSON);
`gemma-4` template (never `gemma-4-thinking`); base `unsloth/gemma-4-26B-A4B-it`, GGUF export
UD-Q4_K_XL (never q4_0). **Deploy gate: the FROZEN `po-heldout` suite** (fleet-evals,
pre-registered §5 gate, frozen 2026-07-03) — graded PASS before any llama-swap entry;
on-demand entry first, preload only after burn-in.

---

## Lane B — QAV: from spec to deployed L5 judge (8 steps, 5 gates)

**Docs of record:** `domains/qa-verifier/` — `PLAN-qav-phase1-dataset-generation.md` (the mode
design), `OUTPUT-CONTRACT.md` (row + manifest), `SPEC-qav-gold-negatives.md`,
`SCOPE-qav-finetune-training-serving.md` (training/serving half). Kickoff text for B-1 lives
in the WS2 build plan §B11.

| # | Step | Owner/Model | GPU? | Earliest slot |
|---|---|---|---|---|
| B1 | **Code half** (the one factory change): `seeded_defect` mode — injector (11 recipes, PLAN §3), harvest transform, contamination-check script, manifest writer + unit tests; verify on disk whether original `coach_turn_N.json` survives for the 4 gold negatives | [Opus 4.8] session, WS2 B11 code half | none | **now** — can run during the PO run *if* done on a branch/worktree touching nothing under `output/` and the run's checkpoints |
| B2 | **Pilot P2:** ~40 rows, recipes interleaved; regen is CPU/pytest-dominant but the teacher-rationale stage needs the GPU | factory run | teacher stage only | post-PO-run (~07-13+) |
| B3 | **GATE — Rich hand-audit:** spot-check ≥10 pilot rows + the 4 gold-negative reconstructions by name (B11 validation bar) | Rich | — | after B2 |
| B4 | **Bulk P3** to GOAL targets (~500 seeded rejects + ~500 approves incl. ≥45% ugly greens); finalize `manifests/qav-phase1-train.manifest.json` + eval manifest. **GATES:** balance bands (50/50 ±10%) + embedded contamination check = pass | factory run | teacher stage | after B3 |
| B5 | **B12 — file FEAT-EVAL-QAV** in fleet-evals: 4 gold negatives as must-catch + held-out seeded slice + honest-green over-reject rows; Rich freezes the bar | [Opus 4.8] attended | none | after B4 manifests |
| B6 | **Train:** write `RUNBOOK-qav-fine-tune.md` (deltas vs coach runbook per SCOPE §3): staging gates a–d, NO prepare-time oversampling, **seq-length audit is the critical Phase-0 gate** (`llama-tokenize` on the served GGUF; bundle rows are the fleet's longest and the verdict sits at the END — truncation eats the label), per-class count tripwire vs manifest. QLoRA train + merge + GGUF (coach precedent ~71 min; QAV seq may stretch it). Manual SSH-paste launch | [Operator] + [Opus 4.8] | full box, short | booked window post-PO-run, coordinated vs WS2 V1 (w/c 07-14) |
| B7 | **GATE — grade vs FEAT-EVAL-QAV:** 100% must-catch + false-block ceiling; pre-registered dispositions written into the RESULTS template BEFORE the run. FAIL ⇒ checkpoint stays a directory | WS4 consumes fleet-evals | eval inference | same booked window |
| B8 | **Serve + shadow:** llama-swap `qav-ft-v1` **on-demand only**; verdict-trio GBNF grammar threaded per-request (shape from grammar, judgment from the fine-tune); keepalive/probe changes as a named runbook phase; rollout gate 1 = shadow (log-only next to every Coach verdict, no authority) | [Operator] | negligible | after B7 PASS |

**Hard disciplines (already pinned, listed so nobody re-derives):** hold-out rows
(`split: eval_qav`, incl. all 4 gold negatives) never enter the training manifest — the
contamination check is embedded in the manifest and re-run at train staging; no training row
generated from the 4 gold-negative source tasks; base = gemma-4-26B-A4B (D9-compliant vs the
gpt-oss/frontier Player), QAT base swap rejected, never q4_0; DF-008 — dataset private.

---

## Combined calendar (assuming PO launch Saturday 07-11)

| When | Box | Lane A | Lane B |
|---|---|---|---|
| 07-08 → 07-10 | free (07-09 demo QUIET) | idle; D-WS4-3 pre-drafted | **B1 code half** (Opus, no GPU) |
| 07-11 (weekend, per D-WS4-3) | **PO run starts (~90h)** | launch steps above | B1 finishes; CPU-side regen smoke OK on a worktree; no teacher calls |
| ~07-14/15 | PO run ends → restore posture | RESULTS delta; curation begins | **B2 pilot → B3 Rich audit** |
| w/c 07-14 (booked vs WS2 V1) | contended — program plan books it | A′ seq audit + QLoRA train + `po-heldout` grade | **B4 bulk → B5 B12 filing** |
| following | — | PO deploy on graded PASS | **B6 train → B7 grade → B8 shadow** |

Two trains (A′ and B6) are each ~1–2h of box time — they slot into gaps; the long occupations
are the PO run (~90h) and QAV bulk teacher-rationale generation (size TBD from pilot timing).

## Risks

- **Keepalive re-enable with the stale allowlist** silently demotes the production Coach —
  fix the allowlist before `systemctl start`, per the standing item.
- **B1 built during the PO run** collides with checkpoints if it touches `output/` or runs
  the factory against the live llama-swap — branch/worktree + zero teacher calls until the
  box frees. If in doubt, sequence B1 after 07-13 (it's the only float in Lane B).
- **QAV seq-length** may exceed comfortable GB10 training length — the B6 Phase-0 audit
  decides truncation/exclusion with a dated note; never silent tail loss.
- **PO reject-rate at scale** unknown beyond n=72 — the monitoring arithmetic above catches a
  drift within hours, and `--resume` makes a stop/fix/resume cheap.
