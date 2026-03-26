# Review Report: TASK-REV-F5F5

## Executive Summary

The Phase 2 feature creation pipeline for agentic-dataset-factory followed a 7-stage command sequence that produced 43 implementation tasks across 6 features, all of which completed successfully via autonomous `guardkit autobuild`. The pipeline demonstrates a repeatable, largely automatable workflow with clear automation opportunities — particularly around command chaining, context inference, and Graphiti seeding. The primary human intervention point was the DeepAgents SDK decision, which materially shaped two features.

## Review Details

- **Mode**: Process Documentation / Decision Analysis
- **Depth**: Standard
- **Task**: Document Phase 2 feature creation process for automation

---

## Process Map

### Stage 1: Architecture Definition (`/system-arch`)

**Command**:
```
/system-arch
```
(No `--context` flags documented; interactive session)

**Key Outputs**:
- `docs/architecture/ARCHITECTURE.md` (index + summary)
- C4 diagrams: `system-context.md` (L1), `container.md` (L2), `domain-model.md`
- 9 ADRs (ADR-ARCH-001 through ADR-ARCH-009)
- `assumptions.yaml` (10 assumptions)

**Human Input**:
- Resolved open questions during session (player turn limit, chunking strategy, rejection logging, concurrency model, domain validation, ingestion CLI approach)
- Key decision: Both Player and Coach models configurable via `agent-config.yaml` (ADR-ARCH-005)
- Confirmed 6-module decomposition (ADR-ARCH-002)

**Defaults Accepted**: Modular monolith pattern, Docker containerisation, ChromaDB embedded, sequential generation, structured JSON logging, start-fresh restart strategy

**Note**: Graphiti was unavailable at this stage — artefacts written to markdown only.

---

### Stage 2: System Design (`/system-design`)

**Command**:
```
/system-design --from docs/architecture/ARCHITECTURE.md \
  --context docs/research/agentic-dataset-factory-conversation-starter.md \
  --context docs/research/gcse-tutor-training-data-format.md
```

**Key Outputs**:
- `docs/design/DESIGN.md` (summary + file tree)
- 6 API contracts (`contracts/API-*.md`)
- 5 data models (`models/DM-*.md`)
- 3 DDRs (DDR-001 through DDR-003)

**Human Input**:
- Selected `--context` files (2 research docs + architecture)
- Resolved 6/6 design questions during session

**Defaults Accepted**: All design decisions aligned with architecture — no contradictions detected.

---

### Stage 3: Architecture Refinement (`/arch-refine`)

**Command**:
```
/arch-refine
```
(Full review — all 6 categories)

**Key Outputs**:
- 1 new ADR: ADR-ARCH-010 (overnight run resilience)
- Updated: ARCHITECTURE.md, container.md, API-entrypoint.md, DM-agent-config.md, DESIGN.md
- 3 cross-cutting gaps identified and resolved:
  1. LLM retry strategy
  2. Checkpoint/resume mechanism
  3. Per-target timeout

**Human Input**: Confirmed refinement scope (full review vs targeted). No other intervention needed.

---

### Stage 4: Graphiti Seeding (Manual)

**Commands** (from scratch_notes.md lines 99-121):
```
guardkit graphiti add-context docs/design/DESIGN.md
guardkit graphiti add-context docs/design/contracts/API-domain-config.md
guardkit graphiti add-context docs/design/contracts/API-ingestion.md
guardkit graphiti add-context docs/design/contracts/API-generation.md
guardkit graphiti add-context docs/design/contracts/API-tools.md
guardkit graphiti add-context docs/design/contracts/API-output.md
guardkit graphiti add-context docs/design/contracts/API-entrypoint.md
guardkit graphiti add-context docs/design/models/DM-goal-schema.md
guardkit graphiti add-context docs/design/models/DM-training-example.md
guardkit graphiti add-context docs/design/models/DM-coach-rejection.md
guardkit graphiti add-context docs/design/models/DM-agent-config.md
guardkit graphiti add-context docs/design/models/DM-rejected-example.md
guardkit graphiti add-context docs/design/decisions/DDR-001.md
guardkit graphiti add-context docs/design/decisions/DDR-002.md
guardkit graphiti add-context docs/design/decisions/DDR-003.md
```

Post-`/arch-refine` seeding:
- ADR-ARCH-010, cross-cutting concerns update, config contract update, architecture summary refresh

**Human Input**: Entirely manual — human selected which documents to seed and executed each command individually.

**Pain Point**: 15+ individual CLI commands with no batch mode. High friction, error-prone.

---

### Stage 5: BDD Specification (`/feature-spec` x6)

