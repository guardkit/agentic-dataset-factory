# Implementation Guide — LangChain 1.x Portfolio Alignment (FEAT-AD14)

**Origin:** TASK-REV-AD14 / ADR-ARCH-011 (Proposed)
**Scope:** Manifest-only changes to `pyproject.toml`, plus optional ADR flip + CLAUDE.md cross-reference + dev-extra hygiene fix.
**Total effort:** ~30 minutes (cumulative across all three subtasks).

## Why this feature exists

Empirical investigation in [TASK-REV-AD14](`/Users/richardwoollcott/Projects/appmilla_github/agentic-dataset-factory/.claude/reviews/TASK-REV-AD14-report.md`) verified that:

1. The current open-floor `>=0.3` langchain pins **already drift to coherent 1.x** every fresh install (deepagents transitive constraints lock the stack to 1.x).
2. The deepagents API surface this project uses is **identical between 0.4.11 and 0.5.4** — zero source-side migration.
3. The agent factories already call `langchain.agents.create_agent` (1.x API) directly with langchain-1.x-shaped middleware imports.
4. The Jarvis ADR-ARCH-010-rev2 portfolio recipe (`<2` caps, `deepagents>=0.5.3,<0.6`, `requires-python = ">=3.11"`) applies cleanly to this project.

The pin diff is a manifest-only codification of the resolved state, plus `<2` caps so the resolver can't drift to 2.x langchain on a future ship.

## Subtask map

| ID | Title | Wave | Mode | Effort | Status |
|---|---|---|---|---|---|
| TASK-AD14-A | Apply pin diff + flip ADR to Accepted | 1 | direct | ~15 min | backlog |
| TASK-AD14-C | CLAUDE.md cross-reference (optional) | 1 | direct | ~5 min | backlog |
| TASK-AD14-B | pytest-asyncio dev-extra hygiene fix (optional) | 2 | direct | ~10 min | backlog |

All subtasks are `direct` mode (no agent loop). The whole feature is a sequence of small manifest edits + test verification.

## Wave breakdown

### Wave 1 — Parallel-safe (different files)

```
TASK-AD14-A   (pyproject.toml [project].dependencies)
TASK-AD14-C   (.claude/CLAUDE.md)              ← optional, can run in parallel
```

Both edit different files; no merge conflict risk.

### Wave 2 — Sequential after Wave 1

```
TASK-AD14-B   (pyproject.toml [project.optional-dependencies].dev)   ← optional, sequential after A
```

Sequenced after Wave 1 because both A and B edit `pyproject.toml`. They could be combined into a single commit if preferred.

## Data flow

This feature is purely declarative — no runtime data flow changes. The only "flow" is the resolver's choice during install:

```text
Before:                                      After:
─────────────────────────────────────       ─────────────────────────────────────
pyproject.toml (open floor >=0.3)            pyproject.toml (coherent 1.x, <2 caps)
       │                                            │
       ▼                                            ▼
uv resolver                                  uv resolver
       │                                            │
       ▼                                            ▼
deepagents transitive constraints lock        Pin shape itself locks the stack
the stack to 1.x (accidental coherence)      to 1.x (explicit coherence)
       │                                            │
       ▼                                            ▼
Resolved 1.x stack                           Resolved 1.x stack
                                             (identical to "Before" — no functional
                                              change; just no longer accidental)
```

## Execution order

Recommended sequence:

