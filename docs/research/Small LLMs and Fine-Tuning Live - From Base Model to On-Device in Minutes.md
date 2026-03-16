# Small LLMs and Fine-Tuning Live - From Base Model to On-Device in Minutes

**Source:** [Small LLMs and Fine-Tuning Live - From Base Model to On-Device in Minutes](https://www.youtube.com/watch?v=EXB8HokGVMI)
**Channel:** Daniel Bourke (Queensland AI Meetup talk)
**Focus Areas:** AI Concepts · AI Tools · Practical Applications
**Extracted:** 2026-03-14

---

## Summary

Machine learning engineer Daniel Bourke delivers a live, hands-on talk at a Queensland AI meetup demonstrating the full pipeline of fine-tuning a small language model (Gemma 3, 270M parameters) on a custom synthetic dataset — from data creation to training to on-device deployment on an iPhone — in under two hours. He showcases real-world case studies including "Sunny," an iOS skin cancer tracking app powered by a fine-tuned MedGemma model that runs entirely on-device for privacy, and argues that we're 18 months behind state-of-the-art in what can run on consumer hardware. The core message: custom fine-tuned small models give you privacy, infinite free inference, offline capability, and ownership of your compute stack.

---

## Key Quotes

> *"A small language model is a model that can run natively on your own computer or your iPhone."*

> *"The hardest part these days is constructing a data set and deciding what the specific use case is for your business."*

> *"These days we can create custom data sets in hours instead of months."*

> *"Go large on parameters but then go hard on precision... more parameters give your model more capacity, and even if you do lose some precision you still get that performance."*

---

## Insights

### 🤖 AI Concepts

#### 1. Small LLMs Are Models That Run Natively on Consumer Hardware
**Category:** AI Concepts
**Actionable:** ❌

Daniel defines a small language model not by parameter count but by where it runs: natively on your computer or phone. A year ago, "small" meant under 1 billion parameters. Today, 4B parameter models run comfortably on iPhones, and models like Qwen 3.5 4B outperform GPT-4o on public benchmarks while running locally on a MacBook. The trajectory suggests GPT-5-equivalent open-source models running locally by end of year.

> *"I would define a small LM these days as a model that can run natively on your own computer or your iPhone."*

---

#### 2. We're 18 Months Behind State-of-the-Art in What Runs on Your Phone
**Category:** AI Concepts
**Actionable:** ❌

The gap between the cutting-edge frontier model and what you can run on a phone is roughly 18 months to two years. Qwen 3.5 4B now matches GPT-4o (released ~2 years ago) and runs on a MacBook. Even accounting for 30% benchmark inflation from overfitting to public evals, these small models are remarkably capable for on-device use.

> *"We're like 18 months to two years from state-of-the-art to model you can run on your phone."*

---

#### 3. Go Large on Parameters, Hard on Precision — The Jeff Dean Rule
**Category:** AI Concepts
**Actionable:** ✅

Research (and Jeff Dean's recommendation) suggests the optimal strategy for small on-device models is to use the largest parameter count that fits your hardware, then aggressively quantize the precision. More parameters give greater capacity; even with reduced precision (e.g., 4-bit quantization), the sheer parameter count preserves performance. MedGemma went from 8GB (float16) to 3.5GB (4-bit) and ran comfortably on an iPhone.

---

#### 4. Fine-Tuning Teaches the Model Structure, Not Facts
**Category:** AI Concepts
**Actionable:** ✅

A critical insight from the live demo: the fine-tuned model learned the exact output structure Daniel wanted (formatted LinkedIn-style bios) but hallucinated facts for people not well-represented in training data. Fine-tuning is best for teaching a model how to respond (format, style, task structure), not what to respond with (factual recall). For factual accuracy, pair fine-tuning with RAG.

> *"The fine-tune model has actually learned the structure of what we wanted it to output, but all the facts are wrong... This is probably where we'd want to build a RAG system."*

---

#### 5. Fine-Tuning vs RAG vs Prompting — A Simple Framework
**Category:** AI Concepts
**Actionable:** ✅

Daniel's decision framework: start with prompting (cheapest, fastest iteration). Use fine-tuning when you need a model to perform a specific task consistently (structure, format, style). Use RAG when you need specific knowledge injected. Then mix and match as needed. They're all blends of the same goal — guiding model behaviour — at different levels of commitment.

> *"You would start with prompting. You would use fine-tuning for specific task and you use RAG for specific knowledge and then you would just mix and match them."*

---

#### 6. Every Token Counts in the On-Device Regime
**Category:** AI Concepts
**Actionable:** ✅

On constrained hardware, prompt length directly impacts memory usage through the KV cache. A longer prompt can nearly double memory consumption, potentially crashing the app on devices with less than 8GB RAM. Fine-tuning allowed the Sunny team to achieve the same structured output with a much shorter prompt — the model learned the task implicitly rather than needing explicit instructions each time.

> *"When you're in a small device regime, every token counts because every one of these tokens adds to the memory tally."*

---

### 🔧 AI Tools & Infrastructure

#### 7. The Full Fine-Tuning Stack: HuggingFace TRL + Google Colab
**Category:** AI Tools
**Actionable:** ✅

The live demo used a straightforward stack: HuggingFace Transformers for model access, HuggingFace Datasets for data, TRL (Transformers Reinforcement Learning) for SFT (Supervised Fine-Tuning), Google Colab for GPU compute ($10/month gets you access to state-of-the-art GPUs like the RTX Pro 6000 Blackwell with ~100GB VRAM), and HuggingFace Hub for model storage and sharing. The entire fine-tuning run took ~100 seconds.

---

#### 8. MLX Is Apple's PyTorch — And It's Exploding
**Category:** AI Tools
**Actionable:** ✅

Apple's MLX framework (PyTorch-equivalent for Apple Silicon) has matured rapidly. Essentially every new open-source model uploaded to HuggingFace can run locally on a Mac via MLX within a day or two. The only limiting factor is RAM. For on-device iPhone deployment, MLX combined with HuggingFace Swift Transformers handles the full pipeline from fine-tuned model to running app.

---

#### 9. iPhone NPU for Vision, GPU for Language — The Current Best Practice
**Category:** AI Tools
**Actionable:** ✅

For deploying Vision Language Models (VLMs) on iPhone, the current best practice (discovered through experimentation, not Apple documentation) is to run the vision component on the Neural Processing Unit (NPU) and the language model on the GPU. The NPU excels at batch processing images in milliseconds; the GPU handles autoregressive token-by-token generation. This split reduced Sunny's inference from 10 seconds to near-instant.

---

### 💡 Practical Applications

#### 10. Synthetic Data Creation: From Months to Hours
**Category:** Practical Applications
**Actionable:** ✅

Daniel created the entire fine-tuning dataset synthetically in hours. The process: take attendee names from the meetup page, Google their public LinkedIn info, paste that into an open-source model (GPT-OSS 12B on HuggingFace), ask it to generate 5 QA pairs per person, convert to JSON. When 1,000 samples weren't enough (V1), he 10x'd to 8,000 by augmenting with lowercase variations, typos, and reformulated questions (V2). The same process scales to any business domain.

> *"These days we can create custom data sets in hours instead of months."*

---

#### 11. The Sunny Case Study: Privacy-First On-Device Medical AI
**Category:** Practical Applications
**Actionable:** ✅

Sunny is an iOS skin cancer tracking app that runs a fine-tuned MedGemma model entirely on-device. Photos never leave the phone for inference or storage. It generates structured dermatological notes from skin photos, locked behind biometric auth. The key insight: for health data, on-device is non-negotiable for privacy. The model was fine-tuned in ~15 minutes, quantized from 8GB to 3.5GB, and runs comfortably on modern iPhones. At scale (10M images), the API alternative would cost ~$55K; on-device inference is free forever.

---

#### 12. When to Choose a Custom Model vs API
**Category:** Practical Applications
**Actionable:** ✅

Daniel's decision matrix: need privacy → custom model. Need on-device/offline → custom model. Want to get started ASAP → API. Need the most powerful model available → API. Want to own your compute stack → custom model. The upfront investment is in hardware and training time, but then you get infinite free inference. For the conservation project (900 bird species), models had to run on devices in offline environments — API was never an option.

---

#### 13. Data Quality > Model Architecture — The Hardest Part Is the Dataset
**Category:** Practical Applications
**Actionable:** ✅

Daniel repeatedly emphasises that the hardest and most valuable part of any fine-tuning project is constructing the dataset and defining the specific use case. The model training itself took 100 seconds. The dataset iteration — deciding what inputs and outputs look like, handling edge cases (names without full profiles, lowercase vs uppercase, typos), scaling from V1 to V2 — is where the real work lives.

> *"The hardest part these days is constructing a data set and deciding what the specific use case is for your business."*

---

#### 14. Production Loop: Version Data and Models Together
**Category:** Practical Applications
**Actionable:** ✅

For production systems, Daniel versions datasets and models together (model V3 trained on dataset V3) so you can track which model was trained on which data. The loop: deploy model → track inputs/outputs in production → review mismatches (mostly automated with models reviewing models) → create improved dataset → fine-tune next version → deploy. This is exactly how his Neutrify food analysis app operates in production.

---

#### 15. Fine-Tuning Can Remove Unwanted Behaviours, Not Just Add New Ones
**Category:** Practical Applications
**Actionable:** ✅

MedGemma shipped with excessive safety disclaimers on every response ("I'm not a medical professional..."). In the on-device regime, these wasted tokens add to memory pressure and slow inference. Daniel simply trained the disclaimers out by fine-tuning on examples without them. The same technique works in reverse — you can fine-tune models to add safety behaviours (as governments may do for content moderation), and subsequent fine-tuning can reverse those changes.

---

## Action Checklist

- [ ] Try Google Colab ($10/month paid tier) to access state-of-the-art GPUs for fine-tuning experiments
- [ ] Pick a specific, narrow task in your business where a model needs to do one thing consistently
- [ ] Create a synthetic dataset: take your domain knowledge, feed it to a strong open-source model, generate QA pairs at scale
- [ ] Start with ~1,000 samples; if results are weak, 10x to 8,000+ with augmentation (lowercase, typos, rephrased questions)
- [ ] Fine-tune Gemma 3 (or similar small model) using HuggingFace TRL's SFT Trainer — expect training in minutes, not hours
- [ ] Compare base model vs fine-tuned model side by side on real inputs before deploying anything
- [ ] For on-device deployment, quantize to 4-bit precision and test on target hardware (iPhone/Mac via MLX)
- [ ] Version your datasets and models together so you can trace production issues back to training data
- [ ] For factual accuracy needs, plan to pair fine-tuning (for structure) with RAG (for knowledge)
