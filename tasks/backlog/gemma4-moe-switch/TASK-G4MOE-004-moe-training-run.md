---
id: TASK-G4MOE-004
title: Execute MoE fine-tune on GB10 (sanity + full run)
status: backlog
created: 2026-04-15T00:00:00Z
updated: 2026-04-15T00:00:00Z
priority: high
tags: [fine-tuning, gemma4, moe, gb10, hardware]
complexity: 4
parent_review: TASK-REV-G4MOE
feature_id: FEAT-G4MOE
wave: 2
implementation_mode: manual
dependencies: [TASK-G4MOE-002, TASK-G4MOE-003]
---

# Task: Execute MoE fine-tune on GB10 (sanity + full run)

## Description

Run the new `train_gemma4_moe.py` on GB10 hardware to produce the first Gemma 4 26B A4B MoE fine-tune on the GCSE English tutor dataset. This is a real unattended training run — **not** a codemod task and **not** something that can be done in a Claude Code session. It requires physical/remote access to the DGX Spark.

**Sequence**: sanity run first, full run only after sanity passes. Do **not** start the full run without confirming the sanity run produced decreasing loss and no crashes.

## Prerequisites

- [ ] TASK-G4MOE-002 landed (`train_gemma4_moe.py` exists and `--help` works)
- [ ] TASK-G4MOE-003 landed (documentation reflects MoE as primary; you're following the updated steps)
- [ ] DGX Spark GB10 reachable, Docker image `nvcr.io/nvidia/pytorch:25.11-py3` pulled
- [ ] `~/fine-tuning/data/train.jsonl` exists on the host (from the existing Dense run's data prep)
- [ ] `~/.cache/huggingface` has HF_TOKEN set if needed for gated model access
- [ ] Pin the Unsloth version: `pip show unsloth` — record the version in the execution log before starting. If it differs from what worked for Dense, check Unsloth GitHub issues for `gemma-4-26B-A4B` entries.

## Execution Steps

### Step 1: Copy the new MoE script to the GB10

```bash
scp docs/research/train_gemma4_moe.py gb10:~/fine-tuning/scripts/
```

### Step 2: Launch Docker (same volume mounts as Dense run)

```bash
docker run --gpus all \
  --ulimit memlock=-1 \
  --ulimit stack=67108864 \
  -it \
  -v ~/fine-tuning/data:/workspace/data \
  -v ~/fine-tuning/output:/workspace/output \
  -v ~/fine-tuning/scripts:/workspace/scripts \
  -v ~/.cache/huggingface:/root/.cache/huggingface \
  --entrypoint /usr/bin/bash \
  nvcr.io/nvidia/pytorch:25.11-py3
```

### Step 3: Install deps (inside container)

```bash
pip install transformers peft hf_transfer "datasets==4.3.0" "trl==0.26.1"
pip install --no-deps unsloth unsloth_zoo bitsandbytes
pip show unsloth | grep -i version   # record in execution log
pip show peft | grep -i version      # record — torchao gate was added in recent PEFT (TASK-REV-G4R1)
```

### Step 4: Sanity run (`--max-steps 30`)

```bash
cd /workspace
python scripts/train_gemma4_moe.py --max-steps 30
```

**Watch for**:
- [ ] Model download progress — expect ~48 GB for the MoE checkpoint (first run only)
- [ ] "Unsloth: Will patch your computer..." line — confirms Unsloth loaded for MoE path
- [ ] No `bitsandbytes` quantisation errors (would indicate `load_in_4bit=True` leaked in — would be an earlier-task bug)
- [ ] "Loaded N training examples from /workspace/data/train.jsonl"
- [ ] Response-only masking shows ~40–60% tokens masked
- [ ] Loss in 1–3 range, decreasing across 30 steps
- [ ] `nvidia-smi` in another terminal shows ~45–55 GB used (not 22 GB — that would mean 4-bit path accidentally active)

**Failure modes to capture**:
- If `ImportError: Found an incompatible version of torchao`: the script already has a monkey-patch workaround (TASK-REV-G4R1). If this still fires, `pip show peft` and check that the patch is present before `get_peft_model()`
- If loss explodes to 100+: gradient-accum bug, `pip install --upgrade --no-deps unsloth unsloth_zoo`
- If hang with CPU 100% GPU 5%: the known Spark long-run hang — drop `--max-seq-length` to 2048 and retry
- If OOM at 48 GB: unexpected on 128 GB unified; check `nvidia-smi` for zombie processes first
- If `load_in_16bit` unrecognised kwarg: Unsloth version is too old; update

### Step 5: Full training run

Only if Step 4 completed cleanly:

```bash
python scripts/train_gemma4_moe.py \
  --epochs 1 \
  --save-steps 200 \
  --lr 2e-4
```

Expected wall-clock: **3–6 hours**. Leave `watch -n 5 nvidia-smi` running in a second terminal.

### Step 6: Verify outputs

After training completes, confirm three artifact directories exist under `~/fine-tuning/output/gcse-tutor-gemma4-26b-moe/`:

```
├── lora-adapter/          # Small LoRA weights (~80-150 MB, bigger than Dense r=8)
├── merged-16bit/          # Full merged model (~48-52 GB)
└── gguf/                  # Quantised GGUF for llama.cpp/Ollama
    └── *.gguf             # Q4_K_M, ~16 GB
```

### Step 7: Smoke-test the fine-tuned model

Inside the container, run the existing GCSE prompt through the LoRA adapter:

```python
python -c "
from unsloth import FastModel
from transformers import TextStreamer

model, tokenizer = FastModel.from_pretrained(
    '/workspace/output/gcse-tutor-gemma4-26b-moe/lora-adapter',
    max_seq_length=4096,
    load_in_16bit=True,
)

messages = [
    {'role': 'user', 'content': 'How does Shakespeare use dramatic irony in Romeo and Juliet Act 3 Scene 1? I am a Year 10 student studying for my GCSE English Literature exam.'}
]

inputs = tokenizer.apply_chat_template(
    messages, add_generation_prompt=True, enable_thinking=True,
    tokenize=True, return_dict=True, return_tensors='pt',
).to('cuda')

streamer = TextStreamer(tokenizer, skip_prompt=True)
model.generate(**inputs, max_new_tokens=512, use_cache=True,
    temperature=1.0, top_p=0.95, top_k=64, streamer=streamer)
"
```

**Check**:
- [ ] Uses `<think>` blocks before answering
- [ ] Pitched at GCSE level (not university)
- [ ] References AQA assessment objectives (AO1, AO2)
- [ ] Encouraging, tutorial tone
- [ ] **Response feels fluent in real time** (this is the whole point of the switch — should feel dramatically different from Dense inference)

## Scope

- [ ] Sanity run with `--max-steps 30` passes
- [ ] Full 1-epoch run completes without crashes or hangs
- [ ] LoRA adapter, merged-16bit, and GGUF artifacts exist on host at `~/fine-tuning/output/gcse-tutor-gemma4-26b-moe/`
- [ ] Smoke-test inference produces coherent GCSE-tone response
- [ ] Execution log captured (below)

## Execution Log (fill in at run time)

```
Unsloth version:            __________
Start time (sanity):        __________
End time (sanity):          __________
Sanity final loss:          __________
VRAM peak (sanity):         __________
Start time (full):          __________
End time (full):            __________
Full run final loss:        __________
VRAM peak (full):           __________
Total training steps:       __________
Artifacts size:             lora=___ merged=___ gguf=___
Observations:               __________
```

## Acceptance Criteria

- [ ] Execution log fully populated with measured values
- [ ] Three artifact directories exist and are non-empty
- [ ] Smoke-test response uses `<think>` and is pitched at GCSE level
- [ ] No unresolved errors in training stdout (warnings OK if documented)
- [ ] If the smoke test passes, the feature is effectively done. File a follow-up for vLLM serving deployment.
- [ ] If the smoke test fails (tone wrong, incoherent, doesn't use `<think>`), do not delete artifacts — diagnose, file a follow-up, and fall back to the Dense tier in the interim.

## Notes

- This task is `implementation_mode: manual` because it requires unattended execution on hardware outside Claude Code's reach. `/task-work` cannot drive it.
- If the sanity run fails with an Unsloth bug that wasn't caught during TASK-G4MOE-002 review, **stop and file a follow-up task** rather than hacking the script live. The sibling structure means we can diagnose without risking the Dense tier.
- Do not delete or overwrite the existing `/workspace/output/gcse-tutor-gemma4-31b/` directory. Sunk-cost preservation.
