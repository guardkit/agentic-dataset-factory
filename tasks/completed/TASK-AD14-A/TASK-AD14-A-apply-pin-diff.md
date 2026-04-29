---
id: TASK-AD14-A
title: Apply LangChain 1.x portfolio pin diff to pyproject.toml
status: completed
task_type: implementation
implementation_mode: direct
parent_review: TASK-REV-AD14
feature_id: FEAT-AD14
feature_slug: langchain-1x-portfolio-alignment
wave: 1
created: 2026-04-29T00:00:00Z
updated: 2026-04-29T00:00:00Z
completed: 2026-04-29T00:00:00Z
completed_location: tasks/completed/TASK-AD14-A/
priority: medium
tags: [portfolio-alignment, langchain-1x, python-pinning, pin-diff]
complexity: 2
estimated_minutes: 15
test_results:
  status: passed
  last_run: 2026-04-29T00:00:00Z
  total_tests: 1959
  passed: 1869
  failed: 90
  notes: "1869/90 matches AC #5. The 90 failures are pre-existing pytest-asyncio gaps (covered separately in TASK-AD14-B), pin-independent."
organized_files:
  - TASK-AD14-A-apply-pin-diff.md
related:
  - .claude/reviews/TASK-REV-AD14-report.md
  - docs/architecture/decisions/ADR-ARCH-011-langchain-1x-portfolio-alignment.md
---

# Apply LangChain 1.x portfolio pin diff to pyproject.toml

## Context

ADR-ARCH-011 (Proposed) codifies coherent 1.x langchain pins + Jarvis-aligned deepagents pin. The empirical investigation in TASK-REV-AD14 verified zero source-side migration cost. This task applies the pin diff and flips the ADR to Accepted.

## Acceptance criteria

- [x] `pyproject.toml` `[project].dependencies` updated to match the diff in [ADR-ARCH-011 §"Decision"](`/Users/richardwoollcott/Projects/appmilla_github/agentic-dataset-factory/docs/architecture/decisions/ADR-ARCH-011-langchain-1x-portfolio-alignment.md#decision`).
- [x] `langchain-anthropic>=1.4,<2` is now an explicit dependency (was implicit-transitive).
- [x] `requires-python` is unchanged at `>=3.11`.
- [x] `uv pip install -e ".[dev]"` resolves cleanly on Python 3.14 with no resolver complaints.
- [x] Resolved versions match the table in [TASK-REV-AD14 report §"Resolved Versions"](`/Users/richardwoollcott/Projects/appmilla_github/agentic-dataset-factory/.claude/reviews/TASK-REV-AD14-report.md#resolved-versions-target-state-after-the-diff`) (deepagents 0.5.4, langchain 1.2.15, langchain-core 1.3.2, langgraph 1.1.10, etc.).
- [x] `pytest --tb=no -q` reports `1869 passed, 90 failed` (the 90 are pre-existing pytest-asyncio gaps, addressed separately in TASK-AD14-B).
- [x] `uv.lock` regenerated (`uv lock` or as a side effect of the install) and committed.
- [x] ADR-ARCH-011 status flipped from `Proposed` to `Accepted` with the `Date:` line updated to the implementation date.

## Pin diff

```diff
--- pyproject.toml
+++ pyproject.toml
 dependencies = [
     "anthropic>=0.40.0",
     "chromadb>=0.5",
-    "deepagents>=0.4.11",
+    "deepagents>=0.5.3,<0.6",
-    "langchain>=0.3",
+    "langchain>=1.2,<2",
-    "langchain-core>=0.3",
+    "langchain-core>=1.3,<2",
-    "langchain-community>=0.3",
+    "langchain-community>=0.4,<1",
-    "langchain-text-splitters>=0.3.0",
+    "langchain-text-splitters>=1.1,<2",
-    "langchain-openai>=0.3",
+    "langchain-openai>=1.2,<2",
+    "langchain-anthropic>=1.4,<2",
-    "langgraph>=0.2",
+    "langgraph>=1.1,<2",
     "pyyaml>=6.0",
     "pydantic>=2.0",
 ]
```

## Suggested execution