| # | Feature | Command Context Files | Scenarios |
|---|---------|----------------------|-----------|
| 1 | Domain Config | `API-domain-config.md`, `DM-goal-schema.md` | 36 |
| 2 | Ingestion Pipeline | `API-ingestion.md`, `API-domain-config.md` | 31 |
| 3 | LangChain Tools | `API-tools.md`, `API-output.md` | 41 |
| 4 | Agent Factories | `API-generation.md`, `DM-coach-rejection.md` | 35 |
| 5 | Entrypoint | `API-entrypoint.md`, `DM-agent-config.md`, `ADR-ARCH-010.md` | 44 |
| 6 | GCSE GOAL.md | `gcse-tutor-training-data-format.md`, `API-domain-config.md` | 38 |
| | **Total** | | **225** |

**Human Input**:
- Chose the 6-feature breakdown (1:1 with modules)
- Selected `--context` files for each command (2-3 files each)
- Confirmed feature names/descriptions
- Reviewed assumptions files (2 features had low-confidence assumptions requiring verification)

**Defaults Accepted**: Scenario counts, tag distributions, scenario groupings all accepted as generated.

---

### Stage 6: Feature Planning (`/feature-plan` x6)

| Feature | ID | Tasks | Waves | Review Task |
|---------|------|-------|-------|-------------|
| Goal.md Parser | FEAT-5606 | 5 | 4 | TASK-REV-DC5D |
| Ingestion Pipeline | FEAT-F59D | 7 | 4 | TASK-REV-F479 |
| LangChain Tools | FEAT-945D | 5 | 4 | TASK-REV-723B |
| Agent Factories | FEAT-5AC9 | 11 | 3 | TASK-REV-DAA1 |
| Entrypoint | FEAT-6D0B | 10 | 8 | TASK-REV-9EDC |
| GCSE GOAL.md | FEAT-FBBC | 5 | 3 | TASK-REV-843F |
| **Total** | | **43** | | |

**Human Input**:
- Passed `--context` with feature spec summary for each
- Confirmed task breakdown, wave structure, implementation modes
- All 6 review tasks accepted (completed status)

**Key Design Decision — DeepAgents SDK**:
The system's initial recommendations suggested LangGraph + Pydantic as the agent framework. The human directed use of the **LangChain DeepAgents SDK** (`create_deep_agent()`), which shaped:
- FEAT-5AC9 (Agent Factories): Player/Coach factory functions use `create_deep_agent()`
- FEAT-6D0B (Entrypoint): Plain Python loop for target iteration, NOT LangGraph state machine; LangGraph is a thin runtime wrapper only

**Rationale**: DeepAgents SDK manages tool calling and conversation natively, reducing boilerplate vs raw LangGraph state graphs. LangGraph retained only for `langgraph dev` / Docker runtime export.

---

### Stage 7: Autonomous Build (`guardkit autobuild feature` x6)

**Command** (identical for all 6):
```
GUARDKIT_LOG_LEVEL=DEBUG guardkit autobuild feature FEAT-XXXX --max-turns 35 --verbose
```

| Feature | Tasks | Turns | 1st-Attempt Pass | Completion |
|---------|-------|-------|-------------------|------------|
| FEAT-5606 | 5 | 8 | 60% | 2026-03-20 15:21 |
| FEAT-F59D | 7 | 7 | 100% | 2026-03-20 17:17 |
| FEAT-945D | 5 | 6 | 80% | 2026-03-20 21:16 |
| FEAT-5AC9 | 11 | 11 | 100% | 2026-03-20 23:15 |
| FEAT-6D0B | 10 | 10 | 100% | 2026-03-20 23:41 |
| FEAT-FBBC | 5 | 6 | 80% | 2026-03-21 07:17 |
| **Total** | **43** | **48** | **93.3%** | |

**Human Input**: Started each build manually (separate terminal tabs). No intervention during builds.

**Key Metrics**:
- 43/43 tasks completed successfully
- Average 1.12 turns per task
- 0 SDK ceiling hits
- All quality gates passed

---

## Human Input vs Defaults Matrix

| Stage | Human Decision | Impact |
|-------|---------------|--------|
| `/system-arch` | Resolved 7 open questions | Shaped all ADRs |
| `/system-arch` | Confirmed 6-module decomposition | Defined feature boundaries |
| `/system-design` | Selected 2 context files | Scoped design session |
| `/system-design` | Resolved 6 design questions | No — all aligned with arch |
| `/arch-refine` | Confirmed full review scope | Low — standard workflow |
| Graphiti | Selected docs + executed 15+ commands | Populated knowledge graph |
| `/feature-spec` x6 | Selected context files (2-3 per feature) | Scoped each spec correctly |
| `/feature-spec` x6 | Confirmed 6-feature breakdown | High — 1:1 with modules |
| `/feature-plan` x6 | Accepted all 6 plans as generated | Low — plans were solid |
| **DeepAgents SDK** | **Overrode system recommendation** | **High — reshaped 2 features** |
| `autobuild` x6 | Started each build manually | Low — could be scripted |

**Summary**: 3 high-impact decisions (module decomposition, feature breakdown, DeepAgents SDK), ~10 medium decisions (context file selection), many low-impact confirmations.

---

## Automation Opportunity Matrix

