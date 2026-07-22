# Runbook — building the Recruiter authoring corpus (the tune's training data)

**Purpose.** Generate the SYNTHETIC training corpus for the **recruiter fine-tune** — a small,
fast Qwen3-4B-class model that drafts office clerks and pipelines and PASSES the owner's hiring exam.
The recruiter sat its first real gate on 2026-07-21 and the office **refused to hire it** (receipt:
office-manager `docs/receipts/2026-07-21-recruiter-first-gate-refusal.md`): the stock workhorse
misclassified pipeline-for-clerk, faked a missing integration, and complied with a smuggled egress
grant while claiming to ignore it. This corpus is the durable cure — the DCL pilot's exact discipline
(stock 2/9 → tuned 7/9 on a frozen exam), re-aimed at hiring turns.

**The one mental model (borrowed verbatim from DCL): the office's OWN checkers are the boss, not the
model.** Every row is admitted ONLY if the office's real validators pass its drafts AND it matches the
request's authoritative sorting label. A strong teacher (`workhorse` on the Spark) merely
*proposes* the drafting turn; `deckhand config-check` and `office pipeline validate` *decide*. A bad
run can waste time; it can never poison the corpus with drafts the office would refuse.

### The teacher is `workhorse` (and why NOT `gpt-oss-120b`) — a recorded wall

The teacher is **`workhorse`** (Qwen3.6-35B-A3B) — the SAME model family the DCL corpus used as its
proven teacher, and the exact model the 2026-07-21 gate exam ran against (the stock candidate).
**`gpt-oss-120b` CANNOT be used as the teacher on this Spark (recorded 2026-07-22):** the llama-swap
residents (coach 26B + workhorse 35B + embed, all `ttl:0 --no-mmap`, ~90 GiB of the 121 GiB unified
memory) leave no room, so the 120b server OOMs on start (`exited prematurely`). This is a memory-
residency wall, not a code bug; do **not** attempt to load 120b and do **not** touch the llama-swap
config. `workhorse` is a **thinking** model, but the harness sends `chat_template_kwargs:{enable_thinking:
false}` (`player.enable_thinking: false`) to **disable** the thinking channel: measured **~5x faster**
(71s → 15s per clerk turn) and serve-faithful — the tuned recruiter is a non-thinking 4B, so a
non-thinking target matches its serve contract. (Even with thinking on, the reasoning lands in a
separate `reasoning_content` field the harness never reads, so there is no `<think>` leak either way.)
`max_tokens` is 6000 so up to four drafted files fit comfortably.

---

## The one-minute version

1. Point the harness at the Spark's llama-swap API (`http://spark-fcf6:9000/v1`, seat `workhorse`).
2. Run it **under office-manager's own venv** — that venv carries `office_manager` + `deckhand`
   (the checkers) + `pydantic` + `yaml`; the harness itself uses only stdlib `urllib` for HTTP, so
   no extra deps are needed.
3. The harness authors each brief, runs the office checkers on every draft, feeds the checker's named
   error back once (a bounded repair), and **streams** every checker-clean, class-matching,
   contamination-clean row into a staging **run dir** under `pilot-runs/` (crash-safe: append per row).
4. **Freeze** the frozen `corpus/` from one or more run dirs in a second phase (`--freeze`): global
   dedup by `row_id` and a real, per-class-stratified, deterministic-by-`row_id` ~10% held-out
   `val.jsonl`. The corpus (`train.jsonl` + `val.jsonl` + `manifest.json`) is written ONCE, and lives
   under `domains/recruiter-agent/corpus/`. **Private (DF-008).** All churn stays in `pilot-runs/`.

---

## The serve contract (why the rows are shaped as they are)

The tune must byte-match what the served recruiter actually sees (RUNBOOK-dcl-fine-tune v1.2 catch 3:
*staged targets must byte-match what the serving contract asks the model to emit*). Verified against
the office serving code (`hire/serving.py` + `live_classifier.build_agent_complete` +
`hire/loop.build_user_turn` + `hire/protocol.parse_turn`), every row is:

| Message   | Content                                                                                     |
|-----------|---------------------------------------------------------------------------------------------|
| system    | the recruiter **seed's `system_prompt`, verbatim** — vocab-in-prompt is the operating mode  |
| user      | `office_manager.hire.loop.build_user_turn(kind, request, ())` → `"The owner says:\n<request>"` |
| assistant | the raw drafting turn: a conversational message + zero or more ```` ```file:<path> ```` blocks that `parse_turn` reads |

**The recruiter's contract KEEPS its ```` ```file: ```` fences** — unlike the DCL model (whose serve
contract is bare source, so fences were stripped), the recruiter's serve format IS the fenced-block
protocol `parse_turn` parses. So targets are NOT fence-stripped; the fences are load-bearing here.

---

## Prerequisites

- The Spark's llama-swap is up and serves `workhorse`:
  `curl -s http://spark-fcf6:9000/v1/models` lists it. (Model-swapping between seats is llama-swap's
  job — just name the model; do not touch its config. `gpt-oss-120b` is unavailable as a teacher —
  see the recorded wall above.)
