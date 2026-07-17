# RUNBOOK — building the DCL capability-language dataset

> **READY-STATE (2026-07-17).** Everything you need is built and proven. The generator, the
> vendored DCL compiler, the brief bank (50 briefs), and the run driver all exist and pass a
> full mock smoke with **zero real model calls** (`SMOKE-RECEIPT-mock-2026-07-17.md`). What is
> left is one attended run on the GB10 with the fleet up. A full run of today's 50-brief bank
> produces roughly **50 author rows + ~450 repair rows (~500 total)**; the corpus grows toward
> the GOAL's 300 author / 720 repair targets as the brief bank is expanded later. Cost:
> **roughly 10–20 hours** wall time (sequential model calls at ~1–2 min each, plus a few
> minutes to load `gpt-oss-120b` the first time). Nothing here needs the internet or any paid
> API — it all runs on your own box.

---

## The one-minute version

1. Make sure your local model server (`llama-swap` on port **9000**) is up.
2. **Stop the keepalive timer** so loading the big model doesn't knock the fleet over.
3. In a `tmux` window, run **one command** (the driver) pointed at this domain's config.
4. Wait. Watch the counters go up.
5. When it finishes: look at `manifest.json`, run the one self-check command, then
   **restart the keepalive timer**.

That's it. The rest of this document is detail and safety nets.

## The one mental model

**The compiler is the boss, not the model.** Every capability in the dataset is checked by a
real DCL compiler before it is allowed in. The AI model only *proposes* text; the compiler
*decides* whether it's correct. So a "bad" run can waste time, but it can never poison the
dataset with capabilities that don't actually compile. Two kinds of examples are produced:

- **author** — "here's a plain-English feature; write the DCL capability" (the model writes,
  the compiler checks).
- **repair** — "here's a broken capability and the compiler's exact complaint; fix it" (we
  break a known-good capability on purpose, so we already hold the correct answer).

---

## Prerequisites (check these once, before you start)

- **The model server is up on :9000.** This is `llama-swap`, serving an OpenAI-style API at
  `http://localhost:9000/v1`. Check: `curl -s http://localhost:9000/v1/models` should list
  models. The two this run uses:
  - `gpt-oss-120b` — the author/teacher (writes capabilities and repair rationales).
  - `gemma4-coach` — the coach (judges whether a capability matches the brief).
- **`OPENAI_API_KEY` is set to any non-empty value.** The local server ignores it, but the
  client library wants *something* there. `export OPENAI_API_KEY=local` is fine.
- **Node is installed** (`node --version`, needs v18+). The DCL compiler runs on Node. The
  GB10 Spark carries Node v24 — good. If `node` is missing, the run refuses loudly rather than
  emitting unchecked rows (by design).
- **The Python environment is ready.** From the repo root: `source .venv/bin/activate`.

## ⚠️ THE KEEPALIVE GOTCHA (do this — it is the one thing that bites)

Loading `gpt-oss-120b` is heavy. If the `llama-swap-keepalive` timer fires mid-load, it
revives the rest of the fleet on top of the big model and you run out of memory (OOM). So,
**verbatim from the build-plan precedent**:

```bash
# Keepalive OFF (idempotent — often already inactive, but VERIFY; it revives the fleet
#    on top of gpt-oss otherwise -> OOM):
sudo systemctl stop llama-swap-keepalive.timer
systemctl is-active llama-swap-keepalive.timer   # expect: inactive
```

Do this **before** the run. Turn it back **on after** the run (see "When it finishes").

> Standing footnote (pre-dates this lane): before you ever re-enable keepalive, its allowlist
> `/usr/local/bin/llama-swap-keepalive.sh` still probes `gemma4-coach`, not `coach-ft-v3` —
> that's a separate serving-posture item, not something this run changes.

## Smoke-first discipline (always pilot before the full run)

Never launch the full thing blind. Run a **tiny pilot first**, eyeball the output, *then* run
full. The pilot is the same command with a small `--limit`:

```bash
# PILOT: author only, 4 examples, so you can read them in a minute.
PYTHONPATH=src python domains/dcl-capability-language/run_dcl_generation.py \
    --config domains/dcl-capability-language/agent-config.draft.yaml \
    --mode dcl_author --limit 4
```

