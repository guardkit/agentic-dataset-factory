# DCL Row Contract — author + repair rows, metadata, manifest

**Status:** G3 lane code half, 2026-07-17 (Opus 4.8). The row shapes the training pipeline
consumes and the manifest the handover carries. Deterministic truth source: the vendored DCL
compiler (`src/dcl/bin`, pin `4f9fbe56`) — every label is compiler-fixed, never model-decided.

## 1. Row envelope

One row = one JSON object per line (`.jsonl`), ShareGPT envelope matching the factory's existing
`train.jsonl` conventions:

```json
{
  "messages": [
    {"role": "system",    "content": "<the GOAL.md DCL authoring system prompt>"},
    {"role": "user",      "content": "<§2 — the authoring brief, or the broken .dcl + diagnostics>"},
    {"role": "assistant", "content": "<§3 — a fenced ```dcl capability (repair rows prefix a <think>)>"}
  ],
  "metadata": { … §4 … }
}
```

Chat template at train time: `gemma-4` (NOT `gemma-4-thinking`). Two modes:

- **AUTHOR** (`mode=dcl_author`, `type=direct`): a brief → a compiler-clean capability.
- **REPAIR** (`mode=dcl_repair`, `type=reasoning`): a broken capability + diagnostics → the fix.

## 2. Input contract (user message)

**AUTHOR** — the feature brief followed by the compiler-verified closed vocabulary reference
(`src/dcl/vocab-reference.md`, embedded verbatim so the row is self-contained and
serving-faithful):

```
## Feature brief
<one-paragraph brief>

## DCL vocabulary reference (closed — author using ONLY these literals)
<vocab-reference.md>

## Task
Author a single DCL capability that models the brief. … Emit exactly one ```dcl fenced block …
```

**REPAIR** — the broken `.dcl` plus the VERBATIM compiler diagnostics JSON (exactly what
`dcl-check.mjs` emitted), then the repair instruction:

```
## Broken DCL capability
```dcl
<broken capability>
```

## Compiler diagnostics (verbatim from the DCL compiler)
```json
[ {"severity":"error","code":"DCL_SEM_ACTOR_KIND_UNKNOWN", …}, … ]
```

## Task
This capability fails to compile. Diagnose the cause … changing only what the diagnostics require …
```

## 3. Assistant contract

- **AUTHOR**: exactly one ```` ```dcl ```` fenced capability, **no `<think>` block** (direct).
  The capability compiles clean — the label fixed by the compiler.
- **REPAIR**: a `<think>` rationale (names the `DCL_*` error + the minimal fix), then exactly one
  ```` ```dcl ```` fenced **corrected** capability. The correction equals the pre-injection
  original **by construction** (semantic preservation is guaranteed).

## 4. Row metadata

```json
{
  "row_id": "dcl-<sha256[:16] of the user message content>",
  "domain": "dcl-capability-language",
  "layer": "behaviour",
  "type": "direct" | "reasoning",
  "mode": "dcl_author" | "dcl_repair",
  "split": "train" | "eval_dcl",
  "recipe_id": "<defect recipe id, repair rows only; null on author rows>",
  "provenance": {"source": "synthetic-brief" | "derived" | "harvested", "vocab_pin": "4f9fbe56", "compiler_pin": "4f9fbe56"},
  "compile_verified": true
}
```

`row_id` is content-addressed on the user message — what the contamination check hashes.
`split: eval_dcl` rows are named at creation and NEVER enter a training manifest. `recipe_id`
names the defect recipe (`src/dcl/recipes.py`) a repair row was minted from. `compile_verified`
is always `true` — a row whose label the compiler did not verify is not admissible.

## 5. Hold-out + contamination (enforced in code)

The four frozen `dcl-heldout` exam capabilities are the eval and are NEVER trained. Enforced in
`src/dcl/contamination.py`:

- **Content denylist:** the sha256s of `dcl-held-00{1,2,3}` solutions + `dcl-held-004`
  solution/broken-input. A brief/source/emitted capability matching one is refused loudly.
- **Identity denylist:** the exam capability/endpoint names — `stats`/`/stats`/`GetStats`,
  `version`/`/version`, `uptime`/`/uptime` — matched (camelCase-aware) against briefs and
  capability text (NOT the vocabulary boilerplate, which legitimately contains "version").
- **Split disjointness:** `train.row_id ∩ eval.row_id = ∅`, with a stratified `eval_dcl` slice
  frozen at creation by a recorded seed + `holdout_fraction`.

## 5a. Harvested real briefs (W2c — `provenance.source == "harvested"`)

Beyond the synthetic brief bank, the corpus generator can draw **real feature briefs** from a
factory run's plan-commit capture queue (`.guardkit/dcl-capture/queue.jsonl`, `kind == "brief"`
rows). Enabled via config: `generation.briefs_source: harvested` + `corpus.harvest_queue: <path>`
(default `synthetic` leaves the pipeline byte-identical). Loading is `src/dcl/harvest.py`.

- **AUTHOR-ONLY.** A harvested brief carries the natural-language request + machine criteria but
  NO structured synthetic fields, so it mints AUTHOR rows only — it can never drive repair
  minting (`render_reference_capability` needs those fields). The generator skips it for repair
  and notes the skip in the manifest `harvest` block.
- **M-22 gate, per brief.** Before a harvested brief becomes a row, the frozen-exam denylist
  (§5) scans its request + criteria; any hit REFUSES that brief loudly (recorded, never yielded,
  zero rows) without aborting the batch. Malformed queue lines are counted + logged, never fatal.
- **Provenance shape.** Harvested rows extend the pinned triple with three REQUIRED keys naming
  where the brief came from (FORBIDDEN on every other source):

  ```json
  {"source": "harvested", "vocab_pin": "4f9fbe56", "compiler_pin": "4f9fbe56",
   "repo": "<org/name or path>", "feature": "<feature id>", "run": "<correlation id>"}
  ```

  A harvested row is still `mode: dcl_author`, `type: direct`, compiler-verified — the label is
  compiler-fixed exactly as for synthetic author rows.
- **Manifest.** A harvested run embeds a `harvest` block (`scanned` / `refused` / `malformed` /
  `author_rows_from_harvest` / `repair_skipped_author_only` + the author-only note) and counts
  `by_provenance_source` per split. Synthetic-only runs omit the `harvest` block entirely.

## 6. Handover manifest

`output/dcl-capability-language/manifest.json` — per-mode / per-type / per-split / per-recipe
counts, a `compile_verified` tally (must equal total), and the **embedded** contamination-check
result. A manifest without a passing embedded check is **invalid by contract**
(`dcl.manifest.validate_manifest`). Datasets are **private (DF-008)**. Chat template `gemma-4`.
