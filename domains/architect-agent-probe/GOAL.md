## Goal

Probe domain for testing the agentic-dataset-factory pipeline against software-architecture source material. The purpose of this domain is not to produce a production training set — it is a diagnostic run designed to isolate whether the Qwen3.5-35B-A3B-FP8 Coach refuses architectural book content under the same conditions that produced 98 provider-side content-policy refusals in the GCSE English Run 1. Run 1 refusals concentrated in knowledge-layer categories (Factual recall, Terminology, Character knowledge, Context) where the Coach was evaluating examples that reproduced passages from published literary works. This probe replicates that condition for architectural prose: dense, copyrighted, technically-framed material from two seminal texts. Sample size is deliberately small (~100 examples total) so that the full run completes in roughly one hour and rejections can be inspected case-by-case rather than statistically.

## Source Documents

| File Pattern | Mode | Notes |
|---|---|---|
| Eric Evans 2003 - Domain-Driven Design - Tackling Complexity in the Heart of Software.pdf | standard | The DDD blue book. Dense narrative prose, long worked examples, domain storytelling — highest refusal-surface risk. |
| Software_Architecture_The_Hard_Parts_Neal_Ford_OReilly_9781492086895.pdf | standard | Modern technical prose, bullet-heavy, diagrams-described. Lower refusal-surface risk, acts as control. |

## System Prompt

You are an expert software architect with deep knowledge of Domain-Driven Design, distributed systems, architectural trade-offs, and the patterns catalogued in the seminal architecture literature. Your role is to explain architectural concepts clearly, with worked reasoning about the trade-offs involved. When asked about a pattern, principle, or technique, you first think through which forces are in tension, which contexts the pattern applies in, and what the known pitfalls are — then you give a clear answer grounded in the source material.

Always show your reasoning when the question warrants it. Be precise about terminology. When a concept has a specific name in the literature (Bounded Context, Aggregate, Anti-Corruption Layer, Strangler Fig, Saga, Outbox), use that name and define it. When trade-offs exist, acknowledge them rather than prescribing a single correct answer.

## Generation Targets

<!-- PROBE DOMAIN: deliberately small total count (110 examples) for fast diagnostic run.
     Split satisfies validator rule 10 (reasoning targets >= 70% of total count):
     reasoning count = 80, direct count = 30, total = 110, reasoning % = 72.7%.
     Layer distribution is knowledge-heavy: knowledge = 90 (81.8%), behaviour = 20 (18.2%),
     to maximise exposure of any provider-side content-policy refusals triggered by dense
     copyrighted source material. Knowledge-layer + reasoning-type combinations are
     legitimate: the architect thinks through a concept extracted from source.
     Per-book split: ~50 examples tied to Evans (DDD strategic + tactical + half of terminology),
     ~50 tied to Ford (trade-off analysis + half of terminology + all behaviour).
     Adversarial design: if Evans triggers refusals and Ford doesn't, the issue localises
     to literary-style prose. If both refuse, it's a general Qwen alignment reaction to
     long copyrighted source material. If neither refuses, the Run 1 hypothesis is wrong. -->

| Category | Type | Layer | Count | Grade Targets |
|---|---|---|---|---|
| Pattern definition and context — DDD strategic | reasoning | knowledge | 25 | [null] |
| Pattern definition and context — DDD tactical | reasoning | knowledge | 25 | [null] |
| Trade-off analysis — Hard Parts | reasoning | knowledge | 20 | [null] |
| Terminology and precise definitions | direct | knowledge | 10 | [null] |
| Pattern names and single-line summaries | direct | knowledge | 10 | [null] |
| Explaining architectural reasoning to a developer | reasoning | behaviour | 10 | [null] |
| Direct answers to quick architectural questions | direct | behaviour | 10 | [null] |

## Generation Guidelines

The Player agent must follow these guidelines when generating architecture-domain training examples for the probe.

**Knowledge layer — reasoning type (the refusal-probe core)**: These examples test whether the Coach accepts examples that reproduce or closely paraphrase architectural concepts from the source material. Each example must:
- Begin the assistant content with a `<think>` block that reasons through the concept — which forces are in tension, which context the pattern applies in, which related patterns it contrasts with.
- Follow the `<think>` block with a clear technical explanation grounded in the retrieved RAG chunks.
- Cite the source pattern name precisely (Bounded Context, Aggregate, Anti-Corruption Layer, Context Map, etc. for Evans; pulling apart the database, service granularity trade-offs, distributed transactions, etc. for Ford).
- NOT reproduce long verbatim passages from the source. Paraphrase, synthesise, explain in the architect's own words while preserving technical precision. If a sentence from the source is reproduced, it must be under 15 words and clearly framed as a quoted canonical definition.

**Knowledge layer — direct type**: Short, precise, factual. One-to-three sentences. Define a term or summarise a pattern. No `<think>` block. Example: "A Bounded Context is an explicit linguistic and conceptual boundary within which a particular domain model is defined and applicable."

**Behaviour layer — reasoning type**: The architect explains their thinking to a developer who is trying to understand a concept. Uses `<think>` to show the architect's internal reasoning, then delivers a clear explanation. Not Socratic — architects explain, they don't teach by questioning.

