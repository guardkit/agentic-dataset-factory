# Feature: Agent Factories — Player and Coach

## Problem

The agentic-dataset-factory pipeline requires Player and Coach agents instantiated via factory functions using `create_deep_agent`. Role separation must be enforced through tool access asymmetry: the Player generates training examples with RAG and file-writing tools; the Coach evaluates quality with no tools and no file access.

## Solution

Implement the Hybrid approach (Option C): contract-faithful factory signatures with an extracted shared model factory.

- **Player factory** (`agents/player.py`): Accepts `ModelConfig`, `tools`, `system_prompt`, `memory`. Delegates to `create_deep_agent` with `FilesystemBackend`.
- **Coach factory** (`agents/coach.py`): Accepts `ModelConfig`, `system_prompt`, `memory`. No `tools` parameter (structural D5 enforcement). Always passes `tools=[]`, no backend.
- **Shared model factory** (`agents/model_factory.py`): Translates `ModelConfig` to concrete `BaseChatModel` (DRY).
- **Prompt builders** (`prompts/`): Inject GOAL.md sections into base prompts.
- **Config models** (`config/`): `ModelConfig` and `CoachVerdict` Pydantic BaseModels.

## Subtasks

| # | Task | Complexity | Wave |
|---|------|-----------|------|
| 1 | [TASK-AF-001](TASK-AF-001-modelconfig-pydantic-model.md) — ModelConfig Pydantic model | 3 | 1 |
| 2 | [TASK-AF-002](TASK-AF-002-prompt-builder-module.md) — Prompt builder module | 4 | 1 |
| 3 | [TASK-AF-005](TASK-AF-005-coach-verdict-model.md) — CoachVerdict Pydantic model | 2 | 1 |
| 4 | [TASK-AF-011](TASK-AF-011-pyproject-updates.md) — pyproject.toml updates | 1 | 1 |
| 5 | [TASK-AF-003](TASK-AF-003-player-factory.md) — Player factory | 3 | 2 |
| 6 | [TASK-AF-004](TASK-AF-004-coach-factory.md) — Coach factory | 3 | 2 |
| 7 | [TASK-AF-006](TASK-AF-006-model-factory.md) — Shared model factory | 3 | 2 |
| 8 | [TASK-AF-007](TASK-AF-007-unit-tests-modelconfig.md) — ModelConfig unit tests | 3 | 2 |
| 9 | [TASK-AF-010](TASK-AF-010-unit-tests-prompt-builders.md) — Prompt builder tests | 3 | 2 |
| 10 | [TASK-AF-008](TASK-AF-008-unit-tests-player-factory.md) — Player factory tests | 3 | 3 |
| 11 | [TASK-AF-009](TASK-AF-009-unit-tests-coach-factory.md) — Coach factory tests | 3 | 3 |

## Context

- Review: [TASK-REV-DAA1](../TASK-REV-DAA1-plan-agent-factories.md)
- Feature spec: [agent-factories.feature](../../features/agent-factories/agent-factories.feature) (35 BDD scenarios)
- API contract: [API-generation.md](../../docs/design/contracts/API-generation.md)
- Agent config: [DM-agent-config.md](../../docs/design/models/DM-agent-config.md)
