━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ARCHITECTURE DOCUMENTATION CREATED
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


Created: docs/architecture/
  ├── ARCHITECTURE.md (index + summary)
  ├── domain-model.md
  ├── system-context.md (C4 Level 1)
  ├── container.md (C4 Level 2)
  ├── assumptions.yaml (10 assumptions)
  └── decisions/
      ├── ADR-ARCH-001-modular-monolith.md
      ├── ADR-ARCH-002-six-module-decomposition.md
      ├── ADR-ARCH-003-docker-containerisation.md
      ├── ADR-ARCH-004-chromadb-embedded-persistent.md
      ├── ADR-ARCH-005-configurable-agent-models.md
      ├── ADR-ARCH-006-sequential-generation.md
      ├── ADR-ARCH-007-structured-json-logging.md
      ├── ADR-ARCH-008-start-fresh-restart.md
      └── ADR-ARCH-009-non-deterministic-generation.md
NOTE: Artefacts NOT seeded to Graphiti (unavailable). Markdown artefacts generated in docs/architecture/.

Open questions resolved during session:

Player turn limit — to be specified in /system-design (GOAL.md config)
Chunking strategy — to be specified in /system-design
Rejection logging — output/rejected.jsonl (ADR-ARCH-007/008)
Concurrency — sequential for v1 (ADR-ARCH-006)
Domain validation — yes, fail fast at startup (Category 5)
Ingestion CLI — standalone script in ingestion/, adapted from docling-dgx-spark-scripts
New decision captured: Both Player and Coach models configurable via agent-config.yaml (ADR-ARCH-005), replacing the exemplar's coach-config.yaml.

Next steps:

Review: docs/architecture/ARCHITECTURE.md
Design APIs: /system-design for full GOAL.md schema, tool contracts, Coach rejection schema, agent-config.yaml spec
Plan features: /system-plan for implementation planning









━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SYSTEM DESIGN COMPLETE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


Created: docs/design/
├── DESIGN.md                          ← summary + file tree + next steps
├── contracts/
│   ├── API-domain-config.md           ← GOAL.md schema (9 sections), parser contract
│   ├── API-ingestion.md               ← CLI interface, chunking, ChromaDB strategy
│   ├── API-generation.md              ← Player-Coach protocol, Coach rejection schema
│   ├── API-tools.md                   ← rag_retrieval + write_output contracts
│   ├── API-output.md                  ← JSONL schemas, rejected format, post-processing split
│   └── API-entrypoint.md              ← agent-config.yaml, startup sequence, generation loop
├── models/
│   ├── DM-goal-schema.md              ← GoalConfig entity + validation rules
│   ├── DM-training-example.md         ← ShareGPT format + metadata + invariants
│   ├── DM-coach-rejection.md          ← CoachVerdict entity + acceptance rule
│   ├── DM-agent-config.md             ← AgentConfig entity + migration notes
│   └── DM-rejected-example.md         ← RejectedExample entity + debugging purpose
└── decisions/
    ├── DDR-001.md                     ← GOAL.md strict validation at startup
    ├── DDR-002.md                     ← Train/validation split as post-processing
    └── DDR-003.md                     ← 3-turn Player-Coach limit before discard
Design questions resolved: 6/6
Contradiction detection: No conflicts with 9 existing ADRs
Graphiti: Unavailable — artefacts written to markdown only

Next steps:

Review: docs/design/DESIGN.md
Plan features: /system-plan for implementation planning
Generate specs: /feature-spec for BDD specifications
Refine design: /design-refine for iterative updates







# Design summary
*guardkit graphiti add-context docs/design/DESIGN.md

# API contracts (6 modules)
*guardkit graphiti add-context docs/design/contracts/API-domain-config.md
*guardkit graphiti add-context docs/design/contracts/API-ingestion.md
*guardkit graphiti add-context docs/design/contracts/API-generation.md
*guardkit graphiti add-context docs/design/contracts/API-tools.md
*guardkit graphiti add-context docs/design/contracts/API-output.md
*guardkit graphiti add-context docs/design/contracts/API-entrypoint.md


# Data models (5 entities)
*guardkit graphiti add-context docs/design/models/DM-goal-schema.md
*guardkit graphiti add-context docs/design/models/DM-training-example.md
*guardkit graphiti add-context docs/design/models/DM-coach-rejection.md
*guardkit graphiti add-context docs/design/models/DM-agent-config.md
*guardkit graphiti add-context docs/design/models/DM-rejected-example.md