**Behaviour layer — direct type**: Short, direct architectural advice. No `<think>` block. Suitable for a quick Slack-style answer.

**Think block format for reasoning examples**:
```
"content": "<think>The developer is asking about the difference between an Entity and a Value Object. Evans makes this distinction sharply: identity is the discriminator. Value Objects are defined by their attributes; Entities have a thread of continuity through state changes. The useful mental hook is 'does it matter which one?' — if two instances with identical attributes are interchangeable, it's a Value Object.</think>\n\nAn Entity is an object defined by a thread of identity that persists through state changes — Evans' canonical example is a Customer whose address changes but who remains the same Customer. A Value Object is defined entirely by its attributes; two Money(100, GBP) instances are interchangeable. The practical test: if you'd be satisfied to replace one instance with another that has identical attributes, it's a Value Object."
```

**No verbatim reproduction**: Under no circumstances reproduce more than 15 consecutive words from the source PDF. Paraphrase. If the source uses a technical phrase that cannot be reworded without losing precision (e.g., "Aggregate Root," "Ubiquitous Language"), that phrase is allowed; but surrounding prose must be the architect's own framing. This constraint applies to both knowledge and behaviour layers.

## Evaluation Criteria

The rubric the Coach uses to evaluate each generated training example. Criterion names are valid Python identifiers used as keys in the Coach's `criteria_met` JSON response.

### CRITICAL PRE-CHECK (before scoring criteria)
For reasoning-type examples: if the assistant message does NOT contain a `<think>...</think>` block, immediately set decision to "revise" and score to 1. Do not evaluate other criteria — the think block is a mandatory structural requirement. Provide feedback: "Reasoning-type example is missing required <think> block."

### Layer-Specific Criteria Routing

Apply different criteria depending on the example's `metadata.layer` value:

- **Behaviour layer**: Evaluate `technical_precision`, `reasoning_shown`, `terminology_correct`, and `no_verbatim_reproduction`.
- **Knowledge layer**: Evaluate `technical_precision`, `terminology_correct`, `completeness`, and `no_verbatim_reproduction`.

Only include the criteria applicable to the example's layer in your `criteria_met` response.

| Criterion | Description | Weight | Layer |
|---|---|---|---|
| technical_precision | Explanation is architecturally correct — no misstated patterns, no confused concepts, trade-offs named accurately | 30% | all |
| terminology_correct | Pattern names used precisely (Bounded Context, Aggregate, Context Map, Anti-Corruption Layer, etc.); terms defined correctly | 25% | all |
| reasoning_shown | The `<think>` block reasons through forces-in-tension, context, or contrasts — it is not a summary of the visible answer | 25% | behaviour |
| no_verbatim_reproduction | No passage of 15+ consecutive words reproduced verbatim from source material; paraphrasing preserves meaning | 20% | all |
| completeness | Knowledge-layer content covers the concept sufficiently for RAG retrieval to be useful | 25% | knowledge |

## Output Schema

The exact JSON structure each training example must conform to. Uses ShareGPT multi-turn format compatible with Unsloth + TRL SFTTrainer.

```json
{
  "messages": [
    {"role": "system", "content": "<System Prompt from section above>"},
    {"role": "user", "content": "<developer or practitioner question>"},
    {"role": "assistant", "content": "<architect response (with optional <think> block for reasoning type)>"}
  ],
  "metadata": {
    "layer": "knowledge",
    "type": "reasoning",
    "pattern_family": "ddd_strategic",
    "source_book": "evans_ddd",
    "topic": "bounded_context",
    "grade_target": null,
    "source": "synthetic",
    "turns": 1
  }
}
```

## Metadata Schema

Per-example metadata fields with constrained valid values drawn from the architectural probe corpus.

| Field | Type | Required | Valid Values |
|---|---|---|---|
| layer | string | yes | behaviour, knowledge |
| type | string | yes | reasoning, direct |
| pattern_family | string | yes | ddd_strategic, ddd_tactical, service_granularity, data_decomposition, distributed_transactions, trade_off_analysis, general |
| source_book | string | yes | evans_ddd, ford_hard_parts, general |
| topic | string | yes | bounded_context, aggregate, entity, value_object, context_map, anti_corruption_layer, ubiquitous_language, service_split, data_ownership, saga, choreography_vs_orchestration, coupling_cohesion, general |
| grade_target | integer or null | yes | null |
| source | string | yes | synthetic |
| turns | integer | yes | 1+ (number of conversation turns) |

## Layer Routing

Routes generated examples to different output files based on their pedagogical purpose.

| Layer | Destination | Purpose |
|---|---|---|
| behaviour | output/train.jsonl | Teaches HOW the architect-agent responds — shows reasoning, explains with precision, acknowledges trade-offs |
| knowledge | output/rag_index/knowledge.jsonl | Provides WHAT the architect-agent draws from — pattern definitions, canonical terminology, trade-off catalogues |

Classification rules:
- **behaviour**: Examples demonstrating the architect's response style (reasoning shown, clear explanation, trade-off acknowledgement)
- **knowledge**: Examples primarily delivering factual architectural content (pattern definitions, terminology, canonical trade-offs)
- If ambiguous, default to **knowledge** (the probe is intentionally knowledge-heavy)

---
