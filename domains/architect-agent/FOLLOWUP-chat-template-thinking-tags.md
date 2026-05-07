# FOLLOWUP: chat template / `<think>` tag interaction

**Status:** open investigation — not blocking; the fine-tuned `architect-agent` is serving correctly via llama-swap and producing high-quality, persona-consistent responses. This brief is for a specialist agent to assess whether the chat-template / training-data interaction should be changed for the **next** fine-tune in this portfolio.

**For:** specialist agent (likely the `langchain-tool-specialist`, `domain-driven-config-specialist`, or a fresh chat-template-specialist if one is appropriate).

**Created:** 2026-05-03 from observations during the architect-agent serve-and-verify step.

---

## TL;DR

Our training data for `architect-agent` had every assistant turn open with `<think>...</think>`. After fine-tuning Gemma-4-26B-A4B-it via Unsloth, the model emits **persona-correct, reasoning-shaped** responses but **no literal `<think>` tags** in default output. An explicit system-prompt instruction reliably reproduces them on demand.

The likely root cause: the Gemma-4-thinking chat template's native `<|channel>thought<channel|>` framing nests our `<think>` markers redundantly during training, and the model learned to fold its reasoning into the channel rather than emit the inner tags.

**Decision needed:** for the next fine-tune (next domain, or a re-train of architect-agent), should we:
1. Keep the current setup and accept implicit reasoning, or
2. Change the chat template, or
3. Change the training data shape?

---

## What we observed

### The training data
- 894 behaviour examples in `output/train.jsonl`
- 100% of examples had `<think>...</think>` blocks at the start of the assistant content (verified Phase 0.3 of `RUNBOOK-architect-fine-tune.md`)
- ShareGPT format with `system` / `user` / `assistant` roles
- Assistant content typical length: ~5 KB, with `<think>` block typically ~30-40% of total

### The fine-tune itself
- Base: `unsloth/Gemma-4-26B-A4B-it`
- Unsloth + TRL SFTTrainer, 16-bit LoRA, `lora_r=16`, lr 2e-4, 1 epoch (224 steps), `--max-seq-length 2048`
- Chat template: `gemma-4-thinking` (the script's option that "preserves `<think>` blocks", per the script's own comment)
- Training loss: 2.775 → 0.997 — clean monotonic descent
- `train_on_responses_only` masking with `instruction_part="<|turn>user\n"` and `response_part="<|turn>model\n"`
- Reported masked-token ratio: 27.7% (correct for our long-response dataset; system+user is the masked portion)

### The chat template (`/opt/llama-swap/config/gemma4-thinking.jinja`)

Generic Gemma-4-thinking template, byte-identical copy of `gemma4-tutor.jinja`. Key fragments:

```jinja
{%- if role == "model" -%}
    {{ '<|channel>thought
<channel|>' }}
{%- endif -%}
…
{{ '<turn|>
' }}
…
{%- if add_generation_prompt -%}
    {{'<|turn>model
<|channel>thought
<channel|>'}}
{%- endif -%}
```

So during training, every assistant turn was wrapped:

```
<|turn>model
<|channel>thought
<channel|><think>reasoning</think>actual answer<turn|>
```

### Inference behaviour (verified 2026-05-03 against the running architect-agent)

- **Without system prompt, no system-prompt instruction:**
  - Response is well-formed prose, but no `<think>...</think>` opening
  - Quality is good; persona is somewhat present
- **With the architect system prompt from training data (1,678 chars):**
  - Response shifts noticeably: references Evans by name, talks about "architectural tension," uses DDD vocabulary fluently
  - Still no `<think>...</think>` tags
- **With explicit system-prompt instruction "Always begin your response with a `<think>...</think>` block showing your reasoning":**
  - Tags emit reliably, well-formed reasoning inside, programmatically parseable
  - Both with and without the architect persona prompt
- **Raw `/completion` endpoint** (no chat-template processing applied to the prompt — we manually constructed the input):
  - Same result: clean prose, no `<think>` tags
  - Confirms it's not a llama.cpp post-processing strip; the model genuinely isn't generating the tokens

### What this rules out
- **Quantisation loss** — q4_k_m is what's served, but the issue would persist on the merged-16bit too (the response shape is determined by the LoRA adapter, which is loaded into either format)
- **llama.cpp `reasoning_format` stripping** — `reasoning_format: "none"` was tried; same result. Also, `choices[0].message` only has `role` and `content` keys — there's no separate `reasoning_content` channel where it could have been hidden
- **Wrong model file served** — verified the `architect-agent` worker process loads `/opt/llama-swap/models/architect-agent/architect-agent.Q4_K_M.gguf` (our actual fine-tune output), not the base or the tutor. The persona shift confirms the LoRA is taking effect

---

## Hypotheses

### H1 (most likely): the native `<|channel>thought<channel|>` absorbed the `<think>` markers