# Design decision records (3 DDRs)
*guardkit graphiti add-context docs/design/decisions/DDR-001.md
*guardkit graphiti add-context docs/design/decisions/DDR-002.md
*guardkit graphiti add-context docs/design/decisions/DDR-003.md




Let me check the Graphiti success document and the current state of the architecture docs to understand where we are before proceeding.

Read add-graphiti-success.md
Read scratch_notes.md
Good — Graphiti is working and you've seeded the core architecture docs (ARCHITECTURE.md, container.md, domain-model.md, and ADR-002).

For Phase 2, the pipeline defined by /system-arch is:

/system-arch (done) → /system-design (API contracts) → /system-plan (planning) → /feature-spec (specification)

The two commands serve different purposes:

/system-design — Detailed design: full GOAL.md schema, tool contracts (rag_retrieval, write_output), Coach rejection schema, agent-config.yaml spec, ChromaDB collection strategy, ingestion pipeline design, layer routing logic, LangSmith integration points. This resolves the open design questions from the conversation starter.

/system-plan — Implementation planning: breaks the work into features/tasks, determines build order, identifies dependencies, estimates complexity.

Recommended order: /system-design first, then /system-plan. The design contracts inform what needs to be built and in what order.

Shall I run /system-design with the context from the architecture session? The command would be:


/system-design --from docs/architecture/ARCHITECTURE.md --context docs/research/agentic-dataset-factory-conversation-starter.md --context docs/research/gcse-tutor-training-data-format.md


Good — the design phase produced a comprehensive set of artefacts. The /system-plan command should reference both the architecture and design outputs:


/system-plan \
  --from docs/design/DESIGN.md \
  --context docs/architecture/ARCHITECTURE.md \
  --context docs/research/agentic-dataset-factory-conversation-starter.md \
  --context docs/research/gcse-tutor-training-data-format.md


This gives /system-plan the design contracts as the primary input (what needs to be built) with architecture and research context for constraints and domain knowledge.




━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✅ GRAPHITI SEEDING COMPLETE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


Graphiti context:
  ✓ 1 ADR seeded (ADR-ARCH-010)
  ✓ 1 cross-cutting concerns update seeded
  ✓ 1 config contract update seeded
  ✓ 1 architecture summary refresh seeded
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

SESSION SUMMARY
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Mode: Refine (full review — all 6 categories)

Categories reviewed:

✓ Domain & Methodology — no changes needed
✓ System Structure — 6 modules fully specified, no gaps
✓ Service/Module Relationships — clean unidirectional dependencies
✓ Technology Decisions — coherent stack, grounded in GB10 constraints
✓ Cross-Cutting Concerns — 3 gaps identified and resolved (LLM retry, checkpoint/resume, per-target timeout)
✓ Constraints and NFRs — Coach consistency analysed, documented (no code change needed for v1)
Artefacts produced:

1 new ADR: ADR-ARCH-010 (Accepted)
Updated: ARCHITECTURE.md, container.md, API-entrypoint.md, DM-agent-config.md, DESIGN.md
Next steps:

/feature-plan — decompose into implementation tasks
/feature-spec — generate BDD specifications
/design-refine — iterate on specific design contracts



I prompted:
I think the next stage is to use the /feature-spec commands to generate some specs, please review the docs/research and lets work out which features we need to spec out and what commands parameters to use



Now I have the full picture. The training-pipeline-plan.md is the key document — it defines a two-phase approach and explicitly recommends the /feature-spec workflow. Let me map out the features.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Feature Spec Planning
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Based on the architecture (6 modules), design contracts, and the training pipeline plan, here are the features that need specs. I've ordered them by dependency chain — each feature builds on the previous.

Phase 1: Foundation (no agents, direct Claude API synthesis)
Feature 1 — Phase 1 Synthesis Script
The training pipeline plan explicitly recommends this as the first /feature-spec:


/feature-spec "Phase 1: Generate GCSE English training examples via Claude API synthesis" \
  --context docs/research/gcse-tutor-training-data-format.md \
  --context docs/research/training-pipeline-plan.md
Covers: synthesis/synthesise.py, synthesis/templates.py, synthesis/validator.py, domains/gcse-english-tutor/generation-plan.yaml. Produces the baseline dataset (200-300 examples) for the ablation comparison.

