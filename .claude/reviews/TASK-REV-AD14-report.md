# Review Report: TASK-REV-AD14

**Mode:** Diagnostic (review)
**Depth:** Standard
**Subject:** Apply Jarvis FEAT-J004-702C / ADR-ARCH-010-rev2 portfolio pin recipe to agentic-dataset-factory
**Date:** 2026-04-29
**Cross-repo precedent:** [`guardkit/.claude/reviews/TASK-REV-FA04-report.md`](../../../guardkit/.claude/reviews/TASK-REV-FA04-report.md), [`jarvis/docs/architecture/decisions/ADR-ARCH-010-python-312-and-deepagents-pin.md`](../../../jarvis/docs/architecture/decisions/ADR-ARCH-010-python-312-and-deepagents-pin.md) Revision 2
**Portfolio policy:** [`guardkit/docs/guides/portfolio-python-pinning.md`](../../../guardkit/docs/guides/portfolio-python-pinning.md)

## Executive Summary

The task brief framed this review around a hypothesised conflict — "deepagents 0.4.11 likely requires langchain<1, so we'll have to bump deepagents AND langchain together, OR stay on 0.x for both." Empirical investigation **falsifies the hypothesis**: deepagents 0.4.11 already requires `langchain-core<2,>=1.2.27` and `langchain<2,>=1.2.15` (PyPI metadata), so coherent 1.x langchain has been mandated by the existing pin floor for months. The current `>=0.4.11` / `>=0.3` pin shape **already drifts to coherent 1.x** on every fresh install: a clean 3.14 venv resolves to deepagents 0.5.4 + langchain 1.2.15 + langchain-core 1.3.2 + langgraph 1.1.10 with no resolver complaints. The portfolio-coherence work amounts to **making explicit what is already implicitly happening**, plus adding the canonical `<2` caps from the Jarvis ADR-rev2 pattern so the resolver can't drift to a future 2.x langchain release silently.

**Recommendation: Branch A — coherent 1.x langchain pins with `<2` caps + deepagents `>=0.5.3,<0.6` floor + add explicit `langchain-anthropic` dep.** Source-side migration cost is **zero**: the deepagents API surface this project depends on (`FilesystemBackend`, `MemoryMiddleware`, `PatchToolCallsMiddleware`) is identical between 0.4.11 and 0.5.4, and the project's agent factories already bypass `create_deep_agent` and call `langchain.agents.create_agent` directly with langchain-1.x-shaped middleware imports.

A separate, **unrelated** finding: the empirical pytest runs surface 90 pre-existing test failures (`async def functions are not natively supported`) caused by a missing `pytest-asyncio` dev dependency. This is independent of the pin question. Filed as a follow-up hygiene fix below.

## Empirical Evidence

### Run 1 — Fresh 3.14 venv, current pins (no `--upgrade`)

```bash
rm -rf .venv
uv venv --python 3.14 .venv          # → CPython 3.14.2
uv pip install --python .venv/bin/python -e ".[dev]"
.venv/bin/python -m pytest --tb=no -q
```

| Package | Resolved |
|---|---|
| `deepagents` | **0.5.4** |
| `langchain` | 1.2.15 |
| `langchain-core` | 1.3.2 |
| `langchain-community` | 0.4.1 |
| `langchain-text-splitters` | 1.1.2 |
| `langchain-openai` | 1.2.1 |
| `langchain-anthropic` | 1.4.2 *(transitive — not declared in pyproject.toml)* |
| `langgraph` | 1.1.10 |
| `langgraph-checkpoint` | 4.0.3 |
| `pydantic` | 2.13.3 |
| `chromadb` | 1.5.8 |

**Pytest:** `90 failed, 1869 passed, 121 warnings in 8.30s` — log at `/tmp/adf-3.14-current-pytest.log`.

All 90 failures share the same root cause: missing `pytest-asyncio`. Representative traceback:

```
tests/test_format_gate_key_validation.py::TestFormatGateKeyValidation::test_rejects_json_with_only_messages_no_metadata
async def functions are not natively supported.
You need to install a suitable plugin for your async framework, for example:
  - anyio
  - pytest-asyncio
  - pytest-tornasync
  - pytest-trio
  - pytest-twisted
```

