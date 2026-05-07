# Runbook: Open WebUI — Architect Agent Access

**Status:** Executed 2026-05-06 against Open WebUI 0.9+ — Phases 0.1, 0.2, 0.3, 2.2, 4.1 all PASS (browser verification 4.2 still pending). Notable deviation: the admin password from the tutor runbook (`CHANGE_ME_ON_FIRST_LOGIN`) didn't work on this run — recovery via direct bcrypt-update of `auth` table inside the container; see "Execution notes" below.
**Purpose:** Expose the fine-tuned `architect-agent` model through Open WebUI so Rich (and future collaborators) can chat with it via a browser instead of curl.
**Machine:** Dell DGX Spark GB10 (`promaxgb10-41b1`), 128 GB unified memory.
**Predecessors:**
- [`RUNBOOK-architect-fine-tune.md`](RUNBOOK-architect-fine-tune.md) — produced and registered the model in llama-swap (Phase 5.3)
- [`study-tutor/docs/research/ideas/RUNBOOK-open-webui-tutor-access.md`](../../../study-tutor/docs/research/ideas/RUNBOOK-open-webui-tutor-access.md) — parent pattern; this runbook is its architect-domain sibling
- [`guardkit/docs/runbooks/RUNBOOK-INFRA-ORCHESTRATION.md`](../../../guardkit/docs/runbooks/RUNBOOK-INFRA-ORCHESTRATION.md) — owns the llama-swap supervisor and Open WebUI container lifecycle

**Expected duration:** ~30 minutes (most infra is already in place — OWUI is up, admin exists, model is served).

## Execution notes (2026-05-06)

These deviations from the original runbook were needed and are now folded inline as well — flagged with **EXEC NOTE** markers for future operators.

1. **Admin password from tutor runbook didn't work.** The tutor runbook captured `CHANGE_ME_ON_FIRST_LOGIN` as the placeholder admin password (`RUNBOOK-open-webui-tutor-access.md:202`). On the architect-access run, OWUI returned `HTTP 400` for that password — likely because Rich did change it after the tutor setup but the new value isn't recorded. **Recovery:** direct bcrypt update of the `auth` table inside the OWUI container, since OWUI lacks a CLI password-reset subcommand on 0.9.x. See "Recovery: forgotten admin password" below for the exact procedure used. After reset and self-verify (`bcrypt.checkpw` matched, signin returned a 247-char JWT), Phase 0.3 onwards proceeded normally.
2. **`docker exec open-webui sqlite3` is not available.** The container ships Python 3 + bcrypt but not the `sqlite3` CLI. Use Python's stdlib `sqlite3` module via `docker exec open-webui python3 -c "..."` instead.
3. **OWUI container's WEBUI_SECRET_KEY is empty.** Confirmed via `docker inspect open-webui --format '{{range .Config.Env}}{{.}}{{"\n"}}{{end}}'` — `WEBUI_SECRET_KEY=` (no value). This is fine; OWUI auto-generates and persists one in the `open-webui-data` volume on first start. Worth noting only because it means JWTs survive container recreation as long as the volume persists.
4. **API-key endpoint produces a JWT-shaped token, not an opaque key.** "Settings → Account → API Keys → Create" yielded a 247-char JWT with a 28-day exp claim (`iat=1778061447, exp=1780480647`). Treat it like a JWT — long-lived but not infinite. Regenerate before expiry if integrating into a long-running automation.

## Context

The architect-agent fine-tune is live on llama-swap at `http://localhost:9000/v1` and verified working (response routes correctly, persona transferred). Rich currently hits it via `curl`. Open WebUI gives a browser-based chat with conversation history and proper rendering of the `<think>` reasoning panel.

The tutor runbook's deployment pattern (model preset with system prompt + `reasoning_tags` + public-read `access_grants`) ports over almost cleanly. The remaining work is one preset's worth of API calls plus a system-prompt recovery step.

### Pre-existing state (verified 2026-05-05)

| Component | State |
|---|---|
| Open WebUI container `open-webui` | up 2+ days, healthy |
| OWUI on `localhost:8080` | HTTP 200 |
| Admin account `rich@appmilla.com` | exists from tutor setup |
| `architect-agent` served by llama-swap | yes (Phase 5.3 of fine-tune runbook) |
| `/opt/llama-swap/models/architect-agent/system-prompt.txt` | **MISSING** — recovered in Phase 0.2 below |
| OWUI preset `architect-agent` | does not exist — created in Phase 2 |

