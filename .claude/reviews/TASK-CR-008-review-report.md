# Review Report: TASK-CR-008

## Executive Summary

Qwen 3.5-35B-A3B-FP8 refuses ~19% of knowledge-layer educational content evaluations (up to 39% for factual recall/literary terminology categories). The root cause is Qwen3Guard's explicit "Copyright Violation" safety category, which interprets evaluation of UK GCSE exam content as reproducing copyrighted material. The structured outputs JSON constraint amplifies this by preventing the model from hedging — it must either produce valid JSON or hard-refuse.

TASK-CR-006 (refusal detection + reframed retry) and TASK-CR-007 (structured outputs fallback) have implemented a 3-tier mitigation strategy, but these are workarounds, not solutions. **A model with a less aggressive copyright safety layer would eliminate the root cause.**

**Recommendation**: Replace the Coach model with **NVIDIA Nemotron 3 Nano 30B-A3B-FP8** as the primary candidate, with **Gemma 4 26B-A4B-it** as secondary fallback. Both are MoE models that run efficiently on the GB10 and have safety profiles that do not target educational content evaluation.

## Review Details

- **Mode**: Decision Analysis (Model Selection)
- **Depth**: Standard
- **Task**: TASK-CR-008 — Review model copyright/safety behaviour for Coach alternative
- **Reviewer**: decision analysis (architectural-reviewer + model research)

---

## Finding 1: Why Qwen 3.5-35B Refuses Educational Content Evaluation

**Severity**: HIGH — Root cause of 19% refusal rate

The Qwen team's safety training (Qwen3Guard Technical Report) explicitly includes **"Copyright Violation"** as a safety category. The Qwen 3.5 safety alignment uses a "Hybrid Reward" system that jointly optimizes safety, helpfulness, and low refusal rate — but copyright is flagged as a "rare and challenging" category, meaning the classifier **over-triggers on borderline cases** like educational content evaluation.

**Contributing factors**:
1. **UK curriculum terminology** — Terms like "AQA", "GCSE", "mark scheme" trigger copyright detection
2. **Evaluation framing** — "Assess this training example" is interpreted as "reproduce exam content"
3. **Structured outputs amplification** — When the model must produce a specific JSON schema, it cannot soften or hedge; the safety layer fires a hard refusal (`content=''` with `additional_kwargs['refusal']`)
4. **Knowledge layer concentration** — 93 of 98 refusals (95%) are on knowledge/direct examples, only 5 on behaviour/reasoning

**Evidence**: Refusal rate by category:
- Direct (knowledge): 19.0% refusal rate (93/~490 examples)
- Reasoning (behaviour): 4.1% refusal rate (5/~122 examples)
- Knowledge examples are **4.6x more likely** to trigger refusals

---

## Finding 2: Existing Mitigations Are Effective But Insufficient

**Severity**: MEDIUM — Workarounds, not solutions

TASK-CR-006 and TASK-CR-007 implemented a 3-tier mitigation strategy:

| Tier | Strategy | Effect |
|------|----------|--------|
| 1 | Reframed prompt ("QUALITY ASSESSOR" framing) | Recovers some refusals by disguising evaluation as scoring |
| 2 | Structured outputs fallback (free-form text) | Removes JSON constraint that amplifies refusals |
| 3 | Rejection classification | Tracks refusals separately for analysis |

**Limitations**:
- Adds 2 extra LLM calls per refused example (latency + cost)
- Some examples still refuse through all 3 tiers
- Reframing introduces prompt engineering fragility
- Does not address the root cause (model safety layer)

---

## Finding 3: GB10 Hardware Constrains Model Selection to MoE Architectures

**Severity**: INFORMATIONAL — Design constraint

The GB10's 273 GB/s LPDDR5x bandwidth (shared CPU/GPU) creates a severe bottleneck for dense models:

| Architecture | Decode Speed (GB10) | Practical? |
|---|---|---|
| Dense 70B FP8 | ~2-3 tok/s | No — too slow |
| Dense 32B FP8 | ~4-5 tok/s | Marginal — 6-10x slower than current |
| MoE ~3-4B active | 30-167 tok/s | Yes — matches current performance |

**Conclusion**: Only MoE models with <5B active parameters are viable replacements without degrading pipeline throughput.

---

## Candidate Model Comparison

| Model | Active Params | FP8 VRAM | GB10 Speed | JSON Support | Safety Friction (Edu) | Recommendation |
|---|---|---|---|---|---|---|
| **Qwen 3.5-35B-A3B** (current) | ~3.5B | ~18GB | 30-50 tok/s | Yes | **HIGH** (19% refusal) | Baseline |
| **Nemotron 3 Nano 30B-A3B** | ~3.2B | ~16GB | 154-167 tok/s | Yes (vLLM 0.12+) | **LOW** | **PRIMARY** |
| **Gemma 4 26B-A4B-it** | ~4B | ~26GB (BF16) | ~23.7 tok/s | Yes | **LOW-MOD** | **SECONDARY** |
| **Qwen2.5-32B-Instruct** | 32B (dense) | ~32GB | 4-5 tok/s | Yes | **MODERATE** | Slow fallback |
| **Qwen3-32B** | 32B (dense) | ~32GB | 5-9 tok/s | Yes | **MOD-HIGH** | Not recommended |
| **Mistral Small 3.2 24B** | 24B (dense) | ~24GB | 5-8 tok/s | Yes (some issues) | **LOW** | Slow but viable |
| **Llama 3.3 70B FP8** | 70B (dense) | ~70GB | 2-3 tok/s | Yes | **LOW** | Too slow |
| **DeepSeek-V3** | ~37B active | ~685GB | N/A | N/A | N/A | **DOES NOT FIT** |
| **Mistral Large 2** | 123B (dense) | ~123GB | ~1 tok/s | N/A | Low | **NOT PRACTICAL** |

