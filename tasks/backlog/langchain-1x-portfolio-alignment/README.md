# LangChain 1.x Portfolio Alignment (FEAT-AD14)

> Implementation feature spawned from TASK-REV-AD14 / ADR-ARCH-011.

## Problem

`pyproject.toml` carries open-floor `>=0.3` langchain ecosystem pins that were correct when the project started but no longer reflect the resolved state. A fresh `uv pip install` on Python 3.14 today resolves to coherent langchain 1.x (deepagents 0.5.4 + langchain 1.2.15 + langchain-core 1.3.2 + langgraph 1.1.10) **because of transitive constraints from deepagents**, not because the pin shape mandates it. If a future deepagents release relaxed those constraints, or if the resolver chose differently, this project could non-deterministically land on 0.x langchain. Additionally, when langchain 2.x ships, the open-floor pins will silently allow it — exactly the failure mode that motivated the Jarvis FEAT-J004-702C portfolio recipe (`<2` caps).

The brief feared a deepagents-0.4.x-vs-langchain-1.x conflict requiring a coordinated bump. The empirical investigation falsified the conflict — deepagents 0.4.11+ already mandates langchain 1.x — and revealed the actual issue is just pin-shape hygiene with zero source-side migration cost.

## Solution

Apply the Jarvis ADR-ARCH-010-rev2 portfolio recipe to this project:

| Pin | Before | After |
|---|---|---|
| `requires-python` | `>=3.11` | `>=3.11` *(unchanged — already correct)* |
| `deepagents` | `>=0.4.11` | `>=0.5.3,<0.6` *(Jarvis-aligned)* |
| `langchain` | `>=0.3` | `>=1.2,<2` |
| `langchain-core` | `>=0.3` | `>=1.3,<2` |
| `langchain-community` | `>=0.3` | `>=0.4,<1` *(community on 0.4.x semver track)* |
| `langchain-text-splitters` | `>=0.3.0` | `>=1.1,<2` |
| `langchain-openai` | `>=0.3` | `>=1.2,<2` |
| `langchain-anthropic` | *(implicit-transitive)* | `>=1.4,<2` *(NEW explicit dep)* |
| `langgraph` | `>=0.2` | `>=1.1,<2` |

Plus three optional follow-ups: ADR flip to Accepted, CLAUDE.md cross-reference, and a separate hygiene fix for the 90 pre-existing pytest-asyncio failures (independent of this feature, but surfaced by the empirical run).

## Subtasks

| File | Wave | Mode | Required |
|---|---|---|---|
| [TASK-AD14-A](TASK-AD14-A-apply-pin-diff.md) — Apply pin diff + flip ADR | 1 | direct | ✅ Yes |
| [TASK-AD14-C](TASK-AD14-C-claudemd-pointer.md) — CLAUDE.md cross-reference | 1 | direct | Optional |
| [TASK-AD14-B](TASK-AD14-B-add-pytest-asyncio.md) — pytest-asyncio dev hygiene | 2 | direct | Optional |

## Sequence

```
Wave 1:  TASK-AD14-A  ─┬─ commit  ┐
                       │          │
         TASK-AD14-C  ─┘          │  ← optional, parallel-safe
                                  │
Wave 2:  TASK-AD14-B  ─── commit  ┘  ← optional, sequential (also edits pyproject.toml)
```

See [IMPLEMENTATION-GUIDE.md](IMPLEMENTATION-GUIDE.md) for full execution recipe and verification checklist.

## Done when

- [ ] `pyproject.toml` matches the post-diff shape in TASK-AD14-A.
- [ ] `uv pip install -e ".[dev]"` resolves cleanly on Python 3.14.
- [ ] `pytest --tb=no -q` reports 1869 passed (post-A) or 1959 passed (post-B).
- [ ] ADR-ARCH-011 status: `Accepted`.
- [ ] *(Optional)* `.claude/CLAUDE.md` Technology Stack references portfolio-pinning guide.

## References

- [TASK-REV-AD14 review report](../../../.claude/reviews/TASK-REV-AD14-report.md) — empirical evidence + decision rationale.
- [ADR-ARCH-011](../../../docs/architecture/decisions/ADR-ARCH-011-langchain-1x-portfolio-alignment.md) — decision record.
- Cross-repo: [Jarvis ADR-ARCH-010 Revision 2](`/Users/richardwoollcott/Projects/appmilla_github/jarvis/docs/architecture/decisions/ADR-ARCH-010-python-312-and-deepagents-pin.md`) — precedent.
- Cross-repo: [GuardKit portfolio-python-pinning guide](`/Users/richardwoollcott/Projects/appmilla_github/guardkit/docs/guides/portfolio-python-pinning.md`) — policy.
