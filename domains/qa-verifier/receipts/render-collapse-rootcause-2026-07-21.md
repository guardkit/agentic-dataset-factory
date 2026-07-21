# Receipt — RENDER-COLLAPSE ROOT CAUSE (evidenced) + study_tutor anchor verdict (2026-07-21)

> **ROOT CAUSE FOUND, EVIDENCED WITH TWO LIVE REGENERATIONS.** The seeded sweep's "26 DC-03/DC-05
> legs → 0 unique rows" is **not** row_id keying too narrowly, **not** bundle-field truncation, and
> **not** a subtle test-selection miss. For every discovered source task the regenerated bundle is a
> **pure function of the materialized static `task_work_results.json` record** — the mutated worktree
> is **never executed**. guardkit `gather_evidence` short-circuits at `partial_gate_abort` (a
> *spurious* arch-review gate failure) **before** it runs independent tests / requirements / wiring /
> coverage. So control, DC-03, DC-05 and R-ABSENT-junit all render **byte-identical** bundles per
> task; the only reason any reject row banks at all is write-order (R-ABSENT-junit sorts first and
> stamps a reject label on a green bundle). **The recipe class is structurally unfit on the current
> regeneration — recorded honestly here, like the 5 documented expected-misses.** Extending
> study_tutor reject anchors is therefore not just yield-zero but **actively harmful** (it would
> cannibalize the 7 clean approve controls into 7 mislabeled reject rows). No frozen file touched; no
> anchor added; the finding does not support one.

---

## The one-minute version

`row_id` content-addresses the whole rendered bundle (`contracts.row_id`, FROZEN — and correct). Two
mutated legs collapse to one row **iff their regenerated bundles are byte-identical**. They are —
because `gather_evidence`, handed the original green run-record materialized into the worktree
(`.guardkit/autobuild/<task>/task_work_results.json`, the round-3 poison-fix), sees
`arch_review_required=true` + `arch_review_passed=false` (the record carries **no** arch result — arch
review runs in a separate phase), computes `all_gates_passed=false`, and **returns
`partial_gate_abort`, skipping every step that would touch the mutated worktree** (guardkit
`coach_validator.py` docstring L3132-3134 + code L3453-3460). The bundle is then a replay of the
static record — identical across all 7 recipe legs of a task, and identical to the no-op control.
The planted TypeError never surfaces because no worktree test run ever happens.

## Reproduction 1 — DC-03 callsite == control, byte-identical

Live regeneration (real guardkit `gather_evidence` via the bridge; no model, no GPU, no fleet),
guardkit **TASK-QAWE-001 @ 799cefd0**, record materialized from
`.guardkit/archive/FEAT-C332/run1-artifacts-TASK-QAWE-001`:

- `R-DC03-callsite` mutated **2 real files** (`full_doc_parser.py` dropped the `chunk_threshold`
  kwarg + its unit test; production call site left broken).
- Regenerated bundle sha256[:16] = **`db72fb201b23fb5e`**.
- No-op **control** bundle sha256[:16] = **`db72fb201b23fb5e`** — **IDENTICAL**.
- `gathering_status = partial_gate_abort`; `tests.all_passed = null`, `tests.tests_run = null`
  (independent test run **never executed**); `wiring / mocked_seam / independent_tests /
  coverage_details.*` all null; `tests.tests_passed = true` is **read from the static record**, not
  re-derived.

Cross-check against banked data: the sweep's banked **R-ABSENT-junit reject** row for TASK-QAWE-001
(`output/qa-verifier/eval_qav.jsonl`) hashes to the **same `db72fb201b23fb5e`** — i.e. the "reject"
row's evidence bundle is byte-for-byte the honest green control bundle. The reject label's
finding-locus ("independent junit suppressed while self-report claims pass") describes a defect that
**is not present anywhere in the bundle it is attached to**.

## Reproduction 2 — study_tutor is fully source-blind

study_tutor **TASK-PRV-001 @ 94f3331** (340-file scoped map). Control bundle vs a deliberately
**broken** worktree (a `SyntaxError` appended to a source `.py` + an `assert False` failing test
appended to `features/conftest.py`):

- control sha256[:16] = **`d5f5bee8fed4c8f8`**
- broken-source sha256[:16] = **`d5f5bee8fed4c8f8`** — **IDENTICAL**
- both `gathering_status = partial_gate_abort`, `all_gates_passed = false`.

A syntax error and a hard test failure produce **zero** bundle change. The regeneration reads the
static record and aborts; the worktree contents are irrelevant.

## Why the short-circuit fires (the spurious gate)

The materialized `task_work_results.json` for these APPROVED-green tasks records
`quality_gates: {tests_passing: true, tests_passed: 173, coverage_met: null}` and **no arch_review
field at all** — arch review is a separate phase not captured in `task_work_results.json`.
`gather_evidence` nonetheless applies the `feature` profile's `arch_review_required=true`, cannot find
a pass, sets `arch_review_passed=false` → `all_gates_passed=false` → `partial_gate_abort`. The abort
is an artifact of **replaying an arch-incomplete record**, not a real gate failure.

## Is it fixable at the bridge? — Probed, and NO (not with a one-liner)

Calling `gather_evidence(..., skip_arch_review=True)` on the same two worktrees:

- `gathering_status` flips **`partial_gate_abort → complete`**, `all_gates_passed → true`, and the
  control vs DC-03 bundles now **differ** (`eef1e433…` vs `0375e9c4…`). The abort short-circuit is
  confirmed as the first-layer cause.
