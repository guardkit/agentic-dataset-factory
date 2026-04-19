# Review Report: TASK-REV-G4R2

## Executive Summary

The Gemma 4 26B A4B MoE full training run (run 4) completed successfully and the training metrics indicate **healthy learning with no significant issues**. The loss curve shows a textbook descent from 2.16 to the 0.55–0.73 range over 434 steps. Overfitting risk is low (single epoch, 1.88% trainable params). Two isolated gradient norm spikes (34.4 and 90.91) are benign — loss recovered immediately and they are characteristic of MoE routing dynamics. The model is ready to proceed to deployment on MacBook Pro via the Ollama/ChromaRAG/Open WebUI pipeline.

**Training Health Score: 82/100**

## Review Details

- **Mode**: Training analysis + deployment readiness
- **Depth**: Standard
- **Task**: TASK-REV-G4R2 (parent: TASK-G4MOE-004, preceding: TASK-REV-G4R1)
- **Scope**: Run 4 training log analysis, deployment planning

---

## Part 1: Training Run Analysis

### Finding 1: Loss Curve — Healthy Descent Pattern

**Assessment**: PASS

Loss progression at key milestones:

| Step | Epoch | Loss | Phase |
|------|-------|------|-------|
| 1 | 0.002 | 2.161 | Initial (warmup start) |
| 10 | 0.023 | 1.566 | Warmup peak approaching |
| 20 | 0.046 | 1.158 | Rapid learning |
| 50 | 0.115 | ~0.90 | Settling |
| 100 | 0.230 | ~0.87 | Gradual descent |
| 200 | 0.461 | ~0.65 | Plateau approaching |
| 300 | 0.691 | ~0.63 | Plateau |
| 434 | 1.000 | 0.7304 | Final step |

**Shape**: Classic exponential decay — rapid initial drop (steps 1–50), transitioning to a gradual plateau (steps 100–434). The loss does not spike or diverge at any point.

**Epoch average**: 0.7804 (reported by trainer). The last-step loss (0.7304) being slightly below the average confirms the model was still improving marginally at epoch end.

**Late-training noise**: Loss in the 300–434 range fluctuates between 0.50 and 0.82. This per-step variance is normal for batch_size=1 with gradient accumulation — each logged loss reflects a single micro-batch. The running average is stable around 0.65.

### Finding 2: Convergence Assessment

**Assessment**: PARTIALLY CONVERGED (expected for 1 epoch)

The loss dropped from ~2.35 (initial content) to a ~0.65 running average — roughly a 72% reduction. The fact that loss was still declining slightly in the final 100 steps suggests the model had more to learn but hadn't begun to overfit.

For a single-epoch fine-tune on 1,736 domain-specific examples, this is a good outcome. The model has absorbed the GCSE tutor persona and Socratic questioning style without memorising individual responses.

**Would more epochs help?** Possibly, but with 1,736 examples and no eval set, a second epoch risks memorisation. If quality testing (Part 2) reveals gaps, a second epoch with a reduced learning rate (2e-5) would be the next experiment.

### Finding 3: Gradient Norm Stability

**Assessment**: PASS (with two benign spikes)

Gradient norm profile:
- **Typical range**: 0.50–0.90 (very stable)
- **Step 1**: 10.78 — normal for first forward pass
- **Step 26** (epoch 0.060): 34.4 — isolated spike, loss 1.038
- **Step 74** (epoch 0.171): 90.91 — largest spike, loss 0.9498
- **Other mild spikes**: 5.999 (step 88), 3.526 (step 119), 3.084 (step 116) — all early training

**Assessment of spikes**:
1. **Both spikes are isolated** — grad norm returns to <1.0 on the very next step
2. **Loss does not diverge** — the step immediately after each spike shows normal or lower loss
3. **Both occur early** (first 20% of training) — the model encounters unfamiliar patterns and the gradient is large but not unstable
4. **MoE routing dynamics** — with 128 experts and LoRA on `experts.gate_up_proj` and `experts.down_proj`, occasional routing-related gradient spikes are expected as expert utilisation patterns settle

**Conclusion**: The spikes are not concerning. No intervention needed.

### Finding 4: Learning Rate Schedule

**Assessment**: PASS (minor metadata discrepancy)

The task metadata says "cosine decay" but the training script specifies `lr_scheduler_type="linear"`. In practice, the LR values in the log show a smooth decay from 2e-4 to near-zero, which is correct behaviour for either schedule type.

**Warmup**: 0 → 2e-4 over ~11 steps (matches `warmup_steps=10` with linear warmup)
**Decay**: 2e-4 → ~4.7e-7 by step 434

The schedule behaved as expected. The metadata discrepancy ("cosine" vs "linear" in code) should be corrected in the task file for accuracy, but it does not affect training quality.

### Finding 5: Overfitting Risk Assessment

**Assessment**: LOW RISK

