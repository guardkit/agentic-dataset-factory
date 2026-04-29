# Runbook: Fix Gemma 4 Tutor Template-Token Leak

**Purpose:** Fix the `<|channel>thought<channel|>` and `<think>...</think>` token leak in the fine-tuned GCSE study tutor model output.
**Machine:** Dell DGX Spark GB10 (`promaxgb10-41b1`)
**Predecessor:** `RESULTS-v3-production-deployment.md` Follow-up #1
**Root cause:** The base Gemma 4 GGUF metadata includes a chat template with thinking/reasoning support. `--jinja` reads this from the GGUF, not the Ollama Modelfile. The fine-tune didn't train away the thinking tokens. The workhorse model already uses `--reasoning off` and produces clean output.
**Expected duration:** ~5 minutes

---

## Phase 1: Baseline — Confirm the Leak Exists

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

**Expected:** YES — the output contains `<|channel>thought<channel|>` and/or `<think>...</think>` blocks before the actual tutoring response.

**If NO:** The leak may have been intermittent or already fixed. Run three more times to confirm, then skip to Phase 4.

---

## Phase 2: Apply Fix — Add `--reasoning off` to Tutor Config

```bash
echo "=== Applying fix: --reasoning off ==="

CONFIG="/opt/llama-swap/config/config.yaml"

# Back up current config
cp "$CONFIG" "${CONFIG}.pre-reasoning-fix.bak"

# Check if --reasoning off is already present for the tutor
if grep -A 20 "gemma4-tutor" "$CONFIG" | grep -q "reasoning off"; then
    echo "Fix already applied — --reasoning off present in tutor config"
else
    # Insert --reasoning off after the --jinja line in the tutor block
    # Find the tutor's --jinja line and add --reasoning off after it
    sed -i '/--alias gemma4-tutor/,/checkEndpoint/{
        /--jinja/a\      --reasoning off
    }' "$CONFIG"
    echo "Added --reasoning off to gemma4-tutor config"
fi

# Verify the change
echo ""
echo "=== Tutor config block (post-fix) ==="
sed -n '/gemma4-tutor/,/checkEndpoint/p' "$CONFIG"
```

---

## Phase 3: Restart the Tutor Model

llama-swap reloads model config when the child process restarts. Kill the tutor child — the keep-alive timer (or a manual request) will revive it with the new flags.

```bash
echo "=== Restarting tutor model ==="

# Get the tutor's PID from llama-swap's running list
TUTOR_PID=$(curl -s http://localhost:9000/running 2>/dev/null | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    # Handle both list and dict formats
    if isinstance(data, list):
        for m in data:
            name = m.get('model', '') if isinstance(m, dict) else str(m)
            if 'gemma4-tutor' in str(name):
                print(m.get('pid', ''))
                break
    elif isinstance(data, dict):
        for k, v in data.items():
            if 'gemma4-tutor' in str(k) or 'gemma4-tutor' in str(v):
                if isinstance(v, dict):
                    print(v.get('pid', ''))
                break
except:
    pass
" 2>/dev/null)

if [ -n "$TUTOR_PID" ] && [ "$TUTOR_PID" != "" ]; then
    echo "Killing tutor child PID: $TUTOR_PID"
    kill "$TUTOR_PID" 2>/dev/null
else
    echo "Could not find tutor PID from /running — trying pkill"
    # The tutor's llama-server process has gemma4-tutor in its args
    pkill -f "gemma4-tutor" 2>/dev/null || true
fi

echo "Waiting for keep-alive to revive (or triggering manually)..."
sleep 5

# Trigger a request to force llama-swap to respawn with new config
curl -s http://localhost:9000/v1/chat/completions \
    -H "Content-Type: application/json" \
    -d '{"model":"gemma4-tutor","max_tokens":1,"messages":[{"role":"user","content":"test"}]}' > /dev/null 2>&1

# Wait for the model to fully load
echo "Waiting for tutor to load..."
ATTEMPTS=0
while [ $ATTEMPTS -lt 30 ]; do
    RESULT=$(curl -s --max-time 5 http://localhost:9000/v1/chat/completions \
        -H "Content-Type: application/json" \
        -d '{"model":"gemma4-tutor","max_tokens":1,"messages":[{"role":"user","content":"ping"}]}' 2>/dev/null)
    if echo "$RESULT" | grep -q "choices"; then
        echo "Tutor model reloaded successfully (attempt $((ATTEMPTS+1)))"
        break
    fi
    ATTEMPTS=$((ATTEMPTS + 1))
    sleep 10
done

if [ $ATTEMPTS -ge 30 ]; then
    echo "ERROR: Tutor did not reload within 5 minutes. Check logs:"
    echo "  tail -50 /opt/llama-swap/logs/llama-swap.log"
    exit 1
fi
```

---

## Phase 4: Validate Fix — Three Test Prompts

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

### 4.2 Multi-turn conversation (leaks sometimes only appear on turn 2+)

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

## Phase 5: Decision Gate

| Test | Result | Notes |
|---|---|---|
| P1: Baseline leak confirmed | | |
| P2: `--reasoning off` added to config | | |
| P3: Tutor model restarted | | |
| P4.1: Same prompt — clean | | |
| P4.2: Multi-turn — clean | | |
| P4.3: Stability 5/5 clean | | |

### All pass → Fix confirmed

Remove the config backup:
```bash
rm /opt/llama-swap/config/config.yaml.pre-reasoning-fix.bak
echo "Fix confirmed and backup removed."
```

### Fix doesn't work → Escalate

If `--reasoning off` doesn't suppress the tokens, try these in order:

**Option A:** Try `--reasoning-format none` instead of `--reasoning off`:
```bash
sed -i 's/--reasoning off/--reasoning-format none/' /opt/llama-swap/config/config.yaml
# Then repeat Phase 3 restart + Phase 4 tests
```

**Option B:** Strip the thinking template from the GGUF metadata:
```bash
# This permanently modifies the GGUF file
python3 ~/llama.cpp/gguf-py/scripts/gguf_set_metadata.py \
    /opt/llama-swap/models/gemma4-tutor/gemma-4-26b-a4b-it.Q4_K_M.gguf \
    tokenizer.chat_template.reasoning ""
# Then restart the tutor
```

**Option C:** Disable `--jinja` for the tutor only and rely on llama.cpp's built-in Gemma template (loses custom template but eliminates all metadata-derived tokens).

### Rollback

```bash
cp /opt/llama-swap/config/config.yaml.pre-reasoning-fix.bak \
   /opt/llama-swap/config/config.yaml
# Kill and revive the tutor as in Phase 3
```

---

*Prepared: 2026-04-29*
*Cross-references: RESULTS-v3-production-deployment.md Follow-up #1, RUNBOOK-v3-production-deployment.md*