- Run from a box that can reach `spark-fcf6:9000` **and** import the office checkers — i.e.
  office-manager's own venv (`office-manager/.venv`). Inference happens on the Spark seat; the harness
  + checkers run CPU-only wherever you launch them (not a GPU job).
- The four eval-held sessions under `~/office-authoring/` are present (read-only) so the contamination
  denylist can add their file-hashes. If they are NOT present, the harness still runs — the hard-coded
  distinctive-phrase floor protects the run regardless (a `corpus_seen=false` note lands in the log).

---

## Smoke-first discipline (always)

Two smokes, in order — spend zero model calls until the offline one is green:

```bash
# 1. OFFLINE — prove the acceptance path + denylist + checkers wire correctly (ZERO model calls):
cd ~/Projects/appmilla_github/office-manager
OFFICE_AGENTS_ROOT=/tmp ./.venv/bin/python \
  ../agentic-dataset-factory/domains/recruiter-agent/selftest_acceptance.py
# expect: ALL GREEN (18 PASS/FAIL cases incl. both hardenings + the contamination guard)

# 2. PILOT — a small cross-class batch end-to-end through the REAL Spark + acceptance path:
DOMAIN=~/Projects/appmilla_github/agentic-dataset-factory/domains/recruiter-agent
OFFICE_AGENTS_ROOT=/tmp PYTHONPATH="$DOMAIN" ./.venv/bin/python "$DOMAIN/run_recruiter_generation.py" \
  --config "$DOMAIN/agent-config.yaml" --sample-per-class 2 --run-dir pilot-workhorse
# streams into pilot-runs/pilot-workhorse/{accepted,rejected}.jsonl + run-manifest.json
```

Read a few accepted rows and a few `rejected.jsonl` reasons. A high reject rate is a QUALITY signal
(the teacher missing the closed vocabulary), not a crash — read the reasons.

---

## The full run — two phases (generate, then freeze)

**Phase A — GENERATE (streaming, crash-safe).** Long job: launch it detached (`nohup`/`tmux`) and
poll; each accepted row is appended+flushed to the run dir immediately, so a crash loses only the
in-flight call, and re-running against the same `--run-dir` resumes without duplicating.

```bash
cd ~/Projects/appmilla_github/office-manager
DOMAIN=~/Projects/appmilla_github/agentic-dataset-factory/domains/recruiter-agent
OFFICE_AGENTS_ROOT=/tmp PYTHONPATH="$DOMAIN" nohup ./.venv/bin/python \
  "$DOMAIN/run_recruiter_generation.py" \
  --config "$DOMAIN/agent-config.yaml" --author-reps 12 --run-dir run-full \
  > "$DOMAIN/pilot-runs/run-full.out" 2>&1 &
# poll: wc -l "$DOMAIN/pilot-runs/run-full/accepted.jsonl"; tail "$DOMAIN/run_logs/recruiter_gen_*.log"
```

`--author-reps K` authors every brief K× (fresh calls at temp 0.6); distinct valid turns coexist as
distinct rows (content-addressed `row_id`), byte-identical duplicates dedupe. The seed briefs at K≈12
target the ~450-row plan (see `COVERAGE-PLAN.md`); the achieved total is an honest count, not a target
to fudge — a class that will not generate at acceptable quality is a **finding**. Grow the corpus by
adding briefs to `briefs.yaml` or raising K — never by relaxing a checker.

**Phase B — FREEZE (writes the frozen corpus once).**

```bash
OFFICE_AGENTS_ROOT=/tmp PYTHONPATH="$DOMAIN" ./.venv/bin/python \
  "$DOMAIN/run_recruiter_generation.py" \
  --config "$DOMAIN/agent-config.yaml" --freeze run-full
# writes corpus/{train.jsonl,val.jsonl,manifest.json} ONCE (global dedup + real 10% val split).
```

You may pass several run dirs to `--freeze` (e.g. `run-full run-topup`) to combine them; dedup by
`row_id` is global across them. Generation logs land under `<domain>/run_logs/`, never the shared
repo-root `run_logs/`.

---

## What the harness does, per row (the acceptance path — `acceptance.py`)

1. **Author** — the teacher (`workhorse`; see the recorded 120b wall above) is handed the recruiter's own operating rules, the closed
   vocabulary (`recruiter-vocab-reference.md`), the request's authoritative sorting, and the owner
   request; it emits the drafting turn.
2. **Materialise + check** — `parse_turn` slices the turn; each `file:` block is written to a tempdir
   and run through the office's OWN checker:
   - clerk `config.yaml` → `deckhand config-check` (`load_role_config`) — 3–6 criteria summing to 1.0,
     closed `side_effect_class`, no egress for a clerk;
   - pipeline definition → `office pipeline validate --file` (`load_pipeline_file` +
     `validate_pipeline`) — closed schedule/window/source/stage/role vocabulary, approval ceilings.
