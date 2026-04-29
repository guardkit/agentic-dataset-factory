# architect-agent-probe — Findings

**Run date:** 2026-04-26
**Pipeline elapsed:** 7,157s (~1.99 hours)
**Model under test:** Qwen/Qwen3.5-35B-A3B-FP8 (Player and Coach both)
**Endpoint:** http://localhost:8002/v1 (single GB10, GPU util 0.70)
**LangSmith tracing:** disabled (no `LANGSMITH_API_KEY` configured; see Caveats)

## TL;DR

The hypothesis being tested was that the 98 provider-side content-policy
refusals seen in GCSE English Run 1 were **literature-specific** — triggered
by reproducing passages from Macbeth, Dickens, etc. This probe ran the same
Qwen model under the same conditions against two architecture books (Evans'
DDD blue book and Ford's *Software Architecture: The Hard Parts*) and observed
**4 provider-side refusals across 110 targets**, with a perfectly clean split:

| Cut | Targets | Refusals | Rate |
|---|---|---|---|
| `type=reasoning` (with `<think>` block) | 80 | 0 | 0.0% |
| `type=direct` (no `<think>` block) | 30 | 4 | **13.3%** |

**Conclusion: the Run 1 hypothesis is rejected.** Refusals correlate with
**direct/factual short-form generation, not with corpus or subject matter**.
Architecture content reproduces the same refusal pattern. The literary-style
prose of Evans (highest projected risk per the GOAL.md) produced **zero**
refusals across 50 reasoning targets.

## Decision

For the production architect-agent training-data pipeline:

1. **Keep Qwen3.5-35B-A3B-FP8 as the Coach for `type=reasoning` categories.**
   Across 80 reasoning targets the Coach refused 0 times and produced
   high-quality verdicts (mostly score 4–5 acceptances) on dense, copyrighted
   architectural prose.
2. **Do not use Qwen3.5-35B-A3B-FP8 as the Coach for `type=direct` categories.**
   13.3% provider-refusal rate is incompatible with a production pipeline.
   Either:
   - Swap to Nemotron 3 Super for the Coach on direct-type targets, or
   - Restructure direct categories to require a `<think>` block (which
     eliminates the refusal trigger), or
   - Drop direct categories from the architect-agent spec entirely.

The third option is cheapest and is recommended unless direct-type examples
turn out to be load-bearing for the downstream evaluation.

## Methodology

110 targets across seven categories. Sample size deliberately small for a
~1-hour diagnostic run. Per-book split: ~50 Evans (DDD strategic + tactical
+ half of terminology), ~60 Ford (trade-off analysis + half of terminology
+ pattern names + all behaviour). Adversarial framing: if Evans triggered
refusals and Ford didn't, the issue would localise to literary-style prose;
if both refused, it would suggest a general Qwen reaction to long copyrighted
material; if neither refused, the Run 1 hypothesis would be wrong.

The actual outcome — **a clean split by `type` rather than by book** — was
not predicted by either the original hypothesis or the probe design. This is
the most useful finding of the run.

## Quantitative results

### Per-category breakdown

| Layer | Type | Category | Accepted | Rejected | Total |
|---|---|---|---|---|---|
| knowledge | reasoning | DDD strategic (Evans) | 25 | 0 | 25 |
| knowledge | reasoning | DDD tactical (Evans) | 25 | 0 | 25 |
| knowledge | reasoning | Trade-off analysis (Ford) | 18 | 2 | 20 |
| knowledge | direct | Terminology and precise definitions | 8 | 2 | 10 |
| knowledge | direct | Pattern names and single-line summaries | 9 | 1 | 10 |
| behaviour | reasoning | Explaining architectural reasoning to a developer | 10 | 0 | 10 |
| behaviour | direct | Direct answers to quick architectural questions | 9 | 1 | 10 |
| **Total** | | | **104** | **6** | **110** |

### Per-quadrant summary

| Layer | Type | Accepted | Rejected | Provider refusals |
|---|---|---|---|---|
| knowledge | reasoning | 68 | 2 | 0 |
| knowledge | direct | 17 | 3 | 3 |
| behaviour | reasoning | 10 | 0 | 0 |
| behaviour | direct | 9 | 1 | 1 |

### Pipeline economics

- Total tokens: 1,672,779 (1.41M prompt, 260K completion)
- Total turns across all targets: 164
- Mean tokens per accepted target: ~16K
- Worst-case target (51, exhausted): 43,361 tokens

## Rejection analysis

The 6 rejections fall into two distinct categories that the probe did not
distinguish at log-emission level (both are surfaced as `target_rejected`)
but which mean very different things.

### Provider-side content-policy refusals (4)

Signature: Coach response has `content=''` and `additional_kwargs keys=['refusal']`
on the very first Coach turn. No `rejection_history` is recorded because the
Coach never returned an evaluable verdict — the OpenAI-compatible vLLM endpoint
emitted the structured-output `refusal` token instead of content. This is the
exact signature of the GCSE Run 1 refusals.

| Target | Layer | Type | Category |
|---|---|---|---|
| 71 | knowledge | direct | Terminology and precise definitions |
| 79 | knowledge | direct | Terminology and precise definitions |
| 84 | knowledge | direct | Pattern names and single-line summaries |
| 109 | behaviour | direct | Direct answers to quick architectural questions |

All four are `type=direct`. None had a recoverable `rejection_history`.

### Rubric-and-pipeline-driven rejections (2)

Both are in the Ford trade-off analysis category, both surfaced as
`max_turns_exhausted`, but the underlying causes are different and both are
**Coach-functioning-correctly outcomes** rather than refusals:

**Target 51 — schema enum confusion.** The Coach accepted the content three
times in a row (score 5, all criteria met). The Player set
`metadata.topic = "trade_off_analysis"`, which is a valid value in the
`pattern_family` enum but not in the `topic` enum. The write-validation
layer rejected each acceptance because the metadata wasn't conformant.
After three write-failures interleaved with format-gate retries, the
per-target turn budget was exhausted.

**Target 55 — verbatim-reproduction enforcement.** The Coach correctly flagged
two phrases as verbatim copyright violations under the `no_verbatim_reproduction`
criterion (15-word rule):

> "If I change X, what else is likely to change?"

> "two parts are coupled if a change in one might cause a change in the other"

Both are direct quotations from Ford's *Hard Parts*. The Coach issued
revise verdicts citing the rule precisely; the Player kept regenerating with
those same phrases preserved (likely because the RAG-retrieved chunks
contained them and the Player's paraphrasing didn't go far enough). The
rubric is working as designed — this is an example of the Coach **catching
exactly the kind of reproduction the GOAL.md was set up to prevent**.

### Recurring Player envelope-discipline failures (informational)

Throughout the run, two non-fatal Player issues recurred but were absorbed
by the pipeline's retry mechanisms:

- **Schema-drift on `metadata.topic`** — Player invented values like
  `entity_vs_value_object`, `entity_value_object`, `repository`, `coupling`
  on entity/value-object questions and DDD-tactical patterns not in the
  enum. Recovered via the 3-attempt write-retry on most targets; caused the
  target 51 rejection when it intersected with format-gate failures.
- **Markdown-mode runaway** — Player occasionally produced long markdown
  prose with no JSON envelope, hitting the 4096-token completion cap on at
  least two targets (37 and 48). The pre-Coach format gate intercepted these
  and forced retries. Most recovered cleanly; one (target 51) contributed
  to exhaustion.

Neither issue is a refusal. Both are addressable via Player prompt tightening
or via widening the `metadata.topic` enum to cover commonly-attempted values
(`repository`, `service`, `factory`, `coupling`, etc.).

## Distribution analysis: the cut that wasn't predicted

The probe was designed around a per-book adversarial cut (Evans = high risk,
Ford = control). The actual signal was per-`type`:

| Cut | Refusals |
|---|---|
| Evans (50 reasoning targets) | 0 |
| Ford (20 reasoning + 30 direct + 10 behaviour-reasoning) | 4 (all on direct, none on reasoning) |
| `type=reasoning`, both books | 0/80 |
| `type=direct`, both books | 4/30 |

If the original hypothesis were correct, refusals should have concentrated on
Evans (literary, narrative, high refusal-surface risk). Instead Evans produced
zero refusals across 50 targets and Ford produced refusals only when the
target was direct-type. The shared structural feature of refusal-bearing
targets is that they ask the Player to produce **short, factual, definition-style
content without showing reasoning** — which appears to be what triggers the
provider-side filter, not the prose register of the source material.

Why this might be: a plausible mechanism is that the `<think>` block reframes
the assistant turn as analytical/reasoning text, which the model's alignment
treats differently from a flat factual reproduction. Direct-type targets
produce assistant content that more closely resembles a verbatim definition
or pattern summary, which is closer to the alignment-trained refusal surface
for "reproduce copyrighted material on demand". This is a hypothesis, not
a finding — confirming it would require a follow-up probe varying the
prompt structure while holding the source content fixed.

## Caveats

- **No LangSmith traces.** The `LANGSMITH_API_KEY` was not configured in the
  environment when the run started, so per-target trace inspection is not
  available. The case-by-case rejection inspection mentioned in the README
  was satisfied via `output/rejected.jsonl` instead, which captures full
  `rejection_history` for the 2 rubric-driven rejections but is empty for
  the 4 refusals (because the Coach returned no content to record).
- **Sample size.** 30 direct-type targets is small. The 13.3% refusal rate
  has a 95% confidence interval roughly 4%–28%; the true rate could be
  meaningfully higher or lower. The qualitative finding (refusals are direct,
  not reasoning) holds at any plausible point estimate.
- **Pipeline-side conflation.** The pipeline's `complete:` log emits
  `refusals=0` despite 4 provider-side refusals occurring. The 4 are visible
  in `rejected.jsonl` under `reason=llm_failure` with the `additional_kwargs
  keys=['refusal']` substring. Worth a small follow-up to surface
  provider-refusal as its own category in the summary line.

## Recommendations

In priority order:

1. **For the architect-agent production run, drop or restructure direct-type
   categories.** The refusal surface is on direct-type generation; reasoning-type
   is clean. If direct-type examples are wanted in the dataset, prepend a
   minimal `<think>` block to the spec or route them through a non-Qwen Coach.
2. **Widen the `metadata.topic` enum** to include the commonly-attempted DDD
   tactical patterns the Player keeps inventing (`repository`, `service`,
   `factory`, possibly `coupling` distinct from `coupling_cohesion`). This
   eliminates a recurring class of write-validation failures and cleans up
   the rejection log.
3. **Surface provider-refusal in the pipeline summary line** so future probes
   don't have to grep `rejected.jsonl` to find the count. Trivial change to
   the `complete:` emitter.
4. **Configure `LANGSMITH_API_KEY` for any future probe runs** so per-target
   trace inspection is available without having to reconstruct from the rejection
   log.
5. **Consider a follow-up probe holding source content fixed and varying
   prompt structure** (with/without `<think>`, with/without explicit "show
   your reasoning" framing) to confirm the structural hypothesis. ~20 targets
   would be enough to differentiate.

## Provenance

- Source PDFs: [domains/architect-agent-probe/sources/](sources/)
  - Eric Evans 2003 - Domain-Driven Design (PDF v1.2, 7.3M, MD5 `11edcb29974052333fcf77d15eb084c5`)
  - Software Architecture: The Hard Parts (PDF v1.6, 16M, MD5 `6abdba667e209c75f49d97e44bc16b5c`)
- Stage 0 ingestion: 4,674 chunks across both books, ChromaDB collection
  `architect-agent-probe`, 409s elapsed.
- Stage 1 generation: 110 targets, 1.99h, log at
  `run_logs/run-architect-probe-20260426-113427.log`
- Output artefacts:
  - `output/train.jsonl` — 19 behaviour-layer examples (training set)
  - `output/rag_index/knowledge.jsonl` — 85 knowledge-layer examples (RAG corpus)
  - `output/rejected.jsonl` — 6 rejection records with full history where available
- Pre-probe state of `output/` was preserved as `output_gcse_rerun/`; the
  GCSE training set in `output_backup_pre_rerun/` and `output_backup_run1/`
  is untouched.
- Existing ChromaDB collection `gcse-english-tutor` (3,850 chunks) was not
  affected; the probe collection coexists alongside it.
