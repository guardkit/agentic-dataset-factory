# Dataset-Factory Fix: Eliminate Tutor Template-Token Leak at Source

**Status:** Pending — to apply on the next fine-tune of the GCSE study tutor / architect-agent.
**Companion to:** [RUNBOOK-fix-tutor-template-leak.md](RUNBOOK-fix-tutor-template-leak.md) (server-side workaround currently in production).
**Goal:** Train the next checkpoint without `<|channel>thought\n<channel|>` baked into assistant turns, so the served model stops emitting it on its own. Once that ships, the custom-Jinja workaround on the inference host can be removed.

---

## Why the current model leaks

The leak is **trained behaviour**, not a serving bug. Specifically:

1. The fine-tune scripts ([docs/research/train_gemma4_moe.py](../../docs/research/train_gemma4_moe.py), [docs/research/train_gemma4_dense.py](../../docs/research/train_gemma4_dense.py)) call:
   ```python
   tokenizer = get_chat_template(tokenizer, chat_template="gemma-4-thinking")
   ```
2. Unsloth's `gemma-4-thinking` template wraps every assistant turn as:
   ```
   <|turn>model
   <|channel>thought
   <channel|>{assistant_content}<turn|>
   ```
3. SFT runs on text formatted by exactly that template, so the model learns: *after `<|turn>model\n`, always emit `<|channel>thought\n<channel|>` and only then produce useful tokens.*
4. At serve time the runtime prompt ends at `<|turn>model\n`, so the model's first generated tokens are `<|channel>thought\n<channel|>` — that's the leak.

The `<think>...</think>` blocks already in the dataset content (75% of records, by design — see [docs/research/gcse-tutor-training-data-format.md](../../docs/research/gcse-tutor-training-data-format.md)) are **not** the problem; those live inside the assistant content and are intentional. Only the channel-marker wrapper is.

---

## Decision: which knob to turn