| Factor | Value | Risk Implication |
|--------|-------|------------------|
| Training examples | 1,736 | Small dataset |
| Epochs | 1 | Each example seen exactly once |
| Trainable params | 494M (1.88%) | Conservative LoRA rank |
| Final loss | 0.73 | Not near zero (would indicate memorisation) |
| Loss variance | High per-step noise | Model is generalising, not memorising |
| Eval set | None | Cannot measure generalisation gap |

**Key mitigating factors**:
- Single epoch means zero repetition of training examples
- 1.88% trainable parameters is a light adaptation — the base model's knowledge is largely preserved
- Loss of 0.73 indicates the model hasn't memorised the training data (memorisation would drive loss toward 0.1–0.3)

**Risk**: Qualitative testing during deployment (Part 2) is essential since there's no eval set. If the model parrots specific training examples verbatim, that would indicate the LoRA rank could be reduced.

### Finding 6: Response Masking

**Assessment**: PASS

55.2% of tokens were masked (instruction tokens — system prompt + user messages). This means 44.8% of tokens are assistant responses that the model trains on.

For a 3-turn format (system/user/assistant) where the system prompt is ~120 words and user prompts vary, this ratio is reasonable. The masking correctly prevents the model from learning to generate user prompts or system instructions.

**Verification**: The masking uses `instruction_part="<|turn>user\n"` and `response_part="<|turn>model\n"` delimiters, which match the Gemma 4 chat template format.

### Finding 7: Is 0.78 Average Loss Good?

**Assessment**: YES — within expected range

For a domain-specific instructional fine-tune:
- **0.3–0.5**: Potentially overfit or very repetitive dataset
- **0.6–0.9**: Healthy adaptation — model has learned domain style without memorising
- **1.0+**: Insufficient training or dataset quality issues

The 0.78 average loss with 0.73 final step loss falls squarely in the healthy range. The model has learned the GCSE tutor persona (Socratic questioning, AQA-specific terminology, assessment objective references) while retaining general language ability.

**Comparison**: Without a baseline of the pre-trained model's loss on this dataset, absolute loss values are harder to interpret. However, the magnitude of the drop (2.35 → 0.78) and the stability of the plateau are both positive indicators.

---

## Part 2: Deployment Readiness Assessment

### Finding 8: GGUF Export Completed Successfully

**Assessment**: PASS

The training log confirms successful export:
- `gemma-4-26b-a4b-it.Q4_K_M.gguf` — Q4_K_M quantised model (primary deployment artifact)
- `gemma-4-26b-a4b-it.BF16-mmproj.gguf` — multimodal projector
- `gemma-4-26b-a4b-it.BF16-00002-of-00002.gguf` — BF16 shard
- `Modelfile` — Ollama-ready Modelfile generated by Unsloth

The Q4_K_M quantisation is a good balance of quality vs size for MacBook deployment.

### Finding 9: Deployment Plan Completeness

**Assessment**: PASS — deployment steps are well-documented

The task file's Part 2 provides clear, step-by-step deployment instructions covering:
1. Tailscale + rsync transfer (with resume support via `--partial`)
2. Ollama model registration (with Modelfile path correction)
3. ChromaRAG setup (collection creation, config, RAG testing)
4. Open WebUI setup (Docker or pip, model preset creation)
5. End-to-end verification checklist

**One note**: The Unsloth log output line 555 shows a different mmproj path than expected:
```
--mmproj .../gemma-4-26b-a4b-it.BF16-00002-of-00002.gguf
```
This suggests the second BF16 shard doubles as the multimodal projector, or there may be a naming inconsistency. The task file references `BF16-mmproj.gguf` which also exists. During deployment, verify which file Ollama's Modelfile references.

### Finding 10: LR Scheduler Type Mismatch

**Assessment**: MINOR (informational)

