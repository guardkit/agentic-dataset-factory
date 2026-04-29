# Runbook: Fix Gemma 4 Tutor Template-Token Leak

**Status:** Resolved 2026-04-29 (server-side workaround applied; upstream fix pending — see [DATASET-FIX-tutor-template-leak.md](DATASET-FIX-tutor-template-leak.md))
**Purpose:** Suppress `<|channel>thought\n<channel|>` (and the trailing `<think>...</think>`) tokens leaking from the fine-tuned GCSE study tutor.
**Machine:** Dell DGX Spark GB10 (`promaxgb10-41b1`)
**Predecessor:** `RESULTS-v3-production-deployment.md` Follow-up #1
**Expected duration:** ~10 minutes (config edit + llama-swap reload + validation)

---

## Root cause (corrected after first execution)

The original hypothesis — *"the base Gemma 4 GGUF metadata includes a chat template with thinking support; `--reasoning off` will suppress it"* — was **wrong**. `--reasoning off` only changes how llama.cpp's *parser* surfaces thoughts in the response JSON; it does not modify prompt construction.

> ⚠️ **Red herring:** the original runbook cited the workhorse model as evidence (*"the workhorse model already uses `--reasoning off` and produces clean output"*). The workhorse is clean because it's a Qwen3 model with a Qwen chat template that has no channel-marker injection — *not* because `--reasoning off` is doing anything. Don't reach for `--reasoning off` first when triaging template leaks on a different model family; verify what its template actually contains via `curl http://localhost:5800/props | jq -r .chat_template`.

The real cause is two-part:

