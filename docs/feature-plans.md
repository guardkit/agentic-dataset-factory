

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

FEATURE PLANNING COMPLETE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

✅ Feature FEAT-5606 created
📁 Feature file: .guardkit/features/FEAT-5606.yaml

📋 Tasks: 5

Task	Name	Complexity	Wave	Mode
TASK-DC-001	Create domain_config package + Pydantic models	3	1	direct
TASK-DC-002	Implement markdown section splitter	4	2	task-work
TASK-DC-003	Implement table parser + JSON extractor	5	2	task-work
TASK-DC-004	Cross-section validation + error aggregation	5	3	task-work
TASK-DC-005	Public API + integration tests	4	3	task-work
🔀 Parallel execution groups: 4 waves

Wave 1: [TASK-DC-001]
Wave 2: [TASK-DC-002, TASK-DC-003] (parallel)
Wave 3: [TASK-DC-004]
Wave 4: [TASK-DC-005]
📁 Files created:


tasks/backlog/goal-md-parser/
├── README.md
├── IMPLEMENTATION-GUIDE.md
├── TASK-DC-001-pydantic-models.md
├── TASK-DC-002-section-splitter.md
├── TASK-DC-003-table-json-parsers.md
├── TASK-DC-004-cross-section-validation.md
└── TASK-DC-005-public-api-integration-tests.md

.guardkit/features/FEAT-5606.yaml
Original review: TASK-REV-DC5D

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Next steps:

Review: IMPLEMENTATION-GUIDE.md
Start Wave 1: /task-work TASK-DC-001
Or run autonomously: /feature-build FEAT-5606






━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
FEATURE PLANNING COMPLETE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

✅ Feature FEAT-F59D created
📋 Tasks: 7

Wave	Tasks	Parallel
1	TASK-ING-001: Package + models (scaffolding, c:3)	—
2	TASK-ING-002: Chunker (c:4), TASK-ING-003: Docling (c:5), TASK-ING-004: ChromaDB (c:5), TASK-ING-005: GOAL reader (c:3)	4 parallel
3	TASK-ING-006: Orchestrator + CLI (c:5)	—
4	TASK-ING-007: Integration tests (c:5)	—
📁 Files created:

Feature YAML: .guardkit/features/FEAT-F59D.yaml
Task folder: tasks/backlog/ingestion-pipeline/
Implementation guide: IMPLEMENTATION-GUIDE.md
7 task files: TASK-ING-001 through TASK-ING-007
🔗 Review task: TASK-REV-F479 (review_complete)

Next steps:

Review: IMPLEMENTATION-GUIDE.md
Start autonomous build: /feature-build FEAT-F59D
Or start manually: /task-work TASK-ING-001



━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
FEATURE PLANNING COMPLETE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

✅ Feature FEAT-945D created
📁 Feature file: .guardkit/features/FEAT-945D.yaml

📋 Tasks: 5

| Task | Name | Complexity | Wave | Mode |
|------|------|-----------|------|------|
| TASK-LCT-001 | Create tools package + Pydantic models | 3 | 1 | direct |
| TASK-LCT-002 | Implement rag_retrieval factory + tool | 5 | 2 | task-work |
| TASK-LCT-003 | Implement write_output factory + tool + layer routing | 6 | 2 | task-work |
| TASK-LCT-004 | Tool assignment + factory wiring | 3 | 3 | direct |
| TASK-LCT-005 | Unit + integration tests (41 BDD scenarios) | 5 | 3 | task-work |

🔀 Parallel execution groups: 4 waves

Wave 1: [TASK-LCT-001]
Wave 2: [TASK-LCT-002, TASK-LCT-003] (parallel)
Wave 3: [TASK-LCT-004]
Wave 4: [TASK-LCT-005]

📁 Files created:

tasks/backlog/langchain-tools/
├── README.md
├── IMPLEMENTATION-GUIDE.md
├── TASK-LCT-001-tools-package-and-models.md
├── TASK-LCT-002-rag-retrieval-tool.md
├── TASK-LCT-003-write-output-tool.md
├── TASK-LCT-004-tool-assignment-factory-wiring.md
└── TASK-LCT-005-unit-integration-tests.md

.guardkit/features/FEAT-945D.yaml
🔗 Review task: TASK-REV-723B (review_complete)

Next steps:

Review: IMPLEMENTATION-GUIDE.md
Start Wave 1: /task-work TASK-LCT-001
Or run autonomously: /feature-build FEAT-945D





━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
FEATURE PLANNING COMPLETE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

✅ Feature FEAT-945D created
📁 Feature file: FEAT-945D.yaml

📋 Tasks: 5

Task	Name	Complexity	Wave	Mode
TASK-LCT-001	Create tools package + Pydantic models	3	1	direct
TASK-LCT-002	Implement rag_retrieval factory + tool	5	2	task-work
TASK-LCT-003	Implement write_output factory + tool + layer routing	6	2	task-work
TASK-LCT-004	Tool assignment + factory wiring	3	3	direct
TASK-LCT-005	Unit + integration tests (41 BDD scenarios)	5	3	task-work
🔀 Parallel execution groups: 4 waves

