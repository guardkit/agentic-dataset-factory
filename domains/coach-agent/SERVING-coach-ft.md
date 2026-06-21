# Serving the fine-tuned Coach + running the "beats base" eval

What the serving-contract verification (2026-06-19) found, and how to wire the fine-tune in.

## What I verified against the live stack

| Item | Finding | Consequence |
|---|---|---|
| **Fence** | `coach-verdict.gbnf` `code-fence ::= "```json" ws verdict-obj ws "```"` — the ```` ```json ```` fence **is kept** | `prepare_coach_sft.py` default (`--fence`) is correct; do **not** use `--no-fence` |
| **Verdict schema** | grammar **requires** `{ "task_id":str, "turn":int, "decision":"approve"|"feedback", … }` as the first three keys, in order (matches `coach_output_parser.py` + `_validate_coach_decision`) | the harvested data leads with `decision` and has **no task_id/turn** — fixed by `prepare_coach_sft.py --coachsplit-schema` (ON by default) |
| **How the grammar is applied** | **per-request on the toolless synthesis call** (COACHSPLIT). `coach_grammar.py`: toolless+grammar = valid; tool-bound+grammar = HTTP 400. The server block has **no** `--grammar-file` | the model block needs no `--grammar-file`; the orchestrator threads the grammar in. Eval must hit the endpoint **toolless** + pass `grammar` in the request body |
| **Serving quant** | live `gemma4-coach` runs **UD-Q4_K_XL** (`gemma-4-26B-A4B-it-UD-Q4_K_XL.gguf`) | confirms the brief — export/serve UD-Q4_K_XL (q4_k_m interim), never q4_0 |
| **Reasoning posture** | live base uses `--reasoning auto` + grammar (free reasoning prefix → forced final verdict). Comment notes the base 26B-A4B sometimes reasons 49,720 chars with **no** verdict — the reason to fine-tune | the fine-tune is trained to go straight to the verdict (non-thinking) → serve with `--reasoning off` (matched) or `auto` (grammar still catches it) |

**Why this matters:** without `--coachsplit-schema`, a Coach trained on the raw corpus emits
`{"decision":…}` and the COACHSPLIT parser/grammar **reject it**. This is the train==serve
alignment the HANDOFF flagged — now resolved in data-prep. (Reconcile the injected prompt
wording in `to_coachsplit_schema` with guardkit's actual `HarnessAdapter.invoke_synthesis`
prompt if it differs — the grammar fixes *structure*, the prompt supplies the *values*.)

## 0. Post-train serving verification (2026-06-20 — RESOLVED)

Tested the trained `q4_k_m` GGUF served standalone (`llama-server --reasoning off --jinja`,
port 8123):

- **No token leaks (the #7 question — PASS):** with `--reasoning off` the model emits a clean
  fenced ```` ```json ```` verdict immediately — **no `<|channel>thought` / `<|turn>` leakage**.
  The [G2] empty-thought-block concern does not materialise at serve.
- **Schema training took (PASS):** given the COACHSPLIT identity in the prompt (the suffix
  `prepare_coach_sft.py --coachsplit-schema` adds), the model emits the exact contract and
  **echoes the right values**: `{"task_id":"TASK-RLY-001","turn":1,"decision":"approve",…}`.
  Without the identity it falls back to `decision`-first (still valid JSON). ⇒ **the orchestrator's
  synthesis prompt must carry task_id/turn** (it does) for the parser-valid schema.
- **Grammar field caveat (OPEN):** passing `grammar` in the `/v1/chat/completions` (and a short
  `/completion`) body did **not** visibly force task_id-first in a short generation — the model's
  natural block satisfies the grammar's free `prefix` rule. Since the model already emits the
  correct schema from the prompt identity, this is a backstop, not load-bearing — but confirm the
  exact path COACHSPLIT's `invoke_synthesis` uses to apply the grammar before relying on it in prod.

## 1. Place the fine-tuned GGUF

After the full run + export (RUNBOOK Phase 3.5):

```bash
mkdir -p /opt/llama-swap/models/coach-ft
# from the training output (best int4: build true UD-Q4_K_XL; q4_k_m is the interim stand-in)
cp ~/fine-tuning/output/coach-gemma4-26b-moe/gguf/*.gguf \
   /opt/llama-swap/models/coach-ft/coach-gemma4-26b-moe.Q4_K_M.gguf
```