| Step | Current Effort | Automation Feasibility | Dependencies | Priority |
|------|---------------|----------------------|--------------|----------|
| **Command chaining** (`arch` → `design` → `refine`) | Manual copy-paste of context paths | High — output paths are deterministic | None | P1 |
| **Context inference** | Human selects `--context` files | High — can infer from previous stage outputs | Command chaining | P1 |
| **Graphiti auto-seeding** | 15+ manual CLI commands | High — seed after each stage automatically | Graphiti availability | P1 |
| **Feature-spec batching** | 6 separate commands, 6 conversations | Medium — need feature list + context map | Context inference | P2 |
| **Feature-plan batching** | 6 separate commands | High — input is feature spec summary | Feature-spec completion | P2 |
| **Autobuild orchestration** | 6 manual terminal tabs | High — simple loop/parallel script | Feature-plan completion | P1 |
| **Review task auto-accept** | Human confirms each review | Medium — could auto-accept if score > threshold | Policy decision | P3 |
| **End-to-end pipeline** | ~7 stages, multiple conversations | Medium — requires decision injection points | All above | P3 |

---

## Pain Points and Friction Log

| Pain Point | Impact | Suggested Mitigation |
|-----------|--------|---------------------|
| **Multiple Claude Code tabs** | High — context fragmentation across conversations | Pipeline command that maintains context across stages |
| **Conversation clearing** | High — loss of decision context and rationale | Auto-capture decisions to Graphiti before clearing |
| **Manual Graphiti seeding** | Medium — 15+ commands, error-prone | Auto-seed after each `/system-*` and `/arch-refine` stage |
| **Context parameter construction** | Medium — human must know which files to pass | Auto-infer from previous stage outputs |
| **Sequential feature-spec/plan** | Medium — 6 commands each, could parallelize | Batch command or parallel execution |
| **No pipeline resume** | Low (for now) — if a stage fails, restart from scratch | Checkpoint mechanism per stage |
| **Autobuild tab management** | Low — 6 terminals, but builds are autonomous | Script with `&` or job queue |

---

## Recommendations

### R1: Create `guardkit pipeline` orchestration command (P1)

A single command that chains: `system-arch` → `system-design` → `arch-refine` → Graphiti seed → `feature-spec` x N → `feature-plan` x N → `autobuild` x N.

**Decision points** would pause for human input (e.g., module decomposition, SDK choice) with defaults that can be overridden.

### R2: Auto-seed Graphiti after each stage (P1)

After each `/system-arch`, `/system-design`, `/arch-refine` command, automatically seed all produced artefacts to Graphiti. Eliminate the 15+ manual CLI commands.

### R3: Context inference engine (P1)

Each stage's output directory is deterministic. The next command should auto-populate `--context` flags from previous stage outputs. E.g., `/system-design` should automatically find `docs/architecture/ARCHITECTURE.md`.

### R4: Parallel autobuild orchestration (P1)

Replace 6 manual terminal tabs with:
```bash
guardkit autobuild feature FEAT-5606 FEAT-F59D FEAT-945D FEAT-5AC9 FEAT-6D0B FEAT-FBBC \
  --max-turns 35 --parallel 3
```
With dependency-aware scheduling (e.g., FEAT-6D0B depends on FEAT-5AC9).

### R5: Feature batch commands (P2)

```bash
guardkit feature-spec --batch features.yaml  # specs all features
guardkit feature-plan --batch features.yaml  # plans all features
```
Where `features.yaml` defines the feature list with context mappings.

### R6: Decision capture protocol (P2)

Auto-capture all human decisions to Graphiti during interactive sessions, eliminating the risk of losing context when conversations are cleared.

### R7: Pipeline resume/checkpoint (P3)

Track pipeline state so a failed stage can be restarted without re-running earlier stages. Store stage completion status and outputs.

---

## Appendix: Timeline

| Time | Stage | Duration (est.) |
|------|-------|-----------------|
| Session 1 | `/system-arch` | ~60 min |
| Session 2 | `/system-design` | ~45 min |
| Session 3 | `/arch-refine` + Graphiti seed | ~30 min |
| Session 4 | `/feature-spec` x6 | ~90 min (6 x 15 min) |
| Session 5 | `/feature-plan` x6 | ~60 min (6 x 10 min) |
| 2026-03-20 15:21 – 2026-03-21 07:17 | `autobuild` x6 | ~16 hours (autonomous) |
| **Total** | | ~20 hours (5 hrs human, 16 hrs autonomous) |

## Appendix: Artefact Inventory

| Category | Count |
|----------|-------|
| ADRs | 10 (9 + ADR-ARCH-010) |
| DDRs | 3 |
| API Contracts | 6 |
| Data Models | 5 |
| BDD Scenarios | 225 |
| Features | 6 |
| Tasks | 43 |
| C4 Diagrams | 2 (L1, L2) |
| Assumptions | 10 (arch) + 25 (feature specs) |