- **BUT the difference is not the defect.** The only differing field is
  `independent_tests.duration_seconds` (`0.0666` vs `0.0562`) — **non-deterministic wall-clock
  jitter**. The independent-test oracle **mis-detected the stack as `node`**, ran `npm test`, and got
  `returncode 127` ("absent signal", identical for both legs). The mutated **Python** code was never
  exercised; the DC-03 unit test stays green by construction anyway.

So `skip_arch_review=True` **alone is net-harmful**: it would defeat dedup by timing noise, minting
"unique" rows that carry identical evidence with divergent labels — pure label-noise poison, worse
than the current honest collapse. A real fix is **multi-layer** and out of this lane's frozen scope
(and needs a GB10 generation-run to validate):
1. don't abort regeneration on an arch gate the replayed record never measured (`skip_arch_review`),
2. pin the correct per-repo **stack/interpreter** so the mutated suite actually runs (the node
   mis-detect defeats it today),
3. scrub non-deterministic fields (`duration_seconds`) out of the row_id surface,
4. and even then DC-03/DC-05 are green-at-unit by design — they surface only in
   wiring/mocked_seam/behavioural_oracle, which need `guardkitfactory` + the deeper analysis to run.

## Fixable vs structural — the verdict

| layer | status |
|---|---|
| `contracts.row_id` (whole-bundle hash) | **correct, FROZEN** — not the bug; not narrow keying, not truncation |
| recipe mutation machinery | **correct** — it plants real source defects (2 files changed, verified) |
| regeneration path (materialize gate-failing record → `gather_evidence` short-circuit → static replay) | **STRUCTURALLY source-blind** for every task whose record has `all_gates_passed=false` (all discovered tasks) — the true layer, out of frozen scope, needs a validated GB10 redesign |

**seeded_code SOURCE injection cannot produce a defect-bearing bundle on this corpus.** This is the
same visibility limit already documented for `R-DC12-planvisible` / `R-DC14-narrative` (their signal
lives in the gitignored materialized record, not the source map) — **generalized**: the gate-abort
makes *every* recipe's source mutation invisible, not just the record-sourced ones.

## study_tutor anchors — 0/11 is a SYMPTOM, and "fixing" it is harmful

The receipts name study_tutor anchor coverage (0/11) the "single highest-yield reject-side lever."
The render-collapse finding **refutes that**:

- study_tutor tasks are `partial_gate_abort` too (Reproduction 2) → any reject plant regenerates a
  bundle **identical to that task's control**.
- In `_run_seeded_code`, reject recipes are written **before** the control. Identical bundle ⇒ same
  `row_id` ⇒ the reject recipe **claims the row first** and the control **dedups out**.
- Net effect of adding a study_tutor-hitting reject anchor: each of the **7 clean approve controls**
  (currently the only surviving seeded approve rows) **flips to a reject row** whose bundle is an
  honest green regeneration (`tests_passed:true`, `honesty_score 1.0`, no discrepancies) carrying a
  reject label + a finding-locus for a defect not in the evidence. That is exactly the false-BLOCK
  poison QAV exists to prevent, and it destroys the approve side.

**Verdict:** all 11 reject recipes are **EXPECTED-MISSES on study_tutor under the current
regeneration** — recorded here, matching the discipline of the existing 5 expected-misses (semantic
fidelity over hit-rate). No study_tutor reject anchor is added; the finding does not support one, and
adding one is a corpus regression. The study_tutor **approve/control** side is unaffected and
continues to bank 7 distinct rows via record-distinctness.

## The real reject-volume levers (engine-external, already wired)

1. **`seeded_bundle` mode** (cap 25%, currently 0): mutate a **serialized bundle's fields** directly
   to a documented defect signature — bundle-visible **by construction**, gated by the cue-audit.
   This is the sanctioned "target what the evidence exercises" path.
2. **`harvest` mode**: real committed bundles + ratified labels — genuine reject signal (the corpus
   run banked the first 3 real MP-R merge_review_caught rejects this way).
3. A validated regeneration redesign (the 4-layer fix above) — a GB10 lane, not this one.

## Method / provenance

- Reproductions run locally via `qav.discover.discover_source_tasks` +
  `qav.regenerate.SubprocessBridgeRegenerator` + a direct `CoachValidator.gather_evidence` probe
  under the guardkit venv. **Zero model / GPU / fleet work** (bundle regen is CPU/pytest-substrate
  only). Corpus repos read-only: guardkit `b68c9e9d`, study-tutor `f843cb5` — HEADs unchanged; only
  detached scratch worktrees, cleaned after.
- guardkit source grounding: `guardkit/orchestrator/quality_gates/coach_validator.py`
  L3132-3134 (docstring: *"Quality gates failed → `partial_gate_abort`. Independent tests /
  requirements validation are not run."*) + L3453-3460 (the short-circuit return).
- **Shared-venue note:** at investigation time this tree carried a concurrent lane's uncommitted
  work (`src/qav/discover.py`, `src/qav/generate.py`, `agent-config.yaml`) and HEAD had advanced to
  `c0d749e`. This receipt is committed path-limited; **no code file was touched** by this lane.
- No frozen file modified (`contracts.py` / recipe machinery/families/ids all byte-unchanged). No
  push. Datasets private (DF-008).