## 2. llama-swap model block (add under `models:` in /opt/llama-swap/config/config.yaml)

Cloned from the live `gemma4-coach` block — same Coach posture, only the model + alias change.
**Apply safely** (the config has a long history; back up + restart via systemd, never `pkill`+`nohup`):

```bash
cp /opt/llama-swap/config/config.yaml \
   /opt/llama-swap/config/config.yaml.bak-$(date +%Y%m%d-%H%M%S)-pre-coach-ft
# paste the block below under models:, then:
systemctl --user restart llama-swap.service
```

```yaml
  # AUTOBUILD COACH — FINE-TUNED Gemma-4-26B-A4B MoE (coach LoRA, merged→GGUF).
  # Same posture as gemma4-coach (the base substrate); this variant is trained to emit
  # the COACHSPLIT verdict directly (closes the "reasons forever, no verdict" F17 gap).
  # Grammar is applied per-request by the orchestrator's toolless synthesis call — NOT here.
  "coach-ft":
    cmd: >
      /home/richardwoollcott/llama.cpp-new/build/bin/llama-server
      --port ${PORT}
      --host 0.0.0.0
      --model /opt/llama-swap/models/coach-ft/coach-gemma4-26b-moe.Q4_K_M.gguf
      --alias coach-ft
      --ctx-size 98304
      --batch-size 2048
      --ubatch-size 2048
      --threads 16
      -ngl 999
      --no-mmap
      --flash-attn on
      --cache-type-k q8_0
      --cache-type-v q8_0
      --jinja
      --reasoning off
      --temp 0.1
      --top-p 0.9
      -np 1
    checkEndpoint: /health
    ttl: 0
    concurrencyLimit: 2
    aliases:
      - "autobuild-coach-ft"
      - "coach_test_ft"
```

Notes:
- `--reasoning off` matches the non-thinking training posture (the fine-tune was trained to go
  straight to the verdict). If verdict-emission regresses, try `--reasoning auto` (the grammar's
  free-prefix tolerates a reasoning preamble) — single-flag change + restart.
- `--jinja` uses the chat template embedded in the GGUF by Unsloth's export. Verify the
  exported template matches train time (RUNBOOK smoke-test #7 — the export→grammar-serve
  round-trip). If the GGUF template misbehaves, point `--chat-template-file` at a coach jinja.
- To make the fine-tune the autobuild Coach, repoint the orchestrator's per-role override
  (TASK-HMIG-013 AC-004, `model=gemma4:26b`) to `coach-ft`, or move the relevant aliases here
  from `gemma4-coach`. That's a guardkit-side change — don't move them silently.

## 3. Run the "beats base" eval (matches the toolless+grammar serving posture)

Both models through the same endpoint, **with the grammar** (so the comparison reflects how the
Coach is actually served), greedy:

```bash
python domains/coach-agent/eval_coach.py \
  --endpoint http://localhost:8080/v1 \
  --model coach-ft \
  --base-model gemma4-coach \
  --grammar /opt/llama-swap/grammars/coach-verdict.gbnf \
  --report ~/coach-dataset/curated/eval_report.json
```

The harness prints, per model, on the 76-row **held-out** set: parse-rate, correct-verdict
rate, and **false-approval rate** (the anti-rubber-stamp metric), plus the in-train symptom
probes (`hard_cases` + `relabelled`) separately. It ends with a `BEATS-BASE VERDICT` line:
**win = correct-verdict ↑ AND false-approval ↓ vs base.**

Caveats baked into the harness:
- gold is taken from the reference **completion**, not the metadata `decision` (auto-corrects
  the mislabelled `path-string-mismatch` trap → gold `approve`).
- one `hard_case` (`TASK-BDDW-009 ReqnrollPlugin.discover`) has malformed source JSON — fix it
  in `hard_cases.jsonl` (trailing `}`) or it stays a bad probe; `prepare_coach_sft.py
  --drop-malformed` removes it from training.
- with `--grammar`, the base model is *forced* into a valid verdict shape too — so the
  comparison isolates **judgment** (correct decision), not formatting. That's the right test:
  the fine-tune's job is better verdicts, the grammar already guarantees the shape.