Open `output/dcl-capability-language/train.jsonl`, read a couple of rows, run the self-check
(below). If they look right and compile clean, proceed to the full run.

---

## The full run — exact commands

```bash
cd ~/Projects/appmilla_github/agentic-dataset-factory
source .venv/bin/activate
export OPENAI_API_KEY=local

# 1. Keepalive OFF (see the gotcha above):
sudo systemctl stop llama-swap-keepalive.timer
systemctl is-active llama-swap-keepalive.timer   # expect: inactive

# 2. Launch inside tmux so the run survives your SSH session dropping:
tmux new -s dcl-gen
source .venv/bin/activate
export OPENAI_API_KEY=local
PYTHONPATH=src python domains/dcl-capability-language/run_dcl_generation.py \
    --config domains/dcl-capability-language/agent-config.draft.yaml \
    2>&1 | tee run_logs/dcl_gen_$(date +%Y%m%d-%H%M%S).log
# detach from tmux: Ctrl-b then d      reattach later: tmux attach -t dcl-gen
```

That single driver command reads the models + settings from the config, wires the real clients
to `:9000`, and runs both modes (author then repair) into
`output/dcl-capability-language/`, writing `manifest.json` at the end.

**Config note (why you don't touch the root `agent-config.yaml`).** The driver takes
`--config`, so you point it straight at this domain's own file
(`domains/dcl-capability-language/agent-config.draft.yaml`). You do **not** need to copy it
over the repo-root `agent-config.yaml`. That root file is shared by other tools and other
sessions — leave it alone. (If you ever *do* wire a run the old `agent.py` way that reads the
root config, **back up the root `agent-config.yaml` first**: `cp agent-config.yaml
agent-config.yaml.bak`, then restore it after. The `--config` path above avoids all of that.)

**Pilot vs. full.** For a pilot, add `--mode dcl_author --limit 4` (small, author-only). For
the full run, omit both — the config's `mode: both` and full brief bank take over. (You can
also raise the config's `limit:` or set it to run everything; a pilot cap of `20` is set in the
config today.)

### `--resume` behaviour (read this — it's different from `agent.py`)

This generator is **fresh-start, not checkpoint-resumable.** There is no `--resume`. Each run:

- **backs up** any existing `output/dcl-capability-language/*.jsonl` and `manifest.json` to
  `*.bak` (so you never silently lose a prior corpus), then
- **regenerates from scratch.**

If a run is interrupted (power, OOM, crash), just **run the command again** — your last
complete corpus is preserved as `*.bak`. Because the run is only ~10–20h and cheap to repeat,
this is deliberate simplicity, not a limitation to work around. If you want a natural
mid-point checkpoint, run `--mode dcl_author` to completion first, copy the output aside, then
run `--mode dcl_repair` — but the single `mode: both` run is the normal path.

---

## When it finishes

1. **Snapshot + restore serving posture.**
   ```bash
   cp -r output/dcl-capability-language output_backup_dcl_$(date +%Y%m%d)
   sudo systemctl start llama-swap-keepalive.timer   # keepalive back ON
   ```
2. **Read the manifest** — `output/dcl-capability-language/manifest.json`. The parts that matter:
   - `counts.train` / `counts.eval_dcl` → how many rows, split by `by_mode` (author vs repair),
     `by_type` (direct vs reasoning), and `by_recipe` (which defects).
   - `contamination_check.status` → must be **`"pass"`** (no hold-out leakage, no train/eval
     overlap). If it ever says `fail`, stop and raise it — do not train on it.
   - `visibility` → **`"private (DF-008)"`**. This dataset never leaves the fleet.
