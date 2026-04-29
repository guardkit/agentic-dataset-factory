# ADR-ARCH-011: LangChain 1.x Portfolio Alignment + DeepAgents Pin

> Status: **Accepted** *(implemented under TASK-AD14-A)*
> Date: 2026-04-29
> Related: TASK-REV-AD14 (`/Users/richardwoollcott/Projects/appmilla_github/agentic-dataset-factory/.claude/reviews/TASK-REV-AD14-report.md`), Jarvis ADR-ARCH-010 Revision 2 (cross-repo precedent), GuardKit TASK-REV-FA04 + portfolio-python-pinning guide (cross-repo policy)

## Context

Jarvis FEAT-J004-702C stalled on autobuild for 33 minutes (2026-04-27) because of a `requires-python` mismatch on Python 3.14, compounded by open-floor `>=0.3` langchain ecosystem pins that let the resolver pick mixed 0.x / 1.x langchain pairs at install time. The cross-repo investigation (TASK-REV-FA04 in GuardKit) and Jarvis's own remediation (ADR-ARCH-010 Revision 2) established a portfolio policy:

1. `requires-python = ">=3.11"` — open upper bound.
2. LangChain ecosystem packages pinned to coherent 1.x with `<2` caps.
3. `deepagents>=0.5.3,<0.6` — exclusive upper cap to insulate against 0.6 breakage of preview features.
4. `pydantic>=2`.

This ADR applies that policy to agentic-dataset-factory. The empirical investigation is in [TASK-REV-AD14 report](`/Users/richardwoollcott/Projects/appmilla_github/agentic-dataset-factory/.claude/reviews/TASK-REV-AD14-report.md`).

### Pre-existing state (read directly from `pyproject.toml`, 2026-04-29)

```toml
requires-python = ">=3.11"  # already correct

dependencies = [
    "deepagents>=0.4.11",                # 0.x floor, no upper cap
    "langchain>=0.3",                    # 0.x floor, no upper cap
    "langchain-core>=0.3",               # 0.x floor, no upper cap
    "langchain-community>=0.3",          # 0.x floor, no upper cap
    "langchain-text-splitters>=0.3.0",   # 0.x floor, no upper cap
    "langchain-openai>=0.3",             # 0.x floor, no upper cap
    "langgraph>=0.2",                    # 0.x floor, no upper cap
    "pydantic>=2.0",                     # already correct
    ...
]
# (no explicit langchain-anthropic — pulled in transitively, used directly in source)
```

### What the resolver actually does today

A fresh `uv pip install -e ".[dev]"` on Python 3.14.2 against the existing pyproject resolves to:

| Package | Resolved | Note |
|---|---|---|
| `deepagents` | 0.5.4 | (pin allows 0.4.11+, resolver picks latest) |
| `langchain` | 1.2.15 | deepagents 0.5.4 transitively requires `<2,>=1.2.15` |
| `langchain-core` | 1.3.2 | langchain-openai 1.2.1 requires `<2,>=1.3.2` |
| `langchain-community` | 0.4.1 | community is on 0.4.x semver track, not 1.x |
| `langchain-text-splitters` | 1.1.2 | requires `langchain-core<2,>=1.2.31` |
| `langchain-openai` | 1.2.1 | 1.x |
| `langchain-anthropic` | 1.4.2 | transitive (deepagents 0.5.4 requires it) |
| `langgraph` | 1.1.10 | langchain 1.2.15 requires `<1.2,>=1.1.5` |
| `langgraph-checkpoint` | 4.0.3 | 1.x |
| `pydantic` | 2.13.3 | 2.x |

Pytest: 1869 passed, 90 pre-existing failures (all `pytest-asyncio` missing — pin-independent). Confirmed identical resolution with `--upgrade`. The resolved state is **already coherent 1.x**; the open-floor pins simply happen to land there because deepagents' transitive constraints lock the langchain stack to 1.x.

### The latent risk

The current pin shape works **by accident of transitive constraints**. If a future deepagents release relaxed its `langchain-core>=1.2.27` floor, or if a resolver choice changed (e.g. uv 1.0 picks differently), this project could non-deterministically land on 0.x langchain on a clean install. The fix is to encode the resolved state explicitly so the resolver cannot drift.

Additionally, when langchain 2.x ships, the open-floor pin shape will silently allow 2.x to be picked, which is exactly the failure mode that motivated Jarvis's `<2` caps.

## Decision

Adopt the Jarvis ADR-ARCH-010-rev2 portfolio recipe in this project, with one project-specific addition (the `langchain-anthropic` explicit dep) and one project-specific retention (the `langchain-text-splitters` pin):

