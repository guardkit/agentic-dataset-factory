/system-arch \
  --from docs/research/agentic-dataset-factory-conversation-starter.md \
  --context docs/research/gcse-tutor-training-data-format.md


/system-design --from docs/architecture/ARCHITECTURE.md --context docs/research/agentic-dataset-factory-conversation-starter.md --context docs/research/gcse-tutor-training-data-format.md


/system-plan \
  --from docs/design/DESIGN.md \
  --context docs/architecture/ARCHITECTURE.md \
  --context docs/research/agentic-dataset-factory-conversation-starter.md \
  --context docs/research/gcse-tutor-training-data-format.md


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