`pyproject.toml` has `[tool.pytest.ini_options].asyncio_mode = "auto"` but the dev extra (`pytest>=8.0`, `pytest-bdd>=8.1,<9`, `pytest-cov`, `ruff`) does not include `pytest-asyncio`. **This failure cluster is pin-independent** — confirmed by repeating the run against the previous .venv (deepagents 0.4.12 + langchain 1.2.13) which produced the identical 90/1869 split.

### Run 2 — `--upgrade` install in same venv

```bash
uv pip install --upgrade --python .venv/bin/python -e ".[dev]"
.venv/bin/python -m pytest --tb=no -q
```

| Package | Resolved |
|---|---|
| Identical to Run 1 | (no version drift) |

**Pytest:** `90 failed, 1869 passed, 121 warnings in 4.94s` — log at `/tmp/adf-3.14-upgraded-pytest.log`.

`uv pip install` already does a fresh resolve from `pyproject.toml` constraints (it does not honour `uv.lock`); `--upgrade` makes no difference to the resolved set. The current pin shape resolves to the same coherent 1.x stack with or without `--upgrade`.

**There is no deepagents-0.4.x-vs-langchain-1.x trapdoor in this project**, contradicting the task brief's hypothesis. The reason: deepagents 0.4.11 / 0.4.12 already declare `langchain-core<2,>=1.2.27` and `langchain<2,>=1.2.15` (verified PyPI metadata, see "deepagents version compatibility" below).

### Pre-existing .venv snapshot (March 31 install — informational)

The `.venv` in the working tree before this review (created 2026-03-31) had:

| Package | Version |
|---|---|
| `deepagents` | 0.4.12 |
| `langchain` | 1.2.13 |
| `langchain-core` | 1.3.2 |
| `langgraph` | 1.1.3 |

The same 90/1869 split. This is independent confirmation that deepagents 0.4.x cohabits cleanly with langchain 1.x — the resolver picked 0.4.12 (latest 0.4.x at install time) on March 31, and would pick 0.5.4 today.

## deepagents Version Compatibility

PyPI metadata (verified live, 2026-04-29):

| deepagents | requires-python | langchain-core | langchain | langchain-anthropic | Released |
|---|---|---|---|---|---|
| **0.4.11** | `<4.0,>=3.11` | `<2.0.0,>=1.2.27` | `<2.0.0,>=1.2.15` | `<2.0.0,>=1.4.2` | (current pin floor) |
| 0.4.12 | `<4.0,>=3.11` | `<2.0.0,>=1.2.27` | `<2.0.0,>=1.2.15` | `<2.0.0,>=1.4.2` | 2026-03-20 (latest 0.4.x) |
| **0.5.4** | `<4.0,>=3.11` | `<2.0.0,>=1.2.27` | `<2.0.0,>=1.2.15` | `<2.0.0,>=1.4.2` | (latest stable) |

**Identical langchain dependency constraints across 0.4.11 → 0.5.4.** The 0.4.x → 0.5.x version bump must be carrying API or feature changes (per the Jarvis ADR-rev2, 0.5.3 introduced `AsyncSubAgent` as a preview), not a langchain-version cliff.

### deepagents API surface used by this project

```text
agents/coach.py:
  from deepagents.backends import FilesystemBackend
  from deepagents.middleware import MemoryMiddleware
  from deepagents.middleware.patch_tool_calls import PatchToolCallsMiddleware

agents/player.py:
  (identical three imports)

(tests under tests/ and agents/tests/ assert the same imports + verify
 FilesystemMiddleware is NOT included in the middleware stack)
```

Used signatures:
- `FilesystemBackend(root_dir=".")`
- `MemoryMiddleware(backend=backend, sources=memory)`
- `PatchToolCallsMiddleware()` *(no args)*

The factories explicitly bypass `create_deep_agent` (per TASK-TRF-012 and TASK-TRF-016 — to fix tool leakage) and call `langchain.agents.create_agent` directly. There are project tests (`tests/test_player_factory.py`, `tests/test_coach_factory.py`, `agents/tests/test_player.py`, `agents/tests/test_coach_factory.py`) that **assert `create_deep_agent` is not imported** in the agent modules.

