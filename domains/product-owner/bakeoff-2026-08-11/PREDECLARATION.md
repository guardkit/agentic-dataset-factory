# Teacher bake-off — pre-declaration (committed BEFORE any candidate generated anything)
## 2026-08-11 · job 4 of the PO dataset-generation lane · anti-fishing receipt

## The one-minute version

Three candidate teachers each produce the same nine specification artifacts from the
same nine pre-declared inputs. Deterministic gates (the same code family as the frozen
exam) grade every artifact identically. The generation teacher for the corpus is picked
on those numbers — declared here, before any candidate ran, so the method cannot bend
toward a preferred answer.

## Candidates

| ID | Teacher | Endpoint | Role in the comparison |
|---|---|---|---|
| T1 | DeepSeek V4 Flash 0731 | the two-Spark seat, LiteLLM alias `deepseek` (Rich's window word 08-11: "you have both sparks") | The recommended teacher (08-01 verdict) on trial |
| T2 | The current production PO seat | `openai:product-owner-agent` via llama-swap :9000, production defaults | The honest baseline — what the spec chain uses today |
| T3 | Claude (Fable 5, attended) | this session, direct generation | Frontier reference point ONLY — pre-declared INELIGIBLE to win the teacher seat (mission law: frontier is a revocable attended teacher, never the standing seat) |

Ordering: T2 and T3 generate BEFORE the DeepSeek window opens (T2's seat is drained
during the window); T1 generates inside the window. Inputs are byte-identical across
candidates (MANIFEST.sha256).

## The nine inputs (fixed by `select_inputs.py`, position-based and reproducible)

| ID | Source | SHA-256 (first 16) |
|---|---|---|
| GF-1 | capture 0bfd3eff — /version endpoint brief | 18d33bd54d04de11 |
| GF-2 | capture 3cbc79db — /time endpoint brief | 27273d3eb7ea8adb |
| GF-3 | capture 478dc52c — jarvis socket-liveness watchdog brief | 140fe90d601799fe |
| FS-1 | capture 0f4fb5b7 — feature-spec session | 3dd5d73bfe6f0167 |
| FS-2 | capture 7c68af74 — feature-spec session | db856f8f1e91f23b |
| FS-3 | capture e75c1685 — feature-spec session | 9fce4e5193356ecc |
| EX-1 | forge FEAT-FORGE-002 spec history (53KB doc) | b8decc1a79033caa |
| EX-2 | study-tutor session-planner spec history (~30KB doc) | fb5d4c10918d71a7 |
| EX-3 | forge runbook-step-types spec history (~14KB doc) | a61dc1a91e6d8fdf |

Capture inputs replay the production Player's exact `player_input.messages`; extract
inputs pair the production `player_extract.md` system prompt with one real estate doc
rendered as a `## File:` block. A leakage guard asserted no input carries any of the
eight exam tasks' identifying content (FinProxy / RoundRoute / HomeStretch / kiln /
member-directory-search / po-held-*): the selector aborts on a hit and did not abort.

**Idea-mode is deliberately absent**: all 34 idea-mode captures carry probe-grade
inputs ("x", "Test", "AI-powered code review tool" — 23–49 chars). Grading teachers on
toy inputs grades nothing. (This also amends the job-1 stock-take: idea-mode corpus
rows must be teacher-authored, like extract and scope.)

## Generation parameters (fixed)

- T1 (DeepSeek): temperature 1.0, top_p 1.0 (the seat's production guidance), NO stop
  sequences, thinking at seat default, max_tokens 16384. Never temperature 0 (the
  banked decapitated-reasoning trap).
- T2 (PO seat): the production seat's own serving defaults — zero overrides. Train==serve
  parity is the point of the baseline.
- T3 (Claude): one attended generation per input, no retries, no self-grading.
- One generation per input per candidate. No cherry-picking: every response is banked
  raw before grading; regeneration is forbidden (a failed/empty response scores as
  gate-fail on all gates).

## Marking (deterministic, identical for all candidates, run after ALL generations)

Roadmap shapes (GF, EX) — gates from `fleet-evals/harness` (imported read-only):
1. `parse_response`: exactly one think block then one fenced JSON (the serving shape).
2. `po_contract.validate_product_roadmap` with the mode the input demands
   (GF → greenfield, EX → extract): full schema battery.
3. Grounding: GF → grounding emptiness (no citations anywhere, coverage_score null)
   plus ≥3 assumptions with falsifiable statement + impact_if_wrong; EX → every cited
   filename exists verbatim in the input's `## File:` blocks (fabricated-reference
   check), coverage of the provided doc.

Spec shape (FS) — the emitted three-file triple materialized to a tree, then the
structural gates from `spec_gates.py`: three-file completeness, Gherkin structural
parse, single-physical-line steps, banned implementation language in steps,
assumptions-manifest schema + ASSUM-NNN sequencing, summary/manifest/feature count
coherence, ≥8 scenarios. (Gates that require the target-terminal harness context —
header timestamp provenance, F1 seed — are out of scope for all candidates equally.)

Per artifact: PASS = zero blocking findings across its gate set; otherwise the
finding count is recorded.

## Metrics and the decision rule (in order; declared before any run)

1. **Gate-clean count** (of 9) — higher wins.
2. Tie → **mean blocking findings per artifact** — lower wins.
3. Still tied → **T2 wins over T1** (the cheaper teacher: no Spark window, no fleet
   drain). T3 cannot win regardless (reference only).

Operational telemetry (tokens/sec, wall-clock, GPU temperature under the thermal cap)
is recorded but decides nothing.

## Disposal

Bake-off outputs live under this directory only. **No bake-off output ever enters the
training corpus.** fleet-evals receives nothing (its harness code is imported
read-only; no runs are written into the exam repo).
