# The bundled recruiter seat — ship the office's brain inside the office

## One-minute version

The office needs a small AI model (the "recruiter") to draft its configuration in conversation with
the owner. Instead of asking the owner to install an AI engine, **the engine ships inside the
office**. You run one command:

```bash
docker compose up
```

...and two things start together: the **office**, and its **seat** — a tiny web service
(`llama.cpp`'s `llama-server`, one small binary) that runs the tuned 4-billion-parameter model and
answers over a standard OpenAI-style API. The office talks to the seat over a private network on the
same machine. The owner never learns the words "vLLM", "Ollama", or "inference engine" — the engine
is invisible plumbing.

**One mental model:** the seat is a light-switch on the wall — you flip `docker compose up` and the
brain is on. This folder is that light-switch, wired.

## Jargon, defined once

- **GGUF** — the single-file format the model ships as (`llama.cpp`'s format). Ours is 2.4 GB.
- **seat** — the service that runs the model and answers questions over an API. Here it is
  `llama-server`.
- **Q4_K_M** — the model is *quantized* (compressed to 4-bit) so it runs on a laptop. This is the
  "4B Q4" you'll see mentioned.
- **digest pin** (`@sha256:...`) — we name the exact engine image by its fingerprint, not a moving
  tag, so the same bytes run every time.
- **loopback / OPENAI_BASE_URL** — how the office is told where its model lives (see "The one wire").

## What's in this folder

| File | What it is |
|---|---|
| `docker-compose.yml` | the bundled seat (CPU, runs anywhere) + a stub `office` service showing the one wire |
| `docker-compose.gpu.yml` | optional override to use an NVIDIA GPU (never required) |
| `fetch-model.sh` | the sha256-verified "download the model on first start" script (a documented option) |
| `gguf-manifest.json` | the model's fingerprint, provenance, and the backup-gap note |
| `speed-measurement.md` | measured first-token + full-turn latency, GPU and CPU |
| `llama-swap-seat-STAGED.md` | the Spark seat entry for Rich's re-sit (staged, not applied) |
| `latency-{gpu,cpu}.json` | the raw measurement evidence |

## Step 1 — Getting the model into the volume

The model (the GGUF) is **private** and is **not** in this folder. It lives on the Spark at
`~/fine-tuning/recruiter-tune/output/recruiter-qwen3-4b/gguf_gguf/qwen3-4b-instruct-2507.Q4_K_M.gguf`.
Two ways to put it where the seat can read it (the seat reads `/models` inside a named Docker volume
called `recruiter-model`):

**Option A — place it yourself (works today, no external host needed).** Copy the GGUF onto the
target machine, then load it into the volume and check its fingerprint:

```bash
# 1. create the volume and copy the file in (rename to the bundle name the compose expects)
docker volume create recruiter-model
docker run --rm -v recruiter-model:/models -v "$PWD":/src alpine \
  sh -c 'cp /src/qwen3-4b-instruct-2507.Q4_K_M.gguf /models/recruiter-qwen3-4b-Q4_K_M.gguf'

# 2. verify the fingerprint — MUST print: ...  OK
docker run --rm -v recruiter-model:/models alpine \
  sh -c 'echo "c13c3f2e3bce98d2115990786cd3c11dc73abad3b3b23ed37fe92e95879e234d  /models/recruiter-qwen3-4b-Q4_K_M.gguf" | sha256sum -c -'
```

**Option B — download on first start (needs a URL).** When the GGUF is published somewhere the
machine can reach, `fetch-model.sh` downloads it into the volume and verifies the fingerprint before
the seat starts (a bad or half-downloaded file is refused). See the header of `fetch-model.sh` for
the small init-service block to add. **Not wired by default** — see "The backup gap" below for why.

## Step 2 — Start it

```bash
docker compose up            # CPU — runs on any machine
```

This starts the **seat** (the `office` service in the compose is a wiring reference, held behind a
profile so a placeholder image can't break the default run — see "The one wire"). The seat reports
healthy once the model is loaded (the compose healthcheck waits for it). Confirm it answers:

```bash
curl -s http://localhost:8080/v1/models   # only if you published 8080; by default the seat is
                                          # internal-only, reachable by the office over the network
```

To ship it for real, copy the `seat` service and the `OPENAI_BASE_URL` line into your actual client
office compose — then `docker compose up` brings the office and its brain up together. On a GPU
machine, see "Using a GPU" below.

## The one wire (how the office finds the seat)

The office resolves its model endpoint with this rule (deckhand's resolver): the config says
`model.endpoint: loopback`, which means "use the `OPENAI_BASE_URL` environment variable if it's
set". The compose sets it to the seat:

```yaml
OPENAI_BASE_URL: "http://seat:8080/v1"
```

That is the entire integration. `OPENAI_API_KEY` is set to `local` (the seat ignores it, but the
client library needs a non-empty value).

### The egress-fact wrinkle (read this — it is deliberate)

Because `seat` is a service **name** (not `localhost` / `127.0.0.1`), the office resolves this as a
**non-loopback** endpoint and records it as an **egress fact** in every ledger event. That fact is
**true and correct**: the seat is a separate container. But the traffic **never leaves this host** —
it stays on the private compose network. This is the same honest posture the estate already uses for
any self-hosted non-loopback seat; the office surfaces "the model is a URL" truthfully rather than
pretending the seat is in-process. (If you want it to read as pure loopback, put the office and seat
in one network namespace so the office reaches the seat at `127.0.0.1` — a coupling most deployments
don't need.)

## Using a GPU (optional, never required)

CPU is the default and is fully functional (see `speed-measurement.md`). On an NVIDIA machine with
the `nvidia-container-toolkit` installed, add the GPU override:

```bash
# preflight — must list your GPU; if it doesn't, stay on CPU:
docker run --rm --gpus all \
  ghcr.io/ggml-org/llama.cpp:server-cuda@sha256:c1ddeb6d30932ddd9ddff962cb62dbc5450cd99d8e82c8c20de2fd1f99fde85b \
  nvidia-smi -L

# then bring it up with the override:
docker compose -f docker-compose.yml -f docker-compose.gpu.yml up
```

If the preflight fails, plain `docker compose up` (CPU) is the graceful fallback. The office works
either way; GPU only makes each drafting turn faster.

### macOS note

Docker containers on macOS **cannot reach Apple Metal** — a GPU override does nothing there, and CPU
in the Linux VM is the only in-container path. For a native Metal-accelerated Mac experience, the
escape hatch is **llamafile** (the model + engine as one double-clickable file). Evaluate that at the
MacBook stranger test; it is not part of this Docker bundle.

## Refreshing the pinned image

The engine images are pinned by digest in the compose files. To re-resolve the current digest for a
tag (e.g. after a llama.cpp release you want to adopt), from any machine with `curl`:

```bash
TOKEN=$(curl -s "https://ghcr.io/token?scope=repository:ggml-org/llama.cpp:pull&service=ghcr.io" \
  | python3 -c "import json,sys;print(json.load(sys.stdin)['token'])")
curl -sI -H "Authorization: Bearer $TOKEN" \
  -H "Accept: application/vnd.oci.image.index.v1+json" \
  https://ghcr.io/v2/ggml-org/llama.cpp/manifests/server | grep -i docker-content-digest
# repeat with .../manifests/server-cuda for the GPU image
```

Pinned at packaging time (2026-07-22):
- `ghcr.io/ggml-org/llama.cpp:server` → `sha256:6c9257ee7187fd01bb479a9a3142e59c3d4f37bb6c3fc4c12326bcffcbfcf2ba`
- `ghcr.io/ggml-org/llama.cpp:server-cuda` → `sha256:c1ddeb6d30932ddd9ddff962cb62dbc5450cd99d8e82c8c20de2fd1f99fde85b`

## The backup gap (say it plainly)

**There is no off-box backup of this model yet.** The GGUF exists only on the Spark. If that disk is
lost, the model must be re-quantized from the merged weights (also Spark-only) or re-trained. This is
the estate's known GGUF-backup gap. It is also why `fetch-model.sh` (Option B) is documented but not
wired: there is no hosted URL to fetch from yet. Closing the gap — publishing the GGUF as a verified
release asset or to the NAS sink — is the prerequisite for the zero-manual-step download path and for
any real client ship. Until then, Option A (place it yourself, verify the fingerprint) is the path.

## What this bundle does and does not settle

- **Settled:** the office comes up with its brain via `docker compose up`; the engine is invisible;
  the model serves faithfully (measured — no template leak); speed is recorded, CPU and GPU.
- **Not settled here:** whether the model is *good enough* to hire. That is **Rich's attended,
  unlabelled re-sit** on the four banked sessions plus the smuggled-egress probe, and the freeze of
  a `baseline.json` — his signed act, using the seat staged in `llama-swap-seat-STAGED.md`. Fast and
  faithful is necessary, not sufficient.