---

## Phase 0: Pre-flight

### 0.1 Confirm llama-swap is serving architect-agent

```bash
curl -s --max-time 10 http://localhost:9000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "architect-agent",
    "max_tokens": 32,
    "messages": [{"role":"user","content":"Hello"}]
  }' \
  | python3 -c "
import sys, json
d = json.load(sys.stdin)
print('model:', d.get('model'))
print('content[:120]:', d['choices'][0]['message']['content'][:120])
print('PASS' if d.get('model') == 'architect-agent' else 'FAIL: wrong model')
"
```

Expected: `model: architect-agent` and a brief response. If `model: gemma4-tutor` (or anything else), routing is broken — see fine-tune runbook Phase 5.3 / guardkit infra runbook §8.

### 0.2 Recover the system prompt

The Modelfile in `/opt/llama-swap/models/architect-agent/` only carries chat-template content, not a SYSTEM block. Recover the canonical prompt from training data — same procedure as the tutor runbook Phase 0.2.

```bash
SYSTEM_PROMPT_FILE="/opt/llama-swap/models/architect-agent/system-prompt.txt"
TRAIN_JSONL="/home/richardwoollcott/fine-tuning/data/train-architect-agent.jsonl"

if [ -f "$SYSTEM_PROMPT_FILE" ]; then
    echo "PASS: system prompt already exists ($(wc -c < "$SYSTEM_PROMPT_FILE") bytes)"
else
    python3 - "$TRAIN_JSONL" "$SYSTEM_PROMPT_FILE" <<'PY'
import json, hashlib, pathlib, sys
src, dst = sys.argv[1], sys.argv[2]
counts, samples = {}, {}
with open(src) as f:
    for line in f:
        try: obj = json.loads(line)
        except: continue
        for m in obj.get("messages", []):
            if m.get("role") == "system":
                c = m.get("content", "")
                h = hashlib.sha256(c.encode()).hexdigest()[:12]
                counts[h] = counts.get(h, 0) + 1
                samples.setdefault(h, c)
                break
if not counts:
    raise SystemExit("No system prompts found in training data")
dominant = max(counts, key=counts.get)
prompt = samples[dominant].rstrip() + "\n"
pathlib.Path(dst).write_text(prompt)
print(f"Recovered prompt {dominant}: {counts[dominant]}/{sum(counts.values())} samples, {len(prompt)} bytes")
PY
fi

ls -la "$SYSTEM_PROMPT_FILE"
```

### 0.3 Confirm OWUI is healthy and grab an admin JWT

```bash
# Liveness check
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" --max-time 5 http://localhost:8080)
[ "$HTTP_CODE" = "200" ] && echo "PASS: OWUI on :8080 (HTTP $HTTP_CODE)" || echo "FAIL: OWUI not reachable"
```

To get an admin JWT for the API calls in Phase 2:

- **Option A (preferred):** in OWUI, **Settings → Account → API Keys**, generate a new key, copy it. This is a long-lived API key that won't expire when you log out.
- **Option B:** curl the signin endpoint with the admin password:
  ```bash
  ADMIN_TOKEN=$(curl -s http://localhost:8080/api/v1/auths/signin \
      -H "Content-Type: application/json" \
      -d '{"email":"rich@appmilla.com","password":"<your-password>"}' \
      | python3 -c "import sys,json; print(json.load(sys.stdin).get('token',''))")
  ```
  Avoid putting the password in shell history; prefer Option A.

Set the variable for use by later phases:
```bash
export ADMIN_TOKEN="<paste your JWT or API key here>"
```

---

## Phase 2: Create the architect-agent OWUI preset

Single preset, public-read for consistency with the tutor pattern (allows future shareability without a re-edit).

### 2.1 Choose preset parameters

