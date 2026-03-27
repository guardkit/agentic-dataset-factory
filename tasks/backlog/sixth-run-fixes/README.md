# Sixth Run Fixes (TASK-REV-TRF6)

## Problem

Run 6 (qwen35-run03) crashed: Player wrote training example to `/tmp/training_example.json` via leaked `write_file` tool instead of returning content. 0 targets processed.

Root cause: `agents/player.py` calls `create_deep_agent()` which injects `FilesystemMiddleware` and 8 platform tools. TASK-TRF-012 fixed the Coach but left the Player unchanged.

## Tasks

| ID | Title | Priority | Wave | Depends On |
|----|-------|----------|------|------------|
| TASK-TRF-016 | Bypass create_deep_agent for Player | Critical | 1 | — |
| TASK-TRF-017 | Update Player factory tests | Critical | 1 | TRF-016 |
| TASK-TRF-018 | Add token usage logging | Medium | 2 | — |
| TASK-TRF-019 | Verify `<think>` closing tag | Low | 2 | — |
| TASK-REV-TRF7 | Seventh run validation | Critical | 3 | TRF-016, TRF-017 |

## Execution Strategy

**Wave 1** (Critical — blocks pipeline):
- TASK-TRF-016: Fix Player factory (mirrors Coach fix from TRF-012)
- TASK-TRF-017: Update tests (depends on TRF-016)

**Wave 2** (Improvements — can run in parallel):
- TASK-TRF-018: Token usage logging
- TASK-TRF-019: `<think>` tag investigation

**Wave 3** (Validation):
- TASK-REV-TRF7: Run pipeline and analyse results → production readiness decision
