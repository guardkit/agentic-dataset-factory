# PO Phase 2 — Harvest Lift: Reconstruction Contract, `harvest` Enum, Weighting, Phased-Extract Shapes

**Date:** 2026-07-07 (WS4-S1, spec only — WS4-S2 builds this). **Reviewed in-session, two adversarial passes:** builder pass (22 findings) + independent fact-verification pass, all resolved; then a re-review of the revision (1 HIGH / 3 MED / 6 LOW residuals — the HIGH: `Graphiti-Student-Model` failing the 2-sentence validator on both description sources), all resolved into this text. Factual corrections folded in: §1 brief-length facts, keepalive timer state, wire-the-production's unparsed `--context=` flags.
**Canon this deltas (does NOT respec):** `PLAN-po-dataset-generation.md` §6–§7 (Phase 2), `ai-transition/docs/po-fine-tune-{scope,build-plan}.md`, `GOAL.md`, `OUTPUT-CONTRACT.md` (all this dir unless pathed).
**Binding parent:** `ai-transition/docs/ws4-learning-flywheel-scope-and-build-plan-2026-07-07.md` §3.1 + §9 row WS4-S1.
**Companion (filed same session):** `MEMO-prelaunch-decisions-D-WS4-1-2.md` (this dir) — Rich's two pre-launch decisions.
**Corpus:** `~/po-dataset/po_history_records.jsonl` (91 records; 31 `feature_spec`) + `~/po-dataset/MANIFEST.md` — host-local, private (DF-008; durable home is D-WS4-5 / WS4-S0, not this spec).
**Schema pin:** all serving shapes pinned at specialist-agent commit `69c8620` (2026-07-07): `src/specialist_agent/roles/product_owner/types.py` (`ProductRoadmap`, `Epic`, `FeatureSpecInput`, `SourceCitation`), `phased_extraction.py` (`EpicPlan`, `EpicStub`, `FeatureStub`), `phase_b_delta.py` (`EnrichmentBatch`, `FeatureEnrichment`), `src/specialist_agent/roles/architect/types.py` (`Assumption`, `SourceDocument`), and — at the specialist-agent **repo root**, not under `src/` — `roles/product-owner/prompts/player_extract_features.md` (Phase-B input framing).

**Two caveats, carried verbatim, that bound what these rows may teach:**

> **DDD-drift caveat** (`~/po-dataset/README.md`): "This corpus contains drift as well as signal. The histories from the final days before DDD SouthWest (≈14–16 May 2026) show the methodology slipping — rushed curation, fast 'accept all' with less scrutiny, occasional skipped phases. The Feb–Apr histories are the disciplined ones. … recency is not the quality axis; curation quality is."

> **Fleet-memory-cutover caveat** (WS4-S1 task, binding): "traces predate the fleet-memory cutover — shape only." Every harvest session predates the specialist-agent fleet-memory cutover (`f411baf`, 2026-07-04) and, in most cases, months of stack evolution. Reconstructed rows teach the **shape** of PO behaviour (decomposition, testable ACs, assumption-surfacing with confidence + basis) — never current-stack facts. Briefs mentioning Ollama endpoints, ChromaDB layouts, Graphiti, etc. are historical inputs the PO reasons *over*; nothing in this contract may "modernise" them, and nothing downstream may treat them as current-architecture knowledge.

---

## 1. Corpus facts (re-derived from the JSONL on this host, 2026-07-07; independently re-verified by the review pass)

- 31 `feature_spec` records: **19 `rubber_stamp`** (all 19 carry the full `features/<slug>/` triple), **12 `partial`** (3 of the 12 carry a triple: `FEAT-FORGE-003`, forge `minimal-runbook-executor-…`, specialist-agent `architect-ingestion-v2-llama-swap-…`). 22 records total carry the full triple — the MANIFEST's "22 cleanly-paired". `record.feature_slug` equals the triple's directory slug on all 31.
- `paired_artefacts` paths are **Mac-side** (`/Users/richardwoollcott/…`). Remap rule (§2.2). All 22 triples (66 files) resolve on this host after remap (verified, 0 missing).
- **Duplicate-slug pair:** `FEAT-RAG-08` (rubber_stamp) and `architect-ingestion-v2-llama-swap-…` (partial) both pair to `specialist-agent/features/architect-ingestion-v2/` — two history files, one session's outputs.
- **Golden-set overlap (train/eval leak):** Phase 0 seeded `golden_set/golden_extract.jsonl` from 6 of these triples. The overlapping records, by slug (verified by joining `reference.summary_path` slugs against `paired_artefacts.feature_path` slugs): `FEAT-FORGE-008` → `mode-b-feature-and-mode-c-review-fix`; `FEAT-JARVIS-005` → `feat-jarvis-005-build-queue-dispatch-to-forge`; `NATS-Fleet-Registration&Specialist-Dispatch` → `feat-jarvis-004-fleet-registration-and-specialist-dispatch`; `FEAT-RAG-08` (+ its partial duplicate) → `architect-ingestion-v2`; `Graphiti-Student-Model` → `graphiti-student-model`; `primary-text-rag` → `primary-text-rag-and-quote-verifier`. **7 records / 6 slugs.**
- **`command_invocation` anatomy** (drives §2.3): invocations are multi-line shell text — a first *logical* command line (backslash-continued) carrying `/feature-spec`, an optional quoted brief and/or a bare feature-id token, plus `--context <path>` / `--context=<path>` flags; **three records (`FEAT-FORGE-002`, `FEAT-FORGE-006`, `JARVIS-003`) additionally captured a second physical line of assistant echo text** ("I'll execute the /feature-spec command… Starting Phase 1…"), which is transcript bleed, not brief. After §2.3's extraction rule, Tier-T prose-brief lengths are: JARVIS-003 262, `fine-tune-comparision` 1,180, `deepagents-tutoring-loop` 124, `deterministic-session-planner` 90, `graphiti-runtime-integration-repair` 283 chars (the five clean briefs); the six `FEAT-FORGE-00x` records and `autobuild-runner` reduce to empty (id + context flags only — those sessions' real briefs *were* the context files, whose contents are anachronistic and not reconstructable), and `wire-the-production-pipeline-orchestrator` reduces to its 58-char quoted title — all eight take the fallback path (§2.3-2).
- `why_rationales` are **line-clipped** in many records (truncated mid-sentence at capture width). `scenario_count` / `scenario_count_counted` / `scenario_count_declared_sum` disagree on several records (e.g. FEAT-RAG-08: 23/17/17 — resolved: 22 `Scenario:` + 1 `Scenario Outline:`; see §2.5). The plan's "unpaired rubber_stamp" weighting bucket (§6) is **empty in reality** — every rubber_stamp is paired.
- `assumptions[].human_response` is **mostly but not uniformly** `"confirmed"`: `deterministic-session-planner` carries `signed-off-with-implementation-evidence` / `signed-off-with-measured-data` (+ an extra `signed_off_at` key), `NATS-Fleet-…` (Tier Q) carries a "promoted to DDR-023 … binding decision" resolution, `FEAT-FORGE-006` carries `confirmed (default accepted — REVIEW REQUIRED)`. None of these is a Modify/Reject/Defer curation event — the MANIFEST's `considered = 0` stands; they are post-session *resolution* annotations. Disposition: provenance-only, never rendered, and they do **not** qualify for the reserved `considered` weight bucket (§4).

