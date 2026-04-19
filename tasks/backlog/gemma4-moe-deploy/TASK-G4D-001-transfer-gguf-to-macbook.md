---
id: TASK-G4D-001
title: Transfer GGUF model from DGX Spark to MacBook via Tailscale + rsync
status: backlog
created: 2026-04-19T00:00:00Z
priority: high
tags: [deployment, rsync, tailscale, gguf]
complexity: 2
task_type: implementation
implementation_mode: manual
parent_review: TASK-REV-G4R2
feature_id: FEAT-G4D
wave: 1
dependencies: []
---

# Task: Transfer GGUF model from DGX Spark to MacBook via Tailscale + rsync

## Description

Copy the fine-tuned Gemma 4 26B MoE GGUF model files from DGX Spark to MacBook Pro using rsync over Tailscale. The model was produced by training run 4 (TASK-REV-G4R2).

## Source Files

On DGX Spark (inside Docker container `6150ec61761e` or on host after `docker cp`):

```
/workspace/output/gcse-tutor-gemma4-26b-moe/gguf_gguf/
├── gemma-4-26b-a4b-it.Q4_K_M.gguf          # Primary (~15 GB)
├── gemma-4-26b-a4b-it.BF16-mmproj.gguf      # Multimodal projector
├── gemma-4-26b-a4b-it.BF16-00002-of-00002.gguf  # BF16 shard
└── Modelfile                                  # Ollama Modelfile
```

## Steps

1. **Copy files from Docker to DGX Spark host** (if not already done):
   ```bash
   docker cp 6150ec61761e:/workspace/output/gcse-tutor-gemma4-26b-moe/gguf_gguf/ \
     ~/fine-tuning/output/gcse-tutor-gemma4-26b-moe/gguf_gguf/
   ```

2. **Verify both machines on Tailscale**:
   ```bash
   tailscale status
   ```

3. **Create target directory on MacBook**:
   ```bash
   mkdir -p ~/Models/gcse-tutor-gemma4-26b-moe
   ```

4. **rsync the Q4_K_M GGUF and Modelfile** (pull from MacBook):
   ```bash
   rsync -avP --partial \
     <dgx-spark-hostname>:~/fine-tuning/output/gcse-tutor-gemma4-26b-moe/gguf_gguf/gemma-4-26b-a4b-it.Q4_K_M.gguf \
     ~/Models/gcse-tutor-gemma4-26b-moe/

   rsync -avP --partial \
     <dgx-spark-hostname>:~/fine-tuning/output/gcse-tutor-gemma4-26b-moe/gguf_gguf/Modelfile \
     ~/Models/gcse-tutor-gemma4-26b-moe/
   ```

5. **Verify transfer** — check file size matches source:
   ```bash
   ls -lh ~/Models/gcse-tutor-gemma4-26b-moe/
   ```

## Note on mmproj file

The review (TASK-REV-G4R2, Recommendation 5) flagged that the Unsloth log shows both `BF16-mmproj.gguf` and `BF16-00002-of-00002.gguf`. For a text-only tutor, the projector may not be needed. Transfer it only if Ollama's Modelfile references it.

## Acceptance Criteria

- [ ] Q4_K_M GGUF file present on MacBook at `~/Models/gcse-tutor-gemma4-26b-moe/`
- [ ] File size matches source (no corruption)
- [ ] Modelfile transferred
