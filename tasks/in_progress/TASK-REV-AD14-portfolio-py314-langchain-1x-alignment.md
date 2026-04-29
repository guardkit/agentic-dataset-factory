---
id: TASK-REV-AD14
title: Verify Python 3.14 + langchain-1.x portfolio alignment (per Jarvis FEAT-J004-702C precedent)
status: review_complete
task_type: review
review_mode: diagnostic
review_depth: standard
created: 2026-04-28T00:00:00Z
updated: 2026-04-29T00:00:00Z
previous_state: backlog
state_transition_reason: "Automatic transition for task-review execution"
priority: medium
tags: [portfolio-alignment, langchain-1x, python-pinning, FA04-followup]
complexity: 0
test_results:
  status: pending
  coverage: null
  last_run: null
related_external_reviews:
  - "guardkit/.claude/reviews/TASK-REV-FA04-report.md"  # langchain trapdoor diagnosis (closed)
  - "jarvis/docs/architecture/decisions/ADR-ARCH-010-python-312-and-deepagents-pin.md"  # rev2 pin recipe
  - "guardkit/docs/guides/portfolio-python-pinning.md"  # portfolio policy
review_results:
  mode: diagnostic
  depth: standard
  decision: implement
  branch_chosen: A
  source_migration_required: false
  report_path: .claude/reviews/TASK-REV-AD14-report.md
  adr_path: docs/architecture/decisions/ADR-ARCH-011-langchain-1x-portfolio-alignment.md
  empirical_evidence:
    pytest_current_pins: /tmp/adf-3.14-current-pytest.log    # 1869 passed, 90 failed
    pytest_upgraded:     /tmp/adf-3.14-upgraded-pytest.log    # 1869 passed, 90 failed
    pytest_baseline_existing_venv: /tmp/adf-3.14-baseline-existing-venv-pytest.log
  completed_at: 2026-04-29T00:00:00Z
  feature_id: FEAT-AD14
  feature_slug: langchain-1x-portfolio-alignment
  implementation_tasks:
    - id: TASK-AD14-A
      path: tasks/backlog/langchain-1x-portfolio-alignment/TASK-AD14-A-apply-pin-diff.md
      wave: 1
      required: true
    - id: TASK-AD14-C
      path: tasks/backlog/langchain-1x-portfolio-alignment/TASK-AD14-C-claudemd-pointer.md
      wave: 1
      required: false
    - id: TASK-AD14-B
      path: tasks/backlog/langchain-1x-portfolio-alignment/TASK-AD14-B-add-pytest-asyncio.md
      wave: 2
      required: false
  independent_finding:
    description: "90 pre-existing pytest failures from missing pytest-asyncio dev dependency (pin-independent)"
    follow_up_task: TASK-AD14-B
---

# Verify Python 3.14 + langchain-1.x portfolio alignment (per Jarvis FEAT-J004-702C precedent)

## Context

Jarvis hit a 33-min autobuild stall on FEAT-J004-702C run 1 (2026-04-27) caused by a stale Python pin compounded by langchain ecosystem 0.x→1.x version skew when the resolver was given open-floor `>=0.3` pins. Investigation: [`guardkit/.claude/reviews/TASK-REV-FA04-report.md`](../../../guardkit/.claude/reviews/TASK-REV-FA04-report.md). Remediation in Jarvis: [`jarvis/docs/architecture/decisions/ADR-ARCH-010-python-312-and-deepagents-pin.md`](../../../jarvis/docs/architecture/decisions/ADR-ARCH-010-python-312-and-deepagents-pin.md) Revision 2 — `requires-python = ">=3.11"` + langchain ecosystem coherent 1.x with `<2` caps. Empirical Jarvis run 2 validated the recipe end-to-end.

This review applies the recipe to agentic-dataset-factory. **Priority is medium** because agentic-dataset-factory is not on the DDD South West demo critical path (jarvis/study-tutor/forge are). However, the project is the **most-stale** in the portfolio — ALL its langchain pins are still on 0.x — so it's the most likely to break on the next clean machine setup, and aligning it now keeps the portfolio coherent.

## Current pin state (read directly from `pyproject.toml` — pre-review snapshot)

```toml
requires-python = ">=3.11"

dependencies = [
    "deepagents>=0.4.11",                # 0.x — Jarvis pinned 0.5.3,<0.6
    "langchain>=0.3",                    # 0.x ← all 0.x — highest mismatch risk
    "langchain-core>=0.3",               # 0.x
    "langchain-community>=0.3",          # 0.x
    "langchain-text-splitters>=0.3.0",   # 0.x — agentic-dataset-factory-specific
    "langchain-openai>=0.3",             # 0.x
    "langgraph>=0.2",                    # 0.x
    "pydantic>=2.0",
    ...
]
```

**Highest-risk shape in the portfolio**. Every langchain pin is on 0.x. With `--upgrade`, the resolver will move to coherent 1.x where each is published, but `deepagents>=0.4.11` is locked to a 0.4.x family that may not have a langchain-1.x-compatible release. Specifically: **deepagents 0.4.11 likely requires langchain<1** internally — Jarvis upgraded to deepagents 0.5.3 to get langchain-1.x compatibility. So this project may need to bump deepagents AND the langchain set together, OR stay on 0.x for both.

The right answer depends on what deepagents 0.4.x supports. The review needs to investigate.

## Goal

Apply the FA04 recipe to agentic-dataset-factory, but with a critical decision branch upfront:

**Branch A — bump deepagents to 0.5.x and rebase langchain to 1.x** (matches Jarvis):
- Requires verifying agentic-dataset-factory's source code is compatible with deepagents 0.5.x's API
- May require source-side migration work
- Aligns with the rest of the portfolio
- Best long-term answer

