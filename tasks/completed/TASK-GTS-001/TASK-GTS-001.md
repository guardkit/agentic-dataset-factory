---
id: TASK-GTS-001
title: "Create project scaffolding for synthesis module"
task_type: scaffolding
parent_review: TASK-REV-6DBC
feature_id: FEAT-GTS
wave: 1
implementation_mode: direct
complexity: 2
dependencies: []
status: completed
completed: 2026-03-17T20:45:00Z
completed_location: tasks/completed/TASK-GTS-001/
priority: high
tags: [synthesis, phase1, scaffolding]
---

# Task: Create project scaffolding for synthesis module

## Description

Set up the `synthesis/` directory structure, `pyproject.toml` with dependencies, and the `domains/gcse-english-tutor/` placeholder structure as defined in the training pipeline plan.

## Requirements

### synthesis/ directory
```
synthesis/
├── __init__.py
├── synthesise.py      (empty module with docstring)
├── templates.py       (empty module with docstring)
├── validator.py       (empty module with docstring)
└── tests/
    ├── __init__.py
    ├── conftest.py    (shared fixtures)
    ├── test_synthesise.py
    ├── test_templates.py
    └── test_validator.py
```

### pyproject.toml
- Project name: `agentic-dataset-factory`
- Python: `>=3.11`
- Dependencies:
  - `anthropic>=0.40.0` (Claude API SDK)
  - `pyyaml>=6.0` (generation plan loading)
  - `pydantic>=2.0` (schema validation)
- Dev dependencies:
  - `pytest>=8.0`
  - `pytest-cov`
  - `ruff` (linting)
- Ruff config: line-length 100, Python 3.11 target

### domains/ placeholder
```
domains/
└── gcse-english-tutor/
    └── .gitkeep
```

### output/ gitignore
- Ensure `output/` is in `.gitignore`
- Ensure `checkpoints/` is in `.gitignore`

## Acceptance Criteria

- [x] `synthesis/` directory exists with all files
- [x] `pyproject.toml` is valid and `pip install -e .` succeeds
- [x] `pytest synthesis/tests/ -v` runs (0 tests collected is acceptable)
- [x] `domains/gcse-english-tutor/` directory exists
- [x] `output/` and `checkpoints/` are gitignored
- [x] `ruff check synthesis/` passes with zero errors

## Implementation Notes

This is pure scaffolding — no business logic. Create files with module-level docstrings only.
The `conftest.py` should include a fixture for a sample generation plan (list of target dicts) and a fixture for sample valid/invalid examples.
