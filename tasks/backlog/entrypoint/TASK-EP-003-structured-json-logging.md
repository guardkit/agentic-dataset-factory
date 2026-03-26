---
id: TASK-EP-003
title: Structured JSON logging setup
task_type: scaffolding
parent_review: TASK-REV-9EDC
feature_id: FEAT-2CF1
wave: 1
implementation_mode: direct
complexity: 2
dependencies:
- TASK-EP-001
status: in_review
autobuild_state:
  current_turn: 1
  max_turns: 35
  worktree_path: /Users/richardwoollcott/Projects/appmilla_github/agentic-dataset-factory/.guardkit/worktrees/FEAT-6D0B
  base_branch: main
  started_at: '2026-03-20T23:36:11.515109'
  last_updated: '2026-03-20T23:42:03.444795'
  turns:
  - turn: 1
    decision: approve
    feedback: null
    timestamp: '2026-03-20T23:36:11.515109'
    player_summary: 'Implemented config/logging.py with JsonFormatter class and configure_logging(config:
      LoggingConfig) function per ADR-ARCH-007. The JsonFormatter outputs single-line
      JSON with ''level'' and ''message'' fields, plus any extra fields merged from
      the ''extra'' dict parameter. configure_logging() installs a StreamHandler with
      JsonFormatter on the root logger, clears existing handlers, and sets the root
      level from config.level. The implementation follows the existing pattern in
      synthesis/synthesise.py but i'
    player_success: true
    coach_success: true
---

# Task: Structured JSON Logging Setup

## Description

Implement `configure_logging(config: LoggingConfig)` that sets up structured JSON logging as required by ADR-ARCH-007. This must be called early in the startup sequence (step 2) before any other output.

## Requirements

- `configure_logging(config: LoggingConfig)` function
- Output structured JSON log lines (ADR-ARCH-007)
- Support log levels: DEBUG, INFO, WARNING, ERROR
- Use Python's `logging` module with a JSON formatter
- Set root logger level from config
- Log format must match the progress logging examples in API-entrypoint.md:
  ```json
  {"event": "startup", "domain": "gcse-english-tutor", "targets": 1000}
  ```

## Acceptance Criteria

- [ ] Structured JSON logging active after `configure_logging()` call
- [ ] Log level set from config (BDD: "Structured logging is configured from the config file")
- [ ] JSON format output on all log lines
- [ ] Works with Python standard `logging` module

## Reference

- ADR-ARCH-007: Structured JSON logging
- API contract: `docs/design/contracts/API-entrypoint.md` (Progress Logging section)
- BDD: "Structured logging is configured from the config file"

## Implementation Notes

Place in `config/logging.py`. Use `python-json-logger` or a minimal custom `JsonFormatter`.
