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