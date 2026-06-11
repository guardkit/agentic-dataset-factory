# YouTube Video — Outline and Script

> Written 2026-06-11. Companion document: [ml-concept-mapping.md](ml-concept-mapping.md)
> (full concept mapping and the stats cited below, with extraction provenance).

## Working titles

1. **"I read one AI paper and built a training-data factory from it — with no ML background"** (transfer-story-led, recommended)
2. "Two AI agents argued for 50 hours. The result fine-tuned my model." (hook-led)
3. "Block's Player-Coach pattern, pointed at fine-tuning data — fully local, full numbers"

## Format

- **Length:** 18–22 minutes
- **Audience:** ML-curious developers + fine-tuning practitioners. Each chapter teaches
  one established ML concept using this repo as the concrete example, so it serves both.
- **Through-line:** "I took Block's adversarial-cooperation pattern out of code
  synthesis and pointed it at training-data generation. Here's the machine, the
  established concepts it's built from, the real numbers, and the failures."
- **Positioning (load-bearing):** this is presented as a **transfer and an engineering
  build, not a new method**. Prior art is named on screen early and deliberately
  (Block's paper, Constitutional AI, STaR, Distilabel, Nemotron) — pre-empting the
  "this already exists" comment is a credibility feature, not a concession. The
  word "novel" does not appear in this video.
- **Secondary hook:** the builder has no ML background — a practitioner read a
  frontier-lab paper and shipped a working transfer of it. That story is more
  repeatable for the audience than any novelty claim.

---

## Chapter structure

### 0. Cold open / hook (0:00–1:15)

**Screen:** Side-by-side demo. Left: the GCSE tutor refusing to give a Year 10 student
the answer about Lady Macbeth, asking a Socratic question instead. Right: the architect
agent reasoning through a monolith-split trade-off with its `<think>` block visible.

**Script:**
> "These two models were fine-tuned on training data that no human wrote. One is a
> Socratic GCSE English tutor — watch it refuse to just give the answer. The other is
> a software architect distilled from nineteen architecture books. The data for both
> came out of the same machine: two AI agents — a Player that writes training examples,
> and a Coach that rejects them — arguing with each other for about fifty hours on the
> computer under my desk. Total API bill: zero.
>
> Here's the part that should encourage you: I'm not a machine-learning researcher.
> The pattern comes from a Block AI Research paper on code synthesis — adversarial
> cooperation, a Player and a Coach. I didn't invent it; I took it and pointed it at
> a different problem: generating fine-tuning datasets. And when I checked the
> literature afterwards, almost every design decision turned out to already have a
> name — Constitutional AI, rejection sampling, distillation. That's the video: the
> machine, the established concepts it's built from, the real numbers, and the three
> failures that taught me the most."

**On-screen citation:** Block AI Research, *Adversarial Cooperation in Code Synthesis*
(Dec 2025) — show the paper title card during this paragraph; link in description.

**On-screen stat card:** `4,100 accepted examples · ~103M tokens · 2 fine-tuned models · $0 API spend`

---

### 1. The problem (1:15–3:00)

**Concept taught:** why fine-tuning is a *data* problem, not a training problem.

- Want: a small model that *behaves* a specific way (Socratic tutor; trade-off-aware
  architect) and runs on-device.
- Unsloth/QLoRA make the training step easy. The bottleneck is thousands of
  high-quality, consistently-formatted, domain-grounded conversation examples.
- Hand-writing 2,000+ examples is not realistic. Scraping gives you the average of the
  internet, not a personality.

**Script beat:**
> "Fine-tuning is ninety percent a data problem. The training run is a solved
> commodity — what's hard is getting two and a half thousand examples that all share
> one voice, one format, and are actually grounded in your source material."

### 2. The machine (3:00–6:30)

**Concept taught:** the Player-Coach loop and where it comes from. **Screen:** the
pipeline diagram from [ARCHITECTURE.md](../architecture/ARCHITECTURE.md), then a live
log tail of one target going generate → revise → accept.

- **The pattern's origin:** Block AI Research's *adversarial cooperation* — a bounded
  Player-Coach feedback loop, originally for code synthesis ("dialectical
  autocoding"). The transfer here: instead of the Player writing code and the Coach
  reviewing implementations, the Player writes training examples and the Coach
  enforces a dataset rubric. Same loop, different payload.
- Stage 0: Docling ingests source PDFs → chunks → ChromaDB.
- Stage 1: for each generation target: Player retrieves grounding context, generates an
  example; Coach scores it against a rubric and returns structured JSON
  (`accept` / `revise` + per-criterion verdicts + feedback); Player revises; max 3
  rounds, then the example is discarded to `rejected.jsonl`.
- Everything about the domain lives in one file: `GOAL.md` — system prompt, generation
  targets table, generation guidelines, evaluation rubric with weights, output schema.
- Role separation is structural: the Coach factory literally has no `tools` parameter —
  it can judge but cannot write ([coach.py](../../agents/coach.py), D5 invariant).

**Script beat:**
> "The Coach can't write files. Not 'is told not to' — it structurally has no tools.
> The judge can't tamper with the exam papers. Keep that thought, because it maps
> straight onto something the LLM-as-judge literature worries about."

### 3. The concept map (6:30–12:00) — the core of the video

**Format:** one card per concept, ~45–60s each. Repo mechanism on the left, named ML
concept + paper on the right. Full table in
[ml-concept-mapping.md](ml-concept-mapping.md).

**Lead-in — the prior-art card (do this first, on purpose).** Name the family this
belongs to before anyone in the comments does: Constitutional AI (critique-revise),
STaR (rejection sampling), Distilabel and Curator (open-source generator+judge
frameworks), NVIDIA's Nemotron-4 synthetic-data pipeline.

> "Quick disclaimer before the concept tour: none of what follows is my invention —
> and that's sort of the point. Tools like Distilabel already chain generators and
> judges; Anthropic published critique-and-revise in 2022. What's different in this
> build is the combination: Block's coach-player pattern, the whole domain defined in
> one declarative spec file, and the entire thing running locally with the numbers
> published. So here's the tour — nine decisions I made by instinct that turn out to
> have names."

1. **Critique-and-revise → Constitutional AI.** The generate → critique → revise loop
   is the supervised phase of Anthropic's Constitutional AI, with GOAL.md's rubric
   playing the role of the constitution.
2. **Quality gate + discard → rejection sampling / STaR.** Sample, score, keep what
   passes. *Stat card: 83.2% acceptance (architect), 68.8% accepted first try, mean
   accept turn 1.39.*
3. **Big model teaching a small one → knowledge distillation.** Qwen 35B writes data,
   Nemotron Nano / Gemma 26B learn from it — the Alpaca/Orca/Phi recipe.
4. **Mandatory RAG before generation → grounded generation.** The Player may not
   invent; the orchestrator pre-fetches curriculum chunks. Controls hallucination AND
   distribution drift.
5. **Behaviour vs knowledge layers → parametric vs non-parametric memory.** Fine-tune
   for *how it behaves*, RAG for *what it knows* — encoded as a metadata field the
   Coach validates per example. *Stat card: architect — 894 behaviour examples to
   train.jsonl, 1,102 knowledge examples to the RAG index.*
6. **`<think>` blocks → chain-of-thought distillation.** Same mechanism as the
   DeepSeek-R1 distills: train on reasoning traces, not just answers.
7. **Generation targets table → dataset curriculum / stratified sampling.** You don't
   scrape a distribution; you *design* one. 275 literary analysis, 250 Macbeth, grade
   targets 4–9...
8. **Player temp 0.7, Coach temp 0.3 → exploration vs judge variance.** And the
   rubric polarises verdicts: *stat card — coach scores: 791× "2", 64× "3",
   2,255× "4–5". A judge that rarely shrugs.*
9. **rejected.jsonl → free DPO preference data.** Every rejection history is an
   (accepted, rejected) pair waiting to be used. *Tease as future work.*

**The credibility moment — script beat:**
> "Now, the analogy you're itching to make is the GAN — generator, discriminator, I
> get it. Resist it. There's no gradient here; the Coach's feedback arrives as
> *language*, not as a loss. The Coach isn't trained adversarially — it's a fixed
> judge with a rubric. And the relationship is cooperative: the Coach's feedback is
> trying to help the Player pass next turn. That's why the pattern is called
> adversarial *cooperation*. The honest description is: generate, critique, revise —
> plus rejection sampling — with natural-language feedback standing in for gradients."

### 4. War stories (12:00–17:00) — the retention segment

**4a. The refusal mystery (the best 3 minutes of the video).**
Run 1 of the GCSE tutor: 98 provider-side refusals. Hypothesis: the model objects to
reproducing copyrighted literature — Macbeth, Dickens. So: a controlled probe. Same
model, same conditions, architecture books instead of literature. 110 targets, two
hours.
> "Result: reasoning-type targets with think blocks — zero refusals out of eighty.
> Direct-type, short factual targets — 13.3% refusals. The hypothesis was dead. It was
> never about Shakespeare. The model balks at short-form factual reproduction, not at
> subject matter. So the architect dataset dropped direct-type entirely — and that
> probe cost two hours and saved the fifty-hour production run."

**Teaching point:** treat your pipeline like an experiment — hypothesis, probe,
decision. ([probe-findings.md](../../domains/architect-agent-probe/probe-findings.md))

**4b. The 28-hour stall.**
The 2500-target run stalled at index 1405: the loop ran on a MacBook over Tailscale and
macOS power management suspended the process. Evidence-trail moment: TCP client ports
changing across the gaps. Lesson: run the loop on the server hosting the LLM, in tmux.
([2500-run-stall-analysis.md](../learnings/2500-run-stall-analysis.md))

**4c. Death by 91 tokens.**
The architect main run crashed after ~41 hours: 65,627 prompt tokens against a 65,536
context window. Ninety-one tokens over. Checkpointing (ADR-ARCH-008/010) meant the
resume run recovered the remaining 402 targets in 9.3 hours with zero loss.
> "Resilience features feel like over-engineering right up until hour forty-one."

**4d. (quick beat) The hardest things to generate.**
The architect's most-rejected category: *applying* complexity principles (59
rejections) — applying is harder than reciting. The tutor's most-rejected:
"Encouragement and study skills" (78) — the pipeline found being encouraging harder to
pass than analysing Macbeth.

### 5. The payoff (17:00–19:30)

- Unsloth QLoRA fine-tune of both models; back-to-back demo: base model vs fine-tuned
  tutor on the same student question — base gives the answer away, tuned one asks the
  scaffolded Socratic question.
- The domain switch was config-only: new GOAL.md + new source PDFs, zero code changes.
- **Stat recap card:** architect — 2,400 targets, 1,996 accepted (83.2%), ~58M tokens,
  ~50h, ~29k tokens per accepted example, $0. GCSE — 2,500 targets, 2,104 accepted
  (84.2%), ~14% multi-turn, 97.6% with think blocks.

### 6. Close (19:30–21:00)

- What's next: DPO from rejected.jsonl; Coach ensembles; new domains.
- Restate the positioning as the takeaway:
> "So, to be clear about what this is and isn't: the method isn't mine — it's Block's
> pattern standing on a decade of synthetic-data research. What I'm offering is the
> transfer, the spec-driven design, the receipts, and the failures. The frontier labs
> run this at billions of tokens; it works at millions, on one box, on your desk.
> If a non-ML person can read one paper and ship this, so can you. Repo linked below."
- CTA: like/subscribe + "tell me what domain you'd point this at."

---

## Production notes

- **B-roll:** live `tail -f` of the structured JSON log during a real target (the
  generate → revise(score=2) → accept(score=5) arc is genuinely watchable); ChromaDB
  ingest run; GB10 on the desk; LangSmith trace of one Player-Coach exchange;
  Unsloth loss curve; the GOAL.md targets table scrolling.
- **Receipts:** every number on screen comes from `run_logs/`, `output/*.jsonl`, or the
  committed findings docs — cite file names on the stat cards for credibility.
- **Description links (positioning support):** Block's Adversarial Cooperation paper
  (https://block.xyz/documents/adversarial-cooperation-in-code-synthesis.pdf),
  Constitutional AI, STaR, Distilabel — the same prior-art list shown on the lead-in
  card. Anyone arriving ready to say "this already exists" should find it already
  cited.
- **Cross-posting:** the same transfer framing is the template for the LangChain,
  NVIDIA forum, and Hugging Face posts — see positioning notes in
  [ml-concept-mapping.md](ml-concept-mapping.md).
- **Do NOT show:** source PDF content (copyrighted — and `domains/*/sources/` is
  gitignored for the same reason); raw chunks in retrieved context.
- **Chapters = YouTube timestamps**; the concept-map segment also cuts cleanly into
  9 shorts (one per concept card), plus the refusal-mystery story as a standalone short.

## Key stats reference (for on-screen cards)

| Card | Value | Source |
|---|---|---|
| Total accepted examples (both domains) | 4,100 | output/train.jsonl + rag_index counts, both runs |
| Architect acceptance rate | 1,996 / 2,400 = 83.2% | run_logs + output file counts |
| Architect first-try acceptance | 68.8%, mean accept turn 1.39 | turn_complete log lines |
| Architect tokens / wall clock | ~58.2M tokens · ~50h · ~75s/target | target_tokens lines + run timestamps |
| GCSE acceptance rate | 2,104 / 2,500 = 84.2% | output_gcse_rerun file counts |
| GCSE first-try acceptance | 75.3%, mean accept turn 1.35 | turn_complete log lines |
| Probe refusal split | reasoning 0/80 (0%) vs direct 4/30 (13.3%) | probe-findings.md |
| Coach score bimodality | 791× s2 · 64× s3 · 1,011× s4 · 1,244× s5 (architect) | turn_complete log lines |
| Context-overflow crash | 65,627 vs 65,536 tokens — 91 over, after ~41h | architect main run log tail |
| API cost | $0 (local llama.cpp/vLLM on GB10) | agent-config / run logs |