## 2. The reconstruction contract (RAW record → training rows)

Deterministic principle (coach-v3 lesson, plan §6): **code renders the JSON; the LLM writes only the reasoning.** Every assistant JSON field is assembled by the lift script from the real artifacts, except the explicitly named LLM-filled fields (§2.6). A row's *answer* is real; only its *think block* (and the small glue-field allowlist) is synthesised.

**Text-normalisation rule (applies everywhere this contract lifts text from files or records):** join the physical lines of a block with single spaces, collapse whitespace runs, strip. A *paragraph* is a maximal run of consecutive non-empty lines bounded by blank lines.

**Message envelope:** every row is `[system, user, assistant]` (`turns: 1`). **`system` = GOAL.md §System Prompt verbatim** (`goal.system_prompt` — the same content every factory row and the golden harness use).

### 2.1 Record routing (precedence order — first match wins)

1. `curation_richness == "partial"` → **Tier R (reference-only)**. Not reconstructed. Per canon plan §6: "partial (12) = reference only, exclude from training." This excludes all 12 partials, including the 3 paired ones and the `architect-ingestion-v2` duplicate (its triple survives via `FEAT-RAG-08` in Tier Q). Dispositions logged in the lift MANIFEST.
2. Triple slug ∈ the golden slug set (derived per §2.7-5) → **Tier Q (quarantine)**. Fully reconstructed (machinery proof + future eval-side fixtures) and written to `quarantine_golden_overlap.jsonl`; **never merged into any training set**. This is the holdout-overlap staging gate of plan §2⑦ applied at the source. 6 records.
3. Else → **Tier T (train-eligible)**. 13 records — `reconstruction_grade` per §2.3: **clean_brief (5):** `JARVIS-003`, `fine-tune-comparision`, `deepagents-tutoring-loop`, `deterministic-session-planner`, `graphiti-runtime-integration-repair`; **fallback_brief (8):** `FEAT-FORGE-002/004/005/006/007/009`, `wire-the-production-pipeline-orchestrator`, `autobuild-runner`.

Consequence for the WS4-S2 acceptance bar ("22 paired rows reconstructed and factory-accepted"): the achievable, leak-free number is **19 records reconstructed (13 Tier T + 6 Tier Q), 3 paired-partials excluded per canon**. The dated correction is filed in the WS4 doc §9 (this session).

General dedup rule (beyond the one known pair): if two Tier-T/Q-eligible records ever share a triple slug, reconstruct only the record with more `phases_present`; log the loser as `duplicate_of` in the MANIFEST.

### 2.2 Path remap + integrity