The Gemma-4-thinking chat template already wraps the assistant turn with `<|channel>thought\n<channel|>` … `<turn|>`. These are special tokens in Gemma 4's vocabulary and they ARE the model's native thinking framing.

During training, the actual content the model saw was:

```
<|channel>thought
<channel|><think>reasoning</think>actual answer<turn|>
```

This is *redundant* thinking framing (channel + tags). The model probably learned the shorter, lower-loss path: produce content directly inside the channel, skipping the inner `<think>...</think>` wrapper entirely. After 224 steps of consistent training, the model learned that "thinking happens inside the channel" is the reliable signal, and the literal `<think>` tags became low-probability low-loss artefacts.

If true: this is a **chat-template / data-shape mismatch**. The dataset assumed a non-thinking template would wrap the assistant turn; we used the thinking template. The two thinking conventions clashed.

### H2: training was too short to consolidate both signals

224 steps of 1 epoch on 894 examples is a moderate fine-tune. Maybe more epochs / steps would have driven the literal `<think>` emission lower in loss. Loss did plateau around 1.0 by the end though, which suggests the model had converged.

### H3: tokenisation of `<think>` and `</think>` is fragile

If `<think>` tokenises as multiple subword tokens (e.g. `<`, `think`, `>`), the model has to consistently emit a multi-token sequence. The training data has consistent `<think>` openings, so this should work — but if the chat template's special-token framing has higher logit priority, the model might "skip" producing the tag sequence.

Could be tested by checking the tokeniser's treatment of `<think>` against the same model.

---

## Three candidate paths

| Path | Effort | Outcome | Risk |
|---|---|---|---|
| **A. Live with implicit reasoning + system-prompt nudge** | None — already done | Reasoning happens inline; system-prompt instruction reliably forces literal tags when downstream tools need them | Callers must remember the system-prompt nudge; no global guarantee |
| **B. Use `--chat-template gemma-4` (not `-thinking`) for the next training run** | Re-train (~1.5h on architect dataset) | Removes the native thought channel; our `<think>` tags become the only thinking framing and *should* be preserved literally | Untested. May lose some Gemma-native thinking-mode capabilities. Worth a smoke test on a small (60-step) run before committing |
| **C. Strip `<think>...</think>` from training data and let the channel framing carry it** | Re-train + dataset transform | Dataset becomes pure prose answers; the chat template's `<|channel>thought<channel|>` provides the only thinking shape, model emits a clean separation between thinking and answer at inference | Reasoning becomes opaque to programmatic parsers — they'd have to parse `<\|channel>...<channel\|>` instead of `<think>...</think>` |

**My recommendation if forced to pick:** B. It's the cleanest, surfaces the explicit `<think>` tags consistently, and matches the dataset's intent. The 1.5h cost is small relative to the cumulative benefit across future domains. Run a 60-step smoke first to confirm.

---

## Suggested investigation by the specialist

1. **Confirm H1 with a tokeniser check.** Use Hugging Face `transformers.AutoTokenizer.from_pretrained("unsloth/Gemma-4-26B-A4B-it")` and check whether `<|channel>thought<channel|>` and `<think></think>` are special tokens or multi-token sequences. Their relative token IDs and any `add_special_tokens` interactions inform H1's plausibility.
2. **Run smoke test on path B.** Edit `train_gemma4_moe.py:99` (the `--chat-template choices`) — actually it already supports `gemma-4` as a choice. Re-run a 60-step smoke against the existing architect dataset with `--chat-template gemma-4 --max-steps 60 --skip-export`, dump first 5 step losses, and verify the resulting fine-tune emits literal `<think>` tags by default. Decision: if loss curve is comparable and tags emit, B is validated.
3. **Document the finding** back into `RUNBOOK-architect-fine-tune.md` Phase 5.4 (the response-shape table) and into the script docstring at `docs/research/train_gemma4_moe.py` (note which chat template to choose for which output behaviour).
4. **(Optional) Update the chat template choice as the default** if path B works — change `DEFAULTS["chat_template"]` in the script.

## Files to read first

- [`RUNBOOK-architect-fine-tune.md`](RUNBOOK-architect-fine-tune.md) — Phase 0.3, 5.4, the masking-ratio note in 3.4
- [`/opt/llama-swap/config/gemma4-thinking.jinja`](/opt/llama-swap/config/gemma4-thinking.jinja) — the chat template
- [`docs/research/train_gemma4_moe.py`](../../docs/research/train_gemma4_moe.py) — the trainer script (lines 99-101 for the chat-template choice)
- A handful of `output/train.jsonl` records — confirm the assistant-turn shape in the source data

---

*Brief authored: 2026-05-03 by the assistant who walked the fine-tune through to a successful llama-swap deployment. Open the conversation back up if any of the above is wrong — it's all "best understanding from one full lifecycle" and could be off in subtle ways.*
