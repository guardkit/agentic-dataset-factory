# RUNBOOK — building the QAV (QA-verifier) seeded-defect dataset

> **READY-STATE (2026-07-20).** The generation engine (`src/qav/generate.py`), the injector +
> recipes + harvest + gold-negatives + contamination + manifest validators (`src/qav/**`), and
> the run driver (`domains/qa-verifier/run_qav_generation.py`) all exist and pass a full unit
> suite with **zero real model calls and zero network** (`tests/test_qav_generate.py`). What is
> left is one attended run on the GB10 with the fleet up **and** guardkit importable against each
> corpus repo's pytest substrate. This run has TWO real-work stages: bundle regeneration (CPU /
> pytest-substrate-dominant — `guardkit gather_evidence` over each mutated worktree) and the
> teacher rationale (the only GPU stage). Nothing here needs the internet. Datasets are private
> (DF-008).

---

## The one-minute version

1. Make sure your local model server (`llama-swap` on port **9000**) is up.
2. **Stop the keepalive timer** so loading the big model doesn't knock the fleet over.
3. Confirm guardkit imports against each corpus repo (the per-repo `interpreters:` in the config).
4. In a `tmux` window, run **one command** (the driver) pointed at this domain's config, **with a
   tiny `--limit` first** (pilot), read the rows, then run full.
5. When it finishes: look at `manifest.json`, run the one self-check, snapshot the output, then
   **restart the keepalive timer**.

## The one mental model

**The injector is the boss, not the model.** Every seeded row's verdict and findings are fixed by
the injector — we plant a known defect into a known-green task and we already know the label. The
teacher model *only* writes the `<think>` reasoning that leads to that fixed verdict; it never
decides the verdict. So a "bad" teacher run can waste time or get rows rejected by the Coach gate,
but it can never poison the dataset with a wrong label. Two kinds of seeded row are produced:

- **seeded_code (primary)** — plant a defect into a real task's tree, then *honestly regenerate*
  the evidence bundle with guardkit's own `gather_evidence`. The bundle is real; only the code is
  sabotaged. The label is `reject` + the injected `{class, locus}`.
- **seeded-control green** — the *same* machinery with a no-op patch, so a true-green regenerated
  bundle is labelled `approve`. This controls for any "was regenerated" cue.

Plus **seeded_bundle** (augmentation, capped at 25% of seeded rows — cue-audited hard) and
**harvest** (real historical bundles + curator outcomes). The **4 gold negatives** are always
written to `eval_qav` (the must-catch holdout) and their source tasks never seed a training row.

---

## Prerequisites (check these once, before you start)

- **The model server is up on :9000** (`llama-swap`, OpenAI-style API at `http://localhost:9000/v1`).
  Check: `curl -s http://localhost:9000/v1/models`. The two this run uses:
  - `gpt-oss-120b` — the teacher (writes the `<think>` rationales).
  - `coach-ft-v3` — the row-quality gate (judges rationale-vs-label consistency only).
- **`OPENAI_API_KEY` is set to any non-empty value** (the local server ignores it): `export
  OPENAI_API_KEY=local`.
- **guardkit imports against each corpus repo.** `seeded_code` regeneration drives
  `guardkit CoachValidator.gather_evidence` over each repo's worktree using that repo's pytest
  substrate. Resolve the interpreter per-repo (the SIBTESTENV01 lesson) — the `interpreters:`
  block in `agent-config.yaml` names each repo's venv python. If guardkit is not importable the run
  **refuses loudly** (`GatherEvidenceRegenerator`) rather than emitting unchecked rows — by design.
- **The Python environment is ready.** From the repo root: `source .venv/bin/activate`.

## ⚠️ THE KEEPALIVE GOTCHA (do this — it is the one thing that bites)

Loading `gpt-oss-120b` is heavy. If the `llama-swap-keepalive` timer fires mid-load, it revives
the rest of the fleet on top of the big model and you run out of memory (OOM). So, verbatim from
the build-plan precedent:

```bash
# Keepalive OFF (idempotent — often already inactive, but VERIFY; it revives the fleet on top
#    of gpt-oss otherwise -> OOM):
sudo systemctl stop llama-swap-keepalive.timer
systemctl is-active llama-swap-keepalive.timer   # expect: inactive
```

Do this **before** the run. Turn it back **on after** (see "When it finishes").

## PILOT-SMALL-FIRST (always pilot before the full run)