Phase 2: agentic-dataset-factory Pipeline (6 features, one per module)
Feature 2 — Domain Config & GOAL.md Validation


/feature-spec "Domain Config module: GOAL.md parser and strict validation" \
  --context docs/design/contracts/API-domain-config.md \
  --context docs/design/models/DM-goal-schema.md
Covers: GoalConfig parser, 9-section validation, GoalValidationError. Foundation for all other modules.

Feature 3 — Ingestion Pipeline


/feature-spec "Ingestion pipeline: Docling PDF processing to ChromaDB" \
  --context docs/design/contracts/API-ingestion.md \
  --context docs/design/contracts/API-domain-config.md
Covers: ingestion/ingest.py CLI, ingestion/chunker.py, ChromaDB collection lifecycle. Depends on Feature 2 (reads Source Documents from GOAL.md).

Feature 4 — Tools (rag_retrieval + write_output)


/feature-spec "LangChain tools: rag_retrieval and write_output with layer routing" \
  --context docs/design/contracts/API-tools.md \
  --context docs/design/contracts/API-output.md
Covers: tools/rag_retrieval.py, tools/write_output.py, schema validation, layer routing. Depends on Feature 3 (ChromaDB populated).

Feature 5 — Agent Factories (Player + Coach)


/feature-spec "Agent factories: Player and Coach via create_deep_agent" \
  --context docs/design/contracts/API-generation.md \
  --context docs/design/models/DM-coach-rejection.md
Covers: agents/player.py, agents/coach.py, prompt injection from GOAL.md, Coach rejection schema. Depends on Feature 4 (tools).

Feature 6 — Entrypoint & Generation Loop


/feature-spec "Entrypoint: config loading, validation, and generation loop orchestration" \
  --context docs/design/contracts/API-entrypoint.md \
  --context docs/design/models/DM-agent-config.md \
  --context docs/architecture/decisions/ADR-ARCH-010-overnight-run-resilience.md
Covers: agent.py, agent-config.yaml loading, 12-step startup, sequential generation loop, --resume flag, retry/backoff/timeout (ADR-ARCH-010). Depends on Features 2-5.

Feature 7 — GCSE English Tutor Domain Config


/feature-spec "GCSE English tutor GOAL.md: first domain configuration" \
  --context docs/research/gcse-tutor-training-data-format.md \
  --context docs/design/contracts/API-domain-config.md
Covers: domains/gcse-english-tutor/GOAL.md (all 9 sections populated), generation-plan.yaml. This is the content that drives the pipeline — not code, but needs acceptance criteria.

Summary
#	Feature	Module	Dependencies	Phase
1	Phase 1 synthesis script	synthesis/	None	Phase 1 (baseline)
2	Domain Config & GOAL.md validation	domains/	None	Phase 2
3	Ingestion pipeline	ingestion/	Feature 2	Phase 2
4	Tools (RAG + write_output)	tools/	Feature 3	Phase 2
5	Agent factories (Player + Coach)	agents/ + prompts/	Feature 4	Phase 2
6	Entrypoint & generation loop	agent.py	Features 2-5	Phase 2
7	GCSE English tutor domain config	domains/gcse-english-tutor/	Feature 2	Phase 2
Recommendation
Start with Feature 1 (Phase 1 synthesis) — it's self-contained, produces the baseline dataset for the ablation comparison, and validates the training data format before building the full pipeline. The training pipeline plan explicitly recommends this order.

Then Features 2 → 7 in order for Phase 2.

Would you like me to run /feature-spec for Feature 1 now, or would you prefer to adjust the feature breakdown first?






Feature Plans

Based on the existing feature spec, the command would be:


/feature-plan "GCSE English Training Example Synthesis" \
  --context features/gcse-training-synthesis/gcse-training-synthesis_summary.md
You could also pass the original research docs for additional context:


/feature-plan "GCSE English Training Example Synthesis" \
  --context features/gcse-training-synthesis/gcse-training-synthesis_summary.md \
  --context docs/research/gcse-tutor-training-data-format.md \
  --context docs/research/training-pipeline-plan.md





━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
FEATURE SPEC COMPLETE: GOAL.md Parser and Strict Validation
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Files written:
domain-config.feature
domain-config_assumptions.yaml
domain-config_summary.md