I verified all four imports on the freshly-resolved deepagents 0.5.4:

```bash
$ .venv/bin/python -c "from deepagents.backends import FilesystemBackend; \
                       from deepagents.middleware import MemoryMiddleware, FilesystemMiddleware; \
                       from deepagents.middleware.patch_tool_calls import PatchToolCallsMiddleware"
# (no output — all imports succeed)
```

**Source-side migration cost from 0.4.11 → 0.5.x: zero.** The narrow API surface this project depends on is unchanged. The Jarvis "0.5.3-required-for-langchain-1.x" framing reflects Jarvis's own AsyncSubAgent dependency, not a langchain-compatibility cliff in 0.4.x.

## langchain-text-splitters Compatibility (AC #5)

PyPI metadata for `langchain-text-splitters`:

| Version | requires-python | langchain-core | Released |
|---|---|---|---|
| 1.1.2 (latest) | `<4.0.0,>=3.10.0` | `<2.0.0,>=1.2.31` | 2026-04-16 |
| 1.1.1 | (same) | (same) | — |
| 1.1.0 | (same) | (same) | — |
| 1.0.0 | — | — | (initial 1.x) |

A coherent 1.x release exists and is already what the resolver picks (1.1.2 in both runs above). Used in `ingestion/chunker.py:23`:

```python
from langchain_text_splitters import RecursiveCharacterTextSplitter
```

Recommend pin: `langchain-text-splitters>=1.1,<2`.

## Source-Code Compatibility with langchain 1.x (Pre-Existing)

Grep across `agents/`, `synthesis/`, `ingestion/`, `src/`, `entrypoint/` (excluding tests):

| File:line | Import | Notes |
|---|---|---|
| `agents/model_factory.py:18` | `from langchain.chat_models import init_chat_model` | langchain 1.x canonical (`init_chat_model`) |
| `agents/player.py:29`, `agents/coach.py:29` | `from langchain.agents import create_agent` | **langchain 1.x API** (replaces 0.x `AgentExecutor`) |
| `agents/player.py:30`, `agents/coach.py:30` | `from langchain_anthropic.middleware import AnthropicPromptCachingMiddleware` | 1.x-shaped (middleware module) |
| `agents/player.py:35`, `agents/coach.py:36` | `from langgraph.graph.state import CompiledStateGraph` | langgraph 1.x canonical |
| `ingestion/chunker.py:23` | `from langchain_text_splitters import RecursiveCharacterTextSplitter` | available on 1.x |
| `src/tools/rag_retrieval.py:18`, `src/tools/write_output.py:22` | `from langchain_core.tools import tool` | langchain-core 1.x canonical |

**Every langchain import in the runtime source is 1.x-shaped.** The codebase has been written against 1.x semantics; the open-floor `>=0.3` pins were the only thing keeping 0.x as a theoretical resolution path. In practice that path was already closed by deepagents' transitive constraints. The pin update merely codifies the resolved state.

## Branch Decision

| Branch | Pros | Cons | Cost | Recommendation |
|---|---|---|---|---|
| **A — coherent 1.x + `<2` caps + deepagents `>=0.5.3,<0.6`** | Aligns with portfolio canonical (Jarvis ADR-rev2). Locks against future 2.x langchain drift. Makes resolved state explicit. | Pin churn in `pyproject.toml`. | **Zero source migration.** Pin diff only. | **✅ Recommended.** |
| B — cap langchain ecosystem at `<1` to "stay on 0.x" | Preserves "0.x-stable" framing | Empirically wrong: current pins ALREADY resolve to 1.x via deepagents transitive constraints. Forcing `<1` would either (a) be impossible to satisfy with deepagents 0.4.11+ (resolver fails), or (b) require a deepagents downgrade to a release prior to the langchain-1.x mandate (research not done — would also fail to install on Python 3.14). | Diverges from portfolio. Potentially impossible to satisfy. | ❌ Reject. |

The task brief framed Branch B as "preserves current API". The current API **is** langchain 1.x. Branch B would be a regression, not a preservation.

### Open question for the user (out of scope of this review)

