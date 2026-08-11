#!/usr/bin/env python3
"""Bake-off runner — drives ONE candidate over the nine pre-declared inputs.

Usage:
  python3 run_bakeoff.py --candidate T2 --endpoint http://localhost:9000/v1 \
      --model product-owner-agent
  python3 run_bakeoff.py --candidate T1 --endpoint http://localhost:4000/v1 \
      --model deepseek --temperature 1.0 --top-p 1.0 --max-tokens 16384

Discipline (per PREDECLARATION.md):
- Inputs are verified against MANIFEST.sha256 before anything runs; mismatch aborts.
- ONE generation per input. A response that arrives (even empty/garbage) is banked
  and never regenerated. Only a pure transport failure (zero bytes of completion
  received: connection refused/timeout) earns ONE retry — no content was seen, so
  nothing is being cherry-picked.
- Every response is stamped: request SHA, params, usage, timing, server /models probe.
- T2 sends NO sampling overrides: the production seat's own defaults ARE the baseline.
"""

import argparse
import hashlib
import json
import time
import urllib.request
import urllib.error
from pathlib import Path

HERE = Path(__file__).parent
INPUTS = HERE / "inputs"


def http_json(url, payload=None, timeout=1800):
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode() if payload is not None else None,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def verify_manifest():
    manifest = (INPUTS / "MANIFEST.sha256").read_text().strip().splitlines()
    for line in manifest:
        sha, name = line.split(None, 1)
        actual = hashlib.sha256((INPUTS / name.strip()).read_bytes()).hexdigest()
        if actual != sha:
            raise SystemExit(f"FATAL: {name} sha mismatch — inputs changed after pre-declaration")
    return len(manifest)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--candidate", required=True, choices=["T1", "T2"])
    ap.add_argument("--endpoint", required=True)
    ap.add_argument("--model", required=True)
    ap.add_argument("--temperature", type=float, default=None)
    ap.add_argument("--top-p", type=float, default=None)
    ap.add_argument("--max-tokens", type=int, default=None)
    args = ap.parse_args()

    n = verify_manifest()
    print(f"manifest verified ({n} inputs)")

    out_dir = HERE / "responses" / args.candidate
    out_dir.mkdir(parents=True, exist_ok=True)

    try:
        models = http_json(f"{args.endpoint}/models", timeout=30)
    except Exception as e:
        models = {"probe_error": str(e)}
    (out_dir / "models_probe.json").write_text(json.dumps(models, indent=2))

    for f in sorted(INPUTS.glob("*.json")):
        if f.name == "MANIFEST.sha256":
            continue
        payload = json.loads(f.read_text())
        bid = payload["bakeoff_id"]
        out_file = out_dir / f"{bid}.json"
        if out_file.exists():
            print(f"{bid}: already banked — never regenerated, skipping")
            continue
        body = {"model": args.model, "messages": payload["messages"]}
        if args.temperature is not None:
            body["temperature"] = args.temperature
        if args.top_p is not None:
            body["top_p"] = args.top_p
        if args.max_tokens is not None:
            body["max_tokens"] = args.max_tokens

        req_sha = hashlib.sha256(json.dumps(body, sort_keys=True).encode()).hexdigest()
        t0 = time.time()
        resp, transport_error = None, None
        for attempt in (1, 2):
            try:
                resp = http_json(f"{args.endpoint}/chat/completions", body)
                break
            except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
                transport_error = f"attempt {attempt}: {e}"
                print(f"{bid}: transport failure ({e}); {'one retry' if attempt == 1 else 'banking as failed'}")
                time.sleep(10)
        elapsed = time.time() - t0

        record = {
            "bakeoff_id": bid,
            "candidate": args.candidate,
            "model": args.model,
            "endpoint": args.endpoint,
            "request_sha256": req_sha,
            "params": {k: body.get(k) for k in ("temperature", "top_p", "max_tokens")},
            "elapsed_seconds": round(elapsed, 1),
            "transport_error": transport_error if resp is None else None,
            "response": resp,
            "content": (resp["choices"][0]["message"].get("content") if resp else None),
            "usage": (resp.get("usage") if resp else None),
            "timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }
        out_file.write_text(json.dumps(record, indent=2))
        n_out = len(record["content"] or "")
        print(f"{bid}: banked ({elapsed:.0f}s, {n_out} chars)")

    print("run complete")


if __name__ == "__main__":
    main()
