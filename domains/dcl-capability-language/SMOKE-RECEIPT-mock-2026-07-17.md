# SMOKE RECEIPT — dcl-capability-language mock end-to-end (2026-07-17)

**Verdict: PASS.** The generation lane runs end-to-end with **zero real model calls**. All
28 model-style requests went to a local OpenAI-compatible stub on an ephemeral port; **nothing
left for `:9000` or any LLM endpoint.** The deterministic truth source (the vendored DCL
compiler) and the defect injector were the REAL ones — never mocked.

- Factory SHA at smoke: `94eeaf8` (C1). Node: `v24.15.0`. Python venv: `.venv`.
- Harness: `domains/dcl-capability-language/smoke_mock.py` (self-contained; in-process
  threaded stub server; real `OpenAICompatibleClient` from `src/dcl/generate.py` pointed at
  it; an HTTP Coach adapter that also talks only to the stub).
- Full test suite after the smoke: **2160 passed** (unchanged from the C1 baseline; no
  existing test edited).

## Command (verbatim)

```bash
cd ~/Projects/appmilla_github/agentic-dataset-factory
source .venv/bin/activate
PYTHONPATH=src python domains/dcl-capability-language/smoke_mock.py
```

## What it drives

1. **PHASE A — author, `limit=6`.** 6 briefs; the stub returns 4 clean vocab-skeleton
   capabilities, 1 dirty-then-clean (fails the compiler once → real diagnostics fed back →
   compiles on retry), 1 coach-rejected. Real compile gate; real contamination refusal at
   brief-load and row-mint.
2. **PHASE B — repair, `limit=6`.** REAL injector (`src/dcl/recipes.py`) + REAL compiler on
   the offline-rendered compiling skeletons; the stub teacher authors only the `<think>`
   rationale (the corrected text is the pre-injection original by construction).
3. **PHASE B2 — repair re-run** (same seed/config) to prove deterministic `row_id`s.
4. **MERGE** both phases into `output/dcl-capability-language/` with a manifest.

## Console output (verbatim)

```
# stub OpenAI-compatible server: http://127.0.0.1:34875/v1  (ephemeral port 34875; :9000 untouched)

## PHASE A — author (mode=dcl_author, limit=6)
   author_accepted=5 author_rejected=1 train=4 eval_dcl=1

## PHASE B — repair (mode=dcl_repair, limit=6)
   repair_written=6 skipped_anchor=0 train=6 eval_dcl=0

## PHASE B2 — repair re-run (same seed/config) for determinism
   deterministic repair row_ids: True (6 ids identical)

## MERGE -> output/dcl-capability-language/ (+ manifest)

## ASSERTIONS (over output/dcl-capability-language/)
   [1] ShareGPT parse: all 11 rows validate
   [2] compile sweep: 11/11 accepted capabilities compile ok:true
   [3] repair byte-equality: all 6 corrections == a pre-injection original; all broken inputs fail the compiler
   [4] manifest: train.total=10 eval.total=1 by_mode(train)={'dcl_author': 4, 'dcl_repair': 6} contamination=pass visibility='private (DF-008)'
   [5] rejected.jsonl: 1 row, reason='coach_rejected'
   [6] stub traffic: player_calls=21 coach_calls=7 -> ALL local (:34875); :9000 requests = 0
```

## Assertions proven (maps to the C2 acceptance list)

| # | Assertion | Result |
|---|-----------|--------|
| 1 | Rows in `output/dcl-capability-language/` parse as ShareGPT | 11/11 validate (`contracts.validate_row`) |
| 2 | **Corpus-level** compile guarantee: every accepted/corrected capability compiles `ok:true` | 11/11 clean (checker swept over the whole output) |
| 3 | Repair completions byte-equal the pre-injection originals | all 6 corrections == a rendered original; all 6 broken inputs fail the compiler |
| 4 | Manifest counts + embedded contamination result correct | train.total=10, eval.total=1, by_mode/by_type/by_recipe consistent, `contamination_check.status=pass`, `visibility="private (DF-008)"` |
| 5 | `rejected.jsonl` carries rejects with reasons | 1 row: `{"mode":"dcl_author","reason":"coach_rejected","brief":"brief-006"}` |
| 6 | Deterministic `row_id`s for repair mode across re-run | True — 6 ids identical (PHASE B == B2) |
| 7 | ZERO real model calls / no `:9000` traffic | 28 stub calls (21 player + 7 coach), all local; `:9000` = 0 |

## Corpus-level checker sweep (self-verify command — verbatim, re-runnable)

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

Result:
```
swept 11 rows | compile-clean 11 | FAILURES 0
CORPUS OK
```

## Notes

- The mock corpus in `output/dcl-capability-language/` is **gitignored** (not committed) — it
  is smoke evidence, not a shipped dataset. A real run overwrites it (with a `*.bak` backup).
- The smoke deliberately routes the Coach over HTTP to the same stub, so **every** model-style
  call (author, retry, revise, teacher rationale, coach verdict) is proven local.
- Manifest `dataset_id` for the smoke is `dcl-phase1-smoke-mock` to distinguish it from a real
  run's `dcl-phase1-train-v1`.