Two viable options. We use Option 1 unless we have a concrete need for the channel-segregated reasoning_content path (which we don't — the tutor UI consumes plain `message.content`).

### Option 1 (chosen): switch the Unsloth template to `gemma-4`

The fine-tune script already accepts `--chat-template gemma-4` as an alternative:

```python
# docs/research/train_gemma4_moe.py:99-101
p.add_argument("--chat-template", default=DEFAULTS["chat_template"],
               choices=["gemma-4-thinking", "gemma-4"],
               help="gemma-4-thinking preserves <think> blocks (use this)")
```

`gemma-4` formats assistant turns without the thinking-channel wrapper, so:
- Training data the model sees: `<|turn>model\n{assistant_content}<turn|>` — no marker injected.
- The model un-learns the "always emit `<|channel>thought\n<channel|>`" reflex.
- `<think>...</think>` blocks inside `{assistant_content}` survive (they're just text), so reasoning behaviour is preserved.

**Trade-off:** llama.cpp / vLLM will not auto-segregate thoughts into `message.reasoning_content`. Our consumers don't use that field (we strip `<think>` client-side or post-train), so the trade-off is free.

### Option 2 (fallback): keep `gemma-4-thinking`, override the wrapper post-`get_chat_template`

If we later need `gemma-4-thinking` for some reason, after `get_chat_template` returns, monkey-patch `tokenizer.chat_template` with a string that drops the `{%- if role == "model" -%}{{ '<|channel>thought\n<channel|>' }}{%- endif -%}` block and removes the channel injection from `add_generation_prompt`. The exact replacement is the file at [/opt/llama-swap/config/gemma4-tutor.jinja](file:///opt/llama-swap/config/gemma4-tutor.jinja) on the GB10 host *minus* the trailing `<|channel>thought\n<channel|>` we currently bake into `add_generation_prompt`. More fragile than Option 1; only worth it if we discover Option 1 regresses a behaviour we need.

---

## Required changes

### Change 1 — flip the default in both training scripts

In **both** [docs/research/train_gemma4_moe.py](../../docs/research/train_gemma4_moe.py) and [docs/research/train_gemma4_dense.py](../../docs/research/train_gemma4_dense.py):

```diff
 DEFAULTS = {
     ...
-    "chat_template": "gemma-4-thinking",  # Preserves <think> blocks
+    "chat_template": "gemma-4",  # Drops the <|channel>thought\n<channel|> wrapper.
+                                 # <think> blocks inside assistant content are preserved
+                                 # (they're plain text in the dataset). See
+                                 # domains/architect-agent-probe/DATASET-FIX-tutor-template-leak.md
     ...
 }
```

Also update the `--chat-template` argparse help so the recommended value isn't misleading anymore:

```diff
     p.add_argument("--chat-template", default=DEFAULTS["chat_template"],
                    choices=["gemma-4-thinking", "gemma-4"],
-                   help="gemma-4-thinking preserves <think> blocks (use this)")
+                   help="gemma-4 (default) avoids the <|channel>thought\\n<channel|> "
+                        "leak; gemma-4-thinking is retained only for reproducing "
+                        "the v3 fine-tune for comparison.")
```

### Change 2 — sanity check at the start of training

Add a fail-fast check to `formatting_prompts_func` so a regression on the chat template gets caught before we burn GPU hours:

```python
# After dataset = dataset.map(formatting_prompts_func, batched=True)
sample = dataset[0]["text"]
if "<|channel>thought" in sample:
    raise RuntimeError(
        "Formatted training text contains '<|channel>thought' — "
        "this would teach the model to leak the marker. "
        "Check --chat-template (should be 'gemma-4', not 'gemma-4-thinking'). "
        "See domains/architect-agent-probe/DATASET-FIX-tutor-template-leak.md"
    )
```

### Change 3 — dataset content stays as-is

No change to JSONL generation. The 75/25 think-block ratio in [docs/research/gcse-tutor-training-data-format.md](../../docs/research/gcse-tutor-training-data-format.md) is unaffected. `<think>...</think>` blocks remain inside `assistant.content` as plain text, and the new template wraps them in `<|turn>model\n…<turn|>` with no channel marker.

### Change 4 — eval gate

Before promoting the next fine-tune to production, run Phase 4.1–4.3 from the runbook with **the server-side `--chat-template-file` workaround removed**. All three must report CLEAN. If they do, the workaround can be retired.

---

## Retirement procedure (after the next fine-tune ships)

Once the new GGUF is deployed under `/opt/llama-swap/models/gemma4-tutor/` and validation passes:

1. Edit [/opt/llama-swap/config/config.yaml](file:///opt/llama-swap/config/config.yaml), tutor block:
   - Remove `--chat-template-file /opt/llama-swap/config/gemma4-tutor.jinja`
   - Keep `--jinja` (the GGUF's own template is fine — only the model's *trained reflex* was the problem, and that's gone).
2. `kill -HUP "$(pgrep -f '/llama-swap ' | head -1)"`
3. Re-run Phase 4 of the runbook. Confirm 5/5 clean.
4. `rm /opt/llama-swap/config/gemma4-tutor.jinja`
5. Update this doc and the runbook's status header to **Resolved upstream**.

If Phase 4 still leaks at that point, **stop**. The fine-tune did not cleanly un-learn the marker — restore the workaround, root-cause why (most likely the chat-template flag wasn't actually applied; verify via Change 2's check), and try again on the following run.

---

## Open question: should `train_gemma4_*.py` move to `scripts/`?

These files currently sit under `docs/research/` because they were prototyped there. They're now load-bearing for the production model. Worth a follow-up to either (a) move them under `scripts/` and import-test them, or (b) leave them in `docs/research/` but tag them as research-only and fork a productionised copy. Out of scope for this fix; flagging for triage.

---

*Created: 2026-04-29 alongside the v1 server-side workaround.*