3. **Self-verify the whole corpus compiles** (the corpus-level guarantee — run it yourself):
   ```bash
   cd ~/Projects/appmilla_github/agentic-dataset-factory && source .venv/bin/activate
   PYTHONPATH=src python - <<'PY'
   from dcl import checker, contracts
   from dcl.contamination import load_jsonl
   from pathlib import Path
   d = Path("output/dcl-capability-language")
   rows = load_jsonl(d/"train.jsonl") + load_jsonl(d/"eval_dcl.jsonl")
   bad = [r["metadata"]["row_id"] for r in rows if not checker.compile(contracts.extract_capability(r)).ok]
   print(f"swept {len(rows)} rows | compile-clean {len(rows)-len(bad)} | FAILURES {len(bad)}")
   print("CORPUS OK" if not bad else f"BROKEN: {bad}")
   PY
   ```
   Expect `CORPUS OK`. This compiles every accepted/corrected capability in the output; any
   failure means something is wrong and the corpus is not ready to train.

### Output locations (what you get)

| File (in `output/dcl-capability-language/`) | What it is |
|---|---|
| `train.jsonl` | the training rows (author + repair), ShareGPT format |
| `eval_dcl.jsonl` | the frozen hold-out slice for evaluation (never trained on) |
| `rejected.jsonl` | rows the coach or compile-gate turned away, with reasons |
| `manifest.json` | the counts + the embedded contamination check + provenance pins |
| `*.bak` | your previous run's files, kept automatically |

---

## What NOT to do

- **Do not edit `src/qav/**` or any other domain.** This lane is additive; the QAV and other
  domains stay exactly as they are.
- **Do not publish the dataset anywhere.** It is private (DF-008). No uploads, no sharing
  outside the fleet.
- **Do not skip the keepalive stop.** It is the one step that causes an OOM.
- **Do not trust a manifest whose `contamination_check.status` is not `pass`.** That's a hard
  stop.
- **Do not use `scripts/run-on-gb10.sh` for this run** (see below).

## Do NOT use `scripts/run-on-gb10.sh` here — use the plain-Python path above

`scripts/run-on-gb10.sh` is for the *old* factory/PO path, not this one. Two mismatches make it
wrong for DCL:

- Its pre-flight checks **`localhost:8002`** (the old vLLM container), but this run uses
  **`llama-swap` on `:9000`** — so its check would fail (or pass for the wrong server).
- It launches **`python agent.py`**, which is the PO/factory generator, **not** the DCL
  driver.

The canonical DCL path is the plain-Python driver command shown under **"The full run"**:
`python domains/dcl-capability-language/run_dcl_generation.py --config
domains/dcl-capability-language/agent-config.draft.yaml`. Wrap it in `tmux` yourself (shown
above); that's all `run-on-gb10.sh` was doing anyway.

---

## Troubleshooting

| Symptom | Cause → fix |
|---|---|
| `node not found on PATH` (loud refusal) | Node isn't installed / not on PATH. Install Node v18+, or run on the GB10 Spark (has v24). The run refuses on purpose rather than emitting unchecked rows. |
| The run hangs or errors on the first model call | The model server/seat isn't ready. Check `curl -s http://localhost:9000/v1/models` lists `gpt-oss-120b` and `gemma4-coach`. `gpt-oss-120b` can take a few minutes to load on the first call — give it time before assuming a hang. |
| Out of memory (OOM), box thrashing | Almost always the keepalive timer revived the fleet on top of `gpt-oss-120b`. Stop the run, `sudo systemctl stop llama-swap-keepalive.timer`, confirm `inactive`, and start over. |
| `contamination_check.status: fail` in the manifest | A hold-out capability or a train/eval overlap slipped in. Stop — do not train. Capture the manifest's `denylist_violations` / `intersection_row_ids` and raise it; this should not happen (it's enforced in code). |
| Lots of rows in `rejected.jsonl` | The coach is turning capabilities away (brief-fidelity) or the compile-gate is exhausting retries. Read the `reason` field. A high reject rate is a quality signal to note, not a crash. |
| Interrupted run | No resume — just re-run the driver command. Your prior corpus is safe as `*.bak`. |

---

*Proof this all works offline: `domains/dcl-capability-language/smoke_mock.py` +
`SMOKE-RECEIPT-mock-2026-07-17.md` (full mock run, zero real model calls, corpus compiles
100%). The mechanism is `src/dcl/**`; the compiler is vendored at pin `4f9fbe56`.*
