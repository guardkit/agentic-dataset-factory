## Goal

Fine-tune a local model to author and repair **Declarative Capability Language (DCL v1.0)**
capabilities — the closed-vocabulary language for modelling business-system capabilities
(upstream `github.com/russelleast/Capability-Language`, pin `4f9fbe56`). The model turns a
plain-language feature brief into a single capability that compiles clean against the DCL
compiler, and it repairs capabilities the compiler has rejected, changing only what the
diagnostics require. The dataset is built two-sided from day one: **author** examples (brief →
compiler-clean capability, direct) and **repair** examples (a broken capability plus the real
compiler diagnostics → the corrected capability, reasoning). The single load-bearing idea is
that **DCL is a closed vocabulary and the compiler is the only authority** — every label in the
corpus is fixed by the vendored compiler, never by a model, so a row that does not compile
never enters the manifest.

## Source Documents

This domain is **ungrounded** (`grounded: false`, the product-owner precedent): there is no
document corpus to ingest. The only "source" is the compiler-verified closed vocabulary
reference (`src/dcl/vocab-reference.md`, pinned at `4f9fbe56`), which is embedded verbatim into
every author example rather than ingested via Docling. The row below is a required note row, not
a real ingestion target.

| File Pattern | Mode | Notes |
|---|---|---|
| (ungrounded — no document corpus; vocabulary is the compiler-verified reference) | standard | The closed vocabulary reference is embedded per-row from `src/dcl/vocab-reference.md`. No PDFs, no Docling. Grounding is the DCL compiler, not documents. |

## System Prompt

You are an expert author of the Declarative Capability Language (DCL v1.0), a closed-vocabulary language for modelling business-system capabilities. You translate a plain-language feature brief into a single, compiler-clean DCL capability, and you repair capabilities the compiler has rejected.

Your core discipline: **DCL is a closed vocabulary, and the compiler is the only authority.** Every actor kind, effect kind, policy family, policy concern, concern value, field type, observation type, lifecycle step kind, and causation keyword comes from a fixed set given in the vocabulary reference — you never invent a literal outside it. Inventing an actor kind (`is machine`), an effect kind (`is in_memory`), a policy concern, a concern value, or a field type (`String`, `Int`) makes the file fail to compile, even when the invention reads plausibly. A capability that does not compile is worthless.

You reason from the brief to the smallest faithful capability: one actor, a typed intent shape, the declared outcomes, the emitted events, the effects, the governing policy, and — when the brief implies process state — a lifecycle whose `when` block causes every declared outcome. You keep identifiers well-formed, you attach policies to legal targets, and you satisfy the compiler's cross-cutting rules (a retry policy requires an idempotency guarantee on the same target; every declared outcome must be caused in `when`).

When repairing, you read the compiler diagnostics as ground truth: you diagnose the named `DCL_*` error, change only what the diagnostics require, and preserve every unaffected declaration. You never rewrite a capability from scratch to dodge a single defect, and you never introduce a new literal to patch an old one.

## Generation Targets

<!-- Phase-1 OPERATIVE caps (config-capped at run time via generation.limit,
     agent-config.draft.yaml): author 300 / repair 600 (a 2:1 author:repair split).
     The PLANNING table below lists repair 720 rather than 600 for one mechanical reason:
     author rows are `direct` (no <think> block) and repair rows are `reasoning`, and the
     domain-schema rule requires reasoning >= 70% of the total. 600/900 = 66.7% would FAIL
     the GOAL.md validator; 720/1020 = 70.6% clears it with margin. The binding numbers are
     the ratios and the run-time config cap, not the planning totals. -->

| Category | Type | Layer | Count | Grade Targets |
|---|---|---|---|---|
| Author a compiler-clean DCL capability from a plain-language feature brief | direct | behaviour | 300 | [null] |
| Repair a compiler-rejected capability from its verbatim diagnostics, preserving unaffected declarations | reasoning | behaviour | 720 | [null] |

## Generation Guidelines

The Player authors from a brief; the compiler decides truth; a teacher authors only the repair
rationale. These rules are enforced in code (`src/dcl/**`), not by convention.

**Closed-vocabulary discipline (the point).** Author using ONLY the literals in the embedded
vocabulary reference — actor kinds (`human`, `system`, `agent`, `scheduled_process`), effect
kinds (`persistence`, `notification`, `invocation`, `tool`), policy families and their bound
concerns, concern values, field types (`Text`, `Number`, `Uuid`, `Money`, …). Field types in
particular pass the compiler silently in the default (no-`context`) scope, so `String`/`Int`
do not raise — the Coach MUST check field types against the reference by eye, because the
compiler will not.

**Compile gate (mandatory).** Every author example is compiled by the vendored DCL compiler
(`src/dcl/bin`, pin `4f9fbe56`) before it can be accepted. A capability that does not compile is
sent back with its verbatim diagnostics for up to `max_format_retries` repair-style retries, then
rejected. The accepted text is the compiler-fixed label — never a model's say-so.

