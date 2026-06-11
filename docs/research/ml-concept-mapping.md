# ML Concept Mapping — Validating the Player-Coach Pipeline Against the Literature

> Written 2026-06-11. Purpose: validate that the concepts used in this repo map to
> established machine-learning techniques, as groundwork for a YouTube video about
> the project. Companion document: [youtube-video-outline.md](youtube-video-outline.md).

## TL;DR

The Player-Coach pattern itself comes from Block AI Research's
[*Adversarial Cooperation in Code Synthesis*](https://block.xyz/documents/adversarial-cooperation-in-code-synthesis.pdf)
(Dec 2025), where it drives a code-generation/review loop ("dialectical autocoding").
This repo's contribution is a **transfer, not an invention**: the same bounded
Player-Coach loop applied to fine-tuning dataset generation, where it lands squarely
in the established synthetic-data family (Constitutional AI critique-revise, rejection
sampling, knowledge distillation, chain-of-thought distillation, LLM-as-judge).
Two fine-tuned models produced from its output (architect-agent and GCSE English
tutor) demonstrate that the pipeline works end-to-end.

Two framings to avoid in public write-ups: the GAN analogy (see
[Precision matters](#precision-matters-this-is-not-a-gan)) and any claim of a novel
*method* (see [Prior art and positioning](#prior-art-and-positioning)). The honest
claim — "Block's pattern, transferred to dataset generation, spec-driven, fully
local, with published numbers and failures" — is also the strongest one.

## Concept Mapping

| This repo | Established ML concept | Canonical references |
|---|---|---|
| The Player-Coach loop itself | **Adversarial cooperation** — bounded coach-player feedback loop, originally for code synthesis | Block AI Research 2025 (*Adversarial Cooperation in Code Synthesis*) — the pattern's direct source |
| Player generates → Coach critiques with structured JSON → Player revises (max 3 rounds) | **Critique-and-revise loops** — the supervised phase of Constitutional AI; also Self-Refine | Bai et al. 2022 (Constitutional AI); Madaan et al. 2023 (Self-Refine) |
| Coach as quality gate; discard to `rejected.jsonl` after max turns | **Rejection sampling / filtered self-generation** — sample, score, keep only what passes | Zelikman et al. 2022 (STaR); Llama 2/3 post-training reports |
| Larger generator model produces data for a smaller fine-tune target (Qwen 35B → Nemotron Nano; Qwen3.6 → Gemma 4 26B) | **Knowledge distillation via synthetic data** (teacher–student) | Alpaca 2023; Orca 2023; Phi "Textbooks Are All You Need" 2023; NVIDIA Nemotron-4 synthetic-data pipeline |
| Mandatory RAG retrieval before generation; orchestrator pre-fetches curriculum context | **Grounded generation** — anchoring the generator in source material to control hallucination and distribution drift | Retrieval-augmented distillation; RAG (Lewis et al. 2020) |
| Behaviour layer → `train.jsonl` (fine-tune), knowledge layer → `rag_index/knowledge.jsonl` (RAG) | **Parametric vs non-parametric memory** — fine-tune for behaviour/form, RAG for facts | Standard SFT-vs-RAG guidance; Lewis et al. 2020 |
| `<think>` blocks required in reasoning-type examples | **Chain-of-thought distillation** — training on reasoning traces | DeepSeek-R1 distillations 2025; s1 (Muennighoff et al. 2025) |
| GOAL.md Generation Targets table (categories, counts, grade targets) | **Dataset curriculum / stratified sampling** — deliberately controlling the training distribution | Data-centric AI practice; curriculum construction in Phi/Cosmopedia |
| Player temperature 0.7 / Coach temperature 0.3 (ADR-ARCH-009) | **Exploration vs evaluation-variance control** — diverse sampling on the generator, low-variance judging | LLM-as-judge consistency literature (MT-Bench, Zheng et al. 2023) |
| Weighted Evaluation Criteria in GOAL.md; CoachVerdict JSON schema | **Hand-built scoring/reward function** — the declarative analogue of a reward model in RLHF; rubric-based LLM-as-judge | Zheng et al. 2023; RLHF reward modelling |
| `rejected.jsonl` with rejection histories, scores, and reasons | **Hard negatives / error analysis** — and accepted-vs-rejected pairs are natural **DPO preference data** (unexploited so far) | Rafailov et al. 2023 (DPO) |
| Role separation enforced structurally (Coach has no tools — D5 invariant) | **Evaluator independence** — preventing judge contamination/collusion, an LLM-as-judge reliability concern | Judge-bias literature; separation of generator and verifier |
| Non-deterministic generation + Coach gate instead of seeding (ADR-ARCH-009) | **Sample-and-filter** rather than deterministic reproduction — quality via the gate, not via the seed | STaR; best-of-n sampling |

## Precision matters: this is NOT a GAN

The analogy an ML audience will reach for first is the GAN (generator/discriminator),
and it is the loosest fit:

- **No gradient signal.** The Coach's feedback reaches the Player as natural language,
  not as a backpropagated loss. Nothing is trained during the loop.
- **The Coach is not trained adversarially.** It is a fixed judge with a declarative
  rubric, not a discriminator co-evolving with the generator.
- **The relationship is cooperative.** The Coach's rejection feedback is designed to
  help the Player succeed on the next turn — hence the repo's own term,
  *adversarial cooperation*.

Honest description: **generate–critique–revise plus rejection sampling, with
natural-language feedback in place of gradients.** Making this distinction explicitly
is a credibility win with an ML audience, not a weakness.

## Prior art and positioning

Checked 2026-06-11. The generator+judge synthetic-data pipeline is established
territory; do not claim a novel method in any public post. Known neighbours:

| Prior art | What it is | How this repo differs |
|---|---|---|
| [Block — Adversarial Cooperation in Code Synthesis](https://block.xyz/documents/adversarial-cooperation-in-code-synthesis.pdf) (Dec 2025) | The Player-Coach pattern, for code synthesis | Same loop, different payload: training examples instead of code; rubric instead of code review. **No published application of this pattern to dataset generation was found** — the transfer is the contribution |
| [Distilabel](https://argilla.io/blog/synthetic-data/) (Argilla) | Open-source generator+judge synthetic-data pipelines | Python pipeline API vs this repo's declarative GOAL.md spec; no behaviour/knowledge routing; no bounded revise loop per example |
| Curator (Bespoke Labs) | Open-source synthetic-data synthesis framework | Same as above — framework, not spec-driven factory |
| Constitutional AI (Bai et al. 2022) | Generate → critique → revise against a constitution | This repo's loop is its supervised phase with GOAL.md as the constitution |
| STaR / Llama post-training | Sample-and-filter rejection sampling | This repo adds natural-language revision between samples |
| NVIDIA Nemotron-4 pipeline | Industrial-scale synthetic data generation | Billions of tokens, cluster-scale; this repo is millions of tokens on one box |
| [CPMöbius](https://arxiv.org/html/2602.02979) (Feb 2026) | Coach-Player loop for data-free RL curriculum | RL with trained Coach/Player policies; this repo is fixed models + SFT dataset output |

**Positioning for forum posts (LangChain, NVIDIA, Hugging Face, r/LocalLLaMA):**
lead with the prior-art comparison, the numbers, and the failures — "working
implementation + receipts + lessons", never "novel method". The differentiators to
emphasise are the four points below, plus the refusal-probe finding, which is a
genuinely unpublished empirical datapoint.

## What is genuinely distinctive here

1. **Domain-agnostic by configuration.** Switching from GCSE English tutoring to
   software architecture was a new `GOAL.md` + source PDFs, not new code. The GOAL.md
   is simultaneously dataset card, generation spec, and reward rubric.
2. **The two-layer routing decision** (behaviour → fine-tune, knowledge → RAG) encodes
   the parametric/non-parametric split as a first-class metadata field that the Coach
   validates per example.
3. **Fully local at meaningful scale.** ~58M tokens processed for the architect run on
   a single GB10 (DGX Spark) with zero API spend.
4. **Empirical findings with data**, documented as they happened (see below).

## Empirical findings (war stories with numbers)

- **Refusal probe** ([probe-findings.md](../../domains/architect-agent-probe/probe-findings.md)):
  provider-side refusals correlate with *direct/factual short-form generation*
  (13.3% refusal rate), not with copyrighted subject matter — reasoning-type targets
  with `<think>` blocks had a 0.0% refusal rate across 80 targets. Result: the
  architect spec dropped direct-type categories entirely.
- **28-hour stall** ([2500-run-stall-analysis.md](../learnings/2500-run-stall-analysis.md)):
  the GCSE 2500-run stalled at index 1405 because the orchestrating process ran on a
  MacBook that macOS suspended. Led to ADR-ARCH-010 (retry, checkpoint, per-target
  timeout) and the rule: run the loop on the server hosting the LLM.
- **Context overflow at 91 tokens** (run_logs/architect-generation-20260429-175200.log):
  the architect main run crashed after ~41 hours at 65,627 prompt tokens against a
  65,536 context limit. Checkpoint/resume (ADR-ARCH-008/010) recovered the remaining
  402 targets in a 9.3-hour resume run with zero data loss.
- **Chat template leak** ([DATASET-FIX-tutor-template-leak.md](../../domains/architect-agent-probe/DATASET-FIX-tutor-template-leak.md)):
  motivated the `gemma-4` (not `gemma-4-thinking`) chat template choice for the
  architect fine-tune.

## Run statistics (extracted from logs and output files, 2026-06-11)

### Architect-agent production run (Apr 29 – May 2, 2026)

Model: `qwen36-workhorse` via llama-swap/llama.cpp on GB10, Player temp 0.4, Coach temp 0.3.

| Metric | Value |
|---|---|
| Targets | 2,400 |
| Accepted | **1,996 (83.2%)** — 894 behaviour + 1,102 knowledge |
| Rejected | 403 (400 max-turns-exhausted, 2 verdict-parse failures, 1 timeout) |
| First-try acceptance | **68.8%** (1,551 of 2,255 accepts on turn 1; 537 turn 2; 167 turn 3) |
| Mean accept turn | 1.39 |
| Coach decisions | 2,255 accept / 960 revise |
| Coach score distribution | 1: 105 · 2: 791 · 3: 64 · 4: 1,011 · 5: 1,244 (strongly bimodal — the rubric polarises verdicts) |
| Tokens | ~48.3M prompt + ~9.9M completion ≈ **58.2M total** (~29k tokens per accepted example) |
| Wall clock | ~41h main run (crashed on context overflow) + 9.3h resume ≈ **50h** (~75s/target) |
| API cost | **$0** — fully local |
| Hardest category | "Complexity management — applying complexity principles to real designs" (59 rejections) |
| Dataset shape | 100% reasoning-type with `<think>` blocks; avg assistant response ~5,000 chars |

### GCSE English tutor rerun (early April 2026)

Model: Qwen3.5-35B-A3B-FP8, fine-tune target Nemotron 3 Nano 30B-A3B.

| Metric | Value |
|---|---|
| Targets | 2,500 |
| Accepted | **2,104 (84.2%)** — 1,736 behaviour + 368 knowledge |
| Rejected | 457 (311 max-turns, 125 Coach empty-content refusals, 21 Player failures) |
| First-try acceptance | **75.3%** (1,201 of 1,595 logged accepts on turn 1); mean accept turn 1.35 |
| Multi-turn examples | 245 of 1,736 train examples (~14%) |
| `<think>` coverage | 1,695 of 1,736 train examples (97.6%); knowledge layer 0% by design (direct-type) |
| Tokens (two logged segments) | ~44.8M total |
| Wall clock (logged segments) | 50.4h for 1,546 targets + 20.3h for final 622 |
| Hardest category | "Encouragement and study skills" (78 rejections) — the model found *being encouraging* harder to pass than analysing Macbeth |

### Probe run (Apr 26, 2026)

110 targets in ~2.0h: 0/80 refusals on reasoning-type, 4/30 (13.3%) on direct-type.
Hypothesis "refusals are literature-specific" **rejected**.

## Conclusion for the video

The video concept is validated on three grounds:

1. **Conceptual rigour** — every major design decision maps to a named, citable
   technique; the mapping table above is the video's backbone.
2. **Proof** — two working fine-tuned models in different domains, with the domain
   switch being config-only.
3. **Differentiated content** — real numbers, real failures, local hardware, at a
   scale a viewer can reproduce. Most fine-tuning content has none of these.

**Framing (final):** the story is a *transfer* — "a practitioner with no ML
background read Block's adversarial-cooperation paper and pointed the pattern at a
new problem, and it worked, twice." That framing is more credible than a novelty
claim, pre-empts the "this already exists" objection by citing the existing work
first, and is a more repeatable story for the audience. The word "novel" should not
appear in the video or in any forum post.
