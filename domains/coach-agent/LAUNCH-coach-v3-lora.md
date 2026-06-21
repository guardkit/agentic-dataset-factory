# LAUNCH — Coach v3 bundle-format LoRA (manual GB10 run, seq 6144)

**Why you launch this, not Claude:** `RUNBOOK-coach-fine-tune.md` — *"Phase 3 launch is a manual
SSH-paste workflow, NOT driven from a Claude Code session on the GB10. The Claude→tmux→docker chain
caused two GB10 freezes."* Claude prepared + validated everything below; **you run the docker steps.**
A freeze needs a power-cycle, so the memory watchdog is mandatory.

## What this tests
Step 0 proved the rubber-stamp was a **train≠serve** artifact: the base `gemma4-coach`, given the
**production evidence-bundle prompt**, already scores **false-approval 13.3% / false-feedback 13.3%**
on the bundle-format holdout (vs 94% FA on the old player-report-only prompt). v3 asks: does a LoRA
trained on the **production bundle format** push those residual rates down — especially the base's
misses (zero-BDD + independent-fail leniency; path-demotion + benign-warning over-rejection) — **without
over-rejecting**? Gate: **false-approval AND false-feedback both < ~20%, and beat base 13.3% / 13.3%.**

## Why seq 6144 (your call) — and the risk
v3 prompts are the full production bundle (real gemma4 p50 **3980**, max **4488** tok). The verdict
completion is p50 660 tok → at seq 4096 the completion truncates (decision survives, issues/rationale
clip). **seq 6144 → 0% truncation** (v3 max example = 5784 tok; full verdicts trained). RISK: seq ≥6144
OOM-climbed on a single 121 GB GB10 in v1 (6144 → ~112 GB, watchdog-killed). **But v3's data is shorter
than v1's** (max 5784 vs 7215 tok), so the peak should land lower — possibly under the ceiling. The
smoke's job is to find out. **Fallback if it OOMs:** `-e SEQ=4096` (decision-preserved run) or wait for
the 2nd GB10 (seq 8192 clean).

## Pre-flight (DONE by Claude — CPU-safe)
- `~/fine-tuning/data/train-coach-v3.jsonl` — **174 rows, 94 approve / 80 feedback**, `source=synthetic_v3`,
  COACHSPLIT-reshaped (task_id+turn+decision lead), 0 holdout leakage. Production-format prompts rendered
  by the REAL `AgentInvoker._build_coach_prompt(synthesis=True)`; gold verdicts written by an Opus
  teacher-Coach and **gated on decision==deterministic-gold + a guard-checker** (172/176 kept; 2 dropped).
  Matched (clean↔flaw) bundle pairs across all 7 absence-of-failure guards + approve-traps; edge-dense on
  the base's Step-0 misses.
- `~/fine-tuning/data/holdout_synth_v3.jsonl` — **30 bundle-format cases (15 fb / 15 ap)**, the eval gate.
  **Base baseline on this set: FA 13.3% (2/15), FF 13.3% (2/15).** (2 cases — SYN-019, SYN-028 — were
  flagged ambiguous by the Step-0 blind-verify; excluding them the base is FA 13.3% / FF 7.7%.)
- `~/fine-tuning/scripts/` — `train_coach_moe.py`, `eval_coach.py`, `mem_watchdog.sh`,
  `run_coach_v3_smoke.sh`, `run_coach_v3_full.sh` (both default `SEQ=6144`, override via `-e SEQ=...`).

## Step A — STOP the fleet (freeze prevention; frees the 121 GB pool)
```bash
systemctl --user stop forge-autobuild-runner forge-langgraph-sidecar llama-swap
docker stop forge-prod
pkill -f "llama-server" 2>/dev/null || true
nvidia-smi --query-compute-apps=pid,used_memory --format=csv   # must be EMPTY before launching
```

