# QAV seeded-defect mode — code half (WS2-B11, delivered 2026-07-08 [Opus 4.8])

The **one dataset-factory code change** — the seeded-defect generation mode and its
supporting transforms — implemented per the committed spec half (adf `11db17a`:
`GOAL.md` / `OUTPUT-CONTRACT.md` / `PLAN-qav-phase1-dataset-generation.md` /
`SPEC-qav-gold-negatives.md` / `agent-config.draft.yaml`) and
`ai-transition/docs/qav-fine-tune-build-plan.md` Step 1.

**This is mechanism + tests only — NO generation runs.** Running it against the real repos
to emit rows (driving `gather_evidence`, calling the teacher model) is the GB10 generation
run, post-window, per the program-plan calendar. Nothing here touches `output/`, the GB10,
or a teacher model.

## Where the code lives

| Module | Role | Spec anchor |
|---|---|---|
| `src/qav/contracts.py` | Row / label / metadata / bundle validators; `row_id`; system prompt (pinned to `GOAL.md`) | OUTPUT-CONTRACT §1–§4 |
| `src/qav/recipes.py` | The 11 injector recipes as deterministic, in-memory-file-map mutations; loud `AnchorNotFound` | PLAN §3 table |
| `src/qav/injector.py` | `inject()` (self-checks "NOTHING else"), `inject_control()` (seeded-control), `GatherEvidenceRegenerator` seam (generation-run boundary, never called by tests) | PLAN §2 |
| `src/qav/harvest.py` | Walk `coach_evidence_turn_*.json`, post-hoc labels, ugly-green detection | PLAN §2 harvest transform |
| `src/qav/gold_negatives.py` | The 4 gold negatives; verbatim probe (GN-3 survives) → else reconstruct | SPEC-qav-gold-negatives.md |
| `src/qav/contamination.py` | row_id disjointness + sibling-variant + gold-source-task exclusion | PLAN §6 |
| `src/qav/manifest.py` | Manifest writer + validator; invalid without a passing embedded check | OUTPUT-CONTRACT §5 |
| `scripts/qav_contamination_check.py` | CLI gate (exit 0/1); runnable now on written jsonl | PLAN §6 |

Tests: `tests/test_qav_{contracts,injector,harvest,gold_negatives,contamination,manifest}.py`
(54 tests). Run: `python -m pytest tests/test_qav_*.py -q`.

## Gates met (WS2-B11 code-half GATE)

- **Seeded-control:** each of the 11 recipes on a known-green fixture produces the labelled
  defect and NOTHING else (only declared files change; the DC-03 call-site defect leaves the
  production call site broken); a missing anchor raises loudly; `inject_control` is a true
  no-op. — `test_qav_injector.py`
- **Contamination REFUSES a poisoned manifest:** row_id intersection, sibling-variant
  straddle, and gold-negative-source-task leakage each fail the check and make the manifest
  invalid by contract. — `test_qav_contamination.py`, `test_qav_manifest.py`
- **The 4 gold negatives reconstruct field-by-field per SPEC and validate;** GN-3 is served
  verbatim from disk when the corpus is present (`bundle_schema_sha=888906f2`). —
  `test_qav_gold_negatives.py`
- **Manifest validates against OUTPUT-CONTRACT §5** with an embedded passing contamination
  check and two-sided balance report. — `test_qav_manifest.py`

## What the generation run (Step 2+, GB10, post-window) still wires

`agent-config.draft.yaml` → live config; `GatherEvidenceRegenerator` against per-repo pytest
substrates (the SIBTESTENV01 per-repo interpreter lesson); the teacher `<think>` stage
(gpt-oss-120b) authoring rationale against the injector-fixed labels; then pilot → Rich
hand-audit → bulk → manifest finalize. Hold-out discipline (`split: eval_qav` at creation,
the 4 gold negatives never trained, no training row from the 4 source tasks) is enforced in
`contamination.py`, not by convention.
