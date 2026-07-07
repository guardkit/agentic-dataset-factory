# QAV Fine-Tune Scope — Training / Serving / Scheduling (the WS4 half)

> **Plan-of-record pointer (added 2026-07-08):** the umbrella phase pair now lives at
> `ai-transition/docs/qav-fine-tune-{scope,build-plan}.md` (`1ace79d`, PO-pair-templated) — it
> federates this doc (the WS4 training/serving half) with the WS2 dataset half in this directory
> and NEVER re-decides either. Day-of operator checklist: `../../docs/BUILDPLAN-fine-tunes-po-and-qav-2026-07-07.md`.
> This doc remains the owning authority for training/serving/scheduling decisions.

**Status:** WS4-S8, 2026-07-07 (Fable 5, in-window). This is the fine-tune scope doc the
2026-06-11 findings named (`guardkit/docs/retro/conversation-starter-qa-verifier-finetune.md`,
piece #1) and nobody wrote — its blocker, COACHGATHER01, was decided **Option B-min on
2026-07-01**, so the input contract is settled and the doc can exist. Piece #3 of that starter
(the glue policy) is **NOT this doc's scope and remains unwritten** — flagged, not owned here.
**Binding parents:** `ai-transition/docs/ws4-learning-flywheel-scope-and-build-plan-2026-07-07.md`
§5.3 (this doc graduates its training/serving half) and the ownership split dated 2026-07-07:
**WS2 owns dataset shape + eval + deployment position; WS4 owns training, serving, scheduling.**
Everything dataset-side below is a POINTER to the WS2-B11 spec half committed earlier tonight
(`11db17a`, this directory) — never a duplication.

## THE GATE — FEAT-EVAL-QAV

**FEAT-EVAL-QAV (fleet-evals, filed by WS2 B12 — single registration; WS4 consumes it, never
re-registers)** is this fine-tune's checkpoint gate and the gate for every later model bump:

- **Must-catch bar:** 100% on the 4 gold negatives (`SPEC-qav-gold-negatives.md` — SMP-002 /
  SMP-003 / 10AC / DD4F, `eval_qav` from birth) + a held-out seeded-slice catch rate WS2/Rich
  set at B12 filing (precedent: the coach-v3 bar).
- **False-block ceiling:** over-reject rate on held-out honest greens (clean AND ugly) — the
  two-sided discipline; a judge that rejects every blemish is a rubber stamp in reverse.
- **Pre-registered dispositions:** PASS/FAIL written into the grade run's RESULTS template
  **before** the run (WS4 §3.4 discipline). Frozen suite — never edited after B12 freezes it;
  anything a grade reveals becomes an additive suite.
- **No deploy without a graded PASS.** A checkpoint that fails stays a directory, not a seat.

Status at writing: B12 not yet filed (trails B11's Opus code half — WS2 build plan §B12,
which already carries a dated note pointing at tonight's manifest format).

## 1. Seat definition (pointer)

The QAV fine-tune is the **L5 judgment layer**: it reads a CoachEvidenceBundle (B-min,
`CoachEvidenceBundle.to_dict()` pinned at guardkit `41a0ebe457`) and renders
approve/reject-with-findings. It does not drive the app — driving is WS2's live-gate runner.
Full judgment criteria, system prompt, and generation targets: **`GOAL.md`** (this dir, WS2).
Row/label/manifest contracts: **`OUTPUT-CONTRACT.md`** (this dir, WS2).

## 2. Base model (D9-compliant)

**Gemma-4-26B-A4B MoE (`unsloth/gemma-4-26B-A4B-it`), the coach-ft lineage** — the same served
base as the coach/PO judgment fleet.

- **D9 different-family rule** (`workstream-a-dark-factory-consolidation-scope.md:128`;
  restated `po-fine-tune-scope.md:265`): the QAV must not share a model family with the Player
  whose work it judges. Satisfied: the Player is gpt-oss-120b (in-factory) / frontier Claude
  (autobuild); the judgment fleet is Gemma. **Any future SLM-Player lane re-checks this
  pairing** (see `domains/player/GOAL.md`). Namespace caveat carried from WS4 §5: the
  factory-scaling findings doc has a *separate* D1–D15 register whose D9 is the FinProxy fork —
  do not conflate.
- **The QAT decision is binding** (`../coach-agent/RESEARCH-gemma4-qat-decision.md`, resolved
  2026-06-19): do NOT swap to the QAT checkpoint as fine-tune base; export/serve UD-Q4_K_XL
  (q4_k_m interim), **never q4_0** (70.2% top-1 collapse).
- Chat template **`gemma-4`, not `gemma-4-thinking`** (the tutor template-leak lesson;
  already pinned in `OUTPUT-CONTRACT.md` §1 — restated because it is a training-time knob).

## 3. Training recipe (pointer + QAV deltas)

**Recipe = the Unsloth QLoRA precedent:** `../coach-agent/RUNBOOK-coach-fine-tune.md`
(Unsloth + TRL inside the NVIDIA PyTorch container; smoke ~14 min / full ~71 min incl. merge +
GGUF export on the GB10), which itself inherits the domain-agnostic phases (0.5
freeze-prevention, 3 launch, 4 monitor) from `../architect-agent/RUNBOOK-architect-fine-tune.md`.
The QAV run gets its own `RUNBOOK-qav-fine-tune.md` at training time, written as deltas against
the coach runbook exactly as the coach runbook is written as deltas against the architect's.
The launch discipline carries: **manual SSH-paste launch, never Claude→tmux→docker from the
GB10** (two documented freezes).

Deltas the QAV runbook must resolve (the coach precedent decides *how*, these decide *what*):

1. **Input, not corpus curation:** training input is the **B11 handover manifest**
   (`manifests/qav-phase1-train.manifest.json`, format = `OUTPUT-CONTRACT.md` §5). Staging
   gates, in order: (a) manifest's embedded `contamination_check` = pass — a manifest without
   one is invalid by contract; (b) `balance_report` inside bands (approve≈reject 50/50 ±10%,
   ≥45% ugly greens — PLAN §5); (c) `bundle_schema_shas` mixing only when additive
   (OUTPUT-CONTRACT §2 drift rule); (d) a re-run leakage check vs
   `qav-phase1-eval.manifest.json` at staging time (coach Phase 0.1 precedent — belt and
   braces over the factory's check, because the eval manifest may have grown since generation).
2. **No prepare-time oversampling.** The coach recipe rebalances at data-prep
   (`prepare_coach_sft.py` copies=round(weight)); QAV balance is enforced **at generation**
   by the manifest bands. The prep step converts and audits; it does not weight. If a future
   phase needs weighting, it re-uses the copies=round(weight) precedent and records it in the
   manifest, not in silence.
3. **Seq-length audit is the critical Phase-0 gate.** QAV rows are the longest in the fleet:
   the user message is a full serialized bundle and the verdict sits at the END (truncation
   eats the label, the coach lesson squared). Measure with the real serving tokenizer
   (`llama-tokenize` on the served GGUF — coach precedent: 3.50 chars/token, p95/p99/max
   drive the choice) **before** picking `--max-seq-length`; do not inherit the coach's number.
   If p99 exceeds what the GB10 can train, the answer is documented truncation strategy or
   row exclusion with a dated note — never silent tail loss.
4. **Class-imbalance tripwire:** the conversion audit prints per-verdict and per-DC-class
   counts against the manifest's `counts` block; any mismatch aborts (the coach-v2 81/19 →
   87.5% false-approval saga is why this is a hard gate, not an eyeball).

## 4. Serving (llama-swap)

- **Entry:** new llama-swap model id (e.g. `qav-ft-v1`) on the GB10, endpoint **:9000** (not
  :8080). Placement/config precedent: `../coach-agent/SERVING-coach-ft.md` (GGUF staging under
  `/opt/llama-swap/models/`, UD-Q4_K_XL target, `--reasoning` posture verified at serve).
- **Staged-deploy discipline (WS4 §6.2, binding): on-demand only.** Preload membership is a
  scarce, contended resource (the R-G5 lesson); promotion to preload is a separate, evidenced
  decision after burn-in. The previous GGUF entry is never deleted at deploy time; rollback =
  config revert + reload, rehearsed once as part of the deploy runbook's acceptance.
- **Keepalive probe-list changes are a named runbook phase with a Pass: check, never a side
  effect** — the proven foot-gun (`../coach-agent/RESULTS-coach-v3.md:166–168`; the coach-ft-v3
  allowlist edit is *still* an outstanding operator action at writing — re-read the live probe
  list, never assume it).
- **Schema at serving = GBNF grammar, not the fine-tune** (the conversation-starter's working
  note, proven by COACHSPLIT and verified in `SERVING-coach-ft.md`): the verdict trio
  (`verdict`/`findings`/`ground_truth_source`, OUTPUT-CONTRACT §3) gets a grammar threaded
  per-request on the toolless synthesis call, exactly as `coach-verdict.gbnf` does for the
  Coach. The fine-tune trains the *judgment*; the grammar guarantees the *shape*. **Phase GRAM
  (FEAT-GRAM-001/002, WS4-S9) is the generalized form of this cure and is scheduled before any
  new SLM role goes live** (WS4 §5 design rule) — the QAV seat is a direct beneficiary: its
  grammar is one entry in GRAM's per-role/mode registry rather than a bespoke file.
- **Consumer:** the v1 deterministic guardkit runner (WS2's decision, DF filing in the B13
  batch) invokes the model toolless and parses the fenced trio. Where the seat sits in the
  orchestrator, and the v1→v2 (agentic, guardkitfactory substrate) evolution, is **WS2's
  deployment position — pointer only** (`ws2-qa-verifier-and-last-mile-scope-design-2026-07-07.md`
  §3/§6).

## 5. Scheduling vs the GB10 calendar

**`factory-program-plan-2026-07-07.md` §2.2 owns the box — this doc books slots, it does not
re-decide the calendar.** Fixed points at writing: 07-09 HSBC demo = quiet window; 07-09
evening → ~07-13 = the 82h PO Phase-3 run owns the box; WS2 V1's live-gate window books after
it (w/c 07-14).

Dependency chain and GPU shape of each stage:

| Stage | Owner | GPU load | Earliest slot |
|---|---|---|---|
| B11 code half (injector, harvest transform, contamination check, manifest writer) | WS2 [Opus 4.8] | none (code only) | now — code lands any time |
| P2 pilot (~40 rows) + P3 bulk generation | WS2, factory run | teacher-rationale stage only (bundle regen is CPU/pytest-dominant) | **after ~07-13** (82h run ends); never during demo/run windows |
| B12 files FEAT-EVAL-QAV | WS2 [Opus 4.8] | none | after P2/P3 manifests exist |
| QLoRA train + GGUF export | **WS4** [Operator]+[Opus 4.8] | full box, but short (~71-min scale per coach precedent; QAV seq-length may stretch it — Phase-0 audit tells) | post-82h window, coordinated with WS2 V1's booking via the program plan |
| Grade vs FEAT-EVAL-QAV | WS4 consumes fleet-evals | eval-scale inference | immediately after train, same booked window |
| Serve (on-demand entry) + burn-in | WS4 [Operator] | negligible (on-demand) | after graded PASS |

Operational constraints carried from the fleet record:

- **Keepalive timer state varies — check, don't assume** (observed inactive/enabled 2026-07-07).
  Pausing it for train/eval windows needs Rich's sudo; it is a P0-preflight item in the QAV
  runbook exactly as in the 82h run's (WS4 §3.3 P0).
- Bulk generation's teacher stage and the training run are **separate bookings** — do not
  assume one window covers both; the manifest freeze between them is where B12's eval
  provisioning happens.
- **DF-008:** dataset rows, manifests, weights, and eval corpora stay private end-to-end
  (already stamped `visibility: private` in the manifest format).

## 6. Versioning + continual learning

Per WS4 §6.2 (binding for every role): the trained checkpoint enters the content-addressed
chain — **dataset sha (manifest `dataset_id` + file sha256s) → base model + adapter → GGUF
digest → llama-swap entry name** — recorded in the QAV runbook's RESULTS. Every grade emits a
`grading_outcome` episode (backward-edge contract, fleet-memory `974669c`) carrying the
checkpoint id, so this seat's eval history is queryable from the store from its first grade.
qav-ft-v2's trigger comes from the continual-learning loop (WS4 §6.2 / S10), fed by
`live_verdict` + `review_report` rows once WS2's runner emits them — not from vibes.

## 7. Open items (dated 2026-07-07, owners named)

| # | Item | Owner / when |
|---|---|---|
| 1 | B13 register filing batch (incl. the QAV runner v1/v2 decision → DF record) | Rich + [Opus 4.8], scheduled 07-08 (program plan §2.2) |
| 2 | B12 files FEAT-EVAL-QAV (bars set with Rich at filing) | WS2, after B11 code half |
| 3 | 9 of 16 DC ids unnamed in durable record — Phase-1 seeds named classes only; coverage widens when the taxonomy doc lands | flagged to WS3's seam work (PLAN §3 dated note) |
| 4 | Phase GRAM (FEAT-GRAM-001/002) scheduling — before QAV goes live | WS4-S9 [Opus 4.8] |
| 5 | Glue policy (conversation-starter piece #3) — still unwritten | unowned; surfaced to Rich with this doc |