Never launch the full thing blind. Run a **tiny pilot first**, eyeball the output, *then* run full.

```bash
cd ~/Projects/appmilla_github/agentic-dataset-factory
source .venv/bin/activate
export OPENAI_API_KEY=local

# 1. SPIKE — one row, so you can read it in a minute and confirm the whole pipe works:
PYTHONPATH=src python domains/qa-verifier/run_qav_generation.py \
    --config domains/qa-verifier/agent-config.yaml --limit 1

# 2. PILOT — ~10 rows, interleaved recipes, to spot-check quality (the B11 validation bar
#    is Rich spot-checks >= 10; the 4 gold negatives are among them by name):
PYTHONPATH=src python domains/qa-verifier/run_qav_generation.py \
    --config domains/qa-verifier/agent-config.yaml --limit 10
```

Open `output/qa-verifier/train.jsonl` and `eval_qav.jsonl`, read a couple of rows, run the
self-check (below). If the labels are right, the `<think>` reasons over real bundle fields, and the
cue-audit is clean, proceed to the full run.

---

## The full run — exact commands

```bash
cd ~/Projects/appmilla_github/agentic-dataset-factory
source .venv/bin/activate
export OPENAI_API_KEY=local

# 1. Keepalive OFF (see the gotcha above):
sudo systemctl stop llama-swap-keepalive.timer
systemctl is-active llama-swap-keepalive.timer   # expect: inactive

# 2. Make sure the pilot cap is OFF for the full run. The shipped config keeps `limit:` COMMENTED
#    OUT; if you uncommented it for a pilot, comment it back:
grep -n "limit" domains/qa-verifier/agent-config.yaml   # expect: the limit line commented out

# 3. Launch inside tmux so the run survives your SSH session dropping:
tmux new -s qav-gen
source .venv/bin/activate
export OPENAI_API_KEY=local
PYTHONPATH=src python domains/qa-verifier/run_qav_generation.py \
    --config domains/qa-verifier/agent-config.yaml \
    2>&1 | tee run_logs/qav_gen_$(date +%Y%m%d-%H%M%S).log
# detach from tmux: Ctrl-b then d      reattach later: tmux attach -t qav-gen
```

That single driver command reads the models + settings from the config, wires the real teacher +
Coach clients to `:9000` and the real `GatherEvidenceRegenerator`, runs the seeded pipelines (plus
harvest if outcomes are wired) into `output/qa-verifier/`, and writes `manifest.json` at the end —
**refusing to finish** if the embedded contamination check does not pass.

### `--resume` behaviour (read this — it's different from `agent.py`)

This generator is **fresh-start, not checkpoint-resumable.** There is no `--resume`. Each run backs
up any existing `output/qa-verifier/*.jsonl` and `manifest.json` to `*.bak`, then regenerates from
scratch. If a run is interrupted (power, OOM, crash), just **run the command again** — your last
complete corpus is preserved as `*.bak`.

---

## When it finishes

1. **Snapshot + restore serving posture.**
   ```bash
   cp -r output/qa-verifier output_backup_qav-<label><N>_$(date +%Y%m%d-%H%M%S)
   sudo systemctl start llama-swap-keepalive.timer   # keepalive back ON
   ```
   > Standing footnote: before you re-enable keepalive, re-read the live probe list
   > (`/usr/local/bin/llama-swap-keepalive.sh`) — the coach-ft-v3 allowlist edit is a separate
   > serving-posture item, not something this run changes. Never assume it.
2. **Read the manifest** — `output/qa-verifier/manifest.json` (also written to
   `domains/qa-verifier/manifests/qav-phase1-train.manifest.json`). The parts that matter:
   - `counts` → rows by `by_verdict`, `by_dc_class`, `by_ground_truth_source`, `by_generation_mode`.
   - `balance_report` → `approve_share` should sit at 0.50 ±0.10 and
     `ugly_green_share_of_approves` ≥ 0.45 for a bulk run (a pilot may be intentionally off-balance).
   - `contamination_check.status` → must be **`"pass"`** (the run already refuses otherwise, but
     re-read it). If it ever says `fail`, stop and raise it — do not train.
   - `visibility` → **`"private (DF-008)"`**. This dataset never leaves the fleet.
