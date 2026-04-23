# architect-agent-probe — Runbook

## Purpose

Diagnostic probe to test whether Qwen3.5-35B-A3B-FP8 produces content-policy
refusals on software-architecture source material under the same pipeline
conditions that produced 98 refusals in the GCSE English Run 1.

Hypothesis being tested: **the Run 1 refusals were triggered specifically by
literary-style prose (Macbeth, Dickens, AQA literature content) rather than
by copyrighted source material in general.** If the probe completes with
zero provider-side `refusal` events, Qwen is fine for the architect-agent
training data pipeline and no model swap is needed. If refusals occur, the
probe data tells us which kind of prose triggers them.

## Setup (one-time)

```bash
# From the agentic-dataset-factory repo root
cd /Users/richardwoollcott/Projects/appmilla_github/agentic-dataset-factory

# Create the domain directory
mkdir -p domains/architect-agent-probe/sources

# Copy the two probe source PDFs
cp /Users/richardwoollcott/Projects/appmilla_github/architecture_books/"Eric Evans 2003 - Domain-Driven Design - Tackling Complexity in the Heart of Software.pdf" \
   domains/architect-agent-probe/sources/

cp /Users/richardwoollcott/Projects/appmilla_github/architecture_books/"Software_Architecture_The_Hard_Parts_Neal_Ford_OReilly_9781492086895.pdf" \
   domains/architect-agent-probe/sources/

# Verify
ls -lh domains/architect-agent-probe/sources/
```

Then drop the `GOAL.md` file (from this probe package) into
`domains/architect-agent-probe/GOAL.md`.

## Ingestion (Stage 0 — Docling → ChromaDB)

Both PDFs are digital, so standard mode is correct. Expect this to take
roughly 5–20 minutes depending on GB10 load; Evans is a long book.

```bash
# Activate the venv
source .venv/bin/activate

# Run ingestion
python -m ingestion.ingest --domain architect-agent-probe --chunk-size 512 --overlap 64
```

Success criteria:
- Exit code 0
- Summary prints `Documents processed: 2`
- Summary prints `Chunks created: <several thousand>` — the exact number
  depends on book length but both together should produce roughly
  3,000–6,000 chunks
- A new ChromaDB collection named `architect-agent-probe` exists

If you get a Docling failure on either PDF, that's an ingestion-side issue
unrelated to the refusal hypothesis — worth logging but doesn't invalidate
the probe.

## Run (Stage 1 — Player-Coach generation)

Keep `agent-config.yaml` pointing at the same Qwen3.5-35B-A3B-FP8 endpoint
you used for the current GCSE run. The whole point of the probe is to use
the same model under the same conditions — changing anything else confounds
the signal.

```bash
# Ensure LangSmith tracing is on so rejections are inspectable
export LANGSMITH_TRACING=true

# Point at the probe domain
# Either temporarily edit agent-config.yaml to set `domain: architect-agent-probe`,
# or override via env var / CLI (depending on how agent.py is wired)
python agent.py  # adjust invocation to match your current GCSE run command
```

Expected wall-clock: ~1 hour for 110 examples at 3 max_turns each.

## What to look for in the output

**Primary signal — refusal count:**
```bash
# Count provider-side content-policy refusals in the probe run
jq 'select(.category == "coach_refusal")' output/rejected.jsonl | wc -l

# Or inspect by source book if you tagged them
jq 'select(.category == "coach_refusal") | .target_index' output/rejected.jsonl
```

Three outcomes and what each means:

| Refusal count | Interpretation | Action |
|---|---|---|
| 0 | Run 1 refusals were GCSE-literature-specific. Qwen is fine for architecture content. | Proceed with Qwen on full architecture corpus. No model swap needed. |
| 1–10 | Edge cases, probably specific passages. Worth inspecting but not blocking. | Inspect the triggering chunks, decide if a content-filter tweak is enough. |
| >10, clustered on one book | One book's prose style triggers refusals. | Consider whether to swap models for that book or chunk-level filter. |
| >10, both books equally | Qwen has a general reaction to long copyrighted technical material. | Swap to Nemotron 3 Super for the Coach on the architecture domain. |

**Secondary signal — `max_turns_exhausted`:**
This is the Player-envelope-discipline problem from Run 1, not a refusal.
If it dominates again, the fix is in the Player prompt, not the model.

**Tertiary signal — Coach revise verdicts:**
Inspect the `criteria_met` fields on rejections. If `no_verbatim_reproduction`
is the most common failure, the probe is correctly catching reproduction
attempts — that's the rubric working as designed, not a problem.

## What NOT to change for the probe

- Don't swap models. The whole point is to test *this* model.
- Don't tweak `max_turns` or `temperature`. Same as current GCSE run.
- Don't add more books mid-run. Two books with clear adversarial framing
  gives clean signal; more books dilutes it.
- Don't extend `max_turns` if you hit `max_turns_exhausted` — the probe is
  a snapshot, not an optimisation exercise.

## After the probe

Whichever outcome you get, write a short `probe-findings.md` noting:
- Total refusals observed
- Distribution across Evans vs Ford
- Any pattern in the chunks that triggered refusals (concrete examples
  from the rejection log)
- The decision taken as a result

This becomes the ADR for the architect-agent domain's Coach model choice
and also feeds into your DDD Southwest talk as a concrete "war story" data
point about alignment-triggered failures in production-adjacent pipelines.
