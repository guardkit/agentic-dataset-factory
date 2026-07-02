# PO Output Contract — Findings (OQ#4 resolution)

**Date:** 2026-07-01
**Resolves:** scope §9 **OQ#4** — pin the exact `product-owner` serving output shape so the
fine-tune's training examples mirror it (scope §5: *misaligned examples are wasted*).
**Source, verbatim-pinned:** `specialist-agent/roles/product-owner/role.yaml` +
`prompts/player_greenfield.md`, `player_extract_roadmap.md`, `player_extract_features.md`
(and the `OutputHandler` protocol, `src/specialist_agent/roles/output_handler.py`).
**Feeds:** this domain's `GOAL.md` — the serving-contract guideline, the new
`grounding_fidelity` criterion, and the Output Schema.

---

## The headline correction

The PO output is **structured JSON conforming to typed Pydantic schemas**, *not* free-form
markdown. The Player emits a JSON object → the Coach evaluates it → `ProductOwnerOutputHandler`
`parse()`s it into the typed model and `format()`s it into the written artefacts. So
**training-example assistant content must produce the mode's JSON schema** (after the `<think>`
block) — with the exact fields, enum Literals, and citation rules below — not prose
decomposition. This is the single most important thing to get right for serving-contract
alignment.

## Two written artefacts (role.yaml `output:`)

- **`roadmap.md`** — slim (epics + feature stubs), deliberately slimmed under **TASK-POFX-001**
  for James's `/po-spreadsheet-export` skill.
- **`feature_spec_inputs/<feature_id>.md`** — per-feature enriched bodies, written separately by
  the handler: `specialist_agent.roles.product_owner.handler.ProductOwnerOutputHandler`.

## Three JSON schemas, keyed by mode

### A. `ProductRoadmap` — `idea` · `greenfield` · `evolve` · `impact` · `scope` · single-pass `extract` (`--phase=full`)
Top level: `project_name`, `mode`, `epics[]`, `priority_rationale` (advisory prose),
`constraints_and_dependencies[]`, `open_questions[]`, `feature_spec_inputs[]`,
`coverage_score` (fraction, or `null` for greenfield/idea — no corpus), `source_documents[]`
(`{filename, contribution}` objects at roadmap level — never bare strings), `assumptions[]`.
- `epics[]`: `{id, name, bounded_context, description, features[], source_documents[]}`.
- `features[]` (= `FeatureSpecInput`): `{feature_id, title, description (**2+ sentences**,
  domain language, behavioural, spec-ready), bounded_context, source_documents[], constraints[],
  suggested_context_files[], depends_on[]}`.
- `feature_spec_inputs[]`: **the flattened list of ALL features as full `FeatureSpecInput`
  objects — identical objects to `epics[].features[]`, not strings or summaries.**
- `assumptions[]`: `{id, category, statement (**falsifiable**), source, confidence
  (low/medium/high), impact_if_wrong}`.

### B. `EpicPlan` — `extract` **Phase A (roadmap)**
The machine-readable handoff (`epic_plan.json`) to Phase B. Stubs ONLY — no enrichment.
- `epics[]`: `{epic_id` (**NOT `id`**)`, name, bounded_context, cited_docs[]` (**the docs Phase B
  must read for this epic — a hard-required field; empty/missing = hard failure**)`, feature_stubs[]`
  (**NOT `features`**)`}`.
- `feature_stubs[]`: **only** `{feature_id, title, intent (**one line, ≤100 chars**),
  source_citations[]}`. Any enrichment field here (`description`, `priority`, `moscow`, `value`,
  `complexity`, `acceptance_criteria`, `depends_on`, `constraints`, …) is an `ENRICHMENT_LEAK`.
- `source_citations[]`: `{document, section_path[]` (heading breadcrumb, non-empty)`,
  line_start?, line_end?, quote?` (≤200 chars)`}`.
- Also carries `coverage_score` (fraction of doc sections covered) and `nfr_candidates[]`
  (`{nfr_id, title, category}`, ids only — Phase C expands them).

### C. `EnrichmentBatch` — `extract` **Phase B (features)**
Per-stub enrichments for a **single epic**; the dispatcher **merges them onto the Phase A stubs
server-side** (delta contract, TASK-POE-DELTA-002). Emits neither `title`/`bounded_context` (the
dispatcher copies those) nor a `ProductRoadmap` envelope.
- `{project_name, epic_id, enrichments[]}`.
- `enrichments[]`: `{feature_id` (from the stub allowlist)`, description (2+ sentences),
  source_documents[]` (≥1, from `cited_docs`)`, constraints[], suggested_context_files[],
  depends_on[], type, role, priority, moscow, value, complexity, acceptance_criteria[],
  technical_notes[], risks[], open_questions[], links[]` (list of URL strings)`, field_citations{}}`.
