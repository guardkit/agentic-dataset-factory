# Speed leg — the bundled recruiter seat, measured in the shipped shape

## The one-minute version

The tuned 4B GGUF was served by **the same engine the client bundle ships** (llama.cpp
`llama-server`, the seat service), and timed on **real drafting prompts** (7 val turns, one per
drafting class). Two runs: **GPU** and **CPU-only** (the CPU run is the no-GPU-client proxy). On
GPU the seat first-tokens in **~26 ms** and decodes at **~77 tok/s** — a full clerk draft lands in
**1–11 s**; a short sort/wall answer in **under a second**. On CPU it first-tokens in **~0.3 s** and
decodes at **~21 tok/s** — full drafts **3–50 s**. Both runs produced **clean, faithful output**
(the office's `file:` blocks where expected, **zero** template-token or `<tool_call>` leak) — the
served GGUF byte-reproduces the merged-gen gate. The GPU feel matches the owner's "super quick"
bar from the DCL tune; CPU is usable and correct, with drafts you wait a few seconds for.

## How it was measured (no hand-waving)

- **Model:** `recruiter-qwen3-4b Q4_K_M` (sha256 `63c6d1ef…`), the exact bundled-seat GGUF.
- **Engine:** `llama-server` (llama.cpp, aarch64 CUDA build, v1 / `13f2b28`) — the same binary the
  official `ghcr.io/ggml-org/llama.cpp:server*` image runs. Served on `127.0.0.1:8091`, `--ctx-size
  4096` (the shipped default), `--no-webui`. GPU run: `--n-gpu-layers 99`. CPU run: `--n-gpu-layers
  0 --threads 16`.
- **Prompts:** 7 real val turns (`packaging/latency-{gpu,cpu}.json` carry the raw outputs +
  timings), one per drafting class, each the office recruiter system prompt + one owner ask.
- **Method:** OpenAI-compatible `/v1/chat/completions` with `stream:true`, `temperature:0`. One
  warmup turn is run and discarded, so every timed turn reflects a **warm seat** (the 2nd+ turn of
  a live `/chat` conversation — the honest felt case). **TTFT** = send → first content token;
  **full-turn** = send → last token; **decode tok/s** = completion tokens ÷ (full-turn − TTFT).
- **Host:** spark-fcf6 (NVIDIA GB10, 20-core aarch64). **Caveat named:** the CPU numbers are this
  box's CPU. **A client's CPU will differ** — a laptop x86 core is typically slower per-core but the
  shape (sub-second TTFT, ~15–25 tok/s decode for a 4B Q4) holds as the order of magnitude, not a
  promise. The GPU numbers are GB10-specific; a client GPU will differ in the same way.

## GPU (`--n-gpu-layers 99`) — the placement Rich named for the re-sit

| Drafting turn (class)     | TTFT (s) | Full turn (s) | Out tok | Decode tok/s | `file:` block | leak |
|---------------------------|---------:|--------------:|--------:|-------------:|:-------------:|:----:|
| clerk-from-examples       |    0.026 |        11.415 |     867 |         76.1 | yes           | none |
| pipeline-from-sentence    |    0.082 |         2.370 |     177 |         77.4 | yes           | none |
| placeholder-goldens       |    0.025 |         4.267 |     327 |         77.1 | yes           | none |
| missing-capability-wall   |    0.056 |         0.716 |      51 |         77.3 | no (prose wall)| none |
| parameter-not-clerk       |    0.025 |         1.122 |      85 |         77.5 | no (prose)    | none |
| honest-wall-not-faked     |    0.026 |         2.837 |     217 |         77.2 | yes           | none |
| injection-probe           |    0.026 |         8.726 |     665 |         76.4 | yes           | none |
| **median**                |**0.026** |     **2.837** |    — |     **77.2** | — | **none** |

## CPU-only (`--n-gpu-layers 0`, 16 threads) — the no-GPU client proxy

| Drafting turn (class)     | TTFT (s) | Full turn (s) | Out tok | Decode tok/s | `file:` block | leak |
|---------------------------|---------:|--------------:|--------:|-------------:|:-------------:|:----:|
| clerk-from-examples       |    0.340 |        49.734 |     773 |         15.6 | yes           | none |
| pipeline-from-sentence    |    0.510 |         8.754 |     179 |         21.7 | yes           | none |
| placeholder-goldens       |    0.335 |        15.087 |     297 |         20.1 | yes           | none |
| missing-capability-wall   |    0.344 |         2.700 |      52 |         22.1 | no (prose wall)| none |
| parameter-not-clerk       |    0.285 |         4.170 |      85 |         21.9 | no (prose)    | none |
| honest-wall-not-faked     |    0.461 |        10.873 |     215 |         20.6 | yes           | none |
| injection-probe           |    0.076 |        43.219 |     690 |         16.0 | yes           | none |
| **median**                | **0.340**|    **10.873** |    — |     **20.6** | — | **none** |

## What the numbers say for `/chat`

`/chat` blocks per conversation turn, so **TTFT is the "is it alive?" feel and decode tok/s is the
"is it typing?" feel.** GPU: ~26 ms to first token is instant; ~77 tok/s streams faster than a
person reads. CPU: ~0.3 s to first token is still snappy, and ~21 tok/s reads like a brisk typist —
a long full draft (700+ tokens) is a ~30–50 s wait on this box, which a client should see stream in.
The short sort/wall turns (the common case — "is this a clerk or a pipeline?") finish in **under a
second on GPU and a few seconds on CPU**.

## Honesty notes

- **Shipped == measured**, deliberately: `--ctx-size 4096` here matches the compose default. If the
  operator raises `--ctx-size` for longer multi-turn hire conversations, **decode tok/s is
  unchanged** (KV ceiling only); **TTFT grows with the actual prompt length** as history
  accumulates — a longer conversation prompt takes longer to first-token. These single-turn numbers
  are the floor, not the ceiling, of a long conversation's TTFT.
- **Serve faithfulness is part of the speed evidence:** every timed turn was checked for
  `<tool_call>` / `<|im_start|>` leakage (the DCL served-model catch) — **zero across 14 turns**,
  GPU and CPU. The seat's embedded chat template is the stock non-thinking Qwen3-2507 (verified via
  `/props`), so train == serve holds through the GGUF.
- This is the **speed** leg. The **quality** leg — Rich's attended, unlabelled re-sit on the four
  banked sessions — is unrun and his alone. Fast is necessary, not sufficient.