Whether to track Jarvis exactly with `deepagents>=0.5.3,<0.6` (Jarvis's choice — they need AsyncSubAgent which is preview-flagged in 0.5.x) or use `deepagents>=0.5.4,<0.6` (the latest stable, which is what the resolver currently picks). **This project does not use AsyncSubAgent** — its API surface is the much narrower middleware/backend trio — so the AsyncSubAgent breakage risk that motivates Jarvis's exact-floor pinning doesn't apply here. Either pin works. The Jarvis-aligned `>=0.5.3,<0.6` keeps portfolio coherence; `>=0.5.4,<0.6` matches the resolver's current pick. Recommendation in the pin diff below: `>=0.5.3,<0.6` for portfolio consistency.

## Recommended Pin Diff

```diff
--- pyproject.toml
+++ pyproject.toml
 [project]
 name = "agentic-dataset-factory"
 version = "0.1.0"
 requires-python = ">=3.11"
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
+    "langchain-community>=0.4,<1",          # community is on 0.4.x, NOT 1.x — see note below
-    "langchain-text-splitters>=0.3.0",
+    "langchain-text-splitters>=1.1,<2",
-    "langchain-openai>=0.3",
+    "langchain-openai>=1.2,<2",
+    "langchain-anthropic>=1.4,<2",          # NEW — was implicit transitive, now explicit
-    "langgraph>=0.2",
+    "langgraph>=1.1,<2",
     "pyyaml>=6.0",
     "pydantic>=2.0",
 ]
```

**`requires-python = ">=3.11"` already correct** — no change. Matches portfolio canonical.

### Notes on the diff

1. **`langchain-anthropic` becomes explicit.** It is currently pulled in transitively (via `deepagents` and via `init_chat_model`'s lazy provider import) and used directly in `agents/coach.py` and `agents/player.py` (`AnthropicPromptCachingMiddleware`). This is the same anti-pattern Jarvis ADR-rev2 fixed for `langchain` itself — the fix is to make it explicit so the resolver is constrained directly. **Same-major (`<2`) cap, no upper-version drama.**

2. **`langchain-community` stays on 0.4.x with `<1` cap.** Unlike the rest of the langchain stack, langchain-community did not follow the 1.x rename and remains on 0.4.x (`langchain-community==0.4.1` is the latest). Its own deps allow `langchain-core<2,>=1.0.1`, so it's compatible with the rest of the 1.x stack. The `<1` cap matches its semver track, not the langchain-1.x track.

3. **`langchain` becomes an explicit `<2` cap.** Was open-floor `>=0.3`; now `>=1.2,<2`. Matches Jarvis ADR-rev2 rationale: explicit caps are protection against the next-major bump in a fast-moving ecosystem, *not* the same anti-pattern as Python upper bounds. Schreiner's argument applies to interpreter caps, not library caps where breaking-change majors are the documented contract.

4. **`langgraph>=1.1,<2`.** Resolver picked 1.1.10 today; 1.1 floor leaves headroom for patch/minor; `<2` cap protects against a 2.x release.

5. **Optional dependencies untouched.** `[ingestion]` extra (`docling>=2.0`) and `[dev]` extra are out of scope for this review — though see the pytest-asyncio note below.

## Resolved Versions (target state after the diff)

Same as Run 1 / Run 2 above (the diff codifies, doesn't change, the resolved state):

```text
deepagents==0.5.4
langchain==1.2.15
langchain-core==1.3.2
langchain-community==0.4.1
langchain-text-splitters==1.1.2
langchain-openai==1.2.1
langchain-anthropic==1.4.2
langgraph==1.1.10
langgraph-checkpoint==4.0.3
pydantic==2.13.3
chromadb==1.5.8
```

## Source-Side Migration Work (Branch A)

**None required.**

The narrow deepagents API surface and 1.x-shaped langchain imports mean the pin diff is purely a manifest change. No file edits in `agents/`, `synthesis/`, `ingestion/`, `src/`, or `entrypoint/`. No test rewrites. No behaviour changes.

The acceptance criterion *"If Branch A: identification of any source-side migration work (filed as separate task spec, not implemented here)"* is satisfied vacuously — there is none to file.

## Failure Categorisation (per FA04 playbook)

Mapping the FA04 framework to this project:

| FA04 finding | Applies here? | Notes |
|---|---|---|
| F0. Bootstrap silently broken on Mac for every Jarvis run since 3.14 | **No.** | Empirical: fresh 3.14 install + tests succeeds (modulo pre-existing pytest-asyncio gap). 1869 tests pass. |
| F2. Coach pytest interpreter selection (no requires-python recovery path) | **No.** | This project's `requires-python = ">=3.11"` already accepts 3.14. The trapdoor mechanism never fires. |
| F9. Sibling project Python pin alignment | **Already aligned.** | No change needed. |
| Implicit langchain dependency | **Yes.** | `langchain` is technically explicit in this project's pin (`>=0.3`) but was on 0.x floor. `langchain-anthropic` IS implicit-transitive — addressed in the diff. |
| Open-floor langchain ecosystem pins → resolver picks coherent 1.x or coherent 0.x non-deterministically | **Latent.** | Not an active failure today (deepagents transitive constraints lock to 1.x), but the pin shape is fragile — if a future deepagents release relaxed its langchain-core floor, the resolver could pick 0.x langchain on this project. Branch A's `<2` caps remove the latent risk. |

This project is FA04-clean for the Python-pin trapdoor (`>=3.11` already matches the canonical) and FA04-vulnerable only on the latent langchain-ecosystem pin shape (addressed by Branch A).

## CLAUDE.md Recommendation

The portfolio guide ([`guardkit/docs/guides/portfolio-python-pinning.md`](../../../guardkit/docs/guides/portfolio-python-pinning.md)) is GuardKit-side documentation. This project's `.claude/CLAUDE.md` (verified at `/Users/richardwoollcott/Projects/appmilla_github/agentic-dataset-factory/.claude/CLAUDE.md`) lists the technology stack with versions but does not cross-reference the portfolio pinning policy.

**Light-touch recommendation:** add a one-line pointer near the Technology Stack section, e.g.:

```markdown
## Technology Stack

**Language**: Python 3.11+ (open upper bound — see [portfolio-python-pinning](https://github.com/.../guardkit/docs/guides/portfolio-python-pinning.md))
**Frameworks**: ...
```

Or omit if the consensus is that consumer-project CLAUDE.md files should not cross-link into GuardKit docs (template-driven content vs project-specific). Either choice is defensible; I lean toward including the pointer because the policy is non-obvious to a future maintainer touching the pyproject in isolation.

This is a soft AC — file as part of the implementation task or skip if the portfolio convention is otherwise.

## Independent Finding (out of scope, but flagged)

### Pre-existing `pytest-asyncio` gap — 90 test failures

`pyproject.toml` configures `asyncio_mode = "auto"` under `[tool.pytest.ini_options]`, but the `[project.optional-dependencies].dev` array does NOT include `pytest-asyncio`. Result: 90 tests using `async def` and/or `@pytest.mark.asyncio` fail at collection-execute boundary with:

```
async def functions are not natively supported.
You need to install a suitable plugin for your async framework, for example:
  - anyio
  - pytest-asyncio
  - pytest-tornasync
  - pytest-trio
  - pytest-twisted
```

Affected files (clusters):
- `tests/test_decouple_format_retries.py` (11)
- `tests/test_format_gate_key_validation.py` (8)
- `tests/test_httpstatuserror_handling.py` (8)
- `tests/test_structured_outputs_fallback.py` (10)
- `tests/test_integration_smoke.py` (2)
- `tests/test_valueerror_per_target_handler.py` (2)
- `tests/test_coach_retry_json_reinforcement.py` (1)
- … and several others (90 total)

This is **independent of the langchain pin question** — confirmed by reproducing on both deepagents 0.4.12 and 0.5.4. The fix is a one-line addition to the dev extra:

```diff
 dev = [
     "pytest>=8.0",
+    "pytest-asyncio>=0.24,<1",
     "pytest-bdd>=8.1,<9",
     "pytest-cov",
     "ruff",
 ]
```

**Recommend filing as a separate hygiene task** (TASK-OPS-???) — not bundled with the pin alignment work. The task brief explicitly excludes "implementing the pin updates or any source-side ... migration", and this fix is in the same out-of-scope category. Surface it via the [I]mplement decision at the end of this review if desired.

## Acceptance Criteria — Self-Audit

- [x] Both empirical runs (current pins / `--upgrade`) captured with their pytest outputs. *(Logs: `/tmp/adf-3.14-current-pytest.log`, `/tmp/adf-3.14-upgraded-pytest.log`. Both 90/1869 split, identical resolved versions.)*
- [x] deepagents 0.4.x vs 0.5.x compatibility delta documented (which APIs agentic-dataset-factory uses; which broke). *(See "deepagents API surface used by this project". Delta: zero.)*
- [x] Branch recommendation (A or B) with rationale. *(Branch A.)*
- [x] Resolved versions table for the recommended branch. *(See "Resolved Versions" section.)*
- [x] Pin update recommendation: explicit diff against current `pyproject.toml`. *(See "Recommended Pin Diff" section.)*
- [x] If Branch A: identification of any source-side migration work (filed as separate task spec, not implemented here). *(None required — vacuous satisfaction documented in "Source-Side Migration Work".)*
- [x] `langchain-text-splitters` pin recommendation. *(`>=1.1,<2`.)*
- [x] New ADR drafted with rationale, verified-versions table, cross-repo precedent reference, branch decision. *(Drafted at `docs/architecture/decisions/ADR-ARCH-011-langchain-1x-portfolio-alignment.md`.)*
- [x] Recommendation on whether agentic-dataset-factory needs portfolio-pinning guide reference in its `CLAUDE.md`. *(Light-touch recommendation: add a one-line pointer. See "CLAUDE.md Recommendation".)*
- [x] No proposed changes to GuardKit or Jarvis — fixes live in this repo. *(Confirmed: all changes scoped to this repo's `pyproject.toml`, `docs/architecture/decisions/`, and optionally `.claude/CLAUDE.md`.)*
- [x] Report saved to `.claude/reviews/TASK-REV-AD14-report.md`. *(This file.)*

## Suggested Implementation Tasks (if [I]mplement is chosen)

| Task | Mode | Wave | Work |
|---|---|---|---|
| TASK-AD14-A — apply pin diff + draft ADR-ARCH-011 | direct | 1 | One-edit `pyproject.toml`; add explicit `langchain-anthropic`; verify `uv pip install -e ".[dev]"` resolves cleanly on 3.14 + tests still pass at 1869 (90 pre-existing async failures); commit ADR-ARCH-011 (template provided). |
| TASK-AD14-B — pytest-asyncio hygiene fix (optional, separate) | direct | 1 | Add `pytest-asyncio>=0.24,<1` to `[dev]` extra; expect 1959/1959 passing (or surface any *new* failures that were masked by the async-skip). |
| TASK-AD14-C — CLAUDE.md cross-reference (optional, lightweight) | direct | 1 | One-line pointer to portfolio-pinning guide near Technology Stack section. Skip if portfolio convention disallows cross-repo pointers in consumer CLAUDE.md. |

All three are direct-mode (no agent loop needed). A and C are pin-alignment work; B is a separate hygiene fix that the pin work happened to surface. Bundling B with A is reasonable; splitting them is also reasonable — depends on how pristine the maintainer wants the pin-alignment commit to look.

## Provenance

- All file:line references in "Source-Code Compatibility with langchain 1.x" verified against agentic-dataset-factory HEAD at review time.
- deepagents PyPI metadata (0.4.11, 0.4.12, 0.5.4) verified via `https://pypi.org/pypi/deepagents/json` and via `importlib.metadata` against the freshly-resolved venv.
- langchain-text-splitters PyPI metadata verified via `https://pypi.org/pypi/langchain-text-splitters/json`.
- Both pytest runs executed against `/usr/local/bin/python3.14` (CPython 3.14.2) with a freshly-created `.venv`. Logs preserved at `/tmp/adf-3.14-current-pytest.log` and `/tmp/adf-3.14-upgraded-pytest.log` (see also the baseline against the pre-existing March-31 venv at `/tmp/adf-3.14-baseline-existing-venv-pytest.log`).
- Cross-repo references read read-only; no changes to `guardkit/` or `jarvis/` were made or proposed.
- The current `.venv` was rebuilt during this review (per AC #1) and currently contains the freshly-resolved 1.x stack. Restoring to the prior state is a `uv sync` away if the `uv.lock` shape needs to be preserved.
