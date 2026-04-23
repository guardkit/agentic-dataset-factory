---
id: TASK-G4D-006
title: Set-text quote-factuality evaluation (pre- and post-RAG)
status: backlog
created: 2026-04-20T00:00:00Z
priority: medium
tags: [evaluation, factuality, rag, set-texts]
complexity: 3
task_type: evaluation
implementation_mode: manual
parent_review: TASK-REV-G4R2
feature_id: FEAT-G4D
wave: 4
dependencies: [TASK-G4D-003]
---

# Task: Set-text quote-factuality evaluation (pre- and post-RAG)

## Description

During TASK-G4D-002 smoke testing, the fine-tuned Gemma 4 MoE model produced **two fabricated/misquoted set-text quotations** in a single response:

1. Macbeth 1.7 rendered as *"screw your courage to the hope of belief"* — actual text is *"screw your courage to the sticking-place"*.
2. Inspector Goole's final speech rendered as *"We are all members of one body… and we must learn to live together—and not in our own circumstances"* — the actual line continues *"We are members of one body. We are responsible for each other. And I tell you that the time will soon come when, if men will not learn that lesson, then they will be taught it in fire and blood and anguish."*

For a GCSE English tutor, mis-quoting set texts is materially harmful — students memorise the tutor's quotations for exam use. This task designs and runs a structured factuality eval covering the AQA set-text canon, both **before** and **after** RAG grounding (TASK-G4D-003), so we can quantify the delta RAG provides and decide whether additional mitigation (curated quote corpus as a tool, further fine-tuning) is needed.

## Scope: texts to cover

Minimum — one prompt per text, covering a well-known quotable line:

**Literature Paper 1 — Shakespeare & 19th-century novel**
- Macbeth
- Romeo and Juliet
- The Tempest / Much Ado / Merchant of Venice (pick one)
- A Christmas Carol
- Jekyll and Hyde
- Great Expectations
- Jane Eyre

**Literature Paper 2 — Modern text, poetry anthology, unseen poetry**
- An Inspector Calls
- Blood Brothers
- Animal Farm / Lord of the Flies
- AQA Power & Conflict anthology (pick 2-3 poems)
- AQA Love & Relationships anthology (pick 2-3 poems)

Target: ~15 distinct prompts.

## Prompt design

Use prompts that naturally elicit a verbatim quotation, without explicitly asking "quote line X" (that biases the model toward its training-data form). For example:

- "What does Lady Macbeth say to persuade Macbeth to commit the murder in Act 1 Scene 7?"
- "How does Priestley end An Inspector Calls? What's the Inspector's final warning?"
- "What's the most famous line from Scrooge and Marley's first encounter?"

Capture the model's response and extract any text it presents as a verbatim quotation (look for quotation marks or italics).

## Evaluation method

For each extracted quotation:

1. Compare against an authoritative source text (Arden / Cambridge / Penguin editions — cite edition per text).
2. Classify as:
   - **Exact match** — verbatim, including punctuation.
   - **Substantively correct** — wording correct but minor modernisation (e.g. "you" for "thou") or punctuation drift.
   - **Paraphrase presented as quotation** — meaning correct but wording invented.
   - **Fabrication** — wording does not appear in the source.
3. Compute pass rate per category, per text, per run.

## Two-phase execution

**Phase 1 — Pre-RAG baseline** (run before TASK-G4D-003 completes):
- Run all ~15 prompts against `gcse-tutor-gemma4-moe` via `ollama run`.
- Record to `docs/reviews/factuality/pre-rag.md`.
- Produce baseline pass rate.

**Phase 2 — Post-RAG** (run after TASK-G4D-003):
- Same prompts, same model, now with ChromaRAG providing set-text passages as context.
- Record to `docs/reviews/factuality/post-rag.md`.
- Compute delta vs. Phase 1.

## Decision output

Based on the delta:

- If RAG lifts the quote-factuality pass rate to acceptable levels (e.g. ≥ 90% exact-or-substantive), no further mitigation needed.
- If a gap remains, the follow-up options are:
  - Curate a set-text quotation corpus and expose it as an explicit tool (higher precision than free-text RAG for verbatim quotes).
  - A further fine-tuning round that penalises quote fabrication using rejection-sampled preference data.
  - Add a prompt-level guard instructing the model to only quote when the RAG context contains the line verbatim.

## Acceptance Criteria

- [ ] Prompt set (~15 items) designed and documented.
- [ ] Pre-RAG run executed; pass rate recorded in `docs/reviews/factuality/pre-rag.md`.
- [ ] Post-RAG run executed (after TASK-G4D-003); pass rate recorded in `docs/reviews/factuality/post-rag.md`.
- [ ] Delta analysis with go/no-go recommendation for additional mitigation.