```bash
# Wave 1 — TASK-AD14-A (mandatory)
# Edit pyproject.toml per the diff in tasks/backlog/langchain-1x-portfolio-alignment/TASK-AD14-A-apply-pin-diff.md
uv pip install --python .venv/bin/python -e ".[dev]"
uv lock
.venv/bin/python -m pytest --tb=no -q  # expect 1869 passed, 90 failed (async)

# Edit ADR-ARCH-011: Status: Proposed → Status: Accepted

# Wave 1 — TASK-AD14-C (optional, parallel-safe with A)
# Edit .claude/CLAUDE.md per the diff in TASK-AD14-C-claudemd-pointer.md

git add pyproject.toml uv.lock docs/architecture/decisions/ADR-ARCH-011-langchain-1x-portfolio-alignment.md .claude/CLAUDE.md
git commit -m "chore(deps): align langchain ecosystem to coherent 1.x with <2 caps (ADR-ARCH-011)"

# Wave 2 — TASK-AD14-B (optional, sequential after A)
# Edit pyproject.toml [dev] extra per the diff in TASK-AD14-B-add-pytest-asyncio.md
uv pip install --python .venv/bin/python -e ".[dev]"
uv lock
.venv/bin/python -m pytest --tb=no -q  # expect 1959 passed (or surface newly-visible failures)

git add pyproject.toml uv.lock
git commit -m "chore(test): add pytest-asyncio to dev extra (closes 90 async failures)"
```

## Verification checklist

After Wave 1:
- [ ] `uv pip install -e ".[dev]"` resolves cleanly on Python 3.14 — no resolver complaints.
- [ ] Resolved versions match [TASK-REV-AD14 report §"Resolved Versions"](`/Users/richardwoollcott/Projects/appmilla_github/agentic-dataset-factory/.claude/reviews/TASK-REV-AD14-report.md#resolved-versions-target-state-after-the-diff`).
- [ ] `pytest` reports 1869 passed, 90 failed — same as before. The pin diff is functionally invisible.
- [ ] ADR-ARCH-011 status: Accepted, dated.
- [ ] (Optional) CLAUDE.md Technology Stack references portfolio-pinning guide.

After Wave 2 (if executed):
- [ ] `pytest` reports 1959 passed (or known set of *newly-visible* failures, documented).
- [ ] No regression in the 1869 previously-passing tests.

## Risks and mitigations

| Risk | Likelihood | Mitigation |
|---|---|---|
| `uv pip install` fails with the new pins | Very low — empirically verified during TASK-REV-AD14. | Fall back to the rolled-back pyproject.toml; investigate transitive constraint changes. |
| New test failures surface after Wave 2 (previously masked by async-skip) | Medium — likely some pre-existing logic bugs in async tests. | TASK-AD14-B's AC explicitly requires documenting any newly-visible failures rather than silently leaving them. File follow-up triage if any surface. |
| `langchain-community` 1.x ships and our `<1` cap blocks it | Low — community has been on 0.4.x semver track for a while. | At that point, file an ADR-ARCH-XXX rebase analogous to Jarvis ADR-ARCH-010-rev2. |
| `langchain` 2.x ships sooner than expected | Low — 1.x just shipped recently. | The `<2` cap is exactly the protection here. Surface as an explicit rebase decision when 2.x ships. |
| Surprise breakage from the implicit `langchain-anthropic` becoming explicit | Very low — the package is already installed and used. | Verify the import in `agents/coach.py` and `agents/player.py` still works post-install. |

## Cross-references

- [Review report](`/Users/richardwoollcott/Projects/appmilla_github/agentic-dataset-factory/.claude/reviews/TASK-REV-AD14-report.md`) — full empirical evidence, decision rationale, branch comparison.
- [ADR-ARCH-011](`/Users/richardwoollcott/Projects/appmilla_github/agentic-dataset-factory/docs/architecture/decisions/ADR-ARCH-011-langchain-1x-portfolio-alignment.md`) — decision record with verified-versions table.
- [Jarvis ADR-ARCH-010 Revision 2](`/Users/richardwoollcott/Projects/appmilla_github/jarvis/docs/architecture/decisions/ADR-ARCH-010-python-312-and-deepagents-pin.md`) — cross-repo precedent for the recipe.
- [GuardKit TASK-REV-FA04 report](`/Users/richardwoollcott/Projects/appmilla_github/guardkit/.claude/reviews/TASK-REV-FA04-report.md`) — root-cause analysis that motivated the portfolio recipe.
- [Portfolio-pinning guide](`/Users/richardwoollcott/Projects/appmilla_github/guardkit/docs/guides/portfolio-python-pinning.md`) — `requires-python` policy.