3. **Self-verify the whole corpus** (run these yourself):
   ```bash
   cd ~/Projects/appmilla_github/agentic-dataset-factory && source .venv/bin/activate

   # (a) every emitted row re-validates against the OUTPUT-CONTRACT:
   PYTHONPATH=src python - <<'PY'
   from qav.contracts import validate_row
   from qav.contamination import load_jsonl
   from pathlib import Path
   d = Path("output/qa-verifier")
   rows = load_jsonl(d/"train.jsonl") + load_jsonl(d/"eval_qav.jsonl")
   bad = []
   for r in rows:
       try: validate_row(r)
       except Exception as e: bad.append((r["metadata"]["row_id"], str(e)))
   print(f"swept {len(rows)} rows | valid {len(rows)-len(bad)} | FAILURES {len(bad)}")
   print("CORPUS OK" if not bad else f"BROKEN: {bad[:5]}")
   PY

   # (b) the standalone contamination gate (belt-and-braces over the embedded check):
   PYTHONPATH=src python scripts/qav_contamination_check.py \
       --train output/qa-verifier/train.jsonl --eval output/qa-verifier/eval_qav.jsonl
   # expect: VERDICT: PASS  (exit 0)
   ```
   Expect `CORPUS OK` and `VERDICT: PASS`. Any failure means the corpus is not ready to train.

### Output locations (what you get)

| File (in `output/qa-verifier/`) | What it is |
|---|---|
| `train.jsonl` | the training rows (seeded_code, seeded-control, seeded_bundle, harvest), ShareGPT format |
| `eval_qav.jsonl` | the frozen hold-out slice + the 4 gold negatives (never trained on) |
| `rejected.jsonl` | rows the Coach gate / cue-audit / teacher-refusal turned away, with reasons |
| `manifest.json` | counts + the embedded contamination check + provenance pins |
| `*.bak` | your previous run's files, kept automatically |

---

## What NOT to do

- **Do not edit `src/qav/**` or `agent-config.draft.yaml`.** The engine builds ON the frozen
  validators; the draft is the spec-half sketch (this run uses `agent-config.yaml`).
- **Do not publish the dataset anywhere.** It is private (DF-008). No uploads, no sharing.
- **Do not skip the keepalive stop.** It is the one step that causes an OOM.
- **Do not trust a manifest whose `contamination_check.status` is not `pass`.** Hard stop.
- **Do not commit into the corpus repos.** They are read-only (venue rule) — scratch worktrees
  under `generation.scratch_dir` only; they are cleaned up per row.

---

## Troubleshooting

| Symptom | Cause → fix |
|---|---|
| `guardkit CoachValidator unavailable` (loud refusal) | guardkit not importable against the target repo. Resolve the per-repo interpreter/venv (`interpreters:` in the config, the SIBTESTENV01 lesson). The run refuses on purpose rather than emitting unchecked rows. |
| The run hangs or errors on the first teacher call | The model server/seat isn't ready. Check `curl -s http://localhost:9000/v1/models` lists `gpt-oss-120b` and `coach-ft-v3`. `gpt-oss-120b` can take a few minutes to load on the first call — give it time. |
| Out of memory (OOM), box thrashing | Almost always the keepalive timer revived the fleet on top of `gpt-oss-120b`. Stop the run, `sudo systemctl stop llama-swap-keepalive.timer`, confirm `inactive`, start over. |
| `contamination_check.status: fail` / the run raises at finalize | A hold-out capability or a train/eval overlap slipped in. The run refuses to write an invalid manifest. Capture the `intersection_row_ids` / `sibling_variant_violations` and raise it; this should not happen (it's enforced in code + guaranteed by same-split-for-siblings assignment). |
| Lots of rows in `rejected.jsonl` | Read the `reason` field: `coach_rejected` (rationale inconsistent with the fixed label), `teacher_refusal` (empty teacher output — a RESULT, not retried), `cue_leakage` (a surface artefact in the bundle), `schema_invalid`. A high reject rate is a quality signal to note, not a crash. |
| `source-task discovery is a generation run` (RuntimeError) | You ran a seeded mode without wiring the git-worktree source provider. That provider (approved-sha resolution + per-repo interpreter) is the attended-run wiring — see the open points in the code-half README / commit. |
| Interrupted run | No resume — just re-run the driver command. Your prior corpus is safe as `*.bak`. |

---

*Proof this all works offline: `tests/test_qav_generate.py` drives the whole engine against stub
teacher/coach/regenerator with zero network (a test poisons `socket.socket`). The mechanism is
`src/qav/**`; the code-half contract is `domains/qa-verifier/OUTPUT-CONTRACT.md`.*