**Repair examples are reasoning-typed.** The user turn carries the broken `.dcl` plus the
VERBATIM compiler diagnostics JSON; the assistant turn is a `<think>` rationale that names the
`DCL_*` error and the minimal fix, then ONE fenced `dcl` block whose text equals the
pre-injection original **by construction** (semantic preservation is guaranteed, not hoped).

**Fence integrity.** Author assistant turns are exactly one ```` ```dcl ```` fenced capability
and NO `<think>` block (direct). Repair assistant turns are a `<think>` block then exactly one
```` ```dcl ```` fenced capability (reasoning).

**Hold-out discipline.** The four frozen `dcl-heldout` exam capabilities (stats/version/uptime/
GetStats) are the eval and are NEVER trained. No brief, source, or emitted row may match a
hold-out by content (sha256) or identity (capability/endpoint name) — refused loudly in
`src/dcl/contamination.py`. Rows destined for eval are named `split: eval_dcl` at creation.

**Datasets stay private (DF-008).** No row content leaves the fleet.

## Evaluation Criteria

The rubric the Coach uses to evaluate each generated example. Criterion names are valid Python
identifiers used as keys in the Coach's `criteria_met` response.

| Criterion | Description | Weight | Layer |
|---|---|---|---|
| brief_fidelity | The capability models the brief: the named actor and kind, the intent shape and its typed fields, the declared outcomes, the emitted event and its fields, the policy family+concern, and the lifecycle are all present and faithful to the brief — no invented scope, no dropped requirement. | 30% | behaviour |
| vocabulary_discipline | Only compiler-verified closed-vocabulary literals are used. Because field types pass the compiler silently in the default context, the Coach checks every field type against the reference explicitly — `String`/`Int`/`Float` and any out-of-set actor/effect/concern literal is a failure even if the file compiled. | 30% | behaviour |
| fence_integrity | Assistant content carries exactly one ```` ```dcl ```` fenced capability; author rows carry no `<think>` block, repair rows carry a non-empty `<think>` block before the fence. Malformed or missing fences are a failure. | 15% | behaviour |
| semantic_preservation | For repair rows, the corrected capability changes only what the diagnostics require and preserves every unaffected declaration — never a rewrite-from-scratch. | 15% | behaviour |
| compile_clean | The emitted (author) or corrected (repair) capability compiles clean against the vendored DCL compiler with zero error diagnostics. This is verified deterministically, not judged. | 10% | all |

## Output Schema

Each example is a ShareGPT-envelope JSON object (`messages` + `metadata`). The assistant content
is a fenced `dcl` capability (author: direct, no think block; repair: `<think>` then fence).

```json
{
  "messages": [
    {"role": "system", "content": "<the DCL authoring system prompt above>"},
    {"role": "user", "content": "## Feature brief\n<brief>\n\n## DCL vocabulary reference (closed)\n<vocab>\n\n## Task\nAuthor a single DCL capability ..."},
    {"role": "assistant", "content": "```dcl\nlanguage dcl 1.0\n...\n```"}
  ],
  "metadata": {
    "row_id": "dcl-<sha256[:16] of the user message>",
    "domain": "dcl-capability-language",
    "layer": "behaviour",
    "type": "direct",
    "mode": "dcl_author",
    "split": "train",
    "recipe_id": null,
    "provenance": {"source": "synthetic-brief", "vocab_pin": "4f9fbe56", "compiler_pin": "4f9fbe56"},
    "compile_verified": true
  }
}
```

## Metadata Schema

Per-example metadata fields with constrained valid values. Every field is required (the key is
always present; `recipe_id` is `null` on author rows).

| Field | Type | Required | Valid Values |
|---|---|---|---|
| row_id | string | yes |  |
| domain | string | yes | dcl-capability-language |
| layer | string | yes | behaviour, knowledge |
| type | string | yes | direct, reasoning |
| mode | string | yes | dcl_author, dcl_repair |
| split | string | yes | train, eval_dcl |
| recipe_id | string | yes |  |
| compile_verified | boolean | yes |  |

## Layer Routing

Routes generated examples to output files. This domain emits only behaviour examples; the
knowledge route exists for schema compatibility and is unused (no RAG layer for DCL).

| Layer | Destination | Purpose |
|---|---|---|
| behaviour | output/dcl-capability-language/train.jsonl | The fine-tune: authoring + repair of compiler-clean DCL capabilities. Split `eval_dcl` rows route to `output/dcl-capability-language/eval_dcl.jsonl`. |
| knowledge | output/dcl-capability-language/rag_index/knowledge.jsonl | Unused for DCL — no knowledge/RAG layer. Present for schema compatibility only. |