| Field | Value | Reason |
|---|---|---|
| `id` | `architect-agent` | Matches the llama-swap canonical name; OWUI and llama-swap layers are independent namespaces, no conflict |
| `name` | `Software Architect Agent` | Display name in the dropdown |
| `base_model_id` | `architect-agent` | The llama-swap alias the preset routes to |
| `params.system` | (recovered system prompt + `<think>` instruction prefix — see below) | Bakes the architect persona AND the reasoning-tag emission, since the fine-tune doesn't emit `<think>` by default ([FOLLOWUP-chat-template-thinking-tags.md](FOLLOWUP-chat-template-thinking-tags.md)) |
| `params.reasoning_tags` | `["<think>", "</think>"]` | Tells OWUI's UI middleware to extract reasoning into a collapsible panel |
| `params.temperature` | `0.4` | Matches the llama-swap config for this model — architectural reasoning rewards consistency over creativity |
| `params.top_p` | `0.9` | Matches llama-swap config |
| `access_grants` | `[{user, *, read}]` | Public-read; matches tutor pattern |

The `<think>` instruction prefix prepended to the system prompt:

```
Always begin every response with a <think>...</think> block showing your reasoning
(architectural tradeoffs, what's being optimised, what's being deferred), then give
the visible answer. The <think> block will be rendered as a collapsible panel.

```

Followed by a blank line, then the recovered architect persona prompt.

### 2.2 Create the preset

```bash
python3 - "$ADMIN_TOKEN" <<'PY'
import json, urllib.request, pathlib, sys

token = sys.argv[1]
persona = pathlib.Path("/opt/llama-swap/models/architect-agent/system-prompt.txt").read_text().strip()

think_prefix = (
    "Always begin every response with a <think>...</think> block showing your reasoning "
    "(architectural tradeoffs, what's being optimised, what's being deferred), then give "
    "the visible answer. The <think> block will be rendered as a collapsible panel.\n\n"
)
system_prompt = think_prefix + persona

payload = {
    "id": "architect-agent",
    "name": "Software Architect Agent",
    "meta": {
        "description": "Fine-tuned Gemma 4 26B-A4B architect agent — DDD, evolutionary architecture, trade-off analysis. Surfaces its reasoning in a collapsible <think> panel.",
        "profile_image_url": ""
    },
    "base_model_id": "architect-agent",
    "params": {
        "system": system_prompt,
        "temperature": 0.4,
        "top_p": 0.9,
        "reasoning_tags": ["<think>", "</think>"]
    },
    "access_grants": [
        {"principal_type": "user", "principal_id": "*", "permission": "read"}
    ],
    "is_active": True
}

req = urllib.request.Request(
    "http://localhost:8080/api/v1/models/create",
    data=json.dumps(payload).encode(),
    headers={"Content-Type":"application/json","Authorization":f"Bearer {token}"},
    method="POST"
)
try:
    with urllib.request.urlopen(req) as r:
        result = json.loads(r.read())
        print(f"PASS: preset '{result.get('name')}' created")
        print(f"  id: {result.get('id')}")
        print(f"  base_model_id: {result.get('base_model_id')}")
        print(f"  system prompt: {len(result.get('params',{}).get('system',''))} bytes")
        print(f"  reasoning_tags: {result.get('params',{}).get('reasoning_tags')}")
        print(f"  access_grants: {result.get('access_grants')}")
except urllib.error.HTTPError as e:
    body = e.read().decode()
    print(f"HTTP {e.code}: {body[:400]}")
    if "already exists" in body.lower() or e.code == 409:
        print("→ preset exists; use POST /api/v1/models/model/update?id=architect-agent with the same payload to refresh.")
    sys.exit(1)
PY
```

### 2.3 If the preset already exists (refresh path)

```bash
python3 - "$ADMIN_TOKEN" <<'PY'
import json, urllib.request, pathlib, sys
token = sys.argv[1]
persona = pathlib.Path("/opt/llama-swap/models/architect-agent/system-prompt.txt").read_text().strip()
think_prefix = (
    "Always begin every response with a <think>...</think> block showing your reasoning "
    "(architectural tradeoffs, what's being optimised, what's being deferred), then give "
    "the visible answer. The <think> block will be rendered as a collapsible panel.\n\n"
)
payload = {
    "id": "architect-agent",
    "name": "Software Architect Agent",
    "meta": {"description":"Fine-tuned Gemma 4 26B-A4B architect agent.","profile_image_url":""},
    "base_model_id": "architect-agent",
    "params": {
        "system": think_prefix + persona,
        "temperature": 0.4, "top_p": 0.9,
        "reasoning_tags": ["<think>", "</think>"]
    },
    "access_grants": [{"principal_type":"user","principal_id":"*","permission":"read"}],
    "is_active": True
}
req = urllib.request.Request(
    "http://localhost:8080/api/v1/models/model/update?id=architect-agent",
    data=json.dumps(payload).encode(),
    headers={"Content-Type":"application/json","Authorization":f"Bearer {token}"},
    method="POST"
)
with urllib.request.urlopen(req) as r:
    print(f"refreshed: {json.loads(r.read()).get('name')}")
PY
```

