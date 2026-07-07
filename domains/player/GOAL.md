# Goal — Player (SLM build-agent) · SCAFFOLD SEED

**Status:** WS4-S8 scaffold, 2026-07-07 (Fable 5, in-window). **Scaffold only — no generation
runs, no generation targets, no manifest.** Those absences are deliberate and gated (§3), not
oversights. This file exists because WS4 §5's design rule says qa-verifier and player domains
need scaffolds before their fine-tunes can exist — the qa-verifier scaffold landed as WS2-B11
(`11db17a`, sibling dir); this is the player half.
**Binding parent:** `ai-transition/docs/ws4-learning-flywheel-scope-and-build-plan-2026-07-07.md`
§5 (Player row) + §6.3 (three-seat placement + wasting-asset posture, binding per Rich's
2026-07-07 note).

## 1. What this lane is (and is not)

The SLM-Player is an **experiment lane and a fallback, not a committed migration.** The
frontier Player (Claude Agent SDK, embedded in the guardkit orchestrator for autobuild) stays
until the gates in §3 say otherwise. The lane exists because the frontier lane is a **wasting
asset**: subscription programmatic access was withdrawn once and reversed (the 15-June
episode), and DF-006 exists precisely because that access is revocable. The stated degradation
chain (program plan §8): if programmatic access dies again, attended planning stays
frontier-by-hand while **the build lane falls to this DeepAgents/local harness** — which makes
this lane's readiness scheduled work, not a hobby.

Harness placement (WS4 §6.3, binding — do not relitigate here): autobuild = Claude Agent SDK
embedded; forge-dispatched whole sessions = dcode headless; **the SLM role-harness runtime =
the DeepAgents SDK** (only maintained batteries-included harness that runs local
OpenAI-compatible endpoints / llama-swap under DF-001); harness bundles are data
(HarnessProfileConfig YAML + AGENTS.md + skills + memories), interpreted per seat.

## 2. Fine-tune target sketch (seed only)

A build-capable local model: reads a task + assembled context, drives the build toolset
(files, tests, bash) through the DeepAgents harness, produces work the Coach/QAV judgment
fleet can gate. Training rows are **(assembled Player input, action trajectory / output)
pairs** — which is exactly why this domain cannot generate yet: per WS4 Appendix A, **Player
input capture (full assembled prompt + injected context refs) is missing everywhere today**;
output-only capture cannot be reconstructed into rows. Candidate sources when capture lands:
autobuild artifacts, the ABL corpus, forge-dispatched session traces (dcode `hooks.json` as
the Chronicler tap).

**D9 pairing (re-check at any model choice):** an SLM Player must not share a model family
with the Coach/QAV that judges it. The judgment fleet is Gemma-4 26B — the Player base
therefore comes from a different family (the in-factory generation Player, gpt-oss-120b,
already satisfies this; treat it as the default candidate lineage, not a decision).

## 3. Gates — nothing generates or trains until these hold

| Gate | What | Owner / where |
|---|---|---|
| G-PL-1 | **DeepAgents eval-suite gate pre-registered** — "a 26B fine-tune can drive this harness" is a hypothesis, not an assumption (published DeepAgents evals cover 100B+ only) | WS4-S10 (new pre-registration, WS4 §7 register row) |
| G-PL-2 | **Phase GRAM landed** (FEAT-GRAM-001/002) — no new SLM role goes live before grammar-constrained decoding is structural (WS4 §5 design rule; cure proven in guardkitfactory TASK-ARCH-COACHSPLIT) | WS4-S9 |
| G-PL-3 | **Trace capture to the Appendix-A contract** — a role session not captured to that contract is not a flywheel input; today the Player input field class is `missing` | WS1 FEAT-SPL-005 + guardkit telemetry gap |
| G-PL-4 | **D9 pairing re-checked** against the judgment fleet at the moment a base is picked | this domain's future SPEC |
| G-PL-5 | **DF-008** — any dataset here is private end-to-end | standing |

Memory-side features for this lane (retrieval budgets, RAG) additionally wait on **ABL-006**
(WS4 §6.4 gate) — the write-side dataset design does not.

## 4. Conventions this domain inherits (pointers, not copies)

- **Manifest format:** the WS4 handover manifest pinned by B11 —
  `../qa-verifier/OUTPUT-CONTRACT.md` §5 (`manifest_version`, counts, `balance_report`,
  embedded `contamination_check`, `visibility: private`). A future player manifest follows it.
- **Row provenance:** the `{repo, feature, task, run, sha}` quintet, mandatory per row; a row
  that cannot be traced to a committed record does not enter a manifest.
- **Hold-out discipline:** eval rows named at creation, never in a training manifest;
  contamination check as a named validation step.
- **Source enum:** rows carry `book | harvest | flywheel` provenance
  (`../product-owner/SPEC-po-phase2-harvest-lift.md` precedent).

## 5. Next artifact (not this session)

`SPEC-player-dataset.md` — written only after G-PL-1 and G-PL-3 exist, because the dataset's
input shape IS the capture contract's output. Writing it earlier means guessing the input
shape, which is the exact mistake the QAV thread avoided by waiting for COACHGATHER01.