## Step B — SMOKE (~10 min) — this is the seq-6144 MEMORY probe. 3 terminals.
```bash
# Terminal 2 — watchdog FIRST (kills the container if free RAM < 11 GB i.e. used > ~110 GB):
bash ~/fine-tuning/scripts/mem_watchdog.sh coach-ft-v3 11
# Terminal 3 — watch the climb (read STEP 40, not step 1):
watch -n 5 nvidia-smi
# Terminal 1 (tmux new -s coach-ft-v3):
docker run --gpus all --name coach-ft-v3 --rm \
  -v ~/fine-tuning/data:/workspace/data \
  -v ~/fine-tuning/output:/workspace/output \
  -v ~/fine-tuning/scripts:/workspace/scripts \
  -v ~/.cache/huggingface:/root/.cache/huggingface \
  nvcr.io/nvidia/pytorch:25.11-py3 \
  bash /workspace/scripts/run_coach_v3_smoke.sh 2>&1 | tee ~/fine-tuning/output/v3-smoke.log
```
**GO/NO-GO (paste the log to Claude):** `[G1]` trainable ≥ ~1.0% (expect ~1.88%), `[G3]` sdpa,
`[G4]` moderate masked%, loss decreasing, **and nvidia-smi peak at STEP 40 < ~110 GB.**
- Peak climbing toward ~110 GB by step 40 → **NO-GO at 6144.** Ctrl-C; relaunch with `-e SEQ=4096`
  (decision-preserved) or defer to the 2nd GB10.

## Step C — FULL run (~40–60 min; 3 epochs × 174 rows; keep the watchdog running)
```bash
docker run --gpus all --name coach-ft-v3 --rm \
  -v ~/fine-tuning/data:/workspace/data -v ~/fine-tuning/output:/workspace/output \
  -v ~/fine-tuning/scripts:/workspace/scripts -v ~/.cache/huggingface:/root/.cache/huggingface \
  nvcr.io/nvidia/pytorch:25.11-py3 \
  bash /workspace/scripts/run_coach_v3_full.sh 2>&1 | tee ~/fine-tuning/output/v3-full.log
```
The allocator high-water **climbs over the epoch** — watch nvidia-smi past step 40/80. Abort (Ctrl-C;
watchdog backstops a freeze) if it crosses ~110 GB. Overridable: `-e SEQ=4096 -e EPOCHS=2`.

## Step D — EVAL the fine-tune on the bundle-format holdout (fleet still STOPPED → GPU free)
```bash
docker run --gpus all --name coach-ft-v3-eval --rm \
  -v ~/fine-tuning/data:/workspace/data -v ~/fine-tuning/output:/workspace/output \
  -v ~/fine-tuning/scripts:/workspace/scripts -v ~/.cache/huggingface:/root/.cache/huggingface \
  nvcr.io/nvidia/pytorch:25.11-py3 \
  bash -lc 'pip install -q transformers==5.5.4 peft "datasets==4.3.0" "accelerate==1.10.0" && \
    pip install -q --no-deps unsloth unsloth_zoo bitsandbytes && cd /workspace/scripts && \
    python eval_coach.py --model-path /workspace/output/coach-gemma4-26b-moe-v3/merged-16bit \
      --holdout-file /workspace/data/holdout_synth_v3.jsonl --max-tokens 96 \
      --report /workspace/output/v3-eval.json' 2>&1 | tee ~/fine-tuning/output/v3-eval.log
```
**Read the `[holdout ...]` block** (ignore the probe set — that loads the old player-report-only
hard_cases). **WIN = FA AND FF both < ~20% and beating base 13.3% / 13.3%.** Paste `v3-eval.log`.

## Step E — RESTORE the fleet (reverse order; llama-swap first)
```bash
systemctl --user start llama-swap
sleep 5
systemctl --user start forge-langgraph-sidecar forge-autobuild-runner
systemctl --user reset-failed forge-autobuild-runner 2>/dev/null || true
docker start forge-prod
curl -s http://localhost:9000/v1/models | head -c 200
```

## Decision gate
- **Both rates < base (≤ ~13% / ~13%), traps held** → bundle-format FT calibrated; greenlight a
  UD-Q4_K_XL serve build + a `coach-ft-v3` llama-swap route, and a clean seq-8192 retrain on the 2nd GB10.
- **FA down but FF up (over-rejection)** → the trap coverage is thin (scary_stderr recovered, but 2 path
  traps dropped); scale traps in the generator and retrain.
- **No improvement over base** → base+bundle is already near the ceiling for this model; the value was the
  Step-0 finding (serve the bundle), and FT is optional. Consider scaling the corpus or the 2nd-GB10 run.
- **seq 6144 OOMs** → `-e SEQ=4096` (decision-preserved; tests the FA/FF gate, terser verdicts) or wait
  for the 2nd GB10 (seq 8192, 0% truncation).