1. **GGUF-embedded Jinja template.** The `tokenizer.chat_template` in `gemma-4-26b-a4b-it.Q4_K_M.gguf` injects `<|channel>thought\n<channel|>` *before* the assistant's content for every assistant turn during prompt build. (Inspect via `curl http://localhost:5800/props | jq -r .chat_template`.)
2. **Fine-tune data leakage.** Because every assistant message in training was prefixed this way (Unsloth's `gemma-4-thinking` template applies the same wrapper), the model learned that `<|turn>model\n` is *always* followed by `<|channel>thought\n<channel|>`. Even when the runtime prompt does not include the marker, the model emits it.

So `--reasoning off` cannot fix this. Two server-side options remain:

- **Option C (`--no-jinja` alone) — fails.** llama.cpp can't auto-detect this custom Gemma 4 template and exits with `chat template parsing error: this custom template is not supported`. Without `--chat-template <name>`, the process dies on startup.
- **Option D (working) — provide a custom Jinja template that bakes the marker into `add_generation_prompt`.** The marker becomes part of the prompt, so the model's *output* starts after it. No leakage.

`--reasoning-format none` is **not** a fix: per llama.cpp's own help, that value "leaves thoughts unparsed in `message.content`" — i.e. preserves the leak.

---

## Phase 1: Baseline — confirm the leak exists

```bash
echo "=== Baseline: checking for template-token leak ==="
curl -s http://localhost:9000/v1/chat/completions \
    -H "Content-Type: application/json" \
    -d '{
        "model": "gemma4-tutor",
        "max_tokens": 256,
        "temperature": 0.7,
        "messages": [
            {"role": "system", "content": "You are a GCSE English Language tutor following the AQA specification. Use the Socratic method — guide the student to discover answers through questions rather than giving them directly."},
            {"role": "user", "content": "How do I get better marks on Paper 1 Question 5?"}
        ]
    }' | python3 -c "
import sys, json
text = json.load(sys.stdin)['choices'][0]['message']['content']
has_leak = '<|channel>' in text or '<think>' in text or '<channel|>' in text
print(f'Template leak present: {\"YES — needs fix\" if has_leak else \"NO — already clean\"}')
print()
print('First 400 chars:')
print(text[:400])
" 2>&1 | tee /tmp/tutor-leak-baseline.txt
```

**Expected:** YES — the output starts with `<|channel>thought\n<channel|>`.

---

## Phase 2: Apply fix — install the custom chat template

### 2.1 Drop in the template file

Write the GGUF's embedded template verbatim to `/opt/llama-swap/config/gemma4-tutor.jinja`, with one change: extend `add_generation_prompt` so it ends with `<|channel>thought\n<channel|>` (committing the marker as part of the prompt rather than expecting the model to emit it).

```bash
sudo install -o richardwoollcott -g richardwoollcott -m 0644 /dev/stdin /opt/llama-swap/config/gemma4-tutor.jinja <<'JINJA'
{{ bos_token }}{%- if messages[0]['role'] == 'system' -%}
    {%- set first_user_prefix = messages[0]['content'] + '

' -%}
    {%- set loop_messages = messages[1:] -%}
{%- else -%}
    {%- set first_user_prefix = "" -%}
    {%- set loop_messages = messages -%}
{%- endif -%}
{%- for message in loop_messages -%}
    {%- if (message['role'] == 'user') != (loop.index0 % 2 == 0) -%}
        {{ raise_exception("Conversation roles must alternate user/assistant/user/assistant/...") }}
    {%- endif -%}
    {%- if (message['role'] == 'assistant') -%}
        {%- set role = "model" -%}
    {%- else -%}
        {%- set role = message['role'] -%}
    {%- endif -%}
    {{ '<|turn>' + role + '
' + (first_user_prefix if loop.first else "") }}
    {%- if role == "model" -%}
        {{ '<|channel>thought
<channel|>' }}
    {%- endif -%}
    {%- if message['content'] is string -%}
        {{ message['content'] | trim }}
    {%- elif message['content'] is iterable -%}
        {%- for item in message['content'] -%}
            {%- if item['type'] == 'audio' -%}
                {{ '<|audio|>' }}
            {%- elif item['type'] == 'image' -%}
                {{ '<|image|>' }}
            {%- elif item['type'] == 'video' -%}
                {{ '<|video|>' }}
            {%- elif item['type'] == 'text' -%}
                {{ item['text'] | trim }}
            {%- endif -%}
        {%- endfor -%}
    {%- else -%}
        {{ raise_exception("Invalid content type") }}
    {%- endif -%}
    {{ '<turn|>
' }}
{%- endfor -%}
{%- if add_generation_prompt -%}
    {{'<|turn>model
<|channel>thought
<channel|>'}}
{%- endif -%}
JINJA
```

### 2.2 Point llama-swap at it

```bash
CONFIG="/opt/llama-swap/config/config.yaml"
cp "$CONFIG" "${CONFIG}.pre-template-fix.bak"

# Replace `--jinja` (and any `--reasoning off` left over from earlier attempts)
# with `--jinja --chat-template-file ...` in the gemma4-tutor block only.
python3 - <<'PY'
import pathlib, re
p = pathlib.Path("/opt/llama-swap/config/config.yaml")
text = p.read_text()
# Match the tutor cmd block
m = re.search(r'("gemma4-tutor":[\s\S]*?)checkEndpoint:', text)
assert m, "tutor block not found"
block = m.group(1)
# Drop a stale --reasoning off line if present
new = re.sub(r'\n\s+--reasoning off', '', block)
# Replace bare --jinja with --jinja + custom template file
new = re.sub(
    r'--jinja(?!\s*--chat-template-file)',
    '--jinja\n      --chat-template-file /opt/llama-swap/config/gemma4-tutor.jinja',
    new, count=1)
p.write_text(text.replace(block, new))
print("config patched")
PY

sed -n '/gemma4-tutor/,/checkEndpoint/p' "$CONFIG"
```

---

## Phase 3: Reload llama-swap

llama-swap caches its config in memory at startup. **Killing the child process does NOT reload the on-disk config** — llama-swap respawns the child with the cached cmd. Send `SIGHUP` to llama-swap itself (or run it with `-watch-config` going forward — see the systemd unit proposal under "Operational follow-ups" below).

> ⚠️ **Do not `pkill -f "gemma4-tutor"`** from inside a script. The `-f` matches against the *full command line*, which includes the bash script's own argv (heredocs, JSON bodies, etc. that contain the model name). The script kills itself with exit 144. Either look up the child PID from `/running` and `kill` it directly, or scope the pkill so it can't match anything but the child process: `pkill -f 'llama-server.*--alias gemma4-tutor'`.

```bash
SWAP_PID=$(pgrep -f "/llama-swap " | head -1)
echo "swap pid: $SWAP_PID"
kill -HUP "$SWAP_PID"

echo "Waiting for tutor ready..."
for i in $(seq 1 60); do
  STATE=$(curl -s --max-time 5 http://localhost:9000/running 2>/dev/null \
    | python3 -c "
import sys, json
data = json.load(sys.stdin)
for m in data.get('running', []):
    if 'tutor' in m.get('model',''):
        print(m.get('state',''))
        break
" 2>/dev/null)
  [ "$STATE" = "ready" ] && { echo "  attempt $i: ready"; break; }
  echo "  attempt $i: state=${STATE:-(not in /running)}"
  sleep 5
done
```

After ready, confirm the loaded template ends with the doctored generation prompt:

```bash
curl -s http://localhost:5800/props | python3 -c "
import sys, json
ct = json.load(sys.stdin).get('chat_template','')
print(ct[-200:])
"
# Expected last line: <|channel>thought\n<channel|>
```

---

## Phase 4: Validate fix — three test prompts

### 4.1 Same prompt as baseline

```bash
echo "=== Test 1: Same prompt as baseline ==="
curl -s http://localhost:9000/v1/chat/completions \
    -H "Content-Type: application/json" \
    -d '{
        "model": "gemma4-tutor",
        "max_tokens": 256,
        "temperature": 0.7,
        "messages": [
            {"role": "system", "content": "You are a GCSE English Language tutor following the AQA specification. Use the Socratic method — guide the student to discover answers through questions rather than giving them directly."},
            {"role": "user", "content": "How do I get better marks on Paper 1 Question 5?"}
        ]
    }' | python3 -c "
import sys, json
text = json.load(sys.stdin)['choices'][0]['message']['content']
has_leak = '<|channel>' in text or '<think>' in text or '<channel|>' in text or '<|turn>' in text or '<turn|>' in text
print(f'Template leak: {\"STILL PRESENT — fix did not work\" if has_leak else \"CLEAN\"}')
print()
print(text[:400])
"
```

### 4.2 Multi-turn conversation

```bash
echo "=== Test 2: Multi-turn conversation ==="
curl -s http://localhost:9000/v1/chat/completions \
    -H "Content-Type: application/json" \
    -d '{
        "model": "gemma4-tutor",
        "max_tokens": 256,
        "temperature": 0.7,
        "messages": [
            {"role": "system", "content": "You are a GCSE English Language tutor following the AQA specification. Use the Socratic method."},
            {"role": "user", "content": "I need help with Paper 2 Question 2 comparing two sources."},
            {"role": "assistant", "content": "Great question! Comparing sources is all about finding similarities and differences in how the writers present their ideas. Can you tell me what you find hardest about it — is it identifying the differences, or is it writing them up clearly?"},
            {"role": "user", "content": "I can see the differences but I never know how to structure my answer."}
        ]
    }' | python3 -c "
import sys, json
text = json.load(sys.stdin)['choices'][0]['message']['content']
has_leak = '<|channel>' in text or '<think>' in text or '<channel|>' in text or '<|turn>' in text or '<turn|>' in text
print(f'Template leak: {\"STILL PRESENT\" if has_leak else \"CLEAN\"}')
print()
print(text[:400])
"
```

### 4.3 Stability — 5 sequential requests

```bash
echo "=== Test 3: Stability (5 runs) ==="
LEAK_COUNT=0
for i in $(seq 1 5); do
    RESULT=$(curl -s http://localhost:9000/v1/chat/completions \
        -H "Content-Type: application/json" \
        -d "{
            \"model\": \"gemma4-tutor\",
            \"max_tokens\": 200,
            \"temperature\": 0.7,
            \"messages\": [
                {\"role\": \"system\", \"content\": \"You are a GCSE English Language tutor. Use the Socratic method.\"},
                {\"role\": \"user\", \"content\": \"What is the difference between narrative and descriptive writing?\"}
            ]
        }" | python3 -c "
import sys, json
text = json.load(sys.stdin)['choices'][0]['message']['content']
has_leak = '<|channel>' in text or '<think>' in text or '<channel|>' in text
print('LEAK' if has_leak else 'CLEAN')
" 2>/dev/null)
    echo "  Run $i: $RESULT"
    [ "$RESULT" = "LEAK" ] && LEAK_COUNT=$((LEAK_COUNT + 1))
done
echo ""
echo "Leak count: $LEAK_COUNT/5"
echo "$([ $LEAK_COUNT -eq 0 ] && echo 'PASS: fix confirmed stable' || echo 'FAIL: leak persists')"
```

---

## Phase 5: Decision gate

| Test | Result on 2026-04-29 | Notes |
|---|---|---|
| P1: Baseline leak confirmed | PASS | `<\|channel>thought\n<channel\|>` and `<think>` observed |
| P2: Custom template installed + config patched | PASS | |
| P3: Tutor reloaded via `kill -HUP <llama-swap pid>` | PASS | child PID change confirms respawn |
| P4.1: Same prompt — clean | PASS | |
| P4.2: Multi-turn — clean | PASS | |
| P4.3: Stability 5/5 clean | PASS | |

### All pass → confirm fix

```bash
rm /opt/llama-swap/config/config.yaml.pre-template-fix.bak
echo "Fix confirmed and backup removed."
```

### Fix doesn't work → escalation options

**Option E (last resort): rewrite the chat template inside the GGUF.**
This permanently modifies the model file. Prefer the server-side approach above.

```bash
python3 ~/llama.cpp/gguf-py/gguf/scripts/gguf_new_metadata.py \
    --chat-template "$(cat /opt/llama-swap/config/gemma4-tutor.jinja)" \
    /opt/llama-swap/models/gemma4-tutor/gemma-4-26b-a4b-it.Q4_K_M.gguf \
    /opt/llama-swap/models/gemma4-tutor/gemma-4-26b-a4b-it.Q4_K_M.patched.gguf
# Then point the tutor at the patched GGUF and drop --chat-template-file.
```

### Rollback

```bash
cp /opt/llama-swap/config/config.yaml.pre-template-fix.bak \
   /opt/llama-swap/config/config.yaml
kill -HUP "$(pgrep -f '/llama-swap ' | head -1)"
```

---

## Operational follow-ups

1. **Supervise llama-swap with a systemd user unit.** Installed and active as of 2026-04-29. Full record (unit file, validation, pending sudo cleanup of a stale legacy system unit, rollback) is in [`guardkit/docs/research/dgx-spark/llama-swap-systemd-supervision.md`](../../../../guardkit/docs/research/dgx-spark/llama-swap-systemd-supervision.md). With `-watch-config` now active, future config edits (e.g. swapping the tutor's `--chat-template-file`) auto-reload — no manual `kill -HUP` step needed; the runbook's Phase 3 still works as a fallback.
2. **Self-kill hazard on `pkill -f`.** Already inlined into Phase 3 — keeping it noted here so it doesn't get edited out of the inline warning by accident.

## Cross-references

- Server-side fix files: [/opt/llama-swap/config/gemma4-tutor.jinja](/opt/llama-swap/config/gemma4-tutor.jinja), [/opt/llama-swap/config/config.yaml](/opt/llama-swap/config/config.yaml)
- Upstream (dataset/training) fix to drop this server workaround after the next fine-tune: [DATASET-FIX-tutor-template-leak.md](DATASET-FIX-tutor-template-leak.md)
- Background: `RESULTS-v3-production-deployment.md` Follow-up #1, `RUNBOOK-v3-production-deployment.md`

*First executed: 2026-04-29 (this revision incorporates corrections from that run)*