3. **Per-class predicate** — the draft's KIND must match the request's sorting label (the "sorting-rule
   label verified per row"), plus: placeholder-only goldens (pack law 2); residency (pack law 1);
   honest walls not faked integrations; the injection-probe draft grants no egress/off-allowlist/
   escaped scope (scored on what it GRANTS, not what it CLAIMS — the say-safe-do-unsafe lesson).
4. **Bounded repair (FRESH single-shot)** — a refused draft (or an otherwise-clean turn that leaks,
   see 5) gets ONE repair pass. The pass is a **fresh single-shot re-prompt**, NOT a multi-turn "that
   was wrong, fix it" continuation: the one hard requirement is folded into a fresh copy of the
   original prompt with an instruction to satisfy it SILENTLY. A continuation primes the teacher to
   narrate a correction ("here is the corrected draft") — which is a defective target, because the
   served recruiter drafts once and has no prior draft (train==serve). Still-refused → `rejected.jsonl`,
   never hand-patched.
5. **Prose-leak guard** — the turn's owner-facing MESSAGE (never the file bodies) is scanned for
   repair-narration phrases ("corrected draft", "I've updated", "the checker", "re-emit", …). A leak
   triggers the fresh repair; a leak that survives the repair → `rejected.jsonl`. This keeps every
   trained target a clean first-and-only owner turn.
6. **Contamination gate** — the whole row + every draft file is scanned against the eval-held denylist
   (`denylist.py`); any hit is refused. The four banked sessions are NEVER training data.

---

## When it finishes

- `corpus/manifest.json` (the FROZEN manifest) — row totals + per-class `{total, train, val}`, the
  `source_run_dirs`, the `player_models`, the denylist summary, the serve-contract record, and the
  `split_method`. `visibility: private (DF-008)`. Each staging run also has its own
  `pilot-runs/<run>/run-manifest.json` (attempted / accepted / rejected / deduped / contaminated).
- `corpus/train.jsonl` / `corpus/val.jsonl` — ShareGPT rows. `val.jsonl` is a real, per-class-
  stratified, deterministic-by-`row_id`, **disjoint** ~10% held-out split — a **loss-only** monitoring
  set, NOT the pass exam. **The pass exam is the four banked sessions** — Rich's attended, unlabelled
  re-sit — which are never in this corpus by construction (the denylist enforces it).
- Self-verify a sample: every accepted row's `metadata.checkers` carries the verbatim checker detail
  and `metadata.provenance` carries the seat/model/timestamp/accept_attempt; spot-read 3–4 accepted
  turns for vocabulary discipline and 3–4 `rejected.jsonl` reasons.

## What NOT to do

- **Do not hand-patch a rejected draft into the corpus.** The checker is the boss; fix the teacher
  prompt or the vocabulary reference, never the row.
- **Do not train on the four eval-held sessions** (the denylist enforces this; do not disable it).
- **Do not publish the corpus** (DF-008 private). A synthetic-only slice would be shippable by
  construction, but that is Rich's explicit call, not a default.
- **Do not touch `src/qav/**` or any other domain** — a concurrent QAV lane holds them. This lane is
  additive under `domains/recruiter-agent/**` only.
- **Do not touch the Spark's llama-swap config or the `cr0-comfyui` container** — API calls only.

---

## Artefacts (this domain)

| File | Purpose |
|---|---|
| `recruiter-vocab-reference.md` | the closed vocabulary (clerk config schema + pipeline six-section vocabulary + the sorting rule) — embedded verbatim into the teacher prompt |
| `briefs.yaml` | the coverage plan as data: the seven classes, per-class target rows, seed owner requests |
| `acceptance.py` | the acceptance path — the office's OWN checkers + per-class predicates + the contamination gate |
| `denylist.py` | the eval-held contamination denylist (distinctive-phrase floor + live file-hash set) |
| `generate.py` | the engine: `run_generation` (teacher via urllib, materialise→check→repair→**stream** to a run dir) + `freeze_corpus` (dedup + real 10% val split → frozen `corpus/`) |
| `run_recruiter_generation.py` | the driver: GENERATE (default) / FREEZE (`--freeze`); logs to `<domain>/run_logs/` |
| `pilot-runs/` | staging run dirs (`accepted.jsonl` streamed crash-safe, `rejected.jsonl`, `run-manifest.json`) + archived pilots — all corpus churn lives here |
| `corpus/` | the FROZEN deliverable, written once by freeze: `train.jsonl` + `val.jsonl` + `manifest.json` |
| `agent-config.yaml` | the run config (teacher seat, paths, reps, holdout) |
| `selftest_acceptance.py` | the OFFLINE smoke — proves acceptance + denylist + checkers with zero model calls |
| `COVERAGE-PLAN.md` | the coverage plan write-up (each class → the 2026-07-21 failure it cures + target counts) |

Downstream: this corpus feeds the fine-tune, which follows `../dcl-capability-language/`
`RUNBOOK-dcl-fine-tune.md` v1.2 (Unsloth+TRL QLoRA on Qwen3-4B-Instruct-2507; its three catches
BINDING — stock 2507 template forced by file · never train targets on near-untrained added tokens ·
targets byte-match the serve contract; merged-generation gate mandatory before GGUF). Per Rich's
2026-07-22 green-light, **training, packaging, and latency measurement all run on the Spark**.