Scenarios: 36 total
@key-example: 8    @boundary: 8
@negative: 12      @edge-case: 11
@smoke: 10         @regression: 0

Assumptions: 4 total
high: 1 (auto-proceed)
medium: 3 (Coach review recommended)
low: 0

Deferred: 0 scenario groups

Next steps:
Review: domain-config.feature
Pass to feature-plan:
/feature-plan "GOAL.md Parser and Strict Validation" --context features/domain-config/domain-config_summary.md



FEATURE SPEC COMPLETE: Ingestion Pipeline — Docling PDF Processing to ChromaDB
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Files written:
ingestion-pipeline.feature
ingestion-pipeline_assumptions.yaml
ingestion-pipeline_summary.md

Scenarios: 31 total
@key-example: 7    @boundary: 6
@negative: 9       @edge-case: 11
@smoke: 8          @regression: 0

Assumptions: 4 total
high: 3 (auto-proceed)
medium: 0
low: 1 (human review required)

REVIEW REQUIRED: 1 low-confidence assumption needs verification
See: ingestion-pipeline_assumptions.yaml

Deferred: 0 scenario groups

Next steps:
Review: ingestion-pipeline.feature
Pass to feature-plan:
/feature-plan "Ingestion Pipeline — Docling PDF Processing to ChromaDB" --context features/ingestion-pipeline/ingestion-pipeline_summary.md




━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
FEATURE SPEC COMPLETE: LangChain Tools — RAG Retrieval and Write Output with Layer Routing
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Files written:
langchain-tools.feature
langchain-tools_assumptions.yaml
langchain-tools_summary.md

Scenarios: 41 total
@key-example: 8   @boundary: 8
@negative: 14     @edge-case: 13
@smoke: 10        @regression: 0

Assumptions: 3 total
high: 2 (auto-proceed)
medium: 0
low: 1 (human review required)

REVIEW REQUIRED: 1 low-confidence assumption needs verification
See: langchain-tools_assumptions.yaml

Deferred: 0 scenario groups

Next steps:
Review: langchain-tools.feature
Pass to feature-plan:


/feature-plan "LangChain Tools — RAG Retrieval and Write Output" \
  --context features/langchain-tools/langchain-tools_summary.md




━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
FEATURE SPEC COMPLETE: Agent Factories — Player and Coach via create_deep_agent
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Files written:
agent-factories.feature
agent-factories_assumptions.yaml
agent-factories_summary.md

Scenarios: 35 total
@key-example: 9   @boundary: 6
@negative: 10     @edge-case: 12
@smoke: 11        @regression: 0

Assumptions: 4 total
high: 4 (auto-proceed)
medium: 0
low: 0

Deferred: 0 scenario groups

Next steps:
Review: agent-factories.feature
Pass to feature-plan:


/feature-plan "Agent Factories — Player and Coach" \
  --context features/agent-factories/agent-factories_summary.md



━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
FEATURE SPEC COMPLETE: Entrypoint — Config Loading, Validation, and Generation Loop Orchestration
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Files written:
entrypoint.feature
entrypoint_assumptions.yaml
entrypoint_summary.md

Scenarios: 44 total
@key-example: 8    @boundary: 10
@negative: 10      @edge-case: 16
@smoke: 8          @regression: 0

Assumptions: 5 total
high: 2 (auto-proceed)
medium: 3 (Coach review recommended)
low: 0 (human review required)

Deferred: 0 scenario groups

Next steps:
Review: entrypoint.feature
Pass to feature-plan:


/feature-plan "Entrypoint — Config Loading, Validation, and Generation Loop Orchestration" \
  --context features/entrypoint/entrypoint_summary.md





━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
FEATURE SPEC COMPLETE: GCSE English Tutor GOAL.md — First Domain Configuration
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Files written:
gcse-goal-md.feature
gcse-goal-md_assumptions.yaml
gcse-goal-md_summary.md

Scenarios: 38 total
@key-example: 10   @boundary: 8
@negative: 8       @edge-case: 12
@smoke: 10         @regression: 0

Assumptions: 5 total
high: 2 (auto-proceed)
medium: 3 (Coach review recommended)
low: 0 (human review required)

Deferred: 0 scenario groups

Next steps:
Review: gcse-goal-md.feature
Pass to feature-plan:


/feature-plan "GCSE English Tutor GOAL.md — First Domain Configuration" \
  --context features/gcse-goal-md/gcse-goal-md_summary.md