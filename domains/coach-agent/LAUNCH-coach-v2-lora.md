# LAUNCH — Coach v2 balanced LoRA (manual GB10 run)

**Why you launch this, not Claude:** `RUNBOOK-coach-fine-tune.md` is explicit — *"Phase 3 launch
is a manual SSH-paste workflow, NOT driven from a Claude Code session running on the GB10. The
Claude→tmux→docker chain caused two GB10 freezes."* Claude prepared + validated everything below;
**you run the docker steps.** A freeze needs a power-cycle, so the memory watchdog is mandatory.

## What this tests
Step 3 proved the cue-hardened synthetic data is potent (false-approval 94%→12% on the cue-immune
real holdout) but few-shot over-rejects. This LoRA tests whether **balanced-gradient fine-tuning
calibrates** it: gate = false-approval **AND** false-feedback both **< ~20%** on `holdout_balanced_real`.

## Pre-flight (DONE by Claude — CPU-safe)
- `~/fine-tuning/data/train-coach-v2balanced.jsonl` — **196 rows, 50/50** (84 real fb + 14 synth fb +
  98 approves), coachsplit-reshaped, 0 holdout leakage, 14.3% truncate@4096 (rationale tail only).
  - secondary: `train-coach-v2synthonly.jsonl` (28 rows, synth-only — too small; not recommended).
- `~/fine-tuning/data/holdout_balanced_real.jsonl` — 32 real rows (16 fb/16 ap), the eval gate.
- `~/fine-tuning/scripts/` — `train_coach_moe.py`, `eval_coach.py`, `run_coach_v2_smoke.sh`,
  `run_coach_v2_full.sh`, `mem_watchdog.sh`.
- Baseline to beat (already measured): **base gemma4-coach = 94% false-approval** on this holdout.

## Step A — STOP the fleet (freeze prevention; frees the 121 GB pool)
```bash
systemctl --user stop forge-autobuild-runner forge-langgraph-sidecar llama-swap
docker stop forge-prod
pkill -f "llama-server" 2>/dev/null || true
nvidia-smi --query-compute-apps=pid,used_memory --format=csv   # must be EMPTY before launching
```

## Step B — SMOKE (~10 min). Terminal 1 (tmux), Terminal 2 (watchdog), Terminal 3 (nvidia-smi)
```bash
# Terminal 2 — watchdog FIRST:
bash ~/fine-tuning/scripts/mem_watchdog.sh coach-ft-v2 9
# Terminal 3:
watch -n 5 nvidia-smi
# Terminal 1 (tmux new -s coach-ft-v2):
docker run --gpus all --name coach-ft-v2 --rm \
  -v ~/fine-tuning/data:/workspace/data \
  -v ~/fine-tuning/output:/workspace/output \
  -v ~/fine-tuning/scripts:/workspace/scripts \
  -v ~/.cache/huggingface:/root/.cache/huggingface \
  nvcr.io/nvidia/pytorch:25.11-py3 \
  bash /workspace/scripts/run_coach_v2_smoke.sh 2>&1 | tee ~/fine-tuning/output/v2-smoke.log
```
**GO/NO-GO (paste the log to Claude):** `[G1]` trainable ≥ ~1.0% (expect ~1.88%; else Unsloth
pre-PR-4913), `[G3]` sdpa, `[G4]` moderate masked%, `[G5]` peak < ~85 GB, loss decreasing.
Abort (Ctrl-C in T1, watchdog handles freeze) if nvidia-smi > ~100 GB.

## Step C — FULL run (~30–45 min; 3 epochs × ~196 rows). Same docker, full script:
```bash
docker run --gpus all --name coach-ft-v2 --rm \
  -v ~/fine-tuning/data:/workspace/data -v ~/fine-tuning/output:/workspace/output \
  -v ~/fine-tuning/scripts:/workspace/scripts -v ~/.cache/huggingface:/root/.cache/huggingface \
  nvcr.io/nvidia/pytorch:25.11-py3 \
  bash /workspace/scripts/run_coach_v2_full.sh 2>&1 | tee ~/fine-tuning/output/v2-full.log
```
(Keep the watchdog running. `EPOCHS=2 DATA=...` overridable via `-e EPOCHS=2 -e DATA=...`.)

## Step D — EVAL the fine-tune on the balanced REAL holdout (fleet still STOPPED → GPU free)
```bash
docker run --gpus all --name coach-ft-v2-eval --rm \
  -v ~/fine-tuning/data:/workspace/data -v ~/fine-tuning/output:/workspace/output \
  -v ~/fine-tuning/scripts:/workspace/scripts -v ~/.cache/huggingface:/root/.cache/huggingface \
  nvcr.io/nvidia/pytorch:25.11-py3 \
  bash -lc 'pip install -q transformers==5.5.4 peft "datasets==4.3.0" "accelerate==1.10.0" && \
    pip install -q --no-deps unsloth unsloth_zoo bitsandbytes && cd /workspace/scripts && \
    python eval_coach.py --model-path /workspace/output/coach-gemma4-26b-moe-v2/merged-16bit \
      --holdout-file /workspace/data/holdout_balanced_real.jsonl --max-tokens 96 \
      --report /workspace/output/v2-eval.json' 2>&1 | tee ~/fine-tuning/output/v2-eval.log
```
**WIN = false-approval AND false-feedback both < ~20%** (vs base 94% FA). Paste `v2-eval.log`.

## Step E — RESTORE the fleet (reverse order; llama-swap first)
```bash
systemctl --user start llama-swap
sleep 5
systemctl --user start forge-langgraph-sidecar forge-autobuild-runner
systemctl --user reset-failed forge-autobuild-runner 2>/dev/null || true
docker start forge-prod
curl -s http://localhost:9000/v1/models | head -c 200   # confirm llama-swap back
```

## Decision gate
- **Both rates < ~20%** → the balanced LoRA calibrated; greenlight scaling the synthetic corpus +
  a UD-Q4_K_XL serve build + a permanent `coach-ft` llama-swap route.
- **FA low but FF still high** → over-rejection persists at 196 rows → bump approve ratio
  (`build_lora_corpus_v2.py --approve-ratio 1.3`) and/or scale the corpus, then retrain.
- **FA back up** → undertrained → more epochs, or the synthetic signal needs scaling.
