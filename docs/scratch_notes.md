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