Wave 1: [TASK-LCT-001]
Wave 2: [TASK-LCT-002, TASK-LCT-003] (parallel)
Wave 3: [TASK-LCT-004]
Wave 4: [TASK-LCT-005]
📁 Files created:


tasks/backlog/langchain-tools/
├── README.md
├── IMPLEMENTATION-GUIDE.md
├── TASK-LCT-001-tools-package-and-models.md
├── TASK-LCT-002-rag-retrieval-tool.md
├── TASK-LCT-003-write-output-tool.md
├── TASK-LCT-004-tool-assignment-factory-wiring.md
└── TASK-LCT-005-unit-integration-tests.md

.guardkit/features/FEAT-945D.yaml
🔗 Original review: TASK-REV-723B (review_complete)

Next steps:

Review: IMPLEMENTATION-GUIDE.md
Start Wave 1: /task-work TASK-LCT-001
Or run autonomously: /feature-build FEAT-945D




━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✅ FEATURE PLANNING COMPLETE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📁 Feature: FEAT-5AC9 — Agent Factories — Player and Coach
📋 Tasks: 11 (in backlog)
🔀 Parallel execution: 3 waves

Wave 1 (4 tasks — parallel):

TASK-AF-001: ModelConfig Pydantic model (complexity: 3)
TASK-AF-002: Prompt builder module (complexity: 4)
TASK-AF-005: CoachVerdict Pydantic model (complexity: 2)
TASK-AF-011: pyproject.toml updates (complexity: 1)
Wave 2 (5 tasks — parallel):

TASK-AF-003: Player factory (complexity: 3)
TASK-AF-004: Coach factory (complexity: 3)
TASK-AF-006: Shared model factory (complexity: 3)
TASK-AF-007: ModelConfig unit tests (complexity: 3)
TASK-AF-010: Prompt builder tests (complexity: 3)
Wave 3 (2 tasks — parallel):

TASK-AF-008: Player factory tests (complexity: 3)
TASK-AF-009: Coach factory tests (complexity: 3)
📁 Feature file: FEAT-5AC9.yaml
📁 Task files: tasks/backlog/agent-factories/
📁 Implementation guide: IMPLEMENTATION-GUIDE.md
📋 Original review: TASK-REV-DAA1 (completed)

Next steps:

Review: IMPLEMENTATION-GUIDE.md
Start implementation: /feature-build FEAT-5AC9
Or work individual tasks: /task-work TASK-AF-001






━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
FEATURE PLANNING COMPLETE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Feature: FEAT-6D0B — Entrypoint — Config Loading, Validation, and Generation Loop Orchestration
Approach: Pydantic Config + DeepAgents SDK Orchestration
Aggregate Complexity: 6/10

📁 Feature file: .guardkit/features/FEAT-6D0B.yaml
📁 Task folder: tasks/backlog/entrypoint/
📋 Review: TASK-REV-9EDC (completed)

Tasks (10)
Wave	Task	Name	Complexity	Mode
1	TASK-EP-001	Pydantic config models	3	task-work
2	TASK-EP-002	Config loader	3	task-work
2	TASK-EP-003	Structured JSON logging	2	direct
3	TASK-EP-004	Domain resolution + ChromaDB	3	task-work
3	TASK-EP-005	Checkpoint/resume + lock file	4	task-work
4	TASK-EP-006	Output directory management	2	direct
5	TASK-EP-007	Generation loop (Player-Coach)	6	task-work
6	TASK-EP-008	LangGraph thin wrapper	3	task-work
7	TASK-EP-009	Startup orchestration	4	task-work
8	TASK-EP-010	Integration tests	4	task-work
Key Design Points
DeepAgents SDK drives agent lifecycle — create_deep_agent() manages tool calling and conversation
Plain Python loop for target iteration — NOT LangGraph state machine
LangGraph is a thin runtime wrapper (graph export for langgraph dev / Docker)
Pydantic handles config validation declaratively (covers 10+ BDD boundary scenarios)
ADR-ARCH-010 resilience: retry at model level, timeout at target level, checkpoint via atomic file write
Next Steps
Review: IMPLEMENTATION-GUIDE.md
Start implementation: /feature-build FEAT-6D0B
Or work individual tasks: /task-work TASK-EP-001





━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✅ FEATURE PLANNING COMPLETE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📁 Feature: FEAT-FBBC — GCSE English Tutor GOAL.md — First Domain Configuration
📋 Tasks: 5 across 3 waves
📁 Feature file: FEAT-FBBC.yaml
📁 Task folder: tasks/backlog/gcse-goal-md/
📋 Review task: TASK-REV-843F (completed)

Execution Plan
Wave	Tasks	Parallel	Mode
1	TASK-GG-001: Create directory structure	Solo	direct
2	TASK-GG-002: Sections 1-5, TASK-GG-003: Sections 6-9	✅ 2 parallel	task-work
3	TASK-GG-004: Metadata tests, TASK-GG-005: Smoke tests	✅ 2 parallel	task-work
Next Steps
Review: IMPLEMENTATION-GUIDE.md
Start implementation: /task-work TASK-GG-001
Or autonomous build: /feature-build FEAT-FBBC