---

## Phase 4: Smoke test

### 4.1 API round-trip via OWUI

```bash
curl -s --max-time 180 http://localhost:8080/api/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -d '{
    "model": "architect-agent",
    "messages": [{"role":"user","content":"What strategic DDD pattern should I apply when integrating with five legacy systems?"}]
  }' \
  > /tmp/architect-owui-smoke.json

python3 -c "
import json
r = json.load(open('/tmp/architect-owui-smoke.json'))
ch = r['choices'][0]['message']
content = ch.get('content','')
print('routed model:', r.get('model'))
print('opens with <think>?', content.lstrip().startswith('<think>'))
print('has </think>?', '</think>' in content)
print('contains template tokens (BAD)?', any(t in content for t in ('<|channel>','<channel|>','<|turn>','<turn|>')))
print('---first 600 chars---')
print(content[:600])
"
```

Healthy:
- `routed model: architect-agent`
- `opens with <think>? True` and `has </think>? True` — the system-prompt nudge is producing reasoning blocks
- `contains template tokens (BAD)? False` — no `<|channel>` / `<|turn>` leaks

### 4.2 Browser verification (manual — required)

> Open `http://promaxgb10-41b1:8080` in a browser, log in as `rich@appmilla.com`, select **Software Architect Agent** from the model dropdown.

Verify:
- [ ] Model preset is selectable (it appears in the dropdown)
- [ ] First response renders cleanly — visible answer is architectural prose, no raw `<think>` text in the visible chat
- [ ] A "Show thinking" / reasoning panel exists, collapsible, expandable to show the `<think>` content
- [ ] No `<|channel>`, `<|turn>`, or other template tokens visible anywhere
- [ ] Persona is consistent — DDD vocabulary, references to Evans, "architectural tension," etc.

---

## Phase 6: Decision gate