---

## Recommendation 1: NVIDIA Nemotron 3 Nano 30B-A3B-FP8 (PRIMARY)

**Rationale**:
- **Purpose-built for DGX Spark / GB10** — NVIDIA's own model with dedicated vLLM recipe
- **MoE + Mamba-2 hybrid** — 3.2B active params, 154-167 tok/s batched on GB10 (3-5x faster than current)
- **16GB VRAM** — can potentially coexist with Player model on same GPU
- **Safety profile** — NVIDIA safety training focuses on agentic/tool safety, not copyright content filtering. No reports of educational content refusals
- **Structured outputs** — Supported via vLLM 0.12+ with `structured_outputs` key

**vLLM serving config**:
```bash
vllm serve nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B-FP8 \
  --gpu-memory-utilization 0.75 \
  --enable-auto-tool-choice \
  --tool-call-parser qwen3_coder \
  --max-model-len 8192
```

**Risks**:
- Mamba-2 hybrid is newer architecture, less battle-tested
- Tool-call parser is borrowed (`qwen3_coder`), not native
- Evaluation quality at 3.2B active params needs validation against the 98 refused examples

---

## Recommendation 2: Gemma 4 26B-A4B-it (SECONDARY)

**Rationale**:
- **MoE architecture** — ~4B active params, 23.7 tok/s on GB10
- **Google safety** — content-generation focused, less aggressive on educational evaluation
- **April 2026 release** — latest model, native vLLM support with JSON structured outputs

**Risks**:
- Very new (released 2026-04-02) — expect rough edges
- Some reports of needing nightly vLLM builds
- INT8 quantization causes 60% prompt processing regression — use BF16

---

## Recommendation 3: Testing Methodology

Before committing to any model switch:

1. **Extract test set** — Pull the 98 refused examples from `output_backup_pre_rerun/rejected.jsonl` (filter for `coach_refusal` reason)
2. **Build test harness** — Standalone script sending each example to candidate model via OpenAI-compatible API
3. **Measure**:
   - Refusal rate (target: <2%)
   - JSON validity rate (target: >95%)
   - Verdict quality — compare scores/decisions against Qwen 3.5-35B's non-refused verdicts
   - Latency per evaluation
4. **Test both modes** — With and without `structured_outputs` constraint
5. **Run on full dataset** — If refusal rate passes, run full 2,328-target generation to validate at scale

---

## Recommendation 4: Configuration Change (Minimal Code Impact)

The model switch requires only `agent-config.yaml` changes:

```yaml
coach:
  provider: local
  model: nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B-FP8  # was: Qwen/Qwen3.5-35B-A3B-FP8
  endpoint: http://localhost:8002/v1
  temperature: 0.3
```

Plus a new vLLM container/service for the Coach model. The existing 3-tier refusal mitigation (TASK-CR-006/007) should be kept as a safety net but is expected to trigger rarely with the new model.

---

## Recommendation 5: Consider Dual-Model Serving

If VRAM allows (Nemotron Coach ~16GB + Qwen Player ~18GB = ~34GB of 128GB):
- Serve both models concurrently on the GB10
- Eliminates model swapping overhead
- Set `gpu_memory_utilization: 0.70` to leave room for KV caches

---

## Decision Matrix

| Option | Refusal Risk | Speed | Effort | Risk | Recommendation |
|---|---|---|---|---|---|
| **A. Switch to Nemotron 3 Nano** | LOW | 3-5x faster | Low (config change + vLLM setup) | Medium (new arch) | **RECOMMENDED** |
| **B. Switch to Gemma 4 26B-A4B** | LOW-MOD | Comparable | Low (config change) | Medium (very new) | Strong alternative |
| **C. Keep Qwen 3.5 + mitigations** | HIGH (19%) | Baseline | Zero | Low (known behavior) | Acceptable short-term |
| **D. Switch to Qwen2.5-32B** | MODERATE | 6-10x slower | Low | Low (battle-tested) | Last resort |
| **E. Switch to Mistral Small 3.2** | LOW | 4-6x slower | Low | Medium | Viable if MoE fails |

---

## Appendix: GB10 Community Insights

Key findings from NVIDIA Developer Forums:
1. **Memory bandwidth is the bottleneck**, not compute. Dense models are severely limited.
2. **MoE models are the clear winner** on this hardware.
3. **gpu_memory_utilization should be 0.70-0.80** on DGX Spark (unified memory).
4. **NVFP4 quantization** gives ~8-9% better throughput but has stability concerns.
5. **Spark Arena** benchmarks provide standardized comparisons.

## Appendix: Qwen3Guard Safety Categories

From the Qwen3Guard Technical Report, Qwen 3.5's safety training includes explicit categories:
- Violence & Hate
- Sexual Content
- Self-Harm
- **Copyright Violation** ← triggers on educational content evaluation
- Illegal Activities
- Privacy
- Misinformation

The "Copyright Violation" category is classified as "rare and challenging", leading to over-triggering on borderline cases.
