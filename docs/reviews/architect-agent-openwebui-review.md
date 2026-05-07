# Review — architect-agent in OpenWebUI (first conversations)

**Reviewed:** 2026-05-06
**Source transcript:** [`architect-agent-openwebui.md`](architect-agent-openwebui.md)
**Model under review:** fine-tuned Gemma-4-26B-A4B-it (architect-agent), served via llama-swap, accessed through OpenWebUI
**Related followup:** [`FOLLOWUP-chat-template-thinking-tags.md`](../../domains/architect-agent/FOLLOWUP-chat-template-thinking-tags.md)

---

**Bottom line:** the fine-tune is *working*. Persona is sharp, references are consistent, and reasoning is on-brand. But there's one visible generation defect, and four content-shape gaps that matter for the next training iteration.

---

## What's working

- **Persona is locked in.** Across 4 turns the model consistently uses the architect framing: forces in tension, trade-off explicitness, complexity-as-cost, reversibility heuristic. This is exactly what [`domains/architect-agent/GOAL.md`](../../domains/architect-agent/GOAL.md) was aiming for.
- **Authority references land naturally**: Evans (bounded contexts, ubiquitous language, anti-corruption layer), Ford (fitness functions, evolutionary architecture), Ousterhout (deep modules), Beck (tidying), Kleppmann (partitioning), Team Topologies (interaction modes), Conway's Law. All cited *in service of an argument*, not name-dropped. This is the strongest evidence the SFT corpus shaped behaviour.
- **The strategic-vs-tactical heuristic** at [architect-agent-openwebui.md:152](architect-agent-openwebui.md#L152) ("If we need to reverse this in six months, how much work?") is the kind of crisp, transferable rule a working architect would actually use.
- **Cross-turn coherence** — turns 2→5 build on each other (constraints → strategic/tactical → bounded contexts → e-commerce worked example) without contradiction. The fine-tune isn't just one-shot persona; it sustains the frame.
- **The e-commerce worked example** at [architect-agent-openwebui.md:218-260](architect-agent-openwebui.md#L218-L260) is the strongest single answer: every strategic decision gets an explicit *trade-off you accept*, every tactical decision is justified by *why reversal is contained*. This is the agent doing what the spec asks.

---

## Defects worth fixing

### 1. Turn 1 is truncated mid-sentence

[architect-agent-openwebui.md:54-60](architect-agent-openwebui.md#L54-L60):

> "Ask for the 'why,' not just the 'what': I'll always show my reasoning in the \`"

Then a stray "Thought for less than a second" follows. The response ends inside an unclosed code-fence backtick. Possible causes:

- token limit hit on the OpenWebUI side
- the agent started emitting an example (`<think>`?) and a stop sequence cut it
- OpenWebUI's UI swallowed a partial second turn

This is the *first thing a new user sees* on first contact with the agent. Worth checking the OpenWebUI generation settings (max_tokens, stop sequences) before any further demos. Likely the same family of issue tracked in [`FOLLOWUP-chat-template-thinking-tags.md`](../../domains/architect-agent/FOLLOWUP-chat-template-thinking-tags.md) — the model may be producing native `<|channel>thought<channel|>` framing that the UI is mis-rendering or truncating at.

### 2. One typo in model output: "trade-0ff"

[architect-agent-openwebui.md:81](architect-agent-openwebui.md#L81). Single instance, low priority — a generation glitch (zero-vs-o), not a training data issue worth chasing.

---

## Content gaps for the next iteration

### 3. The agent says "challenge my reasoning" but never challenges the user

At [architect-agent-openwebui.md:53](architect-agent-openwebui.md#L53) it explicitly invites pushback. But across 5 turns it never:

- asks a clarifying question back
- pushes on a vague constraint ("4 developers" → *what's their experience? are they co-located?*)
- flags that the user's own framing has a hidden assumption

This is the asymmetry the Player-Coach pattern is supposed to *avoid*. If the architect-agent is meant to be the **Player** for an architectural decision pipeline, it shouldn't behave like a polite essayist. **Recommendation for the next training corpus:** seed examples where the agent refuses to answer until missing constraints are surfaced, or where it surfaces an unstated alternative the user didn't list.

### 4. Structural monotony — every answer is "5 numbered sections + closing meta-paragraph"

Look at the shape of turns 1, 2, 3, 4, 5 — they're nearly identical templates. After 4 exchanges this becomes predictable and starts to feel like a wrapper rather than an interlocutor. Consider mixing in training examples with: tight 2-paragraph answers, explicit "I don't have enough to answer this yet" responses, and ADR-shaped outputs (Context / Decision / Consequences).

### 5. No artefact production

The agent never produces:

- an ADR draft
- a Mermaid diagram (bounded contexts, event flows)
- a fitness-function expression
- a decision matrix

For a **working** architect agent these are the deliverables. Right now it can *talk about* architecture but doesn't *produce architecture documents*. If the goal is OpenWebUI conversational tutoring this is fine; if the goal is to drop into a real workflow, the next training iteration should include artefact-generation examples.

### 6. Implicit reasoning, no `<think>` tags

Already known and well-documented in [`FOLLOWUP-chat-template-thinking-tags.md`](../../domains/architect-agent/FOLLOWUP-chat-template-thinking-tags.md). The OpenWebUI "Thought for 2 seconds" line confirms the platform *is* exposing some thinking metadata, just not the literal `<think>` content. Path B in the followup (re-train with `--chat-template gemma-4` non-thinking) remains the right call before the next domain.

---

## Suggested next steps (in priority order)

1. **Reproduce and diagnose the truncation in turn 1** — likely OpenWebUI max_tokens or stop-sequence config; takes 5 minutes.
2. **Run path-B smoke test** from the followup brief — 60 steps, see if literal `<think>` tags emit.
3. **Add ~50 training examples to the corpus** that exercise: clarifying questions back to the user, refusal-to-answer with constraint-elicitation, and ADR-format output. Then re-train.
4. **Vary response shape** in the corpus — currently the corpus likely has too-uniform 5-section answers. Mix in 2-paragraph and 1-paragraph answers.

The fine-tune is a clear success on persona and reasoning shape. The gaps above are about turning a *good talker* into a *good interlocutor*, which is the next step.