- **Enum Literals (not prose):** `priority` ∈ {Low, Normal, High, Critical}; `moscow` ∈
  {Must (core), Must, Should, Could, Won't, N/A, ?}; `value` ∈ {1 (Lowest) … 5 (Highest)};
  `complexity` ∈ {Very easy (<.5d), Easy (≈1d), Normal (2-5d), Complex (5-10d), Very complex
  (>10d), Unknown, N/A}.
- **`field_citations{}`** — every non-default enrichment field must be evidenced with a citation
  (`{document, section_path[], …}`), keyed by field name (`description`, `priority`, `moscow`,
  `acceptance_criteria[0]`, …).

## The disciplines the training MUST teach (serving detection patterns)

These are the deployed Coach's penalties. Grounding/citation is central to `extract` and was
**absent from the GOAL.md's original six criteria** — hence the added `grounding_fidelity`:

| Serving detection pattern | GOAL.md criterion |
|---|---|
| `UNGROUNDED_FEATURE`, `FABRICATED_SOURCE_REFERENCE`, `MISSING_COVERAGE` | **`grounding_fidelity`** (new) |
| `SCOPE_CREEP` | `scope_discipline` |
| `DEPENDENCY_MISSING` | `decomposition_coherence` |
| `VAGUE_DESCRIPTION` (desc <2 sentences / not behavioural) | `acceptance_criteria_testability` + `decomposition_coherence` |
| `AI_PRIORITY_INFLATION` (priority escalated w/o cited evidence) | `prioritisation_rationale` |
| (false confidence → invented requirement) | `assumption_explicitness` |

**Two non-negotiable PO disciplines** the prompts state as do-not-reopen decisions:
1. **Propose, never elicit.** No elicitation questions — propose concrete features; the human
   curates. (The RequireKit failure proved questions stall the pipeline.)
2. **No numerical priority.** `priority_rationale` is **advisory prose only** — never numerical
   scores or forced rankings; enum fields default conservatively and escalate only on cited
   evidence.

## Phased `extract` flow

`roadmap` (`EpicPlan`, stubs + `cited_docs` + `epic_plan.json`) → `features` (`EnrichmentBatch`
per epic, merged server-side) → `nfrs` (Phase C). `--phase=full` runs the single-pass
`ProductRoadmap`. Used for corpora >~5 docs to avoid context overload. Training `extract`
examples should cover **both** the roadmap phase (stubs, coverage, citations) and the features
phase (enrichment, enum discipline, field_citations) — they are different output shapes.

## Fleet-memory note

The PO role sets `knowledge_graph.enabled: true` — it **queries Graphiti at startup**
(`query_at_startup`, `max_query_results: 15`) and **writes back** `product_decision` /
`feature_roadmap` / `priority_rationale`. So `product-owner` is squarely one of the four Graphiti
consumers still on the fleet-memory migration list. Training the fine-tune **RAG-out day-one** is
consistent with **ADR-FLEET-002**: behaviour lives in the weights, knowledge via retrieval — two
independently-updatable layers.

## GOAL.md changes made from these findings (2026-07-01)

1. **Serving-contract guideline** rewritten: output is the mode's structured JSON
   (`ProductRoadmap`/`EpicPlan`/`EnrichmentBatch`), not prose; assumptions shape pinned; priority
   discipline (no numerical ranking, enum Literals, escalation-cited) stated; two-artefact +
   phased-extract distinction folded in; points here for exact fields.
2. **`grounding_fidelity` criterion added** (behaviour, 15%) — the missing grounding/citation/
   coverage axis where the harder modes discriminate.
3. **`prioritisation_rationale` sharpened** — advisory prose only; anti-`AI_PRIORITY_INFLATION`.
4. **Output Schema** assistant-content updated to produce the mode's JSON after the `<think>`
   block; OQ#4 comment marked resolved, pointing here.

## Remaining alignment (Step 4, non-blocking)

Align the **generation output instruction** to the exact schemas above (pinned verbatim from the
three prompt files) so training, the golden-set harness, and serving all share one shape. The
golden-set run already shows the base hits the shape under its output instruction, so this is a
generation-time verbatim pin, not new design.
