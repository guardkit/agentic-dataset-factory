---
id: TASK-G4D-002
title: Register model in Ollama and run smoke tests
status: completed
created: 2026-04-19T00:00:00Z
completed: 2026-04-20T00:00:00Z
priority: high
tags: [deployment, ollama, smoke-test]
complexity: 2
task_type: implementation
implementation_mode: manual
parent_review: TASK-REV-G4R2
feature_id: FEAT-G4D
wave: 2
dependencies: [TASK-G4D-001]
---

# Task: Register model in Ollama and run smoke tests

## Description

Register the transferred GGUF model in Ollama on MacBook Pro and verify it works with qualitative smoke tests before setting up the full RAG pipeline. This follows TASK-REV-G4R2 Recommendation 2: test the model's persona before investing time in ChromaRAG/Open WebUI setup.

## Steps

1. **Check and fix the Modelfile FROM path**:
   ```bash
   cat ~/Models/gcse-tutor-gemma4-26b-moe/Modelfile
   # If FROM points to DGX path, fix it:
   sed -i '' 's|FROM .*|FROM ./gemma-4-26b-a4b-it.Q4_K_M.gguf|' \
     ~/Models/gcse-tutor-gemma4-26b-moe/Modelfile
   ```

2. **Create the Ollama model**:
   ```bash
   cd ~/Models/gcse-tutor-gemma4-26b-moe
   ollama create gcse-tutor-gemma4-moe -f Modelfile
   ```

3. **Verify model is listed**:
   ```bash
   ollama list
   ```

4. **Run smoke tests** (from TASK-REV-G4R2 Recommendation 2):

   | # | Category | Prompt |
   |---|----------|--------|
   | 1 | Literature | "I'm studying Macbeth. What makes Lady Macbeth's sleepwalking scene important?" |
   | 2 | Language | "How do I structure a Paper 1 Question 5 creative writing response?" |
   | 3 | Mark scheme | "What's the difference between a Grade 5 and Grade 9 answer for AO2?" |
   | 4 | Socratic | "Just tell me the answer to this question about An Inspector Calls" |
   | 5 | Boundary | "Can you help me with my maths homework?" |

   Run each via:
   ```bash
   ollama run gcse-tutor-gemma4-moe "<prompt>"
   ```

5. **Evaluate responses** against these criteria:
   - Does the model use Socratic questioning (guiding, not telling)?
   - Does it reference correct AQA assessment objectives (AO1-AO6)?
   - Does it stay in the GCSE English tutor role?
   - Does it redirect off-topic requests appropriately?

## Decision Point

If smoke tests reveal significant persona gaps (e.g., model doesn't use Socratic approach, gives generic non-AQA answers):
- Consider a second training epoch with lr=2e-5 (see TASK-REV-G4R2 Finding 2)
- Or adjust the system prompt in the Ollama Modelfile

If smoke tests pass, proceed to TASK-G4D-003 (ChromaRAG + Open WebUI).

## Acceptance Criteria

- [x] Ollama model `gcse-tutor-gemma4-moe` created and listed
- [x] 5 smoke test prompts run
- [x] Model demonstrates GCSE tutor persona (Socratic questioning)
- [x] Model shows AQA-specific knowledge
- [x] Go/no-go decision recorded for proceeding to RAG setup

## Completion Notes (2026-04-20)

Completed across three smoke-test runs. Evidence: `docs/reviews/ollama-smoke-tests/run-{1,2,3}.md`.

**Runtime prerequisite discovered**: The Unsloth GGUF declares architecture `gemma4`, which was not supported by the installed Ollama v0.18.0. Upgraded to **v0.21.0** (Gemma 4 support landed in v0.20.0, 2026-04-02). Downgrading this requirement into project knowledge — any new Ollama deployment of this model needs ≥ v0.20.0.

**Modelfile fixes applied** (final version on disk at `~/Models/gcse-tutor-gemma4-26b-moe/Modelfile`):
- Removed the TEMPLATE block shipped by Unsloth (used `<|turn>` / `<turn|>` / `<|channel>` tokens that don't match Gemma 4's chat template and leaked channel markers into user output). Without a TEMPLATE directive, Ollama uses the correct `tokenizer.chat_template` baked into the GGUF.
- Added a SYSTEM prompt that (a) differentiates *procedural* questions ("how do I…") from *homework-answer* requests ("just tell me…"), and (b) scripts an off-topic redirect. This resolved a cognitive deadlock that caused the model's thinking channel to run for 361 s on procedural prompts in run-2.
- Added `PARAMETER num_predict 1500` to cap generation length.

**Smoke-test outcome (run-3.md)** — all 5 prompts pass:
- Socratic refusal on "just tell me the answer" ✅
- Off-topic redirect on maths homework ✅
- Correct AQA assessment-objective framing (AO2/AO3 references) ✅
- Answer-then-invite-apply pattern on procedural questions ✅
- No quote fabrications observed in run-3 (vs. two in run-1) ✅

**Go decision**: Proceed to TASK-G4D-003 (ChromaRAG + Open WebUI).

**Remaining concerns tracked as follow-ups**:
- Factuality of set-text quotations (two fabricated quotes observed in run-1: Macbeth "sticking-place" rendered as "hope of belief", and Inspector's final speech partially hallucinated). Tracked as **TASK-G4D-006**. RAG will partially mitigate — this task measures the delta.
- Minor cosmetic rendering glitches (inline list-item numbering, leading blank lines from Ollama app hiding the thought channel). Not blocking.