```toml
[project]
requires-python = ">=3.11"  # unchanged

dependencies = [
    "anthropic>=0.40.0",
    "chromadb>=0.5",
    "deepagents>=0.5.3,<0.6",
    "langchain>=1.2,<2",
    "langchain-core>=1.3,<2",
    "langchain-community>=0.4,<1",       # community semver track is 0.4.x — not 1.x
    "langchain-text-splitters>=1.1,<2",
    "langchain-openai>=1.2,<2",
    "langchain-anthropic>=1.4,<2",       # NEW: was implicit-transitive, now explicit
    "langgraph>=1.1,<2",
    "pyyaml>=6.0",
    "pydantic>=2.0",
]
```

### Why explicit `langchain-anthropic`

`agents/coach.py:30` and `agents/player.py:30` import `from langchain_anthropic.middleware import AnthropicPromptCachingMiddleware` and use it unconditionally in the middleware stack. The current pyproject does not list `langchain-anthropic` — it's pulled in transitively (via `init_chat_model` in `agents/model_factory.py:18` and via deepagents 0.5.x). This is the same anti-pattern Jarvis ADR-rev2 fixed for `langchain` itself: when a runtime import is to a transitive dependency, the resolver has no constraint on which version is acceptable to *this project*. Making it explicit gives this project direct version control.

### Why retain `langchain-text-splitters`

Project-specific: `ingestion/chunker.py:23` uses `RecursiveCharacterTextSplitter`. Jarvis does not depend on text-splitters; the Jarvis pin set excludes it. Adding `langchain-text-splitters>=1.1,<2` keeps this project's runtime import explicitly constrained.

### Why `langchain-community` keeps a `<1` cap (not `<2`)

LangChain Community did not follow the rest of the langchain ecosystem's 1.x rename. The latest community release is 0.4.1, on a 0.4.x semver track. Its own deps allow `langchain-core<2,>=1.0.1`, so it cohabits with the 1.x langchain stack. Pin `>=0.4,<1` matches its semver track; this is a narrowing of the existing `>=0.3` open floor, not a divergence from the ecosystem-wide `<2` pattern.

### Why deepagents is `>=0.5.3,<0.6` (not `>=0.5.4`)