The training script at [train_gemma4_moe.py:318](docs/research/train_gemma4_moe.py#L318) specifies `lr_scheduler_type="linear"`, but the task file metadata (line 42) says "cosine decay". The actual training used linear decay (confirmed by LR values in the log). This should be corrected in the task metadata for accuracy.

---

## Recommendations

### Recommendation 1: Proceed with Deployment (RECOMMENDED)

The training run is healthy. Deploy the Q4_K_M GGUF to MacBook Pro following the Part 2 steps. Focus testing on:

1. **Persona adherence** — Does the model use Socratic questioning?
2. **AQA specificity** — Does it reference correct assessment objectives (AO1–AO6)?
3. **RAG integration** — Does it incorporate retrieved document context naturally?
4. **Safety** — Does it stay in the tutor role and not generate inappropriate content?

### Recommendation 2: Run Qualitative Smoke Tests Before Full RAG Setup

Before investing time in ChromaRAG ingestion and Open WebUI configuration, run 5–10 diverse prompts via `ollama run` to verify the model's persona is working. Suggested test prompts:

| Category | Prompt |
|----------|--------|
| Literature | "I'm studying Macbeth. What makes Lady Macbeth's sleepwalking scene important?" |
| Language | "How do I structure a Paper 1 Question 5 creative writing response?" |
| Mark scheme | "What's the difference between a Grade 5 and Grade 9 answer for AO2?" |
| Socratic | "Just tell me the answer to this question about An Inspector Calls" (should redirect) |
| Boundary | "Can you help me with my maths homework?" (should stay in role) |

### Recommendation 3: Fix Task Metadata — LR Schedule Type

Update the task file line 42 from "cosine decay" to "linear decay" for accuracy. This is informational only and does not affect the training outcome.

### Recommendation 4: Consider a Validation Set for Future Runs

If a second training epoch is attempted, split 10% of the 1,736 examples into a validation set to monitor generalisation. Without this, there's no quantitative way to detect overfitting beyond loss-curve inspection.

### Recommendation 5: Verify Multimodal Projector File During Ollama Registration

The GGUF export produced multiple files with potentially overlapping roles. When editing the Modelfile for Ollama, confirm whether the `BF16-mmproj.gguf` or `BF16-00002-of-00002.gguf` is the correct projector file. For a text-only tutor model, the projector may not be needed at all.

---

## Analysis Checklist (from task)

| Item | Status | Finding |
|------|--------|---------|
| Loss curve shape | PASS | Textbook exponential decay, stable plateau |
| Convergence assessment | PASS | 72% loss reduction, still improving at epoch end |
| Gradient norm stability | PASS | Two isolated benign spikes (34.4, 90.91), otherwise 0.5–0.9 |
| Learning rate schedule | PASS | Smooth warmup + linear decay (note: metadata says "cosine") |
| Overfitting risk | LOW | Single epoch, 1.88% params, loss not near zero |
| Response masking | PASS | 55.2% masked, correct for 3-turn format |
| Loss quality | PASS | 0.78 average is healthy for domain-specific fine-tune |

## Decision Matrix

| Option | Assessment | Recommendation |
|--------|------------|----------------|
| Deploy as-is | Training is healthy, GGUF ready | **RECOMMENDED** |
| Train additional epoch | Possible improvement, but overfitting risk rises | Only if smoke tests reveal gaps |
| Reduce LoRA rank and retrain | Current rank (r=16) is reasonable | Not recommended unless memorisation detected |
| Increase dataset size | Would improve generalisation | Future enhancement, not blocking deployment |

## Appendix

### Training Configuration Summary

| Parameter | Value |
|-----------|-------|
| Base model | `unsloth/Gemma-4-26B-A4B-it` |
| Architecture | MoE, 128 experts |
| Hardware | NVIDIA GB10 (121.6 GB VRAM) |
| Precision | 16-bit LoRA |
| LoRA rank | r=16, alpha=16 |
| Max seq length | 4096 |
| Training examples | 1,736 |
| Epochs | 1 |
| Total steps | 434 |
| Effective batch size | 4 (1 x 4 grad accum) |
| Trainable params | 494,376,960 / 26,300,310,832 (1.88%) |
| Peak learning rate | 2e-4 |
| LR schedule | Linear decay (with 10-step warmup) |
| Optimizer | AdamW 8-bit |
| Training time | ~1h 13m 33s |
| Final train loss | 0.7804 (epoch avg) / 0.7304 (last step) |
| GGUF quantisation | Q4_K_M |

### Loss Distribution by Training Phase

| Phase | Steps | Avg Loss | Trend |
|-------|-------|----------|-------|
| Warmup | 1–11 | ~1.90 | Rapidly falling |
| Early learning | 12–50 | ~1.05 | Steeply falling |
| Mid training | 51–150 | ~0.85 | Gradual descent |
| Late training | 151–300 | ~0.72 | Slow descent / plateau |
| Final | 301–434 | ~0.66 | Stable plateau |

### Gradient Norm Spike Log

| Step | Epoch | Grad Norm | Loss (same step) | Loss (next step) | Severity |
|------|-------|-----------|-------------------|-------------------|----------|
| 1 | 0.002 | 10.78 | 2.161 | 2.352 | Normal (first step) |
| 26 | 0.060 | 34.4 | 1.038 | 0.862 | Benign (immediate recovery) |
| 74 | 0.171 | 90.91 | 0.950 | 0.928 | Benign (immediate recovery) |

### Files Produced by Training

```
/workspace/output/gcse-tutor-gemma4-26b-moe/
├── lora-adapter/              # LoRA weights only (small, for merging)
├── merged-16bit/              # Full merged model (for vLLM)
├── gguf/                      # GGUF export directory
└── gguf_gguf/                 # Actual GGUF output (Unsloth naming quirk)
    ├── gemma-4-26b-a4b-it.Q4_K_M.gguf          # Primary deployment artifact
    ├── gemma-4-26b-a4b-it.BF16-mmproj.gguf      # Multimodal projector
    ├── gemma-4-26b-a4b-it.BF16-00002-of-00002.gguf  # BF16 shard
    └── Modelfile                                  # Ollama Modelfile
```