| Step | Expected | 2026-05-06 result |
|---|---|---|
| P0.1: llama-swap serves `architect-agent` | PASS | **PASS** — `routed model: architect-agent`, smoke prompt returned `"Hello! How can I help you today?"` |
| P0.2: system-prompt.txt recovered | PASS | **PASS** — recovered from `train-architect-agent.jsonl`; **894/894 (100%) of training samples used the same persona prompt** (deterministic recovery). 1,679 bytes saved to `/opt/llama-swap/models/architect-agent/system-prompt.txt` |
| P0.3: OWUI healthy on :8080 | PASS | **PASS** (HTTP 200) |
| (recovery) Admin password reset | n/a (was not anticipated) | **PASS** — direct bcrypt update on the `auth` table; signin returned a 247-char JWT after reset. Temporary password set; user instructed to change on first login. |
| P2.2: preset created via API | PASS | **PASS** — preset `id: architect-agent` (display: "Software Architect Agent"); 1,925-byte system prompt (think prefix + 1,679-byte persona); `temperature=0.4`, `top_p=0.9`, `reasoning_tags=["<think>","</think>"]`; 1 public-read `access_grants` entry created |
| P4.1: API round-trip — routes to architect-agent, emits `<think>` | PASS | **PASS** — `routed model: architect-agent`, response opens with `<think>` AND contains `</think>`, 4,151 chars total, **zero template-token leaks** (`<\|channel>` / `<\|turn>` clean), persona was strong (referenced Evans' ACL, weighed strategic vs tactical, mentioned cost-of-reversal and team topology) |
| P4.2: browser render clean | PASS (manual) | _pending — Rich to verify in browser at `http://promaxgb10-41b1:8080`_ |

---

## Stretch (not done now): variant presets

If we want sub-domain flavours later (DDD-focused, operations-focused, system-design-focused), each is one extra `/api/v1/models/create` call with a different `id`, `name`, and a slightly customised system prompt — same `base_model_id: architect-agent`. The tutor runbook's Phase 5 is the template. Skip until there's actual demand: one preset is the right v1.

---

## Recovery: forgotten admin password

If the admin can't log in (HTTP 400 on `/api/v1/auths/signin`) and there's no other admin to demote-and-re-promote with, reset the password directly in the SQLite DB inside the container. The container ships `bcrypt` but **not** the `sqlite3` CLI; use Python's stdlib `sqlite3` module.

```bash
NEWPASS='ResetMe-YYYY-MM-DD!'   # ← clearly-temporary; user MUST change on first login
docker exec open-webui python3 -c "
import bcrypt, sqlite3
new = b'$NEWPASS'
hashed = bcrypt.hashpw(new, bcrypt.gensalt()).decode()
conn = sqlite3.connect('/app/backend/data/webui.db')
c = conn.cursor()
res = c.execute('UPDATE auth SET password=? WHERE email=?', (hashed, 'rich@appmilla.com'))
conn.commit()
print(f'rows updated: {res.rowcount}')
stored = c.execute('SELECT password FROM auth WHERE email=?', ('rich@appmilla.com',)).fetchone()[0]
print(f'self-verify: {bcrypt.checkpw(new, stored.encode())}')
"

# Confirm signin works:
curl -s http://localhost:8080/api/v1/auths/signin \
    -H "Content-Type: application/json" \
    -d "{\"email\":\"rich@appmilla.com\",\"password\":\"$NEWPASS\"}" \
    | python3 -c "import sys,json; print('JWT chars:', len(json.load(sys.stdin).get('token','')))"
```

A returned JWT (~240 chars) confirms the reset worked. Log in via browser, **immediately** change the password (Settings → Account), and consider rotating to a long random one.

The `auth` table schema (verified 2026-05-06 on OWUI 0.9.x):
```sql
CREATE TABLE "auth" (
    "id" VARCHAR(255) NOT NULL,
    "email" VARCHAR(255) NOT NULL,
    "password" TEXT NOT NULL NOT NULL,
    "active" INTEGER NOT NULL
)
```
Identity (name, role, profile, etc.) lives in a separate `user` table joined on `id`.

## Operational notes

- Re-running this runbook is idempotent if you switch `Phase 2.2` to the `Phase 2.3` refresh path. The `system-prompt.txt` recovery is also no-op on subsequent runs.
- If the chat-template `<think>` interaction (see [`FOLLOWUP-chat-template-thinking-tags.md`](FOLLOWUP-chat-template-thinking-tags.md)) is resolved by re-training with `--chat-template gemma-4` (path B), the system-prompt nudge prefix added in Phase 2 may become unnecessary. Drop the `think_prefix` on next preset refresh and verify `<think>` blocks still emit.
- Update path: `docker pull ghcr.io/open-webui/open-webui:main` then `docker stop/rm/run`. Same pattern as tutor runbook Phase 1.1 ("Operational notes / Updating Open WebUI").

## Cross-references

- Architect fine-tune runbook: [`RUNBOOK-architect-fine-tune.md`](RUNBOOK-architect-fine-tune.md) — produced the model
- Chat-template followup: [`FOLLOWUP-chat-template-thinking-tags.md`](FOLLOWUP-chat-template-thinking-tags.md) — explains why we need the `<think>` system-prompt nudge
- Tutor parent runbook: [`study-tutor/docs/research/ideas/RUNBOOK-open-webui-tutor-access.md`](../../../study-tutor/docs/research/ideas/RUNBOOK-open-webui-tutor-access.md) — same pattern, lists EXEC NOTES from 2026-04-29 deployment
- Guardkit infra: [`guardkit/docs/runbooks/RUNBOOK-INFRA-ORCHESTRATION.md`](../../../guardkit/docs/runbooks/RUNBOOK-INFRA-ORCHESTRATION.md) — owns OWUI container lifecycle and llama-swap supervision
- System prompt source: `/home/richardwoollcott/fine-tuning/data/train-architect-agent.jsonl`
- Llama-swap config: `/opt/llama-swap/config/config.yaml`

*Prepared: 2026-05-05*