**Branch B — stay on deepagents 0.4.x and pin langchain ecosystem to coherent 0.x with caps** (preserves current API):
- Avoid source-side migration
- Adds `<1` caps to lock the ecosystem at 0.x
- Maintains divergence from the rest of the portfolio
- Acceptable short-term answer; defer the 0.5.x migration

The review must produce a recommendation with rationale and the corresponding pin diff for whichever branch is chosen.

**No GuardKit changes; no Jarvis changes — fixes live in this repo.**

## Source artefacts

- This repo: `pyproject.toml`, `uv.lock` (if present), `tests/`, `docs/architecture/decisions/`, `src/agentic_dataset_factory/**` (for deepagents API usage check)
- Empirical Jarvis run-2 evidence: `jarvis/docs/history/autobuild-FEAT-J004-702C-run-2-history.md`
- Jarvis ADR rev2: `jarvis/docs/architecture/decisions/ADR-ARCH-010-python-312-and-deepagents-pin.md`
- Portfolio guide: `guardkit/docs/guides/portfolio-python-pinning.md`
- deepagents PyPI metadata for 0.4.x vs 0.5.x: check `requires-python` and langchain compatibility for both lines.

## Investigation scope

1. **Empirical 3.14 install + test run** (current state, no upgrades):
   ```bash
   cd /Users/richardwoollcott/Projects/appmilla_github/agentic-dataset-factory
   mv .python-version .python-version.bak 2>/dev/null
   rm -rf .venv
   uv venv --python 3.14 .venv
   uv pip install --python .venv/bin/python -e ".[dev]"  # NO --upgrade — see what current pins resolve to
   .venv/bin/python -m pytest --tb=no -q | tee /tmp/adf-3.14-current-pytest.log
   mv .python-version.bak .python-version 2>/dev/null
   ```
   Expected: probably works today on a stale lockfile, may fail on a fresh resolution.

2. **Empirical 3.14 + `--upgrade` install + test run** (latest ecosystem):
   ```bash
   uv pip install --upgrade --python .venv/bin/python -e ".[dev]"
   .venv/bin/python -m pytest --tb=no -q | tee /tmp/adf-3.14-upgraded-pytest.log
   ```
   Expected: surfaces the deepagents-0.4.x-vs-langchain-1.x conflict if it exists.

3. **deepagents 0.4.x → 0.5.x migration check**:
   - Read PyPI metadata: does deepagents 0.5.3 still support whatever agentic-dataset-factory uses?
   - Grep agentic-dataset-factory's source for `import deepagents` / `from deepagents` to identify the API surface used.
   - Check deepagents CHANGELOG (or release notes) for breaking changes between 0.4.x and 0.5.x.

4. **Branch decision**:
   - If deepagents 0.5.x preserves the agentic-dataset-factory-relevant API: recommend Branch A (rebase to 1.x langchain + 0.5.x deepagents).
   - If deepagents 0.5.x introduces breaking changes that would require non-trivial source migration: recommend Branch B (cap at 0.x for now).

5. **agentic-dataset-factory-specific pin**: `langchain-text-splitters>=0.3.0` is project-specific. Check if it has a 1.x release compatible with langchain-core 1.x.

6. **Failure categorisation** per FA04 playbook for whichever branch the review picks.

7. **ADR**: file as next available `ADR-ARCH-XXX` (after `ADR-ARCH-010-overnight-run-resilience`, so `ADR-ARCH-011` if numbering is sequential — confirm by listing `docs/architecture/decisions/`). Reference Jarvis ADR-ARCH-010-rev2 as the cross-repo precedent.

## Acceptance criteria

- [ ] Both empirical runs (current pins / `--upgrade`) captured with their pytest outputs.
- [ ] deepagents 0.4.x vs 0.5.x compatibility delta documented (which APIs agentic-dataset-factory uses; which broke).
- [ ] Branch recommendation (A or B) with rationale.
- [ ] Resolved versions table for the recommended branch.
- [ ] Pin update recommendation: explicit diff against current `pyproject.toml`.
- [ ] If Branch A: identification of any source-side migration work (filed as separate task spec, not implemented here).
- [ ] `langchain-text-splitters` pin recommendation.
- [ ] New ADR drafted with rationale, verified-versions table, cross-repo precedent reference, branch decision.
- [ ] Recommendation on whether agentic-dataset-factory needs portfolio-pinning guide reference in its `CLAUDE.md`.
- [ ] No proposed changes to GuardKit or Jarvis — fixes live in this repo.
- [ ] Report saved to `.claude/reviews/TASK-REV-AD14-report.md`.

## Out of scope

- Implementing the pin updates or any source-side deepagents 0.5.x migration — follow-up tasks.
- Investigating the orchestrator complexity/timeout family (closed by 9D13 + CEIL/WALL/FRSH/MAXT/FLOR).
- Other portfolio repos — each has its own review task in its own `tasks/backlog/`.

## Suggested workflow

```bash
/task-review TASK-REV-AD14 --mode=diagnostic
# Run both empirical 3.14 installs (current / --upgrade) + pytest.
# Investigate deepagents 0.4 → 0.5 migration cost.
# Pick Branch A or B with rationale.
# Draft pin diff + identify any source-side migration work.
# Surface the [A]ccept / [I]mplement / [R]evise checkpoint.
```

## References

- Cross-repo (read-only): `guardkit/.claude/reviews/TASK-REV-FA04-report.md`
- Cross-repo (read-only): `jarvis/docs/architecture/decisions/ADR-ARCH-010-python-312-and-deepagents-pin.md` Revision 2
- Cross-repo (read-only): `guardkit/docs/guides/portfolio-python-pinning.md`
- This repo: `pyproject.toml`, `tests/`, `docs/architecture/decisions/`, `src/agentic_dataset_factory/**`