Aligns with Jarvis ADR-rev2 exact-floor pin. This project does not use AsyncSubAgent (the preview feature that motivates Jarvis's exact floor) — its API surface is the much narrower `FilesystemBackend` + `MemoryMiddleware` + `PatchToolCallsMiddleware` trio — so the AsyncSubAgent breakage risk does not apply here. Either `>=0.5.3,<0.6` or `>=0.5.4,<0.6` would work in practice. Recommendation: track Jarvis exactly for portfolio coherence. If a future deepagents 0.5.x release breaks the narrow API this project uses, ADR review point arrives at the same time as Jarvis's.

### Why `requires-python` is unchanged

`>=3.11` is already the portfolio canonical (forge, study-tutor, agentic-dataset-factory, specialist-agent — and now Jarvis post-rev2 — all match the LangChain DeepAgents template). Open upper bound aligns with the [portfolio-python-pinning guide](`/Users/richardwoollcott/Projects/appmilla_github/guardkit/docs/guides/portfolio-python-pinning.md`). No change needed.

## Verified Versions Table

Empirical resolution under the proposed pins, on `/usr/local/bin/python3.14` (CPython 3.14.2):

| Package | Floor | Cap | Resolved (today) | Notes |
|---|---|---|---|---|
| Python | `>=3.11` | (open) | 3.14.2 | Portfolio canonical; `requires-python` unchanged. |
| `deepagents` | `>=0.5.3` | `<0.6` | 0.5.4 | Matches Jarvis ADR-rev2 exact pattern. |
| `langchain` | `>=1.2` | `<2` | 1.2.15 | Explicit cap protects against 2.x drift. |
| `langchain-core` | `>=1.3` | `<2` | 1.3.2 | Pinned by langchain-openai's `>=1.3.2` floor. |
| `langchain-community` | `>=0.4` | `<1` | 0.4.1 | Community is on 0.4.x semver track. |
| `langchain-text-splitters` | `>=1.1` | `<2` | 1.1.2 | Project-specific (used in `ingestion/chunker.py`). |
| `langchain-openai` | `>=1.2` | `<2` | 1.2.1 | 1.x. |
| `langchain-anthropic` | `>=1.4` | `<2` | 1.4.2 | NEW explicit; was transitive. |
| `langgraph` | `>=1.1` | `<2` | 1.1.10 | 1.x. |
| `pydantic` | `>=2.0` | (open) | 2.13.3 | Unchanged. |
| `chromadb` | `>=0.5` | (open) | 1.5.8 | Unchanged. |

Tests: `1869 passed, 90 failed (pre-existing pytest-asyncio gap), 121 warnings in 4.94s`. The 90 failures are unrelated to the pin question — see TASK-REV-AD14 report §"Independent Finding".

## Source-Side Migration

**None.**

The deepagents API surface this project uses (`FilesystemBackend`, `MemoryMiddleware`, `PatchToolCallsMiddleware`) is identical between deepagents 0.4.11 (current pin floor) and 0.5.4 (resolver's current pick). Verified by direct import test on the freshly-resolved 0.5.4 venv. The agent factories (`agents/coach.py`, `agents/player.py`) bypass `create_deep_agent` and call `langchain.agents.create_agent` (1.x API) directly with langchain-1.x-shaped middleware — they were already 1.x-coded.

The pin alignment is a manifest-only change.

## Alternatives Considered

1. **"Stay on 0.x"** *(rejected)*. Empirically impossible: deepagents 0.4.11+ already requires `langchain-core<2,>=1.2.27` and `langchain<2,>=1.2.15` (verified PyPI metadata). To force 0.x langchain we'd have to downgrade deepagents to a pre-0.4.11 release that hasn't been verified for Python 3.14 compatibility. Branch B in the task brief was framed as the conservative choice, but it's actually a regression and likely a non-resolvable pin set.

2. **Use `>=0.5.4,<0.6` for deepagents** *(plausible alternative)*. Matches what the resolver currently picks. Loses portfolio coherence with Jarvis (which pins `>=0.5.3`). Recommendation: take the Jarvis pin for portfolio consistency; the practical difference is one patch release and no behavioural change for this project's narrow API surface.

3. **Pin every transitive dep explicitly** *(rejected)*. Over-engineering. The `<2` ecosystem caps + explicit declaration of every direct runtime import is the right granularity. Lockfile (`uv.lock`) handles transitive reproducibility.

4. **Drop `langchain-community` entirely** *(rejected)*. Need to re-survey usage; community modules may be used in `synthesis/` or `ingestion/`. Out of scope for this ADR — file as a separate hygiene task if community is genuinely unused at runtime.

## Consequences

- Portfolio coherence: this project tracks Jarvis ADR-ARCH-010-rev2 exactly. A maintainer touching pins in either repo can use the other as cross-reference.
- `langchain-anthropic` becomes an explicit, version-controlled dep.
- Future langchain 2.x ship will not silently break this project's installs. The `<2` caps surface the upgrade as an explicit decision (review point: when langchain 2.x ships, file ADR-ARCH-XXX rebase analogous to Jarvis ADR-ARCH-010-rev2).
- Future deepagents 0.6 ship will not silently break this project. Same review point as Jarvis (their ADR-ARCH-025 governs the 0.6 upgrade).
- No source-side change. No test rewrites. No behaviour change.
- The `uv.lock` will need regenerating after the pin diff lands. `uv sync` or `uv lock` after `pyproject.toml` edit.

## Implementation Pointer

Pin diff lives in [TASK-REV-AD14 report §"Recommended Pin Diff"](`/Users/richardwoollcott/Projects/appmilla_github/agentic-dataset-factory/.claude/reviews/TASK-REV-AD14-report.md#recommended-pin-diff`).

Suggested implementation tasks:

| Task | Mode | Work |
|---|---|---|
| TASK-AD14-A | direct | Apply pin diff. Verify `uv pip install -e ".[dev]"` resolves cleanly. Confirm pytest still at 1869/1959 (90 pre-existing async failures). Regenerate `uv.lock`. Mark this ADR Accepted. |
| TASK-AD14-B | direct | (Optional, separate) Add `pytest-asyncio>=0.24,<1` to `[dev]` extra. Expect 1959/1959 — or surface previously-masked failures. |
| TASK-AD14-C | direct | (Optional) Add one-line CLAUDE.md cross-reference to portfolio-pinning guide. |

A and C are pin-alignment work; B is hygiene that the empirical pytest run happened to surface. They are independent.

## Forward Review

When deepagents 0.6 ships (Jarvis ADR-ARCH-025 review point), revisit:

1. Does this project's narrow API surface (`FilesystemBackend`, `MemoryMiddleware`, `PatchToolCallsMiddleware`) survive the 0.6 upgrade?
2. Is langchain 2.x stable enough to rebase the `<2` caps?
3. Does `langchain-community` still hold on its 0.4.x semver track? (If it migrates to 1.x, update the cap.)
4. Is `pytest-asyncio` still the right async-test plugin? (Or has the ecosystem moved to anyio's pytest plugin?)

## Provenance

- TASK-REV-AD14 empirical evidence (this repo, `.claude/reviews/TASK-REV-AD14-report.md`).
- Jarvis ADR-ARCH-010 Revision 2 (read-only cross-repo reference).
- GuardKit TASK-REV-FA04 root-cause review (read-only cross-repo reference).
- GuardKit portfolio-python-pinning guide (read-only cross-repo policy reference).
- PyPI metadata verified live for `deepagents` (versions 0.4.11, 0.4.12, 0.5.4) and `langchain-text-splitters` (latest 1.1.2).
- Source code verified at agentic-dataset-factory HEAD at the time of the empirical run (.venv rebuilt during the review per AC #1).