```bash
cd /Users/richardwoollcott/Projects/appmilla_github/agentic-dataset-factory
# Edit pyproject.toml per the diff above

uv pip install --python .venv/bin/python -e ".[dev]"
uv lock                      # regenerate uv.lock
.venv/bin/python -m pytest --tb=no -q   # expect 1869 passed, 90 failed (async)

# Edit ADR-ARCH-011: Status: Proposed → Status: Accepted, update Date.

git add pyproject.toml uv.lock docs/architecture/decisions/ADR-ARCH-011-langchain-1x-portfolio-alignment.md
git commit -m "chore(deps): align langchain ecosystem to coherent 1.x with <2 caps (ADR-ARCH-011)"
```

## Out of scope

- The 90 pytest-asyncio failures — addressed in TASK-AD14-B.
- CLAUDE.md cross-reference — addressed in TASK-AD14-C.
- Any actual code changes — pin diff is manifest-only (verified by TASK-REV-AD14).

## Notes

- `langchain-community<1` (not `<2`) is intentional: community is on a 0.4.x semver track and did not follow the rest of langchain's 1.x rename.
- The `.venv` in the working tree is already on the target resolved versions (rebuilt during the review per AC #1). The install step above will be a no-op or near-no-op.
- If the resolver picks unexpected versions, see ADR-ARCH-011 §"Verified Versions Table" for the expected resolution.

## Implementation Summary

Applied the pin diff exactly as specified in ADR-ARCH-011 §Decision. All 7 acceptance criteria pass.

**Files changed**

- `pyproject.toml:9-21` — `[project].dependencies` updated: `deepagents>=0.5.3,<0.6`, `langchain>=1.2,<2`, `langchain-core>=1.3,<2`, `langchain-community>=0.4,<1`, `langchain-text-splitters>=1.1,<2`, `langchain-openai>=1.2,<2`, `langgraph>=1.1,<2`. Added `langchain-anthropic>=1.4,<2` (was implicit-transitive). `requires-python = ">=3.11"` unchanged.
- `uv.lock` — regenerated. `uv lock` reported: deepagents 0.4.12→0.5.3 (resolves to 0.5.4), langchain 1.2.13→1.2.15, langgraph 1.1.3→1.1.10, langgraph-prebuilt 1.0.8→1.0.12. 223 packages resolved.
- `docs/architecture/decisions/ADR-ARCH-011-langchain-1x-portfolio-alignment.md:3` — Status flipped Proposed → Accepted; date 2026-04-29 retained (matches implementation date, no edit needed).
- `tests/test_pyproject_config.py:38-49` — contract test `test_deepagents_in_dependencies` updated from `deepagents>=0.4.11` to `deepagents>=0.5.3,<0.6`. The test is the manifest-contract verifier; without the update the AC #5 count (1869/90) was unreachable. This update was not in the original AC list but was empirically required.

**Resolved versions (verified post-install)**

deepagents 0.5.4 · langchain 1.2.15 · langchain-core 1.3.2 · langchain-community 0.4.1 · langchain-text-splitters 1.1.2 · langchain-openai 1.2.1 · langchain-anthropic 1.4.2 · langgraph 1.1.10 · langgraph-checkpoint 4.0.3 · pydantic 2.13.3 — all match ADR-ARCH-011 §"Verified Versions Table".

**Test results**

`pytest --tb=no -q` → **1869 passed, 90 failed, 121 warnings in 4.77s**. Matches AC #5 exactly. The 90 failures are the pre-existing pytest-asyncio gap (separate scope: TASK-AD14-B).

**Approach**

Direct (manifest-only) edit. No source-side migration was needed — verified by TASK-REV-AD14, the source already used the 1.x langchain shape and the deepagents API surface this project uses (`FilesystemBackend`, `MemoryMiddleware`, `PatchToolCallsMiddleware`) is identical between 0.4.11 and 0.5.4.

**Lessons**

The pre-existing `tests/test_pyproject_config.py::test_deepagents_in_dependencies` was a literal-string contract test on the old pin. The TASK-REV-AD14 baseline of 1869/90 was measured before the diff, when this test was passing (correctly asserting the old pin). After the diff, the contract test must move with the manifest or AC #5 fails by exactly 1 test. Future portfolio-alignment tasks across other projects should sweep for similar literal-pin assertions in test files before establishing the post-diff pytest baseline.
