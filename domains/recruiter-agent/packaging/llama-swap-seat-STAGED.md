# STAGED — the Spark llama-swap seat entry for the recruiter re-sit (DO NOT APPLY)

**Status: STAGED, not applied.** This is the exact config block + apply steps for the recruiter
tune's re-sit seat on spark-fcf6's llama-swap. **Applying it is Rich's ceremony act, not this
lane's** — the fence is explicit: the Spark's llama-swap service and its config are untouched until
the re-sit. Nothing below has been run. It is modeled verbatim on the resident-seat schema
(`/opt/llama-swap/config/config.yaml`) and the DCL probe-seat precedent (RUNBOOK-dcl-fine-tune §6.1).

## Why a staged seat at all

The re-sit needs the tuned model reachable by an alias the recruiter seed config can name
(`model_id: recruiter`), on the same `:9000` OpenAI endpoint the estate already uses. The tune is a
**private fine-tune**, so it deliberately does **not** join the public, all-open-model fleet
(`config.yaml`'s stated contract: "no fine-tunes … a viewer can replicate the whole box"). It is an
**on-demand** seat (ttl 1800): it loads when the exam calls it and unloads when idle. At ~2.5 GiB
Q4_K_M it co-resides with the always-on fleet trivially (fleet ~71 GB + 2.5 GB ≪ ~115 GB ceiling),
so it needs **no `matrix.set` membership** and never evicts a fleet member.

## Operator steps at the ceremony (Rich, or an operator at his word)

1. **Copy the GGUF beside the other models** (keep it out of the repo; private):
   ```bash
   mkdir -p /opt/llama-swap/models/recruiter-4b-tuned
   cp ~/fine-tuning/recruiter-tune/output/recruiter-qwen3-4b/gguf_gguf/qwen3-4b-instruct-2507.Q4_K_M.gguf \
      /opt/llama-swap/models/recruiter-4b-tuned/recruiter-qwen3-4b-Q4_K_M.gguf
   # integrity check — must print OK:
   echo "d2c0e5c378653cd5b8d324847ff7678bfa2b6ba2c057bbc504b626c980762c7e  /opt/llama-swap/models/recruiter-4b-tuned/recruiter-qwen3-4b-Q4_K_M.gguf" | sha256sum -c -
   ```
2. **Back up the config first** (the house discipline — dated `.bak`):
   ```bash
   cp /opt/llama-swap/config/config.yaml \
      /opt/llama-swap/config/config.yaml.bak-$(date +%Y%m%d)-pre-recruiter-seat
   ```
3. **Add the model block** below under `models:` (a sibling of `workhorse`/`coach`). Do **not** add
   it to any `matrix.sets` entry and do **not** add it to the `hooks.on_startup.preload` list — it
   is on-demand only.
4. **Reload the user service** (no sudo):
   ```bash
   systemctl --user restart llama-swap
   ```
5. **Point the recruiter seed at it** for the exam — the one knob, as designed:
   `seed/agents/recruiter/config.yaml` → `model.model_id: recruiter`, and the seat resolves on the
   estate's `:9000` (a non-loopback endpoint = a recorded egress fact, the same posture the
   2026-07-21 sitting used with `workhorse`).
6. **After the ceremony**, if the seat was temporary: remove the block (or leave it — it is
   on-demand and idle-unloads), restore from the `.bak` if you prefer a clean config, and
   `systemctl --user restart llama-swap`.

## The model block (paste under `models:`)

```yaml
  # ---------------------------------------------------------------------------
  # RECRUITER (PRIVATE FINE-TUNE) — recruiter-qwen3-4b Q4_K_M, the drafting-clerk
  # tune. On-demand (ttl 1800), co-resides with the fleet (~2.5 GB). NOT part of
  # the public replicable fleet and NOT in any matrix.set / preload — a private
  # adapter's serve seat, added only for the owner's re-sit ceremony.
  # Flags mirror the SHIPPED bundled seat (packaging/docker-compose.yml) exactly,
  # so the re-sit tests what clients get: no --jinja (the recruiter never
  # tool-calls; the embedded stock Qwen3-2507 non-thinking template is applied
  # by default — verified clean at serve, no <tool_call>/<think> leak).
  # ---------------------------------------------------------------------------
  "recruiter":
    cmd: >
      /usr/local/bin/llama-server
      --port ${PORT}
      --host 0.0.0.0
      --model /opt/llama-swap/models/recruiter-4b-tuned/recruiter-qwen3-4b-Q4_K_M.gguf
      --alias recruiter
      --ctx-size 4096
      --threads 16
      -ngl 999
      --no-mmap
      --flash-attn on
    checkEndpoint: /health
    ttl: 1800                # on-demand: auto-unload after 30 min idle
    concurrencyLimit: 2
    aliases:
      - "recruiter-qwen3-4b"
      - "recruiter-4b-tuned"
```

## Notes / honest caveats

- **`-ngl 999` (full GPU offload)** — the ceremony runs on the Spark's GPU (Rich's model-placement
  ruling: "model placement = Spark"). GPU latency measured ~26 ms TTFT / ~77 tok/s
  (`packaging/speed-measurement.md`) — the "super quick" feel.
- **`--ctx-size 4096`** matches the shipped bundle default. If an exam item is a long multi-turn
  authoring walk that approaches the ceiling, raise it (decode tok/s is unchanged; only max
  conversation length and long-prompt TTFT move).
- **`--no-mmap` / `--flash-attn on`** are the house GB10 conventions (mmap is slow on unified
  memory). The bundled client seat omits them because a client box is not a GB10 — that is the one
  intentional flag difference between this Spark seat and the portable client compose, and it does
  not change what the model emits, only how fast the Spark serves it.
- This seat is the **quality-leg** vehicle. The verdict is Rich's unlabelled re-sit on the four
  banked sessions + `probe-smuggled-egress`, and the freeze of a `baseline.json` — his signed act.
```
