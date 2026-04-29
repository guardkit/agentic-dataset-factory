---
id: TASK-AD14-B
title: Add pytest-asyncio to [dev] extra (fix 90 pre-existing async test failures)
status: completed
task_type: implementation
implementation_mode: direct
parent_review: TASK-REV-AD14
feature_id: FEAT-AD14
feature_slug: langchain-1x-portfolio-alignment
wave: 2
created: 2026-04-29T00:00:00Z
updated: 2026-04-29T00:00:00Z
completed: 2026-04-29T00:00:00Z
priority: medium
tags: [test-hygiene, pytest, dev-dependencies]
complexity: 1
estimated_minutes: 10
related:
  - .claude/reviews/TASK-REV-AD14-report.md
optional: true
---

# Add pytest-asyncio to [dev] extra (fix 90 pre-existing async test failures)

## Context

TASK-REV-AD14's empirical pytest run surfaced **90 pre-existing test failures**, all sharing the same root cause: `pyproject.toml` configures `asyncio_mode = "auto"` under `[tool.pytest.ini_options]`, but the `[project.optional-dependencies].dev` extra does not include `pytest-asyncio`. Result: every test using `async def` and/or `@pytest.mark.asyncio` fails at the collection-execute boundary with:

```
async def functions are not natively supported.
You need to install a suitable plugin for your async framework, for example:
  - anyio
  - pytest-asyncio
  - pytest-tornasync
  - pytest-trio
  - pytest-twisted
```

This is **independent of the langchain pin question** (TASK-AD14-A) — confirmed by the review running on both deepagents 0.4.12 and 0.5.4 and producing the identical 90/1869 split. Filing as a separate hygiene task per the brief's "out of scope" guidance.

## Acceptance criteria

- [ ] `[project.optional-dependencies].dev` includes `pytest-asyncio>=0.24,<1`.
- [ ] `uv pip install -e ".[dev]"` succeeds on Python 3.14.
- [ ] `pytest --tb=no -q` reports zero failures attributable to `async def functions are not natively supported`.
- [ ] If new failures surface (previously masked by the async-skip), document them in this task's notes — do not silently leave them. They are most likely also pre-existing and may need a follow-up triage task.
- [ ] `uv.lock` regenerated.

## Diff

```diff
--- pyproject.toml
+++ pyproject.toml
 dev = [
     "pytest>=8.0",
+    "pytest-asyncio>=0.24,<1",
     # TASK-OPS-BDDM-5 / FEAT-BDDM: advisory remediation — pytest-bdd present so future
     # @task:-tagged scenarios cannot trigger the runner-without-producer silent bypass.
     "pytest-bdd>=8.1,<9",
     "pytest-cov",
     "ruff",
 ]
```

`pytest-asyncio` major-zero is `<1` (Schreiner-style same-major cap on a fast-moving plugin). Adjust if the project conventionally uses tighter caps on dev tooling.

## Suggested execution

```bash
cd /Users/richardwoollcott/Projects/appmilla_github/agentic-dataset-factory
# Edit pyproject.toml [dev] extra per the diff above

uv pip install --python .venv/bin/python -e ".[dev]"
uv lock
.venv/bin/python -m pytest --tb=no -q

# Expected: 1959 passed (or close — surface any newly-visible failures)
```

## Out of scope

- Pin alignment work — TASK-AD14-A.
- Triage of any newly-visible test failures (those that were previously masked by the async-skip). File a follow-up if any surface.

## Notes

- The 90 failure clusters span `tests/test_decouple_format_retries.py`, `tests/test_format_gate_key_validation.py`, `tests/test_httpstatuserror_handling.py`, `tests/test_structured_outputs_fallback.py`, `tests/test_integration_smoke.py`, `tests/test_valueerror_per_target_handler.py`, `tests/test_coach_retry_json_reinforcement.py`, and a handful of others. All are `@pytest.mark.asyncio` tests.
- This task is `optional: true` — the pin alignment work in TASK-AD14-A doesn't depend on it. Run if a clean pytest is wanted; skip if the pre-existing failures are tolerated.
- Wave 2 (after TASK-AD14-A) because both tasks edit `pyproject.toml`. Sequential keeps the diff clean per task. They could be bundled into a single commit if preferred.

## Implementation result (2026-04-29)

- Edited `pyproject.toml`: appended `"pytest-asyncio>=0.24,<1"` to `[project.optional-dependencies].dev` per the brief's diff exactly.
- `uv pip install --python .venv/bin/python -e ".[dev]"` succeeded on Python 3.14.2; resolved `pytest-asyncio==0.26.0`. Note: pytest itself was downgraded from 9.0.3 → 8.4.2 to satisfy `pytest-asyncio<1`'s `pytest<9` constraint. The dev extra still pins `pytest>=8.0` so this is in-bounds.
- `uv lock` regenerated cleanly: +1 package added (`pytest-asyncio v0.26.0`), pytest pinned 9.0.2 → 8.4.2.
- `pytest --tb=no -q` result: **1958 passed, 1 failed** (was 1869 passed, 90 failed pre-task). All 89 of the in-scope tests covered by the original async-skip clusters now pass; the 90th appears to have been collapsed into the new total in a way I cannot tell apart without comparing test IDs against the review report.

### Newly-visible failure (acceptance criterion #4)

One non-async test surfaced as failing: `domain_config/tests/test_models.py::TestAC002_PydanticModelsMatchContract::test_evaluation_criterion_fields_match_contract`.

```
AssertionError: assert {'description...me', 'weight'} == {'description...me', 'weight'}
Extra items in the left set: 'layer'
```

The test asserts equality between `EvaluationCriterion.model_fields.keys()` and a hard-coded contract set; the model has gained a `layer` field that the test's expected set was never updated to include. This is a contract-drift bug, fully unrelated to async — `grep "async\|asyncio" domain_config/tests/test_models.py` returns no hits. Not in scope for this task per the "out of scope" guidance; recommend a small follow-up task (test_evaluation_criterion contract refresh — a 2-line edit to add `'layer'` to the expected set, gated on confirming `layer` is the intended public contract).
