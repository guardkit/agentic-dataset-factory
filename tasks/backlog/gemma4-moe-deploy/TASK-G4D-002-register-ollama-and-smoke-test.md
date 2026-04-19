---
id: TASK-G4D-002
title: Register model in Ollama and run smoke tests
status: backlog
created: 2026-04-19T00:00:00Z
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

- [ ] Ollama model `gcse-tutor-gemma4-moe` created and listed
- [ ] 5 smoke test prompts run
- [ ] Model demonstrates GCSE tutor persona (Socratic questioning)
- [ ] Model shows AQA-specific knowledge
- [ ] Go/no-go decision recorded for proceeding to RAG setup