- Remap `paired_artefacts.*` prefix `/Users/richardwoollcott/Projects/appmilla_github/` → `<--repos-root>/` (default `/home/richardwoollcott/Projects/appmilla_github/` — the remap target IS the `--repos-root` arg); fail the record with render-failure disposition `triple_missing` if any of the three files is absent after remap.
- Record `sha256` of each triple file in row provenance (§2.8). The lift never writes to source repos (READ-ONLY, mirroring the harvester's AC-4).

### 2.3 User message construction

The serving PO receives a brief/corpus, not a slash command. Per record:

1. **Brief extraction (Rule R, deterministic):**
   a. Join backslash-continued physical lines of `command_invocation` into logical lines; **keep only the first logical line** (this drops the assistant-echo bleed on FORGE-002/006 and JARVIS-003 deterministically).
   b. Remove every `--context` flag and its argument — both `--context <arg>` and `--context=<arg>` forms; the argument is one quoted or bare token. **If flags were removed here but `record.context_args` is empty** (true for exactly one record, `wire-the-production-…`, whose 16 `--context=`-form flags the harvester never parsed into `context_args`), the Rule-R flag arguments become the record's context-file list for §2.3-3 and `suggested_context_files`, with `context_args_source: "rule_r"` in provenance; otherwise `record.context_args` is authoritative.
   c. Strip the leading whitespace-delimited token that **starts with** `/feature-spec` — the whole token, whatever its tail (handles `/feature-spec`, `/feature-spec.`, and Tier-Q FEAT-FORGE-008's `/feature-spec-FEAT-FORGE-004-history.md`, whose garbage tail must not leak into a brief).
   d. If the remainder starts with `"`: the brief is the content between that quote and the **last** `"` in the remainder. Else: strip one leading bare token matching `[A-Za-z0-9][A-Za-z0-9_.&-]*` (the feature-id argument); if what remains then starts with `"`, apply the quote rule; otherwise the remainder is the brief.
   e. Normalise (rule above). **≥ 80 chars → `clean_brief`; else `fallback_brief`.**
2. **Fallback brief** (the 8 records above, or any future record under 80 chars): concatenate, in order, separated by blank lines, skipping empty/duplicate components: (i) the Rule-R remainder if non-empty and not case-insensitively equal to the feature title (e.g. wire-the-production's real 58-char quoted title); (ii) the `.feature` **title** — the text after `Feature:` on the first line matching `^Feature:` at column 0 (never the `# Feature: …` header *comment*); (iii) the `.feature` **narrative block** — all non-empty lines between the `Feature:` line and the first line whose stripped text starts with `#`, `@`, `Background`, `Scenario`, or `Rule`, normalised as one paragraph. Verified: all 8 fallback records have narrative blocks of 241–476 chars (the Gherkin As/I-want prose — no fixed `As a…/So that…` structure is assumed; `autobuild-runner`'s five-line hard-wrapped story with a folded purpose clause normalises cleanly under this rule).
3. **Render as a corpus document** so extract-mode grounding is real and checkable:

   ```
   Mode: extract
   Decompose the following feature brief. Surface unstated parameters and policies as assumptions; do not ask questions.

   ## File: <feature_slug>-brief.md
   # Brief
   <brief text>
   <if context_args non-empty, a trailing paragraph inside the same document:
   "Context files referenced by this brief (names only, content not supplied): <comma-joined context_args>.">
   ```

   The **only** citable document is `<feature_slug>-brief.md`. Context-file names live *inside* the brief document precisely so citing them as separate documents is a detectable grounding violation. `coverage_score` is therefore `1.0` and never null (corpus mode). (`context_args` come from the record, not from Rule R — the flags removed in step 1b and the `context_args` field are the same list; the record field is authoritative.)
4. **Human skim (named gate, belt-and-braces):** the lift MANIFEST prints every rendered brief; the S2 session reviews all 19 rendered briefs (Tier T and Q) once and may hand-delete residual non-brief text (e.g. any echo form Rule R didn't anticipate), recording `brief_trimmed: true` in that row's provenance. At n=19 this is minutes, and it is the *only* human step in the pipeline.
5. **Row B user message** prepends the serving Phase-B scope block (mirrors `player_extract_features.md`):

   ```
   Mode: extract (Phase B — features)

   ## Phase B Scope
   Target epic: EPIC-001 — "<feature title>" (bounded_context: "<glue.bounded_context, §2.6>")
   Cited docs: <feature_slug>-brief.md
   Stub allowlist:
   - <feature_id> — "<feature title>" — intent: "<intent>"

   ## File: <feature_slug>-brief.md
   <same brief document as above>
   ```

   **`intent`** = the first sentence of the `.feature` narrative block (normalised); if it exceeds 100 chars, truncate at the last word boundary before 100 and append `…`. (Prompt text only; the 100-char cap keeps the stub at the one-line altitude the Phase-A contract describes.)

### 2.4 Assistant — Row A ("full"-phase `ProductRoadmap`)

`<think>…</think>\n\n` + one ```json-fenced `ProductRoadmap` object.

**Serialization pin (applies to Row A and Row B):** `json.dumps(obj, ensure_ascii=False, indent=2)`; key order = the order of the field tables below (dicts constructed in that order). "Omit" for an optional/None-default field = **key absent**; schema-required list fields with no content = **`[]` present**. These bytes are load-bearing three ways: the row id (§2.6), the training content, and the token budget (§2.7-4).

| Field | Source (deterministic unless marked LLM) |
|---|---|
| `project_name` | `record.repo` |
| `mode` | `"extract"` |
| `epics` | exactly one `Epic` |
| `epics[0].id` | `"EPIC-001"` |
| `epics[0].name` | the `.feature` title (§2.3-2 rule ii — line-anchored `^Feature:`, never the header comment) |
| `epics[0].bounded_context` | `glue.bounded_context` (§2.6) |
| `epics[0].description` | first paragraph after the `## Scope` heading of `_summary.md`, normalised. If `_summary.md` has no `## Scope` heading, use the `.feature` narrative block (§2.3-2-iii) |
| `epics[0].features` | exactly one `FeatureSpecInput` (below) |
| `epics[0].source_documents` | `["<feature_slug>-brief.md"]` (`Epic.source_documents: list[str]` at the pin) |
| `epics[0].field_citations` | key absent |
| `features[0].feature_id` | `record.feature_id` verbatim (the `&` in `NATS-Fleet-…` is legal JSON string content; row identity is the content-addressed row id, §2.6, so no filesystem sanitisation issue) |
| `features[0].title` | same as epic name |
| `features[0].description` | same source as epic description; if the pinned 2-sentence validator rejects it, fall back to the `.feature` narrative block; if that also fails, **concatenate the two (Scope ¶1 + space + narrative block)** — this rescues single-sentence-each cases deterministically (verified: `Graphiti-Student-Model`, Tier Q, fails both individually and passes concatenated); if still rejected → render-failure disposition `description_unrecoverable` (§2.7, "Render-time failures") |
| `features[0].bounded_context` | `glue.bounded_context` |
| `features[0].source_documents` | `["<feature_slug>-brief.md"]` |
| `features[0].constraints` | `[]` |
| `features[0].suggested_context_files` | `record.context_args` verbatim (real session inputs; may be `[]`) |
| `features[0].depends_on` | `[]` |
| optional enrichment fields (`type/role/priority/moscow/value/complexity`) | keys absent — conservative defaults; escalation without cited evidence is `AI_PRIORITY_INFLATION` |
| `features[0].acceptance_criteria` / `technical_notes` / `risks` / `open_questions` / `links` / `field_citations` | keys absent (default-factory fields) — ACs live in Row B under the phased contract; Row A stays on the single-pass instruction shape |
| `feature_spec_inputs` | `[ features[0] ]` (identical object — the flatten validator requires the same `feature_id` set) |
| `priority_rationale` | `glue.priority_rationale` (§2.6), advisory prose, never numeric |
| `constraints_and_dependencies` | `[]` |
| `open_questions` | `[]` (low-confidence unknowns are already carried as assumptions; duplicating them is noise) |
| `change_summary` / `estimate_unit` | keys absent |
| `coverage_score` | `1.0` |
| `source_documents` (roadmap level) | `[{"filename": "<feature_slug>-brief.md", "contribution": "The feature brief this decomposition was produced from."}]` (objects at roadmap level only — §5.7) |
| `assumptions` | one `Assumption` per entry of the yaml's **`assumptions:` list**, in file order: `id` ← `id`; `statement` ← `assumption` verbatim; `confidence` ← `confidence`; `source` ← `basis` verbatim; `category` ← `glue.categories[id]`; `impact_if_wrong` ← `glue.impacts[id]` (both §2.6; `impact_if_wrong` is a required field at the pin). The yaml's per-entry `scenario`, `human_response`, extra keys (`signed_off_at`), and any **other top-level yaml lists** (`graphiti-runtime-integration-repair` carries `dropped_assumptions` and `implementer_hints`) are provenance-only — never rendered (§1) |

### 2.5 Assistant — Row B (Phase-B `EnrichmentBatch`)

`<think>…</think>\n\n` + one ```json-fenced `EnrichmentBatch` (same serialization pin):

| Field | Source |
|---|---|
| `project_name` | `record.repo` |
| `epic_id` | `"EPIC-001"` |
| `enrichments` | exactly one `FeatureEnrichment` |
| `.feature_id` | `record.feature_id` (matches the stub allowlist in the user message) |
| `.description` | same value + fallback chain as Row A `features[0].description` |
| `.source_documents` | `["<feature_slug>-brief.md"]` |
| `.constraints` / `.technical_notes` / `.risks` / `.open_questions` / `.links` / `.depends_on` | `[]` |
| `.suggested_context_files` | `record.context_args` verbatim |
| `.type` | `"Dev: Feature"`, serialized explicitly · `role/priority/moscow/value/complexity`: keys absent (None) |
| `.acceptance_criteria` | **one string per `Scenario:` OR `Scenario Outline:` block in the `.feature` file, in file order** (line-anchored match on stripped lines `^Scenario( Outline)?:`, comment lines excluded): the scenario/outline name verbatim. Names in this corpus are behavioural, observable statements ("Re-ingesting the existing knowledge.jsonl through llama-swap preserves vector parity") — exactly the AC-sentence altitude the serving PO emits for `/feature-spec` to turn into Gherkin. Full Given/When/Then bodies are NOT included (they are the *downstream* command's output and blow the sequence budget). Ground truth is the `.feature` file — the record's three scenario-count fields are advisory; the outline-inclusive count reconciles them (e.g. FEAT-RAG-08 = 22 + 1 = 23); mismatches are logged, never reconciled by dropping scenarios |
| `.field_citations` | `{"description": [C], "acceptance_criteria": [C]}` where `C = {"document": "<feature_slug>-brief.md", "section_path": ["Brief"]}` (the brief document's single real heading — §2.3; no `quote`) |

Proposal-group structure (`A Key Examples / B Boundary / C Negative / D Edge …`) and `why_rationales` are **not rendered into either JSON** — the whys are line-clipped (§1) and the grouping is `/feature-spec` presentation, not PO serving shape. Both feed the think block (§2.6) and provenance.

### 2.6 Synthesis (the only LLM steps) — one glue call per record, one think call per row

- **Model:** `gpt-oss-120b` (Decision B teacher), temperature 0. Served via the existing `autobuild_go` set with the standing keepalive discipline: **check the timer state, pause it before the run** (`sudo systemctl stop llama-swap-keepalive.timer` — Rich's sudo), **restore the prior state after** (it has been observed both active and inactive on different days; never assume — 2026-07-07 review observed it inactive/enabled).
- **Call 1 — record-level glue** (once per record, before any row render). Input: the rendered brief document, `_summary.md` in full, the `_assumptions.yaml` entries, `proposal_groups`, `why_rationales` (with a note that they may be line-clipped). Output, JSON: `bounded_context` (short domain-language noun phrase grounded in the brief), `priority_rationale` (advisory prose grounded in the whys/summary), and per-assumption `category` + `impact_if_wrong` (one sentence, grounded in the yaml's `scenario`/`basis`). `category` MUST come from the pinned allowlist `{technology, integration, data, process, security, scale, ux, domain, operations}` — the lift validates membership; one re-ask on violation, then `rejected_rows.jsonl`. **Glue fields are frozen after this call** — no later step may change them; both rows read the same glue, so Row A and Row B have no ordering dependency and no failure coupling.
- **Call 2/3 — per-row think block.** Input: that row's full user message + its deterministic JSON + the glue + groups/whys/summary. Output: the `<think>` text only (Row A: outcome pursued → unknowns→assumptions → in/out scope → sequencing, per GOAL's mandatory think semantics; Row B: coverage strategy across the scenario groups — why key examples / boundaries / negatives / edges each earn ACs). Target ≤ 400 tokens; must *reason*, not summarise; must never mention harvesting, reconstruction, transcripts, or that the answer pre-exists.
- **Re-synthesis budget per row:** the initial think + at most **2** re-syntheses total, regardless of trigger (Coach non-accept, §2.7-3; over-length shrink to ≤ 200 tokens, §2.7-4). A row that would need a third goes to the file its last failing gate names.
- **Row id** = sha256 of the UTF-8 bytes of `"{record.source_path}\n{row_type}\n{assistant_json_bytes}"`, where `row_type` ∈ `{"A","B"}` and `assistant_json_bytes` is the exact serialized inner-JSON body (§2.4 pin — think text deliberately excluded, so re-synthesis does not change identity). The id is **stored** as `metadata.harvest.row_id` on every written row and on every failure stub (below); `--resume` reads stored ids from all four output files and skips them (previously rejected/over-length/failed entries are not auto-retried; delete the line to retry).
- **Failure-entry shapes.** Gate failures on a rendered row write the full row + a `"verdict"`/token-count sidecar key. **Render-time failures** (`triple_missing`, `description_unrecoverable`, glue-call category exhaustion) write a **stub** instead: `{"row_id": <id or null when no JSON exists yet>, "record_feature_id", "row_type" ("A"|"B"|"record" for record-level glue failure), "disposition", "reason"}`. Destination: Tier T stubs → `rejected_rows.jsonl`; Tier Q stubs → the MANIFEST only (the quarantine file holds only rendered rows; tiers never mix). A record-level stub blocks both rows on resume until deleted.

### 2.7 Gates (a row must pass all five to be written; **any mutation — think re-synthesis or shrink — restarts the chain from gate 1**)

1. **Schema gate:** the fenced JSON must validate against the **vendored** models — new file `domains/product-owner/po_schemas.py` containing exactly these classes, fields + validators byte-identical modulo import paths, flattened into one module (I/O helpers and non-model functions excluded), with a header comment mapping each class to `module@69c8620`: `SourceCitation`, `FeatureSpecInput`, `Epic`, `ProductRoadmap`, `Assumption`, `SourceDocument`, `FeatureStub`, `EpicStub`, `EpicPlan`, `FeatureEnrichment`, `EnrichmentBatch`. No runtime import from specialist-agent.
2. **Format gate:** assistant = one `<think>…</think>` block + exactly one ```json fence, strict `json.loads`; envelope validates as `TrainingExample` (`src/tools/models.py`); metadata keys with `valid_values` in the parsed GOAL Metadata Schema are checked exactly as `write_output` step 9 does. The lift does **not** call the `write_output` tool (it hardcodes layer→`output/train.jsonl`); it replicates the validation chain (reuse `domain_config/parser` for the schema table) and appends to its own files (§2.9).
3. **Coach gate:** Coach = `gemma4-coach` (distinct from the reconstructor — no self-scoring; D9 discipline), invoked via the golden-harness seams — `create_model` + `build_coach_prompt` + `_parse_coach_verdict`, as `score_golden_set.py` actually does. Accept ⇔ **`CoachVerdict.is_accepted`** (decision == accept ∧ score ≥ 3 ∧ layer_correct ∧ type_correct ∧ no blocking issues — the factory rule). On a non-accept verdict: re-synthesise **only** the think block (budget §2.6) and restart from gate 1; budget exhausted → `rejected_rows.jsonl` with the verdict attached, for Rich's review. Real fields and glue are never edited to satisfy the Coach. **Precondition (S2 lands it with §5.3): the GOAL Evaluation-Criteria phase-routing note must be in place first** — without it the Coach's unverifiable-criterion rule (blocking issue on absent information) can structurally reject Row A for having no AC field, the exact Phase-0 artifact (`RESULTS-po-phase0.md:131`). See §5.3 for the routing text; the Coach prompt is built from the Evaluation Criteria section, so the note reaches it.
4. **Sequence-length gate:** token length of the full rendered chat (system + user + assistant) via `tokenizer.apply_chat_template(messages, tokenize=True, add_generation_prompt=False)` (training shape) must fit `--max-seq-tokens` (default **4096** — the coach-FT precedent; Phase 4 confirms the final value and the gate re-runs if it shrinks). Tokenizer: `--tokenizer <path>` is a **required** argument — point it at the same gemma-4 tokenizer artifact Phase-4 training will use (no chars-per-token heuristics). Over budget → re-synthesise the think at ≤ 200 tokens (budget §2.6) and restart from gate 1; budget exhausted → `over_length.jsonl` with token counts. Real fields are never truncated.
5. **Holdout-overlap gate:** at write time, re-derive the golden slug set from `golden_set/*.jsonl` — slug = basename of the directory of `reference.summary_path` for every JSON line whose `reference` is an object containing `summary_path`; lines with null/other-shaped references contribute nothing; abort the run if the derived set is empty. Assert no training-file row's triple slug is in the set (belt-and-braces over §2.1 routing; a future golden-set addition automatically widens the exclusion).

**Tier-Q rows** run the identical chain but every *rendered* Q row is written **only** to `quarantine_golden_overlap.jsonl` whatever the outcome, with `gate_outcome: accepted | rejected | over_length` (+ the verdict/counts) in provenance; Q render-time failures go to the MANIFEST only (§2.6 failure-entry shapes) — tiers never mix across files.

### 2.8 Metadata + provenance (mandatory on every row, all tiers)

```json
"metadata": {
  "layer": "behaviour", "type": "reasoning", "dimension": "assumption_surfacing" (Row A) | "acceptance_criteria" (Row B),
  "mode": "extract", "phase": "full" (Row A) | "b" (Row B),
  "source_books": [], "topic": "assumption_confidence" (Row A) | "acceptance_criteria" (Row B),
  "source": "harvest", "turns": 1, "weight": <§4; 0.0 on Tier Q>,
  "harvest": {
    "record_feature_id": "...", "repo": "...", "session_date": "YYYY-MM-DD", "date_basis": "...",
    "history_source_path": "...", "curation_richness": "rubber_stamp",
    "reconstruction_grade": "clean_brief|fallback_brief", "brief_trimmed": false, "tier": "T|Q",
    "triple": {"feature_sha256": "...", "assumptions_sha256": "...", "summary_sha256": "..."},
    "think_model": "gpt-oss-120b", "llm_filled_fields": ["..."], "gate_outcome": "... (Tier Q only)",
    "era": "pre-fleet-memory-cutover", "lift_version": "<factory-repo git short sha at run time>"
  }
}
```

`write_output`-equivalent validation (§2.7-2) checks only metadata keys that carry `valid_values` in the GOAL Metadata Schema and ignores unknown keys (verified `src/tools/write_output.py:182–202`), so `phase`, `weight`, `harvest` ride through untouched; `source: "harvest"` requires the §3 enum change first. Empty `source_books` passes (list-membership check over an empty list).

### 2.9 Script + output layout

- **Script:** `domains/product-owner/lift_harvest.py` (domain-local, the `score_golden_set.py` precedent). Args: `--records` (default `~/po-dataset/po_history_records.jsonl`), `--repos-root` (default `/home/richardwoollcott/Projects/appmilla_github`), `--out` (default `output/harvest/`, resolved against the factory repo root), `--think-model gpt-oss-120b`, `--coach-model gemma4-coach`, `--tokenizer <path>` (required, §2.7-4), `--max-seq-tokens 4096`, `--limit N` (caps *records* processed, for smoke), `--resume` (§2.6 row-id semantics).
- **Outputs** (all under `output/harvest/`, private per DF-008, never published): `train_harvest.jsonl` (Tier T accepted — **not** appended to `output/train.jsonl`, so the 82h run's checkpoint/lock and backups are untouched; Phase-4 assembly merges by manifest), `quarantine_golden_overlap.jsonl` (all Tier Q), `rejected_rows.jsonl`, `over_length.jsonl`, `MANIFEST-harvest-lift.md` (per-record disposition table covering all 31 records — tier, grade, rendered brief text, gate outcomes, no silent drops).
- **Expected yield:** 13 Tier-T records × 2 rows = **26 candidate rows** (≤ 26 accepted), 6 Tier-Q × 2 = 12 quarantined rows. Run cost: ≤ ~60 reconstructor calls + ≤ ~80 Coach calls — trivial next to the 82h run.

### 2.10 Edge cases, named (each with its disposition)

| Edge case | Records | Disposition |
|---|---|---|
| Truncated sessions / the 12 `partial` records | all 12 (incl. paired `FEAT-FORGE-003`, `minimal-runbook-…`, `architect-ingestion-v2-…`) | Tier R, reference-only (§2.1 rule 1, canon) |
| Golden-set overlap | 7 records / 6 slugs (§1) | Tier Q quarantine (§2.1 rule 2) + write-time gate (§2.7-5) |
| Duplicate slug | `FEAT-RAG-08` vs `architect-ingestion-v2-…` | resolved by tiering; general richer-phases rule (§2.1) |
| Assistant-echo bleed in `command_invocation` | `FEAT-FORGE-002/006`, `JARVIS-003` | dropped by Rule R step 1a (first logical line only); human skim as backstop (§2.3-4) |
| Id+context-only invocations (no prose brief) | `FEAT-FORGE-002/004/005/006/007/009`, `autobuild-runner` | fallback brief from `.feature` title + narrative (§2.3-2) |
| Short-but-real quoted brief | `wire-the-production-…` (58 chars) | fallback composition keeps the real title text, deduplicated against the feature title (§2.3-2-i) |
| `--context=` vs `--context ` flag forms | wire-the-production vs the rest | both handled by Rule R step 1b |
| Empty invocation + `mode: unclear` | `FEAT-FORGE-003` | Tier R (partial) — never reaches the brief rule |
| Mac→host path mismatch | all 22 triples | remap + existence check (§2.2), `triple_missing` on failure |
| Line-clipped `why_rationales` | most records | think-conditioning only, never rendered (§2.5/§2.6) |
| `Scenario Outline:` blocks | 18 of 19 Tier-T/Q `.feature` files | included as AC entries alongside `Scenario:` (§2.5); reconciles the count fields |
| `# Feature:` header comment vs real `Feature:` line | every `.feature` file | line-anchored column-0 match (§2.3-2-ii) |
| `## Scope` heading absent from `_summary.md` | none observed; rule for future | description falls to the narrative block (§2.4) |
| `description` < 2 sentences from each source alone | `Graphiti-Student-Model` (Tier Q): 1-sentence Scope AND 1-sentence narrative | rescued by the concatenation step of the §2.4 chain (verified); truly unrecoverable → render-failure stub (§2.6) |
| `&` and spaces in `feature_id` | `NATS-Fleet-Registration&Specialist-Dispatch` | legal in JSON strings; identity via row ids (§2.6) |
| Harvester missed `--context=`-form flags | `wire-the-production-…` (`context_args: []`, 16 flags in invocation) | Rule-R flags become the context list, `context_args_source: "rule_r"` (§2.3-1b) |
| Garbage `/feature-spec-…` token | `FEAT-FORGE-008` (Tier Q) | whole-token strip (§2.3-1c); Tier-Q briefs included in the human skim |
| Extra top-level yaml lists | `graphiti-runtime-integration-repair` (`dropped_assumptions`, `implementer_hints`) | provenance-only; only the `assumptions:` list renders (§2.4) |
| Missing `category`/`impact_if_wrong` in yaml | all records | glue-filled from the pinned category allowlist, flagged in `llm_filled_fields` (§2.6) |
| Non-uniform `human_response` values | `deterministic-session-planner`, `NATS-Fleet-…`, `FEAT-FORGE-006` (§1) | provenance-only; not rendered; not `considered`-grade (§4) |
| Over-length rows | longest Tier-T brief is 1,180 chars (`fine-tune-comparision`); Tier-Q briefs reach 2,734 (`FEAT-RAG-08`) — Q rows are likeliest to hit the gate | seq-gate → think-shrink → `over_length.jsonl` (§2.7-4) |

## 3. The `harvest` source enum

One-line data change + one prose note; **no code change** (verified: `ExampleMetadata.source` is a free `str`; the only enforcement is the `valid_values` lookup built from the GOAL Metadata Schema table — `write_output.py:69–74/182–202`, table parsed by `domain_config/parser.py`).

1. `GOAL.md` → Metadata Schema table, `source` row: valid values `synthetic` → **`synthetic, harvest, flywheel`**. `harvest` = rows reconstructed from real session history under this contract; `flywheel` = **reserved now, produced by nobody until WS4-S7's Chronicler** (definition-with-named-producer discipline — the WS4 doc's ReviewReportPayload lesson).
2. `GOAL.md` prose note under the table (dated): harvest rows carry `source_books: []`, mandatory `metadata.harvest` provenance (§2.8), and a `weight` key (§4); `flywheel` rows will be Coach-validated before joining any training set (WS4 §6.2).
3. Plan §8's open item ("Metadata `source` enum needs a `harvest` value") is closed by this section — WS4-S2 adds the dated pointer when it lands the edit.

## 4. Weighting (the plan's prose made mechanical)

Plan §6 prose → numbers. Carrier: `metadata.weight: float` on every harvest row (book rows carry no key ⇒ 1.0). Consumer: **Phase-4 assembly** (`domains/product-owner/prepare_po_sft.py`, to be built at Phase 4 on the `prepare_coach_sft.py` precedent): TRL's SFTTrainer has no per-sample loss weighting, so weights realise as duplication — `copies = max(1, round(weight))`, `--weight-mode {round,none,scale,ceil}` with `none` as the ablation arm. **Additionally the assembly MUST drop rows with `weight == 0.0`** (belt-and-braces: `max(1, round(0))` would otherwise train one copy of an accidentally merged quarantine row).

| Bucket | Rule (mechanical) | weight | copies (round) |
|---|---|---|---|
| Paired triple, clean brief | Tier T ∧ `reconstruction_grade == clean_brief` (5 records) | **2.0** | 2 |
| Paired triple, fallback brief | Tier T ∧ `fallback_brief` (8 records) | **1.5** | 2 |
| DDD-drift discount | multiply by **0.75** when `session_date ≥ 2026-05-06`. Among Tier T this catches exactly `autobuild-runner` and `fine-tune-comparision` (both 2026-05-06; the latest *rubber_stamp* session is 2026-05-10 — partial/command records run later but are excluded). The README pins the slip to "the final days before DDD SouthWest (≈14–16 May)", so this cutoff is deliberately conservative; `session_date` rides in provenance for Phase-4 ablation either way | ×0.75 | 2.0→1.5→2 · 1.5→1.125→1 |
| Tier Q (quarantine) | any | **0.0** | dropped by assembly |
| Unpaired rubber_stamp (plan §6's "lower" bucket) | **empty in this corpus** (§1) — rule retained for future harvests: 1.0 | 1.0 | 1 |
| `considered` (future, flywheel/WS1-instrumented; §1's resolution annotations do NOT qualify) | reserved: 3.0, revisit when the first real `considered` row exists | 3.0 | 3 |
| `partial` | excluded (Tier R) | — | — |
| Book-generated | no key | 1.0 | 1 |

Volume sanity (why these numbers are safe): 26 harvest rows × ≤2 copies ≈ ≤52 effective rows against ~850 book behaviour rows ≈ **≤6% of the behaviour corpus** — in-distribution reinforcement without letting rubber-stamped weak positives (the self-distillation risk, plan §8) dominate. Anyone re-tuning these constants must re-do this sanity ratio.

## 5. Phased-extract shapes in the factory (generation side)

Motivation is dual: (a) the serving contract has three shapes and training must cover all of them; (b) it cures the Phase-0 eval artifact — `acceptance_criteria_testability` was unmeasurable under single-pass `ProductRoadmap` (`RESULTS-po-phase0.md:131`); ACs live in Phase B.

1. **Mode-token grammar.** `GenerationConfig.modes` entries gain an optional phase suffix: `extract:a` | `extract:b` (plain `extract` ≡ `extract:full`). Config validation rejects a suffix on any non-extract mode (today `modes` is only checked non-empty — `config/models.py:212–221` — so the grammar check is new). At injection the loop splits on `:`: base mode → the `Mode:` line + `Set metadata.mode to "<mode>"` instruction (existing pattern, `generation_loop.py:1396–1402`); the phase is **stamped by the orchestrator** onto the parsed example's `metadata.phase` after generation (`a|b|full`; plain non-extract modes get no `phase` key) — never trusted to the Player.
2. **Layer-aware mode assignment.** Targets carry their layer from the GOAL Generation Targets table, so the loop keeps **two round-robin cursors**: behaviour-layer targets walk the configured `modes` list; knowledge-layer targets walk the same list with phased tokens filtered out (knowledge rows are prose-shaped reference content — Phase-B scope framing and stub allowlists are meaningless there). This also makes item 6's "2/7 of behaviour targets" true by construction.
3. **`_MODE_HINTS` additions** (`entrypoint/generation_loop.py:1345–1361`):
   - `extract:a` — "You are in extract mode, Phase A (roadmap). AUTHOR a realistic 1–3-document product corpus as `## File: <name>` blocks inside the user message, then emit an `EpicPlan` (stubs + `cited_docs` + `source_citations`; any enrichment field is an ENRICHMENT_LEAK). Every citation must reference your `## File:` documents."
   - `extract:b` — "You are in extract mode, Phase B (features). AUTHOR the user message as a `## Phase B Scope` block (target epic, cited docs, stub allowlist) plus the `## File:` documents, then emit an `EnrichmentBatch` enriching the allowlisted stubs — descriptions 2+ sentences, `acceptance_criteria`, enum-Literal `priority/moscow/value/complexity` with `field_citations` for every non-default value."
   - `extract` / `extract:full` — single-pass `ProductRoadmap` over an authored corpus.
   (The generative Player already authors both sides of each example — the synthetic corpus rides in the user message it writes, which is what makes `grounding_fidelity` *checkable* by the Coach: citations must match the in-message `## File:` blocks.)
4. **GOAL.md edits — placed by consumer, because the Coach prompt is built only from the Goal / Evaluation Criteria / Output Schema / Metadata Schema / Layer Routing sections:**
   - **Generation Guidelines** (Player-facing): inline "Phased extract serving schemas" block — the `EpicPlan` and `EnrichmentBatch` field lists + enum Literals + `ENRICHMENT_LEAK` rule, copied from `OUTPUT-CONTRACT.md` §B/§C at the `69c8620` pin (the same inline-into-GOAL mechanism that fixed the ProductRoadmap shape in Phase 1).
   - **Evaluation Criteria** (Coach-facing): a **"Shape-aware criteria routing"** note, the F4 fix and the harvest gate-3 precondition: *for behaviour rows, first identify the fenced object's shape.* `ProductRoadmap` / `EpicPlan` rows: `acceptance_criteria_testability` applies only if AC fields are populated — absence is NOT a failure (ACs are deliberately deferred to extract Phase B; do not raise an unverifiable-criterion blocking issue for their absence). `EpicPlan` rows: `prioritisation_rationale` limited to the `priority_rationale` field (stubs carry no enums); enrichment fields present on a stub are an ENRICHMENT_LEAK failure under `decomposition_coherence`. `EnrichmentBatch` rows: `assumption_explicitness` is evaluated through `open_questions` on enrichments (roadmap-level assumptions are Phase-A/dispatcher territory — absence of an `assumptions` field is not a failure); `decomposition_coherence` is evaluated as stub-fidelity (each enrichment faithfully expands its stub's intent), not epic nesting; `prioritisation_rationale` = enum conservatism + escalation evidenced via `field_citations.priority`. This mirrors the mode-aware `grounding_fidelity` fix precedent (Phase 0).
5. **Inner-schema validation, opt-in:** new `GenerationConfig.validate_inner_schema: bool = false`; when true (PO config sets it), the inner-JSON gate additionally validates the parsed object against `po_schemas.py`, **behaviour-layer rows only**, keyed by (`metadata.mode`, `metadata.phase`): the five no-corpus modes and `extract`/`full` → `ProductRoadmap`; `extract`/`a` → `EpicPlan`; `extract`/`b` → `EnrichmentBatch`; knowledge-layer rows skip this gate. Failures route to the existing targeted-revise path.
6. **Bulk-run mode list:** **`[idea, greenfield, extract:a, evolve, impact, scope, extract:b]`** — extract's phased shapes get 2/7 of behaviour targets (they carry the AC/enum/citation disciplines that have zero coverage otherwise); the five no-corpus modes keep 5/7 and all remain ProductRoadmap-shaped, so single-pass fluency keeps majority volume. `extract:full` is deliberately absent from generation: the harvest's Row A covers real full-pass extract. Run-composition and wall-clock implications are flagged for Rich in the companion memo; the mode list is `agent-config.yaml` data, changeable without code. **`metadata.mode` valid values need no change** (`extract` is already legal; the suffix never reaches metadata — §5.1).
7. **GOAL inline-schema correction (found this session, S2 lands it):** GOAL's inline ProductRoadmap schema shows `source_documents` as `{filename, contribution}` objects at **every** level; the pinned Pydantic types take **plain filename strings at epic and feature level** (`Epic.source_documents: list[str]`, `FeatureSpecInput.source_documents: list[str]`) and objects **only at roadmap level** (`list[SourceDocument]`) — `OUTPUT-CONTRACT.md` §A says exactly this ("objects at roadmap level"). Uncorrected, every corpus-mode generated row that populates epic/feature citations per the current GOAL text fails the §5.5 schema gate (Phase 1 never hit this because greenfield rows carry empty lists at every level — vacuously valid either way). Fix the GOAL inline schema with a dated note when the §5.4 blocks are added.
8. **Eval-side consumer (not this phase's build):** the golden-set harness's `--phase` / EnrichmentBatch path (`RESULTS-po-phase0.md` "Next refinements" item 2) becomes buildable once `po_schemas.py` exists; Phase-4 gating should re-measure `acceptance_criteria_testability` under Phase-B shape. Logged as a Phase-4 input, not WS4-S2 scope.

## 6. WS4-S2 build manifest (what "done" is)

| Item | Artifact | Acceptance |
|---|---|---|
| Vendored schemas | `domains/product-owner/po_schemas.py` (class list + pin header, §2.7-1) | round-trips a Phase-1 accepted row's ProductRoadmap + the §2.4/§2.5 renders |
| Lift script | `domains/product-owner/lift_harvest.py` | 19 records reconstructed (13 T: 5 clean_brief + 8 fallback_brief; 6 Q), 0 leaks past gate §2.7-5, MANIFEST covers all 31 records incl. rendered briefs |
| Human skim | brief review recorded in MANIFEST (§2.3-4) | all 13 Tier-T briefs skimmed; trims flagged `brief_trimmed` |
| Harvest rows | `output/harvest/train_harvest.jsonl` ≤ 26 rows, Coach-accepted | every row passes all five §2.7 gates; spot-check 3 rows vs triples by hand |
| Enum | GOAL.md `source` row + prose note | write-path validation accepts `source: harvest`, still rejects `source: bogus` (unit test) |
| Weighting | weights per §4 on rows + unit-tested weight function in the lift script | §4 table reproduced by tests (incl. Tier-Q 0.0 and the drop rule documented for Phase-4); assembly script itself is Phase-4 scope |
| Shape-aware Coach routing | GOAL Evaluation Criteria note (§5.4) — **lands before any Coach-gated run** | Row A accepted without an AC-absence blocking issue; an EpicPlan row with an enrichment field is rejected |
| Phased shapes | seams §5.1–5.5 + GOAL edits (§5.4, §5.7) | smoke run `limit=6`, modes `[extract:a, extract:b]`: accepted behaviour rows parse + schema-validate as EpicPlan/EnrichmentBatch; knowledge targets receive no phased token |
| Tests | pytest additions per factory discipline (Rule R, tier routing, serialization pin, gates, mode-token grammar, layer-aware cursors) | full suite green |
| CONCLUDED banner | on plan §6 (per WS4 §9 S2 row) + dated pointers (plan §8 enum item, RESULTS-po-phase1 open item 2) | banners dated, canon not silently edited |

Serving-ops footnote for the S2 runs: reconstructor `gpt-oss-120b` + Coach `gemma4-coach` co-reside via `autobuild_go` (`agent-config.yaml` already points both at `:9000`); keepalive discipline per §2.6.

---

*Grounded 2026-07-07 against: the 91-record JSONL on this host (tier counts, overlaps, path remaps, Rule-R brief lengths and fallback narrative blocks all re-derived, not trusted from the MANIFEST), `write_output.py` step-9 semantics, `ExampleMetadata`, `config/models.py` GenerationConfig, `generation_loop.py` mode machinery, `prepare_coach_sft.py` weight mechanics, the pinned specialist-agent PO types at `69c8620`, and `player_extract_features.md` Phase-B framing. WS4-S1 session; adversarial builder review (22 findings) + independent fact verification both resolved into this revision — the review outcome is recorded in the WS4 doc §9 evidence note.*
