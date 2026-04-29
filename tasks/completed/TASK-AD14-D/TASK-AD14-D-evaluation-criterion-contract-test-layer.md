---
id: TASK-AD14-D
title: Update EvaluationCriterion contract test to include layer field
status: completed
previous_state: in_review
state_transition_reason: "task-complete; all quality gates passed (1959/0 pytest, ruff clean)"
task_type: testing
implementation_mode: direct
parent: TASK-AD14-B
parent_review: TASK-REV-AD14
feature_id: FEAT-AD14
feature_slug: langchain-1x-portfolio-alignment
created: 2026-04-29T00:00:00Z
updated: 2026-04-29T00:00:00Z
completed: 2026-04-29T00:00:00Z
completed_location: tasks/completed/TASK-AD14-D/
test_results:
  status: passed
  targeted: "1 passed (test_evaluation_criterion_fields_match_contract)"
  full_suite: "1959 passed, 0 failed (was 1958/1 at end of TASK-AD14-B)"
  lint: "ruff: all checks passed"
priority: low
tags: [testing, contract-drift, domain-config, TASK-AD14-followup]
complexity: 1
estimated_minutes: 5
related:
  - tasks/completed/TASK-AD14-B/TASK-AD14-B-add-pytest-asyncio.md
  - domain_config/models.py
  - domain_config/tests/test_models.py
optional: true
---

# Update EvaluationCriterion contract test to include layer field

## Context

Surfaced by TASK-AD14-B's "newly-visible failure" acceptance criterion. After
adding `pytest-asyncio` to the `[dev]` extra (which un-masked 90 async tests
that had been silently skipping), one previously-hidden non-async failure
appeared:

```
domain_config/tests/test_models.py::TestAC002_PydanticModelsMatchContract::test_evaluation_criterion_fields_match_contract
AssertionError: assert {'description...me', 'weight'} == {'description...me', 'weight'}
Extra items in the left set: 'layer'
```

The test at `domain_config/tests/test_models.py:812` asserts equality between
`EvaluationCriterion.model_fields.keys()` and a hard-coded contract set
`{"name", "description", "weight"}`. The model at
`domain_config/models.py:86` has since gained a fourth public field
`layer: Literal["behaviour", "knowledge", "all"] = "all"` (line 97), but the
test's expected set was never updated. Pure contract drift — fully unrelated
to the async / pytest-asyncio work.

The test instance construction call inside the same test only sets `name`,
`description`, `weight`, which is fine because `layer` defaults to `"all"`,
but the `model_fields.keys()` comparison still fails on the missing key.

## Acceptance criteria

- [ ] `domain_config/tests/test_models.py::TestAC002_PydanticModelsMatchContract::test_evaluation_criterion_fields_match_contract`
      passes.
- [ ] The expected field set in the assertion includes `"layer"` alongside
      the existing `"name"`, `"description"`, `"weight"`.
- [ ] Optional but recommended: add an isinstance/Literal-membership assertion
      for `c.layer` matching the pattern already used for
      `GenerationTarget.layer` at `test_models.py:804-805` (consistency with
      the sibling contract test).
- [ ] Full `pytest --tb=no -q` returns zero failures (was 1958 passed / 1
      failed at end of TASK-AD14-B).
- [ ] No changes to `domain_config/models.py` — this task is a test-only
      contract refresh, not a model change.

## Diff sketch

```diff
--- domain_config/tests/test_models.py
+++ domain_config/tests/test_models.py
@@
     def test_evaluation_criterion_fields_match_contract(self):
-        """EvaluationCriterion: name(str), description(str), weight(float)."""
+        """EvaluationCriterion: name(str), description(str), weight(float),
+        layer(Literal['behaviour','knowledge','all'])."""
         c = EvaluationCriterion(
             name="crit_name", description="desc", weight=0.5
         )
         assert isinstance(c.name, str)
         assert isinstance(c.description, str)
         assert isinstance(c.weight, float)
+        assert isinstance(c.layer, str)
+        assert c.layer in ("behaviour", "knowledge", "all")
         assert set(EvaluationCriterion.model_fields.keys()) == {
-            "name", "description", "weight",
+            "name", "description", "weight", "layer",
         }
```

## Suggested execution

```bash
cd /Users/richardwoollcott/Projects/appmilla_github/agentic-dataset-factory
# Edit domain_config/tests/test_models.py per the diff above.

.venv/bin/python -m pytest \
  domain_config/tests/test_models.py::TestAC002_PydanticModelsMatchContract::test_evaluation_criterion_fields_match_contract \
  -v

# Then full suite to confirm 1959 passed / 0 failed:
.venv/bin/python -m pytest --tb=no -q
```

## Out of scope

- Any changes to `EvaluationCriterion` itself — the `layer` field is the
  intended public contract (referenced as authoritative by the
  `layer_routing` config and used by the Coach criteria-routing logic).
  This task is purely refreshing the test's frozen-snapshot expectations
  to match the current model.
- A wider audit of other contract tests in `TestAC002_PydanticModelsMatchContract`
  for similar drift. If the suite passes after this fix, no other drift
  exists today; if the resolver later admits a different DeepAgents/
  langchain combination that adds further fields, file a fresh follow-up.
- Any documentation update for `layer` semantics — already covered in
  `domain_config/models.py` docstrings and the goal-md parser.

## Implementation result (2026-04-29)

- Edited `domain_config/tests/test_models.py:812` per the brief's diff exactly: added
  `assert isinstance(c.layer, str)` and `assert c.layer in ("behaviour", "knowledge", "all")`
  before the `model_fields.keys()` set comparison, then added `"layer"` to the expected
  set. Updated docstring to mention the new field.
- Targeted run:
  `domain_config/tests/test_models.py::TestAC002_PydanticModelsMatchContract::test_evaluation_criterion_fields_match_contract`
  → **1 passed** in 0.05s.
- Full suite: `pytest --tb=no -q` → **1959 passed, 0 failed** in 14.87s. Closes the
  loop on TASK-AD14-B's acceptance criterion #4 ("if newly-visible failures surface,
  document or fix them"); the +1 vs TASK-AD14-B's 1958/1 final state is exactly this
  test flipping from FAIL to PASS, with no other movement.
- Ruff: `ruff check domain_config/tests/test_models.py` → all checks passed.
- No changes to `domain_config/models.py` (purely a test contract refresh).

## Notes

- TASK-AD14-B explicitly flagged this as a recommended follow-up under its
  acceptance criterion #4 ("If new failures surface ... document them").
  This task closes that loop.
- Marked `optional: true` and `priority: low` because the failure is benign
  for production code paths (the model itself is correct; only the snapshot
  test lags) — but it does prevent a clean green pytest, so worth picking
  up next time the test suite is touched.
